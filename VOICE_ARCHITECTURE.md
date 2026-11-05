# Voice Architecture

Voice has separate web and Android routes and is not disguised as text chat.

## Web client

Explicit microphone button calls `getUserMedia`; an `AnalyserNode` draws waveform from actual time-domain audio amplitude. Stop closes tracks/AudioContext. Browser SpeechRecognition produces a transcript and SpeechSynthesis speaks it. Support is probed and displayed. The screen does not upload audio; browser-vendor recognition privacy remains the user's/browser's boundary.

## Android client

Runtime `RECORD_AUDIO` permission precedes SpeechRecognizer. Partial/final transcript and errors are visible. `onRmsChanged` displays actual input dB. TextToSpeech checks locale availability, including Bengali, and can be stopped. Release cleartext is disabled.

## Backend status

`GET /api/v1/voice/status` truthfully reports backend ASR/TTS `not_implemented`. No Whisper/Piper model, streaming voice pipeline, VAD/barge-in, voice registry or Bengali quality benchmark is configured. Device/browser support does not prove backend voice capability. Device instrumentation and microphone tests remain blocked without SDK/device.
