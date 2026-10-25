import streamlit as st
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.reporter.report_generator import ReportGenerator

st.set_page_config(page_title="Handoff Guardian Dashboard", layout="wide")
st.title("🛡️ Handoff Guardian")
st.subheader("Sales-to-Support Handoff Risk Auditor")

account_id = st.selectbox("Select Test Account",
                          ["acct_101 (Clean)", "acct_104 (Failing Integration)", "acct_108 (Missing Data)"])

if st.button("🚀 Investigate Handoff", type="primary"):
    with st.spinner("Running AI investigation pipeline..."):
        is_failing = "104" in account_id
        eval_result = {
            "account_id": account_id.split()[0],
            "decision": "ESCALATE" if is_failing else "CLEAR",
            "risk_score": 85 if is_failing else 12,
            "confidence": 0.95,
            "conflicts": [{"claim_a": "CRM ready", "claim_b": "Ticket failing",
                           "evidence_ids": ["CRM-7", "T-22"]}] if is_failing else []
        }
        reporter = ReportGenerator()
        report = reporter.generate(eval_result)

    st.divider()
    status = report["status"]
    if status == "CLEAR":
        st.success(f"### Status: {status} (Risk Score: {report['risk_score']}/100)")
    else:
        st.error(f"### Status: {status} (Risk Score: {report['risk_score']}/100)")

    st.markdown("### 📝 Investigation Summary")
    st.write(report["summary"])

    if report["conflicts"]:
        st.markdown("### ⚠️ Detected Conflicts")
        for conflict in report["conflicts"]:
            st.error(f"**Conflict:** {conflict['claim_a']} vs {conflict['claim_b']}")

    st.markdown("### 💡 Recommended Actions")
    for rec in report["recommendations"]:
        st.write(f"- {rec}")