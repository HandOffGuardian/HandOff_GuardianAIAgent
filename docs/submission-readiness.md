# Submission readiness and sponsor technology

## Scope

This note maps the Open Agent Hackathon 2026 submission requirements to the repository at commit `0d53e8de2e07f62db710ff1f115dea7625ff5ebd` on `development`. It records what the checked-in code demonstrates and what remains unimplemented. It is not a claim that the submission meets the sponsor requirements.

## Sponsor requirement assessment

| Requirement | Evidence in this repository | Status |
|---|---|---|
| Zetaris as the data layer | `build_orchestrator()` defaults to `MockEvidenceProvider`. `src/evidence/providers/zetaris_provider.py` is fixture loading code and contains no Zetaris client. | Not implemented |
| At least one working Meterless Engine | No H-MEM, Markovian, World Model, or Scout Intent implementation or test/conformance check was found. | Not implemented |
| Meterless Nightshift as primary AI provider | `NightshiftLLMProvider` posts to an OpenAI-compatible chat-completions URL, but `build_orchestrator()` constructs `ReportGenerator(enable_llm=False)`. Claim extraction uses `NemotronClient` with `NVIDIA_*` configuration. | Optional code exists; not wired into default app, not primary |
| NVIDIA contribution | `NemotronClient` accepts configured model, API key, and base URL. The extractor invokes it when no model client is injected. | Integration path exists; live use and model handling were not verified |
| Demo video showing live workflow and sponsor integrations | A real run would require model setup; live Zetaris and Nightshift/Engine integration are absent. | Cannot honestly demonstrate the rubric's required sponsor flow with this checkout |
| Public repository, clean setup, dependencies | README covers setup, launch, dependencies, and test command. Repository visibility is controlled by GitHub settings and was not checked here. | README guidance present; public access unverified |
| Sample inputs and outputs | README supplies three sample inputs. It avoids promising deterministic model output. | Inputs documented; capture actual outputs before submission |
| Logs showing model per request | UI shows sanitized component diagnostics, but not a model trace per request. | Not implemented |
| `.env.example` with placeholders | `.env.example` contains blank values for NVIDIA settings. `.gitignore` excludes local `.env` files. | Present; review completeness before submission |

## What the implemented pipeline does

The Streamlit UI accepts a handoff ID, account ID, and handoff notes. `build_orchestrator()` connects the claim extractor, fixture evidence agent, evaluator adapter, and report generator. The Orchestrator checks component outputs, links claims to supporting evidence where the values and account match, and only returns `CLEAR` when the evaluator clears the case and the mandatory evidence conditions are satisfied. Errors, unknown statuses, and unresolved conflicts remain escalated. The deterministic evaluator reads the provisional `policy.yaml` rules.

These are repository capabilities. The default fixture path does not establish live evidence access or production readiness. The evidence agent reports no source statuses for the fixture provider, while the evaluator requires them for mandatory sources.

## Sponsor technology details

### Zetaris

The application does not currently query Zetaris. The evidence provider seam is the appropriate future integration point, but a seam is not an integration. A working implementation would need to authenticate with the approved Zetaris environment, query the required account sources, map source rows into the evidence contract, report per-source availability/error status, preserve provenance, and include a test against an approved environment or reliable conformance fixture.

### Meterless Engine and Nightshift

No required Meterless Engine is implemented. The existing `NightshiftLLMProvider` sends a summarization request to a configurable OpenAI-compatible endpoint with Meterless headers. The default application disables this provider, and the reporter uses a deterministic local fallback. There is no engine selection, working feature powered by a Meterless Engine, engine test, or proof that the app's primary AI request goes through Nightshift.

Do not present the optional summarizer as a Meterless Engine implementation. A compliant implementation would need to identify the selected engine, connect it to a user-visible feature, show the app's primary AI path through Nightshift, and record a passing conformance test and a real request/response trace.

### NVIDIA

The claim extractor can use `NemotronClient` with an OpenAI-compatible NVIDIA endpoint selected through `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NEMOTRON_MODEL`. The model returns structured claims, which the extractor checks against the handoff source text. This path is separate from the optional Nightshift reporter client. The project does not currently prove a Nemotron model request went through Nightshift, so it should not claim that it meets the NVIDIA award setup requirement.

### What is unique today

The clearest implemented design choice is the conservative decision boundary: an LLM extracts candidate claims, while deterministic code validates claims, checks required evidence, applies policy, and controls clearance. The report layer cannot change the authoritative disposition. This is a product and architecture distinction, not a unique sponsor integration.

## Evidence to collect before making stronger claims

- A successful Zetaris query using a least-privilege test account, with redacted request metadata and returned provenance.
- A selected Meterless Engine attached to a working product feature and a repeatable passing conformance test.
- A primary AI request routed through Meterless Nightshift, with a trace showing the selected Nemotron model and a redacted result.
- A clean-clone setup run, the offline test output, and an application demo recording that avoids credentials and customer data.
- Confirmation that the GitHub repository is public and that the selected track and pre-existing components are declared in HackOS.

Until that evidence exists, describe the sponsor integrations as gaps or future work. Do not submit a fabricated test result, trace, service call, output, team roster, track, or declaration.

## Source files inspected

- `src/controller/application.py`
- `src/controller/orchestrator.py`
- `src/evidence/agent.py`
- `src/evidence/providers/zetaris_provider.py`
- `src/evidence/providers/mock_provider.py`
- `src/reporter/report_generator.py`
- `src/reporter/llm_provider.py`
- `src/extractor/nemotron.py`
- `src/ui/app.py`
- `tests/test_application_integration.py`
- `policy.yaml`
