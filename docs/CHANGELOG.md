# CHANGELOG

## V18.0.0 — 2026-11-05

The first complete build of TITAN OMEGA INFINITY V18.

### Added — backend
- FastAPI application with 69 REST operations + 1 WebSocket under `/api/v1`.
- 31-table schema with migration `0001_initial`, SQLite default and a Postgres-ready model.
- Own JWT implementation, scrypt password hashing, five-role RBAC, API-key scheme,
  per-IP and per-user rate limiting.
- Central tool execution engine: 25 tools in 14 categories, each with an input schema, an
  output schema, a permission scope, a timeout, a retry policy and a machine-readable
  error contract.
- Model gateway: 8 providers, 20 models, task-based routing, retries, fallback chain,
  per-provider health, token/cost accounting, explicit `provider_mode` on every response.
- Global research engine: 11-stage pipeline, 12 connectors (GitHub / npm / PyPI live),
  partial-failure tolerance, verification badges, findings, Markdown reports.
- Memory with 8 scopes, deduplication, versioning, TTL and soft delete; hybrid RAG with
  BM25 + dense retrieval, RRF fusion, reranking and source attribution.
- Supreme Boss orchestrator (NLU → plan → parallel agents → validation → conflict notes →
  assembly) and Worker Bossman per-agent runner with quality scoring.
- 20 specialised agent contracts; dynamic agent factory and skill factory with a
  sandbox-test-before-publish gate.
- Durable workflow engine: DAG validation, cycle detection, level-parallel execution,
  retry, timeout, DB checkpoint, resume, cancel, approval gates.
- Sandbox: process isolation with rlimits, command allowlist, output caps, per-project
  roots; `BLOCKED_BY_POLICY` refusals instead of 500s.
- Voice capability probing, translation engine with detection + glossary, model evaluation
  and honest training status.
- Live capability report, Prometheus-style metrics, correlation IDs, structured JSON logs
  and a full audit trail.

### Added — Android
- Seven Kotlin screens: Home, Chat, Voice, Agents, Research, Workspace, More.
- SSE streaming chat, real microphone capture with an amplitude-driven waveform, on-device
  STT/TTS, live connector and provider status.
- Offline build pipeline `aapt2 → kotlinc → d8 → zip → apksigner` producing a **signed**
  APK (v1 + v2 + v3).

### Added — research and documentation
- 11 pre-build research documents and the architecture decision record (ADR-001…ADR-018).
- 28 documentation files, this changelog, the delivery manifest, the known-limitations
  list and the BREADCRUMB continuity file.

### Fixed during the acceptance cycle
- `SandboxError` from the sandbox surfaced as a 500 → now a structured `BLOCKED_BY_POLICY`
  refusal plus a `denied` audit row.
- Unknown memory scope returned a 500 → now HTTP 400.
- Unknown model id in `/models/evaluations` returned a 500 → now HTTP 404.
- Evaluation cases without an `id` crashed the run → ids are generated and the prompt is
  validated.
- Every tool shipped an empty `error_contract` → contracts are now composed centrally and
  are scope-specific.
- Memory writes did not deduplicate → identical content now becomes a new version of one
  row.
- The capability probe reported `d8` as present when the file was an Android-native
  binary → the probe now validates the Java entry point inside the archive.

### Known limitations
See `docs/KNOWN_LIMITATIONS.md`. The headline items: no device install test, no real LLM
provider, no Compose client, no fine-tuning, and 9 of 12 research connectors unreachable
from this host.
