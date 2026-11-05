# THIRD-PARTY NOTICES

TITAN OMEGA INFINITY V18 depends on the packages below. Each licence was verified
against the **pinned version** actually installed (PyPI JSON API for the exact release
and, where the metadata was ambiguous, the upstream repository via the GitHub API).

---

## 1. Python runtime dependencies

| Package | Version | Licence | Project |
|---|---|---|---|
| fastapi | 0.115.6 | MIT | tiangolo/fastapi |
| starlette | 0.41.3 | BSD-3-Clause | encode/starlette |
| uvicorn | 0.34.0 | BSD-3-Clause | encode/uvicorn |
| sqlalchemy | 2.0.36 | MIT | sqlalchemy/sqlalchemy |
| aiosqlite | 0.20.0 | MIT | python-aiosqlite |
| greenlet | 3.1.1 | MIT | python-greenlet |
| pydantic | 2.10.4 | MIT | pydantic/pydantic |
| pydantic-core | 2.27.2 | MIT | pydantic/pydantic-core |
| pydantic-settings | 2.7.0 | MIT | pydantic/pydantic-settings |
| annotated-types | 0.7.0 | MIT | annotated-types/annotated-types |
| typing-extensions | 4.12.2 | PSF-2.0 | python/typing_extensions |
| httpx | 0.28.1 | BSD-3-Clause | encode/httpx |
| httpcore | 1.0.7 | BSD-3-Clause | encode/httpcore |
| h11 | 0.14.0 | MIT | python-hyper/h11 |
| idna | 3.10 | BSD-3-Clause | kjd/idna |
| certifi | 2024.8.30 | MPL-2.0 | certifi/python-certifi |
| charset-normalizer | 3.4.0 | MIT | Ousmane1984/charset-normalizer |
| python-multipart | 0.0.20 | Apache-2.0 | Kludex/python-multipart |
| websockets | 14.1 | BSD-3-Clause | python-websockets/websockets |
| numpy | 2.2.1 | BSD-3-Clause | numpy/numpy |
| lingua-language-detector | 2.0.2 | Apache-2.0 | language-detection/lingua-language-detector |
| anyio | 4.16.0 | MIT | agronholm/anyio |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | python-trio/sniffio |
| click | 8.1.8 | BSD-3-Clause | pallets/click |
| pytest | 8.3.4 | MIT | pytest-dev/pytest |
| pytest-asyncio | 0.25.0 | Apache-2.0 | pytest-dev/pytest-asyncio |

## 2. Build-time tooling (not shipped in the APK, not imported at runtime)

| Tool | Version | Licence | Source |
|---|---|---|---|
| Kotlin compiler | 2.4.21 | Apache-2.0 | JetBrains (npm `kotlin-compiler`) |
| Google D8 / R8 | 8.2.2-dev | Apache-2.0 | Google (bundled in npm `@drxiaozhi/minapk`) |
| Google apksigner | 0.9 | Apache-2.0 | Google (bundled in npm `@drxiaozhi/minapk`) |
| Google aapt2 | 2.20 | Apache-2.0 | Google (bundled in npm `aaptjs3`) |
| Temurin JRE 17 | 17.0.9 | GPL-2.0 with Classpath Exception | Adoptium (via the PyPI `jdk4py` wheel) |
| apk_sign_ts | 1.0.1 | MIT | npm (fallback signer only) |
| android.jar (API 34/35) | — | Apache-2.0 | Android Open Source Project (via the `Sable/android-platforms` mirror) |

The Temurin JRE is a GPLv2-with-Classpath-Exception runtime used as a **build tool**. It is
not linked into, redistributed with, or shipped inside the APK. The licence permits this
use; the Classpath Exception additionally permits linking against it if that ever changes.

## 3. Licence verdict

* **No copyleft (GPL/AGPL) dependency is linked into the product.** The only GPL-family
  component is the Temurin JRE used at build time, under the Classpath Exception.
* **No dependency is vendored** — every package is installed from PyPI/npm, unmodified.
* **No third-party source code was copied into this repository.** The 20 agent contracts,
  the research pipeline, the gateway, the RAG stack, the workflow engine and the Android
  client are original work.
* `instagram_2fa_automation.js` in the repository root is a **pre-existing owner asset**.
  It is untouched by TITAN, is not part of this project's licence grant, and is excluded
  from the sources covered by `LICENSE`.

See `docs/LICENSE_AUDIT.md` for the full audit, including the Apache-2.0 obligations
(attribution + patent grant) that apply to `python-multipart`, `lingua-language-detector`
and `pytest-asyncio`.
