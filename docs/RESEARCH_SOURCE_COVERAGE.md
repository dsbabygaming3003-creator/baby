# RESEARCH SOURCE COVERAGE — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04
**Scope:** Every external source the Builder AI consulted *before* implementation, plus the source classes the **TITAN internal research engine** will query at runtime.

Legend: ✅ reachable & used · ⚠️ reachable but unauthenticated/metadata-only · ⛔ network-blocked from the sandbox · 🔑 requires an API key not available here · 📚 documented from secondary sources only

---

## 1. Builder-AI source classes (pre-build phase)

| Platform / source class | Status in this environment | How it was used |
|---|---|---|
| GitHub REST API (`api.github.com`) | ✅ | Primary verification channel for every repository, licence, release tag, language mix and directory listing |
| GitHub repo source (`codeload.github.com`) | ✅ | Toolchain source for `android.jar`; source-of-truth reads for architecture claims |
| npm registry | ✅ | Toolchain acquisition (aapt2, d8, Kotlin compiler, APK signer); package-licence checks |
| PyPI index + file CDN | ✅ | Backend dependency set, licence verification, JDK acquisition |
| Web search (builder channel) | ✅ | Landscape discovery, secondary cross-checks |
| Web fetch (builder channel) | ✅ | Reading vendor docs / third-party comparisons |
| arXiv | ⛔ TLS blocked from sandbox | Listed as a **planned runtime connector**; verified only via secondary literature |
| Hugging Face | ⛔ TLS blocked | Planned connector + model catalog source |
| Reddit | ⛔ TLS blocked | Planned connector (public JSON) |
| YouTube | ⛔ TLS blocked | Planned connector (public RSS/oEmbed only, no scraping) |
| Stack Exchange API | ⛔ TLS blocked | Planned connector |
| OpenAlex / Crossref | ⛔ TLS blocked | Planned connectors for academic research |
| Developer/vendor documentation sites | ⛔ TLS blocked (direct), ✅ via builder fetch channel | Read through the builder fetch channel; cited in this report |
| Debian/Ubuntu package mirrors | ⛔ HTTP :80 blocked | Forced the toolchain reconstruction documented in `ENVIRONMENT_AUDIT.md` §4 |
| Maven Central / Google Maven | ⛔ TLS blocked | Forced Kotlin+framework-views Android client instead of Compose |

**Important honesty note:** the *builder* research channel can reach far more of the internet than the *runtime* sandbox can. The builder used that channel for design decisions; the **TITAN product's** own research engine can only reach what the runtime host can reach. The product therefore implements the connectors for every platform and **reports `INACCESSIBLE` at runtime for blocked ones**, instead of pretending to have read them. This distinction is exactly what the specification demands in §A5.

## 2. Runtime source classes the TITAN Research Engine implements

TITAN ships 12 versioned connector modules (`backend/titan/research/connectors/`). Each declares its own access policy, query adapter, normaliser and verification rules.

| Connector ID | Target | Auth | Runtime status in this sandbox | Verification |
|---|---|---|---|---|
| `github.v1` | GitHub repositories, code, issues, releases | optional PAT (public works anonymously) | ✅ **LIVE** | `api.github.com` reachable; real results returned |
| `pypi.v1` | Python packages & releases | none | ✅ **LIVE** | `pypi.org` reachable |
| `npm.v1` | npm packages | none | ✅ **LIVE** | `registry.npmjs.org` reachable |
| `arxiv.v1` | Papers | none | ⛔ INACCESSIBLE (TLS) | implemented, will work where reachable |
| `huggingface.v1` | Models & datasets | optional token | ⛔ INACCESSIBLE (TLS) | implemented |
| `stackexchange.v1` | Q&A sites | optional key (quota) | ⛔ INACCESSIBLE (TLS) | implemented |
| `reddit.v1` | Public subreddits | optional OAuth | ⛔ INACCESSIBLE (TLS) | implemented |
| `openalex.v1` | Scholarly works | polite pool mailto | ⛔ INACCESSIBLE (TLS) | implemented |
| `crossref.v1` | DOI metadata | none | ⛔ INACCESSIBLE (TLS) | implemented |
| `wikipedia.v1` | Encyclopedia articles | none | ⛔ INACCESSIBLE (TLS) | implemented |
| `hn.v1` | Hacker News (Algolia + official API) | none | ⛔ INACCESSIBLE (TLS) | implemented |
| `devto.v1` | Developer articles (public API) | optional key | ⛔ INACCESSIBLE (TLS) | implemented |

Each connector is a separate module with its own `VERSION`, and each failure is isolated: a research task continues with partial results when one connector fails (`docs/RESEARCH_CONNECTORS.md`).

## 3. Verification protocol applied to every finding

1. **Origin** — the URL or repo path that produced the fact.
2. **Verification status** — `VERIFIED` (first-party API/doc observed), `CORROBORATED` (≥2 independent secondary sources), `UNVERIFIED` (claimed but unconfirmed here).
3. **Timestamp** — when it was observed (all rows: 2026-11-04).
4. **Confidence** — derived from the verification class above.

The live product applies the same protocol at runtime: every retrieved document carries `source_url`, `source_connector`, `verification_status`, `confidence`, `retrieved_at` and `content_hash` (`docs/RESEARCH_ENGINE.md`).

## 4. Coverage gaps that remain open

| Gap | Why | Mitigation in the product |
|---|---|---|
| No access to arXiv/HF/Reddit/YouTube from the runtime host | sandbox egress allowlist | Connectors implemented and shipped; the Research Center shows each connector's live reachability probe so the user sees `INACCESSIBLE` instead of silence |
| No provider API keys | no provider host is allowlisted and no keys were provisioned | Model Gateway ships real HTTP provider adapters **and** a clearly-labelled `mock` provider; every response is tagged `provider_mode: real\|mock` and surfaced in the UI |
| No device/emulator for APK install test | no KVM, no `adb`, no system image | `adb`-free structural verification (aapt2 dump badging + signature block + dex sanity) is automated; the install/launch steps are exported as a runnable script for a device-attached host and reported as `BLOCKED — no device` |

## 5. Rule compliance

- No platform is claimed to be accessible when it is not. ❌→✅ enforced in code by `ConnectorOutcome.status ∈ {OK, EMPTY, INACCESSIBLE, ERROR, UNAUTHORIZED}`.
- No private, paywalled or restricted content is accessed or bypassed. All connectors target public endpoints or official APIs.
- No access-control circumvention is attempted (no scraping behind logins, no cookie replay, no rate-limit evasion). Rate limits are respected and `Retry-After` is honoured.
- Builder research and the product's research engine are **separate artefacts**: the builder's reports live in `docs/`, the product's engine lives in `backend/titan/research/` and stores its own history in its own database.
