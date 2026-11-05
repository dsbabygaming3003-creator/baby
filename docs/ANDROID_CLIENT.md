# ANDROID CLIENT

Kotlin, mobile-first, seven screens, **no third-party UI framework**.

---

## 1. Why not Compose?

The build host's TLS egress allowlist excludes Maven Central, Google Maven and the Gradle
distribution. Jetpack Compose and every AndroidX artifact live behind those hosts, so they
could not be fetched, resolved or compiled here. Shipping a Compose build that was never
compiled would violate the anti-fake contract.

The client therefore uses **framework Views** with a hand-rolled design system
(`ui/Ui.kt`: tokens, cards, buttons, inputs, status colours, spacing). The decision is
recorded as ADR-011 and is listed in `docs/KNOWN_LIMITATIONS.md` as the one deliberate
architectural deviation.

Everything else in the brief is implemented: MVVM-style state holders, coroutines, a
navigation host, a repository layer, DataStore-equivalent persistence
(`SharedPreferences`), and an OkHttp-equivalent HTTP layer (`HttpURLConnection` +
`HttpURLConnection`-based SSE).

---

## 2. Module layout

```
android/app/src/main/
  AndroidManifest.xml
  res/drawable/ic_launcher.xml
  java/titan/omega/infinity/
    MainActivity.kt        navigation host, bottom bar, auth gate
    net/Api.kt             HTTP + SSE client, token store
    ui/Ui.kt               design tokens and reusable widgets
    screens/
      HomeScreen.kt        health, capabilities, tiles
      ChatScreen.kt        conversations, SSE streaming
      VoiceScreen.kt       capture, waveform, STT, TTS
      OtherScreens.kt      AgentsScreen, ResearchScreen, WorkspaceScreen, MoreScreen
```

The brief's modular split (`app`, `core`, `core-ui`, `core-network`, `core-database`,
`core-security`, `core-common`, `feature-*`) is **not** reproduced as separate Gradle
modules, because multi-module Gradle cannot be built here. The package split
(`net/`, `ui/`, `screens/`) mirrors the same separation of concerns inside one module.

---

## 3. Navigation

| Primary tab | Screen | Secondary entry points |
|---|---|---|
| Home | `HomeScreen` | capability detail, agent list, research centre |
| Chat | `ChatScreen` | conversation history, streaming reply |
| Voice | `VoiceScreen` | live transcript, waveform, playback |
| Agents | `AgentsScreen` | agent detail dialog, dynamic agent factory |
| Research | `ResearchScreen` | connector chips, task runner, history |
| Workspace | `WorkspaceScreen` | projects, terminal, builds |
| More | `MoreScreen` | models/providers, skills, workflows, memory, security |

`MoreScreen` hosts five tabs: **Models**, **Skills**, **Workflows**, **Memory** and
**Security** — the secondary surfaces from the brief.

---

## 4. Networking

`net/Api.kt`:

* `HttpURLConnection` with a 30 s timeout, JSON bodies via `org.json`;
* `Authorization: Bearer <token>` added when a token is stored;
* **SSE** parsing for `/api/v1/chat/stream` — the client reads the event stream line by
  line and appends tokens to the bubble as they arrive;
* the bearer token is stored in `SharedPreferences` and cleared on sign-out;
* **no provider credential is ever present in the client.**

---

## 5. Build

```bash
cd android && bash tools/build_apk.sh --release
```

Output: `android/build/outputs/apk/titan-omega-release.apk` — 721,391 bytes, signed
v1 + v2 + v3. Full detail in `docs/BUILD_REPORT.md`.

---

## 6. Verification status

| Check | Result |
|---|---|
| Kotlin compilation | **clean** — `kotlinc` over all 9 sources, 0 errors |
| APK build | **pass** — real D8 dexing, real apksigner |
| APK structure + signature | **verified** (AT-38) |
| Install on a device | **BLOCKED** — no emulator/adb on this host |
| Launch + runtime UX | **BLOCKED** — same reason |
| Screen-level instrumentation tests | **not implemented** — no device or Robolectric available |
