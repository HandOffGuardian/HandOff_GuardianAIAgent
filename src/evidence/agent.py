
"""Evidence Agent that collects evidence without evaluating it."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from src.contracts.evidence import EvidenceRecord


class EvidenceProvider(Protocol):
    """Provider interface implemented by fixture or future data adapters."""

    def get_records(self, account_id: str) -> list[EvidenceRecord]:
        """Return records for one account; provider failures must raise."""


class EvidenceAgent:
    """Collect evidence while preserving its provenance and contradictions."""

    def __init__(self, provider: EvidenceProvider) -> None:
        self._provider = provider

    def get_records(self, account_id: str) -> list[EvidenceRecord]:
        """Return provider records without resolving or rewriting them."""
        return self._provider.get_records(account_id)

    @staticmethod
    def _to_dict(record: Any) -> dict[str, Any]:
        """Convert a record into a JSON-friendly dictionary."""
        if is_dataclass(record) and not isinstance(record, type):
            data = asdict(record)
        elif isinstance(record, dict):
            data = dict(record)
        else:
            raise TypeError(
                f"Unsupported evidence record type: {type(record).__name__}"
            )

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    def collect(
        self,
        account_id: str,
        claims: list | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Return an evidence bundle for the orchestrator.

        Claims and metadata are accepted for interface compatibility.
        Evidence is not evaluated and contradictions are not resolved here.
        """
        records = self.get_records(account_id)

        return {
            "evidence": [self._to_dict(record) for record in records],
            "missing_mandatory": [],
            "conflicts": [],
            "mandatory_satisfied": None,
        }
