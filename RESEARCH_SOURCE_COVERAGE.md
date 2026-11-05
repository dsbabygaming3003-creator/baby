# Research Source Coverage

**Research date:** 2026-11-04
**Verification rule:** a source is “verified” only when the named artifact was actually retrieved. Search-result discovery is recorded separately from direct repository/API inspection.

## Directly retrieved evidence

| Source | Coverage | Status | Evidence |
|---|---|---|---|
| GitHub REST API | 46 repositories: owner, description, license metadata, activity, latest release | VERIFIED | `docs/research/evidence/github_repositories.json` |
| GitHub Contents API | Hermes README/pyproject/root; selected license files including Claude Code | VERIFIED | `docs/research/evidence/source_inspection.json` |
| PyPI JSON API | 13 initial backend/test package candidates | VERIFIED | `docs/research/evidence/pypi_packages.json` |
| Google Gemini official documentation discovered through web research | `gemini-4-argon` model ID, documented availability and capabilities | DOCUMENTATION VERIFIED; LIVE ACCESS UNVERIFIED | https://ai.google.dev/gemini-api/docs/models/gemini-4-argon |
| Android Developers official documentation | Compose releases and modular Android direction | DOCUMENTATION VERIFIED | https://developer.android.com/jetpack/androidx/releases/compose |
| LiteLLM official documentation | Gateway keys, budgets, spend, retry/fallback | DOCUMENTATION VERIFIED | https://docs.litellm.ai/docs/simple_proxy |
| Temporal official documentation | Durable execution, activity retries and human approval | DOCUMENTATION VERIFIED | https://docs.temporal.io/evaluate/understanding-temporal |
| OWASP Cheat Sheet Series | Untrusted content, downstream authorization, action-specific approval | DOCUMENTATION VERIFIED | https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html |
| pgvector official repository/docs | Exact/HNSW/IVFFlat search and hybrid retrieval | VERIFIED | https://github.com/pgvector/pgvector |

## Platform coverage and limits

| Platform | Pre-build coverage | Verification status |
|---|---|---|
| GitHub | Direct public repository/API research | ACCESSED |
| GitLab, Codeberg, SourceHut, Bitbucket | No direct connector/session research performed | NOT ACCESSED |
| Hugging Face | Repositories hosted on GitHub inspected; Hub model/dataset API not queried | PARTIAL / HUB UNVERIFIED |
| Papers with Code | Not directly accessed | NOT ACCESSED |
| arXiv | Not directly queried in this increment | NOT ACCESSED |
| YouTube, TikTok, Facebook, Instagram, X | No direct API ingestion; no bypass attempted | NOT ACCESSED |
| Reddit, LinkedIn, Pinterest | Search discovery may surface public pages; no direct API ingestion | DISCOVERY ONLY / NOT CONNECTED |
| Public Discord / Telegram | No authenticated or public connector ingestion performed | NOT ACCESSED |
| Official developer/provider docs | Gemini, Android, LiteLLM, Temporal, OWASP and GitHub project docs | ACCESSED THROUGH RESEARCH TOOL |
| Technical blogs/developer forums | Used only as secondary discovery; not authoritative for licenses or capabilities | SECONDARY |
| Security advisories | No complete CVE/OSV scan performed | PARTIAL — RELEASE GATE |
| Standards organizations | MCP source/licensing inspected; no broad standards survey | PARTIAL |

## Important distinctions

- Public search snippets are not treated as source verification when an official repository or document is available.
- No private/restricted content or access-control bypass was attempted.
- Lack of coverage is explicitly retained rather than filled with invented findings.
- The runtime TITAN Research Engine is a separate product deliverable; these builder reports do not implement it.

## Coverage status

`PARTIAL but sufficient to make the documented first-increment architecture decisions. Broader social, paper, multi-forge and live-provider research remains open and must not be marked complete.`
