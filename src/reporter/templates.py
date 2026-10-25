def render_fallback_report(evaluation_result: dict, evidence_bundle: dict = None) -> str:
    status = evaluation_result.get("decision", "UNKNOWN")
    risk_score = evaluation_result.get("risk_score", 0)
    conflicts = evaluation_result.get("conflicts", [])

    report_lines = [
        f"### Handoff Investigation Report",
        f"- **Status:** {status}",
        f"- **Risk Score:** {risk_score}/100",
        f"- **Confidence:** {evaluation_result.get('confidence', 0.0) * 100:.0f}%",
        f"\n#### Identified Conflicts:"
    ]

    if conflicts:
        for c in conflicts:
            report_lines.append(f"- *Claim A:* {c.get('claim_a')} vs *Claim B:* {c.get('claim_b')}")
    else:
        report_lines.append("- No material conflicts detected.")

    return "\n".join(report_lines)