# System Architecture

## Current deployable shape

TITAN is a modular monolith with independent service boundaries, not a claimed distributed production platform.

```text
Kotlin/Compose client       Responsive web console
          \                     /
           ---- HTTPS / JSON / SSE ----
                       |
                FastAPI control plane
     +----------------+------------------+
     | Identity/correlation/audit         |
     | Supreme Boss agent orchestration   |
     | Research tasks + connector registry|
     | Model gateway + usage records      |
     | Chat / Skills / Memory / Workflows |
     | Projects / Terminal / Build jobs   |
     +----------------+------------------+
                       |
               SQLAlchemy async persistence
             SQLite dev / PostgreSQL target
                       |
      Workspace files + Markdown research reports

External trust boundary: official GitHub API or configured model provider.
External text is always untrusted data, never privileged instructions.
```

## Module ownership

- `api.py`: typed HTTP contracts, ownership checks and audit entry points.
- `models.py`: persisted registry, task, source, knowledge, chat, workflow, build and audit records.
- `services/agents.py`: registry seeding, factory gates and parallel execution.
- `services/research.py`: versioned connectors, normalization, dedupe, provenance, findings, reports and conversion inputs.
- `services/model_gateway.py`: explicit mock and OpenAI-compatible calls/streaming with metrics.
- `services/memory.py`: scoped memory and explainable lexical source retrieval.
- `services/skills.py`: allowlisted deterministic handlers and publication gates; arbitrary skill code is not accepted.
- `services/workflows.py`: DAG verification, parallel levels and checkpoint/resume.
- `services/projects.py`: canonical file operations, exact command approval and build detection.

## Intelligence flow

User objective → validated request → principal/tenant → Supreme Boss task batch → independent agent tasks → model/tool policy → persisted result/evidence → fan-in. Agents expose concise outputs and evidence, never private chain-of-thought. Mock success means the execution pipeline succeeded, not that live intelligence completed the objective.

## Research flow

`SourceConnector → access policy → official query → normalization → SHA-256 dedupe → source verification label → factual findings → owner-scoped knowledge → persisted report`.

Each connector has an independent source row. `succeeded`, `partial` and `failed` are derived from actual connector outcomes. Runtime state never depends on Builder AI reports or browser history.

## Production evolution

1. Run PostgreSQL migrations after backup/approval; add pgvector retrieval as a separately evaluated implementation.
2. Put web/API behind TLS, managed secrets, SSO/RBAC and tenant-aware authorization.
3. Extract background workers to Temporal or an equivalent durable service for distributed recovery/idempotency.
4. Execute terminal/build work in disposable non-root containers/VMs with resource quotas and egress denial.
5. Add official authorized social/paper/browser connectors independently; failure must remain isolated.
6. Add native Android feature modules and device tests before release.

Cloudflare D1 and PostgreSQL are not treated as equivalent. No Cloudflare deployment is claimed.
