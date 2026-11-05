# THE GLOBAL RESEARCH ENGINE (System B)

TITAN's **own** research subsystem. It is a permanent product feature of the platform —
completely independent of the pre-build research that was performed *for* the project
(deliverable A, `docs/GLOBAL_PREBUILD_RESEARCH.md`).

---

## 1. Pipeline

Each stage is a separate, versioned module. A failure in any stage is contained: the
stage reports it and the task continues with partial results.

```
 query
  │
  ▼
[1] Auth / Policy ............ per-connector credentials + egress policy
  ▼
[2] Query Adapter ............ platform-specific query syntax + pagination
  ▼
[3] Retrieval ................ fetch + status + count + latency per source
  ▼
[4] Normalization ............ unified document shape (title, url, summary, metadata)
  ▼
[5] Dedup .................... content hash + URL normalisation
  ▼
[6] Extraction ............... findings (statement + evidence_url + confidence)
  ▼
[7] Verification ............ verification_status + confidence + injection_risk
  ▼
[8] Ranking ................. relevance × source weight × verification
  ▼
[9] Analysis ................ findings grouped by theme
  ▼
[10] Knowledge .............. chunk → embed → index for hybrid retrieval
  ▼
[11] Report .................. Markdown report on disk + in the task record
```

Implementation: `services/research.py` (engine), `services/research_connectors.py`
(per-source adapters), `services/rag.py` (knowledge stage).

---

## 2. Connector registry

12 connectors. Status is reported live by `GET /research/connectors/probe`.

| Connector | Platform | State on this host | Reason |
|---|---|---|---|
| `github.v1` | GitHub | **ok** | `api.github.com` is reachable |
| `npm.v1` | npm | **ok** | `registry.npmjs.org` is reachable |
| `pypi.v1` | PyPI | **ok / empty** | reachable; empty results are a real result, not a failure |
| `arxiv.v1` | arXiv | inaccessible | host not on the TLS allowlist |
| `huggingface.v1` | Hugging Face | inaccessible | idem |
| `stackexchange.v1` | Stack Exchange | inaccessible | idem |
| `reddit.v1` | Reddit | inaccessible | idem |
| `openalex.v1` | OpenAlex | inaccessible | idem |
| `crossref.v1` | Crossref | inaccessible | idem |
| `wikipedia.v1` | Wikipedia | inaccessible | idem |
| `hn.v1` | Hacker News | inaccessible | idem |
| `devto.v1` | DEV.to | inaccessible | idem |

**Inaccessible is not empty and not failed** — it is a distinct, honest status. A task run
that reaches three live connectors returns documents from them and reports the other nine
as `inaccessible` (AT-13).

---

## 3. Partial-failure tolerance

Every connector call returns a status record:

```json
{"connector_id": "github.v1", "platform": "github", "status": "ok",
 "count": 15, "detail": "…", "http_status": 200, "duration_ms": 812.4}
```

The task never fails because one source failed. A run summary looks like:

```json
{"task_id": "…", "status": "completed",
 "documents": 30, "findings": 12, "verified_documents": 15,
 "connectors": [{"connector_id": "github.v1", "status": "ok", "count": 15}, …],
 "report_path": "data/reports/research-<id>.md"}
```

---

## 4. Verification and trust

Every document carries:

| Field | Meaning |
|---|---|
| `verification_status` | `verified` / `unverified` / `failed` / `partial` |
| `confidence` | 0…1 |
| `injection_risk` | heuristic score for prompt-injection patterns in the fetched text |
| `trust` | always `untrusted` for external content |
| `content_hash` | SHA-256 of the normalised body — the dedup key |

Findings carry a `statement`, an `evidence_url` and their own `verification_status`.

---

## 5. Knowledge stage

`POST /research/documents/{id}/ingest` stores a document in `knowledge_documents`, chunks it
(900 characters, 120 overlap), embeds each chunk with the deterministic local embedder and
writes the vectors to `embeddings`. From that point the material is retrievable through
`GET /knowledge/search`, which fuses BM25 and dense retrieval with reciprocal-rank fusion
and always attaches the source to every chunk (AT-17).

---

## 6. Knowledge base features

| Feature | Where |
|---|---|
| Library of ingested documents | `knowledge_documents` |
| History of research runs | `research_tasks` + `research_sources` |
| Saved findings | `research_findings` (per task) |
| Comparison workspace | findings carry a comparable normalised shape; the agent layer groups them by theme |
| Report export | Markdown report written to `data/reports/` and referenced by the task |
| Research → skill / agent / project | `skills` and `agents` tables accept `research` scope and can be created from findings through the factory |

---

## 7. Research Center UI (Android)

`android/.../screens/OtherScreens.kt` → `ResearchScreen`:

* platform chips with live per-connector status,
* task creation (query + platforms),
* run button with live result counts (documents / findings / verified),
* connector probe,
* task history.

Every value on the screen comes from the backend; there is no static mock data.
