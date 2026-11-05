# TITAN OMEGA INFINITY V18

**Verified development increment — not a completed V18 production release.**

TITAN is a mobile-first AI intelligence control plane with a real FastAPI backend, persistent research/agent/workflow state, a responsive operations console and native Kotlin/Compose Android source. It explicitly separates Builder AI pre-build research from the application's permanent runtime Research Engine.

## Implemented and exercised

- Environment audit and source-backed pre-build research reports; 46 GitHub projects and selected official documentation inspected.
- Permanent runtime research: official GitHub connector, per-source outcomes, partial-result preservation, source URLs, verification status, history, Markdown reports, knowledge ingestion and research-to-project/skill/agent conversion.
- Supreme Boss-style task fan-out with 20 registered specialist agents, independent async database sessions, retries, timeouts and execution evidence.
- Dynamic agent draft → contract sandbox test → approval lifecycle.
- Explicit deterministic mock plus real server-side OpenAI-compatible model adapter; persisted token/latency records.
- Persistent chat with SSE streaming, stop handling, export, title updates and mock labeling.
- Versioned pure-Python skill factory with schema checks, no-I/O sandbox tests, approval, execution and disable controls.
- Source-attributed lexical TF-IDF retrieval (explicitly **not vector RAG**) and scoped memory lifecycle.
- Typed workflow DAG validation, parallel levels, durable checkpoints, cancellation and resume.
- Project files with owner/canonical-path/symlink checks, atomic writes, approved allowlisted real terminal commands, build detection and Python compile builds.
- Alembic migrations, correlation IDs, audit events, source secret scan and 14 automated tests.
- Responsive web console and Android Home/Chat/Voice/Agents/Research routes. Browser/Android speech APIs are separate from the unimplemented backend voice service.

## Status boundaries

| Area | Status |
|---|---|
| Local backend + web operations console | IMPLEMENTED development profile |
| GitHub Research Engine | LIVE SMOKE VERIFIED |
| Hosted AI inference | CONFIGURABLE; credentials/live provider not supplied |
| Actual translation quality | BLOCKED until a live multilingual provider is configured/evaluated |
| PostgreSQL production deployment | CONFIG PROVIDED; not executed in this sandbox |
| Production terminal sandbox | NOT IMPLEMENTED; local boundary only |
| Vector/hybrid pgvector retrieval | PLANNED; current retrieval is lexical |
| Native Android compilation | SOURCE ONLY; JDK/Gradle/Android SDK unavailable |
| APK/install/launch | BLOCKED; no APK or fake download supplied |
| Backend ASR/TTS and Bengali quality | NOT IMPLEMENTED / UNVERIFIED |
| Fine-tuning/training artifacts | BLOCKED; no GPU/jobs/artifacts |
| Social, arXiv and multi-forge runtime connectors | NOT IMPLEMENTED |

See `BREADCRUMB.md` for exact continuation state and `TEST_REPORT.md` for the acceptance matrix.

## Run locally

Requirements: Python 3.11+, Node (only for JavaScript syntax verification) and network access for dependency installation.

```bash
make setup
make migrate
make run
```

Open `http://localhost:8000`. Interactive OpenAPI documentation is at `/docs`; liveness is `/health`.

The development profile uses SQLite and an implicit local principal. It has no provider key by default, so chat/agents/translation return an unmistakable **MOCK — NO LIVE AI INFERENCE** response.

### Configure a real model (server only)

```bash
export TITAN_OPENAI_COMPATIBLE_BASE_URL='https://your-provider.example/v1'
export TITAN_OPENAI_COMPATIBLE_API_KEY='server-side-secret'
export TITAN_OPENAI_COMPATIBLE_MODEL='verified-model-id'
make run
```

Do not put these values in Gradle, Kotlin, JavaScript, Android resources or Git. Gemini 4 Argon's documented ID is `gemini-4-argon`, but this increment does not include a dedicated Gemini adapter or verified account access.

## Verify

```bash
./scripts/verify.sh
```

This runs Ruff, JavaScript syntax checks, 14 tests, Alembic upgrade/check and a provider-secret source scan. Evidence: `docs/evidence/verification.log` and `docs/evidence/live_smoke.json`.

## Android source

`android/` contains `:app`, `:core-network` and `:core-ui`. The debug client targets the emulator host `10.0.2.2`; release requires a reachable HTTPS backend through `TITAN_API_BASE_URL`. No provider secrets are included. Build could not be attempted here because Java, Gradle, Android SDK and adb were absent. See `ANDROID_ARCHITECTURE.md` and `BUILD_REPORT.md`.

## Repository map

```text
backend/app/             FastAPI routes, persistence, policies and static console
backend/app/services/    Agents, research, model gateway, memory, skills, projects, workflows
backend/migrations/      Tested Alembic revisions
backend/tests/           Automated regressions
android/                 Native Kotlin/Compose source (unbuilt here)
deploy/                  PostgreSQL/backend Compose deployment reference
docs/research/evidence/  Builder research API snapshots
docs/evidence/           Verification logs and live smoke results
*.md                     Architecture, research, audit and release records
```

The unrelated pre-existing `instagram_2fa_automation.js` is preserved and was not executed or integrated.
