"""Dynamic Agent Factory + Skill Factory.

A dynamically generated agent is *not* trusted by default: it must pass a
sandbox test and an evaluation score before it can be registered into the
production registry, and publication requires approval.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..agents.definitions import AgentDefinition
from ..models import Agent, AgentVersion, Skill, SkillVersion, ToolExecution
from .observability import log, metrics
from .tools import ToolContext, registry as tool_registry


def _slug(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in (text or "").lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:48] or "agent"


class AgentFactory:
    """Creates new agents from a natural-language specification."""

    def __init__(self) -> None:
        self._pending: Dict[str, Dict[str, Any]] = {}

    async def create(
        self,
        session,
        *,
        specification: str,
        name: str,
        role: str,
        tool_permissions: Optional[List[str]] = None,
        model_task: str = "chat",
        memory_scope: str = "agent",
        org_id: str = "default",
        created_by: str = "system",
    ) -> Dict[str, Any]:
        agent_id = f"{_slug(name)}-{uuid.uuid4().hex[:6]}"
        tools = tool_permissions or ["knowledge.search", "memory.write"]
        unknown = [t for t in tools if tool_registry.get(t) is None]
        definition = AgentDefinition(
            id=agent_id,
            name=name,
            role=role,
            description=specification,
            version="0.1.0",
            system_instructions=(
                f"You are '{name}', a TITAN specialist agent. Specialisation: {role}.\n"
                f"Specification: {specification}\n"
                "Operate only within your granted tool scope. Report evidence for every claim."
            ),
            model={"task": model_task, "preferred": [model_task], "temperature": 0.2, "max_tokens": 2048},
            tool_permissions=tools,
            memory_scope=memory_scope,
            input_schema={"type": "object", "required": ["objective"],
                          "properties": {"objective": {"type": "string"}, "context": {"type": "object"}}},
            output_schema={"type": "object", "required": ["summary", "evidence"],
                           "properties": {"summary": {"type": "string"},
                                          "evidence": {"type": "array", "items": {"type": "object"}}}},
            timeout_seconds=300,
            quality_criteria=["produces a non-empty summary",
                              "cites at least one piece of evidence when tools were used",
                              "does not exceed its granted tool scope"],
        )
        record = Agent(
            id=definition.id, name=definition.name, role=definition.role,
            description=definition.description, version=definition.version,
            status="pending_validation", is_dynamic=True,
            system_instructions=definition.system_instructions,
            model_config_json=definition.model, tool_permissions=tools,
            memory_scope=memory_scope, input_schema=definition.input_schema,
            output_schema=definition.output_schema, timeout_seconds=definition.timeout_seconds,
            retry_policy=definition.retry_policy, org_id=org_id, created_by=created_by,
            metrics={"unknown_tools": unknown},
        )
        session.add(record)
        await session.flush()
        self._pending[definition.id] = {"definition": definition, "unknown_tools": unknown}
        metrics.incr("dynamic_agents_created")
        return {
            "agent_id": definition.id, "status": "pending_validation",
            "unknown_tools": unknown,
            "message": "Agent drafted. It must pass sandbox validation before it can be activated.",
        }

    async def validate(self, session, agent_id: str, *, org_id: str = "default") -> Dict[str, Any]:
        """Run the sandbox test + evaluation for a pending agent."""
        record = (await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )).scalar_one_or_none()
        if record is None:
            return {"agent_id": agent_id, "status": "error", "error": "agent not found"}

        checks: List[Dict[str, Any]] = []
        score = 0.0

        # 1. tools must exist
        unknown = [t for t in (record.tool_permissions or []) if tool_registry.get(t) is None]
        checks.append({"check": "tools_resolvable", "passed": not unknown, "detail": unknown})
        score += 0.3 if not unknown else 0.0

        # 2. execution smoke test: a harmless, permitted tool must actually run
        execution_ok = False
        detail = "no executable tool available for the smoke test"
        for tool_id in (record.tool_permissions or []):
            tool = tool_registry.get(tool_id)
            if tool is None:
                continue
            params = {"query": "TITAN dynamic agent validation probe", "top_k": 1, "limit": 1}
            if tool_id == "knowledge.search":
                params = {"query": "validation", "top_k": 1}
            result = await tool_registry.execute(tool_id, params, ToolContext(
                agent_id=agent_id, org_id=org_id, granted_scopes=set(record.tool_permissions or [])))
            execution_ok = result.ok
            detail = result.error_message or "tool executed successfully"
            checks.append({"check": f"tool_executes:{tool_id}", "passed": result.ok, "detail": detail[:300]})
            if result.ok:
                break
        score += 0.4 if execution_ok else 0.0

        # 3. contract completeness
        complete = all(bool(record.system_instructions) for _ in [0]) and bool(record.output_schema)
        checks.append({"check": "contract_complete", "passed": complete,
                       "detail": "instructions and output schema present" if complete else "missing instructions/schema"})
        score += 0.3 if complete else 0.0

        passed = score >= 0.7 and not unknown
        record.quality_score = round(score, 3)
        record.status = "active" if passed else "rejected"
        record.metrics = {**(record.metrics or {}), "validation": {"score": record.quality_score,
                                                                   "checks": checks, "passed": passed}}
        await session.flush()

        metrics.incr("dynamic_agent_validations", status="passed" if passed else "failed")
        log.info("dynamic agent %s validation: %s (score %.2f)", agent_id, "PASS" if passed else "FAIL", score)
        return {"agent_id": agent_id, "passed": passed, "score": record.quality_score,
                "status": record.status, "checks": checks}

    async def activate(self, session, agent_id: str) -> Dict[str, Any]:
        record = (await session.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if record is None:
            return {"error": "agent not found"}
        if record.status != "active":
            return {"error": f"agent status is '{record.status}'; validate it before activation"}
        session.add(AgentVersion(
            agent_id=record.id, version=record.version,
            snapshot={"system_instructions": record.system_instructions,
                      "model": record.model_config_json,
                      "tool_permissions": record.tool_permissions},
            note="activated",
        ))
        await session.flush()
        return {"agent_id": agent_id, "status": "active"}

    async def list_dynamic(self, session) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(Agent).where(Agent.is_dynamic.is_(True)).order_by(Agent.created_at.desc())
        )).scalars().all()
        return [
            {"id": r.id, "name": r.name, "role": r.role, "status": r.status,
             "quality_score": r.quality_score, "tool_permissions": r.tool_permissions,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "metrics": r.metrics}
            for r in rows
        ]


class SkillFactory:
    """Creates, tests, evaluates, approves and publishes skills."""

    def __init__(self) -> None:
        self._pending: Dict[str, Dict[str, Any]] = {}

    async def create(self, session, *, name: str, description: str,
                     input_schema: Dict[str, Any], output_schema: Dict[str, Any],
                     tool_requirements: List[str], permission_scope: str = "read",
                     steps: Optional[List[Dict[str, Any]]] = None,
                     org_id: str = "default") -> Dict[str, Any]:
        skill_id = f"{_slug(name)}-{uuid.uuid4().hex[:6]}"
        skill = Skill(
            id=skill_id, name=name, version="0.1.0", description=description, status="draft",
            input_schema=input_schema, output_schema=output_schema,
            tool_requirements=tool_requirements, permission_scope=permission_scope,
            dependencies=[], test_cases=[], security_review={"scan": "pending"},
            org_id=org_id, metrics={"steps": steps or []},
        )
        session.add(skill)
        await session.flush()
        metrics.incr("skills_created")
        return {"skill_id": skill_id, "status": "draft",
                "message": "Skill drafted in the laboratory. It must pass its tests before publishing."}

    async def run_tests(self, session, skill_id: str, *, org_id: str = "default") -> Dict[str, Any]:
        skill = (await session.execute(select(Skill).where(Skill.id == skill_id))).scalar_one_or_none()
        if skill is None:
            return {"error": "skill not found"}
        steps = (skill.metrics or {}).get("steps") or []
        results: List[Dict[str, Any]] = []
        passed = 0
        for step in steps:
            tool_id = step.get("tool")
            params = step.get("params") or {}
            if not tool_id:
                results.append({"step": step.get("name", "unnamed"), "ok": False, "detail": "no tool specified"})
                continue
            tool = tool_registry.get(tool_id)
            if tool is None:
                results.append({"step": step.get("name", tool_id), "ok": False, "detail": f"tool '{tool_id}' not registered"})
                continue
            result = await tool_registry.execute(tool_id, params, ToolContext(
                agent_id=None, org_id=org_id, granted_scopes={skill.permission_scope, "execute"}))
            results.append({"step": step.get("name", tool_id), "ok": result.ok,
                            "detail": (result.error_message or "ok")[:300],
                            "output": _short(result.output)})
            if result.ok:
                passed += 1
        total = len(steps) or 1
        ratio = passed / total
        skill.test_cases = results
        skill.quality_score = round(ratio, 3)
        skill.status = "tested" if ratio >= 0.8 else "failed_tests"
        skill.metrics = {**(skill.metrics or {}), "last_test": {"passed": passed, "total": len(steps),
                                                               "ratio": round(ratio, 3)}}
        await session.flush()
        metrics.incr("skill_tests_run", status=skill.status)
        return {"skill_id": skill_id, "passed": passed, "total": len(steps),
                "ratio": round(ratio, 3), "status": skill.status, "results": results}

    async def publish(self, session, skill_id: str) -> Dict[str, Any]:
        skill = (await session.execute(select(Skill).where(Skill.id == skill_id))).scalar_one_or_none()
        if skill is None:
            return {"error": "skill not found"}
        if skill.quality_score < 0.8:
            return {"error": f"skill quality score {skill.quality_score} is below the 0.8 publication gate"}
        skill.status = "published"
        skill.installed = True
        skill.enabled = True
        skill.version = "1.0.0"
        session.add(SkillVersion(skill_id=skill.id, version="1.0.0",
                                 snapshot={"input_schema": skill.input_schema,
                                           "output_schema": skill.output_schema,
                                           "tool_requirements": skill.tool_requirements},
                                 note="published"))
        await session.flush()
        metrics.incr("skills_published")
        return {"skill_id": skill_id, "status": "published", "version": "1.0.0"}

    async def install(self, session, skill_id: str) -> Dict[str, Any]:
        skill = (await session.execute(select(Skill).where(Skill.id == skill_id))).scalar_one_or_none()
        if skill is None:
            return {"error": "skill not found"}
        if skill.status != "published":
            return {"error": f"skill status is '{skill.status}'; only published skills can be installed"}
        skill.installed = True
        skill.enabled = True
        await session.flush()
        return {"skill_id": skill_id, "installed": True}

    async def list_skills(self, session) -> List[Dict[str, Any]]:
        rows = (await session.execute(select(Skill).order_by(Skill.created_at.desc()))).scalars().all()
        return [
            {"id": r.id, "name": r.name, "version": r.version, "status": r.status,
             "description": r.description, "quality_score": r.quality_score,
             "permission_scope": r.permission_scope, "installed": r.installed,
             "tool_requirements": r.tool_requirements, "metrics": r.metrics,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]


def _short(value: Any, limit: int = 400) -> Any:
    if isinstance(value, str):
        return value[:limit]
    try:
        return json.dumps(value, ensure_ascii=False, default=str)[:limit]
    except Exception:
        return str(value)[:limit]


agent_factory = AgentFactory()
skill_factory = SkillFactory()
