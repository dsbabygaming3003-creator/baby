# Research Connector Architecture

## Interface

`SourceConnector.search(query, max_results) -> ConnectorResult` with connector ID/version, official endpoint and normalized documents. Documents include external ID, title, URL, content, author, published time, verification status and metadata.

Required pipeline: access policy → retrieval → normalization → dedupe → verification label → factual findings → owner knowledge → report. Each source attempt commits independently.

## GitHub connector v1.0.0

- Endpoint: fixed `https://api.github.com/search/repositories`.
- Access: public official API; optional server-side token only.
- TLS: certificate verification remains enabled using the operating system trust store.
- Limits: 1–20 results, 10-second connect/30-second request timeout, redirects disabled.
- Verification: `verified_official_api` means returned by the official API, not that a project's claims/security are validated.
- Failure: status/error retained; other connectors may still produce partial results.

## Connector onboarding gate

Every new versioned module needs an official access policy, credential scope, query adapter, fixed/validated egress, normalization tests, failure tests, retention rules, prompt-injection treatment and license/terms review. Private content or access-control bypass is forbidden.

## Registry status

| Connector | Status |
|---|---|
| GitHub repositories | IMPLEMENTED + live verified |
| GitLab/Codeberg/SourceHut/Bitbucket | NOT IMPLEMENTED |
| arXiv/Papers with Code | NOT IMPLEMENTED |
| YouTube/TikTok/Facebook/Instagram/X/Reddit/LinkedIn/Pinterest | NOT IMPLEMENTED; official authorization required |
| Discord/Telegram | NOT IMPLEMENTED |
| Browser/documentation/video extraction | NOT IMPLEMENTED |
