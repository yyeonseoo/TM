from __future__ import annotations

import asyncio
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests

from .types import ImageCandidate, IssueContext


WIKIPEDIA_SUMMARY_API = "https://ko.wikipedia.org/api/rest_v1/page/summary/"


class BaseImageRetriever(ABC):
    @abstractmethod
    async def retrieve(self, keyword: str, issue_ctx: IssueContext) -> list[ImageCandidate]:
        raise NotImplementedError


def _req_get_json(url: str, *, timeout_s: float) -> Optional[dict[str, Any]]:
    try:
        r = requests.get(url, timeout=timeout_s, headers={"User-Agent": "TM-image-ranking/1.0"}, allow_redirects=True)
        if r.status_code != 200:
            return None
        obj = r.json()
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


class WikipediaRetriever(BaseImageRetriever):
    """
    High-precision candidate: ko.wikipedia summary thumbnail/originalimage.
    """

    def __init__(self, *, timeout_s: float = 3.5):
        self.timeout_s = float(timeout_s)

    async def retrieve(self, keyword: str, issue_ctx: IssueContext) -> list[ImageCandidate]:
        kw = (keyword or "").strip()
        if not kw:
            return []
        url = WIKIPEDIA_SUMMARY_API + urllib.parse.quote(kw)
        obj = await asyncio.to_thread(_req_get_json, url, timeout_s=self.timeout_s)
        if not obj:
            return []
        title = obj.get("title") if isinstance(obj.get("title"), str) else kw
        page_url = None
        content_urls = obj.get("content_urls") or {}
        if isinstance(content_urls, dict):
            desktop = content_urls.get("desktop") or {}
            if isinstance(desktop, dict) and isinstance(desktop.get("page"), str):
                page_url = desktop.get("page")
        thumb = (obj.get("thumbnail") or {}).get("source")
        orig = (obj.get("originalimage") or {}).get("source")
        candidates: list[ImageCandidate] = []
        for u in [thumb, orig]:
            if isinstance(u, str) and u.startswith("http"):
                candidates.append(
                    ImageCandidate(
                        url=u,
                        source="wikipedia",
                        title=title,
                        caption=obj.get("description") if isinstance(obj.get("description"), str) else None,
                        page_url=page_url,
                        width=(obj.get("thumbnail") or {}).get("width") if u == thumb else (obj.get("originalimage") or {}).get("width"),
                        height=(obj.get("thumbnail") or {}).get("height") if u == thumb else (obj.get("originalimage") or {}).get("height"),
                        meta={"keyword": kw, "api": "summary"},
                    )
                )
        # de-dupe by url
        uniq = []
        seen = set()
        for c in candidates:
            if c.url in seen:
                continue
            seen.add(c.url)
            uniq.append(c)
        return uniq


class WikimediaRetriever(BaseImageRetriever):
    """
    Optional expansion. For safety, return [] if anything is uncertain.
    TODO: Implement Wikimedia Commons search API (opensearch or mediawiki API).
    """

    def __init__(self, *, timeout_s: float = 3.5):
        self.timeout_s = float(timeout_s)

    async def retrieve(self, keyword: str, issue_ctx: IssueContext) -> list[ImageCandidate]:
        return []


class ArticleImageRetriever(BaseImageRetriever):
    """
    Stub retriever for article images. Needs article HTML / stored image URLs.
    """

    async def retrieve(self, keyword: str, issue_ctx: IssueContext) -> list[ImageCandidate]:
        return []

