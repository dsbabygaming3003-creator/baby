# Technology Comparison

**Date:** 2026-11-04. Versions and metadata are point-in-time observations in the evidence snapshot.

## Agent/orchestration frameworks

| Candidate | Strength | Constraint / risk | Decision |
|---|---|---|---|
| Hermes Agent | Persistent state, skills, provider/tool/gateway breadth | Broad privileged surface; current runtime/dependency target differs; not multi-tenant Android backend | Reference only |
| LangGraph | Graph/state-oriented agent control | Additional abstraction and version compatibility; not a complete durable service by itself | Candidate for later complex graphs |
| AutoGen | Multi-agent research ecosystem | GitHub repository license metadata is CC-BY-4.0, requiring per-path code license review | Not first dependency |
| CrewAI | Role/crew abstraction | Does not supply TITAN's full persistence/security/mobile boundaries | Reference |
| OpenAI Agents Python | Typed tools/handoffs and provider ecosystem | Provider-centered conventions still require policy and durable infrastructure | Optional adapter later |
| Native typed orchestrator | Small auditable contracts, parallel DAG and persistent runs | Local engine is not a distributed durable platform | Selected first increment |
| Temporal | Battle-tested durable execution, retries, signals and approvals | Requires Temporal service/workers and operational deployment | Production migration candidate |

## Coding agents

| Candidate | License observed | Fit / limitation |
|---|---|---|
| Aider | Apache-2.0 | Git-oriented coding workflows; not embedded without compatibility/security review |
| OpenHands | MIT | Broad software-agent platform; substantial execution sandbox requirements |
| Continue | Apache-2.0 | IDE-oriented assistance; not the mobile backend itself |
| Goose | Apache-2.0 | Extensible agent; operational/tool trust boundary remains |
| Claude Code | Proprietary / all rights reserved | Not open source; no code reuse |

No equivalence or benchmark ranking is claimed.

## Research, memory and retrieval

| Candidate | Best use | Decision |
|---|---|---|
| GitHub official REST API | Verifiable repository discovery/inspection | First real versioned connector |
| Playwright | Authorized dynamic public web retrieval | Optional later connector with egress/injection controls |
| LlamaIndex / Haystack | Rich ingestion/RAG pipelines | Later adapters if baseline proves insufficient |
| mem0 | Agent memory abstraction | Reference; tenant/deletion model needs review |
| SQLite lexical index | Small local, explainable source-backed retrieval | Selected development baseline; not called vector RAG |
| PostgreSQL + pgvector | Unified production relational/vector storage and hybrid retrieval | Selected production target |
| Qdrant | Dedicated high-scale vector search | Alternative when scale/operations justify another service |

## Model/runtime

| Candidate | Capability | Decision |
|---|---|---|
| LiteLLM | Unified gateway, virtual keys, budgets, fallback and spend | Future full deployment; native minimal gateway avoids unrun service claims |
| Direct OpenAI-compatible HTTP | Broad compatible-provider/local-runtime coverage with a small surface | Selected first real adapter |
| Ollama / llama.cpp | Local inference | Runtime adapter targets; no local model/hardware verification |
| vLLM | Higher-throughput self-hosting | Production GPU option |
| Gemini 4 Argon | Officially documented reasoning/multimodal model | Candidate after authenticated account/region/network health check |

## Workflow

- **Temporal:** strongest durability target; service required.
- **Prefect:** Python-centric orchestration and operations; another service/model to operate.
- **n8n:** useful visual automation but Sustainable Use License, not treated as unrestricted open source.
- **TITAN local durable store:** selected for an executable baseline with checkpoints/resume; explicitly not distributed exactly-once execution.

## Voice and translation

- **Whisper / faster-whisper:** ASR candidates; Bengali accuracy, latency and model artifacts must be benchmarked.
- **Piper:** TTS candidate but GPL-3.0 and voice/language coverage need separate review.
- **Argos Translate:** MIT local translation candidate; package/model quality and Bengali support require testing.
- **LibreTranslate:** AGPL service option; not silently embedded.
- **Hosted multilingual models:** configurable route, subject to credentials and evaluation.

## Evaluation and training

LM Evaluation Harness and Promptfoo cover different evaluation styles; Opik/Langfuse add observability with their own deployment/licensing boundaries. PEFT and Axolotl are real fine-tuning candidates, but a training center may report jobs complete only with logs, artifacts and held-out evaluation. No GPU/training infrastructure was found, so training is blocked.

## Android

Native Kotlin + Jetpack Compose + ViewModel/StateFlow + Retrofit/OkHttp matches the requested platform and official ecosystem. A responsive web console is useful for development/operations but is not represented as the Android deliverable or a replacement for it.
