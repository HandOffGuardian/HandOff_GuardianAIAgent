
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

from src.reporter.citation_verifier import CitationVerifier
from src.reporter.llm_provider import NightshiftLLMProvider
from src.reporter.templates import render_fallback_report


class ReportGenerator:
    def __init__(self, llm_provider: Any = None, *, enable_llm: bool = True):
        if llm_provider is not None:
            self.llm = llm_provider
        elif enable_llm:
            try:
                self.llm = NightshiftLLMProvider()
            except Exception:
                self.llm = None
        else:
            self.llm = None

    def report(self, orchestration_result: Mapping[str, Any]) -> dict:
        """Implement the Orchestrator reporter interface from its result snapshot."""
        evaluation = orchestration_result.get("evaluation")
        evaluation = dict(evaluation) if isinstance(evaluation, Mapping) else {}
        evaluation["decision"] = orchestration_result.get("disposition", "ESCALATE")
        evaluation["account_id"] = orchestration_result.get("account_id") or "unknown"
        bundle = {"evidence": orchestration_result.get("evidence", [])}
        return self.generate(evaluation, bundle)

    def generate(self, evaluation_result: dict, evidence_bundle: dict = None) -> dict:
        status = evaluation_result.get("decision", "ESCALATE")
        summary = ""

        if self.llm:
            try:
                summary = self.llm.summarize(evaluation_result)
            except Exception:
                summary = ""

        if not summary or "failed" in summary.lower():
            summary = render_fallback_report(evaluation_result, evidence_bundle)
        else:
            # Ensure LLM summaries cannot silently omit blocking findings.
            findings = evaluation_result.get("findings") or []
            blocking_findings = [
                finding
                for finding in findings
                if isinstance(finding, dict) and finding.get("blocking", False)
            ]

            if blocking_findings:
                summary += "\n\n#### Evaluator Blocking Findings"
                for finding in blocking_findings:
                    reason = finding.get("reason_code", "UNSPECIFIED")
                    description = finding.get("description") or reason
                    line = f"- **{reason}:** {description}"
                    if line not in summary:
                        summary += "\n" + line

        findings = [self._finding_dict(item) for item in (evaluation_result.get("findings") or [])]
        evidence_records = (evidence_bundle or {}).get("evidence", [])
        report = {
            "account_id": evaluation_result.get("account_id", "unknown"),
            "status": status if status in ("CLEAR", "ESCALATE") else "ESCALATE",
            "risk_score": evaluation_result.get("risk_score", 0),
            "risk_level": evaluation_result.get("risk_level", "unknown"),
            "summary": summary,
            "conflicts": [self._finding_dict(x) for x in (evaluation_result.get("conflicts") or [])],
            "findings": findings,
            "evidence": evidence_records,
            "policy_version": evaluation_result.get("policy_version"),
            "evaluated_at": evaluation_result.get("evaluated_at"),
            "recommendations": self._get_recommendations(status),
        }
        report["citations_verified"] = CitationVerifier.verify_citations(report, evidence_bundle or {})
        if not report["citations_verified"]:
            report["summary"] += "\n\nEvidence references could not be verified; manual review is required."
        report["citations_verified"] = CitationVerifier.verify_citations(report, evidence_bundle or {})
        if not report["citations_verified"]:
            report["summary"] += "\n\nEvidence references could not be verified; manual review is required."
        return report

    @staticmethod
    def _finding_dict(item: Any) -> dict:
        if isinstance(item, Mapping):
            return dict(item)
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        return {"description": str(item), "evidence_ids": []}

    def _get_recommendations(self, decision: str) -> list:
        if decision == "CLEAR":
            return ["Proceed with standard customer onboarding."]
        elif decision == "RETRY":
            return ["Query missing evidence sources."]
        elif decision == "ESCALATE":
            return [
                "Halt the handoff immediately. Resolve blocking findings "
                "and missing mandatory evidence before proceeding."
            ]
        return ["Perform manual review."]
