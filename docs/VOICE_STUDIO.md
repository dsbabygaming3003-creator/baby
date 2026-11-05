# LIVE VOICE STUDIO

A separate studio from Chat, with real capture, real amplitude, real playback.

---

## 1. Division of labour

| Layer | Responsibility | State on the server |
|---|---|---|
| Android client | microphone capture, waveform, barge-in, on-device STT/TTS | **implemented** (`AudioRecord`, `SpeechRecognizer`, `TextToSpeech`) |
| Backend | transcript storage, cloud ASR/TTS adapters, capability reporting | **adapters present, no engine installed** |

---

## 2. Client implementation

`android/.../screens/VoiceScreen.kt`:

| Feature | Implementation |
|---|---|
| Capture | `AudioRecord` with `MediaRecorder.AudioSource.MIC`, 16 kHz mono PCM |
| Permission gate | `RECORD_AUDIO` is requested at runtime; capture only starts when granted |
| Waveform | a custom `WaveformView` draws the **real** amplitude envelope read from the recorder buffer — not a synthetic animation |
| Live transcript | `SpeechRecognizer` with `RecognizerIntent.EXTRA_LANGUAGE = "bn-IN"`, partial results streamed into the transcript field |
| Playback | `TextToSpeech` with a Bengali `Locale("bn", "IN")`; the engine's availability is probed and reported |
| Barge-in | a new capture cancels the current playback and replaces the transcript |

`RECORD_AUDIO` is declared in the manifest and confirmed present in the built APK
(`uses-permission: name='android.permission.RECORD_AUDIO'`).

---

## 3. Server capability report

`GET /voice/capabilities`

```json
{"server": {"whisper_cpp_binary": false, "piper_binary": false, "cloud_providers": {}},
 "client": {"android_speech_recognizer": "provided by the platform (Android client)",
            "android_text_to_speech": "provided by the platform (Android client)",
            "bengali": "detected by the server's script heuristic; synthesis needs an engine"},
 "note": "A language is reported as supported only after a runtime probe succeeds."}
```

The server probes for `whisper.cpp` and `piper` binaries at request time and reports the
result. In this deployment both are **absent**, so the report says `false` — the platform
does not claim a speech engine it cannot run. `/system/capabilities` marks
`voice_asr_server` and `voice_tts_server` as **degraded** for the same reason.

Verified by AT-32.

---

## 4. Server adapters

`POST /voice/transcribe` and `POST /voice/speak` route to a local engine when one is
present and otherwise return a structured `unavailable` result with the reason. They never
return fabricated audio or fabricated transcripts.

---

## 5. Live transcript events

Transcripts and capture state are published on the `/ws/events` WebSocket, so a second
client (or a desktop view) can follow the live session.
