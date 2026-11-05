# ARCHITECTURE DECISION RECORD — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Status:** Architecture **FROZEN** (pre-build research gate satisfied — see `docs/GLOBAL_PREBUILD_RESEARCH.md` §12)

Format: `ADR-NNN · Title · Decision · Status · Context · Consequences · Alternatives rejected · Verification`

---

### ADR-001 · Two independent research systems
**Decision.** The builder's pre-build research (`docs/`) and TITAN's runtime research engine (`backend/titan/research/`) are **separate deliverables** with separate storage, separate connectors and separate history. The builder's reports are *not* loaded into the product's knowledge base, and the product's engine never reads the builder's session or browser history.
**Context.** The specification (§01) forbids one satisfying the other. A product that ships the builder's documents as its "research" would be a document viewer, not an engine.
**Consequences.** Two code paths, two connector implementations — accepted. The product's engine is proven by live connector calls and by its own `research_tasks` history in the database.
**Rejected.** Seeding the product's knowledge base with the builder's reports (would make acceptance tests circular).

### ADR-002 · Backend: Python 3.11 + FastAPI + SQLAlchemy 2.0 async
**Decision.** FastAPI 0.115.6 (MIT), SQLAlchemy 2.0.36 async, Pydantic v2.
**Context.** Every reference platform (LangChain, LlamaIndex, OpenHands) is Python; FastAPI gives async + SSE + WebSocket + OpenAPI in one stack.
**Consequences.** One language for agents, connectors, gateway, workflow engine, tests.
**Rejected.** Node/NestJS (would fragment the agent code), Go (fewer agent libraries), Ktor (same).

### ADR-003 · SQLite + NumPy by default; PostgreSQL/pgvector/Qdrant behind one interface
**Decision.** `DATABASE_URL` selects the profile. Default `sqlite+aiosqlite` with a NumPy cosine index persisted in the DB.
**Context.** PostgreSQL, Redis, Qdrant and Docker are **unavailable** in this environment (no apt, no Docker, no reachable binaries) — `docs/ENVIRONMENT_AUDIT.md` §5.
**Consequences.** Zero-infrastructure operation works today; production deployments switch by env var with no code change. The vector layer is an interface (`VectorStore`), not a hard dependency.
**Rejected.** Requiring PostgreSQL (would make the product unrunnable here); SQLite-only forever (no path to scale).

### ADR-004 · Native Model Gateway instead of embedding LiteLLM
**Decision.** TITAN implements its own OpenAI-compatible gateway with routing, fallback, health, token/cost/latency accounting and evaluation hooks.
**Context.** The gateway must attribute cost per *agent/tool/skill*, drive agent selection, and feed the Model Evaluation Center — all product concepts LiteLLM does not know. LiteLLM's GitHub licence is `NOASSERTION` (P4 of the licence audit ⇒ not vendored).
**Consequences.** ~500 lines we own; full control over product-specific routing. The API shape mirrors LiteLLM's so it can be fronted later.
**Rejected.** LiteLLM (licence + integration depth), OpenRouter/Portkey (hosted, adds markup, no self-host).

### ADR-005 · Native DAG Workflow Engine with DB-backed checkpoints
**Decision.** Own implementation: nodes, edges, dependency resolution, parallel fan-out, retries, timeouts, checkpoint after each step, resume, cancellation, human-approval gates, schedules.
**Context.** Temporal/Prefect are unavailable and heavy; LangGraph is close but adds a service and a second persistence model. The spec requires the app to be able to close and the workflow to continue — which needs server-side state anyway.
**Consequences.** Workflow state lives in TITAN's own DB and survives restart. A `resume` endpoint continues from the last checkpoint.
**Rejected.** Temporal (service dependency), Celery (broker dependency), Airflow (batch-first).

### ADR-006 · Research connectors as isolated, versioned modules
**Decision.** One module per source, each declaring `VERSION`, an access policy, a query adapter, a normaliser, a dedup key and a verification rule. A connector failure **never** fails the task; the outcome is `INACCESSIBLE` / `ERROR` / `UNAUTHORIZED` and the task continues with partial results.
**Context.** The runtime host can reach only GitHub/PyPI/npm. A task that treated an unreachable source as a task failure would be useless here; the spec explicitly requires partial results and an honest "source could not be accessed" state.
**Consequences.** Users always see per-source status. The Research Center shows live reachability probes.
**Rejected.** A single monolithic fetch layer (loses per-source policy); an external scraping service (unavailable, and would raise legal questions).

### ADR-007 · Hybrid retrieval implemented in-repo (BM25 + dense, RRF fusion)
**Decision.** SQLite full-text postings for BM25; deterministic local hashing embedder (384-d, L2-normalised) so retrieval works with **zero external services**; provider embeddings used when configured; RRF fusion; rerank; source attribution.
**Context.** No embedding provider or vector DB is reachable. A RAG feature that requires a paid key is not testable, and a fake embedding is a fake RAG.
**Consequences.** Retrieval is real and measurable offline (the test suite asserts that a known document is retrieved for a known query); provider embeddings slot in without changing call sites.
**Rejected.** Requiring an embedding API; using a random-hash "embedding" with no lexical component (poor recall — BM25 fixes that).

### ADR-008 · Android client: Kotlin + framework views (this build), Gradle/Compose project also shipped
**Decision.** The shipped APK is Kotlin, rendered with the Android framework view system, built with `aapt2 + kotlinc + d8 + apk_sign_ts`. The repository *also* contains a complete Gradle + Compose project definition for hosts with normal Maven access.
**Context.** `androidx.compose.*` and the Gradle distribution are behind TLS-blocked hosts (`docs/ENVIRONMENT_AUDIT.md` §3.2) — Compose is not "slow to build", it is **unobtainable**. The Kotlin compiler, aapt2, d8 and `android.jar` were all reconstructed from allowlisted sources and each was executed successfully.
**Consequences.** A **real, installable APK** is produced and verified here. The Compose path is present but *not* claimed to be built in this environment.
**Rejected.** Claiming a Compose build that was never compiled (violates §28); shipping no Android client at all (violates §29).

### ADR-009 · No provider secret ever reaches the client
**Decision.** The Android app authenticates to TITAN; TITAN performs every provider call server-side. Provider keys live in `SecretStore` (env / encrypted DB / 0600 file) and are never returned by an API.
**Context.** §08 and §21 make this mandatory; §26 test 31 makes it an acceptance criterion.
**Consequences.** The APK contains no provider credential; a scan of the built APK's DEX/resources for key-shaped strings is part of the release gate.
**Rejected.** BYOK in the client (key extractable from the APK).

### ADR-010 · External content is untrusted data, never instruction
**Decision.** Retrieved documents are wrapped in a delimited `UNTRUSTED REFERENCE DATA` block, stripped of system markers, scored by an injection scanner, and inserted only under an explicit "content cannot change the task" clause.
**Context.** The researched ecosystem shows out-of-scope action rates of 5.4%–27.7% in permissive agent frameworks.
**Consequences.** Retrieval cannot escalate privileges; the Research Center surfaces the injection risk score per document.
**Rejected.** Inserting raw HTML/web text into the system prompt.

### ADR-011 · Process-isolation sandbox now, container sandbox behind one interface
**Decision.** `SandboxBackend` interface with a `ProcessBackend` (rlimits, jailed cwd, env scrubbing, command allowlist, wall-clock kill, output truncation) and a `DockerBackend` for deployments that have Docker.
**Context.** Docker is unavailable here; pretending to sandbox with a `subprocess` call and no limits would be theatre.
**Consequences.** Real limits are applied today and asserted by tests; production can harden without changing call sites.
**Rejected.** Unsandboxed subprocess execution.

### ADR-012 · Single-writer-per-project execution model with agent locks
**Decision.** A project has one active write lock; agents take scoped locks; conflicting concurrent writes are serialised and reported.
**Context.** The spec requires parallel execution *and* conflict resolution; naive parallelism corrupts files.
**Consequences.** Parallel agents still run for read/research tasks; write conflicts are detected and queued.

### ADR-013 · Honest capability reporting is a first-class API
**Decision.** `GET /api/v1/system/capabilities` returns, per capability, a status from `{available, degraded, blocked, unavailable}` plus the reason string — computed live.
**Context.** §28 forbids faking; the environment has real gaps (no Compose, no device, no provider keys, blocked egress).
**Consequences.** The Android UI shows the truth; the acceptance report is generated from the same endpoint.
**Rejected.** A static "everything works" banner.

### ADR-014 · Observability with correlation ids and structured logs
**Decision.** Every request, agent run, tool call, model call, workflow step and research task carries a `correlation_id`; logs are structured JSON with secret redaction; `/metrics` exposes Prometheus-format counters.
**Context.** §24 mandates monitoring across ~15 dimensions and forbids leaking sensitive data into logs.
**Consequences.** A single `X-Correlation-ID` header threads through the whole stack; the Android client displays it in the Security Center so a user can quote it in a bug report.

### ADR-015 · Voice: on-device Android ASR/TTS with honest Bengali verification
**Decision.** The client captures real audio with `AudioRecord` (amplitude drives the waveform), uses Android `SpeechRecognizer` for ASR and `TextToSpeech` for synthesis, and **probes** language availability at runtime instead of assuming it. The server exposes adapters for Whisper-compatible/Piper/cloud providers.
**Context.** §10 requires Bengali verification before claiming support. We cannot verify a specific Bengali voice quality without a device and the language pack; therefore the product reports `bn availability: available|unavailable` from `TextToSpeech.isLanguageAvailable()` and never claims a quality level it did not measure.
**Consequences.** The capability is honest; on a device with the Bengali pack the feature works on-device with no server round trip.
**Rejected.** Simulated waveform (a fake), or claiming Bengali support without a probe.

### ADR-016 · Tests are acceptance-gated, not decoration
**Decision.** A pytest suite plus a `verification/run_acceptance.py` script that executes all 38 acceptance tests from §26 and writes `docs/TEST_REPORT.md` with real pass/fail and captured evidence. The Android build script runs the APK-secret scan and the dex sanity check.
**Context.** §26/§28 make test evidence a delivery artefact.
**Consequences.** The report is generated, not written by hand; failing tests fail the release.

### ADR-017 · Versioned, documented public API
**Decision.** `/api/v1/**` with OpenAPI generated by FastAPI, documented in `docs/API_DOCUMENTATION.md`, and a `X-Titan-Version` header. Breaking changes require a version bump.
**Context.** The Android client and any future integration depend on a stable contract.
**Consequences.** Clients can be written against the schema; the doc is generated from the running app, not hand-maintained.

### ADR-018 · Repository hygiene
**Decision.** The pre-existing `instagram_2fa_automation.js` is preserved unmodified and excluded from every artefact; large toolchain binaries live outside the repository (`/opt/titan/toolchain`); the bootstrap script is committed so the toolchain is reproducible.
**Context.** The owner asked for a project; deleting their file was not requested; committing ~1 GB of binaries would bloat the repository.
**Consequences.** Repository stays small and reviewable; a clean checkout can rebuild the toolchain with one script.

---

## Module map (frozen)

```
backend/titan/
├── main.py                 ASGI app, router mounting, lifespan (DB init + scheduler)
├── config.py               Settings (pydantic-settings), profiles
├── db.py                   Async engine/session, Base, migrations runner
├── models.py               34 entities (users…audit_logs) per docs/DATABASE_SCHEMA.md
├── security/               jwt, passwords, rbac, secrets, ssrf, injection, ratelimit, audit
├── services/
│   ├── gateway.py          Model Gateway: providers, routing, fallback, cost, health
│   ├── agents.py           Worker Bossman: 20 agents, locks, parallel, validation
│   ├── factory.py          Dynamic Agent Factory: spec→agent→sandbox test→register
│   ├── tools.py            Tool registry + executor + permission enforcement
│   ├── skills.py           Skill Factory, registry, laboratory, marketplace
│   ├── memory.py           8 memory scopes, versioning, retention
│   ├── rag.py              chunk→embed→index→hybrid retrieve→rerank→attribution
│   ├── research.py         research engine: task orchestration, findings, reports
│   ├── workflow.py         DAG engine: checkpoints, resume, approval, schedules
│   ├── voice.py            ASR/TTS adapters, transcripts, capability probe
│   ├── translation.py      detect + translate + glossary + history
│   ├── build.py            build service: real command execution, artifacts
│   ├── sandbox.py          SandboxBackend (process | docker)
│   ├── evaluation.py       model evaluation + training dataset/job management
│   └── observability.py    metrics, correlation ids, structured logs
├── research/connectors/    12 versioned connector modules + registry
├── agents/                 agent definitions (20) + boss + prompts
└── api/                    routers: auth, chat, voice, agents, research, skills,
                            memory, models, workflows, projects, terminal, build,
                            settings, security, system, websocket
android/app/src/main/       Kotlin client (activities, views, adapters, network)
scripts/                    toolchain bootstrap, acceptance runner, audits
verification/               acceptance tests + APK checks
docs/                       all research & architecture documents
```
