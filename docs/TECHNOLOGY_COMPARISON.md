# TECHNOLOGY COMPARISON — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Verification:** live `api.github.com` + `pypi.org/pypi/<pkg>/json` probes (licence SPDX + release tags), plus vendor documentation reads.

---

## 1. Backend framework

| Option | Licence | Verdict |
|---|---|---|
| **FastAPI 0.115.6** | MIT | ✅ **CHOSEN** — async-native, automatic OpenAPI, Pydantic v2 validation, 104,408★, the de-facto reference used by LangChain/LlamaIndex/OpenHands ecosystems |
| Flask | BSD-3 | ✗ sync request model, no native streaming |
| Django + DRF | BSD-3 | ✗ heavy ORM/admin weight for an API-first product |
| Litestar | MIT | ✗ smaller ecosystem for agent/streaming patterns |
| Sanic | Apache-2.0 | ✗ smaller ecosystem |

**Decision:** FastAPI. Streaming is served via **SSE** (universally supported by the Android client through `HttpURLConnection`) **and** WebSocket (for agent/task events), implemented with `starlette` primitives.

## 2. Async ORM & database

| Option | Licence | Verdict |
|---|---|---|
| **SQLAlchemy 2.0 async + aiosqlite** | MIT | ✅ **CHOSEN** — one model layer, two database profiles |
| PostgreSQL 16 + pgvector | PostgreSQL licence / pgvector NOASSERTION | ⛔ **unavailable here** (no Docker/apt); retained as the production profile |
| MongoDB | SSPL | ✗ SSPL not OSI-approved — rejected for a self-hostable product |
| Qdrant | Apache-2.0 | ⛔ unavailable (no binary distribution reachable); **vector adapter boundary** implemented |
| Chroma | Apache-2.0 | ⛔ same |
| Redis | RSALv2/SSPL (newer) | ⛔ unavailable; **not required** — the workflow engine is DB-backed and survives restarts without it |

**Decision:** SQLAlchemy 2.0 async with a **`DATABASE_URL` profile switch** (`sqlite+aiosqlite://` default, `postgresql+asyncpg://` production). Vector search = **NumPy cosine index persisted in SQLite** with a pluggable `VectorStore` interface so Qdrant/pgvector can replace it without touching call sites.

## 3. Android UI toolkit

| Option | Verdict |
|---|---|
| **Jetpack Compose + AndroidX** | ⛔ **IMPOSSIBLE HERE** — `androidx.compose.*` AARs live on `maven.google.com`/`repo1.maven.org`, both TLS-blocked. Not "inconvenient": the runtime artifacts cannot be fetched. |
| **Android framework Views + custom Canvas** | ✅ **CHOSEN for this build** — `android.jar` (API 34/35) obtained from `codeload.github.com`; `kotlinc` 2.4.21 compiles Kotlin against it; `d8` dexes it; `aapt2` packages it. |
| Flutter / React Native | ✗ requires the same blocked artifact hosts (engine binaries + pub/npm proxies) |

**Decision:** Kotlin + framework views for the shippable APK in this environment. **Additionally** the repository ships a complete Gradle/Compose project definition (`android/app/build.gradle.kts`, `android/gradle/libs.versions.toml`) so that the identical feature set can be built with Compose on any host with normal Maven access. Both paths are documented in `docs/ANDROID_ARCHITECTURE.md`; the APK actually produced here is the framework-views one and its provenance is recorded in `docs/BUILD_REPORT.md`.

## 4. Model gateway

| Option | Licence | Verdict |
|---|---|---|
| **Native gateway (TITAN-owned)** | MIT (own code) | ✅ **CHOSEN** — needed for agent-aware routing, per-task evaluation scores, health-based fallback, token/cost attribution per agent/tool/skill, and OpenAI-compatible surface |
| LiteLLM | NOASSERTION on GitHub metadata | ⚠️ strong alternative; would add a heavy Rust-core dependency; TITAN mirrors its OpenAI-compatible API shape so it can be fronted later |
| OpenRouter (managed) | hosted | ✗ adds 5.5% credit fee, no self-hosting |
| Portkey | hosted + OSS gateway | ✗ hosted-first |
| Cloudflare AI Gateway | hosted | ✗ hosted-first |

## 5. Agent / orchestration substrate

| Option | Verdict |
|---|---|
| **Native orchestrator (Supreme Boss)** | ✅ **CHOSEN** — the product needs process-level delegation, per-agent locks, checkpoints and conflict resolution that are not LangChain primitives |
| LangChain / LangGraph | ⚠️ MIT and excellent — its `Tool`/`Agent` abstractions informed TITAN's contracts, but TITAN's agent registry is a *product* feature (registry, versions, permissions, metrics) rather than a library concept |
| LlamaIndex | ✗ data-centric; TITAN's RAG is narrower and self-contained |
| OpenHands runtime | ✗ Docker-dependent, and it is a product, not a library to embed |

## 6. RAG / retrieval

| Option | Verdict |
|---|---|
| **Native hybrid retrieval** (BM25 + dense cosine → RRF fusion → rerank) | ✅ **CHOSEN** — BM25 implemented in-repo over SQLite FTS-style postings; dense vectors via a deterministic local embedding function (hashed n-gram, 384-dim, L2-normalised) so retrieval works with **zero external services**, with an adapter for provider embeddings (OpenAI/Gemini/Cohere) when keys exist |
| LlamaIndex / LangChain vectorstores | ✗ require an embedding provider + vector DB to be useful |
| mem0 | ⚠️ Apache-2.0, excellent memory layer — its *pattern* (typed memory scopes) is adopted; its runtime is not embedded because TITAN's memory model is tenant-scoped and versioned |

## 7. Voice (ASR / TTS)

| Option | Verdict |
|---|---|
| **On-device Android `SpeechRecognizer` + `TextToSpeech`** | ✅ **CHOSEN for the client** — real microphone capture via `AudioRecord`, real amplitude-driven waveform, real TTS playback; Bengali availability is a **runtime capability probe**, reported honestly |
| whisper.cpp (MIT) | ⛔ model weights not downloadable here (huggingface.co blocked); adapter implemented for server-side ASR where weights exist |
| Piper TTS | ⛔ same; adapter implemented |
| Cloud ASR/TTS (OpenAI-compatible, ElevenLabs) | ⚠️ adapters implemented — no provider host is allowlisted and no key is provisioned, so the product reports `provider_mode: unavailable` rather than faking it |

## 8. Translation

| Option | Verdict |
|---|---|
| **Gateway-mediated LLM translation + glossary** | ✅ **CHOSEN** — preserves technical terms, handles 30+ target languages, no extra service |
| Google/DeepL APIs | ✗ hosts blocked; adapters implemented for deployment |
| `lingua-language-detector` (Apache-2.0) | ✅ **CHOSEN** for language detection — installed and verified importable |

## 9. Workflow engine

| Option | Verdict |
|---|---|
| **Native DAG engine** with checkpoint/resume | ✅ **CHOSEN** — state in TITAN's own DB, resumable after restart, human-approval gates |
| Temporal | ✗ heavyweight external service, unavailable |
| Prefect / Airflow | ✗ batch-first, heavy |
| LangGraph | ⚠️ MIT, close in spirit; TITAN implements checkpoint semantics natively to avoid an extra service |

## 10. Build & execution

| Option | Verdict |
|---|---|
| **aapt2 + kotlinc + d8 + apksigner-equivalent** | ✅ **CHOSEN** — all four verified working |
| Gradle + AGP | ⛔ distribution and plugins unreachable; Gradle project files still shipped for portability |
| Docker sandboxes | ⛔ docker binary absent; process-isolation sandbox with rlimits + jailed cwd + command allowlist implemented instead, with a Docker backend selectable when available |

## 11. Security posture

| Control | Implementation |
|---|---|
| Secrets | server-side only; provider keys read from env/`SecretStore`; **no key is ever written into the APK** (automated test scans the built APK's DEX + resources for key patterns) |
| Auth | JWT (HS256, own implementation), scrypt password hashing, API keys stored as SHA-256 digests, RBAC roles |
| Injection defence | every retrieved external document is tagged `untrusted` and wrapped in a delimited "REFERENCE DATA" block; system-prompt markers are stripped from retrieved text; a scanner flags injection patterns |
| SSRF | all outbound requests pass an egress allowlist + DNS/IP checks (no link-local, private, or metadata ranges) |
| Sandbox | per-project jailed working root, `ulimit` caps (CPU/memory/file size/process count), command allowlist, wall-clock timeout, output truncation |

## 12. Cost of the chosen stack

All chosen components are permissively licensed (MIT / BSD-3 / Apache-2.0) with the single exception of none — see `docs/LICENSE_AUDIT.md`. Self-hosting cost is a single 2-vCPU/4-GB Linux box plus provider tokens; no paid control-plane service is required for any TITAN feature to function.
