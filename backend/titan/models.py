"""TITAN OMEGA INFINITY V18 — canonical entity model (32 business entities).

Design rules
------------
* Every tenant-scoped row carries ``org_id`` so that isolation is enforced at
  the storage layer, not only in application code.
* Flexible/evolving payloads use ``JSON`` columns (SQLAlchemy maps them to
  ``TEXT`` on SQLite) so that schema evolution never requires a destructive
  migration.
* Mutable content that must be versioned is stored in a child table
  (``*_versions``) rather than overwritten in place.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class TenantMixin:
    org_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="default")


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="standard")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="default")
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="researcher", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    locale: Mapped[str] = mapped_column(String(16), default="en")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Providers, models, evaluation, training
# --------------------------------------------------------------------------
class Provider(Base, TimestampMixin):
    __tablename__ = "providers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    family: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    base_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requires_key: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    status_detail: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelRecord(Base, TimestampMixin):
    __tablename__ = "models"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), ForeignKey("providers.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    family: Mapped[str] = mapped_column(String(48), default="", index=True)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    context_window: Mapped[int] = mapped_column(Integer, default=0)
    input_cost_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    licence_category: Mapped[str] = mapped_column(String(48), default="hosted-proprietary")
    verified_identifier: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelEvaluation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "model_evaluations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    model_id: Mapped[str] = mapped_column(String(96), index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    provider_mode: Mapped[str] = mapped_column(String(16), default="real")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class TrainingDataset(Base, TimestampMixin, TenantMixin):
    __tablename__ = "training_datasets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="manual")
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    cleaned_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="collected", index=True)
    licence_note: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------------------
# Projects, files, conversations
# --------------------------------------------------------------------------
class Project(Base, TimestampMixin, TenantMixin):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    root_path: Mapped[str] = mapped_column(String(500), default="")
    language: Mapped[str] = mapped_column(String(32), default="python")
    template: Mapped[str] = mapped_column(String(64), default="blank")
    git_branch: Mapped[str] = mapped_column(String(120), default="main")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class Conversation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Message(Base, TimestampMixin, TenantMixin):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    reasoning_summary: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    tool_activity: Mapped[list] = mapped_column(JSON, default=list)
    model_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    provider_mode: Mapped[str] = mapped_column(String(16), default="real")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Attachment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    message_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    storage_path: Mapped[str] = mapped_column(String(600), default="")
    scan_status: Mapped[str] = mapped_column(String(32), default="clean", index=True)
    scan_detail: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------
class Agent(Base, TimestampMixin, TenantMixin):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(80), default="", index=True)
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    system_instructions: Mapped[str] = mapped_column(Text, default="")
    model_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_permissions: Mapped[list] = mapped_column(JSON, default=list)
    memory_scope: Mapped[str] = mapped_column(String(48), default="agent")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    retry_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_criteria: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(32), default="system")


class AgentVersion(Base, TimestampMixin):
    __tablename__ = "agent_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id"), index=True)
    version: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    UniqueConstraint("agent_id", "version", name="uq_agent_version")


class AgentTask(Base, TimestampMixin, TenantMixin):
    __tablename__ = "agent_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240), default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class AgentRun(Base, TimestampMixin, TenantMixin):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    trajectory: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
class ToolRecord(Base, TimestampMixin):
    __tablename__ = "tools"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    permission_scope: Mapped[str] = mapped_column(String(48), default="read", index=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    retry_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    error_contract: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)


class ToolPermission(Base, TimestampMixin):
    __tablename__ = "tool_permissions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_id: Mapped[str] = mapped_column(String(80), index=True)
    scope: Mapped[str] = mapped_column(String(48), default="read")
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    granted_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool_permission")


class ToolExecution(Base, TimestampMixin, TenantMixin):
    __tablename__ = "tool_executions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tool_id: Mapped[str] = mapped_column(String(80), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="ok", index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


# --------------------------------------------------------------------------
# Skills
# --------------------------------------------------------------------------
class Skill(Base, TimestampMixin, TenantMixin):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_requirements: Mapped[list] = mapped_column(JSON, default=list)
    permission_scope: Mapped[str] = mapped_column(String(48), default="read")
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    test_cases: Mapped[list] = mapped_column(JSON, default=list)
    security_review: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SkillVersion(Base, TimestampMixin):
    __tablename__ = "skill_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    skill_id: Mapped[str] = mapped_column(String(64), ForeignKey("skills.id"), index=True)
    version: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    UniqueConstraint("skill_id", "version", name="uq_skill_version")


# --------------------------------------------------------------------------
# Workflows
# --------------------------------------------------------------------------
class Workflow(Base, TimestampMixin, TenantMixin):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    graph: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowRun(Base, TimestampMixin, TenantMixin):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    current_step: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    step_results: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------
class SourceConnector(Base, TimestampMixin):
    __tablename__ = "source_connectors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    access_policy: Mapped[str] = mapped_column(String(48), default="public")
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchTask(Base, TimestampMixin, TenantMixin):
    __tablename__ = "research_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), default="")
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    connectors_total: Mapped[int] = mapped_column(Integer, default=0)
    connectors_ok: Mapped[int] = mapped_column(Integer, default=0)
    connectors_failed: Mapped[int] = mapped_column(Integer, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


class ResearchSource(Base, TimestampMixin):
    __tablename__ = "research_sources"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    connector_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ok", index=True)
    url: Mapped[str] = mapped_column(String(800), default="")
    title: Mapped[str] = mapped_column(String(400), default="")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")


class ResearchDocument(Base, TimestampMixin):
    __tablename__ = "research_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    connector_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(800), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    trust: Mapped[str] = mapped_column(String(16), default="untrusted")
    injection_risk: Mapped[float] = mapped_column(Float, default=0.0)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchFinding(Base, TimestampMixin):
    __tablename__ = "research_findings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    document_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str] = mapped_column(String(800), default="")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)


# --------------------------------------------------------------------------
# Knowledge / embeddings / memory
# --------------------------------------------------------------------------
class KnowledgeDocument(Base, TimestampMixin, TenantMixin):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String(48), default="research", index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(800), default="")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    licence_note: Mapped[str] = mapped_column(String(200), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(32), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, default="")
    vector: Mapped[list] = mapped_column(JSON, default=list)
    norm: Mapped[float] = mapped_column(Float, default=1.0)
    model: Mapped[str] = mapped_column(String(64), default="local-hash-v1")
    Index("ix_embedding_document", "document_id", "chunk_index")


class MemoryEntry(Base, TimestampMixin, TenantMixin):
    __tablename__ = "memory_entries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    scope: Mapped[str] = mapped_column(String(48), index=True)
    scope_key: Mapped[str] = mapped_column(String(160), default="", index=True)
    kind: Mapped[str] = mapped_column(String(48), default="note")
    content: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------------------
# Build & audit
# --------------------------------------------------------------------------
class BuildJob(Base, TimestampMixin, TenantMixin):
    __tablename__ = "build_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    target: Mapped[str] = mapped_column(String(64), default="apk")
    variant: Mapped[str] = mapped_column(String(24), default="debug")
    command: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


class BuildArtifact(Base, TimestampMixin):
    __tablename__ = "build_artifacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    build_job_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), default="file")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    path: Mapped[str] = mapped_column(String(600), default="")
    download_url: Mapped[str | None] = mapped_column(String(600), nullable=True)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(32), index=True, default="default")
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(32), default="system")
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(48), default="")
    target_id: Mapped[str] = mapped_column(String(80), default="")
    outcome: Mapped[str] = mapped_column(String(24), default="ok", index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


Index("ix_audit_action_time", AuditLog.action, AuditLog.created_at)
