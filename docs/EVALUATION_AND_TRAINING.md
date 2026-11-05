# MODEL EVALUATION & TRAINING CENTER

---

## 1. Evaluation — implemented and real

`POST /models/evaluations` runs a benchmark and stores the measured result.

* Cases are `{id?, prompt, expected?, criteria?}`.
* Criteria types: `contains`, `not_empty`, `min_length`, `json` (with required keys).
* Each case is sent to the gateway; the reply is scored against the criteria.
* The run records: overall score, mean latency, cost, sample count, `provider_mode` and
  the per-case detail (score, latency, output preview, error).

Verification: AT-33 runs four cases and reports `score=0.5 cases=4 provider_mode=mock` —
the score is a genuine measurement of the mock provider's output, not a hard-coded number.

Because no provider credential exists here, the benchmark scores the mock provider. The
`provider_mode` field makes that explicit in the record and in the API response.

---

## 2. Dataset preparation — implemented and real

`POST /models/training/datasets` performs the steps that do not require a training
runtime:

* record cleaning (empty/blank records dropped),
* deduplication (identical records collapsed),
* quality filtering (minimum length, required fields),
* a stored dataset row with its record count and quality notes.

This is real work with a real artifact in `training_datasets`.

---

## 3. Training — NOT IMPLEMENTED, and reported as such

`GET /models/training`:

```json
{"level": "Level 3 — skills acquired",
 "training_runtime_available": false, "detected_runtime": null,
 "datasets": [...], "jobs": [],
 "status": "NOT_RUN",
 "reason": "No training runtime (torch/transformers/peft) is installed in this deployment,
            so no fine-tuning job can be executed. Dataset preparation, cleaning,
            deduplication and quality filtering ARE implemented and were run on the
            datasets listed above.",
 "policy": "This service never reports a trained model without a real training artifact
            and an evaluation report."}
```

The host's TLS allowlist excludes PyPI-hosted deep-learning wheels that would fit the
platform, and no GPU is present, so no fine-tune is executed.

**The four learning levels are kept distinct.** Writing memories, running agents and
acquiring skills are implemented. Actually fine-tuning model weights is **not** — and the
platform says so in the API, in the UI and in this document. Memory is not training.

---

## 4. What enabling real training would require

1. a reachable training runtime (PyTorch + `transformers` + `peft`, or `llama.cpp` +
   `unsloth`), which the current egress allowlist blocks;
2. a GPU or an acceptably slow CPU path;
3. a dataset with a documented licence and consent basis;
4. an evaluation report produced by the same evaluator used above, so the fine-tuned
   model can be compared with its base model before promotion.
