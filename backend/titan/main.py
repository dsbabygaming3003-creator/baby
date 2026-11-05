"""TITAN OMEGA INFINITY V18 — application entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.deps import rate_limit
from .api.routes import router
from .config import settings
from .db import SessionLocal, dispose_engine, run_migrations
from .agents.definitions import CORE_AGENTS
from .services.gateway import MODELS, PROVIDERS
from .services.observability import configure_logging, get_correlation_id, metrics, set_correlation_id
from .services.tools_impl import register_all as register_tools

log = logging.getLogger("titan.main")


class EventBroker:
    """In-process pub/sub for live agent, workflow and research events."""

    def __init__(self) -> None:
        self._subscribers: List[Any] = []

    def subscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.append(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        message = json.dumps({"event": event_type, "payload": payload,
                              "correlation_id": get_correlation_id()}, ensure_ascii=False)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                self.unsubscribe(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


broker = EventBroker()


async def seed_registry(session) -> None:
    """Register providers, models and the 20 core agents."""
    from sqlalchemy import select

    from .models import Agent, ModelRecord, Provider

    for spec in PROVIDERS.values():
        provider = (await session.execute(
            select(Provider).where(Provider.id == spec.id)
        )).scalar_one_or_none()
        if provider is None:
            provider = Provider(id=spec.id, name=spec.name, family=spec.family,
                                base_url=spec.base_url, requires_key=bool(spec.env_key),
                                secret_ref=spec.env_key, status="unknown")
            session.add(provider)
        else:
            provider.name = spec.name
            provider.base_url = spec.base_url

    for spec in MODELS:
        model = (await session.execute(
            select(ModelRecord).where(ModelRecord.id == spec.id)
        )).scalar_one_or_none()
        if model is None:
            session.add(ModelRecord(
                id=spec.id, provider_id=spec.provider_id, display_name=spec.display_name,
                family=spec.provider_id, capabilities=spec.capabilities,
                context_window=spec.context_window, input_cost_per_mtok=spec.input_cost_per_mtok,
                output_cost_per_mtok=spec.output_cost_per_mtok,
                licence_category="hosted-proprietary", verified_identifier=spec.verified_identifier,
            ))

    for definition in CORE_AGENTS:
        agent = (await session.execute(
            select(Agent).where(Agent.id == definition.id)
        )).scalar_one_or_none()
        if agent is None:
            session.add(Agent(
                id=definition.id, name=definition.name, role=definition.role,
                description=definition.description, version=definition.version, status="active",
                is_dynamic=False, system_instructions=definition.system_instructions,
                model_config_json=definition.model, tool_permissions=definition.tool_permissions,
                memory_scope=definition.memory_scope, input_schema=definition.input_schema,
                output_schema=definition.output_schema, timeout_seconds=definition.timeout_seconds,
                retry_policy=definition.retry_policy,
                quality_criteria=definition.quality_criteria,
            ))
    await session.flush()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("INFO")
    rate_limit(settings.rate_limit_per_minute, settings.rate_limit_burst)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await run_migrations()
    tool_count = register_tools()

    async with SessionLocal() as session:
        await seed_registry(session)
        from .services.research import research_engine

        await research_engine.sync_connectors(session)
        await session.commit()
    log.info("TITAN ready: %d tools registered, database=%s", tool_count,
             settings.resolved_database_url.split("://")[0])
    try:
        yield
    finally:
        await dispose_engine()


app = FastAPI(
    title="TITAN OMEGA INFINITY V18",
    description="Global AI research, multi-agent orchestration, real tool execution and a mobile-first ecosystem.",
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Titan-Version"],
)


@app.middleware("http")
async def correlation_middleware(request, call_next):
    cid = set_correlation_id(request.headers.get("X-Correlation-ID"))
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    response.headers["X-Titan-Version"] = settings.version
    metrics.incr("http_requests_total", method=request.method, path=request.url.path)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={
        "error": "internal_error",
        "detail": f"{type(exc).__name__}: {exc}"[:500],
        "correlation_id": get_correlation_id(),
    })


app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": settings.app_name,
        "edition": settings.edition,
        "version": settings.version,
        "api": settings.api_prefix,
        "docs": "/docs",
        "websocket": "/ws/events",
        "status": "operational",
    }


@app.get("/health")
async def root_health() -> Dict[str, Any]:
    return {"status": "ok", "version": settings.version}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """Live event stream for agent, workflow and research activity."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    broker.subscribe(queue)
    try:
        await websocket.send_json({"event": "connected", "payload": {"subscribers": broker.subscriber_count}})
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_text(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"event": "heartbeat", "payload": {}})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("websocket closed: %s", exc)
    finally:
        broker.unsubscribe(queue)
