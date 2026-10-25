"""Evaluator Adapter.

Bridges between external agent contracts (Evidence Agent, Claim Extractor, Orchestrator)
and the internal Evaluator engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from src.contracts.claim import Claim as ContractClaim
from src.contracts.evidence import EvidenceRecord as ContractEvidence
from src.contracts.finding import Finding as ContractFinding
from src.evaluator.evaluator import Clock, Evaluator
from src.evaluator.models import (
    Claim,
    Decision,
    EvaluationResult,
    EvidenceRecord,
    Finding,
    SourceStatus,
)

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


CATEGORY_ALIASES: dict[str, str] = {
    "engineering_status": "engineering_status",
    "production_status": "engineering_status",
    "blocker_status": "engineering_status",
    "ownership": "ownership",
    "primary_contact": "ownership",
    "account_handler": "ownership",
}


def normalize_category(category: Any, key: Any = None) -> str:
    """Map known evidence fields and claim keys to policy categories."""
    raw_category = str(category).strip().lower() if category is not None else ""
    raw_key = str(key).strip().lower() if key is not None else ""

    if raw_category in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[raw_category]

    if raw_key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[raw_key]

    return raw_category or raw_key or "unknown"


def adapt_claim(raw: Any) -> Claim:
    """Adapt a raw dictionary or ContractClaim into an internal Claim model."""
    if isinstance(raw, Claim):
        return raw
    if isinstance(raw, ContractClaim):
        return Claim(
            claim_id=raw.claim_id,
            category=raw.category,
            key=raw.key,
            value=raw.value,
            validation_status=raw.validation_status,
            evidence_ids=raw.evidence_ids,
            source=normalize_source_name(raw.source) if raw.source else None,
            severity=raw.severity,
        )
    if isinstance(raw, Mapping):
        claim_id = raw.get("claim_id")
        key = raw.get("key") or raw.get("field")
        val = raw.get("value") if raw.get("value") is not None else raw.get("claimed_value")
        category = normalize_category(
            raw.get("category"),
            raw.get("key") or raw.get("field"),
        )
        validation_status = raw.get("validation_status") or "unvalidated"
        evidence_ids = raw.get("evidence_ids")
        if evidence_ids is None:
            raw_single = raw.get("evidence_id")
            evidence_ids_tuple: tuple[str, ...] = (str(raw_single),) if raw_single else ()
        elif isinstance(evidence_ids, str):
            evidence_ids_tuple = (evidence_ids,)
        elif isinstance(evidence_ids, (list, tuple)):
            evidence_ids_tuple = tuple(str(x) for x in evidence_ids if x is not None)
        else:
            evidence_ids_tuple = ()

        raw_source = raw.get("source")
        norm_source = normalize_source_name(str(raw_source)) if raw_source is not None else None
        sev = raw.get("severity")

        return Claim(
            claim_id=str(claim_id) if claim_id is not None else "",
            category=str(category),
            key=str(key) if key is not None else "",
            value=str(val) if val is not None else "",
            validation_status=str(validation_status),
            evidence_ids=evidence_ids_tuple,
            source=norm_source,
            severity=str(sev) if sev is not None else None,
        )
    return raw


def adapt_evidence(raw: Any) -> EvidenceRecord:
    """Adapt a raw dictionary or ContractEvidence into an internal EvidenceRecord."""
    if isinstance(raw, EvidenceRecord):
        return raw

    if isinstance(raw, ContractEvidence):
        return EvidenceRecord(
            evidence_id=raw.evidence_id,
            source=normalize_source_name(raw.source),
            category=normalize_category(raw.field),
            timestamp=raw.updated_at,
            value=str(raw.value) if raw.value is not None else None,
            account_id=getattr(raw, "account_id", None),
            excerpt=getattr(raw, "excerpt", None),
            field=raw.field,
        )

    if isinstance(raw, Mapping):
        evidence_id = raw.get("evidence_id")
        raw_source = raw.get("source") or raw.get("source_id") or ""
        raw_field = raw.get("field")
        norm_source = normalize_source_name(str(raw_source))

        category = normalize_category(
            raw.get("category"),
            raw.get("field"),
        )

        # Support updated_at from the shared contract, falling back to timestamp.
        ts = (
            raw.get("updated_at")
            if raw.get("updated_at") is not None
            else raw.get("timestamp")
        )

        value = raw.get("value")
        account_id = raw.get("account_id")
        excerpt = raw.get("excerpt")

        return EvidenceRecord(
            evidence_id=str(evidence_id) if evidence_id is not None else "",
            source=norm_source,
            category=str(category),
            timestamp=ts,
            value=str(value) if value is not None else None,
            account_id=str(account_id) if account_id is not None else None,
            excerpt=str(excerpt) if excerpt is not None else None,
            field=str(raw_field) if raw_field is not None else None,
        )

    return raw

def _normalise_claim_value(value: Any) -> str:
    """Normalize a value for conservative, case-insensitive comparison."""
    return " ".join(str(value).strip().casefold().split()) if value is not None else ""


def _claim_evidence_matches(claim: Claim, evidence: EvidenceRecord) -> bool:
    """Return True only when evidence matches the claim's category, key, and value."""
    if not evidence.evidence_id or not evidence.value:
        return False

    if not evidence.account_id:
        return False

    claim_category = normalize_category(claim.category, claim.key)
    evidence_category = normalize_category(evidence.category)

    if claim_category != evidence_category:
        return False

    # The evidence field must identify the same fact as the claim key.
    claim_key = str(claim.key).strip().casefold()
    evidence_key = (
        str(evidence.field).strip().casefold()
        if evidence.field is not None
        else str(evidence.category).strip().casefold()
    )
    aliases = {
        "blocker_status": {"blocker_status", "engineering_status", "production_status"},
        "engineering_status": {"blocker_status", "engineering_status", "production_status"},
        "production_status": {"blocker_status", "engineering_status", "production_status"},
        "ownership": {"ownership"},
        "primary_contact": {"primary_contact"},
        "account_handler": {"account_handler"},
        "implementation_owner": {"implementation_owner"},
    }

    compatible_keys = aliases.get(claim_key, {claim_key})
    if evidence_key not in compatible_keys:
        return False

    return _normalise_claim_value(claim.value) == _normalise_claim_value(evidence.value)


def validate_claims_against_evidence(
    claims: list[Claim],
    evidence: list[EvidenceRecord],
    account_id: str,
) -> list[Claim]:
    """Attach supporting evidence IDs only when support is unambiguous."""
    validated: list[Claim] = []

    for claim in claims:
        # Never trust pre-existing references without rechecking them.
        matching = [
            record
            for record in evidence
            if record.account_id == account_id
            and _claim_evidence_matches(claim, record)
        ]

        # Only records matching this specific claim key can establish
        # whether the claim has contradictory supporting evidence.
        claim_key = str(claim.key).strip().casefold()

        key_aliases = {
            "blocker_status": {
                "blocker_status",
                "engineering_status",
                "production_status",
            },
            "engineering_status": {
                "blocker_status",
                "engineering_status",
                "production_status",
            },
            "production_status": {
                "blocker_status",
                "engineering_status",
                "production_status",
            },
            "ownership": {"ownership"},
            "primary_contact": {"primary_contact"},
            "account_handler": {"account_handler"},
            "implementation_owner": {"implementation_owner"},
        }

        compatible_keys = key_aliases.get(claim_key, {claim_key})

        relevant_values = {
            _normalise_claim_value(record.value)
            for record in evidence
            if record.account_id == account_id
            and record.value is not None
            and (
                str(record.field).strip().casefold()
                if record.field is not None
                else str(record.category).strip().casefold()
            ) in compatible_keys
        }

        if len(relevant_values) > 1 or not matching:
            validated.append(
                Claim(
                    claim_id=claim.claim_id,
                    category=claim.category,
                    key=claim.key,
                    value=claim.value,
                    validation_status="unvalidated",
                    evidence_ids=(),
                    source=claim.source,
                    severity=claim.severity,
                )
            )
            continue

        validated.append(
            Claim(
                claim_id=claim.claim_id,
                category=claim.category,
                key=claim.key,
                value=claim.value,
                validation_status="validated",
                evidence_ids=tuple(record.evidence_id for record in matching),
                source=claim.source,
                severity=claim.severity,
            )
        )

    return validated

def adapt_status(raw: Any) -> SourceStatus:
    """Adapt a raw dictionary or SourceStatus model."""
    if isinstance(raw, SourceStatus):
        return SourceStatus(
            source=normalize_source_name(raw.source),
            status=raw.status,
            detail=raw.detail,
        )
    if isinstance(raw, Mapping):
        raw_src = raw.get("source") or raw.get("source_id") or ""
        norm_src = normalize_source_name(str(raw_src))
        status = raw.get("status")
        detail = raw.get("detail")
        return SourceStatus(
            source=norm_src,
            status=str(status) if status is not None else "",
            detail=str(detail) if detail is not None else None,
        )
    return raw


def to_contract_finding(finding: Finding) -> ContractFinding:
    """Convert an internal finding to the shared contract Finding dataclass."""
    return ContractFinding(
        reason_code=finding.reason_code,
        rule_id=finding.rule_id,
        severity=finding.severity,
        blocking=finding.blocking,
        description=finding.description,
        evidence_ids=finding.evidence_ids,
        subject=finding.subject,
        retryable=finding.retryable,
    )


class EvaluatorAdapter:
    """Adapter wrapping Evaluator to seamlessly handle orchestrator and contract formats."""

    def __init__(
        self,
        evaluator: Optional[Evaluator] = None,
        policy_path: Optional[Path] = None,
        clock: Optional[Clock] = None,
        raise_on_retry: bool = False,
    ) -> None:
        self._evaluator = evaluator or Evaluator(
            policy_path=policy_path,
            clock=clock,
            raise_on_retry=raise_on_retry,
        )

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
        """Translate inputs, invoke the Evaluator, and return the adapted result."""
        # Unpack evidence_bundle if provided
        if evidence_bundle is not None and isinstance(evidence_bundle, Mapping):
            if evidence is None:
                evidence = evidence_bundle.get("evidence", [])
            if source_statuses is None:
                bundle_statuses = evidence_bundle.get("source_statuses") or evidence_bundle.get("statuses")
                if bundle_statuses is not None:
                    source_statuses = bundle_statuses
                else:
                    # Infer available statuses for sources present in collected evidence
                    inferred_sources: set[str] = set()
                    for item in evidence or []:
                        raw_src = getattr(item, "source", None)
                        if raw_src is None and isinstance(item, Mapping):
                            raw_src = item.get("source") or item.get("source_id")
                        if raw_src:
                            inferred_sources.add(normalize_source_name(str(raw_src)))
                    source_statuses = [
                        SourceStatus(source=s, status="available")
                        for s in sorted(inferred_sources)
                    ]

        if source_statuses is None and statuses is not None:
            source_statuses = statuses

        # Adapt claims
        adapted_claims: Optional[list[Claim]] = None
        if isinstance(claims, (list, tuple)):
            adapted_claims = [adapt_claim(c) for c in claims]

        # Adapt evidence
        adapted_evidence: Optional[list[EvidenceRecord]] = None
        if isinstance(evidence, (list, tuple)):
            adapted_evidence = [adapt_evidence(e) for e in evidence]
         # Validate claims against evidence for this account before evaluation.
        if adapted_claims is not None and adapted_evidence is not None:
            account_id = (
                context.get("account_id")
                if isinstance(context, Mapping)
                else None
            )

            if isinstance(account_id, str) and account_id.strip():
                adapted_claims = validate_claims_against_evidence(
                    claims=adapted_claims,
                    evidence=adapted_evidence,
                    account_id=account_id,
                )
            else:
                # Fail closed if the account context is missing.
                adapted_claims = [
                    Claim(
                        claim_id=claim.claim_id,
                        category=claim.category,
                        key=claim.key,
                        value=claim.value,
                        validation_status="unvalidated",
                        evidence_ids=(),
                        source=claim.source,
                        severity=claim.severity,
                    )
                    for claim in adapted_claims
                ]

        # Adapt statuses
        adapted_statuses: Optional[list[SourceStatus]] = None
        if isinstance(source_statuses, (list, tuple)):
            adapted_statuses = [adapt_status(s) for s in source_statuses]

        result = self._evaluator.evaluate(
            claims=adapted_claims,
            evidence=adapted_evidence,
            source_statuses=adapted_statuses,
            retries_used=retries_used,
            raise_on_retry=raise_on_retry,
        )

        return result
