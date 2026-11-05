# TITAN OMEGA INFINITY V18

**ULTIMATE SUPREME BUILD** — a mobile-first autonomous AI ecosystem: a FastAPI backend
(74 routes, 25 tools, 20 specialised agents, a global research engine, a model gateway,
memory + RAG, a workflow engine, a skill/agent factory and a real sandboxed terminal) plus a
native Kotlin Android client that ships as a **real, signed, installable APK**.

> **Anti-fake contract.** Every capability in this repository reports its own real state.
> If something did not run, it is reported as `PARTIAL`, `BLOCKED` or `NOT IMPLEMENTED` —
> never as complete. Mock providers exist, but they are labelled `provider_mode=mock` in
> every payload that uses them.

---

## 1. Verified status at a glance

| Area | State | Evidence |
|---|---|---|
| Backend API | **AVAILABLE** | 69 REST operations + 1 WebSocket, live on `0.0.0.0:8000` |
| Database | **AVAILABLE** | SQLite (aiosqlite) at `data/titan.db`, 31 tables, migration `0001_initial` |
| Research engine | **AVAILABLE** | 12 connectors; GitHub / npm / PyPI live; 9 honestly `inaccessible` |
| Tool execution engine | **AVAILABLE** | 25 tools, 14 categories, every tool has schema + permission + timeout + retry + error contract |
| Agent system | **AVAILABLE** | Supreme Boss orchestrator + Worker Bossman + 20 specialised core agents + dynamic factory |
| Model gateway | **AVAILABLE, degraded** | 8 providers registered, 20 models, **none** reports `ready` (no API keys provisioned) → every call is explicitly `provider_mode=mock` |
| Sandbox terminal | **AVAILABLE** | real process execution with CPU/mem/output limits and a command allowlist |
| Memory + RAG | **AVAILABLE** | 8 memory scopes, dedup + versioning + TTL, hybrid BM25 + dense retrieval with source attribution |
| Workflow engine | **AVAILABLE** | DAG validation, cycle detection, retry, checkpoint, resume, approval gates |
| Android client | **AVAILABLE** | Kotlin, 7 screens, compiles clean, **signed APK produced** |
| Android build toolchain | **AVAILABLE** | `aapt2 → kotlinc → d8 → zip → apksigner` running fully offline |
| APK installation / launch test | **BLOCKED** | no emulator, no `adb` device and no system image on this host |
| Server-side ASR / TTS | **DEGRADED** | no `whisper.cpp` / `piper` binary; the Android client uses the on-device engines |
| Real model fine-tuning | **NOT IMPLEMENTED (honest)** | dataset preparation is real; no training runtime is installed, so status stays `NOT_RUN` |
| Browser automation | **BLOCKED** | no browser engine available in this deployment |

Full machine-generated evidence: [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) (38/38 acceptance
tests) and [`verification/acceptance_results.json`](verification/acceptance_results.json).

---

## 2. The Android APK (real, signed, verified)

| | |
|---|---|
| Artifact | `android/build/outputs/apk/titan-omega-release.apk` |
| Size | **721,391 bytes** (release) / 721,397 bytes (debug) |
| SHA-256 (release) | `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` |
| Package | `titan.omega.infinity` |
| Version | `18.0.0` (versionCode 18) |
| min / target SDK | 24 / 35 (compileSdk 35) |
| Signature | APK Signature Scheme **v1 + v2 + v3** (verified by `apksigner`) |
| Contents | `AndroidManifest.xml`, `res/drawable/ic_launcher.xml`, `resources.arsc`, `classes.dex` (2,395,860 B, valid DEX 037), `META-INF/` JAR signature |
| Permissions | `INTERNET`, `ACCESS_NETWORK_STATE`, `RECORD_AUDIO` |
| Install / launch test | **BLOCKED** — no emulator, no `adb`, no system image on this build host |

The APK contains **no provider API key**. Secrets live only in the backend
(`/opt/titan/venv`, `SecretStore`), and the client receives only a bearer JWT.

Build it yourself:

```bash
bash scripts/toolchain/setup_toolchain.sh          # offline toolchain (aapt2/JDK/Kotlin/D8/apksigner)
cd android && bash tools/build_apk.sh --release     # -> build/outputs/apk/titan-omega-release.apk
```

See [`docs/BUILD_REPORT.md`](docs/BUILD_REPORT.md) for the full build log and
[`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md) for the pipeline breakdown.

---

## 3. Run the backend

```bash
bash scripts/toolchain/setup_toolchain.sh          # creates /opt/titan/venv with the deps
cd backend
/opt/titan/venv/bin/python -m uvicorn titan.main:app --host 0.0.0.0 --port 8000
```

```bash
# smoke test  (40 checks)      -> 40/40
/opt/titan/venv/bin/python verification/smoke_test.py
# acceptance suite (38 checks) -> 38/38
/opt/titan/venv/bin/python verification/run_acceptance.py
```

The API is served under `/api/v1`. Register a user and start using it:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"a-strong-password","display_name":"You"}'
```

The **first** account of an installation becomes `owner`; every later self-registration is
restricted to `researcher` / `developer` / `viewer`.

---

## 4. Repository layout

```
backend/titan/            FastAPI backend package
  config.py               settings, egress allowlist, sandbox limits, command allowlist
  db.py                   async engine, migrations, session lifecycle
  models.py               31 ORM tables
  security/core.py        scrypt hashing, own JWT, RBAC scopes, SecretStore, redaction
  security/net.py         SSRF guard + system-CA http client
  agents/definitions.py   20 specialised agent contracts
  services/               research, connectors, agents, gateway, rag, memory, factory,
                          workflow, media, sandbox, tools, observability
  api/routes.py           the full HTTP surface
  main.py                 app, lifespan seeding, CORS, correlation middleware, WS broker
android/app/src/main/     Kotlin client (7 screens, framework Views, no Compose)
android/tools/            build_apk.sh + sign_apk.mjs
verification/             smoke_test.py + run_acceptance.py
scripts/toolchain/        reproducible offline toolchain bootstrap
docs/                     research, architecture, security, test and build reports
```

---

## 5. Documentation index

**Pre-build research (deliverable A — completed before implementation began)**
[`ENVIRONMENT_AUDIT`](docs/ENVIRONMENT_AUDIT.md) ·
[`GLOBAL_PREBUILD_RESEARCH`](docs/GLOBAL_PREBUILD_RESEARCH.md) ·
[`RESEARCH_SOURCE_COVERAGE`](docs/RESEARCH_SOURCE_COVERAGE.md) ·
[`TECHNOLOGY_COMPARISON`](docs/TECHNOLOGY_COMPARISON.md) ·
[`OPEN_SOURCE_INVENTORY`](docs/OPEN_SOURCE_INVENTORY.md) ·
[`LICENSE_AUDIT`](docs/LICENSE_AUDIT.md) ·
[`SECURITY_RESEARCH`](docs/SECURITY_RESEARCH.md) ·
[`HERMES_AGENT_ANALYSIS`](docs/HERMES_AGENT_ANALYSIS.md) ·
[`MODEL_SELECTION_REPORT`](docs/MODEL_SELECTION_REPORT.md) ·
[`UI_UX_RESEARCH`](docs/UI_UX_RESEARCH.md)

**Architecture**
[`ARCHITECTURE`](ARCHITECTURE.md) ·
[`ARCHITECTURE_DECISION_RECORD`](docs/ARCHITECTURE_DECISION_RECORD.md) ·
[`DATABASE_SCHEMA`](docs/DATABASE_SCHEMA.md) ·
[`API_REFERENCE`](docs/API_REFERENCE.md) ·
[`DEVELOPMENT_PHASES`](docs/DEVELOPMENT_PHASES.md)

**Subsystems**
[`RESEARCH_ENGINE`](docs/RESEARCH_ENGINE.md) ·
[`AGENT_SYSTEM`](docs/AGENT_SYSTEM.md) ·
[`SKILL_FACTORY`](docs/SKILL_FACTORY.md) ·
[`MODEL_GATEWAY`](docs/MODEL_GATEWAY.md) ·
[`MEMORY_AND_RAG`](docs/MEMORY_AND_RAG.md) ·
[`WORKFLOW_ENGINE`](docs/WORKFLOW_ENGINE.md) ·
[`TOOL_ENGINE`](docs/TOOL_ENGINE.md) ·
[`SANDBOX_AND_CLOUD_WORKSPACE`](docs/SANDBOX_AND_CLOUD_WORKSPACE.md) ·
[`TRANSLATION_ENGINE`](docs/TRANSLATION_ENGINE.md) ·
[`VOICE_STUDIO`](docs/VOICE_STUDIO.md)

**Platform**
[`ANDROID_CLIENT`](docs/ANDROID_CLIENT.md) ·
[`UI_UX_SPECIFICATION`](docs/UI_UX_SPECIFICATION.md) ·
[`SECURITY_MODEL`](docs/SECURITY_MODEL.md) ·
[`OBSERVABILITY`](docs/OBSERVABILITY.md) ·
[`EVALUATION_AND_TRAINING`](docs/EVALUATION_AND_TRAINING.md) ·
[`SELF_REPAIR`](docs/SELF_REPAIR.md) ·
[`DEPLOYMENT`](docs/DEPLOYMENT.md) ·
[`BUILD_GUIDE`](docs/BUILD_GUIDE.md)

**Delivery**
[`TEST_REPORT`](docs/TEST_REPORT.md) ·
[`BUILD_REPORT`](docs/BUILD_REPORT.md) ·
[`DELIVERY_MANIFEST`](docs/DELIVERY_MANIFEST.md) ·
[`KNOWN_LIMITATIONS`](docs/KNOWN_LIMITATIONS.md) ·
[`ROADMAP`](docs/ROADMAP.md) ·
[`CHANGELOG`](docs/CHANGELOG.md) ·
[`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES.md) ·
[`BREADCRUMB`](BREADCRUMB.md) — the continuity file every session must read first.

---

## 6. Honest deviations

These are deliberate, documented deviations forced by the build host — none of them is
hidden:

1. **No Gradle / Compose / AndroidX.** The host's TLS egress allowlist excludes every
   Maven/Google/Gradle host. The client is therefore plain Kotlin with framework Views and
   a hand-written `aapt2 → kotlinc → d8 → zip → apksigner` pipeline. Gradle build files are
   not shipped because they could not be executed or verified here — shipping an unverified
   build script would violate the anti-fake contract.
2. **SQLite instead of PostgreSQL.** SQLite is the default profile; the schema is
   Postgres-ready (`SQLAlchemy 2.0` async, portable types, explicit migrations). See
   [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md).
3. **No vector database server.** Dense retrieval uses a deterministic local 384-dimensional
   embedder + NumPy cosine, fused with BM25 through reciprocal-rank fusion. A vector server
   (Qdrant / pgvector) is a documented drop-in, not a claim.
4. **No real LLM provider is configured.** No API keys exist in this environment, so every
   model call returns an explicitly labelled mock. Provider reachability is reported live.
5. **No emulator.** The APK is built, signed and structurally verified, but it could not be
   installed or launched on a device here. That limitation is stated in
   [`docs/BUILD_REPORT.md`](docs/BUILD_REPORT.md) rather than papered over.

See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for the exhaustive list.

---

## 7. Licence

See [`LICENSE`](LICENSE) (project code) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (dependency licences).
`instagram_2fa_automation.js` in the repository root is a pre-existing owner asset: it is
untouched, unmodified and excluded from TITAN's licence grant.
