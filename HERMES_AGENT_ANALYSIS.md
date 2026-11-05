# Hermes Agent Analysis

**Verified:** 2026-11-04 against the official GitHub repository, not third-party summaries.

## Identity

- Repository: https://github.com/NousResearch/hermes-agent
- Owner: **NousResearch** (organization)
- Official website listed by repository metadata: https://hermes-agent.nousresearch.com
- License: **MIT**, confirmed from the repository `LICENSE` file.
- Latest GitHub release observed during research: **v0.22.7**. This is a point-in-time API result, not a compatibility endorsement.
- Repository was not archived and had a push dated 2026-11-04 when inspected.

## Runtime and source evidence

The retrieved `pyproject.toml` declares:

- Python distribution name `hermes-agent`.
- Python `>=3.11,<3.15`; comments describe Python 3.14 as the current target while retaining update compatibility for older installations.
- Exact-pinned core dependencies, with provider-specific functionality moved to optional extras.
- OpenAI, HTTPX, Pydantic, Rich, Fire, Tenacity, YAML and other dependencies conditional on Python version.
- JavaScript/TypeScript also exists in the repository for user-interface/tooling components.

The root tree contains `agent/`, `providers/`, `tools/`, `skills/`, `plugins/`, `gateway/`, `cron/`, `evals/`, `tests/`, `web/`, `ui-tui/`, execution/deployment files and a large set of session-state modules. These are observed paths, not assumptions based on marketing.

## Practical architecture

1. **Agent harness:** model/tool execution loop with explicit run/session state.
2. **Provider abstraction:** multiple provider modules and model-specific tooling rather than a Hermes-model-only runtime.
3. **Persistent state:** SQLite/state modules, full-text search, compression and session lifecycle support.
4. **Skills and plugins:** versioned/file-based capabilities and optional distributions.
5. **Messaging/interface gateway:** CLI, TUI, web and messaging adapters.
6. **Execution/tool surface:** terminal, files, research/browser-related tools and delegated tasks; this creates a substantial security boundary.
7. **Evaluation:** repository includes tests and eval directories.

## What TITAN should learn

- Keep provider-specific dependencies optional and isolate credentials.
- Make skills explicit artifacts with tests and rollout control.
- Persist session/task state and support compaction rather than relying on chat context alone.
- Treat memory, skills and model training as different systems.
- Use exact dependency locking and maintain a small core dependency surface.

## Limitations and adoption decision

- Hermes is a broad personal-agent harness, not a ready-made multi-tenant Android/backend ecosystem.
- Its current Python target and large dependency/tool surface differ from TITAN's initial Python 3.11 sandbox and mobile-first requirements.
- Tool use, persistent memory and messaging gateways increase prompt-injection, credential-exfiltration and supply-chain risk.
- Repository popularity or release frequency does not prove security, Bengali quality, model performance or Android compatibility.
- Hermes was not executed or benchmarked in this environment; those claims remain unverified.

**Decision:** use as an architecture reference only in the first increment. Do not vendor or claim Hermes integration. Reassess a narrowly scoped adapter after deployment, license, security and compatibility tests.
