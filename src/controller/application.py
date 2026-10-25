"""Composition root for the implemented handoff workflow."""

from __future__ import annotations

from typing import Any

from src.evaluator.adapter import EvaluatorAdapter
from src.evidence.agent import EvidenceAgent
from src.evidence.providers.mock_provider import MockEvidenceProvider
from src.extractor.claim_extractor import ClaimExtractor
from src.reporter.report_generator import ReportGenerator

from .orchestrator import Orchestrator


def build_orchestrator(
    *,
    model_client: Any = None,
    evidence_provider: Any = None,
    evaluator: Any = None,
    reporter: Any = None,
) -> Orchestrator:
    """Build the application pipeline, allowing deterministic component injection.

    The default evidence source is the repository's explicitly fictional fixture
    provider. Production evidence integrations must be supplied by the caller.
    """
    return Orchestrator(
        claim_extractor=ClaimExtractor(model_client=model_client),
        evidence_agent=EvidenceAgent(evidence_provider or MockEvidenceProvider()),
        evaluator=evaluator or EvaluatorAdapter(),
        reporter=reporter or ReportGenerator(enable_llm=False),
    )
