
"""Handoff Guardian — Streamlit dashboard."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from datetime import date, datetime

# Ensure imports work when launched from the repository root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.controller.application import build_orchestrator


st.set_page_config(
    page_title="Handoff Guardian",
    page_icon="🛡️",
    layout="wide",
)

# ---------- Theme ----------
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

with st.sidebar:
    st.title("🛡️ Handoff Guardian")
    st.caption("Sales-to-Support Handoff Risk Auditor")

    st.selectbox(
        "Appearance",
        ["Dark", "Light"],
        key="theme",
    )

    st.divider()
    page = st.radio(
        "Navigation",
        ["Investigate", "About"],
        label_visibility="collapsed",
    )

if st.session_state.theme == "Dark":
    background = "#0E1117"
    foreground = "#FAFAFA"
    panel = "#1B2029"
    border = "#303744"
else:
    background = "#FFFFFF"
    foreground = "#202938"
    panel = "#F3F6FA"
    border = "#D8DEE8"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {background};
        color: {foreground};
    }}
    [data-testid="stSidebar"] {{
        background-color: {panel};
    }}
    [data-testid="stMetric"] {{
        background-color: {panel};
        border: 1px solid {border};
        padding: 16px;
        border-radius: 12px;
    }}
    div.stButton > button[kind="primary"] {{
        border-radius: 8px;
        min-height: 44px;
        font-weight: 600;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def json_safe(value):
    """Convert nested pipeline results into JSON-compatible values."""
    if isinstance(value, Mapping):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))

    if isinstance(value, Enum):
        return json_safe(value.value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    if isinstance(value, (set, frozenset)):
        return [json_safe(item) for item in value]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Avoid silently flattening unexpected objects into strings.
    raise TypeError(
        f"Unsupported result value for JSON serialization: "
        f"{type(value).__name__}"
    )

# ---------- Main pages ----------

st.title("🛡️ Handoff Guardian")
st.caption("Sales-to-Support Handoff Risk Auditor")

if page == "Investigate":
    st.header("Investigate a Handoff")
    st.write(
        "Review a sales-to-support handoff using the existing "
        "claim extraction, evidence collection, evaluation, and reporting pipeline."
    )

    with st.form("investigate_handoff"):
        handoff_id = st.text_input(
            "Handoff / Account ID",
            placeholder="e.g. ACC001",
        )
        account_id = st.text_input(
            "Account ID",
            placeholder="e.g. ACC001",
        )
        handoff_message = st.text_area(
            "Handoff message",
            placeholder="Paste the handoff notes or message here...",
            height=180,
        )
        submitted = st.form_submit_button(
            "Investigate Handoff",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not (handoff_id.strip() or account_id.strip()):
            st.warning("Please enter a handoff ID or account ID.")
        elif not handoff_message.strip():
            st.warning("Please enter a handoff message before investigating.")
        else:
            try:
                with st.spinner("Running the investigation pipeline..."):
                    orchestrator = build_orchestrator()

                    result = orchestrator.run(
                        {
                            "handoff_id": handoff_id.strip() or account_id.strip(),
                            "account_id": account_id.strip() or handoff_id.strip(),
                            "source_text": handoff_message.strip(),
                        }
                    )


                    st.session_state["last_result"] = json_safe(result)

            except Exception as exc:
                st.error(f"Investigation failed: {exc}")

    result = st.session_state.get("last_result")
    if result is not None:
        st.divider()
        st.subheader("Investigation Results")
        status = result.get("disposition", "ESCALATE")
        evaluation = result.get("evaluation") or {}
        report = result.get("report") or {}
        score = evaluation.get("risk_score", report.get("risk_score", 0))
        if status == "CLEAR":
            st.success(f"Status: {status} (Risk Score: {score}/100)")
        else:
            st.error(f"Status: {status} (Risk Score: {score}/100)")
        st.markdown("### Investigation Summary")
        st.write(report.get("summary", "No report was produced."))
        findings = evaluation.get("findings", [])
        if findings:
            st.markdown("### Findings")
            st.write(json_safe(findings))
        if result.get("evidence"):
            with st.expander("Collected evidence and provenance"):
                st.json(json_safe(result["evidence"]))
        if result.get("diagnostics"):
            st.markdown("### Execution diagnostics")
            for diagnostic in result["diagnostics"]:
                st.warning(f"{diagnostic.get('component')}: {diagnostic.get('error')}")
        st.markdown("### Recommended Actions")
        for recommendation in report.get("recommendations", ["Perform manual review."]):
            st.write(f"- {recommendation}")

elif page == "About":
    st.header("About Handoff Guardian")
    st.write(
        "Handoff Guardian helps identify risks in sales-to-support handoffs "
        "by extracting claims, gathering evidence, evaluating requirements, "
        "and generating a report."
    )

    st.subheader("How the pipeline works")
    st.markdown(
        """
        1. **Claim Extractor** — extracts claims from the handoff.
        2. **Evidence Agent** — gathers supporting evidence.
        3. **Evaluator** — checks evidence and identifies risks.
        4. **Reporter** — summarizes the findings and recommended actions.
        """
    )
