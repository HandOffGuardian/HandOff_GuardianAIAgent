
"""Tests for provider failures and Evidence Agent behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.evidence.agent import EvidenceAgent
from src.evidence.providers.exceptions import EvidenceProviderError
from src.evidence.providers.mock_provider import MockEvidenceProvider


def test_fixture_failure_is_explicit_and_preserves_cause(tmp_path: Path) -> None:
    missing_fixture = tmp_path / "missing.json"

    with pytest.raises(EvidenceProviderError) as error:
        MockEvidenceProvider(missing_fixture).get_records("ACC001")

    assert isinstance(error.value.__cause__, OSError)


def test_invalid_fixture_is_not_reported_as_empty_result(tmp_path: Path) -> None:
    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text("{not json", encoding="utf-8")

    with pytest.raises(EvidenceProviderError) as error:
        MockEvidenceProvider(invalid_fixture).get_records("ACC001")

    assert error.value.__cause__ is not None


def test_agent_returns_provider_records_directly() -> None:
    records = [object(), object()]

    class StubProvider:
        def get_records(self, account_id: str) -> list[object]:
            assert account_id == "ACC001"
            return records

    result = EvidenceAgent(StubProvider()).get_records("ACC001")

    assert result is records


@dataclass(frozen=True)
class StubEvidenceRecord:
    evidence_id: str
    source: str
    account_id: str
    field: str
    value: str | None
    updated_at: datetime | None
    excerpt: str | None


def test_collect_preserves_provenance_and_serializes_timestamp() -> None:
    timestamp = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    record = StubEvidenceRecord(
        evidence_id="EV001",
        source="mock_fixture",
        account_id="ACC001",
        field="production_status",
        value="blocked",
        updated_at=timestamp,
        excerpt="Example source excerpt",
    )

    class StubProvider:
        def get_records(self, account_id: str) -> list[StubEvidenceRecord]:
            assert account_id == "ACC001"
            return [record]

    result = EvidenceAgent(StubProvider()).collect(
        account_id="ACC001",
        claims=[],
        metadata={},
    )

    assert len(result["evidence"]) == 1
    evidence = result["evidence"][0]
    assert evidence["evidence_id"] == "EV001"
    assert evidence["source"] == "mock_fixture"
    assert evidence["account_id"] == "ACC001"
    assert evidence["field"] == "production_status"
    assert evidence["value"] == "blocked"
    assert evidence["updated_at"] == timestamp.isoformat()
    assert evidence["excerpt"] == "Example source excerpt"
    assert result["source_statuses"] == []
    assert result["mandatory_satisfied"] is None


def test_collect_preserves_conflicting_records() -> None:
    records = [
        StubEvidenceRecord(
            evidence_id="EV001",
            source="source_a",
            account_id="ACC001",
            field="production_status",
            value="blocked",
            updated_at=None,
            excerpt="First source",
        ),
        StubEvidenceRecord(
            evidence_id="EV002",
            source="source_b",
            account_id="ACC001",
            field="production_status",
            value="ready",
            updated_at=None,
            excerpt="Second source",
        ),
    ]

    class StubProvider:
        def get_records(self, account_id: str) -> list[StubEvidenceRecord]:
            return records

    result = EvidenceAgent(StubProvider()).collect("ACC001")

    assert len(result["evidence"]) == 2
    assert [item["value"] for item in result["evidence"]] == [
        "blocked",
        "ready",
    ]
    assert [item["evidence_id"] for item in result["evidence"]] == [
        "EV001",
        "EV002",
    ]


def test_collect_returns_empty_evidence_for_unknown_account() -> None:
    class StubProvider:
        def get_records(self, account_id: str) -> list:
            return []

    result = EvidenceAgent(StubProvider()).collect("UNKNOWN")

    assert result["evidence"] == []
