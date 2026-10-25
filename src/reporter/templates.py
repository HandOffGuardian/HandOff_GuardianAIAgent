
def render_fallback_report(
    evaluation_result: dict,
    evidence_bundle: dict = None,
) -> str:
    """Render a deterministic report that explains the evaluator's decision."""
    status = evaluation_result.get("decision", "UNKNOWN")
    risk_score = evaluation_result.get("risk_score", 0)
    confidence = evaluation_result.get("confidence", 0.0)
    conflicts = evaluation_result.get("conflicts", [])
    findings = evaluation_result.get("findings", [])
    missing_mandatory = evaluation_result.get("missing_mandatory", [])

    report_lines = [
        "### Handoff Investigation Report",
        f"- **Status:** {status}",
        f"- **Risk Score:** {risk_score}/100",
        f"- **Confidence:** {confidence * 100:.0f}%",
    ]

    # Explain why the handoff was escalated, even if no conflicts were
    # explicitly identified by the evaluator.
    blocking_findings = [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("blocking", False)
    ]

    if blocking_findings:
        report_lines.append("\n#### Blocking Findings")
        for finding in blocking_findings:
            reason = finding.get("reason_code", "UNSPECIFIED")
            description = finding.get("description") or reason
            report_lines.append(f"- **{reason}:** {description}")

    non_blocking_findings = [
        finding
        for finding in findings
        if isinstance(finding, dict) and not finding.get("blocking", False)
    ]

    if non_blocking_findings:
        report_lines.append("\n#### Additional Findings")
        for finding in non_blocking_findings:
            reason = finding.get("reason_code", "UNSPECIFIED")
            description = finding.get("description") or reason
            report_lines.append(f"- **{reason}:** {description}")

    if missing_mandatory:
        report_lines.append("\n#### Missing Mandatory Requirements")
        for requirement in missing_mandatory:
            report_lines.append(f"- {requirement}")

    report_lines.append("\n#### Identified Conflicts")

    if conflicts:
        for conflict in conflicts:
            if isinstance(conflict, str):
                report_lines.append(f"- {conflict}")
            elif isinstance(conflict, dict):
                claim_a = conflict.get("claim_a", "Unknown claim")
                claim_b = conflict.get("claim_b", "Unknown claim")
                report_lines.append(
                    f"- *Claim A:* {claim_a} vs *Claim B:* {claim_b}"
                )
            else:
                report_lines.append(f"- {str(conflict)}")
    else:
        report_lines.append("- No explicit conflicts were identified.")


    if status == "ESCALATE" and not blocking_findings and not missing_mandatory:
        report_lines.append(
            "\n#### Recommended Action\n"
            "- Keep the handoff on hold and manually review the escalation."
        )
    elif status == "CLEAR":
        report_lines.append(
            "\n#### Recommended Action\n"
            "- Proceed according to the approved handoff process."
        )
    elif blocking_findings or missing_mandatory:
        report_lines.append(
            "\n#### Recommended Action\n"
            "- Keep the handoff on hold until the blocking findings and "
            "mandatory requirements are resolved."
        )

    return "\n".join(report_lines)
