# TITAN OMEGA INFINITY V18 — Android downloads

Signed, installable APKs for the TITAN Android client.

| File | Size | SHA-256 | Signature |
|---|---|---|---|
| `titan-omega-release.apk` | 721,391 B | `297a7ee120057b863b89b5812ae5c75694263430f793d1db2750ee40491b0a67` | v1 + v2 + v3 |
| `titan-omega-debug.apk` | 721,397 B | `a5f3281bc6745957fa97b1ec404354b463013b17c62d2b1b179ad3c902da396f` | v1 + v2 + v3 |

Verify after downloading:

```bash
sha256sum -c SHA256SUMS.txt
```

Package `titan.omega.infinity` · version `18.0.0` (versionCode 18) · minSdk 24 · targetSdk 35.

---

## Install on Android

1. Download `titan-omega-release.apk` (use the release build unless you are debugging).
2. Open it. Android will ask you to allow **install from unknown sources** for the app you
   downloaded it with (Chrome or your file manager) — grant it, then continue.
3. Launch **TITAN Omega Infinity**.
4. Point the app at your TITAN backend (host + port, default `http://10.0.2.2:8000/api/v1`
   for the standard Android emulator, or your machine's LAN IP for a physical device) and
   register an account.

## Permissions requested

| Permission | Why |
|---|---|
| `INTERNET` | talking to the TITAN backend |
| `ACCESS_NETWORK_STATE` | connection status before a request |
| `RECORD_AUDIO` | the Voice Studio (microphone capture, live waveform, speech recognition) |

The microphone is only opened after you grant the permission at runtime.

## There is no API key inside the APK

Provider credentials live only on the backend (`SecretStore`). The APK contains no
`sk-`, `AIza` or `ANTHROPIC` key pattern — verified by scanning `classes.dex`
(see `docs/BUILD_REPORT.md` §5).

## Build it yourself instead

```bash
bash scripts/toolchain/setup_toolchain.sh
cd android && bash tools/build_apk.sh --release
```

The pipeline is fully offline: `aapt2 → kotlinc → d8 → zip → apksigner`.
Build details and the full verification log: `docs/BUILD_REPORT.md`.
