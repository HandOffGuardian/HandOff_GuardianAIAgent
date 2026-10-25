"""Deterministic, independently testable policy checks.

Each check returns Findings; none of them decide CLEAR/ESCALATE (the agent
does, from the `blocking` flag). Absence of evidence is never treated as a
pass, and evidence IDs are only ever copied from the input.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .models import Claim, EvidenceRecord, Finding, SourceStatus
from .policy import Policy, Requirement


def norm(value: object) -> str:
    return str(value).strip().lower()


def make_finding(policy: Policy, code: str, rule_id: str, description: str,
                 evidence_ids: Iterable[str] = (), subject: str = "") -> Finding:
    """Build a Finding whose severity/blocking come only from the policy."""
    rc = policy.reason_codes[code]
    return Finding(code, rule_id, rc.severity, rc.blocking, description,
                   tuple(sorted(set(evidence_ids))), subject or code,
                   code in policy.retryable_codes)


def parse_timestamp(value: Union[datetime, str, None]) -> Optional[datetime]:
    """Aware UTC datetime, or None if missing/naive/unparseable."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def check_source_status(policy: Policy, req: Requirement,
                        statuses: Mapping[str, SourceStatus]) -> Tuple[List[Finding], Set[str]]:
    """Mandatory sources must report an acceptable status. Returns (findings, unusable sources)."""
    findings: List[Finding] = []
    unusable: Set[str] = set()
    for source in req.required_sources:
        subject = f"source:{source}"
        st = statuses.get(source)
        if st is None:
            code = policy.missing_status_code
            desc = f"{req.id}: mandatory source '{source}' reported no status."
        elif norm(st.status) not in policy.status_behavior:
            code = "INVALID_INPUT"
            desc = f"{req.id}: source '{source}' reported unrecognised status {st.status!r}."
        else:
            code = policy.status_behavior[norm(st.status)]
            desc = f"{req.id}: mandatory source '{source}' status is '{norm(st.status)}'."
        if code is not None:
            unusable.add(source)
            findings.append(make_finding(policy, code, req.id, desc, subject=subject))
    return findings, unusable


def check_evidence(policy: Policy, req: Requirement, evidence: Sequence[EvidenceRecord],
                   unusable_sources: Set[str], now: datetime) -> List[Finding]:
    """Each usable required source needs at least one fresh evidence record."""
    findings: List[Finding] = []
    max_age = timedelta(hours=req.max_age_hours)
    skew = timedelta(seconds=policy.clock_skew_seconds)
    for source in req.required_sources:
        if source in unusable_sources:  # already reported as a source issue
            continue
        subject = f"evidence:{req.category}:{source}"
        records = [e for e in evidence if e.category == req.category and e.source == source]
        if not records:
            findings.append(make_finding(
                policy, "MISSING_REQUIRED_EVIDENCE", req.id,
                f"{req.id}: no '{req.category}' evidence from mandatory source '{source}'.",
                subject=subject))
            continue
        fresh, stale, invalid = [], [], []
        for rec in records:
            ts = parse_timestamp(rec.timestamp)
            if ts is None or ts > now + skew:
                invalid.append(rec.evidence_id)
            elif now - ts <= max_age:
                fresh.append(rec.evidence_id)
            else:
                stale.append(rec.evidence_id)
        if fresh:
            continue
        if stale:
            findings.append(make_finding(
                policy, "STALE_EVIDENCE", req.id,
                f"{req.id}: all '{req.category}' evidence from '{source}' is older than "
                f"{req.max_age_hours:g}h.", stale, subject))
        if invalid:
            findings.append(make_finding(
                policy, "EVIDENCE_TIMESTAMP_INVALID", req.id,
                f"{req.id}: '{req.category}' evidence from '{source}' has an invalid timestamp.",
                invalid, subject))
    return findings


def check_claims(policy: Policy, req: Requirement, claims: Sequence[Claim],
                 known_ids: Set[str]) -> Tuple[List[Finding], List[Claim]]:
    """Validate claims of a required category. Returns (findings, trusted claims)."""
    findings: List[Finding] = []
    trusted: List[Claim] = []
    in_cat = [c for c in claims if c.category == req.category]
    if req.require_claim and not in_cat:
        findings.append(make_finding(
            policy, "MISSING_REQUIRED_CLAIM", req.id,
            f"{req.id}: no claim provided for category '{req.category}'.",
            subject=f"category:{req.category}"))
    for c in in_cat:
        subject = f"claim:{c.claim_id}"
        status = norm(c.validation_status)
        known = [e for e in c.evidence_ids if e in known_ids]
        if status == "failed":
            findings.append(make_finding(
                policy, "CLAIM_VALIDATION_FAILED", req.id,
                f"{req.id}: claim '{c.claim_id}' failed validation.", known, subject))
        elif status != "validated":
            findings.append(make_finding(
                policy, "CLAIM_VALIDATION_INCOMPLETE", req.id,
                f"{req.id}: claim '{c.claim_id}' is not validated (status {c.validation_status!r}).",
                known, subject))
        elif not c.evidence_ids:
            findings.append(make_finding(
                policy, "CLAIM_VALIDATION_INCOMPLETE", req.id,
                f"{req.id}: claim '{c.claim_id}' cites no supporting evidence.", subject=subject))
        elif len(known) != len(c.evidence_ids):
            findings.append(make_finding(
                policy, "UNKNOWN_EVIDENCE_REFERENCE", req.id,
                f"{req.id}: claim '{c.claim_id}' cites evidence IDs absent from the input.",
                known, subject))
        else:
            trusted.append(c)
    return findings, trusted


def _rank(policy: Policy, claim: Claim) -> Optional[int]:
    order = policy.source_precedence.get(claim.category, ())
    return order.index(claim.source) if claim.source in order else None


def _effective_blocker_severity(policy: Policy, claim: Claim) -> str:
    return claim.severity or policy.blocker_default_severity


def resolve_conflicts(policy: Policy, trusted: Sequence[Claim]) -> Tuple[List[Finding], Set[str]]:
    """Detect value conflicts per (category, key) and apply source precedence.

    Returns (findings, ids of claims superseded by a higher-authority source).
    Recency is deliberately ignored; only configured authority decides.
    """
    groups: Dict[Tuple[str, str], List[Claim]] = defaultdict(list)
    for c in trusted:
        groups[(c.category, c.key)].append(c)
    findings: List[Finding] = []
    suppressed: Set[str] = set()
    for (category, key), members in sorted(groups.items()):
        by_value: Dict[str, List[Claim]] = defaultdict(list)
        for c in members:
            by_value[norm(c.value)].append(c)
        if len(by_value) < 2:
            continue
        subject = f"fact:{category}/{key}"
        ev_ids = [e for c in members for e in c.evidence_ids]
        is_blocker = category == policy.blocker_category and key == policy.blocker_key
        critical = (key in policy.conflict_critical_keys
                    or any(c.severity in policy.conflict_critical_severities for c in members))
        best: Dict[str, Optional[int]] = {}
        for value, cs in by_value.items():
            ranks = [r for r in (_rank(policy, c) for c in cs) if r is not None]
            best[value] = min(ranks) if ranks else None
        ranked = sorted((r, v) for v, r in best.items() if r is not None)
        winner = None
        if ranked and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
            winner = ranked[0][1]
        losers = [c for v, cs in by_value.items() if v != winner for c in cs]
        override_blocked = (
            winner is not None and is_blocker and not policy.allow_override_of_critical_blocker
            and any(norm(c.value) in policy.blocker_open_values
                    and _effective_blocker_severity(policy, c) in policy.blocker_critical_severities
                    for c in losers))
        if winner is not None and not override_blocked:
            suppressed.update(c.claim_id for c in losers)
            findings.append(make_finding(
                policy, "CONFLICT_RESOLVED_BY_PRECEDENCE", "CONFLICT",
                f"Conflict on {category}/{key} resolved by source precedence "
                f"(value {winner!r} from higher-authority source).", ev_ids, subject))
        elif critical:
            findings.append(make_finding(
                policy, "CRITICAL_CONFLICT_UNRESOLVED", "CONFLICT",
                f"Sources disagree on {category}/{key} and policy cannot resolve it.",
                ev_ids, subject))
        else:
            findings.append(make_finding(
                policy, "MINOR_CONFLICT", "CONFLICT",
                f"Sources disagree on non-critical fact {category}/{key}.", ev_ids, subject))
    return findings, suppressed


def check_blockers(policy: Policy, trusted: Sequence[Claim], suppressed: Set[str]) -> List[Finding]:
    """Open engineering blockers; unrecognised values are never assumed resolved."""
    findings: List[Finding] = []
    for c in trusted:
        if (c.category != policy.blocker_category or c.key != policy.blocker_key
                or c.claim_id in suppressed):
            continue
        value = norm(c.value)
        subject = f"fact:{c.category}/{c.key}"
        if value in policy.blocker_open_values:
            critical = _effective_blocker_severity(policy, c) in policy.blocker_critical_severities
            code = "UNRESOLVED_CRITICAL_BLOCKER" if critical else "UNRESOLVED_NONCRITICAL_BLOCKER"
            findings.append(make_finding(
                policy, code, "BLOCKERS",
                f"Claim '{c.claim_id}' reports an open engineering blocker ({value}).",
                c.evidence_ids, subject))
        elif value not in policy.blocker_resolved_values:
            findings.append(make_finding(
                policy, "CLAIM_VALIDATION_INCOMPLETE", "BLOCKERS",
                f"Claim '{c.claim_id}' has unrecognised blocker value {c.value!r}.",
                c.evidence_ids, f"claim:{c.claim_id}"))
    return findings

def detect_evidence_conflicts(
    policy: Policy,
    evidence: Sequence[EvidenceRecord],
) -> List[Finding]:
    """Detect contradictory values reported for the same account and fact.

    This check reports disagreements; it does not decide which source is
    authoritative or treat either record as validated.
    """
    groups: Dict[Tuple[str, str, str], List[EvidenceRecord]] = defaultdict(list)

    for record in evidence:
        if record.value is None or not record.value.strip():
            continue

        account = norm(record.account_id or "")
        category = norm(record.category)
        source = norm(record.source)

        # Avoid comparing unrelated accounts or records without a known account.
        if not account:
            continue

        # Normalize common field aliases so equivalent fields are compared.
        field_aliases = {
            "production_status": "engineering_status",
            "blocker_status": "engineering_status",
            "engineering_status": "engineering_status",
            "primary_contact": "ownership",
            "account_handler": "ownership",
            "ownership": "ownership",
        }
        fact = field_aliases.get(category, category)

        # Source is retained in the record, but intentionally excluded from
        # the group key so disagreements across sources can be detected.
        groups[(account, fact, "value")].append(record)

    findings: List[Finding] = []

    for (account, fact, _), records in sorted(groups.items()):
        values: Dict[str, List[EvidenceRecord]] = defaultdict(list)

        for record in records:
            values[norm(record.value)].append(record)

        if len(values) < 2:
            continue

        evidence_ids = [
            record.evidence_id
            for record in records
        ]

        # Engineering status conflicts are critical because one source may
        # report a blocker while another suggests readiness.
        critical = fact == norm(policy.blocker_category)

        if critical:
            code = "CRITICAL_CONFLICT_UNRESOLVED"
        else:
            code = "MINOR_CONFLICT"

        findings.append(
            make_finding(
                policy,
                code,
                "EVIDENCE_CONFLICT",
                (
                    f"Conflicting evidence for account '{account}', "
                    f"fact '{fact}': "
                    + "; ".join(
                        f"{record.source} reported {record.value!r} "
                        f"(evidence {record.evidence_id})"
                        for record in records
                    )
                ),
                evidence_ids=evidence_ids,
                subject=f"evidence-conflict:{account}:{fact}",
            )
        )

    return findings