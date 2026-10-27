# Handoff Guardian AI

Handoff Guardian reviews sales-to-support handoffs by extracting claims from handoff notes, collecting account evidence, validating claims against that evidence, checking a policy, and producing a report. It returns `CLEAR` only when the evaluator explicitly clears the handoff and mandatory evidence checks pass. Missing or conflicting evidence, malformed results, and component failures escalate.

## Current implementation and sponsor integration status

This repository contains a Streamlit application, an Orchestrator, a Nemotron-backed claim extractor, an evidence agent, a deterministic evaluator, and a report generator. The default application composition uses fictional local fixtures and disables the optional Meterless Nightshift report summarizer.

The repository does **not** currently demonstrate the hackathon's required sponsor integrations:

- **Zetaris:** no Zetaris client is configured or wired into `build_orchestrator()`. `src/evidence/providers/zetaris_provider.py` contains fixture-provider code, not a Zetaris connector.
- **Meterless Engine:** no H-MEM, Markovian, World Model, or Scout Intent engine implementation or conformance test is present.
- **Meterless Nightshift:** an optional OpenAI-compatible summarizer exists, but the default app disables it. Nightshift is not the app's primary AI provider.
- **NVIDIA:** the claim extractor can call a configured OpenAI-compatible Nemotron endpoint directly through `NVIDIA_*` environment settings. The app does not currently route that request through Nightshift.

See [submission readiness and sponsor technology](docs/submission-readiness.md) for the requirement-by-requirement evidence and limits. Do not describe the project as sponsor-compliant until working integrations and test evidence exist.

## Architecture

The Streamlit entry point in `src/ui/app.py` calls `build_orchestrator()` in `src/controller/application.py`. The composition root wires the ClaimExtractor, fixture-backed EvidenceAgent, EvaluatorAdapter, and ReportGenerator. The Orchestrator validates the returned component data, checks extracted claims against evidence, calls the policy evaluator, and preserves the evaluator's disposition in the report.

The evaluator uses the provisional rules in `policy.yaml`. The policy requires current source-status and evidence information; the fixture provider does not report per-source statuses, so the default UI path conservatively escalates. Fixture data is fictional and is only suitable for development or demonstration.

## Requirements and setup

Use Python 3.10 or newer. From a clean clone, run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

For live claim extraction, configure `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NEMOTRON_MODEL` in the local `.env` file using credentials and endpoints approved for your environment. Do not commit credentials. The repository's `.gitignore` excludes `.env` files.

Without model credentials, the default app can start, but a submitted investigation cannot complete claim extraction. The current default evidence data is fictional; it is not a production data connection.

## Run the application

```powershell
py -m streamlit run src/ui/app.py
```

Enter an account ID such as `ACC001` and handoff notes, then select **Investigate Handoff**. The result view displays the disposition, risk score, summary, evaluator findings, evidence provenance, diagnostics, and recommended actions. Since the default provider has no production evidence access or per-source status reporting, treat its result as a code-path demonstration and not a live customer decision.

## Example inputs

Use fictional accounts and notes only:

1. Account `ACC001`: “Production launch is blocked by identity mapping. Renewal is November 30.”
2. Account `ACC004`: “Nora Patel is the primary contact. Kickoff is scheduled next week.”
3. Account `ACC010`: “Retention is 90 days, according to the handoff.”

The fixture set includes contradictory records for several accounts. These examples are prompts for exercising extraction and evidence review, not guaranteed expected dispositions. The default provider omits required source statuses; therefore the current default path should be expected to escalate. A real model response can vary, so capture actual output and diagnostics during a demo rather than presenting invented outputs.

## Tests and evidence

The repository includes offline tests for the evaluator, claim validation, evidence provider, Orchestrator, reporting, UI, and application integration under `tests/`. They inject fixed model and evidence components where needed. This README does not claim a test run for the current checkout. Run the suite with:

```powershell
py -m pytest -q -p no:cacheprovider --basetemp=.test-tmp
```

The tests do not establish that Zetaris, Meterless Nightshift, a Meterless Engine, or a live Nemotron endpoint works. No live external service has been verified as part of this documentation.

## Repository map

- `src/controller/`: application composition root and Orchestrator
- `src/contracts/`: shared claim, evidence, and finding models
- `src/extractor/`: claim extraction and Nemotron API client
- `src/evidence/`: evidence agent and local fictional fixture provider
- `src/evaluator/`: policy adapter, evaluator, and risk scoring
- `src/reporter/`: summary generation, optional Nightshift client, and citation verification
- `src/ui/`: Streamlit application
- `tests/`: deterministic unit and integration coverage
- `docs/`: architecture, claim extraction, team workflow, submission readiness, and demo storyboard

## Current limitations

- The evidence provider is local fixture code. No Zetaris connection, schema mapping, credentials flow, or live query is implemented.
- Claim validation checks extracted claims against available evidence, but the default fixtures do not meet the configured mandatory source-status contract.
- `policy.yaml` is marked provisional. The required sources, categories, freshness limits, and decision thresholds need product approval.
- The optional Nightshift summary provider is not enabled by the default composition root. Its request path has not been verified against a live Nightshift service.
- There is no implemented Meterless Engine or engine conformance check.
- Nemotron is optional configuration for claim extraction and is not called through Nightshift by the current app.
- The default UI surfaces execution diagnostics, but does not provide an end-to-end audit log identifying the model for every request.

See [docs/architecture.md](docs/architecture.md) for component boundaries and [docs/claim_extractor.md](docs/claim_extractor.md) for the extraction contract.
