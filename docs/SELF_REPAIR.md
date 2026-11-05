# SELF-REPAIR WORKFLOW

The platform can detect, classify, fix and regress-test its own failures. The workflow is
implemented; the *autonomous trigger* is deliberately conservative.

---

## 1. The loop

```
 execute ─▶ capture ─▶ validate ─▶ detect ─▶ classify ─▶ root-cause
    ▲                                                          │
    │                                                          ▼
  accept / rollback ◀── compare ◀── regression ◀── fix ◀─── proposal
```

| Stage | Implementation |
|---|---|
| **execute** | any tool call, agent run, workflow step or build job |
| **capture** | the result, the error code, the parameters and the correlation ID are recorded (`tool_executions`, `agent_runs`, `build_jobs`) |
| **validate** | the result is checked against the tool's output schema, the agent's quality criteria or the build's exit code |
| **detect** | a mismatch between expected and actual is raised as a *defect* |
| **classify** | the defect is classified: `upstream`, `timeout`, `policy`, `schema`, `resource`, `internal` |
| **root-cause** | the captured evidence (error class, message, policy decision, retry counters) is assembled into a cause record |
| **fix** | a candidate fix is produced and recorded with its diff/proposal |
| **regression** | the fix is re-run against the captured case and the surrounding suite |
| **compare** | before/after metrics are compared (success rate, latency, error class) |
| **accept / rollback** | the fix is accepted only if the comparison improves and nothing else regressed |

---

## 2. Safety rails

Changes that touch the **database schema**, **security configuration** or a
**production deployment** require:

1. a **backup** taken before the change (schema dump / config snapshot / release snapshot);
2. an **explicit approval** — the platform refuses to apply the change unilaterally;
3. a **rollback plan** recorded with the change;
4. a **regression report** after the change.

Irreversible tool actions carry `requires_approval` in the tool contract and are refused
without an approval flag (`APPROVAL_REQUIRED`).

---

## 3. What is automated today

| Capability | State |
|---|---|
| Defect capture and classification | **implemented** (error codes are structured per tool contract) |
| Root-cause evidence assembly | **implemented** (audit + execution records) |
| Before/after comparison | **implemented** for tool execution and agent runs (`tool_executions` history) |
| Regression re-run | **implemented** via the verification suites (`smoke_test.py`, `run_acceptance.py`) |
| Automatic patch generation and application | **not implemented** — the platform proposes, a human applies |
| Automatic rollback of a database migration | **not implemented** — backups are a documented procedure, not an automated job |

The refusal to auto-apply fixes is a design decision, not a missing feature: a system that
rewrites its own security or schema configuration without a human in the loop is exactly
the failure mode the brief asked to avoid.
