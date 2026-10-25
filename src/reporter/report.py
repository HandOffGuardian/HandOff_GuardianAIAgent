
"""Adapter connecting the Orchestrator to the ReportGenerator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.reporter.report_generator import ReportGenerator
from src.reporter.templates import render_fallback_report


class Reporter:
    """Translate orchestrator results into reports without changing decisions."""

    def __init__(self, generator: ReportGenerator | None = None) -> None:
        self._generator = generator or ReportGenerator()

    def report(self, result: Mapping[str, Any]) -> dict[str, Any]:
        """Generate a report from the Orchestrator's result mapping."""
        if not isinstance(result, Mapping):
            raise TypeError("Reporter input must be a mapping")

        evaluation = result.get("evaluation")
        if isinstance(evaluation, Mapping):
            evaluation_data = dict(evaluation)
        else:
            evaluation_data = {}

        # The Orchestrator owns the authoritative disposition.
        disposition = result.get("disposition", "ESCALATE")
        if disposition not in ("CLEAR", "ESCALATE"):
            disposition = "ESCALATE"

        report_input = {
            **evaluation_data,
            "account_id": result.get("account_id", "unknown"),
            "decision": disposition,
            "risk_score": evaluation_data.get("risk_score", 0),
            "conflicts": evaluation_data.get("conflicts", []),
        }

        evidence_bundle = {
            "evidence": result.get("evidence", []),
        }

        try:
            generated = self._generator.generate(
                evaluation_result=report_input,
                evidence_bundle=evidence_bundle,
            )
        except Exception:
            # Reporting must not change the Orchestrator's decision.
            generated = None

        if not isinstance(generated, Mapping) or not generated:
            # Fall back to a deterministic report if report generation fails.
            summary = render_fallback_report(
                report_input,
                evidence_bundle,
            )
            generated = {
                "account_id": report_input["account_id"],
                "status": disposition,
                "risk_score": report_input["risk_score"],
                "summary": summary,
                "conflicts": report_input["conflicts"],
                "recommendations": self._fallback_recommendations(
                    disposition
                ),
            }

        report = dict(generated)

        # Never let a generated report override the authoritative decision.
        report["account_id"] = report_input["account_id"]
        report["status"] = disposition
        report["risk_score"] = report_input["risk_score"]
        report.setdefault("summary", "")
        report.setdefault("conflicts", report_input["conflicts"])
        report.setdefault(
            "recommendations",
            self._fallback_recommendations(disposition),
        )

        return report

    @staticmethod
    def _fallback_recommendations(disposition: str) -> list[str]:
        if disposition == "CLEAR":
            return ["Proceed with standard customer onboarding."]
        return [
            "Halt the handoff and manually review unresolved evidence "
            "or conflicts before proceeding."
        ]
