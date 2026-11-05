"""Central Tool Execution Engine.

Every tool declares: id, description, input schema, output schema, permission
scope, timeout, retry policy, error contract, audit behaviour and a security
validator. The executor enforces the calling agent's grants, requires explicit
approval for irreversible scopes, records the *actual* result and never reports
success for a call that did not run.
"""
from __future__ import annotations

import asyncio
import os
import shlex
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..config import settings
from ..security.core import redact
from .observability import get_correlation_id, log, metrics

# Permission scopes, ordered by increasing danger.
SCOPE_ORDER = ["read", "write", "network", "execute", "sensitive", "irreversible"]
IRREVERSIBLE_SCOPES = {"irreversible"}


@dataclass
class ToolContext:
    agent_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    org_id: str = "default"
    project_id: Optional[str] = None
    cwd: Optional[str] = None
    granted_scopes: set = field(default_factory=set)
    correlation_id: Optional[str] = None
    approved: bool = False
    session: Optional[Any] = None   # reuse the caller's unit of work


@dataclass
class ToolResult:
    tool_id: str
    ok: bool
    output: Any = None
    error_code: Optional[str] = None
    error_message: str = ""
    duration_ms: float = 0.0
    exit_code: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id, "ok": self.ok, "output": self.output,
            "error_code": self.error_code, "error_message": self.error_message,
            "duration_ms": round(self.duration_ms, 2), "exit_code": self.exit_code,
            "metadata": self.metadata,
        }


class ToolError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Error contracts
#
# Every registered tool exposes a machine-readable error contract: the codes it
# may emit and whether a retry is worthwhile.  The base contract is shared;
# scope-specific codes are merged in automatically so no tool can ship with an
# empty contract.
# ---------------------------------------------------------------------------
STANDARD_ERROR_CODES: Dict[str, Dict[str, Any]] = {
    "INVALID_INPUT": {"meaning": "the request did not satisfy the input schema",
                      "retryable": False},
    "PERMISSION_DENIED": {"meaning": "the caller's scopes do not grant this tool",
                          "retryable": False},
    "TIMEOUT": {"meaning": "the tool exceeded its timeout budget",
                "retryable": True},
    "BLOCKED_BY_POLICY": {"meaning": "the sandbox or egress policy refused the operation",
                          "retryable": False},
    "SSRF_BLOCKED": {"meaning": "the target resolved to a forbidden address range",
                     "retryable": False},
    "NOT_FOUND": {"meaning": "the referenced resource does not exist",
                  "retryable": False},
    "UPSTREAM_ERROR": {"meaning": "the upstream service returned an error",
                       "retryable": True},
    "INTERNAL_ERROR": {"meaning": "the tool raised an unexpected exception",
                       "retryable": False},
}

SCOPE_ERROR_CODES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "network": {
        "UPSTREAM_RATE_LIMITED": {"meaning": "the upstream service rate-limited the request",
                                  "retryable": True},
        "SOURCE_UNAVAILABLE": {"meaning": "the source could not be reached or refused the connection",
                               "retryable": True},
    },
    "execute": {
        "NON_ZERO_EXIT": {"meaning": "the executed command exited with a non-zero status",
                          "retryable": False},
        "OUTPUT_TRUNCATED": {"meaning": "the output exceeded the configured byte budget",
                             "retryable": False},
    },
    "irreversible": {
        "APPROVAL_REQUIRED": {"meaning": "the action is irreversible and needs explicit approval",
                              "retryable": False},
    },
    "write": {
        "CONSTRAINT_VIOLATION": {"meaning": "the write violated a storage constraint",
                                 "retryable": False},
    },
}


def build_error_contract(permission_scope: str) -> Dict[str, Any]:
    """Compose the error contract for a tool from its permission scope."""
    codes: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in STANDARD_ERROR_CODES.items()}
    codes.update({k: dict(v) for k, v in SCOPE_ERROR_CODES.get(permission_scope, {}).items()})
    return {
        "codes": codes,
        "result_shape": {"ok": "boolean", "error_code": "string|null",
                         "error_message": "string", "output": "any"},
        "policy": "A tool that did not run is reported as failed; a failed tool is never "
                  "reported as successful.",
    }


@dataclass
class Tool:
    id: str
    name: str
    category: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permission_scope: str
    timeout_seconds: int = 60
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"max_attempts": 1, "backoff_seconds": 0.5})
    error_contract: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    handler: Optional[Callable[[Dict[str, Any], ToolContext], Awaitable[Any]]] = None
    validator: Optional[Callable[[Dict[str, Any]], None]] = None

    def __post_init__(self) -> None:
        # A tool may narrow the standard contract, never ship an empty one.
        if not self.error_contract:
            self.error_contract = build_error_contract(self.permission_scope)
        elif "codes" not in self.error_contract:
            merged = build_error_contract(self.permission_scope)
            merged["codes"].update(self.error_contract)
            self.error_contract = merged

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "description": self.description, "input_schema": self.input_schema,
            "output_schema": self.output_schema, "permission_scope": self.permission_scope,
            "timeout_seconds": self.timeout_seconds, "retry_policy": self.retry_policy,
            "error_contract": self.error_contract, "requires_approval": self.requires_approval,
        }


def _require(params: Dict[str, Any], key: str) -> Any:
    if key not in params or params[key] in (None, ""):
        raise ToolError("INVALID_INPUT", f"missing required parameter '{key}'")
    return params[key]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.id] = tool
        return tool

    def get(self, tool_id: str) -> Optional[Tool]:
        return self._tools.get(tool_id)

    def all(self) -> List[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.id)

    def categories(self) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for tool in self._tools.values():
            grouped.setdefault(tool.category, []).append(tool.id)
        return grouped

    # -- execution --------------------------------------------------------
    async def execute(self, tool_id: str, params: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self.get(tool_id)
        if tool is None:
            return ToolResult(tool_id, False, error_code="UNKNOWN_TOOL",
                              error_message=f"tool '{tool_id}' is not registered")
        started = time.perf_counter()

        # 1. scope check
        scope = tool.permission_scope
        if scope in IRREVERSIBLE_SCOPES and not ctx.approved:
            return ToolResult(tool_id, False, error_code="APPROVAL_REQUIRED",
                              error_message=f"tool '{tool_id}' performs an irreversible action and needs explicit approval",
                              duration_ms=(time.perf_counter() - started) * 1000)
        if ctx.granted_scopes and scope not in ctx.granted_scopes and "execute" not in ctx.granted_scopes:
            return ToolResult(tool_id, False, error_code="PERMISSION_DENIED",
                              error_message=f"agent is not granted scope '{scope}' for tool '{tool_id}'",
                              duration_ms=(time.perf_counter() - started) * 1000)

        # 2. input validation
        try:
            if tool.validator:
                tool.validator(params)
        except ToolError:
            raise
        except Exception as exc:
            return ToolResult(tool_id, False, error_code="INVALID_INPUT", error_message=str(exc),
                              duration_ms=(time.perf_counter() - started) * 1000)

        if tool.handler is None:
            return ToolResult(tool_id, False, error_code="NOT_IMPLEMENTED",
                              error_message=f"tool '{tool_id}' has no handler bound",
                              duration_ms=(time.perf_counter() - started) * 1000)

        # 3. run with retry + timeout
        attempts = int(tool.retry_policy.get("max_attempts", 1))
        backoff = float(tool.retry_policy.get("backoff_seconds", 0.5))
        last_error = ""
        for attempt in range(attempts):
            try:
                output = await asyncio.wait_for(tool.handler(params, ctx), timeout=tool.timeout_seconds)
                duration = (time.perf_counter() - started) * 1000
                metrics.incr("tool_executions_total", tool=tool_id, status="ok")
                metrics.observe("tool_duration_ms", duration, tool=tool_id)
                return ToolResult(tool_id, True, output=output, duration_ms=duration,
                                  metadata={"attempts": attempt + 1})
            except asyncio.TimeoutError:
                last_error = f"timeout after {tool.timeout_seconds}s"
            except ToolError as exc:
                last_error = exc.message if hasattr(exc, "message") else str(exc)
                metrics.incr("tool_executions_total", tool=tool_id, status="error")
                return ToolResult(tool_id, False, error_code=exc.code, error_message=redact(last_error),
                                  duration_ms=(time.perf_counter() - started) * 1000)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt + 1 < attempts:
                    await asyncio.sleep(backoff * (2 ** attempt))
        metrics.incr("tool_executions_total", tool=tool_id, status="error")
        return ToolResult(tool_id, False, error_code="EXECUTION_FAILED", error_message=redact(last_error),
                          duration_ms=(time.perf_counter() - started) * 1000)


registry = ToolRegistry()


def register(tool: Tool) -> Tool:
    return registry.register(tool)
