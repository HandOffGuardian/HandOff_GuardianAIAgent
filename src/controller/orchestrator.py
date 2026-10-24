"""Coordinate handoff components without owning their domain logic.

The mappings used here are a temporary boundary until the shared contracts
are implemented. Component methods are injected and are expected to expose
``extract``, ``collect``, ``evaluate``, and ``report`` respectively.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


class Orchestrator:
    """Run claim extraction, evidence collection, evaluation, and reporting."""

    def __init__(
        self,
        claim_extractor: Any,
        evidence_agent: Any,
        evaluator: Any,
        reporter: Any,
        max_retries: int = 2,
    ) -> None:
        if not isinstance(max_retries, int) or isinstance(max_retries, bool):
            raise TypeError("max_retries must be an integer")
        if not 0 <= max_retries <= 2:
            raise ValueError("max_retries must be between 0 and 2")
        self.claim_extractor = claim_extractor
        self.evidence_agent = evidence_agent
        self.evaluator = evaluator
        self.reporter = reporter
        self.max_retries = max_retries

    def run(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Process one handoff and return a decision/result mapping.

        Expected request keys are ``handoff_id``, ``account_id``, and
        ``source_text``. Each component result is validated before it is
        passed downstream. Only explicit evaluator clearance can produce a
        CLEAR disposition.
        """
        result: dict[str, Any] = {
            "disposition": "ESCALATE",
            "handoff_id": None,
            "account_id": None,
            "claims": [],
            "evidence": [],
            "evaluation": None,
            "diagnostics": [],
            "attempts": {},
            "report": None,
        }

        if not isinstance(request, Mapping):
            result["diagnostics"].append({"component": "input", "error": "malformed_request"})
            return self._report(result)

        result["handoff_id"] = request.get("handoff_id")
        result["account_id"] = request.get("account_id")
        if not all(
            isinstance(request.get(key), str) and request[key].strip()
            for key in ("handoff_id", "account_id", "source_text")
        ):
            result["diagnostics"].append({"component": "input", "error": "missing_or_invalid_required_field"})
            return self._report(result)
        metadata = request.get("metadata", {})
        if not isinstance(metadata, Mapping):
            result["diagnostics"].append({"component": "input", "error": "malformed_metadata"})
            return self._report(result)

        claims_response, failed = self._invoke(
            "claim_extractor",
            lambda **kwargs: self.claim_extractor.extract(request=deepcopy(kwargs["request"])),
            result,
            request=dict(request),
        )
        if failed:
            return self._report(result)
        claims = claims_response.get("claims") if isinstance(claims_response, Mapping) else claims_response
        if not isinstance(claims, list) or any(
            not isinstance(claim, Mapping) or not claim for claim in claims
        ):
            self._malformed(result, "claim_extractor")
            return self._report(result)
        result["claims"] = claims

        evidence_response, failed = self._invoke(
            "evidence_agent",
            lambda **kwargs: self.evidence_agent.collect(
                account_id=kwargs["account_id"],
                claims=deepcopy(kwargs["claims"]),
                metadata=deepcopy(kwargs["metadata"]),
            ),
            result,
            account_id=request["account_id"],
            # Each stage gets a private copy; injected agents may mutate inputs.
            claims=claims,
            metadata=dict(metadata),
        )
        if failed:
            return self._report(result)
        if (
            not isinstance(evidence_response, Mapping)
            or not isinstance(evidence_response.get("evidence"), list)
            or any(
                not isinstance(item, Mapping) or not item
                for item in evidence_response["evidence"]
            )
        ):
            self._malformed(result, "evidence_agent")
            return self._report(result)

        evidence = evidence_response["evidence"]
        result["evidence"] = evidence  # retain evidence records and provenance as returned
        missing = evidence_response.get("missing_mandatory", [])
        conflicts = evidence_response.get("conflicts", [])
        evidence_mandatory_satisfied = evidence_response.get("mandatory_satisfied")
        if (
            not isinstance(missing, list)
            or not isinstance(conflicts, list)
            or (evidence_mandatory_satisfied is not None and not isinstance(evidence_mandatory_satisfied, bool))
        ):
            self._malformed(result, "evidence_agent")
            return self._report(result)

        evaluation_response, failed = self._invoke(
            "evaluator",
            lambda **kwargs: self.evaluator.evaluate(
                claims=deepcopy(kwargs["claims"]),
                evidence_bundle=deepcopy(kwargs["evidence_bundle"]),
                context=deepcopy(kwargs["context"]),
            ),
            result,
            claims=claims,
            evidence_bundle=evidence_response,
            context=dict(request),
        )
        if failed:
            return self._report(result)
        if not isinstance(evaluation_response, Mapping):
            self._malformed(result, "evaluator")
            return self._report(result)
        result["evaluation"] = evaluation_response

        findings = evaluation_response.get("findings", [])
        if not isinstance(findings, list):
            self._malformed(result, "evaluator")
            return self._report(result)
        evaluator_missing = evaluation_response.get("missing_mandatory", [])
        evaluator_conflicts = evaluation_response.get("conflicts", [])
        mandatory_satisfied = evaluation_response.get("mandatory_satisfied")
        if (
            not isinstance(evaluator_missing, list)
            or not isinstance(evaluator_conflicts, list)
            or (mandatory_satisfied is not None and not isinstance(mandatory_satisfied, bool))
        ):
            self._malformed(result, "evaluator")
            return self._report(result)

        # Empty bundles and any unresolved mandatory/conflict signals fail closed.
        evidence_complete = (
            bool(evidence)
            and not missing
            and not evaluator_missing
            and evidence_mandatory_satisfied is not False
        )
        no_conflicts = not conflicts and not evaluator_conflicts
        if (
            evaluation_response.get("decision") == "CLEAR"
            and mandatory_satisfied is True
            and evidence_complete
            and no_conflicts
        ):
            result["disposition"] = "CLEAR"
        else:
            result["disposition"] = "ESCALATE"
            if not evidence:
                result["diagnostics"].append({"component": "evidence_agent", "error": "missing_evidence"})
            if missing or evaluator_missing or evidence_mandatory_satisfied is False or mandatory_satisfied is False:
                result["diagnostics"].append({"component": "evaluator", "error": "mandatory_evidence_unresolved"})
            if conflicts or evaluator_conflicts:
                result["diagnostics"].append({"component": "evaluator", "error": "conflicting_evidence_unresolved"})

        return self._report(result)

    def _invoke(self, name: str, operation: Any, result: dict[str, Any], **kwargs: Any) -> tuple[Any, bool]:
        attempts = 0
        while True:
            attempts += 1
            try:
                response = operation(**kwargs)
                result["attempts"][name] = attempts
                return response, False
            except Exception as exc:  # component boundary: report type, not potentially sensitive text
                retryable = getattr(exc, "transient", False) is True and getattr(exc, "safe_to_retry", False) is True
                if retryable and attempts <= self.max_retries:
                    continue
                result["attempts"][name] = attempts
                result["diagnostics"].append(
                    {
                        "component": name,
                        "error": "retry_exhausted" if retryable else "component_failure",
                        "exception_type": type(exc).__name__,
                    }
                )
                return None, True

    @staticmethod
    def _malformed(result: dict[str, Any], component: str) -> None:
        result["diagnostics"].append({"component": component, "error": "malformed_component_output"})

    def _report(self, result: dict[str, Any]) -> dict[str, Any]:
        try:
            # The reporter is a component boundary: it receives an isolated
            # snapshot so its mutations cannot affect the decision or evidence.
            reporter_input = deepcopy(result)
            report = self.reporter.report(reporter_input)
        except Exception as exc:  # do not turn reporting errors into a disposition change
            result["report_status"] = "failed"
            result["diagnostics"].append(
                {
                    "component": "reporter",
                    "error": "reporting_failure",
                    "exception_type": type(exc).__name__,
                }
            )
            return result

        if not isinstance(report, Mapping) or not report:
            result["report_status"] = "failed"
            result["diagnostics"].append(
                {"component": "reporter", "error": "malformed_report_output"}
            )
            return result

        try:
            result["report"] = deepcopy(dict(report))
        except Exception as exc:
            result["report_status"] = "failed"
            result["diagnostics"].append(
                {
                    "component": "reporter",
                    "error": "malformed_report_output",
                    "exception_type": type(exc).__name__,
                }
            )
            return result
        result["report_status"] = "success"
        return result
