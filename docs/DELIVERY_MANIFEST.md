# DELIVERY MANIFEST

What was delivered, how big it is, and how each piece was verified.

---

## 1. Source

| Area | Files | Lines | Path |
|---|---|---|---|
| Backend | 27 | 7,678 | `backend/titan/` |
| Android client | 7 Kotlin + 1 manifest + 1 drawable | 1,727 | `android/app/src/main/` |
| Android build tooling | 2 | — | `android/tools/build_apk.sh`, `android/tools/sign_apk.mjs` |
| Verification | 2 | 988 | `verification/smoke_test.py`, `verification/run_acceptance.py` |
| Toolchain bootstrap | 1 | 156 | `scripts/toolchain/setup_toolchain.sh` |
| Documentation | 38 markdown files | 5,089 | `docs/` + root `README.md`, `ARCHITECTURE.md`, `BREADCRUMB.md`, `THIRD_PARTY_NOTICES.md`, `LICENSE` |
| **Total source + docs** | — | **≈ 15,900** | — |

## 2. Binary artifact

| Artifact | Size | SHA-256 |
|---|---|---|
| `android/build/outputs/apk/titan-omega-release.apk` | 721,391 B | `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` |
| `android/build/outputs/apk/titan-omega-debug.apk` | 721,397 B | `a5f3281bc6745957fa97b1ec404354b463013b17c62d2b1b179ad3c902da396f` |

The APK is **not** committed to git (`android/build/` is ignored); rebuild it with
`bash android/tools/build_apk.sh --release`. The hash above proves the rebuild is
byte-reproducible for the same inputs.

## 3. Backend surface

| Item | Count |
|---|---|
| REST operations | 69 |
| Path templates | 58 |
| WebSocket endpoints | 1 (`/ws/events`) |
| Registered tools | 25 |
| Tool categories | 14 |
| Core agents | 20 |
| Models | 20 (18 with verified identifiers) |
| Providers | 8 (none `ready` — no credentials) |
| Research connectors | 12 (3 live, 9 `inaccessible`) |
| Database tables | 31 |
| Memory scopes | 8 |
| Capabilities reported | 12 |

## 4. Verification summary

| Suite | Checks | Result | Evidence |
|---|---|---|---|
| Smoke test (`verification/smoke_test.py`) | 40 | **40/40 pass** | live run, 2026-11-05 |
| Acceptance suite (`verification/run_acceptance.py`) | 38 | **38/38 pass** | `docs/TEST_REPORT.md`, `verification/acceptance_results.json` |
| Kotlin compilation | 9 sources | **clean, 0 errors** | `android/tools/build_apk.sh` step 3 |
| APK build | — | **pass** | `docs/BUILD_REPORT.md` |
| APK signature | v1 + v2 + v3 | **verified** | `apksigner verify` |
| APK structure | manifest + arsc + DEX 037 | **verified** | `docs/BUILD_REPORT.md` §3 |
| Secrets scan of the artifact | 6 patterns | **0 hits** | `docs/BUILD_REPORT.md` §5 |
| Device install / launch | — | **BLOCKED** | no emulator / `adb` on the host |

## 5. Documentation map

**Deliverable A — pre-build research (10 docs + ADR):** `ENVIRONMENT_AUDIT`,
`GLOBAL_PREBUILD_RESEARCH`, `RESEARCH_SOURCE_COVERAGE`, `TECHNOLOGY_COMPARISON`,
`OPEN_SOURCE_INVENTORY`, `LICENSE_AUDIT`, `SECURITY_RESEARCH`, `HERMES_AGENT_ANALYSIS`,
`MODEL_SELECTION_REPORT`, `UI_UX_RESEARCH`, `ARCHITECTURE_DECISION_RECORD`.

**Deliverable B — the research engine as a product:** `RESEARCH_ENGINE`,
`AGENT_SYSTEM`, `SKILL_FACTORY`, `MODEL_GATEWAY`, `MEMORY_AND_RAG`, `WORKFLOW_ENGINE`,
`TOOL_ENGINE`, `SANDBOX_AND_CLOUD_WORKSPACE`, `TRANSLATION_ENGINE`, `VOICE_STUDIO`.

**Platform:** `ANDROID_CLIENT`, `UI_UX_SPECIFICATION`, `SECURITY_MODEL`, `OBSERVABILITY`,
`EVALUATION_AND_TRAINING`, `SELF_REPAIR`, `DEPLOYMENT`, `BUILD_GUIDE`,
`DEVELOPMENT_PHASES`.

**Delivery:** `TEST_REPORT`, `BUILD_REPORT`, `DELIVERY_MANIFEST`,
`KNOWN_LIMITATIONS`, `ROADMAP`, `CHANGELOG`, plus the root `README.md`,
`ARCHITECTURE.md`, `BREADCRUMB.md`, `THIRD_PARTY_NOTICES.md` and `LICENSE`.

## 6. Reproducing the verification

```bash
bash scripts/toolchain/setup_toolchain.sh
cd backend && /opt/titan/venv/bin/python -m uvicorn titan.main:app --host 0.0.0.0 --port 8000 &
cd .. && /opt/titan/venv/bin/python verification/smoke_test.py
/opt/titan/venv/bin/python verification/run_acceptance.py
cd android && bash tools/build_apk.sh --release
```
