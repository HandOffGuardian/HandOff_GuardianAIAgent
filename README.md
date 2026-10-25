# HandOff Guardian AI

HandOff Guardian reviews a sales-to-support handoff through claim extraction,
evidence retrieval, policy evaluation, and reporting. A `CLEAR` result requires
the Evaluator's explicit clearance; malformed inputs, incomplete evidence,
conflicts, and component failures remain escalated.

## Architecture

The Streamlit entry point in `src/ui/app.py` calls the composition root in
`src/controller/application.py`, which wires the `Orchestrator` to the
ClaimExtractor, Evidence Agent, EvaluatorAdapter, and Reporter. Shared
contracts are under `src/contracts/`. Policy requirements and decision rules
are in `policy.yaml` and `src/evaluator/`.

The default Evidence Agent uses fictional repository fixtures. No production
Zetaris provider is implemented or configured here. The current ClaimExtractor
uses Nemotron through an OpenAI-compatible endpoint and returns unvalidated
claims without evidence IDs. There is no claim-validation component in this
repository yet, so the current real pipeline conservatively escalates instead
of approving unverified claims. Do not use fixture evidence for live customer
decisions.

## Requirements and setup

Use Python 3.10 or newer. From the repository root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Claim extraction requires these environment variables:

- `NVIDIA_API_KEY`
- `NVIDIA_BASE_URL`
- `NEMOTRON_MODEL`

Copy `.env.example` to `.env` and fill in values from the approved model
provider. Keep `.env` local; it is ignored by Git. Never put real credentials in
the example file or commit them. The Reporter uses a deterministic local
fallback in the Streamlit application. Its optional Meterless summarizer
supports `METERLESS_BASE_URL`, `METERLESS_API_KEY`, and `LLM_MODEL` when a caller
explicitly enables it.

## Run the application

From the repository root, after installing dependencies and configuring the
Nemotron variables:

```powershell
py -m streamlit run src/ui/app.py
```

The equivalent repository-root launcher is `py -m streamlit run app.py`.

Choose a fixture account, enter handoff notes, and start the review. The UI
shows the actual Orchestrator disposition, evaluator findings, risk score,
report, and sanitized execution diagnostics. Missing Nemotron configuration is
shown when a review is submitted; the app does not substitute a fabricated decision.

## Tests

Run the full offline suite with:

```powershell
py -m pytest -q -p no:cacheprovider --basetemp=.test-tmp
```

Tests inject deterministic model clients and fixture providers; they do not
require live model credentials or external evidence services. The repository
local basetemp keeps pytest working in restricted Windows environments.

## Repository map

- `src/controller/`: Orchestrator and application composition root
- `src/contracts/`: shared Claim, EvidenceRecord, and Finding models
- `src/extractor/`: claim extraction and Nemotron client
- `src/evidence/`: Evidence Agent and fixture provider
- `src/evaluator/`: policy adapter, rules, and deterministic Evaluator
- `src/reporter/`: report generation and citation verification
- `src/ui/`: Streamlit application
- `tests/`: unit and integration tests
- `docs/claim_extractor.md`: ClaimExtractor contract and configuration details

## Current limitations and troubleshooting

- The only Evidence provider is the local fictional fixture provider. Zetaris
  or other production data access must be implemented behind the Evidence
  Agent's provider interface; the Orchestrator should remain provider-agnostic.
- Extracted claims are unvalidated and have no evidence references. A trusted
  validation/linking step and agreed evidence categories/source-status
  contract are required before a real handoff can qualify for `CLEAR`.
- The Evaluator policy is explicitly provisional. Its required sources,
  categories, freshness windows, and decision thresholds need team approval.
- The reporter can produce a deterministic fallback without Meterless. The
  optional Meterless path is external and has not been verified against a live
  service.
- A provider error is distinct from a successful lookup with no matching
  records. The current fixture provider raises explicit errors for invalid
  fixture data and returns an empty list only when an account has no matches.
- The fixture Evidence Agent reports no per-source statuses because the
  fixture provider is a single local data source. The evaluator treats those
  statuses as unknown and escalates; records alone do not establish that
  Jira/CRM checks ran.
