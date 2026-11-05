# Model Selection Report

**Research date:** 2026-11-04
**Runtime credential state:** no hosted AI provider credential was available.

## Verified model finding

Google's official model documentation identifies **Gemini 4 Argon** with model ID **`gemini-4-argon`**, a unified 1,048,576-token input/output window, text output and multimodal input/tool capabilities. Official release material describes it as generally available. Sources:

- https://ai.google.dev/gemini-api/docs/models/gemini-4-argon
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/changelog

This verifies the documented identifier, **not** access from this workspace or the user's account. No API request was made because no Gemini/Google key is configured and the shell network allowlist does not include the Gemini endpoint.

## Selection policy

| Task | Required class | Routing decision |
|---|---|---|
| Complex planning/coding | Strong reasoning + tool use | Configured reasoning/coding route; Gemini 4 Argon is a candidate after authenticated health check |
| Research synthesis | Long context + structured output | Configured research route with citation/schema validation |
| Translation | Multilingual model | Configured translation route; evaluate Bengali and low-resource language quality |
| Vision/OCR | Vision-capable model | Separate capability requirement; never route text-only models |
| Voice ASR/TTS | Speech-specific model/runtime | Separate voice providers; do not emulate with text model calls |
| Local/self-hosted | OpenAI-compatible or explicit local adapter | Configured base URL plus health/capability probe |
| Tests/development | Deterministic mock | Explicit `mock` provider; responses always labeled mock |

## Gateway requirements

- Provider/model allowlists and task-based aliases rather than model names in Android code.
- Server-side secrets only; Android stores its own short-lived application credential, never provider keys.
- Health, latency, token/cost usage, timeout, bounded retry and fallback records.
- No silent fallback to a mock or a different paid model.
- Structured output schema validation and correlation IDs.
- Model versions and observed capability probes persisted with each evaluation.

## Initial decision

Implement a small native provider interface with an explicit mock and an OpenAI-compatible HTTP adapter. Keep Gemini-specific configuration possible without claiming that all providers share one API. Defer a full LiteLLM deployment until PostgreSQL, secrets and operations infrastructure exist; LiteLLM remains a documented future gateway option.

## Evaluation gate

No model is declared “best,” equivalent to another, Bengali-capable, or production-available without real benchmark results. Required first live evaluation set: Bengali chat, Bengali↔English translation, JSON validity, tool-call correctness, code repair, citation faithfulness, latency, token usage and cost.

**Status:** `DOCUMENTATION COMPLETE; LIVE MODEL SELECTION BLOCKED BY CREDENTIALS/NETWORK.`
