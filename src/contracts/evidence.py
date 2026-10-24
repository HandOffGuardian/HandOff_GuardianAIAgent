"""Shared contract for evidence records."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source: str
    account_id: str
    field: str
    value: str | None
    updated_at: datetime | None
    excerpt: str | None