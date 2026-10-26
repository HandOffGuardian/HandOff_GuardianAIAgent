"""Compatibility wrapper for the Reporter interface and legacy callers.

The Orchestrator calls ``report(result)``. Older repository code called
``generate(evaluation_result, evidence_bundle)``. Both entry points now use
the same deterministic, evidence-preserving reporter.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from src.reporter.report import HandoffReporter


class ReportGenerator:
    """Adapt the old generation signature to the current reporter contract."""

    def __init__(self, reporter: HandoffReporter | None = None) -> None:
        self._reporter = reporter or HandoffReporter()

    def report(self, result: Mapping[str, Any]) -> dict[str, Any]:
        """Implement the exact method expected by ``Orchestrator``."""
        return self._reporter.report(result)

    def generate(
        self,
        evaluation_result: Mapping[str, Any],
        evidence_bundle: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Keep the earlier API working while adapting it to the new report."""
        if not isinstance(evaluation_result, Mapping):
            raise TypeError("evaluation_result must be a mapping")

        evaluation = dict(evaluation_result)
        decision = evaluation.get("decision", evaluation.get("status", "ESCALATE"))
        if isinstance(decision, Enum):
            decision = decision.value
        if decision not in {"CLEAR", "RETRY", "ESCALATE"}:
            decision = "ESCALATE"

        bundle = evidence_bundle if isinstance(evidence_bundle, Mapping) else {}
        records = bundle.get("evidence", bundle.get("records", []))
        if not isinstance(records, list):
            records = []
        findings = evaluation.get("findings", [])
        if not isinstance(findings, list):
            findings = []

        result = {
            "account_id": evaluation.get("account_id"),
            "handoff_id": evaluation.get("handoff_id"),
            "disposition": decision,
            "evaluation": {
                "decision": decision,
                "risk_score": evaluation.get("risk_score"),
                "risk_level": evaluation.get("risk_level"),
                "findings": findings,
                "conflicts": evaluation.get("conflicts", []),
            },
            "evidence": records,
            "diagnostics": evaluation.get("diagnostics", []),
            "attempts": evaluation.get("attempts", {}),
        }
        report = self._reporter.report(result)
        report["conflicts"] = evaluation.get("conflicts", [])
        report["recommendations"] = report["recommended_actions"]
        return report
