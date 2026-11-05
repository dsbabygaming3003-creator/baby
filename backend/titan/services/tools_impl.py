"""Concrete tool implementations registered into the Tool Execution Engine."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import httpx

from ..config import settings
from ..security.net import SSRFError, http_client, validate_url
from .media import translation_service, voice_service
from .observability import log
from .rag import retriever
from .research_connectors import CONNECTOR_INDEX, PLATFORM_INDEX
from .sandbox import backend as sandbox_backend
from .tools import Tool, ToolContext, ToolError, register


# ---------------------------------------------------------------------------
# Research tools
# ---------------------------------------------------------------------------
async def _research_search(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from .research_connectors import run_connectors

    query = params.get("query")
    if not query:
        raise ToolError("INVALID_INPUT", "query is required")
    platforms = params.get("platforms") or []
    limit = int(params.get("limit") or 5)
    outcomes = await run_connectors(query, platforms, limit)
    documents: List[Dict[str, Any]] = []
    for outcome in outcomes:
        for doc in outcome.documents:
            documents.append({"title": doc.title, "url": doc.url, "snippet": doc.snippet,
                              "connector": outcome.connector_id})
    return {
        "query": query,
        "documents": documents[: limit * 4],
        "connector_status": [o.to_dict() for o in outcomes],
        "sources_unavailable": [o.connector_id for o in outcomes if o.status not in ("ok", "empty")],
    }


async def _research_fetch_source(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    url = params.get("url")
    if not url:
        raise ToolError("INVALID_INPUT", "url is required")
    try:
        validate_url(url)
    except SSRFError as exc:
        raise ToolError("BLOCKED_BY_POLICY", str(exc)) from exc
    try:
        async with http_client(timeout=settings.research_request_timeout) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise ToolError("FETCH_FAILED", f"{type(exc).__name__}: {exc}") from exc
    body = response.text[: settings.research_max_document_chars]
    return {"url": url, "http_status": response.status_code, "content_type": response.headers.get("content-type", ""),
            "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(),
            "content": body}


async def _research_verify(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    url = params.get("url")
    if not url:
        raise ToolError("INVALID_INPUT", "url is required")
    connector_id = params.get("connector_id")
    connector = CONNECTOR_INDEX.get(connector_id) if connector_id else None
    if connector is None:
        from .research_connectors import HttpConnector

        connector = HttpConnector()
    from .research_connectors import RawDocument

    verification = await connector.verify(RawDocument(title=params.get("title", ""), url=url))
    return {"url": url, "status": verification.status, "confidence": verification.confidence,
            "detail": verification.detail, "http_status": verification.http_status}


async def _github_repo(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    full_name = params.get("repo")
    if not full_name:
        raise ToolError("INVALID_INPUT", "repo is required")
    connector = PLATFORM_INDEX.get("github")
    if connector is None:
        raise ToolError("UNAVAILABLE", "github connector is not registered")
    details = await connector.repo_details(full_name)
    releases = await connector.releases(full_name)
    return {"details": details, "releases": releases}


# ---------------------------------------------------------------------------
# Knowledge / memory
# ---------------------------------------------------------------------------
async def _knowledge_search(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    query = params.get("query")
    if not query:
        raise ToolError("INVALID_INPUT", "query is required")
    if ctx.session is not None:
        chunks = await retriever.retrieve(ctx.session, query, top_k=int(params.get("top_k") or 5),
                                          org_id=ctx.org_id)
        return {"query": query, "results": [c.to_dict() for c in chunks]}
    from ..db import session_scope

    async with session_scope() as session:
        chunks = await retriever.retrieve(session, query, top_k=int(params.get("top_k") or 5),
                                          org_id=ctx.org_id)
    return {"query": query, "results": [c.to_dict() for c in chunks]}


async def _knowledge_ingest(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from ..db import session_scope
    from ..models import KnowledgeDocument
    from .rag import ingest_document

    content = params.get("content")
    if not content:
        raise ToolError("INVALID_INPUT", "content is required")

    async def _write(session) -> Dict[str, Any]:
        document = KnowledgeDocument(
            org_id=ctx.org_id, source_type=params.get("source_type", "manual"),
            title=params.get("title", "")[:500], content=content,
            source_url=params.get("url", ""), verification_status=params.get("verification_status", "unverified"),
            confidence=float(params.get("confidence", 0.5)),
            licence_note=params.get("licence_note", "operator supplied"),
        )
        session.add(document)
        await session.flush()
        chunks = await ingest_document(session, document_id=document.id, content=content)
        return {"document_id": document.id, "chunks": chunks}

    if ctx.session is not None:
        return await _write(ctx.session)
    async with session_scope() as session:
        return await _write(session)


async def _memory_write(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from ..db import session_scope
    from .memory import memory

    content = params.get("content")
    if not content:
        raise ToolError("INVALID_INPUT", "content is required")

    async def _write(session) -> Dict[str, Any]:
        entry = await memory.write(
            session, scope=params.get("scope", "agent"), content=content,
            kind=params.get("kind", "note"), scope_key=params.get("scope_key", ""),
            org_id=ctx.org_id, source=params.get("source", "agent"),
        )
        return {"memory_id": entry.id, "scope": entry.scope, "version": entry.version}

    if ctx.session is not None:
        return await _write(ctx.session)
    async with session_scope() as session:
        return await _write(session)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
async def _http_fetch(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    url = params.get("url")
    if not url:
        raise ToolError("INVALID_INPUT", "url is required")
    try:
        validate_url(url)
    except SSRFError as exc:
        raise ToolError("BLOCKED_BY_POLICY", str(exc)) from exc
    method = (params.get("method") or "GET").upper()
    try:
        async with http_client(timeout=settings.research_request_timeout) as client:
            response = await client.request(method, url, params=params.get("params"))
    except httpx.HTTPError as exc:
        raise ToolError("FETCH_FAILED", f"{type(exc).__name__}: {exc}") from exc
    return {"url": url, "status": response.status_code, "content_type": response.headers.get("content-type", ""),
            "body": response.text[:12000]}


# ---------------------------------------------------------------------------
# Project / files / code
# ---------------------------------------------------------------------------
def _project_paths(project_id: str):
    try:
        root = sandbox_backend.project_root(project_id or "default")
    except Exception as exc:
        raise ToolError("INVALID_PROJECT", str(exc)) from exc
    return root


async def _project_read(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    path = params.get("path")
    if not path:
        raise ToolError("INVALID_INPUT", "path is required")
    root = _project_paths(ctx.project_id or "default")
    try:
        target = sandbox_backend.resolve_path(ctx.project_id or "default", path)
    except Exception as exc:
        raise ToolError("INVALID_INPUT", str(exc)) from exc
    if not target.exists():
        raise ToolError("NOT_FOUND", f"'{path}' does not exist in the project")
    if target.is_dir():
        entries = []
        for item in sorted(target.iterdir())[:500]:
            entries.append({"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size})
        return {"path": path, "type": "directory", "entries": entries}
    data = target.read_bytes()
    return {"path": path, "type": "file", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content": data.decode("utf-8", "replace")[:60000]}


async def _project_write(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    path = params.get("path")
    content = params.get("content")
    if not path:
        raise ToolError("INVALID_INPUT", "path is required")
    if content is None:
        raise ToolError("INVALID_INPUT", "content is required")
    project_id = ctx.project_id or "default"
    try:
        target = sandbox_backend.resolve_path(project_id, path)
    except Exception as exc:
        raise ToolError("INVALID_INPUT", str(exc)) from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content), encoding="utf-8")
    return {"path": path, "size": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


async def _code_search(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    pattern = params.get("pattern")
    if not pattern:
        raise ToolError("INVALID_INPUT", "pattern is required")
    project_id = ctx.project_id or "default"
    root = _project_paths(project_id)
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ToolError("INVALID_INPUT", f"invalid pattern: {exc}") from exc
    matches: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if len(matches) >= 200:
            break
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                matches.append({"file": str(path.relative_to(root)), "line": number, "text": line.strip()[:300]})
                if len(matches) >= 200:
                    break
    return {"pattern": pattern, "matches": matches, "count": len(matches)}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
async def _terminal_exec(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    command = params.get("command")
    if not command:
        raise ToolError("INVALID_INPUT", "command is required")
    result = await sandbox_backend.run(command, project_id=ctx.project_id or "default")
    return result.to_dict()


async def _test_run(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    command = params.get("command") or "python3 -m pytest -q"
    result = await sandbox_backend.run(command, project_id=ctx.project_id or "default",
                                       timeout=int(params.get("timeout", 120)))
    return {"command": command, "exit_code": result.exit_code, "ok": result.ok,
            "stdout": result.stdout[-8000:], "stderr": result.stderr[-4000:],
            "timed_out": result.timed_out, "duration_ms": round(result.duration_ms, 2)}


async def _build_run(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from ..db import session_scope
    from .media import build_service

    command = params.get("command")
    if not command:
        raise ToolError("INVALID_INPUT", "command is required")
    async with session_scope() as session:
        job = await build_service.run_build(
            session, project_id=ctx.project_id, name=params.get("name", "agent build"),
            command=command, target=params.get("target", "apk"),
            variant=params.get("variant", "debug"), org_id=ctx.org_id)
        return {"build_job_id": job.id, "status": job.status, "exit_code": job.exit_code,
                "log_path": job.log_path, "duration_ms": job.duration_ms, "error": job.error}


async def _database_query(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Read-only query against TITAN's own database (SELECT only)."""
    from sqlalchemy import text

    from ..db import session_scope

    statement = (params.get("sql") or "").strip()
    if not statement:
        raise ToolError("INVALID_INPUT", "sql is required")
    if not re.match(r"^\s*select\b", statement, re.IGNORECASE):
        raise ToolError("FORBIDDEN", "only SELECT statements are permitted through this tool")
    async def _query(session) -> Dict[str, Any]:
        rows = (await session.execute(text(statement))).mappings().all()
        return {"rows": [dict(row) for row in rows[:200]], "count": len(rows)}

    if ctx.session is not None:
        return await _query(ctx.session)
    async with session_scope() as session:
        return await _query(session)


# ---------------------------------------------------------------------------
# Models / translation / voice / media
# ---------------------------------------------------------------------------
async def _models_list(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from .gateway import gateway

    return {"models": [m.__dict__ for m in gateway.list_models()],
            "providers": [p.to_dict() if hasattr(p, "to_dict") else p.__dict__ for p in gateway.list_providers()]}


async def _models_evaluate(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from ..db import session_scope
    from .media import evaluation_service

    model_id = params.get("model")
    if not model_id:
        raise ToolError("INVALID_INPUT", "model is required")
    if ctx.session is not None:
        return await evaluation_service.evaluate_model(ctx.session, model_id, org_id=ctx.org_id)
    async with session_scope() as session:
        return await evaluation_service.evaluate_model(session, model_id, org_id=ctx.org_id)


async def _translate_text(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    text = params.get("text")
    target = params.get("target")
    if not text or not target:
        raise ToolError("INVALID_INPUT", "text and target are required")
    return await translation_service.translate(text, target, source=params.get("source"),
                                               glossary=params.get("glossary"))


async def _translate_detect(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from .media import detect_language

    return detect_language(params.get("text") or "")


async def _voice_capabilities(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    return await voice_service.capabilities()


async def _voice_transcribe(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    from ..db import session_scope

    async with session_scope() as session:
        return await voice_service.transcribe(session, audio_path=params.get("audio_path", ""),
                                              language=params.get("language", "bn"), org_id=ctx.org_id)


async def _voice_speak(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    text = params.get("text")
    if not text:
        raise ToolError("INVALID_INPUT", "text is required")
    return await voice_service.speak(text, language=params.get("language", "bn"),
                                     voice=params.get("voice"))


async def _image_analyse(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Image analysis requires a configured vision provider.

    Without one, the tool reports the boundary instead of inventing a caption.
    """
    from .gateway import CompletionRequest, gateway

    path = params.get("path")
    if not path:
        raise ToolError("INVALID_INPUT", "path is required")
    file_path = Path(path)
    if not file_path.exists():
        raise ToolError("NOT_FOUND", f"image not found: {path}")
    result = await gateway.complete(CompletionRequest(
        messages=[{"role": "user", "content": "Describe the attached image factually."}],
        task="vision", max_tokens=512,
    ))
    if result.provider_mode == "mock":
        return {"ok": False, "error": "no vision-capable provider is configured in this deployment",
                "provider_mode": result.provider_mode, "bytes": file_path.stat().st_size}
    return {"ok": True, "description": result.text, "model": result.model,
            "provider_mode": result.provider_mode}


# ---------------------------------------------------------------------------
# Security / release
# ---------------------------------------------------------------------------
async def _security_scan(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Run TITAN's own security checks over the project tree."""
    from ..security.net import scan_injection

    root = _project_paths(ctx.project_id or "default")
    findings: List[Dict[str, Any]] = []
    scanned = 0
    patterns = [
        (r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{12,}['\"]", "hardcoded-credential"),
        (r"(?i)verify\s*=\s*False\s*", "tls-verification-disabled"),
        (r"(?i)shell\s*=\s*True\s*", "shell-injection-risk"),
        (r"(?i)eval\(", "dynamic-eval"),
        (r"(?i)pickle\.loads\(", "unsafe-deserialization"),
    ]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned += 1
        for pattern, kind in patterns:
            for match in re.finditer(pattern, text):
                line = text[: match.start()].count("\n") + 1
                findings.append({"file": str(path.relative_to(root)), "line": line, "kind": kind,
                                 "excerpt": match.group(0)[:120]})
        injection = scan_injection(text)
        if injection.is_suspicious:
            findings.append({"file": str(path.relative_to(root)), "line": 0,
                             "kind": "prompt-injection-pattern",
                             "excerpt": f"risk {injection.risk}"})
    return {"scanned_files": scanned, "findings": findings, "count": len(findings)}


async def _release_verify(params: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Verify an APK artifact structurally (signature block, dex, manifest)."""
    path = params.get("path")
    if not path:
        raise ToolError("INVALID_INPUT", "path is required")
    artifact = Path(path)
    if not artifact.exists():
        raise ToolError("NOT_FOUND", f"artifact not found: {path}")
    data = artifact.read_bytes()
    return {
        "path": str(artifact),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "has_dex": b"classes.dex" in data,
        "has_manifest": b"AndroidManifest.xml" in data,
        "has_v1_signature": b"META-INF/" in data and (b".RSA" in data or b".DSA" in data),
        "has_v2_signature_block": b"APK Sig Block 42" in data,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_all() -> int:
    register(Tool(
        id="research.search", name="Global research search", category="web_research",
        description="Search every enabled research connector and return documents plus per-connector status.",
        input_schema={"type": "object", "required": ["query"],
                      "properties": {"query": {"type": "string"}, "platforms": {"type": "array"},
                                     "limit": {"type": "integer"}}},
        output_schema={"type": "object", "properties": {"documents": {"type": "array"},
                                                        "connector_status": {"type": "array"}}},
        permission_scope="network", timeout_seconds=120, handler=_research_search))

    register(Tool(
        id="research.fetch_source", name="Fetch research source", category="web_research",
        description="Fetch a specific URL through the egress policy and return the content + hash.",
        input_schema={"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=60,
        handler=_research_fetch_source))

    register(Tool(
        id="research.verify", name="Verify source", category="web_research",
        description="Verify that a source URL resolves and record the verification status.",
        input_schema={"type": "object", "required": ["url"],
                      "properties": {"url": {"type": "string"}, "connector_id": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=45,
        handler=_research_verify))

    register(Tool(
        id="github.repo", name="GitHub repository inspector", category="github",
        description="Fetch repository metadata, licence, activity and recent releases.",
        input_schema={"type": "object", "required": ["repo"], "properties": {"repo": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=45,
        handler=_github_repo))

    register(Tool(
        id="knowledge.search", name="Knowledge search (RAG)", category="database",
        description="Hybrid BM25 + dense retrieval over the knowledge base with source attribution.",
        input_schema={"type": "object", "required": ["query"],
                      "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=45,
        handler=_knowledge_search))

    register(Tool(
        id="knowledge.ingest", name="Ingest knowledge", category="database",
        description="Store a document, chunk it and index its embeddings.",
        input_schema={"type": "object", "required": ["content"], "properties": {"content": {"type": "string"},
                                                                                 "title": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="write", timeout_seconds=45,
        handler=_knowledge_ingest))

    register(Tool(
        id="memory.write", name="Write memory", category="database",
        description="Write a memory entry into one of the eight memory scopes.",
        input_schema={"type": "object", "required": ["content"],
                      "properties": {"content": {"type": "string"}, "scope": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="write", timeout_seconds=30,
        handler=_memory_write))

    register(Tool(
        id="http.fetch", name="HTTP fetch", category="api_client",
        description="Perform an allowlisted HTTP request and return the response.",
        input_schema={"type": "object", "required": ["url"],
                      "properties": {"url": {"type": "string"}, "method": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=45,
        handler=_http_fetch))

    register(Tool(
        id="project.read", name="Read project file", category="file_system",
        description="Read a file or list a directory inside the project's sandbox root.",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=30,
        handler=_project_read))

    register(Tool(
        id="project.write", name="Write project file", category="file_system",
        description="Create or overwrite a file inside the project's sandbox root.",
        input_schema={"type": "object", "required": ["path", "content"],
                      "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="write", timeout_seconds=30,
        handler=_project_write))

    register(Tool(
        id="code.search", name="Code search", category="code_editor",
        description="Regex search across the project tree.",
        input_schema={"type": "object", "required": ["pattern"], "properties": {"pattern": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=60,
        handler=_code_search))

    register(Tool(
        id="terminal.exec", name="Terminal", category="terminal",
        description="Execute an allowlisted command inside the project's sandbox.",
        input_schema={"type": "object", "required": ["command"], "properties": {"command": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="execute", timeout_seconds=90,
        handler=_terminal_exec))

    register(Tool(
        id="test.run", name="Test runner", category="testing",
        description="Execute the project's test command and report real pass/fail output.",
        input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="execute", timeout_seconds=180,
        handler=_test_run))

    register(Tool(
        id="build.run", name="Build service", category="build_system",
        description="Run a build command in the sandbox, capture logs and register artifacts.",
        input_schema={"type": "object", "required": ["command"], "properties": {"command": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="execute", timeout_seconds=600,
        handler=_build_run))

    register(Tool(
        id="database.query", name="Read-only database query", category="database",
        description="Run a SELECT against TITAN's own database (writes are rejected).",
        input_schema={"type": "object", "required": ["sql"], "properties": {"sql": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=45,
        handler=_database_query))

    register(Tool(
        id="models.list", name="List models", category="model_execution",
        description="List the model registry and provider registry.",
        input_schema={"type": "object", "properties": {}}, output_schema={"type": "object"},
        permission_scope="read", timeout_seconds=30, handler=_models_list))

    register(Tool(
        id="models.evaluate", name="Evaluate model", category="model_execution",
        description="Run the evaluation dataset against a model and store the measured scores.",
        input_schema={"type": "object", "required": ["model"], "properties": {"model": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=300,
        handler=_models_evaluate))

    register(Tool(
        id="translate.text", name="Translate", category="translation",
        description="Translate text with technical-term preservation.",
        input_schema={"type": "object", "required": ["text", "target"],
                      "properties": {"text": {"type": "string"}, "target": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=90,
        handler=_translate_text))

    register(Tool(
        id="translate.detect", name="Detect language", category="translation",
        description="Detect the language of a text.",
        input_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=30,
        handler=_translate_detect))

    register(Tool(
        id="voice.capabilities", name="Voice capabilities", category="audio",
        description="Report the ASR/TTS engines available in this deployment.",
        input_schema={"type": "object", "properties": {}}, output_schema={"type": "object"},
        permission_scope="read", timeout_seconds=30, handler=_voice_capabilities))

    register(Tool(
        id="voice.transcribe", name="Transcribe audio", category="audio",
        description="Transcribe an audio file with the available ASR engine.",
        input_schema={"type": "object", "required": ["audio_path"],
                      "properties": {"audio_path": {"type": "string"}, "language": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=300,
        handler=_voice_transcribe))

    register(Tool(
        id="voice.speak", name="Speak text", category="audio",
        description="Synthesise speech with the available TTS engine.",
        input_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=180,
        handler=_voice_speak))

    register(Tool(
        id="image.analyse", name="Analyse image", category="image",
        description="Describe an image using a configured vision provider.",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="network", timeout_seconds=120,
        handler=_image_analyse))

    register(Tool(
        id="security.scan", name="Security scan", category="security",
        description="Scan the project for hardcoded credentials, unsafe patterns and injection markers.",
        input_schema={"type": "object", "properties": {}}, output_schema={"type": "object"},
        permission_scope="read", timeout_seconds=120, handler=_security_scan))

    register(Tool(
        id="release.verify", name="Verify release artifact", category="build_system",
        description="Structurally verify an APK (dex, manifest, signature blocks, checksum).",
        input_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        output_schema={"type": "object"}, permission_scope="read", timeout_seconds=60,
        handler=_release_verify))

    return len(list_tool_ids())


def list_tool_ids() -> List[str]:
    from .tools import registry

    return [t.id for t in registry.all()]
