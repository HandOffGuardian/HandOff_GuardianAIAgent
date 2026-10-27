
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

from src.ui import components as ui
from src.ui.theme import inject_theme
from src.ui.view_model import STAGES, evidence_citations, stage_states, summary_facts


st.set_page_config(
    page_title="Handoff Guardian AI",
    page_icon="🛡️",
    layout="wide",
)


def nemotron_configured() -> bool:
    """Report whether the Nemotron variables are present (values never shown)."""
    names = ("NVIDIA_API_KEY", "NVIDIA_BASE_URL", "NEMOTRON_MODEL")
    file_values: Mapping[str, str | None] = {}
    try:
        from dotenv import dotenv_values

        env_path = ROOT / ".env"
        if env_path.is_file():
            file_values = dotenv_values(env_path)
    except Exception:
        file_values = {}
    return all((os.environ.get(n) or file_values.get(n) or "").strip() for n in names)


# ---------- Theme ----------
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

model_ready = nemotron_configured()

with st.sidebar:
    ui.sidebar_brand()

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

    st.divider()
    ui.sidebar_status(
        [
            ("Nemotron LLM", "Ready" if model_ready else "Not Configured", "accent" if model_ready else "warn"),
            ("Evidence Fixtures", "Active", "ok"),
        ]
    )

inject_theme(st.session_state.theme)


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

    raise TypeError(
        f"Unsupported result value for JSON serialization: "
        f"{type(value).__name__}"
    )


def render_result(result: Mapping) -> None:
    """Render a JSON-safe Orchestrator result without altering its meaning."""
    facts = summary_facts(result)
    status = facts["disposition"]
    evaluation = result.get("evaluation") or {}
    report = result.get("report") or {}
    score = facts["risk_score"]
    score_text = f"{score}/100" if score is not None else "n/a"

    ui.section("Outcome", "Investigation Result")
    ui.hero(facts)

    if status == "CLEAR":
        ui.alert_marker("ok")
        st.success(f"Status: {status} (Risk Score: {score_text})")
    else:
        ui.alert_marker("bad")
        st.error(f"Status: {status} (Risk Score: {score_text})")

    ui.section("Workflow", "Multi-Agent Pipeline")
    ui.pipeline(stage_states(result))

    claims = result.get("claims") or []
    evidence = result.get("evidence") or []
    findings = evaluation.get("findings", [])
    diagnostics = result.get("diagnostics") or []
    states = {s["key"]: s["status"] for s in stage_states(result)}

    ui.section("Details", "Investigation Breakdown")
    tabs = st.tabs(
        [
            "Report",
            f"Findings ({len(findings)})",
            f"Claims ({len(claims)})",
            f"Evidence ({len(evidence)})",
            f"Diagnostics ({len(diagnostics)})",
            "Raw JSON",
        ]
    )

    with tabs[0]:
        if report:
            with st.container(border=True):
                st.markdown(report.get("summary", "No report was produced."))
        else:
            ui.empty_state("No Report Produced", "The reporter produced no summary for this run.")
        ui.text_list("Recommended Actions", report.get("recommendations", ["Perform manual review."]))

    with tabs[1]:
        if findings:
            ui.findings_list(findings)
        elif evaluation:
            ui.empty_state("No Findings", "Zero policy findings recorded.")
        else:
            ui.empty_state("Not Evaluated", "Pipeline did not reach the evaluation stage.")
        if evaluation.get("missing_mandatory"):
            ui.text_list("Missing Mandatory Items", evaluation["missing_mandatory"])
        if evaluation.get("conflicts"):
            ui.text_list("Identified Conflicts", evaluation["conflicts"])

    with tabs[2]:
        if claims:
            ui.claims_table(claims)
        elif states.get("claim_extractor") in ("completed", "warning"):
            ui.empty_state("No Claims", "No assertions detected in the provided handoff text.")
        else:
            ui.empty_state("Unavailable", "Claim extraction stage did not complete.")

    with tabs[3]:
        if evidence:
            ui.evidence_grid(evidence, evidence_citations(result))
        elif states.get("evidence_agent") in ("completed", "warning"):
            ui.empty_state("No Records", "No evidence records found for this account.")
        else:
            ui.empty_state("Unavailable", "Evidence retrieval stage did not complete.")

    with tabs[4]:
        if diagnostics:
            ui.diagnostics_table(diagnostics)
        else:
            ui.empty_state("Clean Execution", "No errors or diagnostics were generated.")

    with tabs[5]:
        st.download_button(
            "Download Result (JSON)",
            data=json.dumps(result, indent=2),
            file_name=f"handoff-guardian-{result.get('handoff_id') or 'result'}.json",
            mime="application/json",
        )
        st.json(result)


# ---------- Main pages ----------

if page == "Investigate":
    ui.topbar("Handoff Risk Auditor")
    ui.intro_card()

    with st.form("investigate_handoff"):
        id_col, account_col = st.columns(2)
        with id_col:
            handoff_id = st.text_input(
                "Handoff ID",
                placeholder="e.g. ACC001",
            )
        with account_col:
            account_id = st.text_input(
                "Account ID",
                placeholder="e.g. ACC001",
            )
        handoff_message = st.text_area(
            "Handoff message",
            placeholder="Paste handoff notes or message here...",
            height=160,
        )
        submitted = st.form_submit_button(
            "Investigate Handoff",
            type="primary",
            use_container_width=True,
        )

    run_failed = False
    if submitted:
        if not (handoff_id.strip() or account_id.strip()):
            ui.alert_marker("warn")
            st.warning("Please enter a handoff ID or account ID.")
        elif not handoff_message.strip():
            ui.alert_marker("warn")
            st.warning("Please enter a handoff message before investigating.")
        else:
            try:
                with st.spinner("Analyzing handoff claims and validating evidence..."):
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
                run_failed = True
                ui.alert_marker("bad")
                st.error(f"Investigation failed: {exc}")

    result = st.session_state.get("last_result")
    if result is not None:
        render_result(result)
    else:
        ui.section("Workflow", "Multi-Agent Pipeline")
        ui.pipeline(stage_states(None))

elif page == "About":
    ui.topbar("System Architecture")

    ui.section("Pipeline Architecture", "Multi-Agent Flow")
    ui.about_stages(STAGES)

    ui.section("Verification Policy", "Fail-Closed Standard")
    ui.text_list(
        "A handoff receives a CLEAR disposition only when:",
        [
            "Evaluator explicitly issues a CLEAR decision.",
            "All mandatory policy requirements are satisfied.",
            "Account evidence is complete with zero unresolved conflicts.",
            "Any extraction, provider, or evaluation failure defaults to ESCALATE.",
        ],
    )

    ui.section("Service Integrations", "Environment Status")
    ui.integration_table(
        [
            ("NVIDIA Nemotron", "Configured" if model_ready else "Not Configured", "accent" if model_ready else "warn",
             "Powers LLM claim extraction via OpenAI-compatible endpoint."),
            ("Evidence Provider", "Fixture Records", "ok",
             "Supplies multi-source account records for offline evaluation."),
            ("Zetaris Connector", "Unlinked", "", "Production adapter slot."),
            ("Meterless LLM", "Offline", "", "Template report generation enabled."),
        ]
    )

# When launched via root `app.py` (`from src.ui.app import *`), Python's
# module cache prevents Streamlit reruns from re-executing this file.
# A deferred eviction allows importlib to finish its initial load cleanly,
# while ensuring subsequent reruns of root `app.py` re-execute without blanking.
if __name__ != "__main__":
    import threading
    threading.Timer(0.05, lambda: sys.modules.pop("src.ui.app", None)).start()
