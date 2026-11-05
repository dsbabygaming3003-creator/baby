# OPEN SOURCE INVENTORY — TITAN OMEGA INFINITY V18

**Snapshot:** 2026-11-04 · **Method:** live `GET https://api.github.com/repos/<owner>/<repo>` and `GET .../releases` calls. `lic` column is the SPDX id returned by the GitHub API (`NOASSERTION` = non-standard/custom licence file, ⚠️ requires manual reading).

## A. Projects evaluated as references (no code copied)

| Repository | Owner | SPDX licence | Lang | Stars | Last push | Role in TITAN |
|---|---|---|---|---|---|---|
| `NousResearch/hermes-agent` | NousResearch | MIT | Python | 260,553 | 2026-11-04 | Primary architectural reference: transports, skills, delegation, permissions |
| `OpenHands/OpenHands` | OpenHands | MIT | TypeScript | 92,660 | 2026-11-04 | Sandbox-per-task autonomous runtime model |
| `OpenHands/software-agent-sdk` | OpenHands | MIT | — | 1,351 | 2026-11-04 | Embeddable agent loop |
| `OpenHands/extensions` | OpenHands | MIT | — | 176 | 2026-11-04 | Extension-registry pattern |
| `cline/cline` | cline | Apache-2.0 | TypeScript | 71,313 | 2026-11-04 | Plan→Act approval-loop reference |
| `continuedev/continue` | continuedev | Apache-2.0 | TypeScript | 36,404 | 2026-11-04 | Tool-permission UX reference |
| `SWE-agent/SWE-agent` | SWE-agent | MIT | Python | 20,724 | 2026-11-02 | Trajectory-as-data reference |
| `openai/codex` | openai | Apache-2.0 | Rust | 133,187 | 2026-11-04 | Terminal coding-agent reference |
| `google-gemini/gemini-cli` | google-gemini | Apache-2.0 | TypeScript | 108,728 | 2026-11-04 | Provider-agnostic agent harness reference |
| `Aider-AI/aider` | Aider-AI | Apache-2.0 | Python | 49,945 | 2026-05-22 | Git-native edit workflow reference |
| `langchain-ai/langchain` | LangChain | MIT | Python | 149,031 | 2026-11-04 | Tool/agent contract reference |
| `run-llama/llama_index` | LlamaIndex | MIT | Python | 52,807 | 2026-11-03 | RAG pipeline reference |
| `BerriAI/litellm` | BerriAI | ⚠️ NOASSERTION | Python | 62,715 | 2026-11-04 | Gateway API-shape reference only (not embedded) |
| `mem0ai/mem0` | Mem0 | Apache-2.0 | Python | 68,409 | 2026-11-04 | Scoped-memory pattern reference |
| `qdrant/qdrant` | Qdrant | Apache-2.0 | Rust | 35,427 | 2026-11-04 | Vector-store adapter target |
| `chroma-core/chroma` | Chroma | Apache-2.0 | Rust | 29,634 | 2026-10-30 | Vector-store adapter target |
| `ollama/ollama` | Ollama | MIT | Go | 185,933 | 2026-11-04 | Local runtime provider target |
| `vllm-project/vllm` | vLLM | Apache-2.0 | Python | 96,328 | 2026-11-04 | Self-hosted inference provider target |
| `ggml-org/whisper.cpp` | ggml-org | MIT | C++ | 54,929 | 2026-11-04 | ASR engine adapter target |
| `browser-use/browser-use` | browser-use | MIT | Python | 120,040 | 2026-11-02 | Browser-agent reference |
| `microsoft/playwright` | Microsoft | Apache-2.0 | TypeScript | 99,306 | 2026-11-04 | Browser automation adapter target |
| `modelcontextprotocol/servers` | MCP | ⚠️ NOASSERTION | TypeScript | 91,797 | 2026-11-04 | Tool-description standard |
| `fastapi/fastapi` | tiangolo | MIT | Python | 104,408 | 2026-11-04 | **Runtime dependency** |
| `pgvector/pgvector` | pgvector | ⚠️ NOASSERTION | C | 23,584 | 2026-11-03 | Production vector index option |
| `TabbyML/tabby` | TabbyML | ⚠️ NOASSERTION | Rust | 33,919 | 2026-06-30 | Self-hosted code-assist reference |
| `NousResearch/hermes-agent-self-evolution` | NousResearch | ⚠️ none reported | Python | 5,645 | 2026-06-17 | DSPy/GEPA self-improvement reference |
| `Sable/android-platforms` | Sable | (repo licence not queried) | — | — | 2026-06-22 | **Toolchain source** for `android.jar` (API 34/35) |

### Not resolvable from this environment (recorded, not relied upon)

| Repository | Lookup result | Consequence |
|---|---|---|
| `block/goose` | `404 NOT_FOUND` via API and absent from the search index | Recorded as **UNVERIFIED-FROM-ENVIRONMENT**; no TITAN code depends on it |
| `sst/opencode` | `404 NOT_FOUND` | Same |
| `All-Hands-AI/OpenHands` | moved → resolves as `OpenHands/OpenHands` | Path updated |

## B. Actual runtime dependencies of TITAN (installed & imported)

| Package | Version installed | Licence | Why |
|---|---|---|---|
| fastapi | 0.115.6 | MIT | ASGI framework, OpenAPI, validation |
| uvicorn[standard] | 0.34.0 | BSD-3-Clause | ASGI server |
| sqlalchemy[asyncio] | 2.0.36 | MIT | Async ORM + migrations |
| aiosqlite | 0.20.0 | MIT | SQLite async driver |
| pydantic | 2.10.4 | MIT | Schema validation |
| pydantic-settings | 2.7.0 | MIT | Config |
| httpx | 0.28.1 | BSD-3-Clause | Async HTTP client (connectors, providers) |
| httpcore / h11 / anyio / sniffio / certifi / idna | (transitive) | MIT / MIT / MIT / MIT / MPL-2.0 / BSD-3 | HTTP stack |
| websockets | 14.1 | BSD-3-Clause | WebSocket transport for live events |
| python-multipart | 0.0.20 | Apache-2.0 | Multipart uploads |
| numpy | 2.2.1 | BSD-3-Clause | Vector math for embeddings & cosine index |
| lingua-language-detector | 2.0.2 | Apache-2.0 | Language detection |
| pytest / pytest-asyncio | 8.3.4 / 0.25.0 | MIT | Test suite |
| starlette / typing-extensions / annotated-types / greenlet / charset-normalizer / idna / sniffio / click / h11 / anyio / httpx-http2 | (transitive) | MIT / PSF / MIT / MIT / MIT / BSD-3 / MIT / BSD-3 / MIT / MIT | — |

**Total third-party runtime dependency surface: 13 direct packages, all OSI-permissive.**

## C. Build toolchain dependencies (not shipped in the product)

| Tool | Version | Source | Licence of the distributed binary |
|---|---|---|---|
| JDK (Temurin) | 17.0.9 | PyPI `jdk4py==17.0.9.2` wheel | GPL-2.0 with Classpath Exception (Temurin) — used only as a build/runtime tool, not redistributed in the product |
| Kotlin compiler | 2.4.21 | npm `kotlin-compiler` | Apache-2.0 |
| aapt2 | 2.20-15009934 | npm `aaptjs3` (bundles Google's aapt2) | Apache-2.0 (Android SDK) |
| d8 / R8 | (bundled 16.8 MB `d8.jar`) | npm `d8-termux` | Apache-2.0 (R8) |
| android.jar API 34/35 | — | GitHub `Sable/android-platforms` | AOSP Apache-2.0 |
| APK signer | 1.0.1 | npm `apk_sign_ts` | see `docs/LICENSE_AUDIT.md` §4 |

## D. Licence risk assessment

- **No copyleft dependency is linked into the product.** No GPL/AGPL/LGPL code is imported at runtime.
- `certifi` is MPL-2.0 — file-level copyleft, used unmodified as a data bundle; compatible with MIT/Apache distribution.
- The **JDK** is GPL-2.0+CE but is used as an external tool (like a compiler), not redistributed or linked into the APK.
- `BerriAI/litellm` (NOASSERTION) and `pgvector` (NOASSERTION) are **not** vendored; they are referenced as deployment targets only.
- No source file from any third-party project was copied into this repository. The only pre-existing file (`instagram_2fa_automation.js`) is the repository owner's own upload, unrelated to TITAN, and is left byte-for-byte unmodified.

## E. Attribution file

`THIRD_PARTY_NOTICES.md` enumerates every direct dependency with its licence and version, generated from the live install (`pip freeze`) — see that file for the machine-generated list.
