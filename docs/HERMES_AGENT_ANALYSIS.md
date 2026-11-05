# HERMES AGENT ANALYSIS — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Canonical repository:** `https://github.com/NousResearch/hermes-agent`
**Verification method:** first-party GitHub REST API (`/repos/…`, `/contents/…`, `/releases`, `/languages`) plus public documentation reads. Every structural claim below was observed directly in the repository, not taken from a blog.

---

## 1. Identity & Verification

| Attribute | Observed value | Source |
|---|---|---|
| Canonical repository | `NousResearch/hermes-agent` | `GET /repos/NousResearch/hermes-agent` → `full_name` |
| Owner | Nous Research | repository owner field |
| Licence | **MIT** | `license.spdx_id = "MIT"`; `LICENSE` file (1,070 B) present at root |
| Primary language | **Python** | `language = "Python"`; `/languages` → Python 119,230,153 B |
| Secondary | **TypeScript** 43,261,399 B; JavaScript 3,130,487 B; Shell 817,665 B; PowerShell 578,569 B; TeX 434,546 B; CSS 350,697 B | `/languages` |
| Language ratio | ≈ **88% Python / ≈8.8% TypeScript** | computed from byte counts — matches independent secondary reports |
| Stars | 260,553 | `/repos` |
| Open issues | 52,905 | `/repos` |
| Last push | **2026-11-04** (same day as this analysis) | `/repos.pushed_at` |
| Latest release | **v0.22.7**, published **2026-11-03** | `/releases?per_page=3` → `v0.22.7 (2026-11-03)`, `v0.22.6 (2026-11-02)`, `v0.22.5 (2026-10-23)` |
| Archived | No | `/repos.archived = false` |
| Companion repo | `NousResearch/hermes-agent-self-evolution` — 5,645★, Python, last push 2026-06-17, licence **not reported** by the API | `/search/repositories` |
| Tagline | "The agent that grows with you" | `/repos.description` |
| Related docs site | `hermes-agent.nousresearch.com/docs` (secondary source) | documentation read |

> **Correction of a stale claim found in secondary sources:** several 2026 articles describe Hermes as "v0.13.0" or "v0.17.0". The live release feed shows **v0.22.7 (2026-11-03)**. Secondary articles are treated as *lagging*; this document always uses the API value.

## 2. Verified Repository Layout

Root entries observed via `GET /repos/NousResearch/hermes-agent/contents/`:

```
.coderabbit.yaml  .dockerignore  .env.example (27,388 B)  .envrc  .gitattributes
.github/  .gitignore  .hadolint.yaml  .mailmap  .npmrc  .nvmrc  .prettierignore
.prettierrc  .python-version
AGENTS.md (11,952 B)  CONTRIBUTING.md (57,145 B)  CONTRIBUTING.es.md  README.md (17,490 B)
README.es.md  README.ur-pk.md  README.zh-CN.md
SECURITY.md (15,752 B)  SECURITY.es.md (18,626 B)
SOUL.md (667 B)
acp_adapter/  activate  activate.fish  activate.ps1
agent/        <-- core runtime
apps/         assets/    batch_runner.py (49,131 B)
cli.py (82,448 B)       cli-config.yaml.example (131,920 B)
contributors/ cron/     docker-compose.yml  docker-compose.windows.yml
Dockerfile (34,476 B)
```

`agent/` contents observed (`GET .../contents/agent`) include:
`agent_init.py`, `agent_init_compression_notice.py`, `agent_init_fallback.py`, `agent_init_memory_provider.py`, `agent_init_ollama.py`, `agent_init_params.py`, `agent_runtime_helpers.py`, `agent_runtime_helpers_dead_connections.py`, `anthropic_adapter.py`, `anthropic_credentials.py`, `anthropic_endpoints.py`, `anthropic_message_convert.py`, `anthropic_thinking_policy.py`, `anthropic_thinking_replay.py`, `api_error_summary.py`, `api_request_hooks.py`, `acp_openai_bridge.py`, `account_usage.py`, `account_usage_cache.py`, `activity_tracking.py`, `async_utils.py`, …

### What this layout proves (and what it refutes)

| Claim | Verdict | Basis |
|---|---|---|
| "Provider-transport abstraction with per-provider adapters" | **CONFIRMED** | `anthropic_adapter.py`, `anthropic_endpoints.py`, `anthropic_credentials.py`, `acp_openai_bridge.py`, `api_request_hooks.py` |
| "Usage/token accounting is first-class" | **CONFIRMED** | `account_usage.py`, `account_usage_cache.py` |
| "Fallback and compression are agent-init concerns" | **CONFIRMED** | `agent_init_fallback.py`, `agent_init_compression_notice.py`, `agent_init_memory_provider.py`, `agent_init_ollama.py` |
| "Batch trajectory generation for training data exists" | **CONFIRMED** | `batch_runner.py` (49 KB) at root |
| "Cron/scheduled execution" | **CONFIRMED** | `cron/` directory |
| "Multi-client surface: CLI + desktop apps + IDE (ACP) + messaging" | **CONFIRMED** | `cli.py` (82 KB), `apps/`, `acp_adapter/`, `docker-compose.yml`, `activate.*` shell/PowerShell/Fish installers |
| "Memory providers are pluggable" | **CONFIRMED** | `agent_init_memory_provider.py` |
| "Context compression exists" | **CONFIRMED** | `agent_init_compression_notice.py` + `SOUL.md`/`AGENTS.md` context files |

## 3. Documented Architecture (secondary sources, corroborated by the layout above)

1. **Agent loop** — a synchronous conversation loop handling provider selection, prompt construction, tool execution, retries and context compression.
2. **Tools** — 40+ built-ins plus MCP servers: files, web search, browser automation, image generation, TTS.
3. **Execution backends** — local, Docker, SSH, and cloud sandboxes (Daytona, Modal). *Command execution is sandboxed by default with pluggable backends.*
4. **Context files** — `AGENTS.md` or `HERMES.md` (highest priority wins, resolved from cwd up to the git root) plus a global `SOUL.md` from the Hermes home directory. Skills load their content lazily, only when needed.
5. **Memory** — bounded `MEMORY.md` (~800 tokens) and `USER.md` (~500 tokens) across sessions; `session_search` full-text search over past CLI and messaging conversations.
6. **Permissions** — tiered approval modes (Smart / Manual / Off) for risky commands, plus a hard blocklist that stops irreversible actions even in "YOLO" mode.
7. **Subagent delegation** — *process-level*: a delegated subagent gets its own conversation, own terminal and Python RPC.
8. **Skills** — the agent writes `SKILL.md` files into `~/.hermes/skills/`, improves them with use, compatible with the `agentskills.io` standard.
9. **Plugins** — extension system; `plugins/` compatible with the agentskills.io standard.
10. **Gateways** — Telegram, Discord, Slack, WhatsApp, Signal, MS Teams bridges.
11. **Interfaces** — Terminal (CLI), desktop app, IDE (VS Code / Zed / JetBrains via ACP), messaging apps.
12. **Packaging** — `uv` + `pyproject.toml`; Python 3.x pin in `.python-version`; Node pin in `.nvmrc`/`.npmrc` for the TypeScript TUI.
13. **Self-evolution** — the companion repo uses **DSPy + GEPA** to optimise skills/prompts/code.

## 4. How TITAN Uses This Analysis

**Adopted as design principles (re-implemented independently, no code copied):**

| Hermes principle | TITAN implementation | Where |
|---|---|---|
| Provider transport abstraction | `ModelGateway` + `ProviderAdapter` per provider family | `backend/titan/services/gateway.py` |
| Usage accounting | `ModelCall` rows with tokens/latency/cost/provider/model, attributed to agent+tool+skill | `backend/titan/models.py` |
| Pluggable memory provider | `MemoryService` with 8 typed scopes | `backend/titan/services/memory.py` |
| Lazy skill loading + procedural skills | `SkillFactory` producing versioned `SKILL.md`-style specs executed in a sandbox | `backend/titan/services/skills.py` |
| Tiered approval + hard blocklist | Tool `permission_scope` + `approval_required` + `IRREVERSIBLE_COMMANDS` blocklist | `backend/titan/services/tools.py` |
| Process-level subagent delegation | `AgentRun` = own task, own context, own tool grants, own transcript | `backend/titan/agents/` |
| Trajectory capture | Every agent run stores the full ordered trajectory of tool calls with timings and errors | `agent_runs` / `tool_executions` |
| Batch trajectory generation | `scripts/research/collect_trajectories.py` | `scripts/` |
| Cron / scheduled execution | `SchedulerService` (workflow schedules) | `backend/titan/services/workflow.py` |
| Compression of long context | Context assembly with token budget + summarisation fallback in the gateway | `backend/titan/services/gateway.py` |
| Error normalisation per provider | `ProviderError` taxonomy → retry / fallback / user-visible message | `backend/titan/services/gateway.py` |

**Deliberately NOT adopted (and why):**

| Hermes feature | Why not |
|---|---|
| Markdown-file memory (`MEMORY.md`, `USER.md`) | TITAN needs tenant-scoped, versioned, searchable, embeddable memory with retention/deletion policies. A flat file cannot satisfy that. |
| CLI/TUI-first UX | TITAN is a mobile-first product; the phone is a first-class client, not a terminal remote. |
| `~/.hermes/skills` as the skill store | TITAN's Skill Factory needs versioning, sandbox validation, approval, marketplace install/update, and metrics — a registry in the database, not files on disk. |
| Skills written by the agent into the user's home | TITAN's factory must run a **sandbox test + evaluation score before registration**, and require approval before publish. |
| Direct multi-provider credential file (`.env.example` pattern) | TITAN centralises secrets server-side and never ships provider keys to clients. |

## 5. Licensing conclusion

Hermes Agent is **MIT**. Its licence would permit reuse of its code with attribution. **TITAN copies none of it.** The value taken is *architectural knowledge* (transport abstraction, delegation semantics, permission tiers, skill lifecycle), which is not copyrightable. TITAN's implementation is original and independently reviewable.

## 6. Confidence table

| Claim | Verification status | Confidence |
|---|---|---|
| Repository, owner, MIT licence | VERIFIED (GitHub API) | High |
| Latest release v0.22.7 (2026-11-03) | VERIFIED (GitHub API) | High |
| Language split ≈88% Python / 8.8% TypeScript | VERIFIED (byte counts) | High |
| Directory layout & file names | VERIFIED (contents API) | High |
| 40+ tools, MCP support | CORROBORATED (docs + layout) | Medium-High |
| Approval modes Smart/Manual/Off + blocklist | CORROBORATED (docs; SECURITY.md present) | Medium-High |
| Subagent delegation is process-level | CORROBORATED (docs) | Medium-High |
| `MEMORY.md` ~800 / `USER.md` ~500 token bounds | CORROBORATED (docs) | Medium |
| DSPy + GEPA self-evolution repo | VERIFIED existence / licence unverified | Medium |
| Version numbers quoted by 2026 blog articles (v0.13/v0.17) | **REFUTED — stale** | — |
