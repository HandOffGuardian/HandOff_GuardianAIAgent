"""Evaluator package."""
from .adapter import EvaluatorAdapter
from .evaluator import Evaluator, evaluate_handoff
from .models import (
    Claim,
    Decision,
    EvaluationResult,
    EvaluatorTransientError,
    EvidenceRecord,
    Finding,
    SourceStatus,
)
from .policy import Policy, PolicyError, load_policy

__all__ = [
    "Evaluator",
    "EvaluatorAdapter",
    "evaluate_handoff",
    "Decision",
    "Claim",
    "EvidenceRecord",
    "SourceStatus",
    "Finding",
    "EvaluationResult",
    "EvaluatorTransientError",
    "Policy",
    "PolicyError",
    "load_policy",
]

