"""PROVISIONAL Evaluator-local types.

The shared contracts in ``src/contracts/`` were empty when this was written, so
these mirror the *concepts* (Claim, EvidenceRecord, SourceStatus, Finding,
Evaluation Result). They must be replaced by (or adapted to) the shared
contracts as soon as those exist; field names here are assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, Union


class Decision(str, Enum):
    """CLEAR: all checks passed. ESCALATE: a risk exists or safety cannot be
    established. RETRY: operational recovery only (a temporary failure left a
    required check incomplete and the retry budget is not spent); it is never
    a handoff approval. The Planner owns the retry loop and counter."""

    CLEAR = "CLEAR"
    ESCALATE = "ESCALATE"
    RETRY = "RETRY"


@dataclass(frozen=True)
class EvidenceRecord:
    """Normalized evidence used by the Evaluator.

    Preserve source provenance and original record content so validation
    and conflict detection can inspect the evidence itself.
    """
    evidence_id: str
    source: str
    category: str
    timestamp: Union[datetime, str, None]
    value: Optional[str] = None
    account_id: Optional[str] = None
    excerpt: Optional[str] = None
    field: Optional[str] = None

@dataclass(frozen=True)
class Claim:
    claim_id: str
    category: str
    key: str
    value: str
    validation_status: str  # "validated" | "failed" | "unvalidated"
    evidence_ids: Tuple[str, ...] = ()
    source: Optional[str] = None
    severity: Optional[str] = None


@dataclass(frozen=True)
class SourceStatus:
    source: str
    status: str  # key of policy `source_status_behavior`
    detail: Optional[str] = None


@dataclass(frozen=True)
class Finding:
    reason_code: str
    rule_id: str
    severity: str
    blocking: bool
    description: str
    evidence_ids: Tuple[str, ...] = ()
    subject: str = ""  # underlying issue; used to avoid double-counting in scoring
    retryable: bool = False  # temporary failure a re-fetch might fix (policy `retry`)


from collections.abc import Mapping
from typing import Any, Iterator, Optional, Tuple, Union


class EvaluatorTransientError(RuntimeError):
    """Raised when evaluation encounters temporary, retryable conditions (transient/safe to retry)."""

    def __init__(self, message: str, findings: Tuple[Any, ...] = ()) -> None:
        super().__init__(message)
        self.transient: bool = True
        self.safe_to_retry: bool = True
        self.findings: Tuple[Any, ...] = findings


@dataclass(frozen=True)
class EvaluationResult(Mapping):
    decision: Decision
    risk_score: int
    risk_level: str
    findings: Tuple[Any, ...] = field(default_factory=tuple)
    policy_version: Optional[str] = None
    evaluated_at: Optional[str] = None
    missing_mandatory: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[Any, ...] = field(default_factory=tuple)
    mandatory_satisfied: bool = False

    def __getitem__(self, key: str) -> Any:
        if key == "decision":
            return self.decision.value
        elif key == "findings":
            return list(self.findings)
        elif key == "missing_mandatory":
            return list(self.missing_mandatory)
        elif key == "conflicts":
            return list(self.conflicts)
        elif key == "mandatory_satisfied":
            return self.mandatory_satisfied
        elif key == "risk_score":
            return self.risk_score
        elif key == "risk_level":
            return self.risk_level
        elif key == "policy_version":
            return self.policy_version
        elif key == "evaluated_at":
            return self.evaluated_at
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yield from (
            "decision",
            "findings",
            "mandatory_satisfied",
            "missing_mandatory",
            "conflicts",
            "risk_score",
            "risk_level",
            "policy_version",
            "evaluated_at",
        )

    def __len__(self) -> int:
        return 9

    def to_dict(self) -> dict[str, Any]:
        return {k: self[k] for k in self}

