# Security Audit — Development Increment

**Date:** 2026-11-04/05 UTC
**Status:** PARTIAL; no production security certification.

## Controls verified by tests/review

- Production refuses missing API key and mock inference; wrong/missing key returns 401.
- Agent batch ownership isolation returns 404 to a different principal.
- Project `../` traversal and non-allowlisted shell execution are denied; terminal requires exact approval.
- Workflow cycle rejection and skill/agent approval gates.
- Research content retains `untrusted_external_content=true`; an injection-shaped fixture remains data.
- Terminal common secret shapes and sensitive argv values are redacted.
- No provider secret pattern was found by the source scan; no APK exists to inspect.
- Release Android manifest disables cleartext; provider keys are absent from Kotlin/Gradle resources.

## Findings and resolutions

1. **Async dependency missing:** initial SQLAlchemy run failed without `greenlet`. Fixed with `sqlalchemy[asyncio]`; full regression rerun.
2. **Agent task tenant scope:** review found batches lacked an owner. Added `owner_id`, query predicates, migration and cross-principal regression.
3. **Live TLS failure:** HTTPX could not find the environment issuer although curl/GitHub succeeded. Fixed with `truststore` OS CA injection while keeping verification enabled. Live GitHub research then succeeded.
4. **Migration existing rows:** owner migration uses `legacy-unowned` backfill rather than failing or exposing old tasks.
5. **Secret scan script path:** corrected a malformed path and reran final verification.

## Open high-risk items

Single-key admin is not enterprise RBAC/SSO. Local terminal is not a hardened sandbox. Generic browser/SSRF connectors are absent. No production PostgreSQL/RLS/load test, dependency CVE scan, rate limiting, malware scanning, external penetration test, mobile build secret scan or device permission test was possible. Browser speech recognition privacy depends on the browser vendor.

Release must remain development-only until these boundaries are addressed according to `SECURITY_MODEL.md`.
