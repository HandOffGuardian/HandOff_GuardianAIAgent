# Handoff Guardian demo storyboard

## Recording goal

Show the current application working honestly in 2 to 3 minutes. This storyboard covers the workflow and product behavior. It does not claim to satisfy the hackathon's required live Zetaris, Nightshift, and Meterless Engine demonstration because those integrations are not wired into this checkout.

## Before recording

- Run from a clean clone after installing `requirements.txt`.
- Configure a permitted Nemotron endpoint only if available. Keep `.env`, provider screens, keys, and personal data off screen.
- Use a fictional handoff and a fictional account from the local fixture set, such as `ACC001`.
- Confirm that a model request and the actual app result are available to show. Do not invent or prewrite a result that differs from the run.
- If credentials are unavailable, show the documented configuration behavior and clearly label the walkthrough as a setup or UI walkthrough, not a successful live investigation.

## Shot list and narration

### 0:00 to 0:20 | Problem and user

Show the Handoff Guardian title and Investigate page.

Narration: “Sales-to-support handoffs can carry unsupported claims, stale evidence, or conflicting account details. Handoff Guardian gives onboarding and support teams a structured review before they act on a transfer.”

### 0:20 to 0:50 | Enter a fictional handoff

Enter account `ACC001` and a short synthetic note that matches claims in the fixture data. Keep all text fictional.

Narration: “I enter the account and handoff notes. The claim extractor returns candidate claims, and the evidence agent retrieves the repository's local demonstration records for this account.”

### 0:50 to 1:35 | Run and inspect the result

Select **Investigate Handoff**. Show the real result, including status, risk score, findings, evidence provenance, diagnostics, and recommendations. Expand the evidence section. Do not imply that these fixture records came from CRM, Jira, GitHub, or Zetaris.

Narration: “The evaluator applies the provisional policy. It checks required evidence, timestamps, claim support, source status, and conflicts. The application keeps the evaluator's disposition authoritative. Missing source status or unresolved conflicts lead to escalation.”

### 1:35 to 2:05 | Architecture and safety boundary

Show the architecture diagram from the slide deck or the README architecture section.

Narration: “The model proposes claims. Deterministic validation and policy code control the decision. The reporter explains the result but cannot override it. The included fixture provider is for demonstration only.”

### 2:05 to 2:35 | Sponsor status and next work

Show the submission readiness slide.

Narration: “The repository includes a Nemotron client path for claim extraction. This checkout does not query Zetaris, does not enable Nightshift as the primary provider, and does not implement a Meterless Engine. Those are required sponsor integrations and remain work to complete before claiming compliance.”

## Editing checklist

- Keep the finished video between one and four minutes.
- Show a real run and retain the actual output, including an escalation if that is what the code returns.
- Blur or omit secrets, personal information, local file paths, and browser autofill.
- Do not use the video to imply unimplemented sponsor features or claim test results that were not run.
- If the required sponsor paths are implemented later, record a new segment showing an actual Zetaris request, the selected Meterless Engine feature and conformance test, and an actual Nightshift request/response with the model identified.

## Current demo blocker

The default app uses fixture evidence and disables its optional Nightshift summarizer. It has no Meterless Engine implementation. Therefore this storyboard can demonstrate the app workflow but cannot satisfy the submission PDF's sponsor integration demo requirements with the current code.
