# MEMORY & RAG

Two subsystems that together give TITAN durable, attributable knowledge.

---

## 1. Memory — eight typed scopes

`conversation`, `user`, `project`, `agent`, `skill`, `research`, `execution`, `recovery`
(`services/memory.py::MEMORY_SCOPES`).

An unknown scope is a **400**, not a 500 — the route validates before writing.

| Operation | Behaviour |
|---|---|
| write | validates the scope, applies the dedup policy, sets importance/confidence/source, optionally sets a TTL |
| dedup | the same content written to the same `scope` + `scope_key` + `kind` becomes a **new version of one row**, not a second copy |
| versioning | `version` is incremented on every dedup hit; `updated` bumps it as well |
| expiration | `ttl_days` sets `expires_at`; expired rows are filtered out of every read |
| deletion | soft delete (`deleted_at`), so the history stays auditable |
| listing | filtered by `scope`, `scope_key` and tenant; ordered by importance then recency |

Verified by AT-20 (all eight scopes persist and list) and AT-21 (a duplicate write yields
version 2 on the same row — exactly one live row carries the content).

---

## 2. RAG — hybrid retrieval with attribution

`services/rag.py`.

```
ingest
  → cleaning (whitespace normalisation, boilerplate strip)
  → chunking (900 chars, 120-char overlap)
  → embedding (deterministic local 384-d encoder, L2-normalised)
  → two indexes: BM25 (lexical) + NumPy cosine (dense)
  → hybrid query: BM25 top-k  ⋈  dense top-k
  → reciprocal-rank fusion (RRF)
  → rerank by fused score × verification weight
  → context assembly
  → answer + source attribution on every chunk
```

### Why a deterministic local embedder

The host cannot reach an embedding API (no provider key) and refuses to fabricate vectors.
The local encoder is a hashed bag-of-tokens projection with L2 normalisation: it is
deterministic, offline, dependency-free and produces genuinely useful lexical-semantic
overlap for retrieval. Replacing it with a real embedding model is a one-function change
(`services/rag.py::embed`) and the schema already stores the vectors.

### Attribution

Every chunk returned by `GET /knowledge/search` carries its source document id, title and
URL. AT-17 asserts that **no** chunk is returned without attribution.

### Source of truth for the corpus

`knowledge_documents` + `embeddings` are populated by
`POST /research/documents/{id}/ingest`, so material collected by the research engine
becomes retrievable knowledge in one step (AT-16 → AT-17).

---

## 3. Relation to the four learning levels

| Level | Substrate |
|---|---|
| knowledge acquisition | `research_documents` + `knowledge_documents` + `embeddings` |
| experience learning | `agent_runs`, `tool_executions`, `audit_logs` |
| skill acquisition | `skills` + `skill_versions` |
| real model training | **not implemented** — `GET /models/training` reports `NOT_RUN` |

Writing a memory entry is **not** model training, and the platform never claims otherwise.
