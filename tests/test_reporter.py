
from unittest.mock import Mock

from src.reporter.report import Reporter


def make_result(disposition="ESCALATE"):
    return {
        "handoff_id": "HANDOFF-001",
        "account_id": "ACC001",
        "disposition": disposition,
        "evaluation": {
            "decision": disposition,
            "risk_score": 100 if disposition == "ESCALATE" else 0,
            "confidence": 0.0,
            "findings": [
                {
                    "reason_code": "STALE_EVIDENCE",
                    "rule_id": "REQ-ENGINEERING",
                    "severity": "high",
                    "blocking": True,
                    "description": "Engineering evidence is older than 48 hours.",
                    "evidence_ids": ["EV002"],
                }
            ] if disposition == "ESCALATE" else [],
            "missing_mandatory": [],
            "conflicts": [],
        },
        "evidence": [],
    }


def test_reporter_preserves_authoritative_escalation():
    generator = Mock()
    generator.generate.return_value = {
        "account_id": "ACC001",
        "status": "CLEAR",
        "risk_score": 0,
        "summary": "Looks fine.",
        "conflicts": [],
        "recommendations": [],
    }

    report = Reporter(generator).report(make_result("ESCALATE"))

    assert report["status"] == "ESCALATE"
    assert report["risk_score"] == 100


def test_reporter_preserves_authoritative_clear():
    generator = Mock()
    generator.generate.return_value = {
        "status": "ESCALATE",
        "risk_score": 100,
        "summary": "Needs review.",
    }

    report = Reporter(generator).report(make_result("CLEAR"))

    assert report["status"] == "CLEAR"
    assert report["risk_score"] == 0


def test_reporter_uses_fallback_when_generator_raises():
    generator = Mock()
    generator.generate.side_effect = RuntimeError("LLM unavailable")

    report = Reporter(generator).report(make_result("ESCALATE"))

    assert report["status"] == "ESCALATE"
    assert report["risk_score"] == 100
    assert "STALE_EVIDENCE" in report["summary"]
    assert report["recommendations"]


def test_reporter_uses_fallback_when_generator_returns_empty_result():
    generator = Mock()
    generator.generate.return_value = {}

    report = Reporter(generator).report(make_result("ESCALATE"))

    assert report["status"] == "ESCALATE"
    assert "STALE_EVIDENCE" in report["summary"]


def test_reporter_passes_evidence_to_generator():
    generator = Mock()
    generator.generate.return_value = {
        "summary": "Investigation complete.",
    }
    result = make_result()
    result["evidence"] = [
        {
            "evidence_id": "EV001",
            "source": "CRM",
            "field": "renewal_date",
            "value": "2026-11-30",
        }
    ]

    Reporter(generator).report(result)

    generator.generate.assert_called_once()
    _, kwargs = generator.generate.call_args
    assert kwargs["evidence_bundle"]["evidence"] == result["evidence"]


def test_reporter_rejects_non_mapping_input():
    import pytest

    with pytest.raises(TypeError):
        Reporter(Mock()).report("not a result mapping")
