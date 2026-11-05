# BUILD GUIDE

How to reproduce the APK and the backend from a clean checkout.

---

## 0. Requirements

No Gradle, no Android Studio, no JDK download from Oracle/Adoptium, no `dl.google.com`.
Everything comes from the host's TLS allowlist:
`github.com`, `api.github.com`, `codeload.github.com`, `registry.npmjs.org`,
`pypi.org`, `files.pythonhosted.org`.

| Tool | Provided by |
|---|---|
| JRE 17 | PyPI `jdk4py` wheel (ships `java`, `keytool`) |
| aapt2 | npm `aaptjs3` (bundles the Google Linux binary) |
| Kotlin compiler | npm `kotlin-compiler` |
| D8 (dexer) | npm `@drxiaozhi/minapk` |
| apksigner | npm `@drxiaozhi/minapk` |
| android.jar | github `Sable/android-platforms` |
| Python deps | PyPI |

---

## 1. One-command bootstrap

```bash
bash scripts/toolchain/setup_toolchain.sh
```

It creates:

```
/opt/titan/toolchain/
  jdk/                    Temurin JRE 17.0.9 (java, keytool)
  build-tools/aapt2       Google aapt2
  build-tools/apksigner.jar
  d8/d8.jar               Google D8 / R8 8.2.2-dev
  platforms/android-35/android.jar
  platforms/android-34/android.jar
  kotlinc/                Kotlin 2.4.21
  apksigner/              apk_sign_ts@1.0.1 (JS fallback signer)
/opt/titan/venv/          backend virtualenv
```

> The JDK wheel unpacks to `java-runtime/`, **not** `jdk*/`. The script looks for
> `java-runtime` first — an earlier version of this script searched for `jdk*` and
> silently failed. Keep that order if you edit it.

---

## 2. Build the Android client

```bash
cd android
bash tools/build_apk.sh --release            # release variant
bash tools/build_apk.sh                      # debug variant
bash tools/build_apk.sh --release --out /tmp # alternative output directory
```

Output: `android/build/outputs/apk/titan-omega-<variant>.apk`

The script:

1. compiles `res/` with `aapt2 compile`;
2. links resources + `AndroidManifest.xml` with `aapt2 link`;
3. compiles the 9 Kotlin sources with `kotlinc` against `android-35/android.jar`;
4. packs `build/manual/classes` into `app-classes.jar` — **D8 rejects a directory**;
5. dexes with `D8 --lib android.jar --min-api 24 --release`;
6. zips the dex into the resource APK;
7. signs with `apksigner` (v1 + v2 + v3) using a `keytool`-generated keystore;
8. prints size, SHA-256, variant, version and `aapt2 dump badging`.

Keystores are generated on demand:

* `android/titan-release.jks` — alias `titan`, password from `$TITAN_KEY_PASSWORD`
  (default `titan-release-2026`);
* `android/titan-debug.jks` — alias `androiddebugkey`, password `android`.

Both are git-ignored. **A release keystore must never be committed.**

Manual Kotlin-only compile (useful while iterating):

```bash
export JAVA_HOME=/opt/titan/toolchain/jdk
export PATH=$JAVA_HOME/bin:$PATH
cd android
kotlinc $(find app/src/main/java -name '*.kt') \
  -classpath /opt/titan/toolchain/platforms/android-35/android.jar \
  -jvm-target 1.8 \
  -d build/manual/classes
```

---

## 3. Run the backend

```bash
cd backend
/opt/titan/venv/bin/python -m uvicorn titan.main:app --host 0.0.0.0 --port 8000
```

Environment variables that matter:

| Variable | Default | Meaning |
|---|---|---|
| `TITAN_DATABASE_URL` | `sqlite+aiosqlite:///data/titan.db` | Postgres-ready DSN |
| `TITAN_DATA_DIR` | `<repo>/data` | reports, artifacts, sandbox root |
| `TITAN_JWT_SECRET` | dev default | **change in production** |
| `TITAN_TOOLCHAIN_DIR` | `/opt/titan/toolchain` | where the Android toolchain lives |
| `TITAN_SANDBOX_ROOT` | `/tmp/titan-sandbox` | sandbox working root |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | unset | provider credentials (server side only) |

---

## 4. Verify

```bash
/opt/titan/venv/bin/python verification/smoke_test.py        # 40/40
/opt/titan/venv/bin/python verification/run_acceptance.py   # 38/38 -> docs/TEST_REPORT.md
```

---

## 5. What is deliberately absent

* **No `build.gradle`.** It could not be executed or verified on this host, and shipping an
  unverified build script would break the anti-fake contract. `android/tools/build_apk.sh`
  is the verified path.
* **No Compose / AndroidX.** Those artifacts live on Maven Central and Google Maven, both
  TLS-blocked here. The client uses framework Views (ADR-011).
* **No `zipalign`.** The npm package that carries it ships a Windows binary only. APK
  alignment is not required for installation; `apksigner` v2/v3 signing is applied and
  verified. `zipalign` should be added once a Linux build-tools package is reachable.
