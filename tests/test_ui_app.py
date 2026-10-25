
"""Streamlit-level wiring test; skipped when the optional UI dependency is absent."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest


def test_submit_invokes_composed_orchestrator():
    orchestrator = Mock()
    orchestrator.run.return_value = {
        "disposition": "ESCALATE",
        "evaluation": {"risk_score": 50, "findings": []},
        "report": {
            "summary": "Manual review required.",
            "recommendations": [],
        },
        "diagnostics": [],
    }

    app_path = Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py"

    with patch(
        "src.controller.application.build_orchestrator",
        return_value=orchestrator,
    ):
        app = AppTest.from_file(str(app_path)).run()

        # Fill in both required IDs and the handoff message.
        app.text_input[0].set_value("H001")
        app.text_input[1].set_value("ACC001")
        app.text_area[0].set_value("The handoff is ready.")

        # Submit the form, then rerun the Streamlit app.
        app.button[0].click().run()

    # Verify that the UI invoked the orchestrator with the expected request.
    orchestrator.run.assert_called_once()
    request = orchestrator.run.call_args.args[0]

    assert request["handoff_id"] == "H001"
    assert request["account_id"] == "ACC001"
    assert request["source_text"] == "The handoff is ready."
    assert any("ESCALATE" in item.value for item in app.error)
