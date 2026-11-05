# Skill Architecture

## Artifact and lifecycle

Skills are owner-scoped and versioned with name/slug, description, handler, input/output object schemas, tools, permissions, dependencies, test results, security review, status and execution count.

Lifecycle: `draft → tested → active → disabled`; failed tests produce `test_failed`. Execution before explicit approval returns HTTP 409.

## Sandbox model

Current handlers (`text_stats`, `source_summary`, `json_keys`) are deterministic pure-Python functions with no file, network, subprocess, dynamic import or arbitrary-code capability. Sandbox tests supply known inputs, execute the handler, validate schemas and JSON serialization, and persist evidence. This is an actual constrained execution environment, but not a general-purpose container sandbox.

## Research conversion

Research-to-skill creates a source-summary draft referencing the task's discovery context and runs its sandbox test. Publication still requires approval. Research text never becomes executable code or system authority.

## Marketplace/laboratory boundary

The web console supports discover/list, create, test, approve/publish, execute and disable. Remote marketplace download, update channels, arbitrary third-party manifests, dependency installation and signed packages are not implemented. Performance metrics currently contain execution counts, not benchmark quality scores.
