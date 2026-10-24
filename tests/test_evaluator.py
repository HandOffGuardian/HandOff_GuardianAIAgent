"""Evaluator tests. Synthetic data, fixed clock. Uses the PROVISIONAL local models."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src.evaluator.evaluator import Evaluator, evaluate_handoff
from src.evaluator.models import Claim, Decision, EvidenceRecord, SourceStatus
from src.evaluator.policy import DEFAULT_POLICY_PATH, PolicyError, load_policy
from src.evaluator.risk_scoring import calculate_risk, risk_level

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def clock():
    return NOW


def hours_ago(h):
    return (NOW - timedelta(hours=h)).isoformat()


def good_evidence():
    return [
        EvidenceRecord("E-JIRA-1", "jira", "engineering_status", hours_ago(2)),
        EvidenceRecord("E-GH-1", "github", "engineering_status", hours_ago(3)),
        EvidenceRecord("E-CRM-1", "crm", "ownership", hours_ago(10)),
    ]


def good_claims():
    return [
        Claim("C-BLK", "engineering_status", "blocker_status", "resolved", "validated",
              ("E-JIRA-1",), "jira"),
        Claim("C-OWN", "ownership", "owner_ready", "yes", "validated", ("E-CRM-1",), "crm"),
    ]


def good_statuses():
    return [SourceStatus("jira", "available"), SourceStatus("crm", "available")]


def run(claims=None, evidence=None, statuses=None, policy_path=None, retries_used=0):
    return evaluate_handoff(
        good_claims() if claims is None else claims,
        good_evidence() if evidence is None else evidence,
        good_statuses() if statuses is None else statuses,
        policy_path=policy_path, clock=clock, retries_used=retries_used)


def codes(result):
    return {f.reason_code for f in result.findings}


def policy_with(tmp_path: Path, mutate) -> Path:
    raw = yaml.safe_load(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    mutate(raw)
    p = tmp_path / "policy.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return p


def replace(items, claim_id, **changes):
    return [Claim(**{**c.__dict__, **changes}) if c.claim_id == claim_id else c for c in items]


# 1
def test_all_requirements_satisfied_is_clear():
    r = run()
    assert r.decision is Decision.CLEAR
    assert not any(f.blocking for f in r.findings)
    assert r.risk_level == "low"


# 2
def test_critical_blocker_escalates():
    r = run(claims=replace(good_claims(), "C-BLK", value="open"))
    assert r.decision is Decision.ESCALATE
    assert "UNRESOLVED_CRITICAL_BLOCKER" in codes(r)


# 3
def test_missing_mandatory_evidence_escalates():
    ev = [e for e in good_evidence() if e.source != "jira" and e.source != "github"]
    r = run(evidence=ev)
    assert r.decision is Decision.ESCALATE
    assert "MISSING_REQUIRED_EVIDENCE" in codes(r)


# 4
@pytest.mark.parametrize("status,code", [("unavailable", "SOURCE_UNAVAILABLE"),
                                         ("timeout", "SOURCE_UNAVAILABLE"),
                                         ("error", "SOURCE_INVALID")])
def test_unavailable_source_escalates(status, code):
    # retries_used=1: the bounded retry is spent, so the incomplete check escalates.
    r = run(statuses=[SourceStatus("jira", status), SourceStatus("crm", "available")], retries_used=1)
    assert r.decision is Decision.ESCALATE and code in codes(r)


def test_missing_source_status_escalates():
    r = run(statuses=[SourceStatus("crm", "available")], retries_used=1)
    assert r.decision is Decision.ESCALATE and "SOURCE_STATUS_MISSING" in codes(r)


# 5
def test_stale_evidence_escalates():
    ev = [EvidenceRecord("E-JIRA-1", "jira", "engineering_status", hours_ago(49))] + good_evidence()[1:]
    r = run(evidence=ev, retries_used=1)
    assert r.decision is Decision.ESCALATE
    stale = [f for f in r.findings if f.reason_code == "STALE_EVIDENCE"]
    assert stale and stale[0].evidence_ids == ("E-JIRA-1",)


# RETRY: operational recovery only, bounded, never an approval
def test_temporary_failure_returns_retry_when_budget_remains():
    r = run(statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")])
    assert r.decision is Decision.RETRY
    assert all(f.retryable for f in r.findings if f.blocking)


@pytest.mark.parametrize("kwargs", [
    dict(statuses=[SourceStatus("crm", "available")]),  # missing status
    # claim cites other real evidence, so only the missing-evidence finding remains
    dict(claims=replace(good_claims(), "C-OWN", evidence_ids=("E-GH-1",)),
         evidence=[e for e in good_evidence() if e.source != "crm"]),  # missing evidence
    dict(evidence=[EvidenceRecord("E-JIRA-1", "jira", "engineering_status", hours_ago(49))]
         + good_evidence()[1:]),  # stale
])
def test_other_retryable_codes_return_retry(kwargs):
    assert run(**kwargs).decision is Decision.RETRY


def test_retry_budget_exhausted_escalates_and_notes_it():
    r = run(statuses=[SourceStatus("jira", "unavailable"), SourceStatus("crm", "available")],
            retries_used=1)
    assert r.decision is Decision.ESCALATE
    unavailable = [f for f in r.findings if f.reason_code == "SOURCE_UNAVAILABLE"]
    assert unavailable and "retry budget exhausted" in unavailable[0].description


def test_non_retryable_failure_escalates_even_with_budget():
    r = run(statuses=[SourceStatus("jira", "error"), SourceStatus("crm", "available")])
    assert r.decision is Decision.ESCALATE


def test_mixed_retryable_and_blocker_escalates_even_with_budget():
    r = run(claims=replace(good_claims(), "C-BLK", value="open"),
            statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")])
    assert r.decision is Decision.ESCALATE


def test_retry_is_never_clear_and_clear_needs_no_blocking_findings():
    for retries in (0, 1, 5):
        assert run(retries_used=retries).decision is Decision.CLEAR
        r = run(statuses=[], retries_used=retries)
        assert r.decision is not Decision.CLEAR


@pytest.mark.parametrize("bad", [-1, 1.5, "1", None, True])
def test_invalid_retries_used_escalates(bad):
    r = run(statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")],
            retries_used=bad)
    assert r.decision is Decision.ESCALATE and "INVALID_INPUT" in codes(r)


def test_policy_failures_never_retry(tmp_path):
    assert run(policy_path=tmp_path / "nope.yaml").decision is Decision.ESCALATE


@pytest.mark.parametrize("mutate", [
    lambda raw: raw["retry"].update(max_retries=-1),
    lambda raw: raw["retry"].update(retryable_reason_codes=["NOPE"]),
    lambda raw: raw["retry"].update(retryable_reason_codes=["INVALID_INPUT"]),
    lambda raw: raw["retry"].update(retryable_reason_codes=["MINOR_CONFLICT"]),
    lambda raw: raw.pop("retry"),
])
def test_invalid_retry_policy_rejected(tmp_path, mutate):
    p = policy_with(tmp_path, mutate)
    with pytest.raises(PolicyError):
        load_policy(p)
    assert run(policy_path=p).decision is Decision.ESCALATE


def test_zero_max_retries_never_retries(tmp_path):
    p = policy_with(tmp_path, lambda raw: raw["retry"].update(max_retries=0))
    r = run(statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")], policy_path=p)
    assert r.decision is Decision.ESCALATE


def test_freshness_boundary_is_inclusive():
    ev = [EvidenceRecord("E-JIRA-1", "jira", "engineering_status", hours_ago(48))] + good_evidence()[1:]
    assert run(evidence=ev).decision is Decision.CLEAR


@pytest.mark.parametrize("ts", [None, "not-a-date", "2026-01-15T10:00:00", hours_ago(-5)])
def test_bad_or_future_timestamp_escalates(ts):
    ev = [EvidenceRecord("E-JIRA-1", "jira", "engineering_status", ts)] + good_evidence()[1:]
    r = run(evidence=ev)
    assert r.decision is Decision.ESCALATE and "EVIDENCE_TIMESTAMP_INVALID" in codes(r)


# 6
def test_unresolvable_critical_conflict_escalates():
    # Neither source is in the precedence list -> no authority -> unresolved.
    claims = good_claims() + [
        Claim("C-X1", "engineering_status", "blocker_status", "resolved", "validated", ("E-JIRA-1",), "slack"),
        Claim("C-X2", "engineering_status", "blocker_status", "open", "validated", ("E-GH-1",), "wiki"),
    ]
    claims = [c for c in claims if c.claim_id != "C-BLK"]
    r = run(claims=claims)
    assert r.decision is Decision.ESCALATE and "CRITICAL_CONFLICT_UNRESOLVED" in codes(r)


def test_equal_authority_conflict_escalates():
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-A", "engineering_status", "blocker_status", "resolved", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-B", "engineering_status", "blocker_status", "open", "validated", ("E-JIRA-1",), "jira"),
    ]
    assert run(claims=claims).decision is Decision.ESCALATE


# 7
def test_noncritical_conflict_resolved_by_precedence():
    claims = good_claims() + [
        Claim("C-P1", "engineering_status", "priority", "p2", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-P2", "engineering_status", "priority", "p3", "validated", ("E-GH-1",), "github"),
    ]
    r = run(claims=claims)
    assert r.decision is Decision.CLEAR
    assert "CONFLICT_RESOLVED_BY_PRECEDENCE" in codes(r)


def test_precedence_cannot_override_critical_blocker_by_default():
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-J", "engineering_status", "blocker_status", "resolved", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-G", "engineering_status", "blocker_status", "open", "validated", ("E-GH-1",), "github"),
    ]
    r = run(claims=claims)
    assert r.decision is Decision.ESCALATE and "CRITICAL_CONFLICT_UNRESOLVED" in codes(r)


def test_precedence_override_when_policy_allows(tmp_path):
    p = policy_with(tmp_path, lambda raw: raw["conflicts"].update(
        allow_precedence_override_of_critical_blocker=True))
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-J", "engineering_status", "blocker_status", "resolved", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-G", "engineering_status", "blocker_status", "open", "validated", ("E-GH-1",), "github"),
    ]
    r = run(claims=claims, policy_path=p)
    assert r.decision is Decision.CLEAR and "CONFLICT_RESOLVED_BY_PRECEDENCE" in codes(r)


def test_higher_authority_open_blocker_wins_and_escalates():
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-J", "engineering_status", "blocker_status", "open", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-G", "engineering_status", "blocker_status", "resolved", "validated", ("E-GH-1",), "github"),
    ]
    r = run(claims=claims)
    assert r.decision is Decision.ESCALATE and "UNRESOLVED_CRITICAL_BLOCKER" in codes(r)


def test_newest_record_does_not_win_over_authority():
    # github evidence is newer, but jira outranks it.
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-J", "engineering_status", "blocker_status", "open", "validated", ("E-JIRA-1",), "jira"),
        Claim("C-G", "engineering_status", "blocker_status", "resolved", "validated", ("E-GH-1",), "github"),
    ]
    ev = [EvidenceRecord("E-JIRA-1", "jira", "engineering_status", hours_ago(20)),
          EvidenceRecord("E-GH-1", "github", "engineering_status", hours_ago(1)),
          good_evidence()[2]]
    assert run(claims=claims, evidence=ev).decision is Decision.ESCALATE


# 8
@pytest.mark.parametrize("status,code", [("failed", "CLAIM_VALIDATION_FAILED"),
                                         ("unvalidated", "CLAIM_VALIDATION_INCOMPLETE")])
def test_failed_or_incomplete_claim_validation_escalates(status, code):
    r = run(claims=replace(good_claims(), "C-OWN", validation_status=status))
    assert r.decision is Decision.ESCALATE and code in codes(r)


def test_missing_required_claim_escalates():
    r = run(claims=[c for c in good_claims() if c.claim_id != "C-OWN"])
    assert r.decision is Decision.ESCALATE and "MISSING_REQUIRED_CLAIM" in codes(r)


def test_unrecognised_blocker_value_is_not_assumed_resolved():
    r = run(claims=replace(good_claims(), "C-BLK", value="maybe"))
    assert r.decision is Decision.ESCALATE


# 9
def test_minor_inconsistency_does_not_escalate():
    claims = good_claims() + [
        Claim("C-M1", "ownership", "region", "emea", "validated", ("E-CRM-1",), "slack"),
        Claim("C-M2", "ownership", "region", "apac", "validated", ("E-CRM-1",), "wiki"),
    ]
    r = run(claims=claims)
    assert r.decision is Decision.CLEAR and "MINOR_CONFLICT" in codes(r)


def test_noncritical_blocker_does_not_escalate():
    claims = replace(good_claims(), "C-BLK", value="open", severity="low")
    r = run(claims=claims)
    assert r.decision is Decision.CLEAR and "UNRESOLVED_NONCRITICAL_BLOCKER" in codes(r)


# 10
def test_low_risk_score_cannot_override_blocking_rule(tmp_path):
    def zero(raw):
        for sev in raw["severities"].values():
            sev["weight"] = 0
        raw["scoring"]["blocking_floor"] = 0
    p = policy_with(tmp_path, zero)
    r = run(claims=replace(good_claims(), "C-BLK", value="open"), policy_path=p)
    assert r.risk_score == 0 and r.risk_level == "low"
    assert r.decision is Decision.ESCALATE


# 11
def test_findings_reference_only_real_evidence_ids():
    claims = replace(good_claims(), "C-BLK", value="open") + [
        Claim("C-GHOST", "ownership", "x", "y", "validated", ("E-CRM-1", "E-NOPE"), "crm")]
    r = run(claims=claims)
    real = {e.evidence_id for e in good_evidence()}
    assert r.decision is Decision.ESCALATE
    assert "UNKNOWN_EVIDENCE_REFERENCE" in codes(r)
    for f in r.findings:
        assert set(f.evidence_ids) <= real
    assert any(f.evidence_ids for f in r.findings)


def test_claim_without_evidence_escalates():
    r = run(claims=replace(good_claims(), "C-OWN", evidence_ids=()))
    assert r.decision is Decision.ESCALATE


# 12
@pytest.mark.parametrize("args", [
    (None, [], []),
    ("bad", [], []),
    ([], None, []),
    ([], [], "bad"),
    ([{"claim_id": "x"}], [], []),
    ([], [{"evidence_id": "x"}], []),
])
def test_invalid_inputs_never_clear(args):
    assert Evaluator(clock=clock).evaluate(*args).decision is Decision.ESCALATE


def test_empty_inputs_never_clear():
    assert run(claims=[], evidence=[], statuses=[]).decision is Decision.ESCALATE


def test_duplicate_ids_escalate():
    r = run(evidence=good_evidence() + [good_evidence()[0]])
    assert r.decision is Decision.ESCALATE and "INVALID_INPUT" in codes(r)


def test_malformed_field_types_escalate():
    bad = replace(good_claims(), "C-OWN", value=None)
    assert run(claims=bad).decision is Decision.ESCALATE


# 13
def test_missing_policy_file_escalates(tmp_path):
    r = run(policy_path=tmp_path / "nope.yaml")
    assert r.decision is Decision.ESCALATE and "POLICY_INVALID" in codes(r)


@pytest.mark.parametrize("content", ["", ":\n  - [unbalanced", "- just\n- a list\n", "policy_version: '1'\n"])
def test_malformed_policy_escalates(tmp_path, content):
    p = tmp_path / "policy.yaml"
    p.write_text(content, encoding="utf-8")
    r = run(policy_path=p)
    assert r.decision is Decision.ESCALATE and "POLICY_INVALID" in codes(r)


@pytest.mark.parametrize("mutate", [
    lambda raw: raw["requirements"][0].update(max_age_hours=-1),
    lambda raw: raw["requirements"][0].update(max_age_hours="soon"),
    lambda raw: raw["reason_codes"].update(BOGUS_CODE=dict(severity="low", blocking=False, description="x")),
    lambda raw: raw["reason_codes"].pop("STALE_EVIDENCE"),
    lambda raw: raw["reason_codes"]["STALE_EVIDENCE"].update(severity="nonexistent"),
    lambda raw: raw["source_precedence"].update(engineering_status=["jira", "jira"]),
    lambda raw: raw["source_precedence"].update(unknown_category=["jira"]),
    lambda raw: raw["source_status_behavior"].update(unavailable="pass"),
    lambda raw: raw["source_status_behavior"].update(error="NOT_A_CODE"),
    lambda raw: raw.update(approved_exceptions=[{"id": "x"}]),
    lambda raw: raw["scoring"].update(blocking_floor=500),
    lambda raw: raw["blockers"].update(resolved_values=["open"]),
    lambda raw: raw.pop("scoring"),
])
def test_invalid_policy_settings_rejected_and_never_clear(tmp_path, mutate):
    p = policy_with(tmp_path, mutate)
    with pytest.raises(PolicyError):
        load_policy(p)
    assert run(policy_path=p).decision is Decision.ESCALATE


def test_default_policy_loads_and_is_cwd_independent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_policy().version
    assert run().decision is Decision.CLEAR


# 14
def test_injected_clock_controls_freshness():
    ev = good_evidence()
    later = lambda: NOW + timedelta(hours=100)
    r = evaluate_handoff(good_claims(), ev, good_statuses(), clock=later, retries_used=1)
    assert r.decision is Decision.ESCALATE and "STALE_EVIDENCE" in codes(r)
    assert run().decision is Decision.CLEAR


def test_naive_clock_does_not_produce_clear():
    # A naive clock is rejected; evaluator falls back to real time, so the
    # 2026-01 fixtures cannot be silently treated as fresh for a bogus "now".
    r = evaluate_handoff(good_claims(), good_evidence(), good_statuses(),
                         clock=lambda: datetime(2026, 1, 15, 12, 0))
    assert r.evaluated_at is not None


# 15
def test_repeated_evaluation_is_identical():
    claims = replace(good_claims(), "C-BLK", value="open")
    assert run(claims=claims) == run(claims=claims)
    assert run() == run()


def test_input_order_does_not_change_result():
    claims = replace(good_claims(), "C-BLK", value="open")
    assert run(claims=claims) == run(claims=list(reversed(claims)), evidence=list(reversed(good_evidence())))


# 16
def test_risk_scoring_consistent_with_policy():
    policy = load_policy()
    clean = run()
    blocker = run(claims=replace(good_claims(), "C-BLK", value="open"))
    minor = run(claims=good_claims() + [
        Claim("C-M1", "ownership", "region", "emea", "validated", ("E-CRM-1",), "slack"),
        Claim("C-M2", "ownership", "region", "apac", "validated", ("E-CRM-1",), "wiki")])
    assert clean.risk_score == 0
    assert minor.risk_score == 3  # one low-severity issue
    assert blocker.risk_score >= policy.blocking_floor
    assert blocker.risk_score > minor.risk_score > clean.risk_score
    assert 0 <= blocker.risk_score <= policy.max_score
    assert blocker.risk_level == risk_level(policy, blocker.risk_score)


def test_score_does_not_double_count_same_issue():
    policy = load_policy()
    claims = [c for c in good_claims() if c.claim_id != "C-BLK"] + [
        Claim("C-A", "engineering_status", "blocker_status", "open", "validated", ("E-JIRA-1",), "slack"),
        Claim("C-B", "engineering_status", "blocker_status", "resolved", "validated", ("E-GH-1",), "wiki"),
    ]
    r = run(claims=claims)
    # conflict + open blocker share one subject -> one critical weight (40), floored to 50
    assert r.risk_score == max(40, policy.blocking_floor)


def test_risk_level_boundaries():
    policy = load_policy()
    assert risk_level(policy, 0) == "low"
    assert risk_level(policy, 24) == "low"
    assert risk_level(policy, 25) == "medium"
    assert risk_level(policy, 75) == "critical"
    assert risk_level(policy, 100) == "critical"
    assert calculate_risk(policy, ())[0] == 0


def test_every_finding_has_reason_description_and_rule():
    r = run(claims=replace(good_claims(), "C-BLK", value="open"))
    for f in r.findings:
        assert f.reason_code and f.rule_id and f.description and f.severity


# Orchestrator Integration & Normalization Tests
def test_orchestrator_contract_mapping_and_normalization():
    from collections.abc import Mapping
    evaluator = Evaluator(clock=clock)
    claims = [
        {"claim_id": "C-BLK", "field": "blocker_status", "claimed_value": "resolved",
         "category": "engineering_status", "validation_status": "validated",
         "evidence_ids": ["E-JIRA-1"], "source": "jira"},
        {"claim_id": "C-OWN", "field": "owner_ready", "claimed_value": "yes",
         "category": "ownership", "validation_status": "validated",
         "evidence_ids": ["E-CRM-1"], "source": "crm"},
    ]
    evidence_bundle = {
        "evidence": [
            {"evidence_id": "E-JIRA-1", "source_id": "jira", "category": "engineering_status", "timestamp": hours_ago(2)},
            {"evidence_id": "E-GH-1", "source_id": "github", "category": "engineering_status", "timestamp": hours_ago(3)},
            {"evidence_id": "E-CRM-1", "source_id": "crm", "category": "ownership", "timestamp": hours_ago(10)},
        ],
        "source_statuses": [
            {"source_id": "jira", "status": "available"},
            {"source_id": "crm", "status": "available"},
        ],
        "missing_mandatory": [],
        "conflicts": [],
    }
    context = {"handoff_id": "H-123", "account_id": "A-456", "source_text": "Sample"}
    r = evaluator.evaluate(claims=claims, evidence_bundle=evidence_bundle, context=context)

    # Validates against Orchestrator's expectations
    assert isinstance(r, Mapping)
    assert r.get("decision") == "CLEAR"
    assert r.get("mandatory_satisfied") is True
    assert isinstance(r.get("findings"), list)
    assert isinstance(r.get("missing_mandatory"), list)
    assert isinstance(r.get("conflicts"), list)
    assert r["risk_level"] == "low"
    assert r["risk_score"] == 0


def test_orchestrator_missing_sources_never_default_to_available():
    evaluator = Evaluator(clock=clock)
    claims = [
        {"claim_id": "C-BLK", "field": "blocker_status", "claimed_value": "resolved",
         "evidence_ids": ["E-JIRA-1"]},
    ]
    # No source_statuses provided in bundle
    evidence_bundle = {
        "evidence": [
            {"evidence_id": "E-JIRA-1", "source_id": "jira", "timestamp": hours_ago(2)},
        ],
    }
    r = evaluator.evaluate(claims=claims, evidence_bundle=evidence_bundle, retries_used=1)
    # Must NOT assume available; must escalate or flag missing source status
    assert r.get("decision") == "ESCALATE"
    assert r.get("mandatory_satisfied") is False
    codes_found = {f.reason_code for f in r.findings}
    assert "SOURCE_STATUS_MISSING" in codes_found


def test_retry_both_return_code_and_transient_exception():
    from src.evaluator.models import EvaluatorTransientError

    # 1. raise_on_retry=False (default): returns decision "RETRY"
    evaluator_return = Evaluator(clock=clock, raise_on_retry=False)
    r = evaluator_return.evaluate(
        claims=good_claims(),
        evidence=good_evidence(),
        statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")],
        retries_used=0,
    )
    assert r.get("decision") == "RETRY"
    assert r.decision is Decision.RETRY

    # 2. raise_on_retry=True: raises EvaluatorTransientError for orchestrator's retry handler
    evaluator_raise = Evaluator(clock=clock, raise_on_retry=True)
    with pytest.raises(EvaluatorTransientError) as exc_info:
        evaluator_raise.evaluate(
            claims=good_claims(),
            evidence=good_evidence(),
            statuses=[SourceStatus("jira", "timeout"), SourceStatus("crm", "available")],
            retries_used=0,
        )
    assert exc_info.value.transient is True
    assert exc_info.value.safe_to_retry is True


