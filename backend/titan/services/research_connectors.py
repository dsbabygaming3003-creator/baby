"""Research source connectors.

Each connector is an independent, versioned module implementing the same
contract. A connector failure never fails the research task: the outcome is
recorded (``OK`` / ``EMPTY`` / ``INACCESSIBLE`` / ``ERROR`` / ``UNAUTHORIZED``)
and the task continues with partial results.

Connector contract
------------------
    SourceConnector
        .id / .version / .platform / .access_policy / .requires_auth
        .search(query, limit) -> list[RawDocument]
        .verify(document) -> VerificationOutcome
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..security.core import secret_store
from ..security.net import SSRFError, http_client, validate_url
from .observability import log, metrics

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_INACCESSIBLE = "inaccessible"
STATUS_ERROR = "error"
STATUS_UNAUTHORIZED = "unauthorized"


@dataclass
class RawDocument:
    title: str
    url: str
    snippet: str = ""
    body: str = ""
    author: str = ""
    published_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    trust: str = "untrusted"

    def content_hash(self) -> str:
        return hashlib.sha256((self.title + "|" + self.url + "|" + self.snippet).encode()).hexdigest()


@dataclass
class ConnectorOutcome:
    connector_id: str
    platform: str
    status: str
    documents: List[RawDocument] = field(default_factory=list)
    detail: str = ""
    http_status: Optional[int] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id, "platform": self.platform, "status": self.status,
            "count": len(self.documents), "detail": self.detail, "http_status": self.http_status,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class Verification:
    status: str        # verified | partially_verified | unverified | unreachable
    confidence: float
    detail: str = ""
    http_status: Optional[int] = None


class SourceConnector:
    id: str = "base"
    version: str = "1.0.0"
    platform: str = "base"
    access_policy: str = "public"
    requires_auth: bool = False
    base_url: str = ""

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:  # pragma: no cover
        raise NotImplementedError

    async def verify(self, document: RawDocument) -> Verification:
        """Confirm the source URL actually resolves and matches the claim."""
        if not document.url:
            return Verification("unverified", 0.0, "document has no URL")
        try:
            validate_url(document.url)
        except SSRFError as exc:
            return Verification("unreachable", 0.0, f"blocked by egress policy: {exc}")
        try:
            async with http_client(timeout=settings.research_request_timeout) as client:
                response = await client.head(document.url)
                if response.status_code >= 400:
                    response = await client.get(document.url)
                if response.status_code < 400:
                    ctype = response.headers.get("content-type", "")
                    confidence = 0.9 if "html" in ctype or "json" in ctype or "xml" in ctype else 0.6
                    return Verification("verified", confidence,
                                         f"HTTP {response.status_code} {ctype}", response.status_code)
                return Verification("partially_verified", 0.4,
                                    f"HTTP {response.status_code}", response.status_code)
        except httpx.HTTPError as exc:
            return Verification("unreachable", 0.0, f"{type(exc).__name__}: {exc}"[:300])


class HttpConnector(SourceConnector):
    """Shared HTTP machinery with honest failure classification."""

    async def _get_json(self, url: str, params: Dict[str, Any] | None = None,
                        headers: Dict[str, str] | None = None) -> tuple[Optional[Any], ConnectorOutcome]:
        import time

        started = time.perf_counter()
        try:
            validate_url(url)
        except SSRFError as exc:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_INACCESSIBLE,
                                          detail=f"egress policy: {exc}",
                                          duration_ms=(time.perf_counter() - started) * 1000)
        try:
            async with http_client(timeout=settings.research_request_timeout) as client:
                response = await client.get(url, params=params, headers=headers or {})
        except httpx.ConnectError as exc:
            # TLS interception / DNS / refused — classify explicitly
            return None, ConnectorOutcome(self.id, self.platform, STATUS_INACCESSIBLE,
                                          detail=f"connection error: {exc}"[:300],
                                          duration_ms=(time.perf_counter() - started) * 1000)
        except httpx.TimeoutException as exc:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_ERROR,
                                          detail=f"timeout: {exc}",
                                          duration_ms=(time.perf_counter() - started) * 1000)
        except httpx.HTTPError as exc:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_ERROR,
                                          detail=f"{type(exc).__name__}: {exc}"[:300],
                                          duration_ms=(time.perf_counter() - started) * 1000)
        duration = (time.perf_counter() - started) * 1000
        if response.status_code in (401, 403):
            return None, ConnectorOutcome(self.id, self.platform, STATUS_UNAUTHORIZED,
                                          detail=f"HTTP {response.status_code}",
                                          http_status=response.status_code, duration_ms=duration)
        if response.status_code >= 400:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_ERROR,
                                          detail=f"HTTP {response.status_code}",
                                          http_status=response.status_code, duration_ms=duration)
        try:
            return response.json(), ConnectorOutcome(self.id, self.platform, STATUS_OK,
                                                     duration_ms=duration)
        except Exception as exc:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_ERROR,
                                          detail=f"invalid JSON: {exc}",
                                          http_status=response.status_code, duration_ms=duration)

    async def _get_text(self, url: str, params: Dict[str, Any] | None = None) -> tuple[Optional[str], ConnectorOutcome]:
        import time

        started = time.perf_counter()
        try:
            validate_url(url)
        except SSRFError as exc:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_INACCESSIBLE,
                                          detail=f"egress policy: {exc}")
        try:
            async with http_client(timeout=settings.research_request_timeout) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            kind = STATUS_INACCESSIBLE if isinstance(exc, httpx.ConnectError) else STATUS_ERROR
            return None, ConnectorOutcome(self.id, self.platform, kind,
                                          detail=f"{type(exc).__name__}: {exc}"[:300],
                                          duration_ms=(time.perf_counter() - started) * 1000)
        duration = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            return None, ConnectorOutcome(self.id, self.platform, STATUS_ERROR,
                                          detail=f"HTTP {response.status_code}",
                                          http_status=response.status_code, duration_ms=duration)
        return response.text, ConnectorOutcome(self.id, self.platform, STATUS_OK, duration_ms=duration)


# ---------------------------------------------------------------------------
# Concrete connectors
# ---------------------------------------------------------------------------
class GitHubConnector(HttpConnector):
    id = "github.v1"
    version = "1.0.0"
    platform = "github"
    access_policy = "public-api"
    requires_auth = False
    base_url = "https://api.github.com"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        headers = {"Accept": "application/vnd.github+json"}
        token = secret_store.resolve("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload, outcome = await self._get_json(
            f"{self.base_url}/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 30)},
            headers=headers,
        )
        if payload is None:
            outcome.connector_id = self.id
            outcome.platform = self.platform
            return outcome
        docs: List[RawDocument] = []
        for item in (payload.get("items") or [])[:limit]:
            docs.append(RawDocument(
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=(item.get("description") or "")[:600],
                author=(item.get("owner") or {}).get("login", ""),
                metadata={
                    "stars": item.get("stargazers_count"),
                    "license": ((item.get("license") or {}) or {}).get("spdx_id"),
                    "language": item.get("language"),
                    "pushed_at": item.get("pushed_at"),
                    "forks": item.get("forks_count"),
                    "open_issues": item.get("open_issues_count"),
                    "archived": item.get("archived"),
                    "default_branch": item.get("default_branch"),
                },
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
            outcome.detail = "no repositories matched the query"
        return outcome

    async def repo_details(self, full_name: str) -> Dict[str, Any]:
        payload, outcome = await self._get_json(f"{self.base_url}/repos/{full_name}")
        if payload is None:
            return {"error": outcome.detail, "status": outcome.status}
        return {
            "full_name": payload.get("full_name"),
            "description": payload.get("description"),
            "license": (payload.get("license") or {}).get("spdx_id"),
            "owner": (payload.get("owner") or {}).get("login"),
            "stars": payload.get("stargazers_count"),
            "forks": payload.get("forks_count"),
            "open_issues": payload.get("open_issues_count"),
            "language": payload.get("language"),
            "created_at": payload.get("created_at"),
            "pushed_at": payload.get("pushed_at"),
            "archived": payload.get("archived"),
            "topics": payload.get("topics"),
            "default_branch": payload.get("default_branch"),
            "url": payload.get("html_url"),
        }

    async def releases(self, full_name: str) -> List[Dict[str, Any]]:
        payload, _ = await self._get_json(f"{self.base_url}/repos/{full_name}/releases?per_page=5")
        if not isinstance(payload, list):
            return []
        return [{"tag": r.get("tag_name"), "published_at": r.get("published_at"),
                 "prerelease": r.get("prerelease"), "url": r.get("html_url")} for r in payload]


class PyPiConnector(HttpConnector):
    id = "pypi.v1"
    platform = "pypi"
    access_policy = "public-api"
    base_url = "https://pypi.org"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        # PyPI has no JSON search endpoint; the search page is HTML. Try the
        # exact-name JSON API first, then fall back to parsing the HTML index.
        payload, outcome = await self._get_json(f"{self.base_url}/pypi/{query}/json")
        if payload is not None and isinstance(payload, dict) and "info" in payload:
            info = payload["info"]
            outcome.documents = [RawDocument(
                title=info.get("name", ""),
                url=f"{self.base_url}/project/{info.get('name','')}/",
                snippet=(info.get("summary") or "")[:600],
                author=info.get("author", "") or "",
                metadata={"version": info.get("version"),
                          "license": info.get("license"),
                          "requires_python": info.get("requires_python"),
                          "home_page": info.get("home_page"),
                          "classifiers": (info.get("classifiers") or [])[:6]},
            )]
            if not outcome.documents:
                outcome.status = STATUS_EMPTY
            return outcome

        text, outcome = await self._get_text(f"{self.base_url}/search/", params={"q": query})
        if text is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        names = re.findall(r'package-snippet__name[^>]*>\s*([^<]+?)\s*<', text)
        if not names:
            names = re.findall(r'<span class="package-snippet__name">([^<]+)</span>', text)
        seen: set = set()
        docs: List[RawDocument] = []
        for name in names[: limit * 3]:
            name = name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            docs.append(RawDocument(
                title=name,
                url=f"{self.base_url}/project/{name}/",
                snippet=f"Python package '{name}' on PyPI",
                metadata={"source": "pypi-search-index"},
            ))
            if len(docs) >= limit:
                break
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
            outcome.detail = "no packages matched the query"
        return outcome


class NpmConnector(HttpConnector):
    id = "npm.v1"
    platform = "npm"
    access_policy = "public-api"
    base_url = "https://registry.npmjs.org"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(
            f"{self.base_url}/-/v1/search",
            params={"text": query, "size": min(limit, 20)},
        )
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in (payload.get("objects") or [])[:limit]:
            pkg = item.get("package") or {}
            docs.append(RawDocument(
                title=pkg.get("name", ""),
                url=pkg.get("links", {}).get("npm", f"{self.base_url}/package/{pkg.get('name')}"),
                snippet=(pkg.get("description") or "")[:600],
                author=(pkg.get("publisher") or {}).get("username", ""),
                metadata={"version": pkg.get("version"), "date": pkg.get("date"),
                          "keywords": pkg.get("keywords", [])[:8]},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class ArxivConnector(HttpConnector):
    id = "arxiv.v1"
    platform = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        import xml.etree.ElementTree as ET

        text, outcome = await self._get_text(self.base_url, params={
            "search_query": f"all:{query}", "start": 0, "max_results": limit,
        })
        if text is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            outcome.status = STATUS_ERROR
            outcome.detail = f"XML parse error: {exc}"
            return outcome
        docs = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            link = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("rel") == "alternate":
                    link = link_el.get("href", "")
            docs.append(RawDocument(title=title, url=link, snippet=summary[:800],
                                    published_at=(entry.findtext("atom:published", default="", namespaces=ns) or "")))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class HuggingFaceConnector(HttpConnector):
    id = "huggingface.v1"
    platform = "huggingface"
    requires_auth = False
    base_url = "https://huggingface.co/api"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(f"{self.base_url}/models",
                                                params={"search": query, "limit": limit})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in (payload if isinstance(payload, list) else [])[:limit]:
            docs.append(RawDocument(
                title=item.get("id", ""),
                url=f"https://huggingface.co/{item.get('id','')}",
                snippet=(item.get("pipeline_tag") or "")[:200],
                metadata={"pipeline_tag": item.get("pipeline_tag"),
                          "downloads": item.get("downloads"),
                          "likes": item.get("likes"),
                          "license": (item.get("cardData") or {}).get("license"),
                          "tags": (item.get("tags") or [])[:8]},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class StackExchangeConnector(HttpConnector):
    id = "stackexchange.v1"
    platform = "stackexchange"
    access_policy = "public-api-quota"
    base_url = "https://api.stackexchange.com/2.3/search/advanced"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={
            "q": query, "site": "stackoverflow", "pagesize": limit, "order": "desc", "sort": "relevance",
        })
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in (payload.get("items") or [])[:limit]:
            docs.append(RawDocument(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=(item.get("body_markdown") or item.get("body") or "")[:600],
                metadata={"score": item.get("score"), "answer_count": item.get("answer_count"),
                          "tags": item.get("tags", [])[:6]},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class RedditConnector(HttpConnector):
    id = "reddit.v1"
    platform = "reddit"
    access_policy = "public-json"
    base_url = "https://www.reddit.com/search.json"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={"q": query, "limit": limit})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for child in ((payload.get("data") or {}).get("children") or [])[:limit]:
            data = child.get("data") or {}
            docs.append(RawDocument(
                title=data.get("title", ""),
                url="https://www.reddit.com" + (data.get("permalink") or ""),
                snippet=(data.get("selftext") or "")[:600],
                author=data.get("author", ""),
                published_at=str(data.get("created_utc", "")),
                metadata={"subreddit": data.get("subreddit"), "score": data.get("score"),
                          "comments": data.get("num_comments")},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class OpenAlexConnector(HttpConnector):
    id = "openalex.v1"
    platform = "openalex"
    base_url = "https://api.openalex.org/works"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={"search": query, "per-page": limit})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in (payload.get("results") or [])[:limit]:
            docs.append(RawDocument(
                title=item.get("title", "") or "",
                url=item.get("doi") or item.get("id", ""),
                snippet="; ".join(item.get("authorships", [])[:3][i].get("author", {}).get("display_name", "")
                                  for i in range(min(3, len(item.get("authorships", [])))))[:300],
                published_at=item.get("publication_date", ""),
                metadata={"cited_by": item.get("cited_by_count"), "type": item.get("type"),
                          "open_access": (item.get("open_access") or {}).get("is_oa")},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class CrossrefConnector(HttpConnector):
    id = "crossref.v1"
    platform = "crossref"
    base_url = "https://api.crossref.org/works"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={"query": query, "rows": limit})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in ((payload.get("message") or {}).get("items") or [])[:limit]:
            title = (item.get("title") or [""])[0]
            docs.append(RawDocument(
                title=title,
                url=item.get("URL", ""),
                snippet=(item.get("abstract") or "")[:600],
                published_at=(item.get("issued", {}).get("date-parts") or [[""]])[0][0],
                metadata={"doi": item.get("DOI"), "publisher": item.get("publisher"),
                          "type": item.get("type")},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class WikipediaConnector(HttpConnector):
    id = "wikipedia.v1"
    platform = "wikipedia"
    base_url = "https://en.wikipedia.org/w/api.php"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={
            "action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": limit,
        })
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in ((payload.get("query") or {}).get("search") or [])[:limit]:
            title = item.get("title", "")
            docs.append(RawDocument(
                title=title,
                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                snippet=re.sub(r"<[^>]+>", "", item.get("snippet", ""))[:600],
                metadata={"wordcount": item.get("wordcount"), "timestamp": item.get("timestamp")},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class HackerNewsConnector(HttpConnector):
    id = "hn.v1"
    platform = "hackernews"
    base_url = "https://hn.algolia.com/api/v1/search"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={"query": query, "hitsPerPage": limit})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for hit in (payload.get("hits") or [])[:limit]:
            object_id = hit.get("objectID")
            docs.append(RawDocument(
                title=hit.get("title") or hit.get("story_title") or "",
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                snippet=(hit.get("story_text") or hit.get("comment_text") or "")[:600],
                author=hit.get("author", ""),
                metadata={"points": hit.get("points"), "comments": hit.get("num_comments"),
                          "hn_id": object_id},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


class DevToConnector(HttpConnector):
    id = "devto.v1"
    platform = "devto"
    base_url = "https://dev.to/api/articles"

    async def search(self, query: str, limit: int = 10) -> ConnectorOutcome:
        payload, outcome = await self._get_json(self.base_url, params={"tag": query.replace(" ", "-")})
        if payload is None:
            outcome.connector_id, outcome.platform = self.id, self.platform
            return outcome
        docs = []
        for item in (payload if isinstance(payload, list) else [])[:limit]:
            docs.append(RawDocument(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=(item.get("description") or "")[:600],
                author=(item.get("user") or {}).get("name", ""),
                published_at=item.get("published_at", ""),
                metadata={"reactions": item.get("positive_reactions_count"),
                          "tags": item.get("tag_list", [])[:6]},
            ))
        outcome.documents = docs
        if not docs:
            outcome.status = STATUS_EMPTY
        return outcome


CONNECTORS: List[SourceConnector] = [
    GitHubConnector(), PyPiConnector(), NpmConnector(), ArxivConnector(),
    HuggingFaceConnector(), StackExchangeConnector(), RedditConnector(),
    OpenAlexConnector(), CrossrefConnector(), WikipediaConnector(),
    HackerNewsConnector(), DevToConnector(),
]

CONNECTOR_INDEX: Dict[str, SourceConnector] = {c.id: c for c in CONNECTORS}
PLATFORM_INDEX: Dict[str, SourceConnector] = {c.platform: c for c in CONNECTORS}


async def run_connectors(query: str, platforms: List[str], limit: int = 8) -> List[ConnectorOutcome]:
    """Run the requested connectors concurrently; isolate every failure."""
    selected = []
    for platform in platforms:
        connector = PLATFORM_INDEX.get(platform) or CONNECTOR_INDEX.get(platform)
        if connector and connector not in selected:
            selected.append(connector)
    if not selected:
        selected = list(CONNECTORS)

    async def _one(connector: SourceConnector) -> ConnectorOutcome:
        try:
            outcome = await connector.search(query, limit)
        except Exception as exc:  # a connector must never break the task
            log.warning("connector %s crashed: %s", connector.id, exc)
            outcome = ConnectorOutcome(connector.id, connector.platform, STATUS_ERROR,
                                       detail=f"{type(exc).__name__}: {exc}"[:300])
        outcome.connector_id = connector.id
        outcome.platform = connector.platform
        metrics.incr("connector_calls_total", connector=connector.id, status=outcome.status)
        return outcome

    return list(await asyncio.gather(*(_one(c) for c in selected)))


async def probe_connectors() -> List[Dict[str, Any]]:
    """Live reachability probe of every registered connector."""
    results = []
    for connector in CONNECTORS:
        started = asyncio.get_event_loop().time()
        outcome = await connector.search("titan connectivity probe", limit=1)
        results.append({
            "connector_id": connector.id,
            "platform": connector.platform,
            "version": connector.version,
            "status": outcome.status,
            "detail": outcome.detail,
            "http_status": outcome.http_status,
            "latency_ms": round((asyncio.get_event_loop().time() - started) * 1000, 2),
        })
    return results
