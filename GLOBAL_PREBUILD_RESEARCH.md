# TITAN OMEGA INFINITY V18 — Global Pre-Build Research

**Research phase:** Builder AI / System A
**Date:** 2026-11-04
**Evidence snapshot:** `docs/research/evidence/`
**Status:** first-increment research gate passed with explicitly documented coverage limits; this is not a claim of exhaustive global research.

## Method

The repository and environment were audited first. Forty-six official GitHub projects were then inspected through authenticated GitHub REST APIs. Owner, license metadata, activity and latest release were recorded. Ambiguous license files and Hermes/Claude Code source roots were retrieved separately. Thirteen Python package candidates were checked through PyPI. Official Android, Gemini, Temporal, LiteLLM, pgvector and OWASP documentation supplemented repository evidence.

No private source, access-control bypass or fabricated social/research result was used. Detailed access limitations are in `RESEARCH_SOURCE_COVERAGE.md`.

## Mandatory topic findings and decisions

| # | Topic | Verified candidates / finding | First-increment decision |
|---|---|---|---|
| 1 | Strong agent platforms | Hermes, OpenHands, LangGraph, AutoGen, CrewAI, OpenAI Agents | Narrow native contracts; compare before embedding |
| 2 | Open-source coding agents | Aider (Apache), OpenHands (MIT), Continue/Goose (Apache) | Architecture references; no unverified reuse |
| 3 | Hermes Agent | Official NousResearch repo, MIT, Python 3.11–3.14, tools/skills/gateway/state | Reference only; see dedicated analysis |
| 4 | Claude Code alternatives | Aider, OpenHands, Continue, Goose | Claude Code treated as proprietary; alternatives not benchmarked |
| 5 | Multi-agent orchestration | LangGraph, AutoGen, CrewAI, OpenAI Agents, Temporal for durability | Typed local DAG/parallel executor; Temporal production option |
| 6 | Agent factories | Hermes skills, CrewAI role model, MCP ecosystems | Versioned registry + schema/tests/approval |
| 7 | Autonomous coding/debugging | OpenHands, Aider, Goose, Continue | File/tool pipeline + tests and evidence; bounded repair |
| 8 | Browser automation | Playwright (Apache), browser-use (MIT), Selenium (Apache) | Playwright candidate; not installed/claimed live |
| 9 | Authorized computer use | Gemini docs and agent tool ecosystems | Approval-bound remote execution only; no hidden device control |
| 10 | Memory/RAG | mem0, LlamaIndex, Haystack, pgvector, Qdrant | Source-backed local lexical baseline; pgvector production path |
| 11 | Model gateways | LiteLLM core MIT outside enterprise | Native adapters first; LiteLLM future deployment option |
| 12 | Local runtimes | Ollama, llama.cpp, vLLM | OpenAI-compatible/self-host adapter; hardware checks required |
| 13 | Research automation | Hermes, OpenHands, LlamaIndex/Haystack, connector pattern | Permanent connector/task/source/finding pipeline in TITAN |
| 14 | Open-source AI GUIs | Open WebUI, Dify, Flowise | Independent UI; custom/archived projects not adopted |
| 15 | Android AI development | Kotlin, Compose, Now in Android, Retrofit, OkHttp | Native modular Kotlin/Compose client |
| 16 | Voice/speech | Whisper/faster-whisper ASR; Piper GPL TTS | Separate voice service; Bengali quality unverified |
| 17 | Translation | Argos MIT, LibreTranslate AGPL, multilingual hosted models | Model route + explicit local-service boundary; language tests |
| 18 | Skills/plugins | Hermes skills, MCP SDK/servers | Manifest, scopes, tests, sandbox and approval |
| 19 | Workflow engines | Temporal MIT, Prefect Apache, n8n source-available | Durable local checkpoints; Temporal production candidate |
| 20 | Evaluation/fine-tuning | LM Eval Harness, Promptfoo, Opik, Langfuse; PEFT/Axolotl | Evaluation records first; training blocked until GPU/jobs/artifacts |
| 21 | Premium AI UI/UX | Compose/Material 3 and modular sample evidence | Graphite/cyan operations UI with honest system state |
| 22 | Cloud Linux/build | Temporal/worker patterns; Android SDK requirements | Isolated worker architecture; current APK build blocked |

## Technology selection summary

- **Backend:** Python 3.11+, FastAPI, Pydantic, SQLAlchemy, HTTPX and Uvicorn. SQLite is explicitly a local development profile; PostgreSQL/pgvector is the production target.
- **Intelligence:** provider-neutral gateway, explicit mock for deterministic tests, real OpenAI-compatible adapter, no silent inference claims.
- **Orchestration:** persisted tasks/runs and dependency-aware parallel execution in the core; production Temporal migration remains an ADR option.
- **Research:** versioned connector interface with per-source outcomes and partial-result persistence. GitHub public API is the first real connector.
- **Android:** native Kotlin, Compose, coroutines/Flow, MVVM and Retrofit/OkHttp source; build is blocked until JDK/SDK are installed.
- **Security:** policy enforcement at tool and repository boundaries, untrusted source content, default-deny scopes and exact-action approval.
- **Verification:** automated API/unit/integration tests plus recorded logs; unavailable device/model/infrastructure tests stay blocked.

## Research-to-architecture consequences

1. A single monolithic “supreme agent” is insufficient: control-plane orchestration, untrusted research, execution and presentation require separate trust boundaries.
2. The Builder's reports and TITAN's runtime Research Engine are independent deliverables and test suites.
3. Durability must be designed into task IDs/checkpoints now even though the local worker is not equivalent to Temporal.
4. A vector database is not a prerequisite for a truthful source-backed retrieval baseline; lexical retrieval is labeled honestly and pgvector can replace its index.
5. Model identifiers and provider availability are runtime configuration backed by health checks, never hardcoded marketing claims.
6. Native APK claims require an actual toolchain, artifact hash, install and launch evidence.

## Gate record

- Environment audit: **COMPLETE**.
- Official ecosystem sample and evidence capture: **COMPLETE**.
- License candidate audit: **COMPLETE for candidates; release audit pending**.
- Hermes identity/runtime/source inspection: **COMPLETE**.
- Model identifier documentation: **VERIFIED; live availability UNVERIFIED**.
- UI/architecture/security decision inputs: **COMPLETE**.
- Social, multi-forge, arXiv and full advisory coverage: **OPEN**, recorded rather than invented.

The architecture in `ARCHITECTURE_DECISION_RECORD.md` is therefore frozen **only for the first implementable increment**, not represented as completion of all V18 research or delivery phases.
