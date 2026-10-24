# Claim Extractor

`ClaimExtractor.extract(request=...)` accepts a mapping with non-empty string
fields `handoff_id`, `account_id`, and `source_text`; optional `metadata` must
be a mapping. It returns `{"claims": [...]}`. The active evaluator policy
supplies the allowed claim categories.

The model returns strict JSON with a `claims` list. Every entry contains only
`category`, `key`, and `value`. Values must occur verbatim in the source text;
the extractor assigns deterministic IDs (`C001`, `C002`, ...), sets
`validation_status` to `unvalidated`, and leaves `evidence_ids` empty. A lack
of identifiable assertions returns an empty claims list. No deterministic
fallback pretends to provide semantic extraction.

Model access is injected through the `ModelClient.generate` protocol for
offline tests. Without injection, the extractor uses `NemotronClient`, which
requires `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NEMOTRON_MODEL`. These names
and the OpenAI-compatible chat-completions interface follow the existing
`test_nemotron.py` smoke script. The `openai` package is declared in
`requirements.txt`; requests use a 30-second timeout and disable SDK retries.
No live Nemotron request was made to verify the configured endpoint or model.

Invalid requests, malformed model output, unsupported policy categories, and
model errors raise `ClaimExtractionError`; missing Nemotron configuration or
the SDK raises `NemotronConfigurationError` during client construction.
Messages exclude source content, model responses, and credentials. The
Orchestrator treats extraction exceptions as component failures and escalates.
Extraction never validates evidence or authorizes a handoff.
