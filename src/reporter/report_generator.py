
from src.reporter.llm_provider import NightshiftLLMProvider
from src.reporter.templates import render_fallback_report


class ReportGenerator:
    def __init__(self):
        try:
            self.llm = NightshiftLLMProvider()
        except Exception:
            self.llm = None

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
            findings = evaluation_result.get("findings", [])
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

        return {
            "account_id": evaluation_result.get("account_id", "unknown"),
            "status": status if status in ("CLEAR", "ESCALATE") else "ESCALATE",
            "risk_score": evaluation_result.get("risk_score", 0),
            "summary": summary,
            "conflicts": evaluation_result.get("conflicts", []),
            "recommendations": self._get_recommendations(status),
        }

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
