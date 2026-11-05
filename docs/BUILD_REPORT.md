# TITAN OMEGA INFINITY V18 — BUILD REPORT

**Build host:** Debian 12, x86_64, 2 CPUs, 3.8 GiB RAM, Linux 5.10 (containerised)
**Date:** 2026-11-05
**Builder:** `android/tools/build_apk.sh` (fully offline, no Gradle)

---

## 1. Result

| Item | Value |
|---|---|
| Release APK | `android/build/outputs/apk/titan-omega-release.apk` |
| Release size | **721,391 bytes** |
| Release SHA-256 | `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` |
| Debug APK | `android/build/outputs/apk/titan-omega-debug.apk` |
| Debug size | **721,397 bytes** |
| Debug SHA-256 | `a5f3281bc6745957fa97b1ec404354b463013b17c62d2b1b179ad3c902da396f` |
| Variant | release / debug |
| Package name | `titan.omega.infinity` |
| versionName / versionCode | `18.0.0` / `18` |
| minSdkVersion / targetSdkVersion | 24 / 35 |
| compileSdkVersion | 35 (Android 15) |
| Permissions | `INTERNET`, `ACCESS_NETWORK_STATE`, `RECORD_AUDIO` |
| Signature schemes | **v1 (JAR) + v2 + v3** — all verified |
| Certificate | CN=TITAN Omega Infinity, OU=TITAN, O=TITAN, L=Dhaka, C=BD (self-signed, RSA 2048, 10 000 days) |

---

## 2. Pipeline actually executed

```
1/6  aapt2 compile   res/                     -> flat resource files
2/6  aapt2 link      + AndroidManifest.xml     -> base.apk (resources.arsc + manifest)
3/6  kotlinc         9 Kotlin sources         -> build/manual/classes (CLEAN, 0 errors)
4/6  zip             classes/                 -> app-classes.jar
5/6  d8              app-classes.jar + stdlib -> classes.dex (2,395,860 B, DEX 037)
6/6  zip             base.apk + classes.dex   -> unsigned.apk
     apksigner       v1 + v2 + v3             -> titan-omega-<variant>.apk
     apksigner verify --min-sdk-version 21 --verbose   -> Verifies
```

### Toolchain used (all fetched from the host's TLS allowlist)

| Tool | Version | Source |
|---|---|---|
| `aapt2` | 2.20 build (Google binary) | npm `aaptjs3@2.0.2` |
| Kotlin compiler | 2.4.21 | npm `kotlin-compiler@2.4.21` |
| JDK | Temurin JRE 17.0.9 | PyPI `jdk4py==17.0.9.2` |
| **D8 / R8** | **8.2.2-dev (build facedf41bbd28b563d1e9e09c5f72d7c5ca598d5)** | npm `@drxiaozhi/minapk@0.5.1` |
| **apksigner** | **0.9** | npm `@drxiaozhi/minapk@0.5.1` |
| `android.jar` | API 35 + API 34 | github `Sable/android-platforms` (plain git mirror) |
| `keytool` | Temurin 17 | jdk4py wheel (ships `keytool`) |

### Failure encountered and resolved

| Attempt | Failure | Root cause | Fix |
|---|---|---|---|
| 1 | `ClassNotFoundException: com.android.tools.r8.D8` | the npm `d8-termux` package's `d8.jar` is an **Android-native binary**, not a Java archive | sourced a real Java D8 from `@drxiaozhi/minapk` |
| 2 | `com.android.tools.r8.internal.Sb: Unsupported source file type` | D8 was pointed at a loose **directory** of `.class` files | pack `classes/` into `app-classes.jar` first, then dex |
| 3 | `is-a-minkey/Html-to-apk` `server/tools/d8.jar` unusable | the committed file is a 404 **stub**, not a jar | discarded |
| 4 | `VMahajan10/UVA-…-Research` `android-sdk/**` unusable | every binary is a **Git LFS pointer** (133 bytes) | discarded |
| 5 | `joshuapetersen/Sarah-John-Genesis` `r8.jar` | the git blob is an **LFS pointer**; `media.githubusercontent.com` is TLS-blocked on this host | discarded |

The fix that worked: **D8 needs a jar, not a directory.** Verified by the successful
`D8 8.2.2-dev --version` banner and a valid DEX 037 header in the produced APK.

---

## 3. Artifact verification (independent of the build)

```
$ apksigner verify --min-sdk-version 21 --verbose titan-omega-release.apk
Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
```

```
$ unzip -l titan-omega-release.apk
     3160  AndroidManifest.xml
      980  res/drawable/ic_launcher.xml
      588  resources.arsc
  2395860  classes.dex
      512  META-INF/ANDROIDD.SF
     1334  META-INF/ANDROIDD.RSA
      385  META-INF/MANIFEST.MF
```

```
$ python3 -c "…struct.unpack_from('<I', dex, 0x38)…"
dex bytes: 2395860   magic: b'dex\n037\x00'
string_ids: 12961   type_ids: 1553   method_ids: 1767   class_defs: 1211
```

```
$ aapt2 dump badging titan-omega-release.apk
package: name='titan.omega.infinity' versionCode='18' versionName='18.0.0'
          platformBuildVersionName='15' compileSdkVersion='35' compileSdkVersionCodename='15'
sdkVersion:'24'
targetSdkVersion:'35'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.ACCESS_NETWORK_STATE'
uses-permission: name='android.permission.RECORD_AUDIO'
```

The DEX contains **1 211 classes** — the 7 screens, the API layer, the UI token layer and
the Kotlin standard library.

---

## 3b. Published download

GitHub release-asset uploads are unreachable from this build host (`uploads.github.com`
is outside the TLS allowlist), so the signed APKs are published in the repository
instead:

| File | Size | SHA-256 |
|---|---|---|
| `releases/titan-omega-release.apk` | 721,391 B | `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` |
| `releases/titan-omega-debug.apk` | 721,397 B | `a5f3281bc6745957fa97b1ec404354b463013b17c62d2b1b179ad3c902da396f` |
| `releases/SHA256SUMS.txt` | — | checksums for post-download verification |

Download URL:
`https://github.com/dsbabygaming3003-creator/baby/raw/arena/3045e0c0-baby/releases/titan-omega-release.apk`

**End-to-end delivery verified:** the copy re-fetched from GitHub has a byte-identical
git blob (`5d485446b5ed8fc2b157f121a65c922612621eee`), the same SHA-256, and passes
`apksigner verify` (v1 + v2 + v3) on the *downloaded* file — not only on the local build.

---

## 4. Installation / launch verification — BLOCKED

| Step | Status | Reason |
|---|---|---|
| Build APK | **PASS** | see above |
| Sign APK | **PASS** | v1 + v2 + v3 verified |
| Structural validation | **PASS** | manifest, resources.arsc, valid DEX |
| `adb install` | **BLOCKED** | no `adb` binary, no USB device, no emulator on this host |
| Launch on device | **BLOCKED** | same |
| Runtime smoke on device | **BLOCKED** | same |

**The exact blocker:** the build host has no Android device, no `adb`, no emulator binary and
no system image, and `dl.google.com` / `developer.android.com` are blocked by the host's TLS
allowlist, so a system image cannot be downloaded either. This is reported as **BLOCKED**
rather than being papered over with a fake install log.

To perform the missing verification on a machine that has a device:

```bash
adb install -r android/build/outputs/apk/titan-omega-release.apk
adb shell am start -n titan.omega.infinity/.MainActivity
adb shell pm list packages | grep titan.omega.infinity
adb logcat -d | grep -i titan
```

---

## 5. Secrets audit of the artifact

| Check | Result |
|---|---|
| Any provider API key string in the APK | **none** |
| Any `sk-` / `AIza` / Anthropic key pattern in the APK | **none** |
| Server base URL baked in | **none** — the client is pointed at a host by the user at runtime |
| User token storage | `SharedPreferences` (device-local), never in the APK |

The key never exists in the client: provider credentials live in the backend
`SecretStore` and are only ever reported as booleans through `/security/summary`.
