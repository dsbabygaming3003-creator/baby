# Model and Provider Registry

| Provider/route | Model | Runtime state | Evidence/boundary |
|---|---|---|---|
| `mock` | `deterministic-mock-v1` | Available only outside production | Explicit mock text and `is_mock=true`; zero cost |
| `openai-compatible` | `TITAN_OPENAI_COMPATIBLE_MODEL` | Available when base URL/key/model are configured | Real HTTP and SSE contract; test transport validates schema/usage, not live account access |
| Gemini | `gemini-4-argon` documented | Unavailable in this increment | Official model documentation verified; dedicated adapter, credential and live health check missing |
| Local/self-hosted | Operator supplied | Unverified | May use OpenAI-compatible adapter after endpoint/capability checks |
| ASR/TTS | None configured | Blocked | Text models are not represented as speech engines |

Task type is persisted on every model call. Current server selection chooses configured OpenAI-compatible otherwise development mock; explicit unsupported providers fail rather than silently fallback. More sophisticated task/cost/quality routing requires benchmark data.

Secrets are read only from server environment. Provider availability in the registry means configured, not health-certified; a successful inference is separately recorded.
