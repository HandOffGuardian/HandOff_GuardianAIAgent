"""Streamlit-level wiring test; skipped when the optional UI dependency is absent."""

from unittest.mock import Mock, patch

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest


def test_submit_invokes_composed_orchestrator():
    orchestrator = Mock()
    orchestrator.run.return_value = {
        "disposition": "ESCALATE",
        "evaluation": {"risk_score": 50, "findings": []},
        "report": {"summary": "Manual review required.", "recommendations": []},
        "diagnostics": [],
    }

    with patch("src.controller.application.build_orchestrator", return_value=orchestrator):
        app = AppTest.from_file("C:\\Users\\Vani\\Desktop\\HandOff_GuardianAIAgent\\src\\ui\\app.py").run()
        app.text_area[0].set_value("The handoff is ready.")
        app.button[0].click().run()

    orchestrator.run.assert_called_once()
    request = orchestrator.run.call_args.args[0]
    assert request["account_id"] == "ACC001"
    assert request["source_text"] == "The handoff is ready."
    assert any("ESCALATE" in item.value for item in app.error)
