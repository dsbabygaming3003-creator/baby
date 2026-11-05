# Observability

Every response carries `X-Correlation-ID`; audit records join actor/action/resource/status/details/time. Agent tasks retain attempts/duration/evidence/errors; model calls retain provider/model/task/success/mock/tokens/latency/cost/error; tool executions retain approval/status/output/error/duration; workflows retain step logs/checkpoints.

`/api/v1/system` exposes actual database counts and environment boundaries. `/models/evaluations` returns observed usage, explicitly not quality scores. `/audit` returns actor-scoped administrative activity. Terminal/audit records redact common secrets and sensitive arguments.

## Missing production telemetry

No Prometheus/OpenTelemetry exporter, metrics aggregation, traces, alerts, queue depth, host CPU/memory dashboards or external log retention is configured. Uvicorn logs are process logs, not a complete observability platform. Production needs RED metrics, worker/connector health, DB/queue telemetry, PII-safe structured logging and alert/runbook tests.
