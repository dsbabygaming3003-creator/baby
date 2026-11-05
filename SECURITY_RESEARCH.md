# Security Research — Pre-Build

**Date:** 2026-11-04
**Primary authority:** [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html), official project source inspection, and deployment-boundary analysis.

## Threat model

| Threat | TITAN control required before exposure |
|---|---|
| Indirect prompt injection in repositories/pages/documents | Source content stored as untrusted data; never concatenated as privileged instructions; tool authorization outside the model |
| Tool misuse / excessive agency | Default-deny tool registry, per-agent scopes, argument schemas, user/project boundaries, action-specific approval |
| Shell/code execution | Workspace confinement, executable allowlist, no shell interpolation, timeout/output limits, network denial by default; stronger container/VM isolation for production |
| SSRF and data exfiltration | URL parsing, scheme allowlist, DNS/IP checks including redirects, egress policy, response size limits |
| Credential leakage | Server-side secret references, no secrets in APK/logs/research content, redaction and short-lived app tokens |
| Memory/RAG poisoning | Provenance, verification state, tenant scope, expiration/deletion, no authority granted by memory text |
| Skill/plugin supply chain | Versioned manifests, review, generated tests, sandbox validation, signed/approved publication |
| Multi-tenant data access | Tenant/owner predicates in every repository query and filesystem namespace; deny cross-tenant IDs |
| Workflow retry duplication | Idempotency keys, durable checkpoints, bounded retries and side-effect approval |
| Unbounded model/agent consumption | Token/cost/time/iteration/concurrency limits, cancellation and circuit breakers |
| Insecure file upload/project paths | Size/type limits, canonical-path checks, no archive traversal, malware scanning when available |
| Audit log disclosure/tampering | Structured events, correlation IDs, secret redaction, restricted retention and append-oriented production storage |

## Non-negotiable interpretation

Prompt wording and detection regexes are not security boundaries. A model may propose an action, but trusted execution code must authorize the exact action and arguments. Read-only research does not implicitly grant terminal, write, deployment, messaging or purchase permissions. High-impact operations require approval bound to the exact operation; blanket prior approval is insufficient.

## Android and backend boundaries

- Provider keys never ship in source, resources, BuildConfig, DataStore or logs.
- Android microphone use requires runtime permission, visible state and user control; no hidden capture.
- TLS and certificate validation remain enabled; release builds disable cleartext traffic by default.
- Local SQLite/in-process execution is a development profile, not a sandbox certification.
- Production terminal/build work requires disposable containers or VMs with seccomp/AppArmor, non-root UID, resource quotas and restricted egress.

## Security verification plan

Unit and integration tests must cover prompt-injection fixtures, tool denial, path traversal, SSRF redirects/private IPs, cross-tenant access, approval binding, cancellation, output limits and secret redaction. Release also requires dependency/OSV scanning, mobile secret scanning, migration backup/rollback tests and an externally reviewed sandbox.

**Status:** `RESEARCH COMPLETE FOR FIRST DESIGN; PRODUCT SECURITY CERTIFICATION NOT CLAIMED.`
