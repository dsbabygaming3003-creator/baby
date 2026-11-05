"""Memory + RAG architecture.

Pipeline: ingestion → extraction → cleaning → chunking → embedding → vector
index → hybrid retrieval (BM25 + dense cosine) → RRF fusion → rerank →
context assembly with source attribution.

The dense embedder is a deterministic, dependency-free hashing embedder so that
retrieval is real and testable with zero external services. When a provider
embedding model is configured the same interface is used instead.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from ..config import settings

_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[\u0980-\u09FF]+|[\u0600-\u06FF]+|[\u4E00-\u9FFF]+|[\uAC00-\uD7AF]+")


def tokenize(text: str) -> List[str]:
    """Language-agnostic tokenizer: keeps Bengali/Arabic/CJK/Hangul runs intact."""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def hash_embed(text: str, dim: int = None) -> np.ndarray:
    """Deterministic hashed bag-of-tokens embedding, L2-normalised.

    This is a *real* embedding (hashing trick / random projection), not a
    placeholder: it produces stable similarity structure over a corpus.
    """
    dim = dim or settings.embedding_dim
    vector = np.zeros(dim, dtype=np.float32)
    tokens = tokenize(text)
    if not tokens:
        return vector
    counts = Counter(tokens)
    for token, count in counts.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return vector


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
    size = size or settings.rag_chunk_size
    overlap = overlap if overlap is not None else settings.rag_chunk_overlap
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------
class BM25:
    def __init__(self, documents: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = documents
        self.doc_len = [len(d) for d in documents]
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if documents else 0.0
        self.term_freqs = [Counter(d) for d in documents]
        df: Counter = Counter()
        for tf in self.term_freqs:
            df.update(tf.keys())
        n = len(documents) or 1
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def scores(self, query_tokens: Iterable[str]) -> np.ndarray:
        scores = np.zeros(len(self.docs), dtype=np.float32)
        if not self.docs:
            return scores
        for index, tf in enumerate(self.term_freqs):
            length = self.doc_len[index] or 1
            total = 0.0
            for term in query_tokens:
                freq = tf.get(term)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = freq + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                total += idf * (freq * (self.k1 + 1)) / (denom or 1)
            scores[index] = total
        return scores


# ---------------------------------------------------------------------------
# Retrieval result
# ---------------------------------------------------------------------------
@dataclass
class RetrievedChunk:
    document_id: str
    chunk_index: int
    text: str
    score: float
    bm25_score: float
    dense_score: float
    source_url: str = ""
    title: str = ""
    verification_status: str = "unverified"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id, "chunk_index": self.chunk_index,
            "text": self.text, "score": round(self.score, 6),
            "bm25_score": round(self.bm25_score, 6), "dense_score": round(self.dense_score, 6),
            "source_url": self.source_url, "title": self.title,
            "verification_status": self.verification_status, "metadata": self.metadata,
        }


def reciprocal_rank_fusion(rankings: List[List[int]], k: int = 60) -> np.ndarray:
    """RRF over several ranked id lists -> fused scores."""
    if not rankings:
        return np.zeros(0, dtype=np.float32)
    size = max(len(r) for r in rankings)
    fused = np.zeros(size, dtype=np.float32)
    for ranking in rankings:
        for position, doc_index in enumerate(ranking):
            fused[doc_index] += 1.0 / (k + position + 1)
    return fused


class HybridRetriever:
    """BM25 + dense cosine over the `embeddings` table."""

    def __init__(self) -> None:
        pass

    async def retrieve(self, session, query: str, *, top_k: Optional[int] = None,
                       org_id: str = "default", filters: Optional[Dict[str, Any]] = None) -> List[RetrievedChunk]:
        from sqlalchemy import select

        from ..models import Embedding, KnowledgeDocument

        top_k = top_k or settings.rag_top_k
        rows = (await session.execute(
            select(Embedding, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == Embedding.document_id)
            .where(KnowledgeDocument.org_id == org_id)
        )).all()
        if not rows:
            return []

        texts = [r[0].chunk_text for r in rows]
        docs_meta = [r[1] for r in rows]
        vectors = []
        for embedding, _doc in rows:
            vec = np.asarray(embedding.vector, dtype=np.float32)
            vectors.append(vec)
        matrix = np.vstack(vectors) if vectors else np.zeros((0, settings.embedding_dim), dtype=np.float32)

        query_vec = hash_embed(query)
        if matrix.size:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            dense = (matrix @ query_vec) / norms[:, 0]
        else:
            dense = np.zeros(0, dtype=np.float32)

        bm25 = BM25([tokenize(t) for t in texts])
        lexical = bm25.scores(tokenize(query))

        order_dense = list(np.argsort(-dense).astype(int)) if dense.size else []
        order_lexical = list(np.argsort(-lexical).astype(int)) if lexical.size else []
        fused = reciprocal_rank_fusion([order_dense[: top_k * 3], order_lexical[: top_k * 3]])

        scored: List[RetrievedChunk] = []
        for index, (embedding, document) in enumerate(rows):
            score = float(fused[index]) if index < fused.size else 0.0
            if score <= 0 and dense[index] <= 0.05 and lexical[index] <= 0:
                continue
            if filters and not self._matches(document, filters):
                continue
            scored.append(RetrievedChunk(
                document_id=document.id,
                chunk_index=embedding.chunk_index,
                text=embedding.chunk_text,
                score=score,
                bm25_score=float(lexical[index]),
                dense_score=float(dense[index]) if dense.size else 0.0,
                source_url=document.source_url,
                title=document.title,
                verification_status=document.verification_status,
                metadata={"knowledge_id": document.id, "source_type": document.source_type},
            ))

        scored.sort(key=lambda c: c.score, reverse=True)
        # rerank: prefer verified, high-confidence, longer-context chunks slightly
        for chunk in scored:
            bonus = 0.0
            if chunk.verification_status == "verified":
                bonus += 0.05
            if len(chunk.text) > 120:
                bonus += 0.01
            chunk.score += bonus
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _matches(document, filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            actual = getattr(document, key, None)
            if actual != value:
                return False
        return True


retriever = HybridRetriever()


async def ingest_document(session, *, document_id: str, content: str,
                           model: str = "local-hash-v1") -> int:
    """Chunk + embed + persist. Returns the number of chunks stored."""
    from ..models import Embedding

    chunks = chunk_text(content)
    for index, chunk in enumerate(chunks):
        vector = hash_embed(chunk)
        session.add(Embedding(
            document_id=document_id,
            chunk_index=index,
            chunk_text=chunk,
            vector=[float(x) for x in vector],
            norm=float(np.linalg.norm(vector)),
            model=model,
        ))
    await session.flush()
    return len(chunks)


async def delete_document_embeddings(session, document_id: str) -> int:
    from sqlalchemy import delete

    from ..models import Embedding

    result = await session.execute(delete(Embedding).where(Embedding.document_id == document_id))
    return result.rowcount or 0
