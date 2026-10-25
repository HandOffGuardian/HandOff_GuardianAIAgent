from src.reporter.llm_provider import NightshiftLLMProvider
from src.reporter.templates import render_fallback_report


class ReportGenerator:
    def __init__(self):
        try:
            self.llm = NightshiftLLMProvider()
        except Exception:
            self.llm = None

    def generate(self, evaluation_result: dict, evidence_bundle: dict = None) -> dict:
        summary = ""
        if self.llm:
            summary = self.llm.summarize(evaluation_result)

        if not summary or "failed" in summary:
            summary = render_fallback_report(evaluation_result, evidence_bundle)

        return {
            "account_id": evaluation_result.get("account_id", "unknown"),
            "status": evaluation_result.get("decision", "UNKNOWN"),
            "risk_score": evaluation_result.get("risk_score", 0),
            "summary": summary,
            "conflicts": evaluation_result.get("conflicts", []),
            "recommendations": self._get_recommendations(evaluation_result.get("decision"))
        }

    def _get_recommendations(self, decision: str) -> list:
        if decision == "CLEAR":
            return ["Proceed with standard customer onboarding."]
        elif decision == "RETRY":
            return ["Query missing evidence sources."]
        elif decision == "ESCALATE":
            return ["Halt handoff immediately. Resolve open engineering tickets and CRM discrepancies."]
        return ["Perform manual review."]