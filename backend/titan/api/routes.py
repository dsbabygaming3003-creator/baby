"""TITAN OMEGA INFINITY — HTTP API (`/api/v1`).

Every endpoint returns live data. Where a dependency (provider, connector,
device) is unavailable, the response carries an explicit status instead of a
fabricated success.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..models import (
    Agent,
    AgentRun,
    AgentTask,
    AuditLog,
    BuildJob,
    Conversation,
    KnowledgeDocument,
    Message,
    ModelEvaluation,
    Project,
    ResearchTask,
    Skill,
    ToolExecution,
    User,
    Workflow,
    WorkflowRun,
)
from ..security.core import Principal, create_jwt, hash_api_key, hash_password, verify_password
from ..services.agents import supreme_boss
from ..services.factory import agent_factory, skill_factory
from ..services.gateway import CompletionRequest, gateway
from ..services.media import (
    build_service,
    evaluation_service,
    translation_service,
    voice_service,
)
from ..services.memory import memory
from ..services.observability import audit, metrics, set_correlation_id
from ..services.rag import retriever
from ..services.research import research_engine
from ..services.research_connectors import probe_connectors
from ..services.sandbox import backend as sandbox_backend
from ..services.tools import registry as tool_registry
from ..services.workflow import workflow_engine
from .deps import current_principal, require_scope

router = APIRouter()


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
@router.get("/system/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "edition": settings.edition,
        "env": settings.env,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Live capability report — the anti-fake contract of the platform."""
    from ..services.sandbox import DockerBackend

    try:
        import shutil as _shutil

        toolchain = Path(os.environ.get("TITAN_TOOLCHAIN_DIR", "/opt/titan/toolchain"))
        aapt2 = _shutil.which("aapt2") or (str(toolchain / "build-tools" / "aapt2")
                                          if (toolchain / "build-tools" / "aapt2").exists() else None)
        java = _shutil.which("java") or (str(toolchain / "jdk" / "bin" / "java")
                                         if (toolchain / "jdk" / "bin" / "java").exists() else None)
        kotlinc = _shutil.which("kotlinc") or (
            str(toolchain / "kotlinc" / "bin" / "kotlinc")
            if (toolchain / "kotlinc" / "bin" / "kotlinc").exists() else None)
        d8_jar = toolchain / "d8" / "d8.jar"
        apksigner_jar = toolchain / "build-tools" / "apksigner.jar"
        android_jar = toolchain / "platforms" / "android-35" / "android.jar"

        def _is_runnable_d8(path: Path) -> bool:
            """A dexer is only 'present' if the Java entry point really exists.

            The npm `d8-termux` artifact is an Android-native binary, not a Java
            archive; zip-listing it is the cheap, honest way to tell them apart.
            """
            if not path.exists():
                return False
            try:
                import zipfile

                with zipfile.ZipFile(path) as zf:
                    names = set(zf.namelist())
                return "com/android/tools/r8/D8.class" in names
            except Exception:
                return False

        d8_runnable = _is_runnable_d8(d8_jar)
        apksigner_present = apksigner_jar.exists()
    except Exception:
        aapt2 = kotlinc = java = None
        d8_jar = android_jar = Path("")
        d8_runnable = apksigner_present = False

    def cap(state: str, detail: str, **extra):
        payload = {"status": state, "detail": detail}
        payload.update(extra)
        return payload

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": {
            "backend_api": cap("available", "FastAPI application is serving"),
            "database": cap("available", f"{settings.resolved_database_url.split('://')[0]} profile"),
            "model_gateway": cap("available", "gateway online; provider reachability reported separately",
                                 providers=await gateway.probe_providers()),
            "research_connectors": cap("available", "connector registry online",
                                       connectors=await probe_connectors()),
            "sandbox": cap("available",
                           "docker backend" if DockerBackend.available() else "process-isolation backend",
                           command_allowlist_size=len(settings.command_allowlist)),
            "android_build_toolchain": cap(
                "available" if (aapt2 and java and d8_runnable and android_jar.exists()) else "blocked",
                f"aapt2={'yes' if aapt2 else 'no'} java={'yes' if java else 'no'} "
                f"kotlinc={'yes' if kotlinc else 'no'} "
                f"d8={'yes' if d8_runnable else 'no'} "
                f"apksigner={'yes' if apksigner_present else 'no'} "
                f"android.jar={'yes' if android_jar.exists() else 'no'}",
                d8_version="D8 (Google R8) 8.2.2-dev" if d8_runnable else None,
                apk_pipeline="aapt2 -> kotlinc -> d8 -> zip -> apksigner (v1+v2+v3)"),
            "device_install_test": cap("blocked", "no emulator or adb device is attached to this host"),
            "voice_asr_server": cap("degraded", "no ASR engine binary installed; Android client uses on-device ASR"),
            "voice_tts_server": cap("degraded", "no TTS engine binary installed; Android client uses on-device TTS"),
            "translation": cap("available", "detection is local; translation requires a configured provider"),
            "model_training": cap("degraded", "dataset preparation implemented; no training runtime installed"),
            "browser_automation": cap("blocked", "no browser engine available in this deployment"),
        },
    }


@router.get("/system/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    return metrics.render()


@router.get("/system/audit")
async def audit_log(principal: Principal = Depends(require_scope("admin")),
                    session: AsyncSession = Depends(get_session),
                    limit: int = 100) -> Dict[str, Any]:
    rows = (await session.execute(
        select(AuditLog).where(AuditLog.org_id == principal.org_id)
        .order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    )).scalars().all()
    return {
        "entries": [
            {"id": r.id, "action": r.action, "actor_id": r.actor_id, "actor_role": r.actor_role,
             "target_type": r.target_type, "target_id": r.target_id, "outcome": r.outcome,
             "correlation_id": r.correlation_id, "detail": r.detail,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
auth_router = APIRouter()


@auth_router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(payload: Dict[str, Any], session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if "@" not in email or len(password) < 8:
        raise HTTPException(status_code=400, detail="a valid email and an 8+ character password are required")
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="an account with this email already exists")
    # A self-registration may never mint an administrative role. The very
    # first account of an installation becomes the owner.
    requested_role = (payload.get("role") or "researcher").lower()
    if requested_role not in {"researcher", "developer", "viewer"}:
        requested_role = "researcher"
    user_count = len((await session.execute(select(User.id))).all())
    role = "owner" if user_count == 0 else requested_role
    user = User(
        email=email, display_name=payload.get("display_name") or email.split("@")[0],
        password_hash=hash_password(password), role=role,
        org_id=payload.get("org_id") or "default", locale=payload.get("locale") or "en",
    )
    session.add(user)
    await session.flush()
    await audit(session, action="auth.register", actor_id=user.id, actor_role=user.role,
               org_id=user.org_id, target_type="user", target_id=user.id)
    token = create_jwt({"sub": user.id, "org": user.org_id, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(user)}


@auth_router.post("/auth/login")
async def login(payload: Dict[str, Any], session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    email = (payload.get("email") or "").strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.get("password") or "", user.password_hash):
        await audit(session, action="auth.login", outcome="denied", detail={"email": email})
        raise HTTPException(status_code=401, detail="invalid email or password")
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    await audit(session, action="auth.login", actor_id=user.id, actor_role=user.role, org_id=user.org_id)
    token = create_jwt({"sub": user.id, "org": user.org_id, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(user)}


@auth_router.get("/auth/me")
async def me(principal: Principal = Depends(current_principal),
              session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    user = (await session.execute(select(User).where(User.id == principal.user_id))).scalar_one_or_none()
    return {"principal": {"user_id": principal.user_id, "org_id": principal.org_id,
                          "role": principal.role, "scopes": sorted(principal.scopes)},
            "user": _user_payload(user) if user else None}


def _user_payload(user: Optional[User]) -> Optional[Dict[str, Any]]:
    if user is None:
        return None
    return {"id": user.id, "email": user.email, "display_name": user.display_name,
            "role": user.role, "locale": user.locale, "org_id": user.org_id,
            "created_at": user.created_at.isoformat() if user.created_at else None}


# ---------------------------------------------------------------------------
# Chat studio
# ---------------------------------------------------------------------------
@router.get("/chat/conversations")
async def list_conversations(principal: Principal = Depends(require_scope("read")),
                             session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(
        select(Conversation).where(Conversation.org_id == principal.org_id)
        .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()).limit(200)
    )).scalars().all()
    return {"conversations": [
        {"id": c.id, "title": c.title, "project_id": c.project_id, "agent_id": c.agent_id,
         "language": c.language, "archived": c.archived, "pinned": c.pinned,
         "message_count": c.message_count,
         "created_at": c.created_at.isoformat() if c.created_at else None,
         "updated_at": c.updated_at.isoformat() if c.updated_at else None}
        for c in rows]}


@router.post("/chat/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: Dict[str, Any],
                              principal: Principal = Depends(require_scope("write")),
                              session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    conversation = Conversation(
        title=payload.get("title") or "New chat", org_id=principal.org_id,
        project_id=payload.get("project_id"), agent_id=payload.get("agent_id"),
        language=payload.get("language") or "en",
    )
    session.add(conversation)
    await session.flush()
    await audit(session, action="chat.conversation.create", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id,
               target_type="conversation", target_id=conversation.id)
    return {"id": conversation.id, "title": conversation.title}


@router.get("/chat/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str, principal: Principal = Depends(require_scope("read")),
                         session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(
        select(Message).where(Message.conversation_id == conversation_id,
                              Message.org_id == principal.org_id)
        .order_by(Message.created_at.asc()).limit(500)
    )).scalars().all()
    return {"messages": [
        {"id": m.id, "role": m.role, "content": m.content, "citations": m.citations,
         "tool_activity": m.tool_activity, "model_id": m.model_id,
         "provider_mode": m.provider_mode, "tokens_in": m.tokens_in, "tokens_out": m.tokens_out,
         "latency_ms": m.latency_ms,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in rows]}


@router.post("/chat/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(conversation_id: str, payload: Dict[str, Any],
                       principal: Principal = Depends(require_scope("write")),
                       session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="message content is required")
    conversation = (await session.execute(
        select(Conversation).where(Conversation.id == conversation_id,
                                   Conversation.org_id == principal.org_id)
    )).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    user_message = Message(conversation_id=conversation_id, role="user", content=content,
                            org_id=principal.org_id, model_id=payload.get("model"))
    session.add(user_message)
    await session.flush()

    history = (await session.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc()).limit(30)
    )).scalars().all()
    messages = [{"role": m.role, "content": m.content} for m in history]

    result = await gateway.complete(CompletionRequest(
        messages=messages, model=payload.get("model"),
        task=payload.get("task") or "chat", max_tokens=int(payload.get("max_tokens") or 2048)))

    assistant_message = Message(
        conversation_id=conversation_id, role="assistant", content=result.text,
        org_id=principal.org_id, model_id=result.model, provider_mode=result.provider_mode,
        tokens_in=result.tokens_in, tokens_out=result.tokens_out, latency_ms=result.latency_ms,
        tool_activity=payload.get("tool_activity") or [], citations=payload.get("citations") or [],
    )
    session.add(assistant_message)
    conversation.message_count = (conversation.message_count or 0) + 2
    await session.flush()
    await audit(session, action="chat.message", actor_id=principal.user_id, actor_role=principal.role,
               org_id=principal.org_id, target_type="conversation", target_id=conversation_id,
               detail={"provider_mode": result.provider_mode, "model": result.model})
    return {"id": assistant_message.id, "content": result.text, "model": result.model,
            "provider_id": result.provider_id, "provider_mode": result.provider_mode,
            "tokens_in": result.tokens_in, "tokens_out": result.tokens_out,
            "latency_ms": round(result.latency_ms, 2), "cost_usd": result.cost_usd,
            "error": result.error}


@router.get("/chat/stream")
async def stream_chat(request: Request, q: str, conversation_id: Optional[str] = None,
                      model: Optional[str] = None,
                      principal: Principal = Depends(require_scope("write"))) -> StreamingResponse:
    """Server-sent events stream of the assistant reply."""

    async def generator():
        payload = CompletionRequest(messages=[{"role": "user", "content": q}], model=model, task="chat")
        result = await gateway.complete(payload)
        yield f"event: meta\ndata: {json.dumps({'model': result.model, 'provider_mode': result.provider_mode})}\n\n"
        if result.error:
            yield f"event: error\ndata: {json.dumps({'error': result.error})}\n\n"
            return
        step = 48
        for index in range(0, len(result.text), step):
            yield f"event: delta\ndata: {json.dumps({'text': result.text[index:index + step]})}\n\n"
        yield f"event: done\ndata: {json.dumps({'tokens_in': result.tokens_in, 'tokens_out': result.tokens_out, 'cost_usd': result.cost_usd})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.patch("/chat/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, payload: Dict[str, Any],
                               principal: Principal = Depends(require_scope("write")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    conversation = (await session.execute(
        select(Conversation).where(Conversation.id == conversation_id,
                                   Conversation.org_id == principal.org_id)
    )).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    for field in ("title", "archived", "pinned", "language", "agent_id", "project_id"):
        if field in payload:
            setattr(conversation, field, payload[field])
    await session.flush()
    return {"id": conversation.id, "updated": True}


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str,
                               principal: Principal = Depends(require_scope("write")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    conversation = (await session.execute(
        select(Conversation).where(Conversation.id == conversation_id,
                                   Conversation.org_id == principal.org_id)
    )).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    await session.delete(conversation)
    await session.flush()
    return {"deleted": True, "id": conversation_id}


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
@router.get("/agents")
async def list_agents(principal: Principal = Depends(require_scope("read")),
                      session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(select(Agent).order_by(Agent.name))).scalars().all()
    return {"agents": [
        {"id": a.id, "name": a.name, "role": a.role, "description": a.description,
         "version": a.version, "status": a.status, "is_dynamic": a.is_dynamic,
         "tool_permissions": a.tool_permissions, "memory_scope": a.memory_scope,
         "model": a.model_config_json, "quality_score": a.quality_score,
         "metrics": a.metrics,
         "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in rows]}


@router.get("/agents/{agent_id}")
async def agent_detail(agent_id: str, principal: Principal = Depends(require_scope("read")),
                       session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    agent = (await session.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    runs = (await session.execute(
        select(AgentRun).where(AgentRun.agent_id == agent_id)
        .order_by(AgentRun.created_at.desc()).limit(20)
    )).scalars().all()
    return {
        "id": agent.id, "name": agent.name, "role": agent.role, "description": agent.description,
        "system_instructions": agent.system_instructions, "model": agent.model_config_json,
        "tool_permissions": agent.tool_permissions, "memory_scope": agent.memory_scope,
        "input_schema": agent.input_schema, "output_schema": agent.output_schema,
        "timeout_seconds": agent.timeout_seconds, "retry_policy": agent.retry_policy,
        "status": agent.status, "quality_score": agent.quality_score, "metrics": agent.metrics,
        "runs": [{"id": r.id, "status": r.status, "duration_ms": r.duration_ms,
                  "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "cost_usd": r.cost_usd,
                  "quality_score": r.quality_score, "error": r.error,
                  "created_at": r.created_at.isoformat() if r.created_at else None} for r in runs],
    }


@router.post("/agents/run", status_code=status.HTTP_201_CREATED)
async def run_agent_task(payload: Dict[str, Any],
                          principal: Principal = Depends(require_scope("agents")),
                          session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    objective = (payload.get("objective") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    agent = (await session.execute(select(Agent).where(Agent.id == payload.get("agent_id")))).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    from ..agents.definitions import AGENT_INDEX
    from ..services.agents import bossman

    definition = AGENT_INDEX.get(agent.id)
    if definition is None:
        from ..agents.definitions import AgentDefinition

        definition = AgentDefinition(
            id=agent.id, name=agent.name, role=agent.role, description=agent.description,
            version=agent.version, system_instructions=agent.system_instructions,
            model=agent.model_config_json or {}, tool_permissions=agent.tool_permissions or [],
            memory_scope=agent.memory_scope, input_schema=agent.input_schema or {},
            output_schema=agent.output_schema or {}, timeout_seconds=agent.timeout_seconds,
            retry_policy=agent.retry_policy or {},
        )
    task = AgentTask(agent_id=agent.id, title=objective[:200], objective=objective,
                     input_payload=payload.get("context") or {}, org_id=principal.org_id,
                     status="running")
    session.add(task)
    await session.flush()
    result = await bossman.run_agent(session, definition, objective,
                                     context=payload.get("context") or {}, org_id=principal.org_id)
    task.status = "completed" if result["status"] == "completed" else "failed"
    task.result = result
    await session.flush()
    await audit(session, action="agent.run", actor_id=principal.user_id, actor_role=principal.role,
               org_id=principal.org_id, target_type="agent", target_id=agent.id)
    return result


@router.post("/agents/factory", status_code=status.HTTP_201_CREATED)
async def create_dynamic_agent(payload: Dict[str, Any],
                                principal: Principal = Depends(require_scope("agents")),
                                session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    result = await agent_factory.create(
        session, specification=payload.get("specification", ""), name=payload["name"],
        role=payload.get("role", "custom"), tool_permissions=payload.get("tool_permissions"),
        model_task=payload.get("model_task", "chat"), org_id=principal.org_id,
        created_by=principal.user_id)
    await audit(session, action="agent.factory.create", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id, target_type="agent",
               target_id=result["agent_id"])
    return result


@router.post("/agents/factory/{agent_id}/validate")
async def validate_dynamic_agent(agent_id: str,
                                  principal: Principal = Depends(require_scope("agents")),
                                  session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    result = await agent_factory.validate(session, agent_id, org_id=principal.org_id)
    await audit(session, action="agent.factory.validate", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id, target_type="agent",
               target_id=agent_id, outcome="ok" if result.get("passed") else "failed")
    return result


@router.get("/agents/factory/dynamic")
async def list_dynamic_agents(principal: Principal = Depends(require_scope("read")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"agents": await agent_factory.list_dynamic(session)}


# ---------------------------------------------------------------------------
# Research center
# ---------------------------------------------------------------------------
@router.get("/research/connectors")
async def list_connectors(principal: Principal = Depends(require_scope("read")),
                           session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"connectors": await research_engine.list_connectors(session)}


@router.get("/research/connectors/probe")
async def probe(principal: Principal = Depends(require_scope("research"))) -> Dict[str, Any]:
    return {"results": await probe_connectors()}


@router.post("/research/tasks", status_code=status.HTTP_201_CREATED)
async def create_research_task(payload: Dict[str, Any],
                               principal: Principal = Depends(require_scope("research")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    query = (payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    task = await research_engine.create_task(
        session, query=query, platforms=payload.get("platforms") or [],
        agent_id=payload.get("agent_id"), org_id=principal.org_id,
        topic=payload.get("topic", ""))
    await audit(session, action="research.task.create", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id, target_type="research_task",
               target_id=task.id)
    return {"task_id": task.id, "status": task.status}


@router.post("/research/tasks/{task_id}/run")
async def run_research_task(task_id: str, principal: Principal = Depends(require_scope("research")),
                            session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    result = await research_engine.run_task(session, task_id)
    await audit(session, action="research.task.run", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id, target_type="research_task",
               target_id=task_id)
    return result


@router.get("/research/tasks")
async def list_research_tasks(principal: Principal = Depends(require_scope("read")),
                              session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(
        select(ResearchTask).where(ResearchTask.org_id == principal.org_id)
        .order_by(ResearchTask.created_at.desc()).limit(100)
    )).scalars().all()
    return {"tasks": [
        {"id": t.id, "query": t.query, "topic": t.topic, "status": t.status,
         "platforms": t.platforms, "findings_count": t.findings_count,
         "connectors_ok": t.connectors_ok, "connectors_failed": t.connectors_failed,
         "report_path": t.report_path,
         "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in rows]}


@router.get("/research/tasks/{task_id}")
async def research_task_detail(task_id: str, principal: Principal = Depends(require_scope("read")),
                                session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    task = (await session.execute(
        select(ResearchTask).where(ResearchTask.id == task_id,
                                   ResearchTask.org_id == principal.org_id)
    )).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="research task not found")
    return {
        "task": {"id": task.id, "query": task.query, "status": task.status, "progress": task.progress,
                 "report_path": task.report_path, "error": task.error},
        "sources": await research_engine.list_sources(session, task_id),
        "documents": await research_engine.list_documents(session, task_id),
        "findings": await research_engine.list_findings(session, task_id),
    }


@router.post("/research/documents/{document_id}/ingest")
async def ingest_document(document_id: str, principal: Principal = Depends(require_scope("research")),
                           session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    knowledge = await research_engine.ingest_to_knowledge(session, document_id, org_id=principal.org_id)
    if knowledge is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"knowledge_document_id": knowledge.id, "status": "ingested"}


# ---------------------------------------------------------------------------
# Knowledge / memory
# ---------------------------------------------------------------------------
@router.get("/knowledge/search")
async def knowledge_search(q: str, top_k: int = 8,
                           principal: Principal = Depends(require_scope("read")),
                           session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    chunks = await retriever.retrieve(session, q, top_k=top_k, org_id=principal.org_id)
    return {"query": q, "results": [c.to_dict() for c in chunks]}


@router.get("/memory")
async def list_memory(scope: Optional[str] = None, scope_key: Optional[str] = None,
                       principal: Principal = Depends(require_scope("read")),
                       session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    entries = await memory.list(session, scope=scope, scope_key=scope_key, org_id=principal.org_id)
    return {"entries": [
        {"id": e.id, "scope": e.scope, "scope_key": e.scope_key, "kind": e.kind, "content": e.content,
         "importance": e.importance, "confidence": e.confidence, "source": e.source,
         "version": e.version, "created_at": e.created_at.isoformat() if e.created_at else None}
        for e in entries]}


@router.post("/memory", status_code=status.HTTP_201_CREATED)
async def create_memory(payload: Dict[str, Any],
                         principal: Principal = Depends(require_scope("memory")),
                         session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    try:
        entry = await memory.write(
            session, scope=payload.get("scope", "user"), content=content,
            kind=payload.get("kind", "note"), scope_key=payload.get("scope_key", ""),
            org_id=principal.org_id, importance=float(payload.get("importance", 0.5)),
            confidence=float(payload.get("confidence", 0.5)), source=payload.get("source", "user"),
            ttl_days=payload.get("ttl_days"))
    except ValueError as exc:
        # unknown memory scope / bad numeric field -> a client error, not a 500
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": entry.id, "scope": entry.scope, "version": entry.version}


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, principal: Principal = Depends(require_scope("memory")),
                         session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    deleted = await memory.delete(session, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory entry not found")
    return {"deleted": True, "id": memory_id}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@router.get("/models")
async def list_models(principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    return {
        "models": [
            {"id": m.id, "provider_id": m.provider_id, "display_name": m.display_name,
             "capabilities": m.capabilities, "context_window": m.context_window,
             "input_cost_per_mtok": m.input_cost_per_mtok, "output_cost_per_mtok": m.output_cost_per_mtok,
             "verified_identifier": m.verified_identifier, "licence_category": m.licence_category}
            for m in gateway.list_models()],
    }


@router.get("/models/providers")
async def list_providers(principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    return {"providers": await gateway.probe_providers()}


@router.get("/models/evaluations")
async def list_evaluations(principal: Principal = Depends(require_scope("read")),
                            session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"evaluations": await evaluation_service.list_evaluations(session, org_id=principal.org_id)}


@router.post("/models/evaluations", status_code=status.HTTP_201_CREATED)
async def run_evaluation(payload: Dict[str, Any],
                          principal: Principal = Depends(require_scope("models")),
                          session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    model_id = payload.get("model")
    if not model_id:
        raise HTTPException(status_code=400, detail="model is required")
    from ..services.gateway import MODELS

    known = {m.id for m in MODELS}
    if model_id not in known:
        raise HTTPException(status_code=404,
                            detail=f"unknown model '{model_id}' (not in the gateway registry)")
    try:
        return await evaluation_service.evaluate_model(session, model_id,
                                                       dataset_id=payload.get("dataset_id"),
                                                       cases=payload.get("cases"),
                                                       org_id=principal.org_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models/training")
async def training_status(principal: Principal = Depends(require_scope("models")),
                          session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await evaluation_service.training_status(session, org_id=principal.org_id)


@router.post("/models/training/datasets", status_code=status.HTTP_201_CREATED)
async def prepare_dataset(payload: Dict[str, Any],
                           principal: Principal = Depends(require_scope("models")),
                           session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    records = payload.get("records") or []
    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="records must be a list")
    return await evaluation_service.prepare_dataset(
        session, name=payload.get("name", "dataset"), records=records,
        org_id=principal.org_id, source=payload.get("source", "manual"))


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
@router.get("/skills")
async def list_skills(principal: Principal = Depends(require_scope("read")),
                      session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"skills": await skill_factory.list_skills(session)}


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def create_skill(payload: Dict[str, Any],
                        principal: Principal = Depends(require_scope("skills")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    return await skill_factory.create(
        session, name=payload["name"], description=payload.get("description", ""),
        input_schema=payload.get("input_schema") or {"type": "object"},
        output_schema=payload.get("output_schema") or {"type": "object"},
        tool_requirements=payload.get("tool_requirements") or [],
        permission_scope=payload.get("permission_scope", "read"),
        steps=payload.get("steps"), org_id=principal.org_id)


@router.post("/skills/{skill_id}/test")
async def test_skill(skill_id: str, principal: Principal = Depends(require_scope("skills")),
                     session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await skill_factory.run_tests(session, skill_id, org_id=principal.org_id)


@router.post("/skills/{skill_id}/publish")
async def publish_skill(skill_id: str, principal: Principal = Depends(require_scope("skills")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await skill_factory.publish(session, skill_id)


@router.post("/skills/{skill_id}/install")
async def install_skill(skill_id: str, principal: Principal = Depends(require_scope("skills")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await skill_factory.install(session, skill_id)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@router.get("/tools")
async def list_tools(principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    tools = tool_registry.all()
    return {"tools": [t.to_dict() for t in tools], "categories": tool_registry.categories()}


@router.post("/tools/{tool_id}/execute")
async def execute_tool(tool_id: str, payload: Dict[str, Any],
                        principal: Principal = Depends(require_scope("write")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    from ..services.tools import ToolContext

    tool = tool_registry.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool not found")
    context = ToolContext(
        agent_id=payload.get("agent_id"), org_id=principal.org_id,
        project_id=payload.get("project_id"),
        granted_scopes=set(payload.get("scopes") or [tool.permission_scope]),
        approved=bool(payload.get("approved")), session=session,
    )
    result = await tool_registry.execute(tool_id, payload.get("params") or {}, context)
    record = ToolExecution(
        tool_id=tool_id, agent_id=context.agent_id, org_id=principal.org_id,
        input_payload=payload.get("params") or {},
        output_payload=result.output if result.ok else {},
        status="ok" if result.ok else "error", error_code=result.error_code,
        error_message=result.error_message, duration_ms=result.duration_ms,
    )
    session.add(record)
    await session.flush()
    await audit(session, action="tool.execute", actor_id=principal.user_id, actor_role=principal.role,
               org_id=principal.org_id, target_type="tool", target_id=tool_id,
               outcome="ok" if result.ok else "error", detail={"error": result.error_code})
    return result.to_dict()


@router.get("/tools/executions")
async def list_tool_executions(principal: Principal = Depends(require_scope("read")),
                               session: AsyncSession = Depends(get_session),
                               limit: int = 50) -> Dict[str, Any]:
    rows = (await session.execute(
        select(ToolExecution).where(ToolExecution.org_id == principal.org_id)
        .order_by(ToolExecution.created_at.desc()).limit(min(limit, 300))
    )).scalars().all()
    return {"executions": [
        {"id": r.id, "tool_id": r.tool_id, "agent_id": r.agent_id, "status": r.status,
         "error_code": r.error_code, "error_message": r.error_message,
         "duration_ms": r.duration_ms,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows]}


# ---------------------------------------------------------------------------
# Projects / terminal / build
# ---------------------------------------------------------------------------
@router.get("/projects")
async def list_projects(principal: Principal = Depends(require_scope("read")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(
        select(Project).where(Project.org_id == principal.org_id)
        .order_by(Project.updated_at.desc())
    )).scalars().all()
    return {"projects": [
        {"id": p.id, "name": p.name, "description": p.description, "language": p.language,
         "template": p.template, "status": p.status, "git_branch": p.git_branch, "tags": p.tags,
         "stats": p.stats,
         "created_at": p.created_at.isoformat() if p.created_at else None}
        for p in rows]}


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(payload: Dict[str, Any],
                          principal: Principal = Depends(require_scope("projects")),
                          session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    project = Project(name=name, description=payload.get("description", ""),
                       language=payload.get("language", "python"),
                       template=payload.get("template", "blank"),
                       org_id=principal.org_id, tags=payload.get("tags") or [])
    session.add(project)
    await session.flush()
    root = sandbox_backend.project_root(project.id)
    project.root_path = str(root)
    await session.flush()
    return {"id": project.id, "name": project.name, "root_path": project.root_path}


@router.post("/terminal/exec")
async def terminal_exec(payload: Dict[str, Any],
                        principal: Principal = Depends(require_scope("projects")),
                        session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    command = (payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    try:
        result = await sandbox_backend.run(command, project_id=payload.get("project_id") or "default",
                                           timeout=int(payload.get("timeout") or settings.sandbox_timeout_seconds))
    except Exception as exc:
        # policy rejections (allowlist, path escape) are reported as a
        # structured refusal, not as a server error
        await audit(session, action="terminal.exec", actor_id=principal.user_id,
                   actor_role=principal.role, org_id=principal.org_id, target_type="terminal",
                   target_id=command[:120], outcome="denied",
                   detail={"error": type(exc).__name__})
        return {"command": command, "ok": False, "exit_code": None, "stdout": "", "stderr": str(exc),
                "duration_ms": 0.0, "timed_out": False, "truncated": False,
                "error_code": "BLOCKED_BY_POLICY"}
    await audit(session, action="terminal.exec", actor_id=principal.user_id, actor_role=principal.role,
               org_id=principal.org_id, target_type="terminal", target_id=command[:120],
               outcome="ok" if result.ok else "error")
    return result.to_dict()


@router.get("/builds")
async def list_builds(principal: Principal = Depends(require_scope("read")),
                      session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"builds": await build_service.list_jobs(session, org_id=principal.org_id)}


@router.post("/builds", status_code=status.HTTP_201_CREATED)
async def start_build(payload: Dict[str, Any],
                       principal: Principal = Depends(require_scope("build")),
                       session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    command = (payload.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    job = await build_service.run_build(
        session, project_id=payload.get("project_id"), name=payload.get("name", "build"),
        command=command, target=payload.get("target", "apk"),
        variant=payload.get("variant", "debug"), org_id=principal.org_id)
    return {"id": job.id, "status": job.status, "exit_code": job.exit_code,
            "log_path": job.log_path, "duration_ms": job.duration_ms, "error": job.error}


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------
@router.get("/workflows")
async def list_workflows(principal: Principal = Depends(require_scope("read")),
                         session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await session.execute(
        select(Workflow).where(Workflow.org_id == principal.org_id)
        .order_by(Workflow.updated_at.desc())
    )).scalars().all()
    return {"workflows": [
        {"id": w.id, "name": w.name, "description": w.description, "status": w.status,
         "graph": w.graph, "schedule": w.schedule, "last_run_id": w.last_run_id,
         "created_at": w.created_at.isoformat() if w.created_at else None}
        for w in rows]}


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
async def create_workflow(payload: Dict[str, Any],
                           principal: Principal = Depends(require_scope("workflows")),
                           session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    graph = payload.get("graph") or {}
    errors = workflow_engine.validate(graph)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    workflow = Workflow(name=payload.get("name") or "workflow",
                         description=payload.get("description", ""), graph=graph,
                         org_id=principal.org_id, status="active",
                         schedule=payload.get("schedule"))
    session.add(workflow)
    await session.flush()
    return {"id": workflow.id, "status": workflow.status}


@router.post("/workflows/{workflow_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_workflow_run(workflow_id: str, payload: Dict[str, Any],
                              principal: Principal = Depends(require_scope("workflows")),
                              session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    run = await workflow_engine.create_run(session, workflow_id, inputs=payload.get("inputs") or {},
                                           org_id=principal.org_id)
    result = await workflow_engine.run(session, run.id)
    return result


@router.get("/workflows/runs")
async def list_workflow_runs(principal: Principal = Depends(require_scope("read")),
                             session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return {"runs": await workflow_engine.list_runs(session, org_id=principal.org_id)}


@router.post("/workflows/runs/{run_id}/resume")
async def resume_workflow_run(run_id: str, principal: Principal = Depends(require_scope("workflows")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await workflow_engine.resume(session, run_id)


@router.post("/workflows/runs/{run_id}/approve")
async def approve_workflow_step(run_id: str, payload: Dict[str, Any],
                                 principal: Principal = Depends(require_scope("workflows")),
                                 session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    step_id = payload.get("step_id")
    if not step_id:
        raise HTTPException(status_code=400, detail="step_id is required")
    return await workflow_engine.approve(session, run_id, step_id,
                                         approved=bool(payload.get("approved", True)),
                                         approver=principal.user_id)


@router.post("/workflows/runs/{run_id}/cancel")
async def cancel_workflow_run(run_id: str, principal: Principal = Depends(require_scope("workflows")),
                               session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    return await workflow_engine.cancel(session, run_id)


# ---------------------------------------------------------------------------
# Voice & translation
# ---------------------------------------------------------------------------
@router.get("/voice/capabilities")
async def voice_capabilities(principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    return await voice_service.capabilities()


@router.post("/voice/transcribe")
async def transcribe(payload: Dict[str, Any],
                     principal: Principal = Depends(require_scope("read")),
                     session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    audio_path = payload.get("audio_path")
    if not audio_path:
        raise HTTPException(status_code=400, detail="audio_path is required")
    return await voice_service.transcribe(session, audio_path=audio_path,
                                          language=payload.get("language", "bn"),
                                          org_id=principal.org_id)


@router.post("/voice/speak")
async def speak(payload: Dict[str, Any], principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return await voice_service.speak(text, language=payload.get("language", "bn"),
                                     voice=payload.get("voice"))


@router.get("/translation/languages")
async def languages(principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    return {"languages": translation_service.supported()}


@router.post("/translation")
async def translate(payload: Dict[str, Any], principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    text = (payload.get("text") or "").strip()
    target = payload.get("target")
    if not text or not target:
        raise HTTPException(status_code=400, detail="text and target are required")
    return await translation_service.translate(text, target, source=payload.get("source"),
                                               glossary=payload.get("glossary"))


@router.post("/translation/detect")
async def detect(payload: Dict[str, Any], principal: Principal = Depends(require_scope("read"))) -> Dict[str, Any]:
    from ..services.media import detect_language

    return detect_language(payload.get("text") or "")


# ---------------------------------------------------------------------------
# Orchestration (Supreme Boss)
# ---------------------------------------------------------------------------
@router.post("/orchestrate", status_code=status.HTTP_201_CREATED)
async def orchestrate(payload: Dict[str, Any],
                       principal: Principal = Depends(require_scope("agents")),
                       session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    task = (payload.get("task") or "").strip()
    if not task:
        raise HTTPException(status_code=400, detail="task is required")
    summary = await supreme_boss.execute(
        session, task, context=payload.get("context") or {}, org_id=principal.org_id,
        max_agents=int(payload.get("max_agents") or 3))
    await audit(session, action="orchestrate", actor_id=principal.user_id, actor_role=principal.role,
               org_id=principal.org_id, outcome="ok" if summary.success else "failed")
    return summary.to_dict()


# ---------------------------------------------------------------------------
# Settings & security
# ---------------------------------------------------------------------------
@router.get("/settings/secrets")
async def secret_status(principal: Principal = Depends(require_scope("admin"))) -> Dict[str, Any]:
    from ..security.core import secret_store

    names = sorted({"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
                    "HUGGINGFACE_API_KEY", "GITHUB_TOKEN", "TITAN_JWT_SECRET"})
    return {"secrets": {name: secret_store.status(name) for name in names}}


@router.post("/settings/secrets")
async def set_secret(payload: Dict[str, Any], principal: Principal = Depends(require_scope("admin")),
                     session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    from ..security.core import secret_store

    name = payload.get("name")
    value = payload.get("value")
    if not name or not value:
        raise HTTPException(status_code=400, detail="name and value are required")
    secret_store.set_override(name, value)
    await audit(session, action="settings.secret.set", actor_id=principal.user_id,
               actor_role=principal.role, org_id=principal.org_id, target_type="secret",
               target_id=name)
    return {"name": name, "configured": True, "source": "override (process memory)"}


@router.get("/security/summary")
async def security_summary(principal: Principal = Depends(require_scope("read")),
                            session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    from ..security.core import secret_store

    tools = tool_registry.all()
    irreversible = [t.id for t in tools if t.permission_scope == "irreversible"]
    return {
        "rbac_roles": ["owner", "admin", "researcher", "developer", "viewer"],
        "current_role": principal.role,
        "scopes": sorted(principal.scopes),
        "tool_count": len(tools),
        "tools_requiring_approval": [t.id for t in tools if t.requires_approval],
        "irreversible_scope_tools": irreversible,
        "egress_allowlist": settings.egress_allowlist,
        "sandbox_backend": "docker" if hasattr(sandbox_backend, "name") and sandbox_backend.name == "docker" else "process",
        "sandbox_limits": {
            "cpu_seconds": settings.sandbox_cpu_seconds,
            "memory_mb": settings.sandbox_memory_mb,
            "max_processes": settings.sandbox_max_processes,
            "timeout_seconds": settings.sandbox_timeout_seconds,
            "max_output_bytes": settings.sandbox_max_output_bytes,
        },
        "secrets_configured": {name: secret_store.status(name)["configured"] for name in
                               ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"]},
        "note": "Provider secrets live only on the server; the Android client never receives them.",
    }


router.include_router(auth_router)
