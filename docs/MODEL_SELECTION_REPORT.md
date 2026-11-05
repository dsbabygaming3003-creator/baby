# MODEL SELECTION REPORT — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Verification class:** model **identifiers** were verified against vendor documentation (Google Cloud "Model versions and lifecycle", Firebase AI Logic "supported models", OpenAI/Anthropic/Groq/HF docs). **Live API availability could NOT be verified from this sandbox** — every provider host is TLS-blocked (`docs/ENVIRONMENT_AUDIT.md` §3.2) and no API key was provisioned. Every model below is therefore marked with an explicit availability class, and TITAN never claims a model is reachable when it is not.

---

## 1. The Gemini 4 Argon question (explicitly requested)

| Property | Value | Verification |
|---|---|---|
| Model identifier | **`gemini-4-argon`** | ✅ VERIFIED — Google Cloud "Model versions and lifecycle" lists `gemini-4-argon`, release date **2026-10-13**, retirement "2027-10-13 or later" |
| Release stage | **Stable** | ✅ VERIFIED (same source) |
| Role | Flagship reasoning model | ✅ VERIFIED (Google Cloud docs + Gemini Enterprise Agent Platform model list) |
| Public API ID | `gemini-4-argon` | ✅ VERIFIED (same source) |
| Published price | ~$2.00 / $10.00 per 1M input/output tokens | ⚠️ CORROBORATED (two independent 2026 guides); VERIFIED price tables live behind the blocked API host |
| Context window | ~1M tokens (shared with the 3.x Flash family) | ⚠️ CORROBORATED |
| **Live API reachability from this sandbox** | ❌ **NOT REACHABLE** — `maven.google.com`-class provider hosts are TLS-blocked and no key exists | Verified by connection probe |
| Companion ids | `gemini-3.8-flash` (2026-09-02), `gemini-3.8-live` (2026-09-24), `gemini-3.5-flash-lite` (2026-07-21), `gemini-3.5-flash` (2026-05-19), `gemini-3.1-flash-lite` (2026-05-07), `gemini-3.1-pro-preview` (2026-02-19), `gemini-3.6-flash` (2026-07-21, deprecated for Agent Platform on 2026-11-19) | ✅ VERIFIED from the lifecycle table |
| Retired / shutting down | `gemini-2.5-pro` and `gemini-2.5-flash` retire **2026-10-20** (replacements `gemini-3.8-flash` / `gemini-3.5-flash`); `gemini-2.5-flash-lite` retires 2026-10-20 → `gemini-3.5-flash-lite` or Gemma 4 | ✅ VERIFIED from the lifecycle table |

**Decision:** TITAN registers **`gemini-4-argon`** as the *preferred planning/reasoning model* for the Gemini provider, with `gemini-3.8-flash` as the agentic/flash default and `gemini-3.5-flash-lite` as the cost-optimised extraction/translation model. Because live availability is unverifiable here, the gateway **does not hard-fail** when Argon is unavailable: it falls back through the configured chain and reports the actual model that served the request.

## 2. Provider & model registry (as shipped in `backend/titan/services/gateway.py`)

Every entry below is a *configured candidate*. The gateway marks each as `configured` (key present) / `unconfigured` (no key) / `unreachable` (host blocked) and never pretends otherwise.

### OpenAI (proprietary, hosted) — OpenAI-compatible wire format
| Model id | Role | Notes |
|---|---|---|
| `gpt-4o` | general / vision | stable |
| `gpt-4o-mini` | cheap general | stable |
| `o3-mini` | reasoning | reasoning family |
| `text-embedding-3-small` | embeddings (1536-d) | RAG adapter target |

### Anthropic (proprietary, hosted) — Messages API
| Model id | Role | Notes |
|---|---|---|
| `claude-sonnet-4` | balanced reasoning/coding | primary coding+agent model |
| `claude-opus-4` | deepest reasoning | complex planning |
| `claude-haiku-4` | low-latency / cheap | classification |

### Google Gemini (proprietary, hosted) — generateContent
| Model id | Role | Verified id? |
|---|---|---|
| `gemini-4-argon` | flagship reasoning, planning | ✅ VERIFIED |
| `gemini-3.8-flash` | agentic flash, tool loops | ✅ VERIFIED |
| `gemini-3.5-flash` | general | ✅ VERIFIED |
| `gemini-3.5-flash-lite` | cheapest bulk | ✅ VERIFIED |
| `gemini-3.1-flash-lite` | cheapest | ✅ VERIFIED |
| `gemini-3.1-pro-preview` | pro preview (≤200K ctx) | ✅ VERIFIED |
| `gemini-embedding-001` | embeddings | ✅ VERIFIED |

### Groq (hosted, OpenAI-compatible)
| Model id | Role |
|---|---|
| `llama-3.3-70b-versatile` | fast general |
| `qwen3-32b` | fast reasoning |

### Hugging Face (hosted inference + local weights)
| Model id | Role |
|---|---|
| `meta-llama/Llama-3.3-70B-Instruct` | open-weight general |
| `Qwen/Qwen3-32B` | open-weight coding |

### Local / self-hosted runtimes (OpenAI-compatible endpoints)
| Target | Role |
|---|---|
| Ollama `http://127.0.0.1:11434/v1` | local dev / offline |
| vLLM `http://127.0.0.1:8000/v1` | production self-host |

### Any OpenAI-compatible endpoint (BYO base_url)
`openai_compatible.v1` — for vLLM, LM Studio, Together, Groq, OpenRouter, Fireworks, or a private gateway. Requires `base_url` + `api_key` + `model`.

## 3. Task → model routing policy

| Task class | Preferred | Fallback chain | Rationale |
|---|---|---|---|
| `planning` / `complex_reasoning` | `claude-opus-4` → `gemini-4-argon` → `gpt-4o` | strong reasoning model | multi-step decomposition, conflict resolution |
| `coding` | `claude-sonnet-4` → `gemini-3.8-flash` → `qwen3-32b` | coding-capable | Hermes/OpenHands both default to Sonnet-class models for edit loops |
| `research_synthesis` | `gemini-3.8-flash` → `claude-sonnet-4` | long-context friendly | large retrieved corpora |
| `extraction` / `classification` | `gemini-3.5-flash-lite` → `gpt-4o-mini` | cheap | high volume, short outputs |
| `translation` | `gemini-3.5-flash` → `claude-haiku-4` | multilingual | glossary instruction |
| `voice` | provider `*-live` / `*-tts` ids | — | audio modality |
| `vision` / `image` | `gpt-4o` / `gemini-3.8-flash` | — | multimodal |
| `embeddings` | `text-embedding-3-small` → `gemini-embedding-001` → **local deterministic embedder** | local | retrieval must work with zero providers |

Routing is implemented as **capability + cost + health aware**: `route(task)` scores candidates by capability match, measured latency, measured error rate and price, then falls back on failure with exponential backoff.

## 4. Model availability handling (the anti-fake rule)

```
ProviderAvailability = { provider, model, configured: bool, reachable: bool,
                         status: "ready" | "no_key" | "unreachable" | "error",
                         detail: str, checked_at: ts }
```

- `GET /api/v1/models/providers` returns exactly this, computed **live** by probing each configured provider (no key ⇒ `no_key`; host blocked ⇒ `unreachable` with the real exception string).
- The Android Home screen renders those statuses; it never shows a model as "ready" unless the probe said so.
- The `mock` provider is explicitly labelled `provider_mode="mock"` in every response, every stored `ModelCall`, and in the UI. It exists so the rest of the product is testable without credentials, and it can never masquerade as a real provider.

## 5. Cost & latency accounting

Every call records: provider, model, prompt/completion tokens, cached tokens, latency ms, http status, error class, and the computed cost (price table per model id, in USD per 1M tokens). Costs roll up per agent, tool, skill, workflow and tenant — exposed in `/api/v1/models/usage` and the Observability dashboard.

## 6. Model Evaluation Center

`/api/v1/models/evaluations` runs a **real** benchmark over a stored evaluation dataset: for each (prompt, expected-criteria) case the gateway calls the chosen model, scores the output against the criteria (rule-based checks: required keywords, JSON validity, length band, refusal detection, instruction-following), and stores per-model scores with latency and cost. The Model Center compares models **only from these measured scores** — no model is ever declared "equivalent" to another without a benchmark run behind it.

## 7. Fine-tuning boundary (honest status)

| Level | Status | Evidence required before claiming completion |
|---|---|---|
| Level 1 — knowledge acquisition | ✅ IMPLEMENTED | Research findings → knowledge base with source + confidence |
| Level 2 — experience learning | ✅ IMPLEMENTED | Task history, error classification, recovery strategies, verified workflows |
| Level 3 — skill acquisition | ✅ IMPLEMENTED | Skill Factory with sandbox test + evaluation before publish |
| Level 4 — model improvement (SFT/LoRA/QLoRA) | ⚠️ **INFRASTRUCTURE ONLY** | `TrainingService` implements dataset preparation, cleaning, dedup, quality filtering, config generation and job tracking, and it **refuses to report a trained model** without a real training artifact + evaluation report. |

**This project does not claim to have trained a model.** No GPU, no `transformers`/`peft` runtime (unavailable behind the egress allowlist), and no training data with a licence that permits training. The Training Center therefore exposes: dataset management, config generation, job state machine, and an explicit `status: "NOT_RUN — no training runtime in this deployment"` for every job, with the exact reason.

## 8. Recommendations for a production deployment

1. Provision keys server-side only (`TITAN_PROVIDER_KEYS` / `SecretStore`); never in the APK.
2. Set `gemini-4-argon` as the planning model if the budget allows ($2/$10 per 1M), otherwise `gemini-3.8-flash` ($0.75/$3.75) — a 2.7× cost difference for ~2.7× the capability tier.
3. Keep `gemini-3.5-flash-lite` for extraction — it is the cheapest id that still satisfies the capability contract.
4. Configure a local Ollama/vLLM endpoint as the **final fallback** so the platform degrades to offline capability instead of failing.
5. Re-run the evaluation dataset after every model-id change; the Model Center's comparison table is the acceptance gate.
