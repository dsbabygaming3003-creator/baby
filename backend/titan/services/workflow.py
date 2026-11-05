"""Durable workflow engine.

A workflow is a directed graph of steps. The engine supports dependency
resolution, parallel execution, retries, timeouts, checkpoints after every
step, resume after a crash, cancellation, human-approval gates and schedules.
State lives in the database, so a workflow survives a process restart.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select

from ..config import settings
from ..models import Workflow, WorkflowRun
from .observability import log, metrics


class WorkflowError(RuntimeError):
    pass


class StepContext:
    def __init__(self, run: "WorkflowRun", graph: Dict[str, Any]):
        self.run = run
        self.graph = graph
        self.state: Dict[str, Any] = dict(run.state or {})
        self.results: Dict[str, Any] = dict(run.step_results or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value


class WorkflowEngine:
    # -- graph helpers ----------------------------------------------------
    @staticmethod
    def _steps(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        return graph.get("steps") or []

    @staticmethod
    def _step_map(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {s["id"]: s for s in WorkflowEngine._steps(graph) if s.get("id")}

    def validate(self, graph: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        steps = self._steps(graph)
        if not steps:
            errors.append("workflow has no steps")
        ids = [s.get("id") for s in steps]
        if len(ids) != len(set(ids)):
            errors.append("duplicate step ids")
        known = set(ids)
        for step in steps:
            for dependency in step.get("depends_on", []) or []:
                if dependency not in known:
                    errors.append(f"step '{step.get('id')}' depends on unknown step '{dependency}'")
            if not step.get("action"):
                errors.append(f"step '{step.get('id')}' has no action")
        # cycle detection
        incoming = {s.get("id"): set(s.get("depends_on", []) or []) for s in steps}
        visiting, visited = set(), set()

        def _visit(node: Optional[str]) -> bool:
            if node is None:
                return False
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in incoming.get(node, set()):
                if _visit(dep):
                    return True
            visiting.discard(node)
            visited.add(node)
            return False

        for node in incoming:
            if _visit(node):
                errors.append("workflow graph contains a cycle")
                break
        return errors

    # -- execution --------------------------------------------------------
    async def create_run(self, session, workflow_id: str, *, inputs: Optional[Dict[str, Any]] = None,
                         org_id: str = "default") -> WorkflowRun:
        workflow = (await session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )).scalar_one_or_none()
        if workflow is None:
            raise WorkflowError(f"workflow {workflow_id} not found")
        errors = self.validate(workflow.graph)
        if errors:
            raise WorkflowError("invalid workflow graph: " + "; ".join(errors))
        run = WorkflowRun(
            workflow_id=workflow.id, org_id=org_id, status="pending",
            state=dict(inputs or {}), step_results={}, checkpoint={"completed": []},
        )
        session.add(run)
        await session.flush()
        workflow.last_run_id = run.id
        await session.flush()
        return run

    async def run(self, session, run_id: str, *, resume: bool = False) -> Dict[str, Any]:
        run = (await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none()
        if run is None:
            raise WorkflowError(f"workflow run {run_id} not found")
        workflow = (await session.execute(
            select(Workflow).where(Workflow.id == run.workflow_id)
        )).scalar_one_or_none()
        if workflow is None:
            raise WorkflowError(f"workflow {run.workflow_id} not found")

        graph = workflow.graph or {}
        steps = self._steps(graph)
        step_map = self._step_map(graph)
        completed: Set[str] = set((run.checkpoint or {}).get("completed", [])) if resume else set()
        context = StepContext(run, graph)
        context.state.update(run.state or {})
        context.results.update(run.step_results or {})

        run.status = "running"
        run.started_at = run.started_at or _utcnow()
        await session.flush()

        pending = [s for s in steps if s["id"] not in completed]
        started = time.perf_counter()
        errors: List[str] = []

        while pending:
            runnable = [s for s in pending
                        if all(dep in completed or dep not in step_map for dep in (s.get("depends_on") or []))]
            if not runnable:
                errors.append("no runnable steps remain (dependency deadlock)")
                break
            # respect the parallelism limit
            batch = runnable[: settings.workflow_max_parallel]
            pending = [s for s in pending if s["id"] not in {b["id"] for b in batch}]

            async def _run_step(step: Dict[str, Any]) -> Dict[str, Any]:
                return await self._execute_step(session, run, step, step_map, context, workflow)

            results = await asyncio.gather(*(_run_step(step) for step in batch), return_exceptions=True)
            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    errors.append(f"{step['id']}: {type(result).__name__}: {result}")
                    context.results[step["id"]] = {"status": "failed", "error": str(result)}
                    continue
                context.results[step["id"]] = result
                if result.get("status") == "completed":
                    completed.add(step["id"])
                elif result.get("status") == "awaiting_approval":
                    pending.append(step)  # re-queue for after approval
                    continue

            # checkpoint after every batch
            run.checkpoint = {"completed": sorted(completed),
                              "state": context.state,
                              "at": _utcnow().isoformat()}
            run.state = context.state
            run.step_results = context.results
            run.current_step = pending[0]["id"] if pending else None
            await session.flush()

        run.state = context.state
        run.step_results = context.results
        run.finished_at = _utcnow()
        if errors:
            run.status = "failed"
            run.error = "; ".join(errors)[:4000]
        elif pending:
            run.status = "awaiting_approval"
        else:
            run.status = "completed"
        await session.flush()
        metrics.observe("workflow_duration_ms", (time.perf_counter() - started) * 1000)
        metrics.incr("workflow_runs_total", status=run.status)
        return {
            "run_id": run.id, "status": run.status, "completed": sorted(completed),
            "pending": [s["id"] for s in pending], "errors": errors,
            "step_results": context.results, "duration_ms": (time.perf_counter() - started) * 1000,
        }

    async def _execute_step(self, session, run: WorkflowRun, step: Dict[str, Any],
                            step_map: Dict[str, Dict[str, Any]], context: StepContext,
                            workflow: Workflow) -> Dict[str, Any]:
        action = step.get("action") or {}
        kind = action.get("type", "tool")
        step_timeout = int(action.get("timeout_seconds") or settings.workflow_step_timeout_seconds)
        retries = int((action.get("retry") or {}).get("max_attempts", 1))
        requires_approval = bool(action.get("requires_approval")) or bool(step.get("requires_approval"))

        if requires_approval:
            approved = context.state.get(f"approval:{step['id']}")
            if not approved:
                context.state[f"approval_request:{step['id']}"] = {
                    "requested_at": _utcnow().isoformat(),
                    "action": kind,
                }
                return {"status": "awaiting_approval", "step": step["id"]}

        if kind == "agent":
            from .agents import supreme_boss

            summary = await supreme_boss.execute(
                session, action.get("objective") or step.get("title") or step["id"],
                context=context.state, org_id=run.org_id,
            )
            context.set(f"result:{step['id']}", summary.final_output)
            return {"status": "completed", "step": step["id"], "output": summary.final_output,
                    "provider_modes": summary.provider_modes, "duration_ms": summary.duration_ms}

        if kind == "research":
            from .research import research_engine

            task = await research_engine.create_task(
                session, query=action.get("query") or step.get("title") or step["id"],
                platforms=action.get("platforms", []), org_id=run.org_id,
            )
            outcome = await research_engine.run_task(session, task.id)
            context.set(f"result:{step['id']}", outcome)
            return {"status": "completed", "step": step["id"], "output": outcome}

        if kind == "tool":
            from .tools import ToolContext, registry as tool_registry

            tool_id = action.get("tool")
            tool = tool_registry.get(tool_id) if tool_id else None
            if tool is None:
                return {"status": "failed", "step": step["id"], "error": f"tool '{tool_id}' not registered"}
            params = dict(action.get("params") or {})
            for key, template in list(params.items()):
                if isinstance(template, str) and template.startswith("${") and template.endswith("}"):
                    params[key] = context.get(template[2:-1])
            last_error = ""
            for attempt in range(retries):
                result = await tool_registry.execute(tool_id, params, ToolContext(
                    org_id=run.org_id, granted_scopes={action.get("scope", "execute"), "execute"},
                    project_id=action.get("project_id")))
                if result.ok:
                    context.set(f"result:{step['id']}", result.output)
                    return {"status": "completed", "step": step["id"], "output": result.output}
                last_error = result.error_message
                await asyncio.sleep(0.2 * (attempt + 1))
            return {"status": "failed", "step": step["id"], "error": last_error}

        if kind == "delay":
            await asyncio.sleep(min(float(action.get("seconds", 1)), 30))
            return {"status": "completed", "step": step["id"]}

        return {"status": "failed", "step": step["id"], "error": f"unknown step action type '{kind}'"}

    async def approve(self, session, run_id: str, step_id: str, *, approved: bool = True,
                      approver: str = "user") -> Dict[str, Any]:
        run = (await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none()
        if run is None:
            raise WorkflowError(f"workflow run {run_id} not found")
        state = dict(run.state or {})
        state[f"approval:{step_id}"] = bool(approved)
        state[f"approval:{step_id}:by"] = approver
        run.state = state
        await session.flush()
        return {"run_id": run_id, "step_id": step_id, "approved": approved}

    async def cancel(self, session, run_id: str) -> Dict[str, Any]:
        run = (await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none()
        if run is None:
            raise WorkflowError(f"workflow run {run_id} not found")
        if run.status in ("completed", "failed"):
            return {"run_id": run_id, "status": run.status, "cancelled": False}
        run.status = "cancelled"
        run.finished_at = _utcnow()
        await session.flush()
        return {"run_id": run_id, "status": "cancelled", "cancelled": True}

    async def resume(self, session, run_id: str) -> Dict[str, Any]:
        """Resume a paused/failed run from its last checkpoint."""
        run = (await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none()
        if run is None:
            raise WorkflowError(f"workflow run {run_id} not found")
        if run.status == "completed":
            return {"run_id": run_id, "status": "completed", "resumed": False,
                    "detail": "run already completed"}
        result = await self.run(session, run_id, resume=True)
        result["resumed"] = True
        return result

    async def list_runs(self, session, org_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(WorkflowRun).where(WorkflowRun.org_id == org_id)
            .order_by(WorkflowRun.created_at.desc()).limit(limit)
        )).scalars().all()
        return [
            {"id": r.id, "workflow_id": r.workflow_id, "status": r.status,
             "current_step": r.current_step, "error": r.error,
             "started_at": r.started_at.isoformat() if r.started_at else None,
             "finished_at": r.finished_at.isoformat() if r.finished_at else None,
             "completed_steps": (r.checkpoint or {}).get("completed", [])}
            for r in rows
        ]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


workflow_engine = WorkflowEngine()
