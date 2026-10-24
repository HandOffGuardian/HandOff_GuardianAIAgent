"""Deterministic, explainable risk scoring.

Rationale:
- Score = sum of policy severity weights over *distinct issues* (findings with
  the same `subject` count once, at their highest weight), capped at max_score.
  This avoids double-counting e.g. an open blocker that also appears in a conflict.
- Weights/thresholds live in policy.yaml; critical > high > medium > low so
  serious blockers always outweigh minor inconsistencies.
- `blocking_floor` raises (never lowers) the score when a blocking finding
  exists so a blocked case is not displayed as low risk.
- The score is a summary, NOT a probability of failure, and it has no influence
  on the CLEAR/ESCALATE decision.
"""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

from .models import Finding
from .policy import Policy


def calculate_risk(policy: Policy, findings: Sequence[Finding]) -> Tuple[int, str]:
    per_issue: Dict[str, float] = {}
    for f in findings:
        w = policy.severity_weights[f.severity]
        per_issue[f.subject] = max(per_issue.get(f.subject, 0), w)
    score = sum(per_issue.values())
    if any(f.blocking for f in findings):
        score = max(score, policy.blocking_floor)
    score = int(min(round(score), policy.max_score))
    return score, risk_level(policy, score)


def risk_level(policy: Policy, score: int) -> str:
    level = policy.levels[0][0]
    for name, lower in policy.levels:
        if score >= lower:
            level = name
    return level
