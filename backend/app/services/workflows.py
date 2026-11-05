import asyncio
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import SessionLocal
from ..models import Workflow, WorkflowRun, utcnow
from ..schemas import WorkflowCreate
from .model_gateway import ModelGateway
from .skills import execute_handler


class WorkflowService:
    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings

    async def create(self, owner_id: str, data: WorkflowCreate) -> Workflow:
        definition = {"steps": data.steps}
        self._validate_acyclic(data.steps)
        workflow = Workflow(owner_id=owner_id, name=data.name, definition=definition)
        self.db.add(workflow)
        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    @staticmethod
    def _validate_acyclic(steps: list[dict[str, Any]]) -> None:
        graph = {step["id"]: step.get("depends_on", []) for step in steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise HTTPException(
                    status_code=422, detail="Workflow dependency graph contains a cycle"
                )
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    async def start(self, workflow_id: str, owner_id: str) -> WorkflowRun:
        workflow = await self.db.scalar(
            select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == owner_id)
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        run = WorkflowRun(workflow_id=workflow.id)
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def run(self, run_id: str, actor_id: str) -> WorkflowRun:
        async with SessionLocal() as db:
            run = await db.get(WorkflowRun, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Workflow run not found")
            workflow = await db.get(Workflow, run.workflow_id)
            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")
            run.status = "running"
            run.error = None
            await db.commit()
            steps = {step["id"]: step for step in workflow.definition["steps"]}
            completed = set(run.checkpoints)
            try:
                while len(completed) < len(steps):
                    await db.refresh(run)
                    if run.cancellation_requested:
                        run.status = "cancelled"
                        run.logs = [
                            *run.logs,
                            {"at": utcnow().isoformat(), "event": "cancellation_honored"},
                        ]
                        await db.commit()
                        return run
                    ready = [
                        step
                        for step in steps.values()
                        if step["id"] not in completed
                        and set(step.get("depends_on", [])).issubset(completed)
                    ]
                    if not ready:
                        raise RuntimeError("No resumable steps; dependency graph is stuck")
                    results = await asyncio.gather(
                        *(self._execute_step(step, actor_id) for step in ready),
                        return_exceptions=True,
                    )
                    checkpoints = dict(run.checkpoints)
                    logs = list(run.logs)
                    failure = None
                    for step, result in zip(ready, results, strict=True):
                        if isinstance(result, Exception):
                            failure = f"Step {step['id']}: {str(result)[:500]}"
                            logs.append(
                                {
                                    "at": utcnow().isoformat(),
                                    "step": step["id"],
                                    "status": "failed",
                                    "error": str(result)[:500],
                                }
                            )
                        else:
                            checkpoints[step["id"]] = result
                            completed.add(step["id"])
                            logs.append(
                                {
                                    "at": utcnow().isoformat(),
                                    "step": step["id"],
                                    "status": "succeeded",
                                }
                            )
                    run.checkpoints = checkpoints
                    run.logs = logs
                    run.current_step = None
                    if failure:
                        run.status = "failed"
                        run.error = failure
                        await db.commit()
                        return run
                    await db.commit()  # durable checkpoint after each parallel level
                run.status = "succeeded"
                run.current_step = None
                await db.commit()
            except Exception as exc:
                run.status = "failed"
                run.error = str(exc)[:1000]
                run.current_step = None
                await db.commit()
            await db.refresh(run)
            return run

    async def _execute_step(self, step: dict[str, Any], actor_id: str) -> dict[str, Any]:
        step_type = step["type"]
        config = step.get("config", {})
        if step_type == "text_stats":
            return {
                "type": step_type,
                "output": execute_handler("text_stats", {"text": config.get("text", "")}),
            }
        if step_type == "delay":
            seconds = float(config.get("seconds", 0.05))
            if not 0 <= seconds <= 2:
                raise ValueError("Delay must be between 0 and 2 seconds")
            await asyncio.sleep(seconds)
            return {"type": step_type, "output": {"delayed_seconds": seconds}}
        if step_type == "model":
            gateway = ModelGateway(self.settings)
            result = await gateway.complete(
                messages=[{"role": "user", "content": str(config.get("prompt", ""))}],
                task_type="workflow",
                actor_id=actor_id,
                requested_provider=config.get("provider"),
                db=None,
            )
            return {
                "type": step_type,
                "output": {
                    "text": result.text,
                    "provider": result.provider,
                    "model": result.model,
                    "is_mock": result.is_mock,
                },
            }
        raise ValueError(f"Unsupported step type: {step_type}")

    async def cancel(self, run_id: str, owner_id: str) -> WorkflowRun:
        run = await self.db.scalar(
            select(WorkflowRun)
            .join(Workflow, Workflow.id == WorkflowRun.workflow_id)
            .where(WorkflowRun.id == run_id, Workflow.owner_id == owner_id)
        )
        if not run:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        if run.status in {"succeeded", "failed", "cancelled"}:
            return run
        run.cancellation_requested = True
        run.status = "cancelling"
        await self.db.commit()
        await self.db.refresh(run)
        return run
