# DURABLE WORKFLOW ENGINE

Server-side, resumable, DAG-based execution (`services/workflow.py`).

---

## 1. Graph model

```json
{"steps": [
  {"id": "a", "action": {"type": "tool", "tool": "terminal.exec",
                         "params": {"command": "echo step-a"}}},
  {"id": "b", "action": {"type": "tool", "tool": "terminal.exec",
                         "params": {"command": "echo step-b"}},
   "depends_on": ["a"]}
]}
```

Step actions: `tool` (call a registered tool), `agent` (run an agent), `approval`
(a human gate) and `noop`.

---

## 2. Validation

`workflow_engine.validate(graph)` rejects:

* a step with an unknown dependency,
* a **cycle** — a cyclic graph returns HTTP 400 (AT-24),
* a duplicate step id,
* a step with no action.

---

## 3. Execution

| Feature | Behaviour |
|---|---|
| parallelism | steps with no unmet dependency run concurrently, up to `workflow_max_parallel` (4) |
| ordering | dependencies are respected; the completion order is recorded |
| retry | per-step retry policy, with backoff |
| timeout | per-step wall-clock budget (`workflow_step_timeout_seconds`, 300 s) |
| checkpoint | the run state (including completed steps and their outputs) is written to `workflow_runs.checkpoint` after every step |
| resume | `POST /workflows/runs/{id}/resume` continues from the checkpoint; already-completed steps are not re-executed |
| cancel | `POST /workflows/runs/{id}/cancel` stops the run and marks it cancelled |
| approval | `POST /workflows/runs/{id}/approve` releases a step that waits for a human |
| survival | runs live in the backend process and their state is in the database, so a restart can resume a run from its checkpoint |

Verified: AT-24 (cycle → 400, valid DAG → 201), AT-25 (run completes, dependency order
respected), AT-26 (resume → `completed`).

---

## 4. Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/workflows` | list / create |
| POST | `/workflows/{id}/runs` | start a run |
| GET | `/workflows/runs` | run history |
| POST | `/workflows/runs/{id}/resume` | resume from the checkpoint |
| POST | `/workflows/runs/{id}/approve` | release an approval gate |
| POST | `/workflows/runs/{id}/cancel` | cancel |

---

## 5. Schedules

`workflows.schedule` accepts a cron-like expression; the field is stored and exposed, but
the scheduler that would fire it is **not implemented in this build** — see
`docs/KNOWN_LIMITATIONS.md`.
