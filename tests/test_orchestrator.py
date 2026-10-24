import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.controller.orchestrator import Orchestrator


def make_components():
    claim = Mock()
    claim.extract.return_value = {"claims": [{"claim_id": "C1", "field": "amount", "claimed_value": "10"}]}
    evidence = Mock()
    evidence.collect.return_value = {
        "evidence": [{
            "evidence_id": "E1", "source_id": "ledger-7",
            "timestamp": "2026-10-23T10:00:00Z",
            "provenance": {"provider": "fixture", "record": 4},
        }],
        "missing_mandatory": [], "conflicts": [],
    }
    evaluator = Mock()
    evaluator.evaluate.return_value = {
        "decision": "CLEAR", "mandatory_satisfied": True,
        "findings": [], "missing_mandatory": [], "conflicts": [],
    }
    reporter = Mock()
    reporter.report.return_value = {"report_id": "R1"}
    return SimpleNamespace(claim=claim, evidence=evidence, evaluator=evaluator, reporter=reporter)


def make_orchestrator(components, max_retries=2):
    return Orchestrator(components.claim, components.evidence, components.evaluator, components.reporter, max_retries)


def sample_request():
    return {"handoff_id": "H1", "account_id": "A1", "source_text": "Payment was 10."}


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.components = make_components()

    def run_orchestrator(self):
        return make_orchestrator(self.components).run(sample_request())

    def test_successful_flow_passes_data_and_preserves_provenance(self):
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "CLEAR")
        self.assertIs(result["evidence"], self.components.evidence.collect.return_value["evidence"])
        self.assertEqual(result["evidence"][0]["provenance"], {"provider": "fixture", "record": 4})
        self.components.claim.extract.assert_called_once_with(request=sample_request())
        self.components.evaluator.evaluate.assert_called_once()
        self.components.reporter.report.assert_called_once()
        self.assertIsNot(self.components.reporter.report.call_args.args[0], result)
        self.assertEqual(result["report_status"], "success")

    def test_missing_empty_or_conflicting_evidence_never_clears(self):
        cases = [
            ({"evidence": []}, {}),
            ({"missing_mandatory": ["payment"]}, {}),
            ({"mandatory_satisfied": False}, {}),
            ({"conflicts": [{"field": "amount"}]}, {}),
            ({}, {"decision": "ESCALATE"}),
            ({}, {"mandatory_satisfied": False}),
        ]
        for evidence_updates, evaluation_updates in cases:
            with self.subTest(evidence=evidence_updates, evaluation=evaluation_updates):
                components = make_components()
                components.evidence.collect.return_value.update(evidence_updates)
                components.evaluator.evaluate.return_value.update(evaluation_updates)
                result = make_orchestrator(components).run(sample_request())
                self.assertEqual(result["disposition"], "ESCALATE")

    def test_retries_only_explicit_transient_safe_failures(self):
        error = RuntimeError("temporary")
        error.transient = True
        error.safe_to_retry = True
        self.components.claim.extract.side_effect = [error, self.components.claim.extract.return_value]
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "CLEAR")
        self.assertEqual(result["attempts"]["claim_extractor"], 2)
        self.assertEqual(self.components.claim.extract.call_count, 2)

    def test_retry_limit_is_bounded_and_failure_escalates(self):
        error = RuntimeError("temporary")
        error.transient = True
        error.safe_to_retry = True
        self.components.claim.extract.side_effect = error
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(self.components.claim.extract.call_count, 3)
        self.assertEqual(result["attempts"]["claim_extractor"], 3)
        self.assertEqual(result["diagnostics"][0]["error"], "retry_exhausted")

    def test_nonretryable_failure_escalates_without_retry(self):
        self.components.evidence.collect.side_effect = RuntimeError("failed")
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(self.components.evidence.collect.call_count, 1)
        self.assertTrue(self.components.reporter.report.called)

    def test_malformed_outputs_escalate(self):
        for component, output in (("claim", {"unexpected": []}), ("evidence", []), ("evaluator", [])):
            with self.subTest(component=component):
                components = make_components()
                if component == "claim":
                    components.claim.extract.return_value = output
                elif component == "evidence":
                    components.evidence.collect.return_value = output
                else:
                    components.evaluator.evaluate.return_value = output
                result = make_orchestrator(components).run(sample_request())
                self.assertEqual(result["disposition"], "ESCALATE")
                self.assertTrue(any(item["error"] == "malformed_component_output" for item in result["diagnostics"]))

    def test_empty_and_mixed_malformed_claim_records_never_reach_evaluator(self):
        cases = [
            [{}],
            [{"claim_id": "C1"}, {}],
        ]
        for claims in cases:
            with self.subTest(claims=claims):
                components = make_components()
                components.claim.extract.return_value = {"claims": claims}
                result = make_orchestrator(components).run(sample_request())
                self.assertEqual(result["disposition"], "ESCALATE")
                components.evaluator.evaluate.assert_not_called()

    def test_empty_and_mixed_malformed_evidence_records_never_reach_evaluator(self):
        valid_record = {"evidence_id": "E2", "provenance": {"source": "fixture"}}
        cases = [
            [{}],
            [valid_record, {}],
        ]
        for evidence_records in cases:
            with self.subTest(evidence=evidence_records):
                components = make_components()
                components.evidence.collect.return_value = {
                    "evidence": evidence_records,
                    "missing_mandatory": [],
                    "conflicts": [],
                }
                result = make_orchestrator(components).run(sample_request())
                self.assertEqual(result["disposition"], "ESCALATE")
                components.evaluator.evaluate.assert_not_called()

    def test_reporter_failure_is_recorded_and_does_not_clear_escalation(self):
        self.components.evaluator.evaluate.return_value["decision"] = "ESCALATE"
        self.components.reporter.report.side_effect = RuntimeError("report failed")
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(result["report_status"], "failed")
        self.assertEqual(result["diagnostics"][-1]["error"], "reporting_failure")

    def test_reporter_failure_does_not_suppress_valid_evaluator_clear(self):
        self.components.reporter.report.side_effect = RuntimeError("report failed")
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "CLEAR")
        self.assertEqual(result["report_status"], "failed")

    def test_reporter_mutations_cannot_change_escalated_result(self):
        self.components.evaluator.evaluate.return_value["decision"] = "ESCALATE"

        def mutate_report_input(payload):
            payload["disposition"] = "CLEAR"
            payload["evidence"][0]["evidence_id"] = "altered"
            payload["evaluation"]["decision"] = "CLEAR"
            return {"report_id": "R1"}

        self.components.reporter.report.side_effect = mutate_report_input
        result = self.run_orchestrator()

        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(result["evidence"][0]["evidence_id"], "E1")
        self.assertEqual(result["evaluation"]["decision"], "ESCALATE")
        self.assertEqual(result["report_status"], "success")

    def test_reporter_mutation_then_exception_cannot_change_authoritative_data(self):
        self.components.evaluator.evaluate.return_value["decision"] = "ESCALATE"

        def mutate_then_raise(payload):
            payload["disposition"] = "CLEAR"
            payload["evidence"][0]["provenance"]["record"] = "altered"
            payload["evaluation"]["decision"] = "CLEAR"
            raise RuntimeError("report failed")

        self.components.reporter.report.side_effect = mutate_then_raise
        result = self.run_orchestrator()

        self.assertEqual(result["disposition"], "ESCALATE")
        self.assertEqual(result["evidence"][0]["provenance"]["record"], 4)
        self.assertEqual(result["evaluation"]["decision"], "ESCALATE")
        self.assertEqual(result["report_status"], "failed")
        self.assertEqual(result["diagnostics"][-1]["error"], "reporting_failure")

    def test_malformed_report_output_is_recorded(self):
        self.components.reporter.report.return_value = []
        result = self.run_orchestrator()
        self.assertEqual(result["disposition"], "CLEAR")
        self.assertEqual(result["report_status"], "failed")
        self.assertEqual(result["diagnostics"][-1]["error"], "malformed_report_output")


if __name__ == "__main__":
    unittest.main()
