# TITAN OMEGA INFINITY V18 — ARCHITECTURE

> Companion to [`docs/ARCHITECTURE_DECISION_RECORD.md`](docs/ARCHITECTURE_DECISION_RECORD.md)
> (the *why* — ADR-001…ADR-018). This document is the *what*.

---

## 1. System shape

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ANDROID CLIENT (Kotlin)                          │
│  Home · Chat · Voice · Agents · Research · Workspace · More             │
│  Framework Views (no Compose — see ADR-011), MVVM, coroutines           │
│  HttpURLConnection + SSE, SharedPreferences token, no secrets           │
└───────────────┬──────────────────────────────┬─────────────────────────┘
                │ HTTPS/JSON  /api/v1            │ SSE  /api/v1/chat/stream
                │ WebSocket  /ws/events          │
┌───────────────▼──────────────────────────────▼─────────────────────────┐
│                          FASTAPI BACKEND                               │
│  api/routes.py — 69 REST operations + 1 WebSocket                      │
│  ┌──────────┬───────────┬────────────┬────────────┬──────────────────┐ │
│  │ Research │  Agents   │  Gateway   │   Memory   │  Workflow/Factory│ │
│  │ Engine   │  Supreme  │  (8 prov.) │  + RAG     │  (DAG, skills)   │ │
│  │ 12 conn. │  Boss +   │  routing,  │  8 scopes, │                  │ │
│  │          │  20 specs │  fallback  │  hybrid    │                  │ │
│  └────┬─────┴─────┬─────┴─────┬──────┴─────┬──────┴──────────────────┘ │
│       │           │           │            │                            │
│  ┌────▼───────────▼───────────▼────────────▼─────────────────────────┐ │
│  │      Central Tool Execution Engine (25 tools / 14 categories)      │ │
│  │  schema · permission · timeout · retry · error contract · audit  │ │
│  └────┬────────────────────────────────────────────────────────────┘ │
│       │                                                                │
│  ┌────▼─────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────┐ │
│  │  Sandbox     │  │  Research    │  │  SecretStore  │  │  Audit +  │ │
│  │  (process)   │  │  connectors  │  │  (server only)│  │  Metrics  │ │
│  └──────────────┘  └──────────────┘  └───────────────┘  └───────────┘ │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ SQLAlchemy 2.0 async
                    ┌───────────▼────────────┐
                    │  SQLite (aiosqlite)    │   →  Postgres-ready schema
                    │  31 tables, migration  │
                    └────────────────────────┘
```

---

## 2. Backend modules

| Module | Responsibility | Key file |
|---|---|---|
| `config` | Settings, egress allowlist, sandbox limits, command allowlist | `titan/config.py` |
| `db` | Async engine, `0001_initial` migration, commit/rollback session lifecycle | `titan/db.py` |
| `models` | 31 ORM tables (see `docs/DATABASE_SCHEMA.md`) | `titan/models.py` |
| `security.core` | scrypt hashing, own JWT (HS256), RBAC scopes, `SecretStore`, redaction | `titan/security/core.py` |
| `security.net` | SSRF guard (DNS + IP range checks), system-CA `http_client()` | `titan/security/net.py` |
| `agents.definitions` | 20 specialised agent contracts (instructions, model config, tool grants, I/O schemas, timeouts, retries, quality criteria) | `titan/agents/definitions.py` |
| `services.research` | Task lifecycle, connector fan-out, verification, findings, Markdown report, knowledge ingestion | `titan/services/research.py` |
| `services.research_connectors` | 12 per-source connectors (GitHub / npm / PyPI live) | `titan/services/research_connectors.py` |
| `services.agents` | `WorkerBossman` (single-agent execution) + `SupremeBoss` (NLU → plan → parallel agents → validation → conflict notes → assembly) | `titan/services/agents.py` |
| `services.factory` | Dynamic agent factory (draft → validate → activate) and skill factory (draft → sandbox test → publish → install) | `titan/services/factory.py` |
| `services.gateway` | Provider registry, routing, retries, fallback, health, cost/token accounting | `titan/services/gateway.py` |
| `services.rag` | Chunking, deterministic 384-d embedder, BM25, RRF fusion, rerank, source attribution | `titan/services/rag.py` |
| `services.memory` | 8 scopes, dedup + versioning + TTL + soft delete | `titan/services/memory.py` |
| `services.workflow` | DAG validation, cycle detection, level-parallel execution, retry, checkpoint/resume, approval gates | `titan/services/workflow.py` |
| `services.tools` | `Tool` dataclass, registry, per-tool error contracts | `titan/services/tools.py` |
| `services.tools_impl` | 25 concrete tool handlers | `titan/services/tools_impl.py` |
| `services.sandbox` | Process isolation with rlimits, command allowlist, output caps | `titan/services/sandbox.py` |
| `services.media` | Translation, voice capability probes, build jobs, evaluation + training status | `titan/services/media.py` |
| `services.observability` | Prometheus-style metrics, correlation IDs, structured logs | `titan/services/observability.py` |
| `api.deps` | JWT/API-key principal resolution, scope enforcement, rate limiting | `titan/api/deps.py` |
| `api.routes` | The full HTTP surface | `titan/api/routes.py` |

---

## 3. The three orchestrators

```
                      user request
                           │
                 ┌─────────▼─────────┐
                 │   SUPREME BOSS    │  NLU → intent → decomposition → plan
                 │ (orchestrator)    │  agent/model/tool selection
                 └─────────┬─────────┘  parallel execution → validation
                           │            → conflict resolution → assembly
              ┌────────────┴────────────┐
              │                         │
   ┌──────────▼─────────┐   ┌───────────▼──────────┐
   │  WORKER BOSSMAN    │   │   TOOL EXECUTION     │
   │ (per-agent runner) │──▶│  ENGINE (25 tools)   │
   │ quality score,     │   │  scope / timeout /    │
   │ tokens, cost, log  │   │  retry / error contract│
   └────────────────────┘   └──────────────────────┘
```

* **Supreme Boss** never exposes private chain-of-thought. Its output is a verifiable
  execution summary: plan, per-step agents, decisions, tool activity, evidence, conflicts.
* **Worker Bossman** runs one agent contract end-to-end and scores the result against the
  agent's own quality criteria.
* **The tool engine** is the only path to a side effect. A tool that did not run can never
  be reported as successful — every call returns `ok`, `error_code`, `duration_ms`.

---

## 4. Research pipeline (System B)

```
 query
   │
   ├─▶ Auth/Policy ─▶ Query Adapter ─▶ Retrieval ─▶ Normalization
   │                                              │
   │                                              ▼
   │                                        Dedup ─▶ Extraction ─▶ Verification
   │                                                                    │
   │                                                                    ▼
   └────────────────────────────────────────────────────────────▶ Ranking
                                                                      │
                        ┌─────────────────────────────────────────────┤
                        ▼                                             ▼
                  Analysis (findings)                          Knowledge (chunks + embeddings)
                        │                                             │
                        └──────────────▶ Report (Markdown) ◀──────────┘
```

* 12 connectors, each with its own auth + policy + query adapter.
* **Partial failure is normal**: one connector failing never aborts a task. The run summary
  lists per-connector `status` / `count` / `duration_ms` / `http_status`.
* Verification assigns `verification_status` + `confidence` + `injection_risk` + `trust`
  (`untrusted` for every external document — external content is data, never instructions).
* Findings are stored with an `evidence_url`; documents are chunked, embedded and indexed
  for hybrid retrieval.

---

## 5. Memory + RAG

```
write ─▶ scope validation (8 scopes) ─▶ dedup (same scope+key+kind+content)
      ─▶ version bump OR insert ─▶ TTL/expiry ─▶ importance/confidence ─▶ soft delete
```

```
ingest ─▶ cleaning ─▶ chunking (900 chars, 120 overlap) ─▶ embed (384-d, L2-normalised)
       ─▶ vector index (NumPy) + BM25 index ─▶ hybrid query ─▶ RRF fusion
       ─▶ rerank ─▶ context assembly ─▶ answer with source attribution
```

---

## 6. Android client

| Screen | Purpose | Live data source |
|---|---|---|
| Home | health, capabilities, agent/research/model tiles | `GET /system/capabilities`, `/agents`, `/models` |
| Chat | conversation list, SSE streaming replies | `GET/POST /chat/conversations`, `GET /chat/stream` |
| Voice | mic capture + waveform + STT + TTS | `AudioRecord`, `SpeechRecognizer`, `TextToSpeech`, `/voice/*` |
| Agents | registry, agent detail, dynamic agent factory | `/agents`, `/agents/factory` |
| Research | connector chips, task create/run, probe, history | `/research/*` |
| Workspace | projects, real terminal execution, builds | `/projects`, `/terminal/exec`, `/builds` |
| More | models/providers, skills, workflows, memory, security tabs | `/models`, `/skills`, `/workflows`, `/memory`, `/security/summary` |

The client uses framework Views and `HttpURLConnection` because Compose/AndroidX artifacts
cannot be fetched on this host (ADR-011). The build pipeline is described in
`docs/BUILD_GUIDE.md`.

---

## 7. Cross-cutting rules

| Rule | Where it is enforced |
|---|---|
| Secrets never leave the server | `security/core.SecretStore`, `/settings/secrets` is `admin`-gated, the APK contains no key |
| External content is untrusted data | `research` marks every document `trust=untrusted`; the prompt path never interpolates fetched text as instructions |
| SSRF / egress control | `security/net.py` resolves DNS and rejects private, loopback, link-local and non-allowlisted targets |
| Sandbox isolation | `services/sandbox.py` — rlimits, allowlisted commands, capped output, per-project root |
| Every side effect is audited | `audit()` in `api/routes.py` → `audit_logs` + `titan_audit_events_total` |
| A tool that did not run is a failure | `ToolResult.ok` is the only success signal; `error_code` is always present |
| Correlation IDs | `main.correlation_middleware` stamps every request and log line |
| Honest capability reporting | `GET /system/capabilities` — 12 capabilities, each with `status` + `detail` |
