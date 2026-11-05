# Agent Architecture

## Contracts

Each agent stores ID/slug, name, description, role, semantic version, instructions, model route, tool permissions, memory scope, input/output object schemas, timeout, retry policy, lifecycle status, tests and quality metrics. Core agents are seeded idempotently.

Task records include batch ID, owner ID, agent ID, objective, dependencies, status, result, evidence, attempts, timestamps, duration and error. Owner scope is enforced on task history and batch retrieval.

## Supreme Boss execution

1. Resolve requested registered agents; reject missing or non-active agents.
2. Persist a batch and one task per agent.
3. Execute independent tasks concurrently with `asyncio.gather` and a separate `AsyncSession` per worker.
4. Enforce per-agent timeout and bounded retry policy.
5. Invoke only the selected model route in this increment; specialist tool invocation is not automatically inferred from untrusted text.
6. Validate non-empty provider output, persist provider/model/mock/token evidence and aggregate all states.
7. An exception in one task does not erase sibling results.

This verifies orchestration mechanics. With the default mock, it does not prove specialist intellectual competence.

## Dynamic Agent Factory

`draft → contract sandbox test → tested → explicit approval → active`.

Contract tests verify instructions, object schemas, bounded timeout and an allowlisted permission set. They do not execute arbitrary agent code. Research-to-agent creates a tested draft, never an automatically active production agent.

## Current limitations

- Core role instructions and permissions are real registry data, but autonomous coding/browser/database tools are not all implemented.
- Dependencies exist in the task schema; general cross-agent dependency scheduling is not yet exposed by the orchestration request. Current batches are parallel independent tasks.
- No quality benchmark establishes any agent as superior to another system.
- Distributed locks, exactly-once side effects and Temporal-backed resume require production workers.
