from src.evaluator.adapter import (
    adapt_claim,
    adapt_evidence,
    validate_claims_against_evidence,
)


def make_claim(category="engineering_status", key="blocker_status", value="blocked"):
    return adapt_claim({
        "claim_id": "C001",
        "category": category,
        "key": key,
        "value": value,
        "validation_status": "unvalidated",
    })


def make_evidence(
    evidence_id="EV001",
    account_id="ACC001",
    field="production_status",
    value="blocked",
    source="Engineering Ticket",
):
    return adapt_evidence({
        "evidence_id": evidence_id,
        "source": source,
        "account_id": account_id,
        "field": field,
        "value": value,
        "updated_at": "2026-10-24T12:00:00+00:00",
        "excerpt": f"Recorded value: {value}",
    })


def test_matching_evidence_validates_claim_and_attaches_id():
    claim = make_claim()
    evidence = [make_evidence()]

    result = validate_claims_against_evidence(claims=[claim], evidence=evidence, account_id="ACC001")

    assert result[0].validation_status == "validated"
    assert result[0].evidence_ids == ("EV001",)


def test_wrong_account_evidence_does_not_validate_claim():
    claim = make_claim()
    evidence = [make_evidence(account_id="ACC002")]

    result = validate_claims_against_evidence(claims=[claim], evidence=evidence, account_id="ACC001")

    assert result[0].validation_status == "unvalidated"
    assert result[0].evidence_ids == ()


def test_mismatched_value_does_not_validate_claim():
    claim = make_claim(value="blocked")
    evidence = [make_evidence(value="ready")]

    result = validate_claims_against_evidence(claims=[claim], evidence=evidence, account_id="ACC001")

    assert result[0].validation_status == "unvalidated"
    assert result[0].evidence_ids == ()


def test_conflicting_values_do_not_validate_claim():
    claim = make_claim()
    evidence = [
        make_evidence(evidence_id="EV001", value="blocked"),
        make_evidence(evidence_id="EV002", value="ready", source="Chat"),
    ]

    result = validate_claims_against_evidence(claims=[claim], evidence=evidence, account_id="ACC001")

    assert result[0].validation_status == "unvalidated"
    assert result[0].evidence_ids == ()


def test_unrelated_field_does_not_validate_claim():
    claim = make_claim()
    evidence = [make_evidence(field="renewal_date", value="blocked")]

    result = validate_claims_against_evidence(claims=[claim], evidence=evidence, account_id="ACC001")

    assert result[0].validation_status == "unvalidated"
    assert result[0].evidence_ids == ()

def test_unrelated_ownership_field_does_not_invalidate_claim():
    claim = make_claim(
        category="ownership",
        key="primary_contact",
        value="Nora Patel",
    )

    evidence = [
        make_evidence(
            evidence_id="EV010",
            field="primary_contact",
            value="Nora Patel",
            source="CRM",
        ),
        make_evidence(
            evidence_id="EV011",
            field="implementation_owner",
            value="Sam Rivera",
            source="Onboarding Project",
        ),
    ]

    result = validate_claims_against_evidence(
        claims=[claim],
        evidence=evidence,
        account_id="ACC001",
    )

    assert result[0].validation_status == "validated"
    assert result[0].evidence_ids == ("EV010",)