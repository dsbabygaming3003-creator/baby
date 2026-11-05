# ROADMAP

Ordered by what removes the largest gap between this build and the brief.

---

## Tier 1 — close the blocked verification gaps

| Item | Why first |
|---|---|
| Install + launch the APK on a device or emulator, then drive the 7 screens | the only unverified part of the Android deliverable |
| Provision one real provider key and re-run the acceptance suite | replaces `provider_mode=mock` with real output everywhere |
| Add a PostgreSQL profile and run the acceptance suite against it | proves the "Postgres-ready" claim instead of asserting it |

## Tier 2 — production readiness

| Item | Notes |
|---|---|
| TLS termination + `TITAN_JWT_SECRET` rotation policy | currently a development default |
| Redis-backed rate limiter and event broker | required before >1 worker |
| Scheduled database backups + restore drill | the recovery story must be tested, not described |
| Dependency scanning (pip-audit / OSV) in CI | closes a security gap |
| Upload malware scanning | closes a security gap |
| Postgres RLS policies | defence in depth beyond `org_id` filtering |
| Observability export (Prometheus scrape + Grafana dashboard) | metrics exist; the dashboard does not |

## Tier 3 — product completeness

| Item | Notes |
|---|---|
| Gradle + Compose + AndroidX client | the brief's intended UI stack, once the artifact hosts are reachable |
| The brief's modular Android layout (`core-*`, `feature-*`) | needs multi-module Gradle |
| Real model fine-tuning | needs a reachable training runtime and hardware |
| Server-side ASR (whisper.cpp) and TTS (piper) | unlocks the audio translation modality |
| Browser automation (Playwright) | unlocks the browser-automation capability |
| Workflow scheduler | the schedule field exists; the trigger loop does not |
| Docker sandbox backend | stronger isolation than the process backend |
| Research→skill/agent/project one-click actions | the data model supports it; the UI flow is partial |

## Tier 4 — scale

| Item | Notes |
|---|---|
| Multi-tenant Postgres with row-level security | required before onboarding external tenants |
| Object storage (S3/R2) for attachments and artifacts | the filesystem store is single-node |
| Vector database (Qdrant/pgvector) for large corpora | the NumPy index is in-process |
| Horizontal scaling of the WebSocket broker | Durable Objects or Redis pub/sub |
| Cost and quota enforcement per tenant | the gateway already accounts per call |
