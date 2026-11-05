# Environment Audit — Phase 0

**Audit time:** 2026-11-04 (UTC)
**Branch:** `arena/b772eb4c-baby`
**Starting commit:** `fbcdf75f5110a8dcd1b071de02365e2f0d1715a2`

## Repository

- `/home/user/baby` is a valid Git checkout on the required session branch.
- Initial tracked content was only `instagram_2fa_automation.js` (135,498 bytes). It is unrelated to TITAN and is preserved unchanged.
- No pre-existing TITAN backend, Android project, package manifest, tests, migrations, or build configuration existed.
- Approximately 20 GB disk space was available at audit time.

## Verified tools

| Capability | Observed state |
|---|---|
| Python | `/usr/bin/python3`, Python 3.11.2 |
| pip | Available; initially pip 23.0.1 |
| Node / npm / npx | Node 22.22.3, npm 10.9.8 |
| Git / GitHub CLI | Git 2.39.5, gh 2.23.0; authenticated GitHub API queries succeeded |
| Network | GitHub API, PyPI and npm registry returned HTTP 200 |
| Java / javac | **NOT FOUND** |
| Gradle / Kotlin CLI | **NOT FOUND** |
| Android SDK / sdkmanager / adb | **NOT FOUND**; `ANDROID_HOME` and `ANDROID_SDK_ROOT` unset |
| Docker | **NOT FOUND** |
| PostgreSQL client/server | **NOT FOUND** |
| Redis server | **NOT FOUND** |

## Credentials and external services

Only presence was inspected; secret values were never printed or written to reports.

- GitHub authentication: available through the configured environment.
- OpenAI, Anthropic, Gemini/Google, Groq, Hugging Face credentials: unset.
- `DATABASE_URL` and `REDIS_URL`: unset.
- No Android device or emulator was detected because `adb` is absent.

## Sandbox outbound boundary

The shell environment documents outbound access only to GitHub/codeload/API GitHub, PyPI/files.pythonhosted.org and npm. Web research tools can discover public pages, but that is not equivalent to authenticated connector access or runtime network permission from the deployed backend.

## Build consequences

- Backend development and tests: **AVAILABLE** with locally installed Python dependencies.
- Native Android source authoring: **AVAILABLE**.
- Android compilation/APK generation: **BLOCKED** by missing JDK, Gradle/Android SDK and packages.
- APK installation and launch verification: **BLOCKED** by missing SDK/adb/device.
- Production PostgreSQL/Redis integration tests: **BLOCKED** locally; local development may explicitly use SQLite and in-process workers without claiming production parity.
- Real hosted model inference: **BLOCKED** until server-side credentials and network policy are supplied.
- Real social platform connectors: **BLOCKED/PARTIAL** per official API credentials and terms; public search results must not be represented as direct platform ingestion.

## Security observations

The unrelated initial script contains Instagram credential/session automation code. It was not executed, integrated, or trusted as TITAN code. Secrets must remain server-side and excluded from source and Android resources.

## Audit status

`COMPLETE for the current sandbox. This is not a production infrastructure certification.`
