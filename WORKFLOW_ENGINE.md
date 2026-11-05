# Workflow Engine

Workflows contain 1–50 typed steps with unique IDs and dependency lists. Creation rejects unknown dependencies, self-dependencies and cycles.

Execution performs topological levels: independent ready steps run concurrently, outputs/errors are collected, successful outputs and logs are committed as checkpoints after each level. Failure preserves prior checkpoints. Resume skips completed step IDs; cancellation is checked between levels. Supported steps: deterministic text statistics, bounded delay (0–2 s) and model call.

`workflow_runs` persists status, checkpoints, current step, logs, error and cancellation flag. Owner is checked through the parent workflow.

## Durability limits

Local checkpoints support failure/resume tests but are not distributed Durable Execution. A process crash during side effects needs idempotency/reconciliation; current steps have limited side effects. There is no multi-worker lock, schedule, durable timer, human-approval step or exactly-once external action. Temporal is the researched production candidate for those requirements.
