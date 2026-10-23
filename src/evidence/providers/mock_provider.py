"""Fixture-backed evidence provider.

This provider uses fictional records only. The records are converted to
Mohan's shared ``EvidenceRecord`` model at lookup time. That shared model is
currently an empty placeholder in this checkout, so full integration requires
it to be populated before records can be returned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.evidence.providers.exceptions import EvidenceProviderError

if TYPE_CHECKING:
    from src.contracts.evidence import EvidenceRecord


DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "accounts.json"
REQUIRED_FIELDS = {
    "evidence_id",
    "source",
    "account_id",
    "field",
    "value",
    "updated_at",
    "excerpt",
}


class MockEvidenceProvider:
    """Load fictional evidence records and filter them by account ID."""

    def __init__(self, fixture_path: str | Path = DEFAULT_FIXTURE_PATH) -> None:
        self._fixture_path = Path(fixture_path)

    def get_records(self, account_id: str) -> list[EvidenceRecord]:
        """Return records for ``account_id`` or raise on provider failure.

        A valid account with no matching fixture records returns ``[]``.
        Fixture I/O or content failures are surfaced as ``EvidenceProviderError``
        with the original error retained as ``__cause__``. An absent shared
        EvidenceRecord model raises ImportError explicitly; it is an integration
        dependency, not a successful empty lookup or a fixture-provider failure.
        """
        try:
            with self._fixture_path.open("r", encoding="utf-8") as fixture_file:
                raw_records = json.load(fixture_file)
            if not isinstance(raw_records, list):
                raise ValueError("fixture root must be a list of evidence records")
            if any(
                not isinstance(record, dict) or not REQUIRED_FIELDS.issubset(record)
                for record in raw_records
            ):
                raise ValueError("each fixture record must contain all seven evidence fields")
            matching_records = [
                record
                for record in raw_records
                if record["account_id"] == account_id
            ]
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise EvidenceProviderError(
                f"Unable to load evidence fixture {self._fixture_path}"
            ) from exc

        if not matching_records:
            return []

        # Import only when conversion is needed. This keeps fixture inspection
        # possible while the shared contract placeholder remains unpopulated.
        from src.contracts.evidence import EvidenceRecord

        try:
            return [self._to_evidence_record(EvidenceRecord, item) for item in matching_records]
        except Exception as exc:
            raise EvidenceProviderError(
                f"Unable to construct EvidenceRecord values for account {account_id}"
            ) from exc

    @staticmethod
    def _to_evidence_record(model: Any, item: dict[str, Any]) -> EvidenceRecord:
        updated_at = item.get("updated_at")
        if updated_at is not None:
            parsed_timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                raise ValueError("updated_at must include a timezone")
            item = {**item, "updated_at": parsed_timestamp.astimezone(timezone.utc)}
        else:
            item = {**item, "updated_at": None}
        return model(**item)
