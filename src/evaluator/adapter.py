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
        category = raw.get("category") or "engineering_status"
        validation_status = raw.get("validation_status") or "validated"
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
        ts = raw.updated_at
        return EvidenceRecord(
            evidence_id=raw.evidence_id,
            source=normalize_source_name(raw.source),
            category="engineering_status",  # default requirement category
            timestamp=ts,
        )
    if isinstance(raw, Mapping):
        evidence_id = raw.get("evidence_id")
        raw_source = raw.get("source") or raw.get("source_id") or ""
        norm_source = normalize_source_name(str(raw_source))
        category = raw.get("category") or "engineering_status"
        # Support updated_at from shared contract, falling back to timestamp
        ts = raw.get("updated_at") if raw.get("updated_at") is not None else raw.get("timestamp")
        return EvidenceRecord(
            evidence_id=str(evidence_id) if evidence_id is not None else "",
            source=norm_source,
            category=str(category),
            timestamp=ts,
        )
    return raw


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
