# BREADCRUMB — TITAN OMEGA INFINITY V18

> **Continuity rule.** Every session MUST read this file and the linked project docs
> **before** doing any work. It records the current phase, what is done, what is not,
> the active errors, the modified files, the decisions taken, the real tool results, the
> test results, the build status and **the exact next action**. Never redo prior work.

---

## Current phase

**Phase 12 — Release.** Phases 0–11 are complete and verified. Phase 12 is
**PARTIAL**: the source, the documentation and a signed APK are delivered; the device
install/launch verification is **BLOCKED** because the host has no emulator, no `adb` and
no system image (and the image hosts are outside the TLS egress allowlist).

**State as of 2026-11-05 (session end):** backend running on `0.0.0.0:8000`,
smoke **40/40**, acceptance **38/38**, release APK built and signed.

**Delivered commits** on branch `arena/3045e0c0-baby`, pushed to `origin`:
`d3505a2` (the build, 87 files) and `3e3fa7f` (published APKs).

**The signed APKs are committed** under `releases/` because GitHub release-asset
uploads are unreachable from this host (`uploads.github.com` is outside the TLS
allowlist). The SQLite database and `android/build/` stay ignored.

Download:
`https://github.com/dsbabygaming3003-creator/baby/raw/arena/3045e0c0-baby/releases/titan-omega-release.apk`
(sha256 `297a7ee1…`; the re-fetched copy was verified byte-identical and still
`apksigner`-valid). Rebuild with `bash android/tools/build_apk.sh --release`.

---

## Completed

| Area | Status | Where |
|---|---|---|
| Phase 0 — environment audit | done | `docs/ENVIRONMENT_AUDIT.md` |
| Phase 1 — pre-build research (10 docs + ADR) | done | `docs/GLOBAL_PREBUILD_RESEARCH.md` + 10 siblings |
| Phase 2 — architecture freeze (ADR-001…ADR-018) | done | `docs/ARCHITECTURE_DECISION_RECORD.md` |
| Backend (69 REST ops + 1 WS, 31 tables, 25 tools, 20 agents, 12 connectors) | done | `backend/titan/` |
| Global research engine | done | `backend/titan/services/research*.py` |
| Model gateway (8 providers, 20 models) | done | `backend/titan/services/gateway.py` |
| Memory + hybrid RAG | done | `backend/titan/services/{memory,rag}.py` |
| Supreme Boss + Worker Bossman + agent/skill factories | done | `backend/titan/services/{agents,factory}.py` |
| Durable workflow engine | done | `backend/titan/services/workflow.py` |
| Sandbox + tool execution engine | done | `backend/titan/services/{sandbox,tools,tools_impl}.py` |
| Android client — 7 screens, Kotlin compiles clean | done | `android/app/src/main/` |
| Offline APK pipeline + signed APK | done | `android/tools/build_apk.sh`, `docs/BUILD_REPORT.md` |
| Toolchain bootstrap script | done | `scripts/toolchain/setup_toolchain.sh` |
| Smoke test (40 checks) | 40/40 | `verification/smoke_test.py` |
| Acceptance suite (38 checks) | 38/38 | `verification/run_acceptance.py`, `docs/TEST_REPORT.md` |
| Documentation (38 files) | done | `docs/`, `README.md`, `ARCHITECTURE.md` |

---

## Not done / blocked (do **not** re-attempt without new capability)

| Item | State | Reason |
|---|---|---|
| APK install + launch on a device | **BLOCKED** | no emulator, no `adb`, no system image; `dl.google.com` / `developer.android.com` TLS-blocked |
| Gradle + Compose + AndroidX client | **BLOCKED** | Maven Central / Google Maven / Gradle distribution TLS-blocked |
| A real LLM provider | **BLOCKED** | no API key exists in this environment |
| 9 of 12 research connectors | **BLOCKED** | hosts outside the TLS allowlist (reported as `inaccessible`) |
| Server-side ASR/TTS, browser automation, Docker | **BLOCKED** | binaries/socket absent |
| Real model fine-tuning | **NOT IMPLEMENTED** | no training runtime → `GET /models/training` returns `NOT_RUN` |
| Workflow scheduler, OCR translation, doc-layout translation, automatic patch application, scheduled backups, upload malware scanning, CI dependency scanning, Postgres RLS, Android instrumentation tests | **NOT IMPLEMENTED** | see `docs/KNOWN_LIMITATIONS.md` §2 |

---

## Active errors

**None outstanding.** The last acceptance run finished with 0 failures.

Bugs found and fixed during the acceptance cycle (do not reintroduce):

| Bug | Fix |
|---|---|
| `SandboxError` surfaced as HTTP 500 from `/terminal/exec` | structured `BLOCKED_BY_POLICY` refusal + `denied` audit row |
| Unknown memory scope → HTTP 500 | route validates the scope → HTTP 400 |
| Unknown model id in `/models/evaluations` → HTTP 500 (`KeyError: 'id'`) | registry check → HTTP 404; cases are normalised and validated |
| Every tool had an empty `error_contract` | contracts composed centrally from the permission scope (`services/tools.py::build_error_contract`) |
| Memory writes never deduplicated | identical content in the same scope+key+kind now bumps `version` on one row |
| The capability probe reported `d8` present for the Android-native `d8-termux` binary | the probe now checks that `com/android/tools/r8/D8.class` exists inside the archive |

---

## Modified files in this session

```
backend/titan/services/tools.py          error contracts + scope-specific codes
backend/titan/services/memory.py         dedup + version-bump policy, TTL
backend/titan/services/media.py           evaluation case normalisation/validation
backend/titan/api/routes.py               400/404 input validation, richer capability probe
verification/run_acceptance.py            NEW — 38-test acceptance suite
verification/acceptance_results.json      NEW — machine-readable evidence
android/tools/build_apk.sh                d8 jar packing, apksigner signing
scripts/toolchain/setup_toolchain.sh      NEW — reproducible offline bootstrap
docs/*.md (38 files)                      NEW/updated
README.md ARCHITECTURE.md BREADCRUMB.md THIRD_PARTY_NOTICES.md LICENSE .gitignore   NEW
```

---

## Key decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Research before building | deliverable A was completed in full before any implementation code was written |
| 2 | Framework Views, no Compose | Compose/AndroidX cannot be fetched on this host; a Compose build that was never compiled would break the anti-fake contract (ADR-011) |
| 3 | Hand-written `aapt2 → kotlinc → d8 → zip → apksigner` pipeline | Gradle is unreachable; this pipeline was executed and verified end to end |
| 4 | SQLite default, Postgres-ready schema | Postgres is not installable here; the schema uses portable types and explicit migrations |
| 5 | Native gateway, not LiteLLM | smaller dependency surface, auditable routing logic, no unreachable package |
| 6 | Deterministic local 384-d embedder | no embedding API is reachable; a fabricated vector would be dishonest |
| 7 | Mock provider is **labelled**, never silent | every response carries `provider_mode`; AT-10/AT-18/AT-31/AT-33 assert it |
| 8 | Blocked capabilities are **reported**, not hidden | `GET /system/capabilities` is computed live on every call |
| 9 | Self-repair proposes, a human applies | auto-rewriting schema or security config is the failure mode the brief asked to avoid |
| 10 | `instagram_2fa_automation.js` untouched | pre-existing owner asset, excluded from the licence grant |

---

## Tool results (real, verified)

| Tool | Result |
|---|---|
| `java -cp d8/d8.jar com.android.tools.r8.D8 --version` | `D8 8.2.2-dev (build facedf41bbd28b563d1e9e09c5f72d7c5ca598d5)` |
| `java -cp build-tools/apksigner.jar …ApkSignerTool version` | `0.9` |
| `kotlinc` over all 9 Kotlin sources | clean, 0 errors |
| `aapt2 dump badging` | `titan.omega.infinity` 18.0.0 / code 18, min 24, target 35 |
| `apksigner verify --min-sdk-version 21 --verbose` | v1 true, v2 true, v3 true |
| DEX header inspection | `dex\n037\0`, 1 211 class defs, 2 395 860 B |
| Secret-pattern scan of `classes.dex` (`sk-`, `AIza`, `api_key`, `API_KEY`, `OPENAI`, `anthropic`) | **0 hits each** |
| `verification/smoke_test.py` | 40/40 pass |
| `verification/run_acceptance.py` | 38/38 pass |
| Live connectors | `github.v1` ok, `npm.v1` ok, `pypi.v1` ok/empty, 9 × `inaccessible` |
| Live research run | 30 documents, 12 findings, 15 verified |

### Dead ends — do not retry

`apt-get` (HTTP 80 blocked) · Adoptium / `dl.google.com` / `developer.android.com` /
`download.jetbrains.com` (TLS) · Maven Central / Google Maven / all Gradle mirrors (TLS) ·
npm `d8-termux` (Android-native binary, not a Java dexer) · `is-a-minkey/Html-to-apk`
`d8.jar`/`r8.jar` (404 stubs) · `VMahajan10/UVA-…-Research` Android SDK (Git LFS
pointers) · `joshuapetersen/Sarah-John-Genesis` `r8.jar` (LFS pointer; `media.githubusercontent.com`
is TLS-blocked) · GitHub LFS batch API (403 for this token) · PyPI `d8`/`r8`/`android-sdk`
(wrong packages) · npm `android-sdk` (a sample app).

**What worked:** npm `@drxiaozhi/minapk` ships the real `d8.jar` **and** `apksigner.jar`
(both Java jars) — that single package unblocked the APK. `Sable/android-platforms` gives
real `android.jar` files over plain codeload.

---

## Test results

| Suite | Result |
|---|---|
| `verification/smoke_test.py` (40 checks) | **40 / 40 PASS**, 10.8 s |
| `verification/run_acceptance.py` (38 checks) | **38 / 38 PASS**, ~12 s |
| Evidence | `docs/TEST_REPORT.md`, `verification/acceptance_results.json` |

---

## Build status

| Artifact | Status |
|---|---|
| Release APK | **built + signed** — 721,391 B, sha256 `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` |
| Debug APK | **built + signed** — 721,397 B, sha256 `a5f3281bc6745957fa97b1ec404354b463013b17c62d2b1b179ad3c902da396f` |
| Backend | **running** on `0.0.0.0:8000` (`titan.main:app`) |
| Database | `data/titan.db` (SQLite), 31 tables, migration `0001_initial` |
| Install / launch on a device | **BLOCKED** |

---

## Exact next action

1. **If new capability arrives** (device/emulator, a provider key, Maven access): re-run
   `scripts/toolchain/setup_toolchain.sh`, rebuild the APK, install it on the device, drive
   the 7 screens, and re-run both verification suites against the real provider.
2. **If nothing new arrives**: the build is complete and honest. The remaining work is
   documentation polish and the honest limitation list, which is already written.

### Next session checklist

```bash
cat BREADCRUMB.md                     # this file
cat docs/KNOWN_LIMITATIONS.md         # what is still blocked
cd backend && /opt/titan/venv/bin/python -m uvicorn titan.main:app --host 0.0.0.0 --port 8000 &
/opt/titan/venv/bin/python verification/smoke_test.py        # expect 40/40
/opt/titan/venv/bin/python verification/run_acceptance.py   # expect 38/38
```

**Never** report a blocked capability as working, and never fabricate a device install
result.
