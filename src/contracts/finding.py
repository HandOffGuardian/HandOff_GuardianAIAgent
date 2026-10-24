"""Shared, immutable Finding contract emitted by evaluation components."""

from dataclasses import dataclass

from ._validation import require_evidence_ids, require_nonempty_string


@dataclass(frozen=True)
class Finding:
    """A policy finding; blocking and retryable remain independent flags."""

    reason_code: str
    rule_id: str
    severity: str
    blocking: bool
    description: str
    evidence_ids: tuple[str, ...] = ()
    subject: str = ""
    retryable: bool = False

    def __post_init__(self) -> None:
        for name in ("reason_code", "rule_id", "severity", "description"):
            require_nonempty_string(name, getattr(self, name))
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking must be a bool")
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        require_evidence_ids(self.evidence_ids)
        if not isinstance(self.subject, str):
            raise TypeError("subject must be a string")
