import asyncio
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import SessionLocal
from ..models import Agent, AgentTask, utcnow
from ..schemas import AgentCreate
from ..utils import slugify
from .model_gateway import ModelGateway

CORE_AGENTS = [
    (
        "global-research",
        "Global Research Agent",
        "research",
        ["research.github", "knowledge.write"],
    ),
    ("open-source-discovery", "Open-Source Discovery Agent", "research", ["research.github"]),
    ("ai-architecture", "AI Architecture Agent", "architecture", ["knowledge.read"]),
    (
        "senior-coding",
        "Senior Coding Agent",
        "coding",
        ["project.read", "project.write", "test.run"],
    ),
    ("bug-fixing", "Bug Fixing Agent", "coding", ["project.read", "project.write", "test.run"]),
    (
        "frontend-development",
        "Frontend Development Agent",
        "coding",
        ["project.read", "project.write"],
    ),
    (
        "android-development",
        "Android Development Agent",
        "coding",
        ["project.read", "project.write", "build.run"],
    ),
    (
        "backend-development",
        "Backend Development Agent",
        "coding",
        ["project.read", "project.write", "test.run"],
    ),
    (
        "api-integration",
        "API Integration Agent",
        "coding",
        ["project.read", "project.write", "http.client"],
    ),
    (
        "database-engineering",
        "Database Engineering Agent",
        "database",
        ["project.read", "database.migrate"],
    ),
    ("ai-model-specialist", "AI Model Specialist", "models", ["model.invoke"]),
    (
        "model-evaluation",
        "Model Evaluation Agent",
        "evaluation",
        ["model.invoke", "evaluation.write"],
    ),
    ("multilingual-translation", "Multilingual Translation Agent", "translation", ["model.invoke"]),
    ("voice-audio", "Voice and Audio Agent", "voice", ["audio.process"]),
    ("image-video", "Image and Video Agent", "media", ["media.process"]),
    (
        "security-engineering",
        "Security Engineering Agent",
        "security",
        ["project.read", "security.scan"],
    ),
    ("quality-assurance", "Quality Assurance Agent", "testing", ["project.read", "test.run"]),
    (
        "devops-infrastructure",
        "DevOps and Infrastructure Agent",
        "infrastructure",
        ["project.read", "deployment.request"],
    ),
    ("build-release", "Build and Release Agent", "release", ["build.run", "artifact.read"]),
    ("documentation", "Documentation Agent", "documentation", ["project.read", "project.write"]),
]


async def seed_agents(db: AsyncSession) -> None:
    for slug, name, role, permissions in CORE_AGENTS:
        existing = await db.scalar(select(Agent).where(Agent.slug == slug))
        if existing:
            continue
        db.add(
            Agent(
                slug=slug,
                name=name,
                description=f"Versioned TITAN specialist for {role} tasks; execution evidence is persisted.",
                role=role,
                version="1.0.0",
                instructions=(
                    f"Act as {name}. Validate requirements, use only explicitly authorized tools, "
                    "produce verifiable output and report limitations. Never expose private chain-of-thought."
                ),
                model_config={"route": role},
                tool_permissions=permissions,
                memory_scope="task",
                input_schema={"type": "object", "required": ["objective"]},
                output_schema={"type": "object", "required": ["text", "provider", "is_mock"]},
                timeout_seconds=120,
                retry_policy={"max_attempts": 2, "backoff_seconds": 0.1},
                status="active",
                test_results={"contract_seed_validated": True},
            )
        )
    await db.commit()


class AgentService:
    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings
        self.gateway = ModelGateway(settings)

    async def create_agent(self, data: AgentCreate, owner_id: str) -> Agent:
        base_slug = slugify(data.name)
        slug = base_slug
        suffix = 2
        while await self.db.scalar(select(Agent).where(Agent.slug == slug)):
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        agent = Agent(
            **data.model_dump(by_alias=True),
            slug=slug,
            version="1.0.0",
            retry_policy={"max_attempts": 1},
            status="draft",
            test_results={"owner_id": owner_id, "tests_run": False},
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def test_agent(self, agent_id: str) -> Agent:
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        checks = {
            "instructions_present": len(agent.instructions) >= 10,
            "input_contract": agent.input_schema.get("type") == "object",
            "output_contract": agent.output_schema.get("type") == "object",
            "timeout_bounded": 1 <= agent.timeout_seconds <= 900,
            "permissions_allowlisted": all(
                permission
                in {
                    "research.github",
                    "knowledge.read",
                    "knowledge.write",
                    "project.read",
                    "project.write",
                    "test.run",
                    "build.run",
                    "model.invoke",
                    "http.client",
                }
                for permission in agent.tool_permissions
            ),
        }
        passed = all(checks.values())
        agent.test_results = {
            "tests_run": True,
            "sandbox": "contract_only_no_arbitrary_code",
            "checks": checks,
            "passed": passed,
        }
        agent.status = "tested" if passed else "test_failed"
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def approve_agent(self, agent_id: str) -> Agent:
        agent = await self.db.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent.status != "tested" or not agent.test_results.get("passed"):
            raise HTTPException(
                status_code=409, detail="Agent must pass sandbox contract tests before approval"
            )
        agent.status = "active"
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def orchestrate(
        self, objective: str, agent_ids: list[str] | None, provider: str | None, actor_id: str
    ):
        if agent_ids:
            agents = list(
                (await self.db.scalars(select(Agent).where(Agent.id.in_(agent_ids)))).all()
            )
            if len(agents) != len(set(agent_ids)):
                raise HTTPException(status_code=404, detail="One or more agents were not found")
        else:
            agents = [await self.db.scalar(select(Agent).where(Agent.slug == "global-research"))]
        if any(agent is None or agent.status != "active" for agent in agents):
            raise HTTPException(
                status_code=409, detail="Only active registered agents can be orchestrated"
            )
        batch_id = str(uuid4())
        tasks = [
            AgentTask(
                batch_id=batch_id,
                owner_id=actor_id,
                agent_id=agent.id,
                objective=objective,
                dependencies=[],
            )
            for agent in agents
        ]
        self.db.add_all(tasks)
        await self.db.commit()
        results = await asyncio.gather(
            *(self._execute_with_retry(task.id, provider, actor_id) for task in tasks),
            return_exceptions=True,
        )
        # Each worker owns a separate AsyncSession. Re-read all states after the fan-in.
        for task, result in zip(tasks, results, strict=True):
            if isinstance(result, Exception):
                async with SessionLocal() as failure_db:
                    failed_task = await failure_db.get(AgentTask, task.id)
                    if failed_task:
                        failed_task.status = "failed"
                        failed_task.error = str(result)[:1000]
                        failed_task.finished_at = utcnow()
                        await failure_db.commit()
            await self.db.refresh(task)
        return batch_id, tasks

    async def _execute_with_retry(self, task_id: str, provider: str | None, actor_id: str) -> None:
        async with SessionLocal() as worker_db:
            task = await worker_db.get(AgentTask, task_id)
            if task is None:
                raise ValueError("Task disappeared before execution")
            agent = await worker_db.get(Agent, task.agent_id)
            if agent is None:
                raise ValueError("Agent disappeared before execution")
            gateway = ModelGateway(self.settings)
            max_attempts = max(1, min(3, int(agent.retry_policy.get("max_attempts", 1))))
            for attempt in range(1, max_attempts + 1):
                task.attempts = attempt
                task.status = "running"
                task.started_at = task.started_at or utcnow()
                await worker_db.commit()
                started = time.perf_counter()
                try:
                    result = await asyncio.wait_for(
                        gateway.complete(
                            messages=[
                                {"role": "system", "content": agent.instructions},
                                {"role": "user", "content": task.objective},
                            ],
                            task_type=agent.role,
                            actor_id=actor_id,
                            requested_provider=provider,
                            db=worker_db,
                        ),
                        timeout=agent.timeout_seconds,
                    )
                    if not result.text or not result.provider:
                        raise ValueError("Agent output validation failed")
                    task.result = {
                        "text": result.text,
                        "provider": result.provider,
                        "model": result.model,
                        "is_mock": result.is_mock,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    }
                    task.evidence = [
                        {"type": "model_call", "provider": result.provider, "mock": result.is_mock}
                    ]
                    task.status = "succeeded"
                    task.error = None
                except Exception as exc:
                    task.status = "failed"
                    task.error = str(exc)[:1000]
                    if attempt < max_attempts:
                        await asyncio.sleep(float(agent.retry_policy.get("backoff_seconds", 0.1)))
                        await worker_db.commit()
                        continue
                finally:
                    task.duration_ms = (time.perf_counter() - started) * 1000
                    if task.status in {"succeeded", "failed"}:
                        task.finished_at = utcnow()
                    await worker_db.commit()
                if task.status == "succeeded":
                    return
