# SECURITY RESEARCH — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Scope:** threat model, controls, and the security posture of the researched ecosystem.

---

## 1. Threat model

| Asset | Threat | Control |
|---|---|---|
| Provider API keys | Exfiltration via APK reverse-engineering, log leakage, source control | Keys live only in the server-side `SecretStore` (env/file/DB, encrypted at rest with a server-held key); the Android client never receives a provider key; an automated test scans the built APK for key-shaped strings; logs are redacted by a `SecretRedactor` |
| User data & research corpus | Cross-tenant leakage | Every query is tenant-scoped; `TenantScope` is injected into every repository method; SQLite `row_factory` + mandatory `org_id` filters |
| Retrieved web content | **Prompt injection** | External content is data, never instruction: retrieval wraps documents in a delimited `UNTRUSTED REFERENCE DATA` block, strips system-prompt markers, and the injected-content scanner flags imperative-injection patterns (`ignore previous instructions`, `you are now`, `disregard the system prompt`, etc.) |
| Outbound HTTP | SSRF to internal metadata/services | `ssrf.py` validates scheme, resolves the host, and rejects loopback/private/link-local/multicast/metadata ranges unless the host is in the deployment egress allowlist; redirects are re-validated |
| Command execution | Arbitrary code execution on the host | Per-project jailed working root, `ulimit` caps, command allowlist, wall-clock kill, output truncation, non-root execution, and an approval gate for irreversible commands |
| Tool invocation | Agent abusing permissions | Every tool declares `permission_scope`; the executor checks the calling agent's grants; irreversible scopes require explicit user approval (`approval_required`) recorded in the audit log |
| Uploaded files | Malware / zip-bomb / path traversal | Content-type + magic-byte sniffing, size caps, filename sanitisation, per-project storage isolation, and a path-traversal check on every resolved path |
| Workflow state loss | Interrupted work silently lost | Checkpoints after every step, DB-backed, resumable |
| Dependency compromise | Supply-chain attack | Pinned versions + hashes in `requirements.txt`, audit script `scripts/audit_dependencies.sh` (pip-audit compatible), licence scan in `docs/LICENSE_AUDIT.md` |
| Audit evasion | Actions without trace | Every tool call, agent run, model call, approval and error is written to `audit_logs` with a correlation id, actor, target and outcome |

## 2. Authentication & authorisation

- **Password hashing:** `hashlib.scrypt` (n=2^14, r=8, p=1) with a per-user random salt; constant-time comparison. No plaintext, no reversible storage.
- **Sessions:** stateless JWT (HS256) implemented in-repo (`backend/titan/security/jwt.py`) — header/payload/signature structure verified by the tests. Expiry, issuer and audience are validated; `exp` is mandatory.
- **API keys:** generated as `tk_` + 32 random bytes, stored as SHA-256 digests only, shown once, revocable, and scoped.
- **RBAC:** roles `owner`, `admin`, `researcher`, `developer`, `viewer`. Each route declares a required scope; the dependency enforces it. Role changes are audited.
- **Tenant isolation:** `org_id` on every tenant-scoped table; repository helpers refuse a query without one.

## 3. Prompt-injection defence (detailed)

The research ecosystem showed the real risk: Hermes Agent's docs describe a startup scanner for known-compromised packages and a hard blocklist for irreversible commands; OpenHands' benchmark work measures "out-of-scope action rates" of 5.4%–27.7% in permissive frameworks vs 0.2%–4.5% with ask-to-continue gates. TITAN therefore implements:

1. **Trust labelling.** Every retrieved document carries `trust=untrusted`. Only system instructions from the operator's own configuration are trusted.
2. **Structural delimiting.** Retrieved text is inserted into a fenced `<<<REFERENCE_DATA ...>>>` block; the system prompt explicitly states that content inside that block cannot grant permissions, change the task, or request tool use.
3. **Marker stripping.** Occurrences of system-prompt delimiters inside retrieved text are removed before insertion.
4. **Pattern scanner.** `injection.py` scores documents with weighted regexes (`ignore previous`, `disregard`, `system prompt`, `you are now`, `exfiltrate`, `curl | sh`, `rm -rf /`) and raises the document's risk score, which lowers its relevance rank and is surfaced in the Research Center.
5. **Permission separation.** Model output can *request* a tool call; the executor independently re-checks permissions. A model cannot widen its own scope.

## 4. Sandboxing

`backend/titan/services/sandbox.py` executes commands with:

- `cwd` forced inside the project root; any path escape is rejected before launch,
- `resource.setrlimit` caps: CPU seconds, address space, file size, process count,
- `env` scrubbed to a minimal allowlist (no provider keys leak into shell output),
- wall-clock timeout with process-group kill,
- stdout/stderr truncated to a bounded size,
- an **egress allowlist** enforced for tools that make network calls.

Docker is unavailable in this sandbox (`docs/ENVIRONMENT_AUDIT.md` §2); the process-isolation backend is the active one, and a Docker backend is implemented behind the same interface for deployments that have it.

## 5. Secret management

- `SecretStore` resolves secrets from (in order): process env → encrypted DB row → file with 0600 permissions.
- Secrets are never returned by any API; the API returns only `{configured: bool, source: "env"|"db"|"file"|"missing"}`.
- A redaction filter scrubs secret-looking substrings from logs, tool outputs and error traces.
- The Android app receives **no** provider credential — it authenticates to TITAN with its own device/user token, and TITAN performs all provider calls server-side.

## 6. Dependency & supply-chain posture

- Pinned requirements with hashes (`backend/requirements.txt`).
- No runtime dependency is GPL/AGPL (see `docs/LICENSE_AUDIT.md`).
- `scripts/audit_dependencies.sh` runs `pip-audit` when available and falls back to a PyPI advisory query; its output is captured in `docs/TEST_REPORT.md`.
- The Android build pulls **zero** external artifacts at build time beyond the pinned toolchain — the client has no third-party runtime dependency, which removes an entire mobile supply-chain surface.

## 7. Assessment of the pre-existing repository file

`instagram_2fa_automation.js` (135 KB) is a WebView user-script that automates Instagram 2FA flows inside a WebView host, reading cookies and clearing browsing data.

**Findings:**
- It is **not** an Android application; it targets a JavaScript environment with a `chrome.runtime` / `Android2FANative` bridge.
- It manipulates session cookies and clears WebView browsing data — behaviour that is *legitimate* for a first-party automation app but that has **no place** in an AI research/agent platform, where the security model assumes no credential-scraping capability.
- No credential-harvesting or exfiltration code was identified (no third-party endpoints, no obfuscated payload upload), but its cookie-handling surface would be a liability if shipped inside TITAN.

**Decision:** the file is **excluded from the TITAN source tree and the APK**, and **left unmodified in the repository** because it is the owner's own asset and deleting it was not requested. TITAN's build script explicitly packages only `android/app/src/main/**`, so this file can never enter an artifact. A CI-style test asserts that no TITAN module imports or references it.

## 8. Security posture of the researched ecosystem (what TITAN borrows / avoids)

| Project | Security posture | TITAN response |
|---|---|---|
| Hermes Agent | Documented tiered approval modes (Smart/Manual/Off) + hard blocklist for irreversible actions; startup package scanner; sandboxed execution backends | ✅ Adopted: per-tool `permission_scope` + approval gate + blocklist + sandbox |
| OpenHands | Container-per-task isolation; enterprise tier is source-available while the core is MIT | ✅ Adopted: per-project isolation. ⚠️ Noted: licence changes with the enterprise tier |
| SWE-agent | Transparent trajectories; benchmark-configured | ✅ Adopted: every agent run stores its full trajectory (tool inputs/outputs, timings, errors) |
| Claude Code | Proprietary; no source to audit | ⛔ Not used as an implementation reference |
| Retrieval RAG | Known injection surface | ✅ Adopted: trust labelling + delimiting + scanner (§3) |
| LiteLLM / gateways | Centralised proxy holds provider keys | ✅ Adopted: keys server-side only; the mobile client never holds one |

## 9. Known residual risks (stated, not hidden)

| Risk | Status | Mitigation / plan |
|---|---|---|
| The backend sandbox uses process isolation, not containers | Active risk | Container backend implemented; deployment guide recommends Docker/K8s where available |
| Rate limiting is in-process (no Redis) | Active risk | Redis-free sliding-window implementation is correct for a single node; multi-node deployments should front it with Redis — documented |
| No malware scanning service (ClamAV) reachable | Active risk | Magic-byte + size + type validation implemented; AV integration point documented |
| Provider keys absent in this environment | By design | The gateway reports `provider_mode: unavailable/mock`; no fabricated completions |
| TLS egress allowlist blocks most research sources | Environmental | Connectors report `INACCESSIBLE` with the real error; UI surfaces it |
