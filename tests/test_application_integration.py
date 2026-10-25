"""Deterministic integration coverage across the application boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.controller.application import build_orchestrator
from src.controller.orchestrator import Orchestrator
from src.evaluator.adapter import EvaluatorAdapter
from src.evaluator.evaluator import Evaluator
from src.evidence.agent import EvidenceAgent
from src.evidence.providers.mock_provider import MockEvidenceProvider
from src.reporter.report_generator import ReportGenerator


class FixedModel:
    def generate(self, *, system_prompt, user_prompt):
        return json.dumps({"claims": [
            {"category": "engineering_status", "key": "blocker_status", "value": "blocked"}
        ]})


class FixedExtractor:
    def extract(self, *, request):
        return {"claims": [
            {"claim_id": "C-ENG", "category": "engineering_status", "key": "blocker_status",
             "value": "resolved", "validation_status": "validated", "evidence_ids": ["E-JIRA"],
             "source": "jira"},
            {"claim_id": "C-OWNER", "category": "ownership", "key": "owner",
             "value": "Team A", "validation_status": "validated", "evidence_ids": ["E-CRM"],
             "source": "crm"},
        ]}


class FixedEvidence:
    def __init__(self, *, conflict=False, omit_crm=False):
        self.conflict = conflict
        self.omit_crm = omit_crm

    def collect(self, account_id, claims=None, metadata=None):
        timestamp = "2026-10-24T12:00:00+00:00"
        evidence = [
            {"evidence_id": "E-JIRA", "source": "jira", "category": "engineering_status",
             "field": "blocker_status", "value": "resolved",
             "timestamp": timestamp, "account_id": account_id},
        ]
        statuses = [{"source": "jira", "status": "available"}]
        if not self.omit_crm:
            evidence.append({"evidence_id": "E-CRM", "source": "crm", "category": "ownership",
                             "field": "owner", "value": "Team A",
                             "timestamp": timestamp, "account_id": account_id})
            statuses.append({"source": "crm", "status": "available"})
        if self.conflict:
            evidence.append({"evidence_id": "E-GH", "source": "github", "category": "engineering_status",
                             "field": "blocker_status", "value": "blocked",
                             "timestamp": timestamp, "account_id": account_id})
        return {"evidence": evidence, "source_statuses": statuses,
                "missing_mandatory": [], "conflicts": [], "mandatory_satisfied": None}


def make_orchestrator(evidence_agent):
    fixed_now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    return Orchestrator(
        FixedExtractor(), evidence_agent,
        EvaluatorAdapter(Evaluator(clock=lambda: fixed_now)),
        ReportGenerator(enable_llm=False),
    )


def request():
    return {"handoff_id": "H-1", "account_id": "A-1", "source_text": "Handoff notes"}


def test_composition_root_runs_real_extractor_evidence_evaluator_and_reporter():
    result = build_orchestrator(model_client=FixedModel()).run({
        "handoff_id": "H-1", "account_id": "ACC001", "source_text": "Production is blocked."
    })

    assert result["disposition"] == "ESCALATE"
    assert result["claims"][0]["validation_status"] == "unvalidated"
    assert len(result["evidence"]) == 3
    assert result["evaluation"].decision.value == "ESCALATE"
    assert result["report"]["status"] == result["disposition"]
    assert result["report"]["citations_verified"] is True
    assert [item["evidence_id"] for item in result["report"]["evidence"]] == [
        item["evidence_id"] for item in result["evidence"]
    ]


def test_complete_component_contract_can_clear_and_report_matches_decision():
    result = make_orchestrator(FixedEvidence()).run(request())

    assert result["disposition"] == "CLEAR"
    assert result["report"]["status"] == "CLEAR"
    assert result["evaluation"].mandatory_satisfied is True
    assert result["report"]["citations_verified"] is True


def test_missing_required_evidence_and_unresolved_conflict_escalate():
    missing = make_orchestrator(FixedEvidence(omit_crm=True)).run(request())
    assert missing["disposition"] == "ESCALATE"
    assert missing["evaluation"].mandatory_satisfied is False

    conflicted_evidence = FixedEvidence(conflict=True)
    conflicted_claims = FixedExtractor()
    conflicted_claims.extract = lambda *, request: {"claims": [
        {"claim_id": "C-JIRA", "category": "engineering_status", "key": "blocker_status",
         "value": "blocked", "validation_status": "validated", "evidence_ids": ["E-JIRA"], "source": "jira"},
        {"claim_id": "C-GH", "category": "engineering_status", "key": "blocker_status",
         "value": "resolved", "validation_status": "validated", "evidence_ids": ["E-GH"], "source": "github"},
        {"claim_id": "C-OWNER", "category": "ownership", "key": "owner",
         "value": "Team A", "validation_status": "validated", "evidence_ids": ["E-CRM"], "source": "crm"},
    ]}
    conflict_result = Orchestrator(
        conflicted_claims, conflicted_evidence,
        EvaluatorAdapter(Evaluator(clock=lambda: datetime(2026, 10, 24, 12, tzinfo=timezone.utc))),
        ReportGenerator(enable_llm=False),
    ).run(request())
    assert conflict_result["disposition"] == "ESCALATE"
    assert conflict_result["evaluation"].conflicts


def test_provider_failure_is_visible_and_does_not_reach_evaluator():
    class BrokenProvider:
        def get_records(self, account_id):
            raise RuntimeError("provider details must not leak")

    orchestrator = Orchestrator(
        FixedExtractor(), EvidenceAgent(BrokenProvider()), EvaluatorAdapter(),
        ReportGenerator(enable_llm=False),
    )
    result = orchestrator.run(request())

    assert result["disposition"] == "ESCALATE"
    assert result["evaluation"] is None
    assert result["diagnostics"][0]["error"] == "component_failure"
    assert "provider details" not in str(result["diagnostics"])


def test_reporter_marks_unknown_evidence_citations_unverified():
    report = ReportGenerator(enable_llm=False).generate(
        {"decision": "ESCALATE", "findings": [
            {"description": "Unsupported finding", "evidence_ids": ["E-NOT-RETURNED"]}
        ]},
        {"evidence": [{"evidence_id": "E-REAL"}]},
    )

    assert report["citations_verified"] is False
    assert "manual review is required" in report["summary"]
