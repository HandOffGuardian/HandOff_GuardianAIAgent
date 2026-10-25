# Architecture and integration boundaries

## Execution path

```text
Streamlit UI
  -> build_orchestrator()
  -> Orchestrator
      -> ClaimExtractor.extract(request=...)
      -> EvidenceAgent.collect(account_id, claims, metadata)
      -> EvaluatorAdapter.evaluate(claims, evidence_bundle, context)
      -> ReportGenerator.report(orchestration_result)
```

The composition root is `src/controller/application.py`. It selects the
ClaimExtractor backed by Nemotron, the configured evidence provider, the
EvaluatorAdapter, and a deterministic Reporter. `src/ui/app.py` displays the
Orchestrator's returned disposition and the Evaluator's findings; it does not
calculate a decision itself.

## Data and decision boundaries

- Claim extraction returns `{"claims": [...]}` using the shared Claim fields.
  Extracted claims are explicitly `unvalidated` and have no evidence IDs.
- Evidence collection returns `evidence`, explicit `source_statuses`,
  `missing_mandatory`, `conflicts`, and `mandatory_satisfied`. Evidence records preserve source, account, field,
  value, timestamp, excerpt, and evidence ID. The current shared evidence
  contract does not include a category or source status; the adapter maps
  source names, while category and provider status must come from the bundle.
  Missing required source statuses fail closed; record presence alone does not
  establish that a provider completed its check.
- The EvaluatorAdapter accepts the Orchestrator's `evidence_bundle` keyword,
  maps contract values to Evaluator models, and returns `EvaluationResult`, a
  mapping exposing decision, findings, mandatory status, conflicts, and risk.
- The Orchestrator only returns `CLEAR` when the Evaluator says `CLEAR`,
  mandatory evidence is satisfied, and no unresolved missing or conflict
  signals remain. Exceptions and malformed component outputs escalate.
- The Reporter receives a snapshot and emits a display report. The decision
  remains authoritative in the Orchestrator/Evaluator result. Citation IDs in
  findings are checked against the current `evidence` bundle.

## Current limits

The default provider reads fictional JSON fixtures. There is no Zetaris client
in this repository. A Zetaris integration belongs behind the Evidence Agent's
provider interface and should return records plus explicit per-source status;
the Orchestrator does not need Zetaris-specific logic.

There is no claim validation/linking agent. The ClaimExtractor correctly
refuses to establish truth or attach evidence IDs, so its output cannot satisfy
the Evaluator's claim-validation requirements and cannot clear a handoff. The
policy is marked provisional in `policy.yaml`; its categories, sources, and
freshness values require product/team approval before live use.

The fixture provider currently returns provenance records but does not report
per-source status or map fixture fields into policy categories. It is useful
for retrieval and report demonstrations, but its output cannot satisfy the
current mandatory evaluation policy by itself.
