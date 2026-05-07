from __future__ import annotations

import re
import urllib.parse
from typing import Optional

from .types import ImageCandidate, ImageFeatures, IssueContext


GENERIC_PATTERNS = [
    r"\blogo\b",
    r"\bicon\b",
    r"\bmap\b",
    r"\bflag\b",
    r"\bsymbol\b",
    r"\billustration\b",
    r"\bstock\b",
    r"\bgeneric\b",
    r"\blocator\b",
    r"\bemblem\b",
    "로고",
    "지도",
    "국기",
    "아이콘",
    "상징",
    "일러스트",
]


def _safe_str(x: object) -> str:
    return str(x) if isinstance(x, str) else ""


def _meta_text(candidate: ImageCandidate) -> str:
    parts = [
        _safe_str(candidate.title),
        _safe_str(candidate.caption),
        _safe_str(candidate.page_url),
        _safe_str(candidate.url),
    ]
    # include some meta values
    for k in ("filename", "description", "entity", "page_title"):
        if k in (candidate.meta or {}):
            parts.append(_safe_str(candidate.meta.get(k)))
    return " ".join([p for p in parts if p]).strip().lower()


def _tokenize(text: str) -> set[str]:
    toks = re.findall(r"[0-9A-Za-z가-힣]{2,}", text or "")
    return {t.lower() for t in toks}


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = max(1, len(a | b))
    return inter / denom


def _normalize_url(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        host = (p.hostname or "").lower()
        path = re.sub(r"/+", "/", p.path or "")
        # drop common thumbnail sizing segments like /330px-...
        path = re.sub(r"/\\d+px-", "/px-", path)
        return f"{p.scheme}://{host}{path}"
    except Exception:
        return url


def extract_features(
    candidate: ImageCandidate,
    keyword: str,
    issue_ctx: IssueContext,
    seen_candidates: Optional[set[str]] = None,
) -> ImageFeatures:
    meta = _meta_text(candidate)
    kw = (keyword or "").strip().lower()
    kw_match = 1.0 if kw and kw in meta else 0.0

    ents = [e.strip().lower() for e in (issue_ctx.entities or []) if e and isinstance(e, str)]
    ent_hits = 0
    for e in ents:
        if e and e in meta:
            ent_hits += 1
    ent_match = (ent_hits / max(1, len(ents))) if ents else 0.0

    issue_toks = _tokenize(issue_ctx.text or "")
    meta_toks = _tokenize(meta)
    text_sim = _overlap(issue_toks, meta_toks)

    src = (candidate.source or "external").lower()
    if src == "wikipedia":
        src_rel = 1.0
    elif src == "wikimedia":
        src_rel = 0.85
    elif src == "article":
        src_rel = 0.9
    else:
        src_rel = 0.5

    w = candidate.width
    h = candidate.height
    if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
        # penalize tiny thumbnails
        min_side = min(w, h)
        quality = 1.0 if min_side >= 240 else 0.7 if min_side >= 120 else 0.4
    else:
        quality = 0.5

    generic_pen = 0.0
    for pat in GENERIC_PATTERNS:
        if re.search(pat, meta, flags=re.IGNORECASE):
            generic_pen = 1.0
            break

    dup_pen = 0.0
    norm = _normalize_url(candidate.url or "")
    if seen_candidates is not None:
        if norm in seen_candidates:
            dup_pen = 1.0
        else:
            seen_candidates.add(norm)

    return ImageFeatures(
        keyword_match=float(kw_match),
        entity_match=float(ent_match),
        text_similarity=float(text_sim),
        source_reliability=float(src_rel),
        quality_score=float(quality),
        generic_penalty=float(generic_pen),
        duplicate_penalty=float(dup_pen),
        clip_issue_similarity=None,
        clip_keyword_similarity=None,
    )

