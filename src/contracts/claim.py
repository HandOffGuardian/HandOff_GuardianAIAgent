"""Shared, immutable Claim contract used across handoff components."""

from dataclasses import dataclass

from ._validation import require_evidence_ids, require_nonempty_string


@dataclass(frozen=True)
class Claim:
    """A source assertion and its current validation state.

    Extraction alone is not verification. Extractors should use
    ``validation_status="unvalidated"`` and leave evidence references empty
    until another component establishes support.
    """

    claim_id: str
    category: str
    key: str
    value: str
    validation_status: str
    evidence_ids: tuple[str, ...] = ()
    source: str | None = None
    severity: str | None = None

    def __post_init__(self) -> None:
        for name in ("claim_id", "category", "key", "value", "validation_status"):
            require_nonempty_string(name, getattr(self, name))
        require_evidence_ids(self.evidence_ids)
        for name in ("source", "severity"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise TypeError(f"{name} must be a non-empty string or None")
