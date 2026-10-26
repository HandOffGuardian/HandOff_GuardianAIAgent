"""Browser UI for running and inspecting the real handoff pipeline.

Launch from the repository root with:
    streamlit run src/reporter/ui/app.py
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.controller.orchestrator import Orchestrator
from src.evaluator.adapter import EvaluatorAdapter
from src.evidence.agent import EvidenceAgent
from src.evidence.providers.mock_provider import DEFAULT_FIXTURE_PATH, MockEvidenceProvider
from src.extractor.claim_extractor import ClaimExtractor
from src.reporter.report import HandoffReporter


def available_accounts(fixture_path: str | Path = DEFAULT_FIXTURE_PATH) -> list[str]:
    """Read fictional account IDs directly from the fixture dataset."""
    with Path(fixture_path).open("r", encoding="utf-8") as stream:
        records = json.load(stream)
    if not isinstance(records, list):
        raise ValueError("The evidence fixture must contain a list of records.")
    return sorted({
        record["account_id"] for record in records
        if isinstance(record, dict) and isinstance(record.get("account_id"), str)
    })


def build_orchestrator() -> Orchestrator:
    """Compose repository components using the local fictional evidence set."""
    return Orchestrator(
        claim_extractor=ClaimExtractor(),
        evidence_agent=EvidenceAgent(MockEvidenceProvider()),
        evaluator=EvaluatorAdapter(),
        reporter=HandoffReporter(),
        max_retries=1,
    )


def run_handoff(orchestrator: Orchestrator, account_id: str, source_text: str) -> dict[str, Any]:
    """Pass the user's handoff input to the real orchestrator pipeline."""
    return orchestrator.run({
        "handoff_id": f"handoff-{uuid.uuid4().hex[:12]}",
        "account_id": account_id,
        "source_text": source_text,
        "metadata": {"event_type": "sales_to_support_handoff", "requested_by": "demo-ui"},
    })


def build_trace(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Summarize the actual component outputs returned by the orchestrator."""
    evaluation = result.get("evaluation")
    if hasattr(evaluation, "to_dict"):
        evaluation = evaluation.to_dict()
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    attempts = result.get("attempts", {})
    diagnostics = result.get("diagnostics", [])
    error_components = {
        item.get("component") for item in diagnostics if isinstance(item, dict)
    }
    stages = [
        ("Claim extractor", "claim_extractor", f"{len(result.get('claims', []))} claim(s)"),
        ("Evidence agent", "evidence_agent", f"{len(result.get('evidence', []))} record(s)"),
        ("Evaluator", "evaluator", f"{result.get('disposition', 'UNKNOWN')} · {evaluation.get('risk_score', 'no score')} risk score"),
        ("Reporter", "reporter", result.get("report_status", "not run")),
    ]
    return [
        {
            "stage": label,
            "attempts": attempts.get(key, 0),
            "result": summary,
            "status": "error" if key in error_components else "completed",
        }
        for label, key, summary in stages
    ]


def render_app() -> None:
    """Render the Streamlit UI; imported lazily to keep helpers testable."""
    import streamlit as st

    st.set_page_config(page_title="Handoff Guardian", page_icon="🛡️", layout="wide")
    st.title("Handoff Guardian")
    st.caption("Sales-to-Support handoff review using the repository pipeline")
    st.info("Demo records are fictional and loaded from the local evidence fixture.")

    try:
        accounts = available_accounts()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.error(f"Could not load the fictional account fixture: {exc}")
        return
    if not accounts:
        st.error("No fictional accounts are available in the evidence fixture.")
        return

    account_id = st.selectbox("Fictional account", accounts)
    source_text = st.text_area(
        "Handoff event details",
        value=f"Sales is handing account {account_id} to Support.",
        help="Enter the handoff context only. The pipeline retrieves evidence separately.",
    )
    investigate = st.button("Investigate handoff", type="primary")
    recheck = st.button("Re-check after fix", help="Runs a new retrieval against the configured evidence provider.")
    if not investigate and not recheck:
        return
    if not source_text.strip():
        st.error("Enter handoff details before starting the investigation.")
        return

    try:
        with st.spinner("Running claim extraction, evidence retrieval, evaluation, and reporting..."):
            pipeline = build_orchestrator()
            result = run_handoff(pipeline, account_id, source_text)
    except Exception as exc:
        message = str(exc)
        if "NVIDIA_API_KEY" in message or "NVIDIA_BASE_URL" in message or "NEMOTRON_MODEL" in message:
            st.error("Nemotron is not configured. Set NVIDIA_API_KEY, NVIDIA_BASE_URL, and NEMOTRON_MODEL in your local environment, then restart Streamlit.")
        else:
            st.error(f"The handoff pipeline could not start: {type(exc).__name__}: {message}")
        return

    report = result.get("report")
    if not isinstance(report, dict):
        st.error("The pipeline completed without a usable report.")
        st.json(result)
        return

    if recheck:
        st.warning("Verification status: NOT_CHECKED. A new retrieval ran, but this UI cannot claim a blocker was fixed unless updated source records establish the resolution.")

    left, middle, right = st.columns(3)
    left.metric("Decision", result.get("disposition", "UNKNOWN"))
    middle.metric("Risk level", report.get("risk_level") or "Unknown")
    score = report.get("risk_score")
    right.metric("Risk score", f"{score}/100" if isinstance(score, int) else "Unknown")
    st.markdown(f"**Summary:** {report.get('summary', 'No summary available.')}")
    st.caption(f"Verification: {report.get('verification_status', 'NOT_CHECKED')} · Evidence citations: {'verified' if report.get('citations_verified') else 'invalid or unavailable'}")

    st.subheader("Evidence found")
    evidence = result.get("evidence", [])
    if evidence:
        st.dataframe(evidence, use_container_width=True, hide_index=True)
    else:
        st.info("The evidence agent returned no records for this account.")

    st.subheader("Evaluator findings")
    findings = report.get("findings", [])
    if findings:
        for finding in findings:
            with st.expander(f"{finding.get('severity', 'finding').upper()}: {finding.get('reason_code', 'Finding')}"):
                st.write(finding.get("description", "No description provided."))
                st.write("Evidence IDs:", ", ".join(finding.get("evidence_ids", [])) or "None")
                st.write("Blocking:", finding.get("blocking", "Unknown"))
    else:
        st.write("No evaluator findings were returned.")

    conflicts = report.get("conflicts", [])
    if conflicts:
        st.subheader("Evaluator conflicts")
        for conflict in conflicts:
            st.write(f"- {conflict}")

    st.subheader("Recommended actions")
    for action in report.get("recommended_actions", []):
        st.write(f"- {action}")

    st.subheader("Investigation trace")
    st.write(f"Handoff: {result.get('handoff_id', 'unknown')} · Account: {result.get('account_id', 'unknown')}")
    st.dataframe(build_trace(result), use_container_width=True, hide_index=True)
    if result.get("diagnostics"):
        st.warning("Pipeline diagnostics")
        st.json(result["diagnostics"])


if __name__ == "__main__":
    render_app()
