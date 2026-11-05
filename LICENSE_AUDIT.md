# License Audit

**Audit date:** 2026-11-04
**Scope:** initial technology candidates; this is an engineering audit, not legal advice.

## Evidence and decision policy

License metadata was retrieved through the GitHub REST API. Ambiguous entries were followed by retrieval of the repository license file. Exact dependency versions must be pinned and notices preserved. Copyleft and custom terms are not silently accepted.

| Project/package | Observed terms | TITAN decision |
|---|---|---|
| Hermes Agent | MIT, verified from `LICENSE` | Reference architecture; reuse requires copyright/permission notice |
| LangGraph, CrewAI, OpenAI Agents Python, OpenHands, browser-use, Temporal, llama.cpp, Ollama, Whisper, faster-whisper, Argos Translate, LM Evaluation Harness, Promptfoo | MIT per GitHub metadata | Permissive candidate; verify each transitive dependency before integration |
| Aider, Continue, Goose, Playwright, Selenium, mem0, Qdrant, vLLM, Transformers, PEFT, Axolotl, Haystack, Retrofit, OkHttp, Now in Android, Opik, asyncpg | Apache-2.0 per GitHub metadata | Permissive candidate with notice and patent terms |
| LiteLLM | MIT outside `enterprise/`; enterprise directory separately licensed | Core-only candidate; do not copy enterprise code |
| Tabby | Apache-2.0 outside `ee/` | Core-only candidate |
| Langfuse | MIT Expat outside listed enterprise directories | Core-only candidate |
| MCP servers repository | Transition: new code/spec Apache-2.0; docs CC-BY-4.0; some legacy MIT | Check license per copied file/version |
| pgvector | PostgreSQL-style permissive license | Candidate for production vector extension |
| Open WebUI | Custom Open WebUI license | Legal review required; not a first-increment dependency |
| Dify | Modified Apache with multi-tenant/branding conditions | Not selected; restrictions conflict with unconstrained multi-tenant deployment |
| n8n | Sustainable Use License plus enterprise restrictions | Source-available, not treated as OSI-open; not selected |
| Flowise | Apache core/commercial enterprise split; repository archived | Not selected |
| Piper (`OHF-Voice/piper1-gpl`) | GPL-3.0 | External-process evaluation only; no linking/distribution without compliance review |
| LibreTranslate | AGPL-3.0 | External service candidate only after network/deployment compliance review |
| Claude Code | “All rights reserved”; Anthropic terms | Proprietary; no source reuse and no open-source claim |
| FastAPI, Pydantic, Pydantic Settings, SQLAlchemy, pytest | MIT per PyPI metadata | Selected for first backend increment |
| Uvicorn | BSD-3-Clause | Selected |
| HTTPX, aiosqlite | PyPI expression absent; package license text/classifiers require lock-time review | Development candidates, not yet distribution-approved |
| python-multipart | Apache-2.0 | Candidate only if upload support is enabled |
| NumPy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Optional; not required in first increment |
| scikit-learn | BSD-3-Clause | Optional; not required in first increment |

## Required release controls

1. Generate an exact dependency lock/SBOM for every distributable artifact.
2. Review direct and transitive licenses again at lock time; metadata alone is insufficient.
3. Include all required copyright, license, NOTICE, and attribution texts.
4. Keep GPL/AGPL components isolated until distribution and source-offer obligations are reviewed.
5. Reject unlicensed code snippets and unknown model/dataset licenses.
6. Record model weights, voices, datasets, fonts, icons, and connectors separately from code licenses.

## Current audit status

`PARTIAL — candidate audit completed; final distributable dependency and asset audit is blocked until implementation and an Android/backend release lock exist.`
