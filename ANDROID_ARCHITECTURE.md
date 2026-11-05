# Android Architecture

## Source modules

- `:app`: MainActivity, Compose routes, MVVM `TitanViewModel`, Android speech integration.
- `:core-network`: kotlinx-serialization DTOs, Retrofit API, OkHttp timeouts and repository.
- `:core-ui`: Graphite/Cyan Material 3 theme.

Presentation observes `StateFlow<TitanUiState>`; repository owns API operations; Retrofit owns transport. Debug uses `http://10.0.2.2:8000`; release requires an HTTPS base URL and disables cleartext. Only a backend URL is in BuildConfig—never provider credentials.

## Current routes

Home/system counts, Chat (non-streaming), Voice (permission + SpeechRecognizer/TextToSpeech), Agents and GitHub Research call real backend contracts. More explicitly identifies native routes not yet implemented rather than showing fake screens.

## Build status

**SOURCE ONLY / BUILD NOT VERIFIED.** The sandbox lacks Java, Gradle, Android SDK and adb. No Gradle wrapper JAR was fabricated. Plugin/library versions are candidates from research but cannot be marked compatible until resolved by a real build. Required next environment: JDK 17, Android SDK 36, Gradle, emulator/device; then lock versions, run lint/unit/instrumentation and generate a signed release.

Further feature modules (`feature-research`, `feature-workspace`, etc.), secure app authentication/session storage, attachment/voice streaming, offline cache and native navigation parity remain incomplete.
