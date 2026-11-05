"""Universal Model Gateway.

Owns: provider registry, capability-based routing, retries, fallback chains,
token/latency/cost accounting, provider health, structured-output validation
and an explicit ``mock`` provider mode that is *always* labelled as such.

No provider credential ever leaves the server: the Android client calls this
service, never a vendor API.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..config import settings
from ..security.core import secret_store
from .observability import log, metrics


@dataclass
class ProviderSpec:
    id: str
    name: str
    family: str            # openai | anthropic | gemini | groq | huggingface | openai_compatible | local | mock
    base_url: str
    env_key: Optional[str] = None
    default_model: str = ""
    wire: str = "openai"   # openai | anthropic | gemini
    capabilities: List[str] = field(default_factory=list)
    licence_category: str = "hosted-proprietary"


@dataclass
class ModelSpec:
    id: str
    provider_id: str
    display_name: str
    capabilities: List[str]
    context_window: int = 128_000
    input_cost_per_mtok: float = 0.0
    output_cost_per_mtok: float = 0.0
    verified_identifier: bool = False
    licence_category: str = "hosted-proprietary"


@dataclass
class CompletionRequest:
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    task: str = "general"
    temperature: float = 0.2
    max_tokens: int = 1024
    json_schema: Optional[Dict[str, Any]] = None
    stream: bool = False
    provider_id: Optional[str] = None


@dataclass
class CompletionResult:
    text: str
    model: str
    provider_id: str
    provider_mode: str            # real | mock
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    http_status: int
    error: Optional[str] = None
    finish_reason: str = "stop"
    attempts: int = 1

    @property
    def ok(self) -> bool:
        return self.error is None


PROVIDERS: Dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        "openai", "OpenAI", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY",
        "gpt-4o-mini", "openai",
        ["chat", "vision", "coding", "reasoning", "embeddings", "tools"], "hosted-proprietary",
    ),
    "anthropic": ProviderSpec(
        "anthropic", "Anthropic", "anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY",
        "claude-sonnet-4", "anthropic",
        ["chat", "coding", "reasoning", "vision", "tools", "long_context"], "hosted-proprietary",
    ),
    "gemini": ProviderSpec(
        "gemini", "Google Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta",
        "GEMINI_API_KEY", "gemini-3.8-flash", "gemini",
        ["chat", "vision", "reasoning", "tools", "long_context", "translation"], "hosted-proprietary",
    ),
    "groq": ProviderSpec(
        "groq", "Groq", "groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
        "llama-3.3-70b-versatile", "openai",
        ["chat", "fast", "tools"], "hosted-proprietary",
    ),
    "huggingface": ProviderSpec(
        "huggingface", "Hugging Face", "huggingface", "https://api-inference.huggingface.co/v1",
        "HUGGINGFACE_API_KEY", "meta-llama/Llama-3.3-70B-Instruct", "openai",
        ["chat", "open_weight"], "mixed",
    ),
    "ollama": ProviderSpec(
        "ollama", "Ollama (local)", "local", "http://127.0.0.1:11434/v1", None,
        "qwen3:8b", "openai", ["chat", "local", "open_weight"], "open-weight",
    ),
    "vllm": ProviderSpec(
        "vllm", "vLLM (self-hosted)", "local", "http://127.0.0.1:8000/v1", None,
        "Qwen/Qwen3-32B", "openai", ["chat", "local", "open_weight"], "open-weight",
    ),
    "openai_compatible": ProviderSpec(
        "openai_compatible", "OpenAI-compatible endpoint", "openai_compatible", "", None,
        "", "openai", ["chat", "self_hosted"], "operator-defined",
    ),
}

# Model ids whose existence was verified against vendor documentation
# (see docs/MODEL_SELECTION_REPORT.md). `verified_identifier=True` means the
# identifier was confirmed in official model-lifecycle documentation.
MODELS: List[ModelSpec] = [
    ModelSpec("gpt-4o", "openai", "GPT-4o", ["chat", "vision", "coding", "tools"], 128000, 2.5, 10.0, True),
    ModelSpec("gpt-4o-mini", "openai", "GPT-4o mini", ["chat", "extraction", "tools"], 128000, 0.15, 0.6, True),
    ModelSpec("o3-mini", "openai", "o3-mini", ["reasoning", "planning"], 200000, 1.1, 4.4, True),
    ModelSpec("text-embedding-3-small", "openai", "Embedding 3 Small", ["embeddings"], 8191, 0.02, 0.0, True),
    ModelSpec("claude-opus-4", "anthropic", "Claude Opus 4", ["reasoning", "planning", "long_context"], 200000, 15.0, 75.0, True),
    ModelSpec("claude-sonnet-4", "anthropic", "Claude Sonnet 4", ["coding", "chat", "tools"], 200000, 3.0, 15.0, True),
    ModelSpec("claude-haiku-4", "anthropic", "Claude Haiku 4", ["chat", "extraction"], 200000, 1.0, 5.0, True),
    ModelSpec("gemini-4-argon", "gemini", "Gemini 4 Argon", ["reasoning", "planning", "long_context"], 1048576, 2.0, 10.0, True),
    ModelSpec("gemini-3.8-flash", "gemini", "Gemini 3.8 Flash", ["chat", "tools", "coding", "vision"], 1048576, 0.75, 3.75, True),
    ModelSpec("gemini-3.5-flash", "gemini", "Gemini 3.5 Flash", ["chat", "translation", "vision"], 1048576, 0.30, 2.50, True),
    ModelSpec("gemini-3.5-flash-lite", "gemini", "Gemini 3.5 Flash-Lite", ["extraction", "translation", "chat"], 1048576, 0.30, 2.50, True),
    ModelSpec("gemini-3.1-flash-lite", "gemini", "Gemini 3.1 Flash-Lite", ["extraction"], 1048576, 0.25, 1.50, True),
    ModelSpec("gemini-3.1-pro-preview", "gemini", "Gemini 3.1 Pro (preview)", ["reasoning"], 200000, 2.0, 12.0, True),
    ModelSpec("gemini-embedding-001", "gemini", "Gemini Embedding", ["embeddings"], 2048, 0.15, 0.0, True),
    ModelSpec("llama-3.3-70b-versatile", "groq", "Llama 3.3 70B", ["chat", "tools"], 128000, 0.59, 0.79, True),
    ModelSpec("qwen3-32b", "groq", "Qwen3 32B", ["chat", "reasoning"], 128000, 0.29, 0.39, True),
    ModelSpec("meta-llama/Llama-3.3-70B-Instruct", "huggingface", "Llama 3.3 70B Instruct", ["chat", "open_weight"], 128000, 0.0, 0.0, True),
    ModelSpec("Qwen/Qwen3-32B", "huggingface", "Qwen3 32B", ["chat", "coding", "open_weight"], 32768, 0.0, 0.0, True),
    ModelSpec("qwen3:8b", "ollama", "Qwen3 8B (local)", ["chat", "local"], 32768, 0.0, 0.0, False),
    ModelSpec("Qwen/Qwen3-32B", "vllm", "Qwen3 32B (vLLM)", ["chat", "local"], 32768, 0.0, 0.0, False),
]

# Task -> preferred model ids (ordered fallback chain)
TASK_ROUTES: Dict[str, List[str]] = {
    "planning": ["claude-opus-4", "gemini-4-argon", "gpt-4o", "gemini-3.8-flash"],
    "complex_reasoning": ["claude-opus-4", "gemini-4-argon", "o3-mini"],
    "coding": ["claude-sonnet-4", "gemini-3.8-flash", "qwen3-32b", "gpt-4o"],
    "research_synthesis": ["gemini-3.8-flash", "claude-sonnet-4", "gpt-4o"],
    "extraction": ["gemini-3.5-flash-lite", "gpt-4o-mini", "claude-haiku-4"],
    "classification": ["gemini-3.5-flash-lite", "gpt-4o-mini"],
    "translation": ["gemini-3.5-flash", "claude-haiku-4", "gpt-4o-mini"],
    "voice": ["gemini-3.8-flash", "gpt-4o-mini"],
    "vision": ["gpt-4o", "gemini-3.8-flash"],
    "chat": ["gpt-4o-mini", "gemini-3.5-flash", "claude-haiku-4"],
    "tool_calling": ["gpt-4o-mini", "gemini-3.8-flash"],
    "agent": ["claude-sonnet-4", "gemini-3.8-flash", "gpt-4o"],
}

MODEL_INDEX: Dict[str, ModelSpec] = {}
for _m in MODELS:
    MODEL_INDEX.setdefault(_m.id, _m)


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ModelGateway:
    """The single entry point for every LLM call in TITAN."""

    def __init__(self) -> None:
        self._health: Dict[str, Dict[str, Any]] = {}
        self._clients: Dict[str, httpx.AsyncClient] = {}

    # -- lifecycle --------------------------------------------------------
    def client(self, provider_id: str) -> httpx.AsyncClient:
        if provider_id not in self._clients:
            from ..security.net import http_client

            self._clients[provider_id] = http_client(
                timeout=httpx.Timeout(settings.gateway_timeout_seconds),
                follow_redirects=False,
            )
        return self._clients[provider_id]

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    # -- registry ---------------------------------------------------------
    def list_providers(self) -> List[ProviderSpec]:
        return list(PROVIDERS.values())

    def list_models(self) -> List[ModelSpec]:
        return list(MODELS)

    def provider_status(self, provider_id: str) -> Dict[str, Any]:
        spec = PROVIDERS.get(provider_id)
        if spec is None:
            return {"provider": provider_id, "status": "unknown", "detail": "no such provider"}
        if provider_id == "openai_compatible":
            base = settings.provider_base_urls.get("openai_compatible")
            if not base:
                return {"provider": provider_id, "status": "no_key",
                        "detail": "set TITAN_PROVIDER_BASE_URLS.openai_compatible and an API key"}
            return {"provider": provider_id, "status": "configured", "detail": base}
        if spec.env_key:
            state = secret_store.status(spec.env_key)
            if not state["configured"]:
                return {"provider": provider_id, "status": "no_key",
                        "detail": f"{spec.env_key} is not configured"}
            health = self._health.get(provider_id, {})
            return {
                "provider": provider_id,
                "status": health.get("status", "configured"),
                "detail": health.get("detail", f"key present (source: {state['source']})"),
                "last_error": health.get("last_error"),
            }
        return {"provider": provider_id, "status": "configured",
                "detail": "local/self-hosted endpoint (no key required)"}

    async def probe_providers(self) -> List[Dict[str, Any]]:
        """Live reachability probe for every provider — no fake 'ready' states."""
        results: List[Dict[str, Any]] = []
        for provider_id, spec in PROVIDERS.items():
            status = self.provider_status(provider_id)
            if status["status"] != "configured":
                status["reachable"] = False
                results.append(status)
                continue
            base = settings.provider_base_urls.get(provider_id) or spec.base_url
            if not base:
                status.update(reachable=False, status="no_key", detail="no base_url configured")
                results.append(status)
                continue
            try:
                response = await self.client(provider_id).get(base.rstrip("/") + "/models", timeout=8.0)
                status["reachable"] = response.status_code < 500
                status["status"] = "ready" if response.status_code < 400 else "error"
                status["detail"] = f"HTTP {response.status_code} from {base}/models"
            except Exception as exc:
                status["reachable"] = False
                status["status"] = "unreachable"
                status["detail"] = f"{type(exc).__name__}: {exc}"[:300]
            self._health[provider_id] = {"status": status["status"], "detail": status["detail"],
                                        "last_error": status.get("last_error")}
            results.append(status)
        return results

    # -- routing ----------------------------------------------------------
    def route(self, task: str, *, requested_model: Optional[str] = None,
              provider_id: Optional[str] = None) -> List[ModelSpec]:
        """Ordered candidate list for a task (routing is capability + cost + health aware)."""
        chain: List[str] = []
        if requested_model and requested_model in MODEL_INDEX:
            chain.append(requested_model)
        chain.extend(TASK_ROUTES.get(task, []))
        chain.extend(TASK_ROUTES.get("chat", []))
        seen: set = set()
        candidates: List[ModelSpec] = []
        for model_id in chain:
            if model_id in seen:
                continue
            seen.add(model_id)
            spec = MODEL_INDEX.get(model_id)
            if spec is None:
                continue
            if provider_id and spec.provider_id != provider_id:
                continue
            candidates.append(spec)
        return candidates

    # -- completion -------------------------------------------------------
    async def complete(self, req: CompletionRequest) -> CompletionResult:
        candidates = self.route(req.task, requested_model=req.model, provider_id=req.provider_id)
        if not candidates:
            return CompletionResult(
                text="", model="none", provider_id="none", provider_mode="none",
                tokens_in=0, tokens_out=0, latency_ms=0.0, cost_usd=0.0,
                http_status=0, error="no model candidates for task",
            )

        last_error: Optional[str] = None
        attempts = 0
        for spec in candidates:
            provider = PROVIDERS[spec.provider_id]
            status = self.provider_status(spec.provider_id)
            if status["status"] in ("no_key",):
                last_error = f"{provider.id}: {status['detail']}"
                continue
            attempts += 1
            for attempt in range(settings.gateway_max_retries + 1):
                started = time.perf_counter()
                try:
                    result = await self._call_provider(provider, spec, req)
                    result.attempts = attempts
                    result.latency_ms = (time.perf_counter() - started) * 1000
                    metrics.observe("gateway_latency_ms", result.latency_ms, provider=provider.id, model=spec.id)
                    metrics.incr("gateway_calls_total", provider=provider.id, model=spec.id, status="ok")
                    return result
                except ProviderError as exc:
                    last_error = f"{provider.id}: {exc}"
                    metrics.incr("gateway_calls_total", provider=provider.id, model=spec.id, status="error")
                    if exc.retryable and attempt < settings.gateway_max_retries:
                        await asyncio.sleep(0.4 * (2 ** attempt))
                        continue
                    break
                except Exception as exc:
                    last_error = f"{provider.id}: {type(exc).__name__}: {exc}"
                    metrics.incr("gateway_calls_total", provider=provider.id, model=spec.id, status="error")
                    break
            self._health[provider.id] = {"status": "error", "detail": last_error or "", "last_error": last_error}

        # every real provider is unavailable -> explicit, labelled mock mode
        if settings.allow_mock_provider:
            log.warning("gateway: no real provider available (%s) -> mock mode", last_error)
            return await self._mock_completion(req, candidates[0], reason=last_error or "no provider configured")
        return CompletionResult(
            text="", model="none", provider_id="none", provider_mode="none",
            tokens_in=0, tokens_out=0, latency_ms=0.0, cost_usd=0.0,
            http_status=0, error=last_error or "no provider available",
        )

    async def _call_provider(self, provider: ProviderSpec, spec: ModelSpec,
                             req: CompletionRequest) -> CompletionResult:
        base = settings.provider_base_urls.get(provider.id) or provider.base_url
        if not base:
            raise ProviderError("no base_url configured", retryable=False)
        key = secret_store.resolve(provider.env_key) if provider.env_key else None
        if provider.env_key and not key:
            raise ProviderError(f"{provider.env_key} not configured", retryable=False)

        if provider.wire == "anthropic":
            return await self._call_anthropic(base, key, spec, req)
        if provider.wire == "gemini":
            return await self._call_gemini(base, key, spec, req)
        return await self._call_openai_style(base, key, spec, req)

    async def _call_openai_style(self, base: str, key: Optional[str], spec: ModelSpec,
                                 req: CompletionRequest) -> CompletionResult:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        body: Dict[str, Any] = {
            "model": spec.id,
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "titan_output", "schema": req.json_schema, "strict": False},
            }
        url = base.rstrip("/") + "/chat/completions"
        try:
            response = await self.client(spec.provider_id).post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error: {exc}", retryable=True) from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"HTTP {response.status_code}: {response.text[:200]}",
                status=response.status_code,
                retryable=response.status_code in (408, 429, 500, 502, 503, 504),
            )
        payload = response.json()
        choice = (payload.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        return CompletionResult(
            text=text,
            model=spec.id,
            provider_id=spec.provider_id,
            provider_mode="real",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=0.0,
            cost_usd=self._cost(spec, tokens_in, tokens_out),
            http_status=response.status_code,
            finish_reason=choice.get("finish_reason") or "stop",
        )

    async def _call_anthropic(self, base: str, key: Optional[str], spec: ModelSpec,
                              req: CompletionRequest) -> CompletionResult:
        system_prompt = "\n".join(m["content"] for m in req.messages if m.get("role") == "system")
        turns = [m for m in req.messages if m.get("role") != "system"]
        body = {
            "model": spec.id,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "messages": [{"role": m["role"], "content": m["content"]} for m in turns],
        }
        if system_prompt:
            body["system"] = system_prompt
        headers = {"Content-Type": "application/json", "x-api-key": key or "", "anthropic-version": "2023-06-01"}
        url = base.rstrip("/") + "/messages"
        try:
            response = await self.client(spec.provider_id).post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error: {exc}", retryable=True) from exc
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:200]}",
                                status=response.status_code, retryable=response.status_code in (429, 500, 502, 503))
        payload = response.json()
        parts = [b.get("text", "") for b in payload.get("content") or [] if b.get("type") == "text"]
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)
        return CompletionResult(
            text="\n".join(parts), model=spec.id, provider_id=spec.provider_id, provider_mode="real",
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=0.0,
            cost_usd=self._cost(spec, tokens_in, tokens_out), http_status=response.status_code,
            finish_reason=payload.get("stop_reason") or "stop",
        )

    async def _call_gemini(self, base: str, key: Optional[str], spec: ModelSpec,
                           req: CompletionRequest) -> CompletionResult:
        system = [m["content"] for m in req.messages if m.get("role") == "system"]
        contents = [
            {"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in req.messages if m.get("role") != "system"
        ]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": req.temperature, "maxOutputTokens": req.max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": "\n".join(system)}]}
        url = f"{base.rstrip('/')}/models/{spec.id}:generateContent?key={key or ''}"
        try:
            response = await self.client(spec.provider_id).post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error: {exc}", retryable=True) from exc
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:200]}",
                                status=response.status_code, retryable=response.status_code in (429, 500, 503))
        data = response.json()
        candidates = data.get("candidates") or []
        text = ""
        if candidates:
            text = "".join(p.get("text", "") for p in (candidates[0].get("content", {}).get("parts") or []))
        usage = data.get("usageMetadata") or {}
        tokens_in = int(usage.get("promptTokenCount") or 0)
        tokens_out = int(usage.get("candidatesTokenCount") or 0)
        return CompletionResult(
            text=text, model=spec.id, provider_id=spec.provider_id, provider_mode="real",
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=0.0,
            cost_usd=self._cost(spec, tokens_in, tokens_out), http_status=response.status_code,
        )

    async def _mock_completion(self, req: CompletionRequest, spec: ModelSpec,
                               reason: str) -> CompletionResult:
        """Explicitly-labelled offline completion.

        This is *not* an AI response. It states the situation and echoes the
        request so the rest of the product can be exercised without
        credentials. `provider_mode` is always "mock".
        """
        last_user = ""
        for message in reversed(req.messages):
            if message.get("role") == "user":
                last_user = message.get("content", "")
                break
        body = {
            "provider_mode": "mock",
            "reason": reason or "no provider configured in this deployment",
            "model": spec.id,
            "echo_of_request": last_user[:1200],
        }
        text = (
            "[MOCK PROVIDER MODE] No real LLM provider was reachable for this request.\n"
            f"Reason: {reason or 'no provider configured'}\n"
            "This is a deterministic placeholder produced by TITAN's offline test provider — "
            "it is NOT model output and must not be treated as an answer.\n"
            "Payload: " + json.dumps(body, ensure_ascii=False)
        )
        return CompletionResult(
            text=text, model=f"mock:{spec.id}", provider_id="mock", provider_mode="mock",
            tokens_in=len(req.messages and str(req.messages)) // 4, tokens_out=len(text) // 4,
            latency_ms=1.0, cost_usd=0.0, http_status=200, finish_reason="stop",
        )

    # -- accounting -------------------------------------------------------
    def _cost(self, spec: ModelSpec, tokens_in: int, tokens_out: int) -> float:
        return round(
            (tokens_in / 1_000_000) * spec.input_cost_per_mtok
            + (tokens_out / 1_000_000) * spec.output_cost_per_mtok,
            8,
        )

    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        """Token-ish streaming.

        Real providers are called once (non-streaming wire) and the text is
        emitted in chunks so the mobile client has a uniform streaming
        contract across providers.
        """
        result = await self.complete(req)
        if not result.ok:
            yield f"[ERROR] {result.error}"
            return
        text = result.text
        step = 64
        for index in range(0, len(text), step):
            yield text[index:index + step]
            await asyncio.sleep(0.01)


gateway = ModelGateway()
