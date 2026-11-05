# UNIFIED MODEL GATEWAY

One entry point for every model call, whatever the provider.

---

## 1. Providers (8)

| Provider | Key variable | Transport | State |
|---|---|---|---|
| `openai` | `OPENAI_API_KEY` | HTTPS `/v1/chat/completions` | no key → `no_key` |
| `anthropic` | `ANTHROPIC_API_KEY` | HTTPS `/v1/messages` | no key → `no_key` |
| `gemini` | `GEMINI_API_KEY` | HTTPS `generativelanguage` | no key → `no_key` |
| `groq` | `GROQ_API_KEY` | HTTPS OpenAI-compatible | no key → `no_key` |
| `huggingface` | `HUGGINGFACE_API_KEY` | HTTPS router | no key → `no_key` |
| `openai_compatible` | `OPENAI_COMPATIBLE_API_KEY` + base URL | HTTPS OpenAI-compatible | no key → `no_key` |
| `local` | — | HTTP to a self-hosted server | not provisioned |
| `mock` | — | in-process deterministic provider | **active fallback only** |

`GET /models/providers` reports each provider's live status. **None of them reports
`ready`** in this deployment, because no credential exists (AT-10). This is the honest
outcome the anti-fake contract requires.

---

## 2. Model registry (20 models, 18 with verified identifiers)

| Model | Provider | Context | Verified identifier |
|---|---|---|---|
| `gpt-4o` | openai | 128 000 | yes |
| `gpt-4o-mini` | openai | 128 000 | yes |
| `o3-mini` | openai | 200 000 | yes |
| `text-embedding-3-small` | openai | 8 191 | yes |
| `claude-opus-4` | anthropic | 200 000 | yes |
| `claude-sonnet-4` | anthropic | 200 000 | yes |
| `claude-haiku-4` | anthropic | 200 000 | yes |
| `gemini-4-argon` | gemini | 1 048 576 | yes |
| `gemini-3.8-flash` | gemini | 1 048 576 | yes |
| `gemini-3.5-flash` | gemini | 1 048 576 | yes |
| `gemini-3.5-flash-lite` | gemini | 1 048 576 | yes |
| `gemini-3.1-flash-lite` | gemini | 1 048 576 | yes |
| `gemini-3.1-pro-preview` | gemini | 200 000 | yes |
| `gemini-embedding-001` | gemini | 2 048 | yes |
| `llama-3.3-70b-versatile` | groq | 131 072 | yes |
| `qwen3-32b` | groq | 131 072 | yes |
| `meta-llama/Llama-3.3-70B-Instruct` | huggingface | 131 072 | yes |
| `Qwen/Qwen3-32B` | huggingface | 131 072 | yes |
| `qwen3:8b` | local | 32 768 | no (self-hosted tag) |
| `Qwen/Qwen3-32B` | openai_compatible | 131 072 | no (deployment-specific) |

> `gemini-4-argon` was verified as a **real, stable identifier** published on 2026-10-13
> (see `docs/MODEL_SELECTION_REPORT.md`). Its live API reachability from this host was
> **not** verified — no key exists — so the registry marks the identifier verified and the
> provider status `no_key`. Those are two different claims and the platform keeps them
> apart.

---

## 3. Routing, fallback and health

`services/gateway.py`:

1. `route(task, requested_model, provider_id)` selects candidates from the registry:
   an exact model match first, then any model whose `capabilities` contain the task
   (`chat`, `coding`, `reasoning`, `translation`, `extraction`, `embeddings`, `planning`,
   `long_context`, `tools`, `vision`).
2. Candidates are tried in order. A provider without a key is skipped and the reason is
   recorded.
3. Each provider call is retried up to `gateway_max_retries` (2) with exponential backoff
   when the error is marked retryable.
4. Provider health (`ok` / `degraded` / `error` / `no_key`) is tracked per provider and
   surfaced by `/models/providers`.
5. If **no** real provider can serve the request, the gateway falls back to the mock
   provider and marks the result `provider_mode = "mock"`, with the reason embedded in the
   text: *"No real LLM provider was reachable for this request. Reason: openai:
   OPENAI_API_KEY is not configured. This is a deterministic placeholder … and must not be
   treated as an answer."*

Every response that touched the mock path carries `provider_mode` — the chat route, the
translation route and the evaluation route all surface it (AT-18, AT-31, AT-33).

---

## 4. Accounting

Per call the gateway records: `tokens_in`, `tokens_out`, `latency_ms`, `cost_usd`,
`http_status`, `provider_id`, `model`, `attempts` and `error`.

Cost is computed from the registry's `input_cost_per_mtok` / `output_cost_per_mtok`.
The totals are stored on `messages`, `agent_runs` and `model_evaluations`.

---

## 5. Structured-output validation

The evaluation service validates structured output against per-case criteria
(`json` + required keys, `min_length`, `contains`, `not_empty`) and scores the result.
The gateway itself returns raw text plus metadata; scoring is the caller's job, so the
contract stays explicit.

---

## 6. Secrets

Credentials are read from the server environment only. They are never written to the
database, never returned by an endpoint and never present in the APK
(verified — `docs/BUILD_REPORT.md` §5).

---

## 7. Adding a provider

1. add a `ProviderSpec` to `PROVIDERS` (id, base URL, env key, transport style);
2. add a call branch in `Gateway._call_provider` if the wire format differs;
3. register its models in `MODELS`;
4. set the environment variable — the provider then reports `ready` and joins the routing
   order automatically.
