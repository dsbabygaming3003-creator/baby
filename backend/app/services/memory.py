import math
import re
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KnowledgeDocument, MemoryEntry
from ..schemas import KnowledgeCreate, MemoryCreate
from ..utils import content_hash

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_knowledge(self, owner_id: str, data: KnowledgeCreate) -> KnowledgeDocument:
        digest = content_hash(data.content)
        existing = await self.db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.owner_id == owner_id, KnowledgeDocument.content_hash == digest
            )
        )
        if existing:
            return existing
        document = KnowledgeDocument(
            owner_id=owner_id,
            title=data.title,
            content=data.content,
            source_url=data.source_url,
            source_type=data.source_type,
            verification_status=data.verification_status,
            metadata_json=data.metadata,
            content_hash=digest,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def search(self, owner_id: str, query: str, limit: int = 5) -> dict:
        documents = list(
            (
                await self.db.scalars(
                    select(KnowledgeDocument).where(KnowledgeDocument.owner_id == owner_id)
                )
            ).all()
        )
        query_tokens = tokens(query)
        if not query_tokens:
            return {"query": query, "retrieval": "lexical_tfidf_v1", "results": []}
        query_counts = Counter(query_tokens)
        document_tokens = [tokens(doc.content + " " + doc.title) for doc in documents]
        frequencies = Counter(token for doc in document_tokens for token in set(doc))
        total = max(1, len(documents))
        scored = []
        for document, doc_tokens in zip(documents, document_tokens, strict=True):
            counts = Counter(doc_tokens)
            score = 0.0
            for token, qcount in query_counts.items():
                if counts[token]:
                    idf = math.log((1 + total) / (1 + frequencies[token])) + 1
                    score += qcount * (1 + math.log(counts[token])) * idf
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, document in scored[:limit]:
            results.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "snippet": self._snippet(document.content, query_tokens),
                    "score": round(score, 6),
                    "source_url": document.source_url,
                    "source_type": document.source_type,
                    "verification_status": document.verification_status,
                    "created_at": document.created_at,
                }
            )
        return {"query": query, "retrieval": "lexical_tfidf_v1_not_vector", "results": results}

    @staticmethod
    def _snippet(content: str, query_tokens: list[str], size: int = 500) -> str:
        lowered = content.casefold()
        positions = [lowered.find(token.casefold()) for token in query_tokens]
        positions = [position for position in positions if position >= 0]
        start = max(0, min(positions, default=0) - 100)
        return content[start : start + size]

    async def add_memory(self, owner_id: str, data: MemoryCreate) -> MemoryEntry:
        expires_at = None
        if data.expires_at:
            try:
                expires_at = datetime.fromisoformat(data.expires_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="expires_at must be ISO-8601") from exc
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(status_code=422, detail="expires_at must be in the future")
        entry = MemoryEntry(
            owner_id=owner_id,
            scope=data.scope,
            content=data.content,
            metadata_json=data.metadata,
            expires_at=expires_at,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def list_memory(self, owner_id: str, scope: str | None = None) -> list[MemoryEntry]:
        now = datetime.now(timezone.utc)
        query = select(MemoryEntry).where(MemoryEntry.owner_id == owner_id)
        if scope:
            query = query.where(MemoryEntry.scope == scope)
        entries = list((await self.db.scalars(query)).all())
        # Naive SQLite datetimes are interpreted as UTC; no expired item is returned.
        return [
            entry
            for entry in entries
            if entry.expires_at is None
            or entry.expires_at.replace(tzinfo=entry.expires_at.tzinfo or timezone.utc) > now
        ]

    async def delete_memory(self, owner_id: str, memory_id: str) -> None:
        entry = await self.db.scalar(
            select(MemoryEntry).where(MemoryEntry.id == memory_id, MemoryEntry.owner_id == owner_id)
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        await self.db.delete(entry)
        await self.db.commit()
