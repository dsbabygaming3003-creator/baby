# CENTRAL TOOL EXECUTION ENGINE

The only path from an agent to a side effect. 25 tools in 14 categories.

---

## 1. Contract

Every tool declares:

| Field | Purpose |
|---|---|
| `id`, `name`, `category`, `description` | identity and discovery |
| `input_schema` | JSON Schema the parameters are validated against |
| `output_schema` | JSON Schema of the result |
| `permission_scope` | `read`, `write`, `network`, `execute`, `irreversible` |
| `timeout_seconds` | wall-clock budget for one call |
| `retry_policy` | `max_attempts`, `backoff_seconds` |
| `error_contract` | the codes the tool may emit and whether a retry helps |
| `requires_approval` | true → the caller must approve explicitly |
| `handler` | the implementation |

The error contract is composed centrally (`services/tools.py::build_error_contract`) from a
base set plus scope-specific codes, so **no tool can ship an empty contract**:

```
base:      INVALID_INPUT  PERMISSION_DENIED  TIMEOUT  BLOCKED_BY_POLICY
           SSRF_BLOCKED   NOT_FOUND          UPSTREAM_ERROR  INTERNAL_ERROR
network:   + UPSTREAM_RATE_LIMITED  SOURCE_UNAVAILABLE
execute:   + NON_ZERO_EXIT  OUTPUT_TRUNCATED
write:     + CONSTRAINT_VIOLATION
irreversible: + APPROVAL_REQUIRED
```

Verified by AT-07 — all 25 tools expose a non-empty contract.

---

## 2. The registry (25 tools / 14 categories)

| Category | Tools |
|---|---|
| `web_research` | `research.search`, `research.fetch_source`, `research.verify` |
| `github` | `github.repo` |
| `database` | `database.query`, `knowledge.search`, `knowledge.ingest`, `memory.write` |
| `api_client` | `http.fetch` |
| `file_system` | `project.read`, `project.write` |
| `code_editor` | `code.search` |
| `terminal` | `terminal.exec` |
| `testing` | `test.run` |
| `build_system` | `build.run`, `release.verify` |
| `model_execution` | `models.list`, `models.evaluate` |
| `translation` | `translate.detect`, `translate.text` |
| `audio` | `voice.capabilities`, `voice.transcribe`, `voice.speak` |
| `image` | `image.analyse` |
| `security` | `security.scan` |

---

## 3. Execution flow

```
agent → POST /tools/{id}/execute {params, scopes}
          │
          ▼
     scope check ────────────────► PERMISSION_DENIED (403)
          │
          ▼
     approval check (if irreversible) ─► APPROVAL_REQUIRED
          │
          ▼
     schema validation ──────────► INVALID_INPUT (400)
          │
          ▼
     handler run (timeout, retry) ─► TIMEOUT / UPSTREAM_ERROR
          │
          ▼
     ToolResult{ok, output, error_code, error_message, duration_ms, exit_code, metadata}
          │
          ▼
     audit row + tool_executions row + metrics
```

**A tool that did not run is never reported as successful.** `ok` is the only success
signal and it is always present, with `error_code` alongside it.

---

## 4. Permission enforcement

```bash
curl -X POST .../api/v1/tools/terminal.exec/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"params": {"command": "echo x"}, "scopes": ["read"]}'
```

→ `{"error_code": "PERMISSION_DENIED", ...}` (AT-08). `terminal.exec` needs the `execute`
scope, which `read` does not carry.

Agent tool grants are stored per agent (`tool_permissions`), so an agent can only reach the
tools it was granted.

---

## 5. Audit and history

Every call is written to `tool_executions` (parameters, result, error code, duration, agent)
and increments the metrics counters. `GET /tools/executions` returns the trail.

---

## 6. Adding a tool

1. write a handler `async def _my_tool(params: dict, ctx: ToolContext) -> dict`;
2. register it in `services/tools_impl.py::register_all` with a full contract;
3. the registry, the `/tools` listing, the permission model and the audit trail pick it up
   automatically — no other wiring is needed.
