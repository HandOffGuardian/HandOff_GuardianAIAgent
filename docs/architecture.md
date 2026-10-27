# Architecture and integration boundaries

## Execution path

```text
Streamlit UI
  -> build_orchestrator()
      -> ClaimExtractor.extract(request)
      -> EvidenceAgent.collect(account_id, claims, metadata)
      -> Orchestrator validates claim/evidence links
      -> EvaluatorAdapter.evaluate(claims, evidence_bundle, context)
      -> ReportGenerator.report(orchestration_result)
```

The composition root is `src/controller/application.py`. It selects the ClaimExtractor backed by Nemotron, the EvidenceAgent with the local fixture provider, the EvaluatorAdapter, and a ReportGenerator with its optional language model disabled. The UI displays the Orchestrator's disposition and the evaluator's findings. It does not calculate a decision itself.

## Data and decision boundaries

- Claim extraction returns `{"claims": [...]}` with the fields defined by the shared Claim model. Extracted claims begin as `unvalidated` and carry no evidence IDs.
- The Orchestrator adapts extracted claims and collected evidence, then matches account, field/category, and value to link supported claims. Conflicting or unrelated records do not validate a claim.
- Evidence collection returns `evidence`, `source_statuses`, `missing_mandatory`, `conflicts`, and `mandatory_satisfied`. Evidence records preserve source, account, field, value, timestamp, excerpt, and evidence ID. The fixture provider returns no per-source statuses, so the evaluator treats status as unknown.
- The EvaluatorAdapter maps shared contracts to the deterministic Evaluator. `policy.yaml` supplies provisional mandatory-source, category, freshness, conflict, and scoring rules.
- The Orchestrator only returns `CLEAR` when the Evaluator says `CLEAR`, mandatory evidence is satisfied, evidence is present, and no unresolved missing or conflict signals remain. Exceptions and malformed component outputs escalate.
- The Reporter receives an isolated result snapshot and emits a display report. The decision remains authoritative in the Orchestrator/Evaluator result. Citation IDs in findings are checked against the current evidence bundle.

## Data provider status

The default provider reads fictional JSON fixtures. No Zetaris client is configured or invoked. Although `src/evidence/providers/zetaris_provider.py` has a sponsor-related filename, its contents implement fixture loading. It is not a Zetaris integration. A real provider should sit behind the Evidence Agent's provider interface, return provenance records and explicit per-source status, and distinguish a successful empty result from a provider failure.

## Model provider status

`ClaimExtractor` uses `NemotronClient` when a model client is not injected. The client reads `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NEMOTRON_MODEL` and sends an OpenAI-compatible chat-completions request. The optional `NightshiftLLMProvider` can summarize a report through a configurable OpenAI-compatible endpoint, but `build_orchestrator()` disables it. The current application therefore does not use Nightshift as its primary AI provider, and no Meterless Engine is present.

## Current limits

The fixture provider reports no per-source statuses and does not satisfy the configured mandatory evidence requirements by itself. The evaluator policy is explicitly provisional; product owners must approve categories, sources, freshness windows, and thresholds before live use. The repository contains deterministic tests using injected components, but this document does not claim a live Zetaris, Nightshift, Meterless Engine, or NVIDIA endpoint verification.
