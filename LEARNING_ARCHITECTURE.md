# Learning Architecture

TITAN separates four concepts:

1. **Knowledge acquisition:** research documents/findings with source, retrieval time, hash and verification state.
2. **Experience records:** successful/failed agent tasks, model calls, tool executions and workflow logs. These can inform later analysis but are not automatic weight updates.
3. **Skill acquisition:** versioned handler/schema artifact, sandbox tests, approval and execution counts.
4. **Model improvement:** requires an actual dataset job, training worker, model artifact and held-out evaluation.

## Current status

Levels 1–3 have constrained development implementations. Level 4 is **BLOCKED**: no GPU/training worker, dataset pipeline, LoRA/QLoRA job or model artifact exists. No continuous background autonomous learning daemon is claimed.

## Safe evolution

Only reviewed, licensed and tenant-authorized examples may enter datasets. Deduplication, poisoning review, train/test leakage checks and privacy redaction precede training. Evaluation compares exact model versions on frozen datasets; rollback requires retained prior artifacts. Memory writes, prompt changes and skill publication must never be reported as fine-tuning.
