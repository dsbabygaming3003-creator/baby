# Memory Architecture

## Current stores

- Conversation memory: persisted conversations/messages and bounded last-30-message model context.
- Knowledge/research memory: owner-scoped `knowledge_documents` with source URL/type, verification, content hash and metadata.
- Explicit memory: `memory_entries` with owner, scope (`conversation`, `user`, `project`, `agent`, `skill`, `research`, `task`, `error`), metadata, creation and optional expiry.
- Task/error memory: agent task, tool execution, workflow checkpoint/log and model-call records.

Memory creation/list/delete are real APIs. Expired explicit entries are filtered at read time. Research content is tagged untrusted and does not gain instruction authority when remembered.

## Separation from learning/training

Persisting a conversation or research document is memory, not model training. No model weights change. User preferences are not inferred silently in this increment; entries require an explicit API write.

## Production requirements

Add automated retention deletion (not only read filtering), per-scope encryption keys, tenant-aware backup/restore, user export/deletion, memory write review for sensitive data and poisoning/adversarial tests. PostgreSQL production policies must enforce the same owner predicates as SQLite tests.
