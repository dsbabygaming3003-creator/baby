# Architecture Decision Record — ADR-001

**Title:** First implementable TITAN intelligence core and trust boundaries
**Date:** 2026-11-04
**Status:** ACCEPTED for the first increment; later ADRs may supersede production deployment choices.

## Context

The initial repository contains no TITAN implementation. Research shows mature individual projects for agents, retrieval, gateways and workflows, but none alone satisfies the mobile-first, multi-tenant, research/execution and verifiable-delivery requirements. The sandbox can run Python but lacks production services, provider credentials and Android tooling.

## Decisions

### 1. Modular monolith first, explicit service boundaries

Build a FastAPI control plane with separate modules for identity, agents, models, research, skills, memory, projects, tools and workflows. Keep contracts independent so workers/services can be extracted. Do not claim a distributed system while running one process.

### 2. Persistent local development profile

Use SQLAlchemy with SQLite for executable local persistence and tests. Define PostgreSQL-compatible IDs/timestamps/JSON boundaries and migrations. Redis/Temporal/pgvector are production targets, not fake local substitutes. SQLite lexical retrieval is explicitly non-vector.

### 3. Two research systems remain separate

Builder evidence lives in root reports and `docs/research/evidence/`. Product research uses runtime APIs, connector registry, persisted tasks/documents/findings/source status/history and reports. Neither substitutes for the other.

### 4. Agent control plane

Twenty versioned specialist definitions are seeded from data. Supreme Boss creates typed tasks, resolves dependencies, executes independent tasks concurrently and stores results/errors/evidence. Agents cannot self-declare success without output/evidence validation. Dynamic agents require schema validation, sandbox tests and approval before activation.

### 5. Honest model gateway

A common async provider contract supports an explicitly labeled deterministic mock and real server-side OpenAI-compatible calls. Provider health/configuration determines availability. No provider secret enters client code. No training claim is derived from memory or prompt use.

### 6. Research connector pipeline

`SourceConnector → access policy → query → retrieval → normalization → dedupe → verification → ranking → findings/knowledge → report`. Each connector returns structured source outcomes. One failure produces partial status rather than deleting successful results. External text is untrusted data.

### 7. Real but bounded execution

Project/file APIs canonicalize paths inside per-project workspaces. Terminal uses argument vectors, an executable allowlist, timeouts and output limits. Local execution is labeled development-only and is not represented as hardened multi-tenant sandboxing. Production builds require isolated workers.

### 8. Native Android plus operations web console

Native Kotlin/Compose source implements the mobile client contracts. A responsive web console exercises real APIs in the available preview environment. It is an additional client, not an APK substitute.

### 9. Verification and delivery

Automated tests exercise persistence, parallel orchestration, connector failure/partial results, source-backed retrieval, model routing, project path defenses, tool permissions and workflow resume. Android compilation/install/launch and hosted model/voice/training tests remain blocked until their actual dependencies exist.

## Consequences

- A useful, testable vertical slice can be delivered without pretending all V18 phases are complete.
- Local persistence/workers require later production hardening and deployment migration.
- Native provider/orchestration code must remain small to avoid recreating mature frameworks poorly.
- Every UI status must come from persisted/runtime truth.

## Alternatives rejected

- Vendoring Hermes/OpenHands wholesale: excessive first-increment surface and unresolved compatibility/tenant controls.
- Making LiteLLM/Temporal/PostgreSQL mandatory now: unavailable infrastructure would prevent executable verification.
- Android-only UI with a mock backend: violates real data-flow requirements and cannot be previewed/tested here.
- Claiming a web app is an APK or mock output is live AI: explicitly prohibited.
