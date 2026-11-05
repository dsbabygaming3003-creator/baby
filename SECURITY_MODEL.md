# Security Model

## Authority boundaries

- Requests receive correlation IDs and security headers. Production startup requires an API key; constant-time comparison protects authentication. Current single-key admin model is not full SSO/RBAC.
- Owner predicates protect research, knowledge, memory, skills, workflows, chat, projects, builds and agent task batches.
- Models can propose text only; trusted code enforces tool registry, schemas, ownership and exact approval.
- External research is untrusted data. Verification labels describe provenance, not truth or safety.
- Provider secrets stay server-side; Android accepts only a backend URL. Common token shapes and sensitive argv values are redacted from execution/audit records.
- TLS verification uses the OS trust store. Release Android disables cleartext.

## Execution boundary

Canonical paths and symlink denial protect project files. Terminal has exact argv, allowlist, no shell, sanitized env, timeout/output caps and audit. These controls are defense-in-depth for development, not a certified hostile-code sandbox.

## High-risk production gates

SSO + granular RBAC/tenant policy, encrypted secret manager, sandbox containers/VMs, SSRF egress proxy for generic web connectors, malware scanning, signed skills, immutable audit storage, rate limiting, backup/restore drills, dependency/OSV scanning and action-bound approval for migrations/deployment. Prompt filters alone are never accepted as protection.
