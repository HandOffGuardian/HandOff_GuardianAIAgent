"""Tests for evidence provenance preservation and contradiction retention."""

from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path

import pytest

from src.evidence.providers.mock_provider import DEFAULT_FIXTURE_PATH, MockEvidenceProvider


def test_fixtures_cover_twelve_accounts_and_unique_evidence_ids() -> None:
    records = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert {record["account_id"] for record in records} == {
        f"ACC{number:03d}" for number in range(1, 13)
    }
    evidence_ids = [record["evidence_id"] for record in records]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert evidence_ids == [f"EV{number:03d}" for number in range(1, len(records) + 1)]


def test_each_fixture_record_has_all_contract_fields_and_provenance() -> None:
    records = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    required = {
        "evidence_id",
        "source",
        "account_id",
        "field",
        "value",
        "updated_at",
        "excerpt",
    }

    assert records
    for record in records:
        assert set(record) == required
        assert record["source"]
        assert record["excerpt"]


def test_conflicting_records_remain_separate() -> None:
    records = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    statuses = [
        record
        for record in records
        if record["account_id"] == "ACC001" and record["field"] == "production_status"
    ]

    assert [record["evidence_id"] for record in statuses] == ["EV002", "EV003"]
    assert [record["value"] for record in statuses] == ["blocked", "ready"]
    assert len({record["source"] for record in statuses}) == 2


def test_unknown_timestamp_is_not_fabricated() -> None:
    records = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert next(record for record in records if record["evidence_id"] == "EV029")["updated_at"] is None


def test_provider_returns_shared_evidence_records_when_model_is_available() -> None:
    try:
        from src.contracts.evidence import EvidenceRecord
    except ImportError as exc:
        pytest.skip(f"Mohan's shared EvidenceRecord model is not populated: {exc}")

    result = MockEvidenceProvider().get_records("ACC001")

    assert len(result) == 3
    assert all(isinstance(record, EvidenceRecord) for record in result)
    assert [record.evidence_id for record in result] == ["EV001", "EV002", "EV003"]
    assert result[2].updated_at.tzinfo is not None
    assert result[2].updated_at.utcoffset().total_seconds() == 0
    assert result[2].updated_at.tzinfo == timezone.utc
    assert result[2].excerpt == "I believe the production setup is ready."


def test_provider_returns_empty_list_for_account_without_matches() -> None:
    assert MockEvidenceProvider().get_records("ACC999") == []
