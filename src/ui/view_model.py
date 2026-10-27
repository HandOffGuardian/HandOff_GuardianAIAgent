"""Presentation view model for the Handoff Guardian UI.

Pure functions that derive display state from the JSON-safe Orchestrator
result dictionary. Nothing here imports the backend or Streamlit, and nothing
here changes a decision: every value is read from fields the Orchestrator
actually returns (``attempts``, ``diagnostics``, ``report_status``, ``claims``,
``evidence``, ``evaluation``, ``report``). When a fact is not present in the
result, the derived status is ``unknown`` or ``not_run``; it is never guessed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Pipeline stages in the exact order the Orchestrator invokes them
# (src/controller/orchestrator.py). Keys match ``attempts`` / diagnostic
# ``component`` names. Roles describe the components as currently composed by
# src/controller/application.py.
STAGES: tuple[dict[str, str], ...] = (
    {
        "key": "claim_extractor",
        "name": "Claim Extractor",
        "role": "Extracts explicitly stated claims from the handoff text using NVIDIA Nemotron.",
        "icon": "extract",
    },
    {
        "key": "evidence_agent",
        "name": "Evidence Agent",
        "role": "Collects account evidence records with source provenance (fixture provider).",
        "icon": "evidence",
    },
    {
        "key": "evaluator",
        "name": "Evaluator",
        "role": "Applies policy rules to validated claims and evidence; decides CLEAR or ESCALATE.",
        "icon": "evaluate",
    },
    {
        "key": "reporter",
        "name": "Reporter",
        "role": "Produces a deterministic, evidence-cited investigation report.",
        "icon": "report",
    },
)

# Diagnostic codes that mean a component did not complete successfully.
FAILURE_ERRORS = frozenset(
    {
        "component_failure",
        "retry_exhausted",
        "malformed_component_output",
        "claim_validation_failed",
        "reporting_failure",
        "malformed_report_output",
    }
)

# Plain-language explanations of the Orchestrator's sanitized diagnostic codes.
DIAGNOSTIC_TEXT: dict[str, str] = {
    "malformed_request": "The request sent to the pipeline was not a valid mapping.",
    "missing_or_invalid_required_field": "A required field (handoff ID, account ID or handoff text) was missing or empty.",
    "malformed_metadata": "Request metadata was not a valid mapping.",
    "component_failure": "The component raised an error and did not complete.",
    "retry_exhausted": "The component failed transiently and the retry budget was exhausted.",
    "malformed_component_output": "The component returned output that did not match the expected contract.",
    "claim_validation_failed": "Extracted claims could not be validated against the collected evidence.",
    "missing_evidence": "No evidence records were found for this account.",
    "mandatory_evidence_unresolved": "Mandatory policy evidence is missing or unresolved.",
    "conflicting_evidence_unresolved": "Evidence sources conflict and the conflict is unresolved.",
    "reporting_failure": "The reporter raised an error; the disposition is unaffected.",
    "malformed_report_output": "The reporter returned malformed output; the disposition is unaffected.",
}

STATUS_LABELS: dict[str, str] = {
    "completed": "Completed",
    "warning": "Completed with warnings",
    "failed": "Failed",
    "not_run": "Not run",
    "unknown": "Not reported",
    "idle": "Awaiting run",
}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def diagnostics_for(result: Mapping[str, Any], component: str) -> list[Mapping[str, Any]]:
    """Return the diagnostics the Orchestrator attributed to ``component``."""
    return [
        d
        for d in _as_list(result.get("diagnostics"))
        if isinstance(d, Mapping) and d.get("component") == component
    ]


def describe_diagnostic(diagnostic: Mapping[str, Any]) -> str:
    code = str(diagnostic.get("error", ""))
    return DIAGNOSTIC_TEXT.get(code, "Diagnostic reported by the pipeline.")


def _stage_outputs(key: str, result: Mapping[str, Any]) -> list[str]:
    """Summaries built only from data present in the result."""
    claims = _as_list(result.get("claims"))
    evidence = _as_list(result.get("evidence"))
    evaluation = _as_map(result.get("evaluation"))
    report = _as_map(result.get("report"))
    out: list[str] = []
    if key == "claim_extractor":
        out.append(f"{len(claims)} claim{'s' if len(claims) != 1 else ''} extracted")
    elif key == "evidence_agent":
        sources = sorted({str(e.get("source")) for e in evidence if isinstance(e, Mapping) and e.get("source")})
        out.append(f"{len(evidence)} evidence record{'s' if len(evidence) != 1 else ''}")
        if sources:
            out.append("Sources: " + ", ".join(sources))
    elif key == "evaluator":
        validated = sum(
            1 for c in claims if isinstance(c, Mapping) and c.get("validation_status") == "validated"
        )
        if claims and any(isinstance(c, Mapping) and "validation_status" in c for c in claims):
            out.append(f"Claim validation: {validated} of {len(claims)} linked to evidence")
        if evaluation:
            findings = _as_list(evaluation.get("findings"))
            blocking = sum(1 for f in findings if isinstance(f, Mapping) and f.get("blocking"))
            if evaluation.get("decision") is not None:
                out.append(f"Evaluator decision: {evaluation.get('decision')}")
            out.append(f"{len(findings)} finding{'s' if len(findings) != 1 else ''} ({blocking} blocking)")
    elif key == "reporter" and report:
        verified = report.get("citations_verified")
        if verified is True:
            out.append("Citations verified against evidence")
        elif verified is False:
            out.append("Citations could not be verified")
        recs = _as_list(report.get("recommendations"))
        if recs:
            out.append(f"{len(recs)} recommendation{'s' if len(recs) != 1 else ''}")
    return out


def stage_states(result: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Derive one honest display state per pipeline stage.

    * ``completed`` — the stage appears in ``attempts`` (or, for the reporter,
      ``report_status == "success"``) and no failure diagnostic names it.
    * ``warning`` — completed, but a non-failure diagnostic names it.
    * ``failed`` — a failure diagnostic names the stage.
    * ``not_run`` — the pipeline reported attempts, and this stage is absent.
    * ``unknown`` — the result does not carry enough information.
    * ``idle`` — no investigation has been run in this session.
    """
    states: list[dict[str, Any]] = []
    if result is None:
        for index, stage in enumerate(STAGES, start=1):
            states.append({**stage, "index": index, "status": "idle", "label": STATUS_LABELS["idle"],
                           "attempts": None, "outputs": [], "diagnostics": []})
        return states

    attempts = result.get("attempts")
    has_attempts = isinstance(attempts, Mapping)
    attempts = attempts if has_attempts else {}

    for index, stage in enumerate(STAGES, start=1):
        key = stage["key"]
        diags = diagnostics_for(result, key)
        failed = any(d.get("error") in FAILURE_ERRORS for d in diags)
        count = attempts.get(key) if key != "reporter" else None

        if key == "reporter":
            report_status = result.get("report_status")
            if failed or report_status == "failed":
                status = "failed"
            elif report_status == "success":
                status = "completed"
            else:
                status = "unknown"
        elif failed:
            status = "failed"
        elif key in attempts:
            status = "warning" if diags else "completed"
        elif has_attempts:
            status = "not_run"
        else:
            status = "unknown"

        states.append(
            {
                **stage,
                "index": index,
                "status": status,
                "label": STATUS_LABELS[status],
                "attempts": count if isinstance(count, int) else None,
                "outputs": _stage_outputs(key, result) if status in ("completed", "warning") else [],
                "diagnostics": diags,
            }
        )
    return states


def evidence_citations(result: Mapping[str, Any]) -> dict[str, list[str]]:
    """Map evidence IDs to the claim IDs / finding codes that cite them."""
    cited: dict[str, list[str]] = {}
    for claim in _as_list(result.get("claims")):
        if isinstance(claim, Mapping):
            for eid in _as_list(claim.get("evidence_ids")):
                cited.setdefault(str(eid), []).append(f"Claim {claim.get('claim_id', '?')}")
    evaluation = _as_map(result.get("evaluation"))
    for finding in _as_list(evaluation.get("findings")):
        if isinstance(finding, Mapping):
            for eid in _as_list(finding.get("evidence_ids")):
                cited.setdefault(str(eid), []).append(f"Finding {finding.get('reason_code', '?')}")
    return cited


def summary_facts(result: Mapping[str, Any]) -> dict[str, Any]:
    """Collect top-level facts for the disposition summary."""
    evaluation = _as_map(result.get("evaluation"))
    report = _as_map(result.get("report"))
    findings = _as_list(evaluation.get("findings"))
    score = evaluation.get("risk_score") if evaluation else None
    return {
        # The Orchestrator defaults to ESCALATE; mirror that fail-closed default.
        "disposition": result.get("disposition") or "ESCALATE",
        "has_evaluation": bool(evaluation),
        "risk_score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
        "risk_level": evaluation.get("risk_level") or report.get("risk_level"),
        "policy_version": evaluation.get("policy_version") or report.get("policy_version"),
        "evaluated_at": evaluation.get("evaluated_at") or report.get("evaluated_at"),
        "citations_verified": report.get("citations_verified"),
        "findings": findings,
        "blocking_count": sum(1 for f in findings if isinstance(f, Mapping) and f.get("blocking")),
        "missing_mandatory": _as_list(evaluation.get("missing_mandatory")),
        "conflicts": _as_list(evaluation.get("conflicts")),
        "handoff_id": result.get("handoff_id"),
        "account_id": result.get("account_id") or report.get("account_id"),
        "failed_stages": [s["name"] for s in stage_states(result) if s["status"] == "failed"],
        "input_diagnostics": diagnostics_for(result, "input"),
    }
