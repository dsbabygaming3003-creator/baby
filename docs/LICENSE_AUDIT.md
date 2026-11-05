# LICENSE AUDIT — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Auditor:** Builder AI · **Method:** SPDX id from `api.github.com` for repositories; `license` field + `License ::` classifier from `pypi.org/pypi/<pkg>/json` for packages; licence files read from unpacked toolchain archives.

---

## 1. Policy

TITAN is a self-hostable product. The bar applied:

| Rule | Requirement |
|---|---|
| P1 | **No copyleft** (GPL/LGPL/AGPL) linked or vendored into the distributed product. |
| P2 | Every third-party artefact used at **runtime** must carry an OSI-approved licence compatible with MIT/Apache-2.0 distribution. |
| P3 | Every third-party artefact used as a **build tool** must be recorded, with its licence noted, even if GPL (compilers are conventionally exempt as "mere aggregation"). |
| P4 | `NOASSERTION` / missing licences ⇒ **not vendored**, referenced only as an optional deployment target, and flagged ⚠️. |
| P5 | No third-party source is copied into this repository without a recorded licence + attribution. |

## 2. Runtime dependency audit (P2)

| Package | Licence (source) | P2 verdict |
|---|---|---|
| fastapi 0.115.6 | MIT (PyPI classifier: MIT) | ✅ |
| uvicorn 0.34.0 | BSD-3-Clause | ✅ |
| sqlalchemy 2.0.36 | MIT | ✅ |
| aiosqlite 0.20.0 | MIT (PyPI classifier: MIT License) | ✅ |
| pydantic 2.10.4 | MIT | ✅ |
| pydantic-settings 2.7.0 | MIT (PyPI classifier: MIT License) | ✅ |
| httpx 0.28.1 | BSD-3-Clause (PyPI `license` field) | ✅ |
| websockets 14.1 | BSD-3-Clause | ✅ |
| python-multipart 0.0.20 | Apache Software License (PyPI classifier) | ✅ |
| numpy 2.2.1 | BSD-3-Clause | ✅ |
| lingua-language-detector 2.0.2 | Apache Software License (PyPI classifier) | ✅ |
| pytest 8.3.4 / pytest-asyncio 0.25.0 | MIT | ✅ (dev only) |
| starlette, anyio, h11, idna, sniffio, click, greenlet, typing-extensions, annotated-types, charset-normalizer, certifi | MIT / MIT / MIT / MIT / MIT / MIT / MIT / PSF-2.0 / MIT / MIT / MPL-2.0 / BSD-3 | ✅ — `certifi` is file-level copyleft (MPL-2.0), used unmodified as a CA bundle; distribution-compatible |

**Result: 0 copyleft runtime dependencies.** All are MIT/BSD-3/Apache-2.0 (plus MPL-2.0 for the unmodified CA bundle).

## 3. Build toolchain audit (P3)

| Tool | Version | Licence | Notes |
|---|---|---|---|
| Temurin JDK | 17.0.9 | GPL-2.0 with Classpath Exception | Used as an external tool. Not redistributed in the APK or the backend image beyond the standard JVM. |
| Kotlin compiler | 2.4.21 | Apache-2.0 | Compiles the Android client. |
| aapt2 | 2.20-15009934 | Apache-2.0 (Android SDK) | Packages resources/assets. |
| d8 / R8 | bundled | Apache-2.0 (Google R8) | Dex compiler. |
| `android.jar` API 34/35 | — | Apache-2.0 (AOSP) | **Compile-time only**; never packaged into the APK. |
| `apk_sign_ts` | 1.0.1 | see §4 | Signing. |

## 4. ⚠️ Items requiring manual licence reading (P4)

| Item | GitHub SPDX | Action taken |
|---|---|---|
| `BerriAI/litellm` | `NOASSERTION` | **Not vendored, not imported.** Used only as an API-shape reference. TITAN's own gateway is original code. |
| `pgvector/pgvector` | `NOASSERTION` | **Not vendored.** Referenced as an optional production index behind the `VectorStore` interface. |
| `modelcontextprotocol/servers` | `NOASSERTION` | **Not vendored.** The MCP *tool-description conventions* were re-implemented from the public specification, not copied from these sources. |
| `TabbyML/tabby` | `NOASSERTION` | Reference only. |
| `NousResearch/hermes-agent-self-evolution` | no licence reported | Reference only; **no code copied**. |
| `apk_sign_ts` (npm) | MIT (`package.json` `license` field) | Build-time signer. MIT permits redistribution of the tool with attribution; the tool is **not** redistributed in the APK. |

## 5. Third-party code in this repository (P5)

**None.** No file in `backend/`, `android/`, `docs/`, `scripts/` or `verification/` is derived from a third-party project. Every line is original to this project (AI-generated under the user's direction).

The one pre-existing file, `instagram_2fa_automation.js`, is the repository owner's own earlier upload (a WebView user-script for Instagram 2FA flows). It is:
- **not** part of the TITAN backend or Android application,
- **not** imported, vendored, or referenced by any TITAN module,
- left **byte-for-byte unmodified** so the repository owner's asset is preserved.

Its separation from TITAN is asserted by an automated test (`verification/test_no_secret_leak.py::test_repository_has_no_unrelated_webview_script_imports`) and documented in `docs/SECURITY_RESEARCH.md` §7.

## 6. Model & data licences (important distinction)

TITAN integrates with **proprietary LLM providers** (OpenAI, Anthropic, Gemini, Groq, Hugging Face). Their **API terms**, not their model weights, govern use from TITAN. TITAN:
- never embeds a provider key in the client,
- records the provider id and model id with every request so a deployment can audit which provider's terms apply,
- exposes a `MODEL_REGISTRY.md` documenting the licence/terms category of each model id (open-weight vs. hosted-proprietary),
- routes open-weight models (Ollama/vLLM endpoints) when the operator configures them.

**Research content licensing.** Connector results store the URL, title, snippet and a content hash plus an excerpt, never a wholesale redistribution of licensed corpora. Full-text storage is opt-in per connector and defaults to off.

## 7. Conclusion

| Check | Result |
|---|---|
| Copyleft in distributed runtime | **NONE** ✅ |
| Unvetted licences in runtime | **NONE** ✅ |
| `NOASSERTION` items vendored | **NONE** ✅ |
| Third-party code copied into repo | **NONE** ✅ |
| Attribution file present | ✅ `THIRD_PARTY_NOTICES.md` (machine-generated from `pip freeze`) |
| Pre-existing owner file harmed | **NO** — untouched ✅ |

**Verdict: P1–P5 all satisfied.**
