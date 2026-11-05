# SECURITY MODEL

Threat model, controls and their verification status. Everything below is implemented in
the running backend; the *verified* column states how it was checked.

---

## 1. Trust boundaries

```
  external content  ──▶  research connectors  ──▶  documents (trust = "untrusted")
        │                                               │
        │  never becomes a system instruction           ▼
        └─────────────────────────────────────▶  agent context / prompts
```

| Boundary | Rule |
|---|---|
| Internet → backend | egress allowlist + SSRF guard (`security/net.py`) |
| Backend → LLM provider | server-side secrets only; the client never sees a key |
| Backend → shell | sandbox with rlimits, allowlisted commands, capped output |
| Backend → database | `org_id` filtering on every tenant query |
| User → tool | scope check + approval gate for irreversible tools |
| External document → agent | **data, never instructions** (`trust=untrusted`, `injection_risk` scored) |

---

## 2. Authentication

| Control | Implementation | Verified |
|---|---|---|
| Password hashing | scrypt (`n=2^14, r=8, p=1`), per-user salt, constant-time compare | AT-03 |
| Session tokens | HS256 JWT issued and verified by TITAN's own code (`security/core.py`); 12 h TTL; `sub`, `org`, `role` claims | AT-03/04 |
| API keys | `ApiKey <digest>` scheme; only the SHA-256 digest is stored | AT-04 |
| Privilege escalation | self-registration may only request `researcher`/`developer`/`viewer`; the **first** account becomes `owner` | AT-03 |
| Rejection | missing header → 401, forged token → 401, wrong password → 401 | AT-03, AT-04 |

The JWT secret defaults to a development value. `TITAN_JWT_SECRET` must be set in any real
deployment — see `docs/DEPLOYMENT.md`.

---

## 3. Authorization (RBAC)

Five roles, scope-based (`security/core.ROLE_SCOPES`):

| Role | Scopes |
|---|---|
| `owner` | `*` |
| `admin` | `read, write, research, agents, skills, memory, models, workflows, projects, build, admin, security` |
| `researcher` | `read, write, research, agents, skills, memory, models, workflows` |
| `developer` | `read, write, projects, build, agents, skills, memory, research, translation, models, workflows` |
| `viewer` | `read` |

`require_scope("admin")` gates `/system/audit` and `/settings/secrets`; a non-admin call
returns **403** (AT-08, AT-35, AT-36).

---

## 4. Secret management

* Credentials live in the backend `SecretStore` (environment-backed, file-backed fallback).
* `/settings/secrets` is `admin`-only and returns **booleans only** — never a value.
* `/security/summary` exposes `secrets_configured: {NAME: true|false}`.
* The Android APK contains **no** provider credential: verified by scanning `classes.dex`
  for `sk-`, `AIza`, `api_key`, `API_KEY`, `OPENAI`, `anthropic` → **0 hits each**
  (`docs/BUILD_REPORT.md` §5).
* The client stores only the user's own bearer token in `SharedPreferences`.

---

## 5. SSRF and egress control

`titan/security/net.py`:

1. resolves the hostname and inspects **every** resolved address;
2. rejects loopback, private, link-local (`169.254.0.0/16` — the cloud metadata address),
   multicast, reserved and unspecified ranges;
3. rejects non-HTTP(S) schemes and redirects to a disallowed host;
4. restricts outbound hosts to `settings.egress_allowlist` when one is configured.

Verification: AT-37 issues a real request to `http://169.254.169.254/latest/meta-data/`
through the `http.fetch` tool and the call is refused with `BLOCKED_BY_POLICY`.

---

## 6. Sandbox

`services/sandbox.py` — process isolation:

| Limit | Default |
|---|---|
| CPU seconds | 20 |
| Memory | 1024 MB |
| Max processes | 64 |
| Wall timeout | 30 s |
| Max output bytes | 256 KB |
| Working root | `/tmp/titan-sandbox` (per project subdirectory) |
| Commands | allowlist only (`echo`, `ls`, `cat`, `uname`, `python`, `node`, `git`, …) |

A refused command is **not** an error page: `/terminal/exec` returns HTTP 200 with
`ok=false`, `error_code="BLOCKED_BY_POLICY"` and a `denied` audit row (AT-23).

Docker is supported as an alternative backend (`DockerBackend.available()`) but is not
installed on this host, so the process backend is what actually runs.

---

## 7. Tool execution engine

* Every tool declares an input schema, an output schema, a permission scope, a timeout,
  a retry policy and a **machine-readable error contract** (8 base codes plus
  scope-specific ones such as `SSRF_BLOCKED`, `NON_ZERO_EXIT`, `APPROVAL_REQUIRED`).
* A caller must hold the scope; otherwise the call fails with `PERMISSION_DENIED`
  (AT-08).
* Irreversible tools carry `requires_approval`; the engine refuses to run them without
  an explicit approval flag.
* Every execution is written to `tool_executions` with its parameters, result, error code
  and duration.

---

## 8. Audit trail

`audit_logs` records `action`, `actor_id`, `actor_role`, `org_id`, `target_type`,
`target_id`, `outcome`, `detail` and the correlation ID. A Prometheus counter
`titan_audit_events_total{action,outcome}` is exported at `/system/metrics` (AT-36).

Audited actions include `auth.register`, `auth.login`, `terminal.exec` (including
denials), `agent.run`, `agent.factory.create`, `agent.factory.validate`, `research.task.*`,
`orchestrate` and `tool.execute`.

---

## 9. Rate limiting

`api/deps.enforce_rate_limit` — sliding window, 120 requests/minute plus a burst of 40,
applied per IP and per user. Exceeding it returns HTTP 429 with a `Retry-After` header.

---

## 10. Input validation

* Pydantic/`Dict` payloads are validated at the route boundary; unknown memory scopes,
  unsupported target languages and unknown model ids return **400/404**, never a 500.
* JSON-schema validation of tool parameters happens before the handler runs.
* Uploaded files are size-limited and hashed (`attachments.sha256`).
* Prompt-injection defence: fetched documents are stored with `trust="untrusted"` and a
  computed `injection_risk`; they are passed to agents as quoted data, never concatenated
  into a system instruction.

---

## 11. Known gaps (honest list)

| Gap | Status |
|---|---|
| No multi-tenant Postgres RLS | service-layer `org_id` filtering only |
| No dependency scanning (Snyk/Dependabot) in CI | not implemented |
| No malware scanning of uploads | hash + size checks only |
| No scheduled DB backup job | manual `pg_dump` / file copy |
| `TITAN_JWT_SECRET` defaults to a dev value | must be overridden in deployment |
| No TLS termination in-process | expected to sit behind a reverse proxy |

See `docs/KNOWN_LIMITATIONS.md`.
