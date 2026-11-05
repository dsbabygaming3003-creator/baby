# API REFERENCE

Base URL: `http://<host>:8000/api/v1` (configurable via `settings.api_prefix`).
69 REST operations across 58 path templates, plus one WebSocket at `/ws/events`.

All authenticated calls use `Authorization: Bearer <jwt>` (or `ApiKey <key>`).
Errors are FastAPI `{"detail": …}`; the correlation middleware adds `correlation_id`
to unhandled errors and to every log line.

---

## System

| Method | Path | Scope | Purpose |
|---|---|---|---|
| GET | `/system/health` | public | liveness + version |
| GET | `/system/capabilities` | public | live capability report (12 capabilities) |
| GET | `/system/metrics` | public | Prometheus-style text metrics |
| GET | `/system/audit` | `admin` | audit trail query |

## Auth

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | create an account (first account ⇒ `owner`; otherwise `researcher`/`developer`/`viewer` only) |
| POST | `/auth/login` | exchange credentials for a JWT (12 h TTL) |
| GET | `/auth/me` | current principal + scopes |

## Chat Studio

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/chat/conversations` | list / create |
| GET/PATCH/DELETE | `/chat/conversations/{id}` | read / rename / delete |
| GET/POST | `/chat/conversations/{id}/messages` | history / send |
| GET | `/chat/stream` | SSE token stream |

## Agents

| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | registry (20 core + dynamic) |
| GET | `/agents/{id}` | one agent contract |
| POST | `/agents/run` | run one agent (Worker Bossman) |
| POST | `/agents/factory` | draft a dynamic agent |
| POST | `/agents/factory/{id}/validate` | sandbox validation |
| GET | `/agents/factory/dynamic` | dynamic agent list |

## Research Center

| Method | Path | Purpose |
|---|---|---|
| GET | `/research/connectors` | connector registry (12) |
| GET | `/research/connectors/probe` | live per-connector probe |
| POST | `/research/tasks` | create a research task |
| POST | `/research/tasks/{id}/run` | execute it |
| GET | `/research/tasks` · `/research/tasks/{id}` | history / detail |
| POST | `/research/documents/{id}/ingest` | ingest a document into the knowledge base |
| GET | `/knowledge/search` | hybrid retrieval |

## Memory

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/memory` | list (8 scopes) / write (dedup + version + TTL) |
| DELETE | `/memory/{id}` | soft delete |

## Models & gateway

| Method | Path | Purpose |
|---|---|---|
| GET | `/models` · `/models/providers` | registry (20 models) / provider health |
| GET/POST | `/models/evaluations` | benchmark history / run a benchmark |
| GET | `/models/training` | training status (honest `NOT_RUN`) |
| POST | `/models/training/datasets` | dataset preparation (real) |

## Skills, tools, projects

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/skills` | list / draft a skill |
| POST | `/skills/{id}/test` | sandbox test |
| POST | `/skills/{id}/publish` | publish (requires a passing test) |
| POST | `/skills/{id}/install` | install into a project |
| GET | `/tools` | 25 tools, 14 categories, full contracts |
| POST | `/tools/{id}/execute` | execute with scope enforcement |
| GET | `/tools/executions` | execution history |
| GET/POST | `/projects` | list / create projects |

## Terminal & builds

| Method | Path | Purpose |
|---|---|---|
| POST | `/terminal/exec` | real sandboxed execution (`BLOCKED_BY_POLICY` on refusal) |
| GET/POST | `/builds` | build jobs |

## Workflows

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/workflows` | list / create (graph validated, cycles rejected) |
| POST | `/workflows/{id}/runs` | run |
| GET | `/workflows/runs` | run history |
| POST | `/workflows/runs/{id}/resume` · `/approve` · `/cancel` | lifecycle |

## Voice, translation, orchestration

| Method | Path | Purpose |
|---|---|---|
| GET | `/voice/capabilities` | honest ASR/TTS capability report |
| POST | `/voice/transcribe` · `/voice/speak` | server-side adapters |
| GET | `/translation/languages` | supported languages |
| POST | `/translation` · `/translation/detect` | translate / detect |
| POST | `/orchestrate` | Supreme Boss multi-agent execution |

## Settings & security

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/settings/secrets` | secret inventory (**`admin` only**) / set a secret |
| GET | `/security/summary` | RBAC roles, scopes, sandbox limits, egress allowlist |

## WebSocket

`ws://<host>:8000/ws/events` — a broadcast broker for agent, workflow, research and
build events plus a heartbeat.
