from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class AgentCreate(APIModel):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    role: str = Field(min_length=3, max_length=100)
    instructions: str = Field(min_length=10, max_length=12000)
    model_routing: dict[str, Any] = Field(
        default_factory=lambda: {"route": "reasoning"}, alias="model_config"
    )
    tool_permissions: list[str] = Field(default_factory=list, max_length=30)
    memory_scope: Literal["task", "project", "user"] = "task"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=120, ge=1, le=900)


class OrchestrationRequest(APIModel):
    objective: str = Field(min_length=3, max_length=12000)
    agent_ids: list[str] | None = Field(default=None, max_length=30)
    provider: str | None = None


class ResearchRequest(APIModel):
    query: str = Field(min_length=2, max_length=500)
    connectors: list[str] = Field(default_factory=lambda: ["github"], min_length=1, max_length=10)
    max_results: int = Field(default=5, ge=1, le=20)
    wait: bool = True


class KnowledgeCreate(APIModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200_000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_type: str = Field(default="user", max_length=50)
    verification_status: Literal["unverified", "user_supplied", "verified_official_api"] = (
        "user_supplied"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryCreate(APIModel):
    scope: Literal["conversation", "user", "project", "agent", "skill", "research", "task", "error"]
    content: str = Field(min_length=1, max_length=20_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: str | None = None


class SkillCreate(APIModel):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    handler: Literal["text_stats", "source_summary", "json_keys"] = "text_stats"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tool_requirements: list[str] = Field(default_factory=list)
    permission_scope: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class SkillExecuteRequest(APIModel):
    input: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(APIModel):
    name: str = Field(min_length=3, max_length=160)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=50)

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = set()
        for step in steps:
            if not isinstance(step.get("id"), str) or not step["id"]:
                raise ValueError("Every step requires a non-empty string id")
            if step["id"] in ids:
                raise ValueError("Step ids must be unique")
            ids.add(step["id"])
            if step.get("type") not in {"text_stats", "model", "delay"}:
                raise ValueError("Step type must be text_stats, model or delay")
            dependencies = step.get("depends_on", [])
            if not isinstance(dependencies, list) or any(
                not isinstance(x, str) for x in dependencies
            ):
                raise ValueError("depends_on must be a list of step ids")
        for step in steps:
            unknown = set(step.get("depends_on", [])) - ids
            if unknown:
                raise ValueError(f"Unknown step dependencies: {sorted(unknown)}")
            if step["id"] in step.get("depends_on", []):
                raise ValueError("A step cannot depend on itself")
        return steps


class ConversationCreate(APIModel):
    title: str = Field(default="New chat", min_length=1, max_length=250)
    project_id: str | None = None


class ConversationUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    pinned: bool | None = None
    archived: bool | None = None


class MessageCreate(APIModel):
    content: str = Field(min_length=1, max_length=50_000)
    provider: str | None = None
    route: Literal["chat", "research", "coding", "translation", "reasoning"] = "chat"


class TranslationRequest(APIModel):
    text: str = Field(min_length=1, max_length=50_000)
    source_language: str = Field(default="auto", max_length=80)
    target_language: str = Field(min_length=2, max_length=80)
    provider: str | None = None


class ProjectCreate(APIModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=4000)
    template: Literal["empty", "python", "research"] = "empty"


class FileWrite(APIModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=1_000_000)


class TerminalRequest(APIModel):
    project_id: str
    argv: list[str] = Field(min_length=1, max_length=50)
    approved: bool = False
    timeout_seconds: int = Field(default=10, ge=1, le=20)

    @field_validator("argv")
    @classmethod
    def validate_argv(cls, argv: list[str]) -> list[str]:
        if any(not arg or len(arg) > 1000 for arg in argv):
            raise ValueError("Arguments must be non-empty and at most 1000 characters")
        return argv
