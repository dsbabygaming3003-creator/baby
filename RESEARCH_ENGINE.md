# Runtime Research Engine

This is **System B**, a permanent product subsystem independent from the Builder AI reports.

## Persistence

`research_tasks` owns query/status/connectors/report; `research_sources` records each connector attempt/version/endpoint/error; `research_documents` stores normalized content/hash/URL/retrieval/verification; `research_findings` links factual claims to evidence; `knowledge_documents` receives owner-scoped source-attributed content.

## Workflow

1. Validate query, connectors and result limit.
2. Persist queued/running task.
3. Invoke each registered connector independently.
4. Preserve `unsupported` or `failed` source outcomes and partial successes.
5. Normalize official repository records, deduplicate by URL/content SHA-256 and label external text untrusted.
6. Generate conservative factual findings—no unsupported capability conclusions.
7. Ingest knowledge, persist task history and write a Markdown report.
8. Optionally convert the verified artifact into a project, tested draft skill or tested draft agent.

## Research Center

The console provides global query, connector selection/result limits, task history, live derived status, source coverage, document verification, source links and report export. Conversion buttons call real endpoints.

## Verification

Unit fixtures test partial failures, knowledge/report/conversions without presenting fixtures as live research. A separate live smoke called GitHub's API and retrieved `langchain-ai/langgraph` and `google-gemini/gemini-fullstack-langgraph-quickstart` with `verified_official_api`; see `docs/evidence/live_smoke.json`. The earlier TLS failure is retained in evidence and was fixed using the OS trust store.

## Open scope

Only GitHub repository search is currently live. Social/video/paper/documentation/browser connectors, scheduling, repository deep inspection, model explorer, semantic comparison and LLM synthesis are not implemented. Reports are factual normalized records, not claimed global expert analysis.
