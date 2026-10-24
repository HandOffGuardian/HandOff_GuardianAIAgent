"""Evaluator entry point: claims + evidence + source statuses -> CLEAR/ESCALATE.

Safety boundary: CLEAR is returned only when no blocking finding exists. RETRY
is operational recovery for temporary failures only (see policy `retry`) and is
never an approval. Any bad input, policy failure or unexpected exception yields
ESCALATE. No LLM, network or database access happens here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Sequence, Set

from .models import (Claim, Decision, EvaluationResult, EvaluatorTransientError,
                     EvidenceRecord, Finding, SourceStatus)
from .policy import Policy, PolicyError, load_policy
from .risk_scoring import calculate_risk
from .rules import (check_blockers, check_claims, check_evidence,
                    check_source_status, make_finding, resolve_conflicts)

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_claim(c: Any) -> Any:
    if isinstance(c, Claim):
        return c
    if isinstance(c, Mapping):
        claim_id = c.get("claim_id")
        key = c.get("key") or c.get("field")
        val = c.get("value") if c.get("value") is not None else c.get("claimed_value")
        category = c.get("category") or "engineering_status"
        validation_status = c.get("validation_status") or "validated"
        raw_ev = c.get("evidence_ids")
        if raw_ev is None:
            raw_single = c.get("evidence_id")
            evidence_ids: tuple[str, ...] = (str(raw_single),) if raw_single else ()
        elif isinstance(raw_ev, str):
            evidence_ids = (raw_ev,)
        elif isinstance(raw_ev, (list, tuple)):
            evidence_ids = tuple(str(x) for x in raw_ev if x is not None)
        else:
            evidence_ids = ()
        return Claim(
            claim_id=str(claim_id) if claim_id is not None else "",
            category=str(category),
            key=str(key) if key is not None else "",
            value=str(val) if val is not None else "",
            validation_status=str(validation_status),
            evidence_ids=evidence_ids,
            source=str(c["source"]) if c.get("source") is not None else None,
            severity=str(c["severity"]) if c.get("severity") is not None else None,
        )
    return c


def _normalize_evidence(e: Any) -> Any:
    if isinstance(e, EvidenceRecord):
        return e
    if isinstance(e, Mapping):
        evidence_id = e.get("evidence_id")
        source = e.get("source") or e.get("source_id")
        category = e.get("category") or "engineering_status"
        ts = e.get("timestamp")
        return EvidenceRecord(
            evidence_id=str(evidence_id) if evidence_id is not None else "",
            source=str(source) if source is not None else "",
            category=str(category),
            timestamp=ts,
        )
    return e


def _normalize_status(s: Any) -> Any:
    if isinstance(s, SourceStatus):
        return s
    if isinstance(s, Mapping):
        source = s.get("source") or s.get("source_id")
        status = s.get("status")
        detail = s.get("detail")
        return SourceStatus(
            source=str(source) if source is not None else "",
            status=str(status) if status is not None else "",
            detail=str(detail) if detail is not None else None,
        )
    return s


def _validate_inputs(claims: object, evidence: object, statuses: object) -> List[str]:
    """Structural checks; returns human-readable problems (empty == OK)."""
    problems: List[str] = []
    for name, seq, typ in (("claims", claims, Claim), ("evidence", evidence, EvidenceRecord),
                           ("source_statuses", statuses, SourceStatus)):
        if not isinstance(seq, (list, tuple)):
            problems.append(f"{name} must be a list or tuple")
        elif not all(isinstance(x, typ) for x in seq):
            problems.append(f"{name} contains items that are not {typ.__name__}")
    if problems:
        return problems
    for c in claims:  # type: ignore[union-attr]
        if not (isinstance(c.claim_id, str) and c.claim_id and isinstance(c.category, str)
                and isinstance(c.key, str) and isinstance(c.value, str)
                and isinstance(c.validation_status, str)
                and isinstance(c.evidence_ids, (list, tuple))
                and all(isinstance(e, str) for e in c.evidence_ids)):
            problems.append(f"claim {getattr(c, 'claim_id', None)!r} has malformed fields")
    for e in evidence:  # type: ignore[union-attr]
        if not all(isinstance(v, str) and v for v in (e.evidence_id, e.source, e.category)):
            problems.append(f"evidence {getattr(e, 'evidence_id', None)!r} has malformed fields")
    for s in statuses:  # type: ignore[union-attr]
        if not (isinstance(s.source, str) and s.source and isinstance(s.status, str)):
            problems.append(f"source status {getattr(s, 'source', None)!r} is malformed")
    for label, ids in (("claim_id", [c.claim_id for c in claims]),  # type: ignore[union-attr]
                       ("evidence_id", [e.evidence_id for e in evidence]),  # type: ignore[union-attr]
                       ("source status source", [s.source for s in statuses])):  # type: ignore[union-attr]
        if len(set(ids)) != len(ids):
            problems.append(f"duplicate {label}")
    return problems


class Evaluator:
    def __init__(
        self,
        policy_path: Optional[Path] = None,
        clock: Optional[Clock] = None,
        raise_on_retry: bool = False,
    ) -> None:
        self._policy_path = policy_path
        self._clock = clock or _utc_now
        self._raise_on_retry = raise_on_retry

    def evaluate(
        self,
        claims: Any = None,
        evidence: Any = None,
        source_statuses: Any = None,
        retries_used: int = 0,
        *,
        evidence_bundle: Any = None,
        context: Any = None,
        raise_on_retry: Optional[bool] = None,
        statuses: Any = None,
        **kwargs: Any,
    ) -> EvaluationResult:
        """Evaluate handoff claims and evidence against policy.

        Supports both standard signature `(claims, evidence, source_statuses)`
        and the Orchestrator calling contract `(claims, evidence_bundle, context)`.
        """
        if raise_on_retry is None:
            raise_on_retry = self._raise_on_retry

        if source_statuses is None and statuses is not None:
            source_statuses = statuses

        # Adapt evidence_bundle if provided (Orchestrator style)
        if evidence_bundle is not None and isinstance(evidence_bundle, Mapping):
            if evidence is None:
                evidence = evidence_bundle.get("evidence", [])
            if source_statuses is None:
                source_statuses = evidence_bundle.get("source_statuses", evidence_bundle.get("statuses", []))


        # Normalize dicts if passed
        if isinstance(claims, (list, tuple)):
            claims = [_normalize_claim(c) for c in claims]
        if isinstance(evidence, (list, tuple)):
            evidence = [_normalize_evidence(e) for e in evidence]
        if isinstance(source_statuses, (list, tuple)):
            source_statuses = [_normalize_status(s) for s in source_statuses]

        try:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None:
                raise ValueError("clock must return a timezone-aware datetime")
            now = now.astimezone(timezone.utc)
        except Exception:
            now = _utc_now()  # still a real time; policy errors below handle the rest
        try:
            policy = load_policy(self._policy_path)
        except PolicyError as exc:
            return _fail_closed("POLICY_INVALID", f"Policy could not be loaded: {exc}", now)
        except Exception as exc:  # defensive: never CLEAR on surprises
            return _fail_closed("POLICY_INVALID", f"Policy loading failed unexpectedly: {exc!r}", now)

        try:
            result = self._evaluate(policy, claims, evidence, source_statuses, now, retries_used)
        except Exception as exc:
            result = self._result(policy, [make_finding(
                policy, "EVALUATOR_ERROR", "EVALUATOR",
                f"Unexpected evaluator error: {exc!r}")], now, 0)

        if raise_on_retry and result.decision is Decision.RETRY:
            raise EvaluatorTransientError(
                f"Temporary retryable failure during evaluation: {[f.description for f in result.findings if f.retryable]}",
                result.findings,
            )

        return result

    def _evaluate(self, policy: Policy, claims: Sequence[Claim], evidence: Sequence[EvidenceRecord],
                  statuses: Sequence[SourceStatus], now: datetime, retries_used: int) -> EvaluationResult:
        problems = _validate_inputs(claims, evidence, statuses)
        if not isinstance(retries_used, int) or isinstance(retries_used, bool) or retries_used < 0:
            problems.append("retries_used must be a non-negative integer")
            retries_used = policy.max_retries  # never grant a retry on bad input
        if problems:
            return self._result(policy, [make_finding(
                policy, "INVALID_INPUT", "INPUT", "Invalid evaluator input: " + "; ".join(problems))],
                now, retries_used)

        status_by_source = {s.source: s for s in statuses}
        known_ids: Set[str] = {e.evidence_id for e in evidence}
        findings: List[Finding] = []
        trusted: List[Claim] = []
        seen_claim_ids: Set[str] = set()
        for req in policy.requirements:
            src_findings, unusable = check_source_status(policy, req, status_by_source)
            findings += src_findings
            findings += check_evidence(policy, req, evidence, unusable, now)
            claim_findings, req_trusted = check_claims(policy, req, claims, known_ids)
            findings += claim_findings
            for c in req_trusted:
                if c.claim_id not in seen_claim_ids:
                    seen_claim_ids.add(c.claim_id)
                    trusted.append(c)
        conflict_findings, suppressed = resolve_conflicts(policy, trusted)
        findings += conflict_findings
        findings += check_blockers(policy, trusted, suppressed)
        return self._result(policy, findings, now, retries_used)

    @staticmethod
    def _result(policy: Policy, findings: Iterable[Finding], now: datetime,
                retries_used: int) -> EvaluationResult:
        ordered = list(findings)
        blocking = [f for f in ordered if f.blocking]
        # Mandatory blocking rules decide; the score is informational only.
        if not blocking:
            decision = Decision.CLEAR
        elif all(f.retryable for f in blocking) and retries_used < policy.max_retries:
            decision = Decision.RETRY  # temporary failures only, budget remains
        else:
            decision = Decision.ESCALATE
            if retries_used >= policy.max_retries:
                ordered = [replace(f, description=f.description + (
                    f" [retry budget exhausted: {retries_used}/{policy.max_retries} used]"))
                    if f.blocking and f.retryable else f for f in ordered]
        ordered_t = tuple(sorted(ordered, key=lambda f: (f.rule_id, f.reason_code, f.subject, f.evidence_ids)))
        score, level = calculate_risk(policy, ordered_t)
        missing_mandatory: List[str] = [
            f.description for f in ordered_t
            if f.reason_code in ("MISSING_REQUIRED_EVIDENCE", "MISSING_REQUIRED_CLAIM")
        ]
        conflicts: List[Any] = [
            f.description for f in ordered_t if "CONFLICT" in f.reason_code
        ]
        mandatory_satisfied = (len(missing_mandatory) == 0 and not any(
            f.blocking for f in ordered_t
            if f.reason_code in ("MISSING_REQUIRED_EVIDENCE", "MISSING_REQUIRED_CLAIM", "SOURCE_STATUS_MISSING")
        ))
        return EvaluationResult(
            decision,
            score,
            level,
            ordered_t,
            policy.version,
            now.isoformat(),
            missing_mandatory=tuple(missing_mandatory),
            conflicts=tuple(conflicts),
            mandatory_satisfied=mandatory_satisfied,
        )


def _fail_closed(code: str, description: str, now: datetime) -> EvaluationResult:
    """ESCALATE result used when no valid policy is available to classify findings."""
    finding = Finding(code, "POLICY", "critical", True, description, (), code)
    return EvaluationResult(
        Decision.ESCALATE,
        100,
        "critical",
        (finding,),
        None,
        now.isoformat(),
        missing_mandatory=(description,),
        conflicts=(),
        mandatory_satisfied=False,
    )


def evaluate_handoff(claims: Any = None, evidence: Any = None,
                     source_statuses: Any = None,
                     policy_path: Optional[Path] = None,
                     clock: Optional[Clock] = None,
                     retries_used: int = 0,
                     evidence_bundle: Any = None,
                     context: Any = None,
                     raise_on_retry: bool = False) -> EvaluationResult:
    return Evaluator(policy_path, clock, raise_on_retry=raise_on_retry).evaluate(
        claims=claims, evidence=evidence, source_statuses=source_statuses,
        retries_used=retries_used, evidence_bundle=evidence_bundle, context=context)

