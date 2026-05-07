from __future__ import annotations

import asyncio
import hashlib
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Optional

from .cache import SimpleTTLCache
from .cutoff import adaptive_cutoff
from .features import extract_features
from .ranker import HeuristicImageRanker
from .retrievers import BaseImageRetriever
from .types import IconSelection, ImageCandidate, IssueContext


def _norm_url(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        host = (p.hostname or "").lower()
        path = p.path or ""
        return f"{p.scheme}://{host}{path}"
    except Exception:
        return url


def _dedupe_candidates(cands: list[ImageCandidate]) -> list[ImageCandidate]:
    out: list[ImageCandidate] = []
    seen: set[str] = set()
    for c in cands:
        u = _norm_url(c.url)
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(c)
    return out


@dataclass
class ImageRankingPipeline:
    retrievers: list[BaseImageRetriever]
    ranker: HeuristicImageRanker
    cache: Optional[SimpleTTLCache] = None

    async def select_icon(
        self,
        keyword: str,
        issue_ctx: IssueContext,
        fallback_factory: Callable[[str], str],
    ) -> IconSelection:
        kw = (keyword or "").strip()
        if not kw:
            fb = fallback_factory(keyword)
            return IconSelection(
                icon_url=fb,
                selected=False,
                score=0.0,
                source="fallback",
                reason="empty_keyword",
                fallback=True,
                candidates_count=0,
            )

        cache_key = None
        if self.cache is not None:
            cache_key = "imgc:" + hashlib.sha1(f"{issue_ctx.issue_id}:{kw}".encode("utf-8")).hexdigest()
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and "icon_url" in cached:
                return IconSelection(**cached)  # type: ignore[arg-type]

        # retrieval (parallel)
        tasks = [r.retrieve(kw, issue_ctx) for r in self.retrievers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        candidates: list[ImageCandidate] = []
        for res in results:
            if isinstance(res, Exception):
                continue
            if isinstance(res, list):
                candidates.extend([c for c in res if isinstance(c, ImageCandidate)])

        candidates = _dedupe_candidates(candidates)

        seen_norm: set[str] = set()
        items = []
        for c in candidates:
            feats = extract_features(c, kw, issue_ctx, seen_candidates=seen_norm)
            items.append((c, feats))

        ranked = self.ranker.rank(items)
        selected, cutoff_reason = adaptive_cutoff(ranked)

        if selected is None:
            fb = fallback_factory(kw)
            out = IconSelection(
                icon_url=fb,
                selected=False,
                score=float(ranked[0].score) if ranked else 0.0,
                source="fallback",
                reason=f"{cutoff_reason}; top={ranked[0].reason if ranked else 'n/a'}",
                fallback=True,
                candidates_count=len(candidates),
            )
        else:
            out = IconSelection(
                icon_url=selected.candidate.url,
                selected=True,
                score=float(selected.score),
                source=str(selected.candidate.source),
                reason=f"{cutoff_reason}; {selected.reason}",
                fallback=False,
                candidates_count=len(candidates),
            )

        if self.cache is not None and cache_key is not None:
            # store as plain dict for simple JSON-ish persistence
            self.cache.set(
                cache_key,
                {
                    "icon_url": out.icon_url,
                    "selected": out.selected,
                    "score": out.score,
                    "source": out.source,
                    "reason": out.reason,
                    "fallback": out.fallback,
                    "candidates_count": out.candidates_count,
                },
                ttl_s=3600.0,
            )

        return out

