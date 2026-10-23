"""Evidence Agent that returns provider records to its caller unchanged.

The caller (the controller/orchestrator) owns integration with downstream
components. This agent does not evaluate evidence, resolve contradictions, or
assign a handoff decision. Full integration requires Mohan's shared
``EvidenceRecord`` model in ``src/contracts/evidence.py`` to be populated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.contracts.evidence import EvidenceRecord


class EvidenceProvider(Protocol):
    """Provider interface implemented by fixture or future data adapters."""

    def get_records(self, account_id: str) -> list[EvidenceRecord]:
        """Return records for one account; provider failures must raise."""


class EvidenceAgent:
    """Expose raw evidence records to the orchestrator/controller."""

    def __init__(self, provider: EvidenceProvider) -> None:
        self._provider = provider

    def get_records(self, account_id: str) -> list[EvidenceRecord]:
        """Return provider records directly without resolving or rewriting them."""
        return self._provider.get_records(account_id)
