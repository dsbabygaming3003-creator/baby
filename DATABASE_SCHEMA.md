# Database Schema and Migrations

## Tables

- Agents/tasks: `agents`, `agent_tasks` (owner-scoped).
- Research: `research_tasks`, `research_sources`, `research_documents`, `research_findings`.
- Knowledge: `knowledge_documents`, `memory_entries`.
- Skills/workflows: `skills`, `workflows`, `workflow_runs`.
- Chat/projects: `conversations`, `messages`, `projects`, `build_jobs`.
- Execution/telemetry: `tool_executions`, `model_calls`, `audit_logs`.

IDs are UUID strings; JSON columns hold contracts/results/metadata; timestamps are UTC-aware at application boundaries. Foreign keys and indexes cover task/source/conversation/project ownership paths. Unique constraints cover agent slug, project relative path and owner skill slug/version.

## Migrations

- `1ee96a1842df`: initial intelligence core.
- `39a8e979b237`: non-null owner scope/index on agent tasks. Existing rows receive `legacy-unowned` during add, then the default is removed; legacy tasks are not exposed cross-tenant.

Verified with upgrade, current, downgrade and re-upgrade plus `alembic check`. Startup `create_all` serves the disposable development profile; deployment runs `alembic upgrade head` explicitly after backup/approval.

## Production notes

PostgreSQL + asyncpg configuration is supplied, but no PostgreSQL server exists in the sandbox, so dialect/locking/load tests are not verified. SQLite shared connections are not used concurrently within a worker. Backups, retention jobs, encryption, RLS and production indexing/load analysis remain required. `embeddings` and fine-tuning tables are not created because those systems are not implemented.
