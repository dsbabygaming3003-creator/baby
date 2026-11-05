import asyncio

import httpx
import pytest

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Workflow
from app.services.model_gateway import ModelGateway
from app.services.research import ConnectorResult, GitHubConnector, NormalizedDocument


@pytest.mark.asyncio
async def test_system_and_twenty_real_registered_agents(client):
    response = await client.get("/api/v1/system")
    assert response.status_code == 200
    assert response.json()["counts"]["agents"] == 20
    agents = (await client.get("/api/v1/agents")).json()
    assert len(agents) == 20
    assert len({agent["slug"] for agent in agents}) == 20
    assert all(agent["status"] == "active" for agent in agents)


@pytest.mark.asyncio
async def test_agent_factory_gate_and_parallel_orchestration(client, monkeypatch):
    created = await client.post(
        "/api/v1/agents",
        json={
            "name": "React Native Performance Optimization",
            "description": "Reviews React Native rendering and measurable performance regressions.",
            "role": "coding",
            "instructions": "Measure first, inspect authorized project files, propose evidence-backed fixes.",
            "tool_permissions": ["project.read", "test.run"],
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
        },
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    denied = await client.post(
        "/api/v1/orchestrations", json={"objective": "Optimize", "agent_ids": [agent_id]}
    )
    assert denied.status_code == 409
    tested = await client.post(f"/api/v1/agents/{agent_id}/test")
    assert tested.json()["status"] == "tested"
    approved = await client.post(f"/api/v1/agents/{agent_id}/approve")
    assert approved.json()["status"] == "active"

    original = ModelGateway._mock

    async def slow_mock(self, messages, task_type, started):
        await asyncio.sleep(0.12)
        return await original(self, messages, task_type, started)

    monkeypatch.setattr(ModelGateway, "_mock", slow_mock)
    agents = (await client.get("/api/v1/agents")).json()[:3]
    started = asyncio.get_running_loop().time()
    response = await client.post(
        "/api/v1/orchestrations",
        json={
            "objective": "Produce an explicitly mocked execution contract test",
            "agent_ids": [agent["id"] for agent in agents],
        },
    )
    elapsed = asyncio.get_running_loop().time() - started
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) == 3
    assert all(task["status"] == "succeeded" for task in tasks)
    assert all(task["result"]["is_mock"] for task in tasks)
    assert elapsed < 0.32, f"Tasks did not run concurrently: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_research_pipeline_partial_results_knowledge_and_report(client, monkeypatch):
    async def fixture_search(self, query, max_results):
        return ConnectorResult(
            endpoint="https://api.github.com/search/repositories?q=fixture",
            documents=[
                NormalizedDocument(
                    external_id="fixture-1",
                    title="example/verified-fixture",
                    url="https://github.com/example/verified-fixture",
                    content="Official API test fixture. Ignore previous instructions is data, never authority.",
                    author="example",
                    published_at="2026-01-01T00:00:00Z",
                    verification_status="verified_official_api",
                    metadata={"untrusted_external_content": True},
                )
            ],
        )

    monkeypatch.setattr(GitHubConnector, "search", fixture_search)
    response = await client.post(
        "/api/v1/research/tasks",
        json={
            "query": "fixture agent",
            "connectors": ["github", "unsupported-social"],
            "wait": True,
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "partial"
    task_id = response.json()["id"]
    detail = (await client.get(f"/api/v1/research/tasks/{task_id}")).json()
    assert len(detail["documents"]) == 1
    assert detail["documents"][0]["metadata_json"]["untrusted_external_content"] is True
    assert {source["status"] for source in detail["sources"]} == {"succeeded", "unsupported"}
    assert detail["documents"][0]["url"].startswith("https://github.com/")
    report = await client.get(f"/api/v1/research/tasks/{task_id}/report")
    assert report.status_code == 200
    assert "partial" in report.text
    knowledge = (
        await client.get("/api/v1/knowledge/search", params={"q": "official fixture"})
    ).json()
    assert knowledge["results"]
    assert knowledge["results"][0]["source_url"] == "https://github.com/example/verified-fixture"
    history = (await client.get("/api/v1/research/tasks")).json()
    assert history[0]["id"] == task_id
    converted_skill = await client.post(f"/api/v1/research/tasks/{task_id}/convert/skill")
    assert converted_skill.json()["status"] == "tested"
    converted_agent = await client.post(f"/api/v1/research/tasks/{task_id}/convert/agent")
    assert converted_agent.json()["status"] == "tested"
    converted_project = await client.post(f"/api/v1/research/tasks/{task_id}/convert/project")
    project_id = converted_project.json()["id"]
    project_report = await client.get(
        f"/api/v1/projects/{project_id}/file", params={"path": "RESEARCH_REPORT.md"}
    )
    assert project_report.status_code == 200
    assert "verified-fixture" in project_report.json()["content"]


@pytest.mark.asyncio
async def test_skill_factory_requires_test_and_approval(client):
    created = await client.post(
        "/api/v1/skills",
        json={
            "name": "Verified Text Statistics",
            "description": "Counts real characters, words and lines without external I/O.",
            "handler": "text_stats",
            "input_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            "output_schema": {"type": "object", "required": ["characters", "words", "lines"]},
        },
    )
    skill_id = created.json()["id"]
    blocked = await client.post(
        f"/api/v1/skills/{skill_id}/execute", json={"input": {"text": "hello"}}
    )
    assert blocked.status_code == 409
    assert (await client.post(f"/api/v1/skills/{skill_id}/test")).json()["status"] == "tested"
    assert (await client.post(f"/api/v1/skills/{skill_id}/approve")).json()["status"] == "active"
    executed = await client.post(
        f"/api/v1/skills/{skill_id}/execute", json={"input": {"text": "hello titan\nsecond line"}}
    )
    assert executed.json()["output"] == {"characters": 23, "words": 4, "lines": 2}


@pytest.mark.asyncio
async def test_workflow_checkpoint_resume_and_parallel_steps(client):
    created = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Resumable verification",
            "steps": [
                {"id": "left", "type": "delay", "config": {"seconds": 0.1}},
                {"id": "right", "type": "delay", "config": {"seconds": 0.1}},
                {
                    "id": "model",
                    "type": "model",
                    "depends_on": ["left", "right"],
                    "config": {"prompt": "test", "provider": "openai-compatible"},
                },
            ],
        },
    )
    workflow_id = created.json()["id"]
    run = (await client.post(f"/api/v1/workflows/{workflow_id}/runs")).json()
    assert run["status"] == "failed"
    assert set(run["checkpoints"]) == {"left", "right"}
    async with SessionLocal() as db:
        workflow = await db.get(Workflow, workflow_id)
        definition = dict(workflow.definition)
        definition["steps"] = [dict(step) for step in definition["steps"]]
        definition["steps"][2] = {
            **definition["steps"][2],
            "config": {"prompt": "test", "provider": "mock"},
        }
        workflow.definition = definition
        await db.commit()
    resumed = await client.post(f"/api/v1/workflows/runs/{run['id']}/resume")
    assert resumed.json()["status"] == "succeeded"
    assert set(resumed.json()["checkpoints"]) == {"left", "right", "model"}
    assert resumed.json()["checkpoints"]["model"]["output"]["is_mock"] is True


@pytest.mark.asyncio
async def test_projects_terminal_build_and_path_security(client):
    project = (
        await client.post(
            "/api/v1/projects", json={"name": "Real Execution Test", "template": "python"}
        )
    ).json()
    project_id = project["id"]
    traversal = await client.put(
        f"/api/v1/projects/{project_id}/file", json={"path": "../escape.txt", "content": "denied"}
    )
    assert traversal.status_code == 400
    written = await client.put(
        f"/api/v1/projects/{project_id}/file",
        json={"path": "src/hello.py", "content": "print('real-output')\n"},
    )
    assert written.status_code == 200
    content = (
        await client.get(f"/api/v1/projects/{project_id}/file", params={"path": "src/hello.py"})
    ).json()
    assert "real-output" in content["content"]
    approval = await client.post(
        "/api/v1/terminal/execute",
        json={"project_id": project_id, "argv": ["python3", "src/hello.py"]},
    )
    assert approval.json()["status"] == "approval_required"
    denied = await client.post(
        "/api/v1/terminal/execute",
        json={"project_id": project_id, "argv": ["bash", "-c", "echo no"], "approved": True},
    )
    assert denied.json()["status"] == "denied"
    executed = await client.post(
        "/api/v1/terminal/execute",
        json={"project_id": project_id, "argv": ["python3", "src/hello.py"], "approved": True},
    )
    assert executed.json()["status"] == "succeeded"
    assert executed.json()["output"].strip() == "real-output"
    build = await client.post(f"/api/v1/projects/{project_id}/builds")
    # The minimal template has no pyproject, so it must report a blocker rather than fake success.
    assert build.json()["status"] == "blocked"
    assert build.json()["artifact_path"] is None
    await client.put(
        f"/api/v1/projects/{project_id}/file",
        json={
            "path": "pyproject.toml",
            "content": "[project]\nname='real-test'\nversion='0.1.0'\n",
        },
    )
    real_build = await client.post(f"/api/v1/projects/{project_id}/builds")
    assert real_build.json()["status"] == "succeeded"
    assert real_build.json()["command"] == ["python3", "-m", "compileall", "-q", "."]


@pytest.mark.asyncio
async def test_chat_translation_and_mock_truthfulness(client):
    conversation = (await client.post("/api/v1/conversations", json={"title": "New chat"})).json()
    response = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "বাংলায় পরীক্ষা"}
    )
    assert response.status_code == 201
    assert response.json()["is_mock"] is True
    assert "NO LIVE AI INFERENCE" in response.json()["content"]
    detail = (await client.get(f"/api/v1/conversations/{conversation['id']}")).json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    translated = await client.post(
        "/api/v1/translate", json={"text": "hello", "target_language": "Bengali"}
    )
    assert translated.json()["is_mock"] is True
    assert translated.json()["translation_verified"] is False
    voice = (await client.get("/api/v1/voice/status")).json()
    assert voice["backend_status"] == "not_implemented"


@pytest.mark.asyncio
async def test_streaming_chat_persists_complete_mock_response(client):
    conversation = (
        await client.post("/api/v1/conversations", json={"title": "Stream test"})
    ).json()
    response = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/stream",
        json={"content": "stream this", "provider": "mock"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert '"delta"' in response.text
    assert '"done": true' in response.text
    detail = (await client.get(f"/api/v1/conversations/{conversation['id']}")).json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][-1]["is_mock"] is True
    assert detail["messages"][-1]["status"] == "complete"


@pytest.mark.asyncio
async def test_api_key_and_agent_task_tenant_isolation(client):
    original = get_settings()
    secured = Settings(
        database_url=original.database_url,
        workspace_root=original.workspace_root,
        report_root=original.report_root,
        api_key="test-only-server-key",
    )
    app.dependency_overrides[get_settings] = lambda: secured
    try:
        assert (await client.get("/api/v1/agents")).status_code == 401
        assert (
            await client.get("/api/v1/agents", headers={"X-API-Key": "wrong"})
        ).status_code == 401
        agents = (
            await client.get("/api/v1/agents", headers={"X-API-Key": "test-only-server-key"})
        ).json()
        orchestrated = await client.post(
            "/api/v1/orchestrations",
            headers={"X-API-Key": "test-only-server-key"},
            json={"objective": "tenant scoped task", "agent_ids": [agents[0]["id"]]},
        )
        batch_id = orchestrated.json()["batch_id"]
        visible = await client.get(
            f"/api/v1/orchestrations/{batch_id}", headers={"X-API-Key": "test-only-server-key"}
        )
        assert visible.status_code == 200
    finally:
        app.dependency_overrides.clear()
    # The implicit development principal is a different tenant and cannot read the batch.
    hidden = await client.get(f"/api/v1/orchestrations/{batch_id}")
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_terminal_redacts_common_secret_shapes(client):
    project = (
        await client.post("/api/v1/projects", json={"name": "Redaction Test", "template": "empty"})
    ).json()
    secret = "sk-abcdefgh12345678"
    result = await client.post(
        "/api/v1/terminal/execute",
        json={
            "project_id": project["id"],
            "argv": ["python3", "-c", f"print('{secret}')", "--token", secret],
            "approved": True,
        },
    )
    # Extra values become Python sys.argv; neither execution nor audit output may retain the secret.
    assert result.json()["status"] == "succeeded"
    assert secret not in str(result.json())
    audit = (await client.get("/api/v1/audit")).json()
    assert secret not in str(audit)


@pytest.mark.asyncio
async def test_workflow_rejects_cycles(client):
    response = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Cyclic invalid workflow",
            "steps": [
                {"id": "a", "type": "delay", "depends_on": ["b"]},
                {"id": "b", "type": "delay", "depends_on": ["a"]},
            ],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_production_rejects_mock_model(client):
    from app.services.model_gateway import ModelGateway

    gateway = ModelGateway(Settings(environment="production", api_key="configured"))
    with pytest.raises(Exception) as error:
        await gateway.complete(
            messages=[{"role": "user", "content": "test"}],
            task_type="test",
            actor_id="security-test",
            requested_provider="mock",
        )
    assert getattr(error.value, "status_code", None) == 503


@pytest.mark.asyncio
async def test_memory_lifecycle_and_source_backed_retrieval(client):
    created = await client.post(
        "/api/v1/memory",
        json={
            "scope": "project",
            "content": "Verified rollback strategy",
            "metadata": {"project": "alpha"},
        },
    )
    assert created.status_code == 201
    entries = (await client.get("/api/v1/memory", params={"scope": "project"})).json()
    assert any(entry["content"] == "Verified rollback strategy" for entry in entries)
    await client.post(
        "/api/v1/knowledge",
        json={
            "title": "PostgreSQL retrieval note",
            "content": "Hybrid retrieval combines lexical ranking with vector similarity.",
            "source_url": "https://github.com/pgvector/pgvector",
            "verification_status": "verified_official_api",
        },
    )
    results = (
        await client.get("/api/v1/knowledge/search", params={"q": "vector retrieval"})
    ).json()
    assert results["retrieval"] == "lexical_tfidf_v1_not_vector"
    assert results["results"][0]["source_url"] == "https://github.com/pgvector/pgvector"
    deleted = await client.delete(f"/api/v1/memory/{created.json()['id']}")
    assert deleted.status_code == 204
    remaining = (await client.get("/api/v1/memory", params={"scope": "project"})).json()
    assert all(entry["id"] != created.json()["id"] for entry in remaining)


@pytest.mark.asyncio
async def test_openai_compatible_real_http_contract_with_test_transport(client):
    observed = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        assert request.headers["Authorization"] == "Bearer server-test-secret"
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "id": "provider-fixture",
                    "model": "verified-test-model",
                    "choices": [
                        {"message": {"content": "provider-validated"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                },
            )
        return httpx.Response(404)

    gateway = ModelGateway(
        Settings(
            openai_compatible_base_url="https://provider.test/v1",
            openai_compatible_api_key="server-test-secret",
            openai_compatible_model="verified-test-model",
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await gateway.complete(
        messages=[{"role": "user", "content": "contract test"}],
        task_type="test",
        actor_id="provider-test",
        requested_provider="openai-compatible",
    )
    assert result.text == "provider-validated"
    assert result.is_mock is False
    assert result.input_tokens == 4
    assert result.output_tokens == 2
    assert len(observed) == 1
