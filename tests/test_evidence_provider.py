"""Tests for provider failures and Evidence Agent pass-through behavior."""

from __future__ import annotations

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

