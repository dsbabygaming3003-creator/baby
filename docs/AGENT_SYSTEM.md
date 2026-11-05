# AGENT SYSTEM

Three layers: the **Supreme Boss** (orchestration), the **Worker Bossman** (single-agent
execution) and the **Agent Factory** (dynamic agents).

---

## 1. Supreme Boss — central orchestrator

`POST /orchestrate` → `services/agents.py::SupremeBoss.execute`

| Stage | What happens |
|---|---|
| NLU | the objective is parsed into an intent + a topic |
| Decomposition | the objective is split into sub-tasks |
| Planning | a plan is built; each step names its agent, model and tools |
| Selection | agents are chosen by role match; models by the gateway registry |
| Parallel execution | independent steps run concurrently; dependent steps are ordered |
| Validation | each step's output is scored against the agent's quality criteria |
| Conflict resolution | divergent step outputs are flagged with an explicit conflict note |
| Error recovery | a failed step is retried per its retry policy, then reported as failed |
| Assembly | the final summary is assembled from the verified step results |

### What it deliberately does not do

It does **not** publish private chain-of-thought. The response contains a plan, the steps,
the decisions, the tool activity and the evidence — a verifiable execution summary.

```json
{"success": true, "intent": "…", "plan": [...],
 "steps": [{"agent_id": "…", "status": "completed", "summary": "…", "evidence": [...]}],
 "decisions": [{"decision": "…", "rationale": "…"}],
 "conflicts": [], "final_output": "…"}
```

Verification: AT-29 (plan, steps, decisions and an assembled output are all present, and the
payload contains no `chain_of_thought` / `<thinking>` marker).

---

## 2. Worker Bossman — per-agent runner

`services/agents.py::WorkerBossman.run_agent`

1. resolve the agent contract (from `agents/definitions.py`, or the DB for dynamic agents);
2. check that the caller granted each tool the agent wants;
3. run the agent's tools through the central tool engine, honouring timeouts and retries;
4. call the model gateway for the synthesis step (labelled `provider_mode` in the result);
5. score the output against `quality_criteria` → `quality_score`;
6. record tokens in/out, cost, duration and a log entry.

Verification: AT-30 (a completed run with a verifiable summary, token counts and tool
activity).

---

## 3. The 20 specialised agents

Each has an execution contract: id, name, role, version, system instructions, model config,
tool permissions, memory scope, input/output schemas, timeout, retry policy, quality
criteria and quality score.

| # | Agent id | Role | Focus |
|---|---|---|---|
| 1 | `global_research` | research | multi-source research and synthesis |
| 2 | `opensource_discovery` | research | project/repository discovery and licensing |
| 3 | `ai_architecture` | architecture | system and AI architecture design |
| 4 | `senior_coding` | coding | production code authoring |
| 5 | `bug_fixing` | coding | diagnosis and patching |
| 6 | `frontend_development` | coding | UI implementation |
| 7 | `android_development` | coding | Android/Kotlin work |
| 8 | `backend_development` | coding | services, APIs, data access |
| 9 | `api_integration` | coding | third-party API integration |
| 10 | `database_engineering` | data | schema, migrations, indexes |
| 11 | `ai_model_specialist` | model | model selection, prompts, fine-tuning plans |
| 12 | `model_evaluation` | model | benchmarks and quality analysis |
| 13 | `multilingual_translation` | language | translation, localisation, glossary handling |
| 14 | `voice_audio` | audio | STT/TTS pipelines and audio UX |
| 15 | `image_video` | multimodal | image and video understanding workflows |
| 16 | `security_engineering` | security | threat modelling, review, hardening |
| 17 | `quality_assurance` | quality | test strategy and verification |
| 18 | `devops_infrastructure` | devops | CI/CD, deployment, observability |
| 19 | `build_release` | release | build systems, packaging, release engineering |
| 20 | `documentation` | documentation | technical writing and doc generation |

Verification: AT-05 (all 20 present) and AT-06 (every one of them carries a complete
execution contract — no agent has an empty model config, tool grant list, memory scope,
quality score or metrics block).

---

## 4. Parallel execution, locks and aggregation

* Independent plan steps execute concurrently (`asyncio.gather` over the step list).
* Dependent steps respect the plan's ordering.
* Tool permissions act as the lock boundary: two agents cannot write the same resource
  without both holding the `write` scope.
* Aggregation happens at the assembly stage, which also records the **conflict notes** when
  two steps disagree.

---

## 5. Dynamic Agent Factory

`POST /agents/factory` → draft → `POST /agents/factory/{id}/validate` → sandbox test →
only then may the agent be activated.

* A draft is created with a generated id, a role, a model task and a specification.
* Validation scores the draft against the contract and returns `passed` + `score`.
* A dynamic agent appears in `/agents` with `is_dynamic = true` and in
  `/agents/factory/dynamic`.
* **No dynamic agent is active in production without a passing validation.**

Verification: AT-27 (draft created, validation returns a verdict, the agent is registered).

---

## 6. Continuous learning — four distinct levels

| Level | What it is | Current state |
|---|---|---|
| 1. Knowledge acquisition | facts with source, date, confidence and verification status | **implemented** — `research_documents`, `research_findings`, `knowledge_documents` |
| 2. Experience learning | run history distilled into reusable procedures | **implemented** — `agent_runs`, `tool_executions`, `audit_logs` feed the agent factory |
| 3. Skill acquisition | versioned, schema'd, permission-scoped, sandbox-tested skills | **implemented** — `skills` + `skill_versions`, publish gated on a passing test |
| 4. Real model training | fine-tuning a model on a prepared dataset with an evaluation report | **NOT IMPLEMENTED (honest)** — dataset preparation runs for real, but no training runtime is installed, so `GET /models/training` reports `status: NOT_RUN` with the reason. Memory is **not** training. |
