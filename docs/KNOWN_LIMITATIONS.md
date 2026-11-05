# KNOWN LIMITATIONS

Everything below is a real, current limitation of this build. None of it is hidden from
the API: `GET /system/capabilities` reports the same states at runtime.

---

## 1. Blocked by the build environment

| # | Limitation | Cause | Effect | Would need |
|---|---|---|---|---|
| 1 | No device install / launch test | no emulator, no `adb`, no system image; `dl.google.com` and `developer.android.com` are outside the TLS allowlist | the APK is built, signed and structurally verified, but not run | a device or an emulator image |
| 2 | No Gradle / Compose / AndroidX | Maven Central, Google Maven and the Gradle distribution are TLS-blocked | the client uses framework Views (ADR-011); the brief's multi-module layout is collapsed into one module with a package split | network access to the artifact hosts |
| 3 | No real LLM provider | no API key exists in this environment | every model call is an explicitly labelled `provider_mode=mock` placeholder | a provider credential |
| 4 | 9 of 12 research connectors are unreachable | the hosts are outside the TLS allowlist | those connectors report `inaccessible`; the other three are live | network access to those hosts |
| 5 | No server-side ASR/TTS | no `whisper.cpp` / `piper` binary is installable here | the server reports the capability as absent; the Android client uses the on-device engines | the engines, or the Android client only |
| 6 | No browser automation | no browser engine in this deployment | the capability reports `blocked` | a browser binary |
| 7 | No Docker | no Docker socket | the sandbox uses process isolation with rlimits instead of containers | a container runtime |
| 8 | No `zipalign` | the only reachable package ships a Windows binary | the APK is installed correctly but is not 4-byte aligned | a Linux build-tools package |

## 2. Not implemented (and reported as such)

| # | Limitation | Where it is reported |
|---|---|---|
| 9 | **Real model fine-tuning** — dataset preparation is real, but no training runtime exists | `GET /models/training` → `status: NOT_RUN` with the reason |
| 10 | Workflow **schedules** — the field is stored, but no scheduler fires it | `docs/WORKFLOW_ENGINE.md` §5 |
| 11 | OCR translation modality | `docs/TRANSLATION_ENGINE.md` §1 |
| 12 | Layout-preserving document translation | `docs/TRANSLATION_ENGINE.md` §1 |
| 13 | Automatic patch application by the self-repair loop — it proposes, a human applies | `docs/SELF_REPAIR.md` §3 |
| 14 | Automatic database-migration rollback | `docs/SELF_REPAIR.md` §3 |
| 15 | Scheduled database backups | `docs/DATABASE_SCHEMA.md`, `docs/DEPLOYMENT.md` |
| 16 | Malware scanning of uploads (hash + size checks only) | `docs/SECURITY_MODEL.md` §10 |
| 17 | Dependency scanning in CI | `docs/SECURITY_MODEL.md` §11 |
| 18 | Postgres row-level security (service-layer `org_id` filtering only) | `docs/DATABASE_SCHEMA.md` |
| 19 | Android instrumentation / UI tests (no device, no Robolectric) | `docs/ANDROID_CLIENT.md` §6 |
| 20 | Multi-worker deployment with the SQLite profile — the rate limiter, the WS broker and the sandbox supervisor are per-process | `docs/DEPLOYMENT.md` §3 |

## 3. Engineering trade-offs taken deliberately

| Decision | Why | Risk |
|---|---|---|
| SQLite as the default database | it runs and is verified here; the schema is portable | single-writer contention under load |
| Deterministic local 384-d embedder instead of a hosted embedding API | no provider key; a fake vector would be dishonest | lower semantic quality than a trained encoder |
| In-process rate limiter | no Redis available | not shared across workers |
| Native gateway instead of LiteLLM | keeps the dependency surface small and the routing logic auditable | fewer provider adapters than LiteLLM |
| `HMAC`-free, dependency-free JWT implementation | avoids one dependency and keeps the token format auditable | must be rotated and kept out of logs |

## 4. Quality caveats on the evidence

* The 38 acceptance tests run against a **SQLite** database and a **mock** model provider.
  They prove the plumbing, the contracts and the policy enforcement — not the quality of
  live LLM output.
* The research results are real (live GitHub/npm/PyPI data), but the **set of reachable
  sources** is a property of this host, not of the product.
* The APK has never been executed. Structural and cryptographic verification is not a
  substitute for a runtime test, and the difference is stated plainly.
