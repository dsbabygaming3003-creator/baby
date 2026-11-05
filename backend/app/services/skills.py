import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Skill
from ..schemas import SkillCreate
from ..utils import slugify

HANDLERS = {"text_stats", "source_summary", "json_keys"}


def validate_object(schema: dict[str, Any], value: dict[str, Any]) -> None:
    if not schema:
        return
    if schema.get("type", "object") != "object":
        raise ValueError("Only object input/output schemas are supported")
    required = schema.get("required", [])
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    types = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, definition in schema.get("properties", {}).items():
        if key in value and "type" in definition:
            expected = types.get(definition["type"])
            if expected and not isinstance(value[key], expected):
                raise ValueError(f"Field {key} must be {definition['type']}")


def execute_handler(handler: str, data: dict[str, Any]) -> dict[str, Any]:
    if handler == "text_stats":
        text = data.get("text", "")
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        return {
            "characters": len(text),
            "words": len(text.split()),
            "lines": len(text.splitlines()),
        }
    if handler == "source_summary":
        sources = data.get("sources", [])
        if not isinstance(sources, list) or any(not isinstance(item, str) for item in sources):
            raise ValueError("sources must be a list of strings")
        return {"source_count": len(sources), "sources": sorted(set(sources))}
    if handler == "json_keys":
        value = data.get("value", {})
        if not isinstance(value, dict):
            raise ValueError("value must be an object")
        return {"keys": sorted(value.keys()), "count": len(value)}
    raise ValueError("Handler is not registered")


class SkillService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: str, data: SkillCreate) -> Skill:
        skill = Skill(
            owner_id=owner_id,
            slug=slugify(data.name),
            **data.model_dump(),
            status="draft",
            security_review={
                "arbitrary_code_allowed": False,
                "handler_allowlist": sorted(HANDLERS),
                "review_status": "automated_manifest_checks_only",
            },
        )
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def sandbox_test(self, skill_id: str, owner_id: str) -> Skill:
        skill = await self._get(skill_id, owner_id)
        samples = {
            "text_stats": {"text": "TITAN verified skill test"},
            "source_summary": {"sources": ["https://github.com/example/project"]},
            "json_keys": {"value": {"verified": True}},
        }
        checks = {}
        try:
            validate_object(skill.input_schema, samples[skill.handler])
            output = execute_handler(skill.handler, samples[skill.handler])
            validate_object(skill.output_schema, output)
            json.dumps(output)
            checks = {
                "input_schema": True,
                "handler_executed": True,
                "output_schema": True,
                "json_serializable": True,
            }
            passed = True
            error = None
        except Exception as exc:
            passed = False
            error = str(exc)[:500]
            checks = {"handler_executed": False}
        skill.test_results = {
            "sandbox": "isolated_pure_python_allowlisted_handler_no_io",
            "checks": checks,
            "passed": passed,
            "error": error,
        }
        skill.status = "tested" if passed else "test_failed"
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def approve(self, skill_id: str, owner_id: str) -> Skill:
        skill = await self._get(skill_id, owner_id)
        if skill.status != "tested" or not skill.test_results.get("passed"):
            raise HTTPException(
                status_code=409, detail="Skill must pass sandbox tests before publication"
            )
        skill.status = "active"
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def disable(self, skill_id: str, owner_id: str) -> Skill:
        skill = await self._get(skill_id, owner_id)
        skill.status = "disabled"
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def execute(self, skill_id: str, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        skill = await self._get(skill_id, owner_id)
        if skill.status != "active":
            raise HTTPException(status_code=409, detail="Only approved active skills can execute")
        validate_object(skill.input_schema, data)
        output = execute_handler(skill.handler, data)
        validate_object(skill.output_schema, output)
        skill.execution_count += 1
        await self.db.commit()
        return {
            "skill_id": skill.id,
            "version": skill.version,
            "output": output,
            "sandbox": "pure_python_no_io",
        }

    async def _get(self, skill_id: str, owner_id: str) -> Skill:
        skill = await self.db.scalar(
            select(Skill).where(Skill.id == skill_id, Skill.owner_id == owner_id)
        )
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill
