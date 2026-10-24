"""Policy loading and validation. Never falls back to a permissive default."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

# Resolved relative to this file so the CWD never matters.
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "policy.yaml"

# Codes the Python rules emit; the policy must define every one of them.
REQUIRED_REASON_CODES = frozenset({
    "MISSING_REQUIRED_EVIDENCE", "SOURCE_STATUS_MISSING", "SOURCE_UNAVAILABLE",
    "SOURCE_INVALID", "STALE_EVIDENCE", "EVIDENCE_TIMESTAMP_INVALID",
    "MISSING_REQUIRED_CLAIM", "CLAIM_VALIDATION_FAILED",
    "CLAIM_VALIDATION_INCOMPLETE", "UNKNOWN_EVIDENCE_REFERENCE",
    "UNRESOLVED_CRITICAL_BLOCKER", "UNRESOLVED_NONCRITICAL_BLOCKER",
    "CRITICAL_CONFLICT_UNRESOLVED", "CONFLICT_RESOLVED_BY_PRECEDENCE",
    "MINOR_CONFLICT", "INVALID_INPUT", "POLICY_INVALID", "EVALUATOR_ERROR",
})


class PolicyError(Exception):
    """Policy missing, malformed, or failing validation."""


@dataclass(frozen=True)
class ReasonCode:
    code: str
    severity: str
    blocking: bool
    description: str


@dataclass(frozen=True)
class Requirement:
    id: str
    category: str
    description: str
    required_sources: Tuple[str, ...]
    max_age_hours: float
    require_claim: bool


@dataclass(frozen=True)
class Policy:
    version: str
    clock_skew_seconds: float
    severity_weights: Mapping[str, float]
    reason_codes: Mapping[str, ReasonCode]
    requirements: Tuple[Requirement, ...]
    source_precedence: Mapping[str, Tuple[str, ...]]
    blocker_category: str
    blocker_key: str
    blocker_open_values: frozenset
    blocker_resolved_values: frozenset
    blocker_critical_severities: frozenset
    blocker_default_severity: str
    conflict_critical_keys: frozenset
    conflict_critical_severities: frozenset
    allow_override_of_critical_blocker: bool
    status_behavior: Mapping[str, Optional[str]]  # None == pass
    missing_status_code: str
    max_score: int
    blocking_floor: int
    levels: Tuple[Tuple[str, int], ...]  # ascending (name, lower bound)
    max_retries: int
    retryable_codes: frozenset


def _req(cond: object, msg: str) -> None:
    if not cond:
        raise PolicyError(msg)


def _mapping(raw: Any, name: str) -> Mapping[str, Any]:
    _req(isinstance(raw, dict), f"'{name}' must be a mapping")
    return raw


def _str_list(raw: Any, name: str, allow_empty: bool = False) -> Tuple[str, ...]:
    _req(isinstance(raw, list) and all(isinstance(x, str) and x for x in raw),
         f"'{name}' must be a list of non-empty strings")
    _req(allow_empty or bool(raw), f"'{name}' must not be empty")
    _req(len(set(raw)) == len(raw), f"'{name}' contains duplicates")
    return tuple(raw)


def _number(raw: Any, name: str, minimum: float = 0, exclusive: bool = False) -> float:
    ok = isinstance(raw, (int, float)) and not isinstance(raw, bool)
    _req(ok, f"'{name}' must be a number")
    _req(raw > minimum if exclusive else raw >= minimum,
         f"'{name}' must be {'>' if exclusive else '>='} {minimum}")
    return raw


def load_policy(path: Optional[Path] = None) -> Policy:
    """Load and validate the policy; raises PolicyError on any problem."""
    p = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"cannot read policy file {p}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyError(f"malformed policy YAML: {exc}") from exc
    return validate_policy(raw)


def validate_policy(raw: Any) -> Policy:
    _req(isinstance(raw, dict), "policy must be a YAML mapping (empty file?)")
    for key in ("policy_version", "clock_skew_tolerance_seconds", "severities",
                "reason_codes", "requirements", "source_precedence", "blockers",
                "conflicts", "source_status_behavior",
                "missing_source_status_code", "scoring", "retry", "approved_exceptions"):
        _req(key in raw, f"missing required setting '{key}'")

    _req(isinstance(raw["policy_version"], str) and bool(raw["policy_version"]),
         "'policy_version' must be a non-empty string")
    skew = _number(raw["clock_skew_tolerance_seconds"], "clock_skew_tolerance_seconds")
    _req(raw["approved_exceptions"] == [],
         "'approved_exceptions' must be empty: no exception schema is approved")

    severities = _mapping(raw["severities"], "severities")
    _req(bool(severities), "'severities' must not be empty")
    weights: Dict[str, float] = {}
    for name, cfg in severities.items():
        _req(isinstance(cfg, dict) and "weight" in cfg, f"severity '{name}' needs a weight")
        weights[str(name)] = _number(cfg["weight"], f"severities.{name}.weight")

    codes: Dict[str, ReasonCode] = {}
    for code, cfg in _mapping(raw["reason_codes"], "reason_codes").items():
        cfg = _mapping(cfg, f"reason_codes.{code}")
        _req(cfg.get("severity") in weights,
             f"reason code '{code}' uses unknown severity {cfg.get('severity')!r}")
        _req(isinstance(cfg.get("blocking"), bool), f"reason code '{code}' needs boolean 'blocking'")
        _req(isinstance(cfg.get("description"), str) and bool(cfg["description"]),
             f"reason code '{code}' needs a description")
        codes[str(code)] = ReasonCode(str(code), cfg["severity"], cfg["blocking"], cfg["description"])
    missing = REQUIRED_REASON_CODES - set(codes)
    _req(not missing, f"policy lacks reason codes: {sorted(missing)}")
    unknown = set(codes) - REQUIRED_REASON_CODES
    _req(not unknown, f"policy defines unknown reason codes: {sorted(unknown)}")

    reqs: List[Requirement] = []
    _req(isinstance(raw["requirements"], list) and bool(raw["requirements"]),
         "'requirements' must be a non-empty list")
    for i, r in enumerate(raw["requirements"]):
        r = _mapping(r, f"requirements[{i}]")
        for k in ("id", "category", "description", "required_sources", "max_age_hours", "require_claim"):
            _req(k in r, f"requirements[{i}] missing '{k}'")
        _req(isinstance(r["id"], str) and bool(r["id"]) and isinstance(r["category"], str) and bool(r["category"]),
             f"requirements[{i}] id/category must be non-empty strings")
        _req(isinstance(r["require_claim"], bool), f"requirements[{i}].require_claim must be boolean")
        reqs.append(Requirement(
            r["id"], r["category"], str(r["description"]),
            _str_list(r["required_sources"], f"requirements[{i}].required_sources"),
            _number(r["max_age_hours"], f"requirements[{i}].max_age_hours", 0, exclusive=True),
            r["require_claim"]))
    _req(len({r.id for r in reqs}) == len(reqs), "duplicate requirement ids")
    categories = {r.category for r in reqs}

    precedence: Dict[str, Tuple[str, ...]] = {}
    for cat, srcs in _mapping(raw["source_precedence"], "source_precedence").items():
        _req(cat in categories, f"source_precedence category '{cat}' matches no requirement")
        precedence[str(cat)] = _str_list(srcs, f"source_precedence.{cat}")

    b = _mapping(raw["blockers"], "blockers")
    for k in ("category", "claim_key", "open_values", "resolved_values",
              "critical_severities", "default_severity"):
        _req(k in b, f"blockers missing '{k}'")
    _req(b["category"] in categories, "blockers.category matches no requirement")
    open_v = frozenset(v.lower() for v in _str_list(b["open_values"], "blockers.open_values"))
    res_v = frozenset(v.lower() for v in _str_list(b["resolved_values"], "blockers.resolved_values"))
    _req(not (open_v & res_v), "blockers open/resolved values overlap")
    crit_b = frozenset(_str_list(b["critical_severities"], "blockers.critical_severities"))
    _req(crit_b <= set(weights) and b["default_severity"] in weights,
         "blockers reference an unknown severity")

    c = _mapping(raw["conflicts"], "conflicts")
    for k in ("critical_keys", "critical_severities", "allow_precedence_override_of_critical_blocker"):
        _req(k in c, f"conflicts missing '{k}'")
    crit_c = frozenset(_str_list(c["critical_severities"], "conflicts.critical_severities"))
    _req(crit_c <= set(weights), "conflicts reference an unknown severity")
    _req(isinstance(c["allow_precedence_override_of_critical_blocker"], bool),
         "conflicts.allow_precedence_override_of_critical_blocker must be boolean")

    behavior: Dict[str, Optional[str]] = {}
    for status, action in _mapping(raw["source_status_behavior"], "source_status_behavior").items():
        if action == "pass":
            _req(status == "available", "only status 'available' may map to 'pass'")
            behavior[str(status)] = None
        else:
            _req(action in codes, f"source_status_behavior.{status} uses unknown reason code {action!r}")
            behavior[str(status)] = action
    _req(behavior.get("available", "x") is None, "status 'available' must map to 'pass'")
    _req(raw["missing_source_status_code"] in codes, "missing_source_status_code is not a known reason code")

    s = _mapping(raw["scoring"], "scoring")
    for k in ("max_score", "blocking_floor", "levels"):
        _req(k in s, f"scoring missing '{k}'")
    max_score = int(_number(s["max_score"], "scoring.max_score", 0, exclusive=True))
    floor = int(_number(s["blocking_floor"], "scoring.blocking_floor"))
    _req(floor <= max_score, "scoring.blocking_floor exceeds max_score")
    levels = _mapping(s["levels"], "scoring.levels")
    ordered = tuple(sorted(((str(n), int(_number(v, f"scoring.levels.{n}"))) for n, v in levels.items()),
                           key=lambda x: x[1]))
    _req(len(ordered) >= 2 and ordered[0][1] == 0, "scoring.levels needs >=2 levels starting at 0")
    _req(len({v for _, v in ordered}) == len(ordered), "scoring.levels bounds must be distinct")
    _req(ordered[-1][1] <= max_score, "scoring.levels bound exceeds max_score")

    r = _mapping(raw["retry"], "retry")
    for k in ("max_retries", "retryable_reason_codes"):
        _req(k in r, f"retry missing '{k}'")
    _req(isinstance(r["max_retries"], int) and not isinstance(r["max_retries"], bool)
         and r["max_retries"] >= 0, "retry.max_retries must be an integer >= 0")
    retryable = frozenset(_str_list(r["retryable_reason_codes"], "retry.retryable_reason_codes", True))
    _req(retryable <= set(codes), f"retry references unknown reason codes: {sorted(retryable - set(codes))}")
    _req(all(codes[c].blocking for c in retryable), "retryable reason codes must be blocking codes")
    # Fail-closed codes can never be retried into a pass.
    _req(not (retryable & {"INVALID_INPUT", "POLICY_INVALID", "EVALUATOR_ERROR"}),
         "input/policy/evaluator errors cannot be retryable")

    return Policy(
        version=raw["policy_version"], clock_skew_seconds=skew, severity_weights=weights,
        reason_codes=codes, requirements=tuple(reqs), source_precedence=precedence,
        blocker_category=b["category"], blocker_key=str(b["claim_key"]),
        blocker_open_values=open_v, blocker_resolved_values=res_v,
        blocker_critical_severities=crit_b, blocker_default_severity=b["default_severity"],
        conflict_critical_keys=frozenset(_str_list(c["critical_keys"], "conflicts.critical_keys", True)),
        conflict_critical_severities=crit_c,
        allow_override_of_critical_blocker=c["allow_precedence_override_of_critical_blocker"],
        status_behavior=behavior, missing_status_code=raw["missing_source_status_code"],
        max_score=max_score, blocking_floor=floor, levels=ordered,
        max_retries=r["max_retries"], retryable_codes=retryable)
