import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import ModelCall, utcnow


@dataclass
class ModelResult:
    text: str
    provider: str
    model: str
    is_mock: bool
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    cost_usd: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ModelGateway:
    """Small provider-neutral gateway; no hidden mock or cross-provider fallback."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def providers(self) -> list[dict[str, Any]]:
        configured = bool(
            self.settings.openai_compatible_base_url
            and self.settings.openai_compatible_api_key
            and self.settings.openai_compatible_model
        )
        return [
            {
                "id": "mock",
                "name": "Explicit deterministic mock",
                "configured": not self.settings.production,
                "available": not self.settings.production,
                "mock": True,
                "note": "Development only. Never represented as live AI or translation.",
            },
            {
                "id": "openai-compatible",
                "name": "Server-configured OpenAI-compatible provider",
                "configured": configured,
                "available": configured,
                "mock": False,
                "model": self.settings.openai_compatible_model if configured else None,
                "note": "Availability means configured; a successful inference is required for health verification.",
            },
            {
                "id": "gemini",
                "name": "Google Gemini",
                "configured": False,
                "available": False,
                "mock": False,
                "documented_models": [{"id": "gemini-4-argon", "runtime_status": "unverified"}],
                "note": "Dedicated Gemini adapter and credentials are not configured.",
            },
        ]

    def _select(self, requested: str | None) -> str:
        provider = requested or (
            "openai-compatible" if self.settings.openai_compatible_base_url else "mock"
        )
        if provider == "mock" and self.settings.production:
            raise HTTPException(status_code=503, detail="Mock provider is disabled in production")
        if provider not in {"mock", "openai-compatible"}:
            raise HTTPException(
                status_code=400, detail=f"Unsupported or unconfigured provider: {provider}"
            )
        return provider

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        actor_id: str,
        requested_provider: str | None = None,
        db: AsyncSession | None = None,
    ) -> ModelResult:
        provider = self._select(requested_provider)
        started = time.perf_counter()
        try:
            if provider == "mock":
                result = await self._mock(messages, task_type, started)
            else:
                result = await self._openai_compatible(messages, task_type, started)
        except HTTPException:
            raise
        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000
            if db is not None:
                db.add(
                    ModelCall(
                        actor_id=actor_id,
                        provider=provider,
                        model=self.settings.openai_compatible_model or "unconfigured",
                        task_type=task_type,
                        success=False,
                        latency_ms=latency,
                        error=str(exc)[:1000],
                        created_at=utcnow(),
                    )
                )
                await db.commit()
            raise HTTPException(
                status_code=502, detail=f"Model provider failed: {str(exc)[:300]}"
            ) from exc
        if db is not None:
            db.add(
                ModelCall(
                    actor_id=actor_id,
                    provider=result.provider,
                    model=result.model,
                    task_type=task_type,
                    success=True,
                    is_mock=result.is_mock,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    cost_usd=result.cost_usd,
                )
            )
            await db.commit()
        return result

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        task_type: str,
        actor_id: str,
        requested_provider: str | None = None,
        db: AsyncSession | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream provider deltas. Mock chunks are explicitly labeled and never called live AI."""
        provider = self._select(requested_provider)
        started = time.perf_counter()
        parts: list[str] = []
        model = (
            "deterministic-mock-v1"
            if provider == "mock"
            else (self.settings.openai_compatible_model or "unconfigured")
        )
        usage: dict[str, int] = {}
        success = False
        error: str | None = None
        try:
            if provider == "mock":
                result = await self._mock(messages, task_type, started)
                words = result.text.split(" ")
                for index, word in enumerate(words):
                    delta = word + (" " if index < len(words) - 1 else "")
                    parts.append(delta)
                    yield {"delta": delta, "is_mock": True}
            else:
                base = self.settings.openai_compatible_base_url
                key = self.settings.openai_compatible_api_key
                if not all((base, key, model)):
                    raise HTTPException(
                        status_code=503, detail="Streaming provider is not fully configured"
                    )
                assert base is not None and key is not None
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(120, connect=15), transport=self.transport
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{base.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": model, "messages": messages, "stream": True},
                    ) as response:
                        if response.status_code >= 400:
                            raise HTTPException(
                                status_code=502,
                                detail=f"Provider returned HTTP {response.status_code}",
                            )
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            import json

                            event = json.loads(data)
                            if event.get("usage"):
                                usage = event["usage"]
                            choices = event.get("choices") or []
                            if choices:
                                delta = choices[0].get("delta", {}).get("content")
                                if isinstance(delta, str) and delta:
                                    parts.append(delta)
                                    yield {"delta": delta, "is_mock": False}
            success = True
        except Exception as exc:
            error = str(exc)[:1000]
            yield {
                "error": "Model stream failed",
                "detail": error[:300],
                "is_mock": provider == "mock",
            }
        finally:
            if db is not None:
                db.add(
                    ModelCall(
                        actor_id=actor_id,
                        provider=provider,
                        model=model,
                        task_type=task_type,
                        success=success,
                        is_mock=provider == "mock",
                        input_tokens=int(usage.get("prompt_tokens") or 0),
                        output_tokens=int(usage.get("completion_tokens") or 0),
                        latency_ms=(time.perf_counter() - started) * 1000,
                        error=error,
                    )
                )
                await db.commit()
        if success:
            yield {
                "done": True,
                "text": "".join(parts),
                "provider": provider,
                "model": model,
                "is_mock": provider == "mock",
            }

    async def _mock(
        self, messages: list[dict[str, str]], task_type: str, started: float
    ) -> ModelResult:
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        text = (
            "[MOCK — NO LIVE AI INFERENCE]\n"
            f"Route: {task_type}. The deterministic development provider received "
            f"{len(latest)} characters. Configure a server-side provider for actual work. "
            "No research, translation, code change, or tool action was performed by this response."
        )
        return ModelResult(
            text=text,
            provider="mock",
            model="deterministic-mock-v1",
            is_mock=True,
            input_tokens=len(latest.split()),
            output_tokens=len(text.split()),
            latency_ms=(time.perf_counter() - started) * 1000,
            cost_usd=0,
        )

    async def _openai_compatible(
        self, messages: list[dict[str, str]], task_type: str, started: float
    ) -> ModelResult:
        base = self.settings.openai_compatible_base_url
        key = self.settings.openai_compatible_api_key
        model = self.settings.openai_compatible_model
        if not all((base, key, model)):
            raise HTTPException(
                status_code=503,
                detail="OpenAI-compatible base URL, API key and model must be configured server-side",
            )
        assert base is not None and key is not None and model is not None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=15), transport=self.transport
        ) as client:
            response = await client.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages},
            )
        if response.status_code >= 400:
            # Response bodies may contain provider details; expose only a bounded generic error.
            raise HTTPException(
                status_code=502, detail=f"Provider returned HTTP {response.status_code}"
            )
        payload = response.json()
        try:
            text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise TypeError("Provider content is not text")
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                status_code=502, detail="Provider response failed output validation"
            ) from exc
        usage = payload.get("usage") or {}
        return ModelResult(
            text=text,
            provider="openai-compatible",
            model=str(payload.get("model") or model),
            is_mock=False,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=(time.perf_counter() - started) * 1000,
            raw={
                "id": payload.get("id"),
                "finish_reason": payload["choices"][0].get("finish_reason"),
            },
        )
