"""Observability: correlation ids, structured logs, metrics registry, audit log."""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from ..security.core import redact

_correlation_id: ContextVar[Optional[str]] = ContextVar("titan_correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: Optional[str]) -> str:
    cid = value or new_correlation_id()
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        for key in ("event", "actor_id", "org_id", "duration_ms", "status", "tool_id", "agent_id", "model_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "asyncio", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


log = logging.getLogger("titan")


class Metrics:
    """In-process counters exposed in Prometheus text format."""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}

    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = _key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        self._gauges[_key(name, labels)] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        self._histograms.setdefault(_key(name, labels), []).append(value)

    def render(self) -> str:
        lines: list[str] = []
        for key, value in sorted(self._counters.items()):
            lines.append(f"titan_{key} {value}")
        for key, value in sorted(self._gauges.items()):
            lines.append(f"titan_{key} {value}")
        for key, samples in sorted(self._histograms.items()):
            if samples:
                lines.append(f"titan_{key}_count {len(samples)}")
                lines.append(f"titan_{key}_sum {sum(samples):.4f}")
        return "\n".join(lines) + "\n"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: {"count": len(v), "sum": sum(v)} for k, v in self._histograms.items()},
        }


def _key(name: str, labels: Dict[str, str]) -> str:
    if not labels:
        return name
    rendered = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{rendered}}}"


metrics = Metrics()


async def audit(
    session,
    *,
    action: str,
    actor_id: Optional[str] = None,
    actor_role: str = "system",
    org_id: str = "default",
    target_type: str = "",
    target_id: str = "",
    outcome: str = "ok",
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an immutable audit record (best-effort; never raises)."""
    from ..models import AuditLog

    try:
        session.add(
            AuditLog(
                org_id=org_id,
                actor_id=actor_id,
                actor_role=actor_role,
                action=action,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome,
                correlation_id=get_correlation_id(),
                detail=detail or {},
            )
        )
        await session.flush()
        metrics.incr("audit_events_total", action=action, outcome=outcome)
    except Exception as exc:  # pragma: no cover - audit must never break a request
        log.warning("audit write failed: %s", exc)
