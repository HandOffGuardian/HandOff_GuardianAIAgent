"""Orchestrator-facing, evidence-preserving reporter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from src.reporter.citation_verifier import CitationVerifier


def _plain(value: Any) -> Any:
    """Convert contract objects into values suitable for JSON/UI rendering."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


class HandoffReporter:
    """Build a deterministic report without changing evaluator decisions."""

    def report(self, result: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(result, Mapping):
            raise TypeError("orchestrator result must be a mapping")

        evidence = _plain(result.get("evidence", []))
        if not isinstance(evidence, list):
            evidence = []
        evaluation = _plain(result.get("evaluation"))
        if not isinstance(evaluation, Mapping):
            evaluation = {}

        disposition = result.get("disposition", "ESCALATE")
        if disposition not in {"CLEAR", "RETRY", "ESCALATE"}:
            disposition = "ESCALATE"
        findings = evaluation.get("findings", [])
        findings = findings if isinstance(findings, list) else []
        conflicts = evaluation.get("conflicts", [])
        conflicts = _plain(conflicts)
        conflicts = conflicts if isinstance(conflicts, list) else []
        diagnostics = _plain(result.get("diagnostics", []))
        diagnostics = diagnostics if isinstance(diagnostics, list) else []
        citation_items = [item for item in findings + conflicts if isinstance(item, Mapping)]
        cited_ids = sorted({
            evidence_id
            for item in citation_items
            for evidence_id in item.get("evidence_ids", [])
            if isinstance(evidence_id, str)
        })
        report = {
            "account_id": result.get("account_id"),
            "handoff_id": result.get("handoff_id"),
            "status": disposition,
            "risk_score": evaluation.get("risk_score"),
            "risk_level": evaluation.get("risk_level"),
            "summary": self._summary(disposition, findings, diagnostics),
            "findings": findings,
            "conflicts": conflicts,
            "evidence_ids": cited_ids,
            "evidence": evidence,
            "diagnostics": diagnostics,
            "attempts": _plain(result.get("attempts", {})),
            "recommended_actions": self._actions(disposition, findings),
            "verification_status": "NOT_CHECKED",
        }
        report["citations_verified"] = CitationVerifier.verify_citations(
            {
                "evidence_ids": cited_ids,
                "findings": findings,
                "conflicts": [item for item in conflicts if isinstance(item, Mapping)],
            },
            {"evidence": evidence},
        )
        if not report["citations_verified"]:
            report["summary"] += " Some referenced evidence IDs were not present in the collected records."
        return report

    @staticmethod
    def _summary(disposition: str, findings: list[Any], diagnostics: list[Any]) -> str:
        if diagnostics:
            return f"The investigation ended with {disposition}; one or more pipeline stages reported a problem."
        if disposition == "CLEAR":
            return "The evaluator found the required checks clear based on the collected evidence."
        if disposition == "RETRY":
            return "The evaluator requested another evidence retrieval before reaching a decision."
        if findings:
            return f"The evaluator identified {len(findings)} finding(s); the handoff is escalated for review."
        return "The handoff could not be cleared with the available pipeline result."

    @staticmethod
    def _actions(disposition: str, findings: list[Any]) -> list[str]:
        if disposition == "CLEAR":
            return ["Proceed with the handoff using the verified evidence shown above."]
        if disposition == "RETRY":
            return ["Retrieve the requested missing or stale evidence, then evaluate again."]
        if findings:
            return ["Review each blocking finding and resolve it at the source before handing off."]
        return ["Review the pipeline diagnostics and evidence availability before retrying the handoff."]
