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

from src.contracts.finding import Finding as ContractFinding
from .models import (Claim, Decision, EvaluationResult, EvaluatorTransientError,
                     EvidenceRecord, Finding, SourceStatus)
from .policy import Policy, PolicyError, load_policy
from .risk_scoring import calculate_risk
from .rules import (
    check_blockers,
    check_claims,
    check_evidence,
    check_source_status,
    detect_evidence_conflicts,
    make_finding,
    resolve_conflicts,
)
Clock = Callable[[], datetime]

CATEGORY_ALIASES = {"engineering_status": "engineering_status", "production_status": "engineering_status", "blocker_status": "engineering_status", "ownership": "ownership", "primary_contact": "ownership", "account_handler": "ownership"}

def normalize_category(category: Any, key: Any = None) -> str:
    raw = str(category).strip().lower() if category is not None else ""
    field = str(key).strip().lower() if key is not None else ""
    return CATEGORY_ALIASES.get(raw, CATEGORY_ALIASES.get(field, raw or field or "unknown"))

SOURCE_ALIASES: dict[str, str] = {
    "engineering ticket": "jira",
    "engineering_ticket": "jira",
    "jira": "jira",
    "crm": "crm",
    "github": "github",
    "chat": "chat",
    "onboarding project": "onboarding_project",
    "onboarding_project": "onboarding_project",
}


def normalize_source_name(source: str) -> str:
    """Normalize source names (e.g., 'Engineering Ticket' -> 'jira', 'CRM' -> 'crm')."""
    if not source:
        return ""
    clean = source.strip().lower()
    return SOURCE_ALIASES.get(clean, clean)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_claim(c: Any) -> Any:
    if isinstance(c, Claim):
        return c
    if hasattr(c, "claim_id") and hasattr(c, "category") and hasattr(c, "key") and hasattr(c, "value"):
        # Shared ContractClaim object
        return Claim(
            claim_id=str(c.claim_id),
            category=str(c.category),
            key=str(c.key),
            value=str(c.value),
            validation_status=str(getattr(c, "validation_status", "validated")),
            evidence_ids=tuple(getattr(c, "evidence_ids", ())),
            source=normalize_source_name(getattr(c, "source", None) or "") or None,
            severity=str(c.severity) if getattr(c, "severity", None) is not None else None,
        )
    if isinstance(c, Mapping):
        claim_id = c.get("claim_id")
        key = c.get("key") or c.get("field")
        val = c.get("value") if c.get("value") is not None else c.get("claimed_value")
        category = normalize_category(c.get("category"), key)
        validation_status = c.get("validation_status") or "unvalidated"
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

        raw_source = c.get("source")
        norm_source = normalize_source_name(str(raw_source)) if raw_source is not None else None

        return Claim(
            claim_id=str(claim_id) if claim_id is not None else "",
            category=str(category),
            key=str(key) if key is not None else "",
            value=str(val) if val is not None else "",
            validation_status=str(validation_status),
            evidence_ids=evidence_ids,
            source=norm_source,
            severity=str(c["severity"]) if c.get("severity") is not None else None,
        )
    return c


def _normalize_evidence(e: Any) -> Any:
    """Normalize evidence while preserving its original content and provenance."""
    if isinstance(e, EvidenceRecord):
        return e

    if hasattr(e, "updated_at") and hasattr(e, "evidence_id"):
        ts = e.updated_at
        src = normalize_source_name(getattr(e, "source", ""))

        raw_value = getattr(e, "value", None)
        raw_account_id = getattr(e, "account_id", None)
        raw_excerpt = getattr(e, "excerpt", None)

        return EvidenceRecord(
            evidence_id=str(e.evidence_id),
            source=src,
            category=normalize_category(None, getattr(e, "field", None)),
            timestamp=ts,
            value=str(raw_value) if raw_value is not None else None,
            account_id=(
                str(raw_account_id) if raw_account_id is not None else None
            ),
            excerpt=str(raw_excerpt) if raw_excerpt is not None else None,
        )

    if isinstance(e, Mapping):
        evidence_id = e.get("evidence_id")
        raw_source = e.get("source") or e.get("source_id") or ""
        norm_source = normalize_source_name(str(raw_source))
        category = normalize_category(e.get("category"), e.get("field"))

        ts = (
            e.get("updated_at")
            if e.get("updated_at") is not None
            else e.get("timestamp")
        )

        raw_value = e.get("value")
        raw_account_id = e.get("account_id")
        raw_excerpt = e.get("excerpt")

        return EvidenceRecord(
            evidence_id=str(evidence_id) if evidence_id is not None else "",
            source=norm_source,
            category=str(category),
            timestamp=ts,
            value=str(raw_value) if raw_value is not None else None,
            account_id=(
                str(raw_account_id) if raw_account_id is not None else None
            ),
            excerpt=str(raw_excerpt) if raw_excerpt is not None else None,
        )

    return e

def _normalize_status(s: Any) -> Any:
    if isinstance(s, SourceStatus):
        return s
    if isinstance(s, Mapping):
        raw_source = s.get("source") or s.get("source_id") or ""
        norm_source = normalize_source_name(str(raw_source))
        status = s.get("status")
        detail = s.get("detail")
        return SourceStatus(
            source=norm_source,
            status=str(status) if status is not None else "",
            detail=str(detail) if detail is not None else None,
        )
    return s


def to_contract_finding(f: Any) -> ContractFinding:
    """Ensure finding conforms to the shared Finding contract."""
    if isinstance(f, ContractFinding):
        return f
    return ContractFinding(
        reason_code=f.reason_code,
        rule_id=f.rule_id,
        severity=f.severity,
        blocking=f.blocking,
        description=f.description,
        evidence_ids=tuple(str(x) for x in f.evidence_ids),
        subject=f.subject or "",
        retryable=f.retryable,
    )


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
        if not (isinstance(c.claim_id, str) and c.claim_id and isinstance(c.category, str) and c.category.strip() and c.category != "unknown"
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
                bundle_statuses = evidence_bundle.get("source_statuses") or evidence_bundle.get("statuses")
                if bundle_statuses is not None:
                    source_statuses = bundle_statuses
                else:
                    # A record proves only that a record was returned; it does
                    # not prove that the mandatory provider completed a check.
                    source_statuses = []

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


        # Inspect raw evidence independently of claim validation.

        findings += detect_evidence_conflicts(policy, evidence)

        # Preserve existing trusted-claim conflict resolution and blocker checks.
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
        # A requirement is not satisfied if any blocking finding remains,
        # including invalid input, incomplete validation, or provider failure.
        mandatory_satisfied = not any(f.blocking for f in ordered_t)
        contract_findings = tuple(to_contract_finding(f) for f in ordered_t)
        return EvaluationResult(
            decision,
            score,
            level,
            contract_findings,
            policy.version,
            now.isoformat(),
            missing_mandatory=tuple(missing_mandatory),
            conflicts=tuple(conflicts),
            mandatory_satisfied=mandatory_satisfied,
        )


def _fail_closed(code: str, description: str, now: datetime) -> EvaluationResult:
    """ESCALATE result used when no valid policy is available to classify findings."""
    finding = to_contract_finding(Finding(code, "POLICY", "critical", True, description, (), code))
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
