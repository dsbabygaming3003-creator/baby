# Build Report

## Backend development build

- Python dependencies installed successfully into `.venv`.
- Ruff: PASS.
- 14 tests: PASS.
- JavaScript syntax: PASS.
- Alembic migrations: upgrade/downgrade/re-upgrade and `check`: PASS on SQLite.
- Live Uvicorn launch: PASS on `0.0.0.0:8000`.
- Docker/PostgreSQL image/deployment: NOT RUN (Docker absent).

## Python project build service

Automated test first confirmed a manifest-less project returns `blocked`, then added `pyproject.toml` and ran real `python3 -m compileall -q .` successfully. This is bytecode validation, not a release binary.

## Android release

| Field | Result |
|---|---|
| Source | `android/` present |
| Build variant | debug/release configured in Gradle, neither built |
| Version | 0.1.0, versionCode 1 |
| APK | **NOT GENERATED** |
| APK size/hash | N/A — no artifact |
| Install verification | BLOCKED — adb/device absent |
| Launch verification | BLOCKED |
| Blocker | `java`, `javac`, `gradle`, `sdkmanager`, `adb` not found; SDK environment unset |

No APK link or success claim is provided. Next exact build action is to provision JDK 17 + Android SDK 36 + pinned Gradle, resolve/lock dependencies, then run clean build/lint/tests and verify the resulting artifact hash/install/launch.
