"""Offline integration test across extraction, evidence, and evaluation."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from src.controller.orchestrator import Orchestrator
from src.evaluator.adapter import EvaluatorAdapter
from src.evaluator.evaluator import Evaluator
from src.evidence.agent import EvidenceAgent
from src.evidence.providers.mock_provider import MockEvidenceProvider
from src.extractor.claim_extractor import ClaimExtractor


class FixedClaimModel:
    def generate(self, *, system_prompt, user_prompt):
        return json.dumps({
            "claims": [
                {
                    "category": "engineering_status",
                    "key": "blocker_status",
                    "value": "blocked",
                }
            ]
        })


class CapturingEvidenceAgent(EvidenceAgent):
    def collect(self, account_id, claims=None, metadata=None):
        self.received_claims = claims
        return super().collect(account_id, claims, metadata)


class StubReporter:
    def report(self, result):
        return {"reported_disposition": result["disposition"]}


class EndToEndTests(unittest.TestCase):

    def test_extraction_reaches_real_evidence_and_evaluator_but_never_auto_clears(self):
        evidence = CapturingEvidenceAgent(MockEvidenceProvider())

        orchestrator = Orchestrator(
            ClaimExtractor(FixedClaimModel()),
            evidence,
            Evaluator(),
            StubReporter(),
        )

        result = orchestrator.run({
            "handoff_id": "H1",
            "account_id": "ACC001",
            "source_text": "Production is blocked.",
        })

        self.assertEqual(
            result["claims"][0]["validation_status"],
            "unvalidated",
        )
        self.assertEqual(result["claims"][0]["evidence_ids"], ())
        self.assertEqual(evidence.received_claims, result["claims"])
        self.assertEqual(len(result["evidence"]), 3)
        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(
            result["report"]["reported_disposition"],
            "ESCALATE",
        )

    def test_extraction_failure_escalates_before_evidence_or_evaluation(self):

        class BrokenModel:
            def generate(self, *, system_prompt, user_prompt):
                raise RuntimeError("sensitive provider detail")

        evidence = CapturingEvidenceAgent(MockEvidenceProvider())

        orchestrator = Orchestrator(
            ClaimExtractor(BrokenModel()),
            evidence,
            Evaluator(),
            StubReporter(),
        )

        result = orchestrator.run({
            "handoff_id": "H1",
            "account_id": "ACC001",
            "source_text": "Production is blocked.",
        })

        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(result["claims"], [])
        self.assertIsNone(result["evaluation"])
        self.assertNotIn("evidence_agent", result["attempts"])
        self.assertNotIn(
            "sensitive provider detail",
            str(result["diagnostics"]),
        )

    def test_fresh_consistent_evidence_can_clear_handoff(self):
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

        class ClearClaimModel:
            def generate(self, *, system_prompt, user_prompt):
                return json.dumps({
                    "claims": [
                        {
                            "category": "engineering_status",
                            "key": "blocker_status",
                            "value": "resolved",
                        },
                        {
                            "category": "ownership",
                            "key": "primary_contact",
                            "value": "Nora Patel",
                        },
                    ]
                })

        class FreshEvidenceAgent:
            def collect(self, account_id, claims=None, metadata=None):
                timestamp = datetime(
                    2026,
                    10,
                    25,
                    11,
                    0,
                    tzinfo=timezone.utc,
                ).isoformat()

                return {
                    "evidence": [
                        {
                            "evidence_id": "EV-CLEAR-001",
                            "source": "Engineering Ticket",
                            "account_id": account_id,
                            "field": "production_status",
                            "value": "resolved",
                            "updated_at": timestamp,
                            "excerpt": "Production blocker is resolved.",
                        },
                        {
                            "evidence_id": "EV-CLEAR-002",
                            "source": "CRM",
                            "account_id": account_id,
                            "field": "primary_contact",
                            "value": "Nora Patel",
                            "updated_at": timestamp,
                            "excerpt": "Primary contact: Nora Patel.",
                        },
                    ],
                    "source_statuses": [
                        {"source": "jira", "status": "available"},
                        {"source": "crm", "status": "available"},
                    ],
                    "missing_mandatory": [],
                    "conflicts": [],
                    "mandatory_satisfied": True,
                }

        orchestrator = Orchestrator(
            ClaimExtractor(ClearClaimModel()),
            FreshEvidenceAgent(),
            EvaluatorAdapter(clock=lambda: now),
            StubReporter(),
        )

        result = orchestrator.run({
            "handoff_id": "H-CLEAR-001",
            "account_id": "ACC-CLEAR-001",
            "source_text": (
                "The production blocker is resolved. "
                "Nora Patel is the primary contact."
            ),
        })

        self.assertEqual(result["disposition"], "CLEAR")
        self.assertTrue(result["evaluation"].mandatory_satisfied)


        self.assertTrue(
            all(
                claim["validation_status"] == "validated"
                for claim in result["claims"]
            )
        )

        self.assertEqual(
            result["claims"][0]["evidence_ids"],
            ("EV-CLEAR-001",),
        )
        self.assertEqual(
            result["claims"][1]["evidence_ids"],
            ("EV-CLEAR-002",),
        )
        self.assertEqual(
            result["report"]["reported_disposition"],
            "CLEAR",
        )


if __name__ == "__main__":
    unittest.main()