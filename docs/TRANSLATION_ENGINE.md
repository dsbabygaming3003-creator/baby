# UNIVERSAL TRANSLATION ENGINE

`services/media.py::TranslationService`.

---

## 1. Modality coverage — honest status

| Modality | State | Notes |
|---|---|---|
| text | **available** | detection + translation + glossary |
| conversation | **partial** | per-turn translation with history is supported by the API; the client sends each turn separately |
| document | **partial** | documents are translated as text; no layout-preserving document renderer ships |
| OCR | **not implemented** | no OCR engine is installed on the server; the Android client can capture an image but the server cannot read it here |
| audio | **not implemented** | no server-side ASR engine (`whisper.cpp`) is installed — see `docs/VOICE_STUDIO.md` |
| subtitle | **partial** | subtitle text is translated as text; no SRT/VTT writer ships |

Unsupported modalities are **rejected with an explicit message**, never silently faked.

---

## 2. Detection

`POST /translation/detect`

```json
{"text": "আজকের অবস্থা সংক্ষেপে বলুন।"}
→ {"language": "bn", "confidence": 0.85, "method": "script-heuristic"}
```

Two detectors are combined:

* `lingua-language-detector` (installed, statistical), and
* a **Unicode script heuristic** for Bengali (`ঀ-৿`) and other Brahmic scripts, which is
  what actually fires on short Bengali sentences where the statistical model is unsure.

The `method` field states which one decided. Bengali detection is verified by AT-31.

---

## 3. Translation

`POST /translation` with `{text, target, source?, glossary?}`.

* The target must be in `SUPPORTED_LANGUAGES`; otherwise the call fails with the list of
  supported languages (never a silent fallback).
* The prompt asks the model to preserve code identifiers, product names, numbers and units
  verbatim.
* A **glossary** is injected as "preserve these terms verbatim: x → y, …".
* The response always carries `provider_mode`. Without a configured provider the result is
  the labelled mock placeholder (AT-31 shows `provider_mode=mock`,
  `model=mock:gemini-3.5-flash`).

---

## 4. Term preservation

Terms are preserved through three mechanisms:

1. the glossary parameter (explicit, caller-supplied);
2. the "preserve identifiers verbatim" instruction in the system prompt;
3. the identity fast-path — a source and target that match return the input unchanged
   without a model call.

---

## 5. History

Chat messages carry their detected language and the translation used, so the conversation
history in the client shows the original and the translation side by side. The
`conversation` memory scope stores the preferred language per conversation.

---

## 6. Bengali quality

Bengali is a first-class path: script heuristics for detection, `bn` in the supported
language list, and the Android client requesting `bn-IN` from the platform speech engines.
**Bengali *output* quality cannot be verified here** — that needs a live model provider —
so it is stated as a capability of the pipeline rather than a verified quality claim.
