"""Contract and claim extraction tests; all model access is faked."""

from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

from src.contracts.claim import Claim
from src.contracts.finding import Finding
from src.extractor.claim_extractor import ClaimExtractionError, ClaimExtractor
from src.extractor.llm_client import NemotronConfigurationError
from src.extractor.nemotron import NemotronClient


class FakeModelClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ClaimContractTests(unittest.TestCase):
    def test_defaults_immutability_and_valid_construction(self):
        claim = Claim("C1", "ownership", "owner_ready", "yes", "unvalidated")
        self.assertEqual(claim.evidence_ids, ())
        self.assertIsNone(claim.source)
        self.assertIsNone(claim.severity)
        with self.assertRaises(FrozenInstanceError):
            claim.value = "no"

    def test_required_fields_and_types_are_validated(self):
        for field, value in (
            ("claim_id", ""),
            ("category", " "),
            ("key", 4),
            ("value", None),
            ("validation_status", ""),
            ("evidence_ids", ["E1"]),
            ("evidence_ids", ("",)),
            ("evidence_ids", ("E1", "E1")),
            ("source", 7),
            ("severity", " "),
        ):
            with self.subTest(field=field, value=value):
                values = {
                    "claim_id": "C1", "category": "ownership", "key": "owner_ready",
                    "value": "yes", "validation_status": "unvalidated",
                }
                values[field] = value
                with self.assertRaises((TypeError, ValueError)):
                    Claim(**values)

        with self.assertRaises(TypeError):
            Claim("C1", "ownership", "owner_ready", "yes")


class FindingContractTests(unittest.TestCase):
    def test_defaults_independent_flags_and_immutability(self):
        finding = Finding("CODE", "RULE", "high", True, "Needs review")
        self.assertEqual(finding.evidence_ids, ())
        self.assertEqual(finding.subject, "")
        self.assertFalse(finding.retryable)
        with self.assertRaises(FrozenInstanceError):
            finding.blocking = False
        retryable_nonblocking = Finding(
            "CODE", "RULE", "info", False, "Can retry", retryable=True
        )
        self.assertFalse(retryable_nonblocking.blocking)
        self.assertTrue(retryable_nonblocking.retryable)

    def test_required_fields_flags_and_evidence_ids_are_validated(self):
        valid = {
            "reason_code": "CODE", "rule_id": "RULE", "severity": "high",
            "blocking": True, "description": "Needs review",
        }
        for field, value in (
            ("reason_code", ""),
            ("rule_id", None),
            ("severity", " "),
            ("blocking", 1),
            ("retryable", "yes"),
            ("evidence_ids", ["E1"]),
            ("evidence_ids", ("",)),
            ("subject", None),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises((TypeError, ValueError)):
                    Finding(**{**valid, field: value})

        with self.assertRaises(TypeError):
            Finding("CODE", "RULE", "high", True)


class ClaimExtractorTests(unittest.TestCase):
    def make_extractor(self, response):
        self.client = FakeModelClient(response)
        return ClaimExtractor(self.client)

    @staticmethod
    def request(source_text="Production is blocked. The owner is ready."):
        return {"handoff_id": "H1", "account_id": "A1", "source_text": source_text}

    def test_multiple_claims_are_deterministic_unvalidated_and_have_no_evidence_ids(self):
        response = json.dumps({"claims": [
            {"category": "engineering_status", "key": "blocker_status", "value": "blocked"},
            {"category": "ownership", "key": "owner_ready", "value": "ready"},
        ]})
        extractor = self.make_extractor(response)
        first = extractor.extract(request=self.request())
        second = extractor.extract(request=self.request())
        self.assertEqual(first, second)
        self.assertEqual([claim["claim_id"] for claim in first["claims"]], ["C001", "C002"])
        self.assertTrue(all(claim["validation_status"] == "unvalidated" for claim in first["claims"]))
        self.assertTrue(all(claim["evidence_ids"] == () for claim in first["claims"]))
        self.assertTrue(all(claim["source"] is None and claim["severity"] is None for claim in first["claims"]))
        self.assertEqual(len(self.client.calls), 2)
        self.assertIn("untrusted data", self.client.calls[0][1])

    def test_single_claim_and_empty_model_result(self):
        extractor = self.make_extractor({"claims": [
            {"category": "ownership", "key": "owner_ready", "value": "ready"}
        ]})
        result = extractor.extract(request=self.request("Owner is ready."))
        self.assertEqual(result["claims"][0]["claim_id"], "C001")

        no_claims = self.make_extractor('{"claims": []}')
        self.assertEqual(no_claims.extract(request=self.request("Just a greeting.")), {"claims": []})

    def test_bad_requests_fail_before_model_call(self):
        extractor = self.make_extractor('{"claims": []}')
        for request in (
            None,
            {},
            {"handoff_id": " ", "account_id": "A", "source_text": "text"},
            {"handoff_id": "H", "account_id": " ", "source_text": "text"},
            {"handoff_id": "H", "account_id": "A", "source_text": "  "},
            {"handoff_id": "H", "account_id": "A", "source_text": "text", "metadata": []},
            {"handoff_id": "H", "account_id": 1, "source_text": "text"},
        ):
            with self.subTest(request=request):
                with self.assertRaises(ClaimExtractionError):
                    extractor.extract(request=request)
        self.assertEqual(extractor._model_client.calls, [])

    def test_malformed_shapes_categories_values_and_duplicates_fail_closed(self):
        cases = [
            "not json",
            "[]",
            '{"claims": [], "other": true}',
            '{"claims": {}}',
            '{"claims": [{"category":"ownership","key":"x"}]}',
            '{"claims": [{"category":"ownership","key":"x","value":"ready","claim_id":"C1"}]}',
            '{"claims": [{"category":"unknown","key":"x","value":"ready"}]}',
            '{"claims": [{"category":"ownership","key":"x","value":"invented"}]}',
            '{"claims":[{"category":"ownership","key":"x","value":"ready"},{"category":"ownership","key":"x","value":"READY"}]}',
            '{"claims":[{"category":"ownership","category":"engineering_status","key":"x","value":"ready"}]}',
        ]
        cases.append(json.dumps({"claims": [
            {"category": "ownership", "key": "x", "value": "ready", "claim_id": "C1"},
            {"category": "ownership", "key": "y", "value": "blocked", "claim_id": "C1"},
        ]}))
        for response in cases:
            with self.subTest(response=response):
                extractor = self.make_extractor(response)
                with self.assertRaises(ClaimExtractionError):
                    extractor.extract(request=self.request())

    def test_model_failure_is_sanitized(self):
        extractor = self.make_extractor(RuntimeError("private source content and credentials"))
        with self.assertRaises(ClaimExtractionError) as caught:
            extractor.extract(request=self.request())
        self.assertNotIn("private source content", str(caught.exception))
        self.assertNotIn("credentials", str(caught.exception))

    def test_nemotron_configuration_and_completion_are_injectable_without_network(self):
        with self.assertRaises(NemotronConfigurationError):
            NemotronClient.from_environment(environ={})

        calls = []

        class FakeSDK:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs))
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

            def create(self, **kwargs):
                calls.append(("generate", kwargs))
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content='{"claims":[]}')
                )])

        client = NemotronClient.from_environment(
            environ={
                "NVIDIA_API_KEY": "fixture-key",
                "NVIDIA_BASE_URL": "https://fixture.invalid/v1",
                "NEMOTRON_MODEL": "fixture-model",
            },
            client_factory=FakeSDK,
        )
        self.assertEqual(client.generate(system_prompt="system", user_prompt="user"), '{"claims":[]}')
        self.assertEqual(calls[0][1]["timeout"], 30.0)
        self.assertEqual(calls[0][1]["max_retries"], 0)
        self.assertEqual(calls[1][1]["model"], "fixture-model")


if __name__ == "__main__":
    unittest.main()
