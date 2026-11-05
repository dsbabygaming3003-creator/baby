# Model Evaluation

## Observed metrics

`model_calls` records actor, provider, model, task type, success/mock, input/output tokens, latency, optional cost, error and timestamp. `GET /api/v1/models/evaluations` returns observed calls and explicitly states that usage is not a quality benchmark.

The OpenAI-compatible contract test uses an HTTP test transport to validate response text, model, token usage and non-mock labeling. This does not test a real provider account. Mock calls validate orchestration/streaming mechanics only.

## Required live benchmark before model selection

- Bengali conversation and Bengali↔English translation adequacy.
- JSON/schema validity and tool-call correctness.
- Coding patch tests and regression rate.
- Research citation faithfulness and unsupported-claim rate.
- Voice/vision capability probes where applicable.
- Latency percentiles, token usage, cost, retry/fallback behavior and reliability.

Each result must identify exact provider/model/version, date, dataset hash and configuration. No model equivalence, superiority, Bengali quality or production availability is currently claimed. Fine-tuning evaluation is blocked with training infrastructure.
