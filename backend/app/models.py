from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    instructions: Mapped[str] = mapped_column(Text)
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_permissions: Mapped[list] = mapped_column(JSON, default=list)
    memory_scope: Mapped[str] = mapped_column(String(50), default="task")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    retry_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    test_results: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentTask(TimestampMixin, Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class ResearchTask(TimestampMixin, Base):
    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    query: Mapped[str] = mapped_column(Text)
    connectors: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    max_results: Mapped[int] = mapped_column(Integer, default=5)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    connector: Mapped[str] = mapped_column(String(80))
    connector_version: Mapped[str] = mapped_column(String(30))
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchDocument(Base):
    __tablename__ = "research_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("research_sources.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_documents.id"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    verification_status: Mapped[str] = mapped_column(String(50))
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="user")
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    scope: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    description: Mapped[str] = mapped_column(Text)
    handler: Mapped[str] = mapped_column(String(80), default="text_stats")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_requirements: Mapped[list] = mapped_column(JSON, default=list)
    permission_scope: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    test_results: Mapped[dict] = mapped_column(JSON, default=dict)
    security_review: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        Index("ix_skill_owner_slug_version", "owner_id", "slug", "version", unique=True),
    )


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(160))
    definition: Mapped[dict] = mapped_column(JSON)


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    checkpoints: Mapped[dict] = mapped_column(JSON, default=dict)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(250), default="New chat")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="complete")
    tool_activity: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    template: Mapped[str] = mapped_column(String(50), default="empty")
    relative_path: Mapped[str] = mapped_column(String(250), unique=True)


class BuildJob(Base):
    __tablename__ = "build_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    variant: Mapped[str] = mapped_column(String(50), default="debug")
    command: Mapped[list] = mapped_column(JSON, default=list)
    logs: Mapped[str] = mapped_column(Text, default="")
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String(100), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_id: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30))
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(160))
    task_type: Mapped[str] = mapped_column(String(80))
    success: Mapped[bool] = mapped_column(Boolean)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
