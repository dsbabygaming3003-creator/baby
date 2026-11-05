from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import (
    KnowledgeDocument,
    ResearchDocument,
    ResearchFinding,
    ResearchSource,
    ResearchTask,
    utcnow,
)
from ..utils import content_hash


@dataclass
class NormalizedDocument:
    external_id: str
    title: str
    url: str
    content: str
    author: str | None
    published_at: str | None
    verification_status: str
    metadata: dict[str, Any]


@dataclass
class ConnectorResult:
    endpoint: str
    documents: list[NormalizedDocument]


class SourceConnector(ABC):
    id: str
    version: str

    @abstractmethod
    async def search(self, query: str, max_results: int) -> ConnectorResult:
        """Retrieve public, authorized content and normalize source provenance."""


class GitHubConnector(SourceConnector):
    id = "github"
    version = "1.0.0"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def search(self, query: str, max_results: int) -> ConnectorResult:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "TITAN-Research/0.1"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        endpoint = "https://api.github.com/search/repositories"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=10), follow_redirects=False
        ) as client:
            response = await client.get(
                endpoint,
                params={"q": query, "per_page": max_results, "sort": "stars"},
                headers=headers,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub API returned HTTP {response.status_code}")
        payload = response.json()
        documents = []
        for item in payload.get("items", []):
            description = item.get("description") or "No repository description supplied."
            content = (
                f"Repository: {item['full_name']}\nDescription: {description}\n"
                f"Owner: {item.get('owner', {}).get('login')}\n"
                f"Language: {item.get('language')}\nLicense: {(item.get('license') or {}).get('spdx_id')}\n"
                f"Default branch: {item.get('default_branch')}\nArchived: {item.get('archived')}\n"
                f"Last pushed: {item.get('pushed_at')}\nStars observed: {item.get('stargazers_count')}"
            )
            documents.append(
                NormalizedDocument(
                    external_id=str(item["id"]),
                    title=item["full_name"],
                    url=item["html_url"],
                    content=content,
                    author=item.get("owner", {}).get("login"),
                    published_at=item.get("created_at"),
                    verification_status="verified_official_api",
                    metadata={
                        "untrusted_external_content": True,
                        "fork": item.get("fork"),
                        "open_issues": item.get("open_issues_count"),
                        "api_url": item.get("url"),
                        "score": item.get("score"),
                    },
                )
            )
        return ConnectorResult(endpoint=f"{endpoint}?q={query}", documents=documents)


class ResearchService:
    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings
        self.registry: dict[str, SourceConnector] = {"github": GitHubConnector(settings)}

    def connectors(self) -> list[dict[str, str]]:
        return [
            {
                "id": connector.id,
                "version": connector.version,
                "access": "public_official_api",
                "content_trust": "untrusted_external_data",
            }
            for connector in self.registry.values()
        ]

    async def create_task(
        self, owner_id: str, query: str, connectors: list[str], max_results: int
    ) -> ResearchTask:
        task = ResearchTask(
            owner_id=owner_id, query=query, connectors=connectors, max_results=max_results
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def run(self, task_id: str) -> ResearchTask:
        task = await self.db.get(ResearchTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Research task not found")
        task.status = "running"
        task.error = None
        await self.db.commit()
        successful = 0
        failed = 0
        seen_hashes: set[str] = set()
        for connector_id in task.connectors:
            connector = self.registry.get(connector_id)
            if connector is None:
                self.db.add(
                    ResearchSource(
                        task_id=task.id,
                        connector=connector_id,
                        connector_version="unknown",
                        query=task.query,
                        status="unsupported",
                        error="Connector is not registered",
                    )
                )
                failed += 1
                await self.db.commit()
                continue
            source = ResearchSource(
                task_id=task.id,
                connector=connector.id,
                connector_version=connector.version,
                query=task.query,
                status="running",
            )
            self.db.add(source)
            await self.db.commit()
            await self.db.refresh(source)
            try:
                result = await connector.search(task.query, task.max_results)
                source.endpoint = result.endpoint
                source.status = "succeeded"
                successful += 1
                for item in result.documents:
                    digest = content_hash(f"{item.url}\n{item.content}")
                    if digest in seen_hashes:
                        continue
                    seen_hashes.add(digest)
                    document = ResearchDocument(
                        task_id=task.id,
                        source_id=source.id,
                        external_id=item.external_id,
                        content_hash=digest,
                        title=item.title,
                        url=item.url,
                        content=item.content,
                        author=item.author,
                        published_at=item.published_at,
                        verification_status=item.verification_status,
                        metadata_json=item.metadata,
                    )
                    self.db.add(document)
                    await self.db.flush()
                    summary = self._factual_summary(item)
                    self.db.add(
                        ResearchFinding(
                            task_id=task.id,
                            document_id=document.id,
                            summary=summary,
                            confidence=0.95,
                            verification_status=item.verification_status,
                            evidence_url=item.url,
                        )
                    )
                    self.db.add(
                        KnowledgeDocument(
                            owner_id=task.owner_id,
                            title=item.title,
                            content=item.content,
                            source_url=item.url,
                            source_type=connector.id,
                            verification_status=item.verification_status,
                            metadata_json={
                                "research_task_id": task.id,
                                "untrusted_external_content": True,
                            },
                            content_hash=digest,
                        )
                    )
            except Exception as exc:
                source.status = "failed"
                source.error = str(exc)[:1000]
                failed += 1
            await self.db.commit()
        task.status = "succeeded" if failed == 0 else ("partial" if successful else "failed")
        task.error = (
            "One or more connectors failed; partial results preserved"
            if successful and failed
            else ("All connectors failed" if failed and not successful else None)
        )
        task.completed_at = utcnow()
        task.report_path = str(await self._write_report(task))
        await self.db.commit()
        await self.db.refresh(task)
        return task

    @staticmethod
    def _factual_summary(item: NormalizedDocument) -> str:
        return (
            f"{item.title} was returned by the official connector. "
            f"Source verification: {item.verification_status}. "
            "Capabilities, security and compatibility still require independent review."
        )

    async def detail(self, task_id: str, owner_id: str) -> dict[str, Any]:
        task = await self.db.scalar(
            select(ResearchTask).where(
                ResearchTask.id == task_id, ResearchTask.owner_id == owner_id
            )
        )
        if not task:
            raise HTTPException(status_code=404, detail="Research task not found")
        sources = list(
            (
                await self.db.scalars(
                    select(ResearchSource).where(ResearchSource.task_id == task_id)
                )
            ).all()
        )
        documents = list(
            (
                await self.db.scalars(
                    select(ResearchDocument).where(ResearchDocument.task_id == task_id)
                )
            ).all()
        )
        findings = list(
            (
                await self.db.scalars(
                    select(ResearchFinding).where(ResearchFinding.task_id == task_id)
                )
            ).all()
        )
        return {"task": task, "sources": sources, "documents": documents, "findings": findings}

    async def _write_report(self, task: ResearchTask) -> Path:
        sources = list(
            (
                await self.db.scalars(
                    select(ResearchSource).where(ResearchSource.task_id == task.id)
                )
            ).all()
        )
        documents = list(
            (
                await self.db.scalars(
                    select(ResearchDocument).where(ResearchDocument.task_id == task.id)
                )
            ).all()
        )
        path = self.settings.report_root / f"research-{task.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Research report: {task.query}",
            "",
            f"- Task ID: `{task.id}`",
            f"- Status: **{task.status}**",
            f"- Generated: {utcnow().isoformat()}",
            "- External content is untrusted data, not agent instructions.",
            "",
            "## Source coverage",
            "",
            "| Connector | Version | Status | Error |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| {s.connector} | {s.connector_version} | {s.status} | {s.error or ''} |"
            for s in sources
        )
        lines.extend(["", "## Verified source records", ""])
        for document in documents:
            lines.extend(
                [
                    f"### {document.title}",
                    "",
                    f"- URL: {document.url}",
                    f"- Verification: {document.verification_status}",
                    f"- Retrieved: {document.retrieved_at.isoformat()}",
                    f"- SHA-256: `{document.content_hash}`",
                    "",
                    "```text",
                    document.content.replace("```", "'''"),
                    "```",
                    "",
                ]
            )
        if not documents:
            lines.append("No documents were retrieved. See connector errors above.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    async def export_report(self, task_id: str, owner_id: str) -> str:
        detail = await self.detail(task_id, owner_id)
        task: ResearchTask = detail["task"]
        if not task.report_path or not Path(task.report_path).is_file():
            raise HTTPException(status_code=409, detail="Research report is not available yet")
        return Path(task.report_path).read_text(encoding="utf-8")

    async def delete_history(self, owner_id: str) -> None:
        # Retention helper; report deletion is deliberately explicit in a later destructive workflow.
        task_ids = list(
            (
                await self.db.scalars(
                    select(ResearchTask.id).where(ResearchTask.owner_id == owner_id)
                )
            ).all()
        )
        if task_ids:
            await self.db.execute(
                delete(KnowledgeDocument).where(
                    KnowledgeDocument.metadata_json["research_task_id"].as_string().in_(task_ids)
                )
            )
        await self.db.commit()
