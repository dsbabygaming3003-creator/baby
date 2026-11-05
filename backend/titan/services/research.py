"""TITAN's internal Global Intelligence Research Engine.

Owns its own database history, its own connector registry, its own findings
and its own knowledge base. It never reads the builder's session, browser
history or research documents.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..config import settings
from ..models import (
    KnowledgeDocument,
    ResearchDocument,
    ResearchFinding,
    ResearchSource,
    ResearchTask,
    SourceConnector,
)
from ..security.net import scan_injection, wrap_untrusted
from .observability import log, metrics
from .rag import ingest_document
from .research_connectors import (
    CONNECTORS,
    ConnectorOutcome,
    RawDocument,
    run_connectors,
)


def _relevance(query: str, text: str) -> float:
    """Simple, transparent lexical relevance in [0,1]."""
    q_tokens = {t.lower() for t in re.findall(r"[\w\-]{2,}", query)}
    if not q_tokens:
        return 0.0
    t_tokens = {t.lower() for t in re.findall(r"[\w\-]{2,}", text or "")}
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return round(overlap / len(q_tokens), 4)


class ResearchEngine:
    # -- registry ---------------------------------------------------------
    async def sync_connectors(self, session) -> int:
        count = 0
        for connector in CONNECTORS:
            existing = (await session.execute(
                select(SourceConnector).where(SourceConnector.id == connector.id)
            )).scalar_one_or_none()
            if existing is None:
                session.add(SourceConnector(
                    id=connector.id, name=connector.platform.title(), platform=connector.platform,
                    version=connector.version, access_policy=connector.access_policy,
                    requires_auth=connector.requires_auth, enabled=True,
                ))
                count += 1
            else:
                existing.version = connector.version
                existing.access_policy = connector.access_policy
        await session.flush()
        return count

    async def list_connectors(self, session) -> List[Dict[str, Any]]:
        rows = (await session.execute(select(SourceConnector).order_by(SourceConnector.platform))).scalars().all()
        return [
            {"id": r.id, "name": r.name, "platform": r.platform, "version": r.version,
             "access_policy": r.access_policy, "requires_auth": r.requires_auth,
             "enabled": r.enabled, "last_status": r.last_status,
             "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None}
            for r in rows
        ]

    async def update_connector_status(self, session, connector_id: str, status: str, stats: Dict[str, Any]) -> None:
        row = (await session.execute(
            select(SourceConnector).where(SourceConnector.id == connector_id)
        )).scalar_one_or_none()
        if row is None:
            row = SourceConnector(id=connector_id, name=connector_id, platform=connector_id.split(".")[0])
            session.add(row)
        row.last_status = status
        row.last_checked_at = datetime.now(timezone.utc)
        row.stats = stats or {}
        await session.flush()

    # -- tasks ------------------------------------------------------------
    async def create_task(self, session, *, query: str, platforms: List[str],
                          agent_id: Optional[str] = None, org_id: str = "default",
                          topic: str = "") -> ResearchTask:
        task = ResearchTask(
            query=query, platforms=platforms or [], agent_id=agent_id, org_id=org_id,
            topic=topic or query[:120], status="pending", connectors_total=len(platforms or []),
        )
        session.add(task)
        await session.flush()
        metrics.incr("research_tasks_total")
        return task

    async def run_task(self, session, task_id: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
        """Execute a research task across connectors, isolating failures."""
        task = (await session.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )).scalar_one_or_none()
        if task is None:
            raise ValueError(f"research task {task_id} not found")

        task.status = "running"
        await session.flush()

        limit = limit or settings.research_max_results_per_connector
        outcomes: List[ConnectorOutcome] = await run_connectors(task.query, task.platforms, limit)

        seen_hashes: set = set()
        total_docs = 0
        ok_connectors = 0
        failed_connectors = 0
        source_rows: List[ResearchSource] = []
        document_rows: List[ResearchDocument] = []

        for outcome in outcomes:
            await self.update_connector_status(session, outcome.connector_id, outcome.status,
                                               {"count": len(outcome.documents), "detail": outcome.detail})
            if outcome.status == "ok":
                ok_connectors += 1
            elif outcome.status == "empty":
                ok_connectors += 1
            else:
                failed_connectors += 1

            source_row = ResearchSource(
                task_id=task.id, connector_id=outcome.connector_id, platform=outcome.platform,
                status=outcome.status, url="", title=outcome.connector_id,
                http_status=outcome.http_status, verification_status="unverified",
                confidence=0.0, detail=outcome.detail[:1000],
            )
            session.add(source_row)
            source_rows.append(source_row)

            for doc in outcome.documents:
                digest = doc.content_hash()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                body = (doc.body or doc.snippet or "")[: settings.research_max_document_chars]
                scan = scan_injection(f"{doc.title}\n{doc.snippet}")
                relevance = _relevance(task.query, f"{doc.title} {doc.snippet}")
                document_row = ResearchDocument(
                    task_id=task.id, source_id=source_row.id, connector_id=outcome.connector_id,
                    title=doc.title[:500], url=doc.url[:800],
                    summary=doc.snippet[:4000], body=body, trust="untrusted",
                    injection_risk=scan.risk,
                    verification_status="unverified", confidence=0.0,
                    content_hash=digest, metadata_json={**doc.metadata, "relevance": relevance},
                )
                session.add(document_row)
                document_rows.append(document_row)
                total_docs += 1

        await session.flush()

        # verification pass (only for documents with a URL)
        verified = 0
        for document_row, doc in zip(document_rows, self._iter_docs(outcomes, seen_hashes)):
            outcome = await self._verify_document(doc)
            document_row.verification_status = outcome["status"]
            document_row.confidence = outcome["confidence"]
            if outcome["status"] == "verified":
                verified += 1
        await session.flush()

        findings = self._derive_findings(task.query, document_rows)
        for finding in findings:
            session.add(finding)

        task.status = "completed" if (ok_connectors or total_docs) else "failed"
        task.progress = 1.0
        task.connectors_ok = ok_connectors
        task.connectors_failed = failed_connectors
        task.findings_count = len(findings)
        task.report_path = str(self._write_report(task, outcomes, document_rows, findings))
        await session.flush()

        metrics.incr("research_tasks_completed", status=task.status)
        log.info("research task %s finished: %d docs, %d findings, %d connectors ok",
                 task.id, total_docs, len(findings), ok_connectors)

        return {
            "task_id": task.id, "status": task.status, "documents": total_docs,
            "findings": len(findings), "verified_documents": verified,
            "connectors": [o.to_dict() for o in outcomes],
            "report_path": task.report_path,
        }

    @staticmethod
    def _iter_docs(outcomes, seen_hashes):
        for outcome in outcomes:
            for doc in outcome.documents:
                if doc.content_hash() in seen_hashes:
                    seen_hashes.discard(doc.content_hash())
                    yield doc

    async def _verify_document(self, doc: RawDocument) -> Dict[str, Any]:
        from .research_connectors import CONNECTOR_INDEX

        connector = None
        for candidate in CONNECTORS:
            if candidate.platform == doc.url.split("/")[2] if "://" in doc.url else False:
                connector = candidate
                break
        if connector is None:
            # fall back to a generic HEAD check using the connector base
            from .research_connectors import HttpConnector
            connector = HttpConnector()
        verification = await connector.verify(doc)
        return {"status": verification.status, "confidence": verification.confidence,
                "detail": verification.detail, "http_status": verification.http_status}

    def _derive_findings(self, query: str, documents: List[ResearchDocument]) -> List[ResearchFinding]:
        findings: List[ResearchFinding] = []
        ranked = sorted(
            documents,
            key=lambda d: (d.confidence * 0.6 + (d.metadata_json or {}).get("relevance", 0) * 0.4),
            reverse=True,
        )
        for document in ranked[:12]:
            statement = document.summary.strip() or document.title
            if not statement:
                continue
            findings.append(ResearchFinding(
                task_id=document.task_id, document_id=document.id,
                statement=statement[:2000], evidence_url=document.url,
                verification_status=document.verification_status, confidence=document.confidence,
                relevance=(document.metadata_json or {}).get("relevance", 0.0),
                tags=[document.platform] if hasattr(document, "platform") else [],
            ))
        return findings

    def _write_report(self, task: ResearchTask, outcomes, documents, findings) -> Path:
        directory = settings.data_dir / "reports"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"research-{task.id}.md"
        lines = [
            f"# TITAN Research Report — {task.topic}",
            "",
            f"- **Task id:** `{task.id}`",
            f"- **Query:** {task.query}",
            f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"- **Documents:** {len(documents)} · **Findings:** {len(findings)}",
            "",
            "## Source coverage",
            "",
            "| Connector | Platform | Status | HTTP | Detail |",
            "|---|---|---|---|---|",
        ]
        for outcome in outcomes:
            lines.append(
                f"| `{outcome.connector_id}` | {outcome.platform} | **{outcome.status}** | "
                f"{outcome.http_status or '-'} | {outcome.detail[:120]} |"
            )
        lines += ["", "## Findings", ""]
        for finding in findings:
            lines.append(
                f"### {finding.statement[:200]}\n"
                f"- verification: **{finding.verification_status}** (confidence {finding.confidence:.2f})\n"
                f"- source: {finding.evidence_url or 'n/a'}\n"
            )
        lines += ["", "## Retrieved documents", ""]
        for document in documents:
            lines.append(
                f"- **{document.title}** — {document.url}\n"
                f"  - verification: {document.verification_status} · confidence {document.confidence:.2f} · "
                f"injection risk {document.injection_risk:.2f}\n"
            )
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- knowledge --------------------------------------------------------
    async def ingest_to_knowledge(self, session, document_id: str, *, org_id: str = "default") -> Optional[KnowledgeDocument]:
        document = (await session.execute(
            select(ResearchDocument).where(ResearchDocument.id == document_id)
        )).scalar_one_or_none()
        if document is None:
            return None
        knowledge = KnowledgeDocument(
            org_id=org_id, source_type="research", title=document.title,
            content=document.body or document.summary, source_url=document.url,
            verification_status=document.verification_status, confidence=document.confidence,
            licence_note="snippet retained for retrieval; full text only when store_full_text is enabled",
            metadata_json={"research_document_id": document.id, "connector_id": document.connector_id},
        )
        session.add(knowledge)
        await session.flush()
        await ingest_document(session, document_id=knowledge.id,
                              content=knowledge.content)
        return knowledge

    async def list_findings(self, session, task_id: str) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(ResearchFinding).where(ResearchFinding.task_id == task_id)
        )).scalars().all()
        return [
            {"id": r.id, "statement": r.statement, "evidence_url": r.evidence_url,
             "verification_status": r.verification_status, "confidence": r.confidence,
             "relevance": r.relevance, "tags": r.tags,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]

    async def list_sources(self, session, task_id: str) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(ResearchSource).where(ResearchSource.task_id == task_id)
        )).scalars().all()
        return [
            {"id": r.id, "connector_id": r.connector_id, "platform": r.platform, "status": r.status,
             "url": r.url, "title": r.title, "http_status": r.http_status,
             "verification_status": r.verification_status, "confidence": r.confidence,
             "detail": r.detail}
            for r in rows
        ]

    async def list_documents(self, session, task_id: str) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(ResearchDocument).where(ResearchDocument.task_id == task_id)
        )).scalars().all()
        return [
            {"id": r.id, "title": r.title, "url": r.url, "summary": r.summary,
             "verification_status": r.verification_status, "confidence": r.confidence,
             "injection_risk": r.injection_risk, "trust": r.trust,
             "connector_id": r.connector_id, "metadata": r.metadata_json}
            for r in rows
        ]


research_engine = ResearchEngine()
