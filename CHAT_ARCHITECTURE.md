# Chat Architecture

Chat is a dedicated web route and native Android route with persisted conversations/messages.

## Backend

- Create/list/search (title query)/rename/pin/archive/delete conversation APIs.
- Last 30 messages form bounded model context; conversation ownership is checked.
- Non-streaming and SSE message endpoints.
- SSE uses real provider delta events for OpenAI-compatible streaming; deterministic mock chunks remain labeled mock.
- Stop aborts the browser request; received partial text is persisted as `stopped` when possible.
- Markdown export, provider/model/mock state and model usage records.

The web console provides conversation history, new chat, streaming display, stop and export. Android currently uses non-streaming new-conversation chat and labels mock responses.

## Not yet implemented

Markdown rendering/syntax highlighting, attachments/OCR/document understanding, regenerate/retry actions, pinning UI (API exists), archived-chat management UI, project context injection, long-context compaction, native Android streaming and full conversation management. These are not represented as complete in acceptance tests.
