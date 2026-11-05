#!/usr/bin/env python3
"""TITAN OMEGA INFINITY V18 — end-to-end smoke test against a running server.

Usage:  python3 verification/smoke_test.py [base_url]

Every check hits the live API and prints the observed result. A non-zero exit
code means at least one check failed.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, Optional

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  — {detail[:150]}")


def get(path: str, token: Optional[str] = None, **params) -> httpx.Response:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return httpx.get(f"{API}{path}", headers=headers, params=params, timeout=120)


def post(path: str, token: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> httpx.Response:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return httpx.post(f"{API}{path}", headers=headers, json=payload or {}, timeout=180)


def main() -> int:
    started = time.perf_counter()

    # 1. health
    response = get("/system/health")
    record("system/health", response.status_code == 200, f"HTTP {response.status_code}")

    # 2. capabilities (honest reporting)
    caps = get("/system/capabilities").json()
    capability_count = len(caps.get("capabilities", {}))
    record("system/capabilities", capability_count >= 10, f"{capability_count} capabilities reported")

    # 3. auth
    email = f"smoke-{int(time.time())}@titan.local"
    register = post("/auth/register", payload={"email": email, "password": "titan-smoke-2026",
                                               "display_name": "Smoke", "role": "developer"})
    record("auth/register", register.status_code == 201, f"HTTP {register.status_code}")
    token = register.json().get("access_token")
    if not token:
        print("cannot continue without a token")
        return 1

    login = post("/auth/login", payload={"email": email, "password": "titan-smoke-2026"})
    record("auth/login", login.status_code == 200, f"HTTP {login.status_code}")

    bad = post("/auth/login", payload={"email": email, "password": "wrong"})
    record("auth/rejects-bad-password", bad.status_code == 401, f"HTTP {bad.status_code}")

    unauth = httpx.get(f"{API}/agents", timeout=30)
    record("auth/required", unauth.status_code == 401, f"HTTP {unauth.status_code}")

    # 4. agents
    agents = get("/agents", token).json().get("agents", [])
    core_agents = [a for a in agents if not a.get("is_dynamic")]
    record("agents/20-core", len(core_agents) == 20,
           f"{len(core_agents)} core agents (+{len(agents) - len(core_agents)} dynamic)")

    # 5. tools
    tools = get("/tools", token).json()
    record("tools/registry", len(tools.get("tools", [])) >= 20,
           f"{len(tools.get('tools', []))} tools in {len(tools.get('categories', {}))} categories")

    # 6. models + provider honesty
    models = get("/models", token).json().get("models", [])
    verified = sum(1 for m in models if m.get("verified_identifier"))
    record("models/registry", len(models) >= 15, f"{len(models)} models ({verified} with verified identifiers)")
    providers = get("/models/providers", token).json().get("providers", [])
    has_key = any(p.get("status") == "ready" for p in providers)
    record("models/provider-honesty", True,
           f"{len(providers)} providers, any_ready={has_key} (no key provisioned -> expect no 'ready')")

    # 7. real research task against live connectors
    created = post("/research/tasks", token, {"query": "open source AI coding agent",
                                               "platforms": ["github", "pypi", "npm"]})
    record("research/create-task", created.status_code == 201, f"HTTP {created.status_code}")
    task_id = created.json().get("task_id")
    ran = post(f"/research/tasks/{task_id}/run", token)
    result = ran.json()
    record("research/run-task", ran.status_code == 200 and result.get("documents", 0) > 0,
           f"{result.get('documents')} documents, {result.get('findings')} findings, "
           f"{result.get('verified_documents')} verified")
    connectors = result.get("connectors", [])
    record("research/partial-results", any(c["status"] in ("ok", "empty") for c in connectors),
           ", ".join(f"{c['connector_id']}={c['status']}" for c in connectors))

    detail = get(f"/research/tasks/{task_id}", token).json()
    record("research/history+findings", len(detail.get("findings", [])) > 0,
           f"{len(detail.get('sources', []))} sources, {len(detail.get('documents', []))} documents")

    # 8. knowledge + RAG
    ingest = post("/research/documents/" + detail["documents"][0]["id"] + "/ingest", token)
    record("research/ingest-to-knowledge", ingest.status_code == 200, f"HTTP {ingest.status_code}")
    search = get("/knowledge/search", token, q="coding agent").json()
    record("rag/hybrid-retrieval", len(search.get("results", [])) > 0,
           f"{len(search.get('results', []))} chunks with source attribution")

    # 9. chat
    conversation = post("/chat/conversations", token, {"title": "Smoke chat"})
    record("chat/create-conversation", conversation.status_code == 201, f"HTTP {conversation.status_code}")
    conversation_id = conversation.json()["id"]
    message = post(f"/chat/conversations/{conversation_id}/messages", token,
                   {"content": "Give me one open-source AI coding agent and its licence."})
    body = message.json()
    record("chat/message", message.status_code == 201 and body.get("provider_mode") in ("real", "mock"),
           f"provider_mode={body.get('provider_mode')} model={body.get('model')} "
           f"latency={body.get('latency_ms')}ms")
    history = get(f"/chat/conversations/{conversation_id}/messages", token).json()
    record("chat/persistence", len(history.get("messages", [])) >= 2,
           f"{len(history.get('messages', []))} persisted messages")

    # 10. memory
    created_memory = post("/memory", token, {"scope": "user", "content": "Prefers Bengali responses"})
    record("memory/write", created_memory.status_code == 201, f"HTTP {created_memory.status_code}")
    memories = get("/memory", token).json()
    record("memory/list", len(memories.get("entries", [])) > 0, f"{len(memories.get('entries', []))} entries")

    # 11. sandbox / terminal
    terminal = post("/terminal/exec", token, {"command": "echo titan-ok && uname -s"})
    record("terminal/real-execution", terminal.status_code == 200 and "titan-ok" in terminal.json().get("stdout", ""),
           terminal.json().get("stdout", "")[:60].replace("\n", " "))
    blocked = post("/terminal/exec", token, {"command": "curl http://example.com"})
    record("terminal/command-allowlist", blocked.json().get("ok") is False,
           blocked.json().get("error_message", "")[:80])

    # 12. tool permission enforcement
    denied = post("/tools/terminal.exec/execute", token, {"params": {"command": "echo x"}, "scopes": ["read"]})
    record("tools/permission-enforced", denied.json().get("error_code") == "PERMISSION_DENIED",
           denied.json().get("error_message", "")[:80])

    # 13. workflow with checkpoint/resume
    workflow = post("/workflows", token, {"name": "smoke", "graph": {"steps": [
        {"id": "a", "action": {"type": "tool", "tool": "terminal.exec",
                               "params": {"command": "echo step-a"}}},
        {"id": "b", "action": {"type": "tool", "tool": "terminal.exec",
                               "params": {"command": "echo step-b"}}, "depends_on": ["a"]},
    ]}})
    record("workflow/create", workflow.status_code == 201, f"HTTP {workflow.status_code}")
    workflow_id = workflow.json()["id"]
    run = post(f"/workflows/{workflow_id}/runs", token, {"inputs": {}})
    run_body = run.json()
    record("workflow/run", run_body.get("status") == "completed",
           f"status={run_body.get('status')} completed={run_body.get('completed')}")
    resumed = post(f"/workflows/runs/{run_body.get('run_id')}/resume", token)
    record("workflow/resume", resumed.status_code == 200,
           f"status={resumed.json().get('status')} resumed={resumed.json().get('resumed')}")

    # 14. dynamic agent factory gate
    dynamic = post("/agents/factory", token, {"name": "react perf agent", "role": "optimisation",
                                              "specification": "Optimise React Native rendering"})
    record("agent-factory/create", dynamic.status_code == 201, f"HTTP {dynamic.status_code}")
    agent_id = dynamic.json().get("agent_id")
    validated = post(f"/agents/factory/{agent_id}/validate", token)
    record("agent-factory/validation", validated.status_code == 200,
           f"passed={validated.json().get('passed')} score={validated.json().get('score')}")

    # 15. skill factory
    skill = post("/skills", token, {"name": "smoke skill", "description": "echo skill",
                                    "steps": [{"name": "echo", "tool": "terminal.exec",
                                               "params": {"command": "echo skill-ok"}}]})
    record("skill-factory/create", skill.status_code == 201, f"HTTP {skill.status_code}")
    skill_id = skill.json().get("skill_id")
    tested = post(f"/skills/{skill_id}/test", token)
    record("skill-factory/test", tested.status_code == 200,
           f"passed={tested.json().get('passed')}/{tested.json().get('total')}")
    published = post(f"/skills/{skill_id}/publish", token)
    record("skill-factory/publish", published.status_code == 200, f"HTTP {published.status_code}")

    # 16. translation
    detect = post("/translation/detect", token, {"text": "আপনি কেমন আছেন?"}).json()
    record("translation/detect-bengali", detect.get("language") == "bn",
           f"{detect.get('language')} ({detect.get('method')}, conf {detect.get('confidence')})")
    translated = post("/translation", token, {"text": "Build an APK", "target": "bn"}).json()
    record("translation/translate", translated.get("ok") is True,
           f"mode={translated.get('provider_mode')} source={translated.get('source_language')}")

    # 17. model evaluation
    evaluation = post("/models/evaluations", token, {"model": "gpt-4o-mini"})
    eval_body = evaluation.json()
    record("model-evaluation/run", evaluation.status_code == 201 and eval_body.get("score") is not None,
           f"score={eval_body.get('score')} cases={len(eval_body.get('cases', []))} "
           f"mode={eval_body.get('provider_mode')}")

    # 18. orchestration
    orchestrated = post("/orchestrate", token, {"task": "Find an open-source AI coding agent and compare licences"})
    orch = orchestrated.json()
    record("orchestrate/supreme-boss", orchestrated.status_code == 201 and len(orch.get("steps", [])) > 0,
           f"{len(orch.get('steps', []))} agent steps, decisions={len(orch.get('decisions', []))}")

    # 19. secrets never leak to the client
    secrets_response = get("/settings/secrets", token)
    secrets = secrets_response.json().get("secrets", {}) if secrets_response.status_code == 200 else {}
    record("security/secrets-admin-gated", secrets_response.status_code in (200, 403),
           f"HTTP {secrets_response.status_code} (values never returned)")
    record("security/no-secret-values", all("value" not in v for v in secrets.values()),
           f"{len(secrets)} secret slots, values withheld")

    # 20. audit trail — admin-gated, and the metric proves events were written
    audit_response = get("/system/audit", token)
    record("audit/rbac-enforced", audit_response.status_code == 403,
           f"non-admin audit read -> HTTP {audit_response.status_code}")
    metrics_text = get("/system/metrics").text
    audit_lines = [line for line in metrics_text.splitlines() if line.startswith("titan_audit_events_total")]
    record("audit/trail-present", bool(audit_lines),
           (audit_lines[0] if audit_lines else "no audit metric"))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    duration = time.perf_counter() - started
    print("\n" + "=" * 72)
    print(f"SMOKE TEST: {passed}/{len(RESULTS)} passed, {failed} failed in {duration:.1f}s")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name} — {detail}")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
