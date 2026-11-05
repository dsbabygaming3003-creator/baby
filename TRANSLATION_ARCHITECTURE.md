# Translation Architecture

`POST /api/v1/translate` accepts text, source (`auto` allowed), target language and optional provider. A configured multilingual model receives a bounded system request to preserve technical terms and report unsupported cases. Response records provider/model/mock and language metadata.

The default mock explicitly performs **no translation** and returns `translation_verified=false`; the UI displays “NOT A VERIFIED TRANSLATION.” Therefore translation orchestration is implemented, but actual multilingual translation acceptance remains blocked until live provider evaluation.

## Planned extensions

Language detection, document/OCR/audio/subtitle pipelines, conversation mode, translation history and terminology glossary require separate implementations and tests. Argos Translate (MIT) and LibreTranslate (AGPL service) remain researched candidates, not integrated engines. Bengali and other low-resource language quality must be evaluated rather than inferred from a provider's general multilingual claim.
