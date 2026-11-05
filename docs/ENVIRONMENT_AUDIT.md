# ENVIRONMENT AUDIT — TITAN OMEGA INFINITY V18

**Audit date:** 2026-11-04 (UTC)
**Audit method:** Direct inspection of the sandbox host (`e2b.local`), live network probes, live package registry probes, live GitHub REST API probes.
**Rule applied:** A capability is only reported as PRESENT if it was *executed and succeeded* during this audit. Everything else is reported as MISSING, BLOCKED or SUBSTITUTED, with the evidence that proves it.

---

## 1. Host & Runtime

| Property | Observed value | Verification |
|---|---|---|
| OS | Debian GNU/Linux 12 (bookworm) | `cat /etc/os-release` |
| Kernel | Linux 6.1.158 x86_64 | `uname -a` |
| CPUs | 2 logical cores | `nproc` |
| RAM | 3.8 GiB total, ~3.6 GiB available | `free -h` |
| Disk | 21 GiB total, 20 GiB available (`/`) | `df -h /home/user` |
| Swap | 0 (none) | `free -h` |
| User | uid=1001 `user`, groups include `sudo` | `id` |
| Passwordless sudo | **Yes** | `sudo -n true` → exit 0 |

## 2. Pre-existing Toolchain (as found)

| Tool | Found? | Evidence |
|---|---|---|
| `python3` | **YES** | 3.11.2 (`/usr/bin/python3`) |
| `pip3` | **YES** | 23.0.1 |
| `node` | **YES** | v22.22.3 (`/usr/local/bin/node`) |
| `npm` / `npx` / `yarn` | **YES** | npm 10.9.8 |
| `git` | **YES** | 2.39.5 |
| `gh` (GitHub CLI) | **YES** | 2.23.0, authenticated as `dsbabygaming3003-creator` via `GH_TOKEN` |
| `java` / `javac` | **NO** | `java -version` → `command not found` |
| `gradle` | **NO** | `which gradle` → empty |
| Android SDK (`ANDROID_HOME`) | **NO** | `ANDROID_HOME` and `ANDROID_SDK_ROOT` both empty; no `sdkmanager`/`adb`/`aapt2` |
| `docker` | **NO** | `which docker` → empty |
| `apt-get` | **YES** (binary) | but **USELESS** — see §3 |

## 3. Network Egress — The Single Most Constraining Fact

The sandbox enforces a **TLS-level egress allowlist**. A raw TCP connect to `:443` succeeds for many hosts (a transparent proxy answers), but the **TLS handshake is only completed for allowlisted hosts**. Every probe below was performed with `curl` (full TLS + HTTP), not a bare TCP test.

### 3.1 ALLOWLISTED (verified working — HTTP status codes shown)

| Host | Status | Note |
|---|---|---|
| `github.com` | 200 | git clone / web |
| `api.github.com` | 200 | REST + GraphQL API |
| `codeload.github.com` | 301→200 | **repository source archives** (tarball/zip) |
| `registry.npmjs.org` | 200 | npm packages |
| `pypi.org` | 200 | PyPI index |
| `files.pythonhosted.org` | (404 on root = served) | PyPI file CDN |

### 3.2 BLOCKED (TLS handshake fails — `SSL_ERROR_SYSCALL`)

`dl.google.com` · `maven.google.com` · `repo1.maven.org` · `repo.maven.apache.org` · `plugins.gradle.org` · `services.gradle.org` · `jitpack.io` · `maven.aliyun.com` · `mirrors.cloud.tencent.com` · `repo.huaweicloud.com` · `raw.githubusercontent.com` · `objects.githubusercontent.com` · `huggingface.co` · `arxiv.org` · `export.arxiv.org` · `api.openalex.org` · `api.crossref.org` · `www.reddit.com` · `youtube.com` · `developer.android.com` · `api.adoptium.net` · `cdn.azul.com` · `download.jetbrains.com` · `deb.debian.org` (HTTP :80 also blocked) · `archive.ubuntu.com` · `cdn.jsdelivr.net` · `unpkg.com` · `crates.io` · `static.rust-lang.org`

### 3.3 Consequence (drives every architecture decision in this project)

1. **No Gradle distribution** (`services.gradle.org` blocked) and **no Maven Central / Google Maven** (`repo1.maven.org`, `maven.google.com` blocked).
2. **Therefore `androidx.*`, `androidx.compose.*`, `kotlin-stdlib` from Maven and the Android Gradle Plugin are unobtainable.** Jetpack Compose cannot be compiled here — not "hard", *impossible*, because the runtime artifacts do not exist behind the firewall.
3. **No official Android SDK** (`dl.google.com` blocked) → no `sdkmanager`, no `build-tools`, no `platforms`.
4. `apt-get` cannot install `openjdk-17-jdk-headless` because Debian mirrors are HTTP :80 and blocked.

## 4. Toolchain Reconstruction (what was actually built, and how)

Because the standard installers are blocked, the toolchain was **rebuilt from allowlisted sources** and every component was **executed successfully** before use.

| Component | Source | Allowlisted host | Verified by |
|---|---|---|---|
| **JDK 17.0.9** (Temurin) | PyPI wheel `jdk4py==17.0.9.2` (JRE binaries) | `files.pythonhosted.org` | `java -version` → `openjdk version "17.0.9" 2023-10-17` |
| **Kotlin compiler 2.4.21** (+ `kotlin-stdlib.jar`, `compose-compiler-plugin.jar`) | npm `kotlin-compiler@2.4.21` | `registry.npmjs.org` | `kotlinc m.kt -include-runtime -d m.jar && java -jar m.jar` → `kotlin ok` |
| **aapt2 2.20-15009934** (Linux x64 binary) | npm `aaptjs3@2.0.2` → `bin/x64/linux/aapt2` | `registry.npmjs.org` | `aapt2 version` → `Android Asset Packaging Tool (aapt) 2.20-15009934` |
| **d8 / R8** (16.8 MB `d8.jar`) | npm `d8-termux@1.0.0` | `registry.npmjs.org` | `java -cp d8.jar com.android.tools.r8.D8 --version` → exit 0 |
| **android.jar (API 34 & 35)** (27.1 MB / 26.4 MB) | GitHub `Sable/android-platforms` via `codeload` | `codeload.github.com` | `unzip -l` → `android-35/android.jar`; used for `kotlinc -classpath` |
| **APK signer** (v1 JAR + v2/v3) | npm `apk_sign_ts@1.0.1` | `registry.npmjs.org` | signature block written into built APK (see `BUILD_REPORT.md`) |

Toolchain root: `/opt/titan/toolchain` (outside the repository so it is not captured in workspace snapshots).
Bootstrap script (committed for reproducibility): `scripts/toolchain/setup_toolchain.sh`.

> **`keytool` note:** the `jdk4py` wheel ships a JRE (no `javac`, no `jarsigner`), but it does include `keytool`, which is sufficient to generate the release keystore. Java compilation is performed by `kotlinc` (Kotlin-only sources), not `javac`.

## 5. Backend Runtime

| Item | Status |
|---|---|
| Python | 3.11.2 (system) |
| Virtualenv | `/opt/titan/venv` (Python 3.11) |
| Installed | `fastapi 0.115.6`, `uvicorn[standard] 0.34.0`, `sqlalchemy[asyncio] 2.0.36`, `aiosqlite 0.20.0`, `httpx 0.28.1`, `pydantic 2.10.4`, `pydantic-settings 2.7.0`, `python-multipart 0.0.20`, `numpy 2.2.1`, `websockets 14.1`, `lingua-language-detector 2.0.2`, `pytest 8.3.4`, `pytest-asyncio 0.25.0` |
| Import smoke test | `deps ok 0.115.6 2.0.36` ✅ |

**PostgreSQL / Redis are NOT present and CANNOT be installed** (no apt, no Docker). The database layer is therefore written against **SQLAlchemy 2.0 async** with a **SQLite (aiosqlite) default profile** and a **PostgreSQL profile** (`postgresql+asyncpg://`) selectable by one environment variable. Vector search uses a **NumPy cosine index persisted in SQLite**, with a Qdrant/pgvector adapter boundary defined for deployment where those services exist. This is an intentional, documented substitution — not a claim of "PostgreSQL deployed".

## 6. Repository State at Audit Time

```
/home/user/baby
└── instagram_2fa_automation.js   (135,498 bytes, 3,584 lines)
```

The repository contained **exactly one pre-existing file**: a WebView-automation user script for Instagram 2FA flows. It is **unrelated to TITAN** (it targets a WebView host, not an Android app framework) and contains no TITAN-relevant code. It is **left untouched and unmodified**; it is not imported, vendored or referenced by any TITAN module. See `docs/SECURITY_RESEARCH.md` §7 for the assessment of why it is excluded from the TITAN source tree.

`git log` at audit time: single commit `fbcdf75 "Add files via upload"` on `main`. Working branch for this session: `arena/3045e0c0-baby`.

## 7. Honest Capability Summary

| Capability | Status | Note |
|---|---|---|
| Android APK compilation | **AVAILABLE (reconstructed)** | aapt2 + kotlinc + d8 + signer, all executed successfully |
| Jetpack Compose | **BLOCKED** | `androidx.compose.*` artifacts are on blocked Maven/Google hosts |
| AndroidX (any) | **BLOCKED** | same |
| Gradle build | **BLOCKED** | no distribution reachable; a Gradle project layout is still shipped for portability |
| Device install / launch test | **BLOCKED** | no emulator, no `adb`, no KVM in this sandbox (see `BUILD_REPORT.md` §6) |
| Real HTTP research from the backend | **PARTIAL** | GitHub / PyPI / npm connectors are LIVE; all others report `INACCESSIBLE` with the TLS error preserved |
| LLM provider calls | **BLOCKED unless a key is supplied** | no provider host is allowlisted; the gateway implements real HTTP calls + a clearly-labelled `mock` provider |
| PostgreSQL / Redis / Qdrant / Docker | **NOT AVAILABLE** | SQLite + NumPy profile used; adapters documented |

Every one of these rows is reproduced in `docs/BUILD_REPORT.md`, `docs/TEST_REPORT.md` and in the live `/api/v1/system/capabilities` endpoint, which reports the same values from the running server rather than from a static document.
