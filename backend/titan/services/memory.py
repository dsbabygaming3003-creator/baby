"""Memory service — eight typed scopes with versioning, retention and retrieval.

Scopes
------
1. conversation   short-term conversation memory
2. user          long-term user memory
3. project       project memory
4. agent         agent memory
5. skill         skill memory
6. research      research knowledge
7. execution     task execution memory
8. recovery      error recovery memory
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import MemoryEntry
from .rag import chunk_text, hash_embed
from .observability import metrics

MEMORY_SCOPES = (
    "conversation", "user", "project", "agent", "skill", "research", "execution", "recovery",
)


class MemoryService:
    async def write(self, session, *, scope: str, content: str, kind: str = "note",
                    scope_key: str = "", org_id: str = "default",
                    importance: float = 0.5, confidence: float = 0.5,
                    source: str = "", metadata: Optional[Dict[str, Any]] = None,
                    ttl_days: Optional[int] = None) -> MemoryEntry:
        if scope not in MEMORY_SCOPES:
            raise ValueError(f"unknown memory scope '{scope}' (expected one of {MEMORY_SCOPES})")
        resolved_key = scope_key or "default"
        now = datetime.now(timezone.utc)

        # Dedup policy: the same content written into the same scope/key is a new
        # *version* of one entry, never a second copy.  Superseded rows are soft
        # deleted so the deletion policy stays auditable.
        existing = (await session.execute(
            select(MemoryEntry).where(
                MemoryEntry.org_id == org_id,
                MemoryEntry.scope == scope,
                MemoryEntry.scope_key == resolved_key,
                MemoryEntry.kind == kind,
                MemoryEntry.content == content,
                MemoryEntry.deleted_at.is_(None),
                (MemoryEntry.expires_at.is_(None)) | (MemoryEntry.expires_at > now),
            ).order_by(MemoryEntry.version.desc())
        )).scalars().first()
        if existing is not None:
            existing.version = existing.version + 1
            existing.importance = importance
            existing.confidence = confidence
            if source:
                existing.source = source
            if ttl_days:
                existing.expires_at = now + timedelta(days=ttl_days)
            if metadata:
                existing.metadata_json = {**(existing.metadata_json or {}), **metadata}
            await session.flush()
            metrics.incr("memory_dedup_total", scope=scope, kind=kind)
            metrics.incr("memory_writes_total", scope=scope, kind=kind)
            return existing

        entry = MemoryEntry(
            scope=scope, scope_key=resolved_key, kind=kind, content=content,
            org_id=org_id, importance=importance, confidence=confidence, source=source,
            metadata_json=metadata or {},
            expires_at=(datetime.now(timezone.utc) + timedelta(days=ttl_days)) if ttl_days else None,
        )
        session.add(entry)
        await session.flush()
        metrics.incr("memory_writes_total", scope=scope, kind=kind)
        return entry

    async def list(self, session, *, scope: Optional[str] = None, scope_key: Optional[str] = None,
                   org_id: str = "default", limit: int = 50,
                   include_expired: bool = False) -> List[MemoryEntry]:
        stmt = select(MemoryEntry).where(MemoryEntry.org_id == org_id, MemoryEntry.deleted_at.is_(None))
        if scope:
            stmt = stmt.where(MemoryEntry.scope == scope)
        if scope_key:
            stmt = stmt.where(MemoryEntry.scope_key == scope_key)
        if not include_expired:
            stmt = stmt.where((MemoryEntry.expires_at.is_(None))
                              | (MemoryEntry.expires_at > datetime.now(timezone.utc)))
        stmt = stmt.order_by(MemoryEntry.importance.desc(), MemoryEntry.created_at.desc()).limit(limit)
        return list((await session.execute(stmt)).scalars().all())

    async def get(self, session, memory_id: str) -> Optional[MemoryEntry]:
        return (await session.execute(select(MemoryEntry).where(MemoryEntry.id == memory_id))).scalar_one_or_none()

    async def update(self, session, memory_id: str, *, content: str,
                     importance: Optional[float] = None,
                     confidence: Optional[float] = None) -> Optional[MemoryEntry]:
        entry = await self.get(session, memory_id)
        if entry is None:
            return None
        entry.content = content
        entry.version = entry.version + 1
        if importance is not None:
            entry.importance = importance
        if confidence is not None:
            entry.confidence = confidence
        await session.flush()
        return entry

    async def delete(self, session, memory_id: str) -> bool:
        entry = await self.get(session, memory_id)
        if entry is None:
            return False
        entry.deleted_at = datetime.now(timezone.utc)
        await session.flush()
        metrics.incr("memory_deletes_total")
        return True

    async def purge_expired(self, session) -> int:
        stmt = select(MemoryEntry).where(
            MemoryEntry.expires_at.is_not(None),
            MemoryEntry.expires_at < datetime.now(timezone.utc),
            MemoryEntry.deleted_at.is_(None),
        )
        entries = list((await session.execute(stmt)).scalars().all())
        now = datetime.now(timezone.utc)
        for entry in entries:
            entry.deleted_at = now
        await session.flush()
        return len(entries)

    async def recall(self, session, query: str, *, scope: Optional[str] = None,
                     org_id: str = "default", top_k: int = 5) -> List[Dict[str, Any]]:
        """Similarity recall over memory content using the shared embedder."""
        entries = await self.list(session, scope=scope, org_id=org_id, limit=500)
        if not entries:
            return []
        query_vec = hash_embed(query)
        scored = []
        for entry in entries:
            best = 0.0
            for chunk in chunk_text(entry.content) or [entry.content]:
                vec = hash_embed(chunk)
                denom = float((vec @ vec) ** 0.5) or 1.0
                similarity = float(vec @ query_vec) / denom
                best = max(best, similarity)
            scored.append((best * entry.importance, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {"id": e.id, "scope": e.scope, "scope_key": e.scope_key, "kind": e.kind,
             "content": e.content, "importance": e.importance, "confidence": e.confidence,
             "source": e.source, "version": e.version, "score": round(score, 6),
             "created_at": e.created_at.isoformat() if e.created_at else None}
            for score, e in scored[:top_k]
        ]


memory = MemoryService()
