# DATABASE SCHEMA

31 tables created by migration `0001_initial` (`titan/db.py`), applied automatically at
startup. The default profile is SQLite via `aiosqlite`; the schema is written with
portable SQLAlchemy 2.0 types so the same models run on PostgreSQL.

`TenantMixin` gives every tenant-scoped table `org_id`; `TimestampMixin` gives
`created_at` / `updated_at`. Soft deletes use `deleted_at` rather than removing rows.

---

## Identity & tenancy

| Table | Purpose | Notable columns |
|---|---|---|
| `organizations` | tenant root | `id`, `name`, `plan` |
| `users` | accounts | `email` (unique), `password_hash` (scrypt), `role`, `org_id`, `locale`, `is_active`, `last_login_at` |

## Model gateway

| Table | Purpose | Notable columns |
|---|---|---|
| `providers` | provider registry | `id`, `base_url`, `env_key`, `status` |
| `models` | model registry | `id`, `provider_id`, `context_window`, `input_cost_per_mtok`, `output_cost_per_mtok`, `verified_identifier`, `licence_category` |
| `model_evaluations` | benchmark results | `model_id`, `score`, `latency_ms`, `cost_usd`, `sample_count`, `provider_mode`, `details` |
| `training_datasets` | prepared datasets | `name`, `records`, `quality`, `source` |

## Projects & chat

| Table | Purpose | Notable columns |
|---|---|---|
| `projects` | code workspaces | `name`, `root_path`, `org_id` |
| `conversations` | chat threads | `title`, `locale`, `agent_id` |
| `messages` | chat turns | `role`, `content`, `tokens_in`, `tokens_out`, `cost_usd`, `provider_mode` |
| `attachments` | uploaded files | `filename`, `mime_type`, `size_bytes`, `sha256` |

## Agents

| Table | Purpose | Notable columns |
|---|---|---|
| `agents` | agent registry | `id`, `role`, `version`, `status`, `system_instructions`, `model_config_json`, `tool_permissions`, `memory_scope`, `input_schema`, `output_schema`, `timeout_seconds`, `retry_policy`, `quality_criteria`, `quality_score`, `metrics` |
| `agent_versions` | version history | `agent_id`, `version`, `spec`, `created_by` |
| `agent_tasks` | a unit of work | `agent_id`, `objective`, `status`, `result` |
| `agent_runs` | an execution | `task_id`, `started_at`, `finished_at`, `tokens_in`, `tokens_out`, `cost_usd`, `log` |

## Tools

| Table | Purpose | Notable columns |
|---|---|---|
| `tools` | tool registry | `id`, `category`, `input_schema`, `output_schema`, `permission_scope`, `timeout_seconds`, `retry_policy`, `error_contract`, `requires_approval` |
| `tool_permissions` | per-agent grants | `agent_id`, `tool_id`, `scope` |
| `tool_executions` | execution trail | `tool_id`, `agent_id`, `params`, `result`, `error_code`, `duration_ms` |

## Skills

| Table | Purpose | Notable columns |
|---|---|---|
| `skills` | skill registry | `id`, `name`, `version`, `status` (`draft`→`tested`→`published`), `input_schema`, `output_schema`, `tool_requirements`, `permission_scope`, `steps`, `test_results` |
| `skill_versions` | version history | `skill_id`, `version`, `spec` |

## Workflows

| Table | Purpose | Notable columns |
|---|---|---|
| `workflows` | DAG definitions | `name`, `graph`, `status`, `schedule` |
| `workflow_runs` | run state | `workflow_id`, `status`, `checkpoint`, `inputs`, `outputs`, `started_at`, `finished_at` |

## Research & knowledge

| Table | Purpose | Notable columns |
|---|---|---|
| `source_connectors` | connector registry | `id`, `platform`, `version`, `status`, `config` |
| `research_tasks` | a research job | `query`, `topic`, `platforms`, `status`, `report_path` |
| `research_sources` | per-source outcome | `task_id`, `connector_id`, `status`, `count`, `http_status`, `duration_ms` |
| `research_documents` | fetched documents | `title`, `url`, `summary`, `content_hash`, `verification_status`, `confidence`, `injection_risk`, `trust` |
| `research_findings` | extracted statements | `statement`, `evidence_url`, `verification_status`, `confidence` |
| `knowledge_documents` | knowledge base | `title`, `content`, `source`, `chunk_count` |
| `embeddings` | dense vectors | `document_id`, `chunk_index`, `vector` (384-d, L2-normalised) |

## Memory, builds, audit

| Table | Purpose | Notable columns |
|---|---|---|
| `memory_entries` | 8-scope memory | `scope`, `scope_key`, `kind`, `content`, `importance`, `confidence`, `source`, `version`, `expires_at`, `deleted_at` |
| `build_jobs` | build executions | `project_id`, `command`, `target`, `variant`, `status`, `exit_code`, `log_path`, `duration_ms` |
| `build_artifacts` | produced artifacts | `job_id`, `path`, `size_bytes`, `sha256` |
| `audit_logs` | the audit trail | `action`, `actor_id`, `actor_role`, `org_id`, `target_type`, `target_id`, `outcome`, `detail`, `correlation_id` |

---

## Indexes, constraints, access control

* Foreign keys on every tenant-scoped table (`org_id`, `agent_id`, `tool_id`, `task_id`, …).
* Indexes on the hot paths: `users.email` (unique), `memory_entries(scope, scope_key)`,
  `research_documents(content_hash)`, `tool_executions(tool_id, created_at)`,
  `audit_logs(org_id, created_at)`, `embeddings(document_id)`.
* Row-level access is enforced in the service layer through `org_id` filters on every
  query — there is no database-level RLS, so a Postgres deployment should add policies.
* **Retention:** expired memory rows are filtered out of reads (`expires_at`); deletes are
  soft (`deleted_at`). Audit rows are append-only.
* **Backups:** the SQLite file is the unit of backup; for Postgres use `pg_dump`. No
  scheduled backup job ships in this build — see `docs/KNOWN_LIMITATIONS.md`.
