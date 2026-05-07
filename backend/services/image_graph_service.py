from __future__ import annotations

import math
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional
import html

import requests

import asyncio

from graph_pipeline.models.graph_quality_model import (
    adaptive_mix_weights,
    blending_weight_from_auroc,
    compute_baseline_importance,
    graph_score_from_issue,
    load_graph_quality_model,
    load_graph_quality_metrics,
)

from backend.services.image_ranking.cache import SimpleTTLCache
from backend.services.image_ranking.pipeline import ImageRankingPipeline
from backend.services.image_ranking.ranker import HeuristicImageRanker
from backend.services.image_ranking.retrievers import (
    ArticleImageRetriever,
    WikipediaRetriever,
    WikimediaRetriever,
)
from backend.services.image_ranking.types import IssueContext


WIKIPEDIA_SUMMARY_API = "https://ko.wikipedia.org/api/rest_v1/page/summary/"


@dataclass(frozen=True)
class ImageCandidate:
    keyword: str
    url: str
    title: str = ""
    score: float = 0.5


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return float(default)
        return v
    except Exception:
        return float(default)


def _tokenize(text: str) -> set[str]:
    # simple tokenizer: Korean/English alnum chunks
    toks = re.findall(r"[0-9A-Za-z가-힣]{2,}", text or "")
    return {t.lower() for t in toks}


def _keyword_match_score(meta_text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    meta = (meta_text or "").lower()
    hit = 0
    for k in keywords:
        if not k:
            continue
        if str(k).lower() in meta:
            hit += 1
    return hit / max(1, len(keywords))


def fetch_wikipedia_thumbnail(keyword: str, *, timeout_s: float = 4.0) -> Optional[str]:
    """
    Best-effort Wikipedia thumbnail URL lookup (ko wiki).
    Returns a https URL or None.
    """
    kw = (keyword or "").strip()
    if not kw:
        return None
    url = WIKIPEDIA_SUMMARY_API + urllib.parse.quote(kw)
    try:
        r = requests.get(url, timeout=timeout_s, headers={"User-Agent": "TM-issue-graph/1.0"})
        if r.status_code != 200:
            return None
        obj = r.json()
        thumb = (obj.get("thumbnail") or {}).get("source")
        if isinstance(thumb, str) and thumb.startswith("http"):
            return thumb
        # Sometimes "originalimage"
        orig = (obj.get("originalimage") or {}).get("source")
        if isinstance(orig, str) and orig.startswith("http"):
            return orig
        return None
    except Exception:
        return None


def fetch_and_rank_images(issue_text: str, keywords: list[str], top_k: int = 10) -> dict[str, Any]:
    """
    Offline-friendly image retrieval + ranking.

    Current implementation:
    - retrieval: Wikipedia thumbnail per keyword (best-effort)
    - ranking: heuristic score (keyword match + light quality prior)
    - adaptive cutoff: mean - 0.3*std
    """
    issue_text = issue_text or ""
    issue_toks = _tokenize(issue_text)

    candidates: list[ImageCandidate] = []
    for kw in keywords[: max(1, top_k)]:
        thumb = fetch_wikipedia_thumbnail(kw)
        if not thumb:
            continue
        # heuristic features
        meta_text = f"{kw} {thumb}"
        kw_match = _keyword_match_score(meta_text, keywords)
        # tiny prior: if keyword appears in issue text tokens, boost
        ent_like = 1.0 if kw.lower() in issue_toks else 0.6
        score = 0.55 * ent_like + 0.45 * kw_match
        candidates.append(ImageCandidate(keyword=kw, url=thumb, title=kw, score=float(score)))

    candidates.sort(key=lambda c: c.score, reverse=True)
    scores = [c.score for c in candidates]
    if not scores:
        return {"selected_images": [], "scores": {}, "threshold": None, "features": {}}

    mu = sum(scores) / len(scores)
    var = sum((s - mu) ** 2 for s in scores) / max(1, len(scores))
    sigma = math.sqrt(var)
    threshold = mu - 0.3 * sigma

    selected = [c for c in candidates if c.score > threshold][:top_k]
    return {
        "selected_images": [{"keyword": c.keyword, "url": c.url, "score": c.score, "title": c.title} for c in selected],
        "scores": {c.url: c.score for c in candidates},
        "threshold": threshold,
        "features": {},
    }


def _svg_fallback_avatar(label: str, *, size: int = 128) -> str:
    """
    Create a tiny SVG avatar as a data URI (always available fallback icon).
    This avoids 'only some nodes show images' when Wikipedia thumbnails are missing.
    """
    txt = (label or "").strip()
    # show first 2 visible chars
    short = txt[:2] if len(txt) >= 2 else (txt[:1] if txt else "?")
    short = html.escape(short)
    # simple stable-ish color based on label hash
    h = abs(hash(txt)) % 360
    bg = f"hsl({h}, 65%, 55%)"
    fg = "rgba(255,255,255,0.96)"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
<defs>
  <clipPath id="c"><circle cx="{size/2}" cy="{size/2}" r="{size/2}"/></clipPath>
</defs>
<g clip-path="url(#c)">
  <rect width="{size}" height="{size}" fill="{bg}"/>
  <text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle"
        font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial"
        font-size="{int(size*0.38)}" font-weight="700" fill="{fg}">{short}</text>
</g>
</svg>"""
    # URL-encode for data URI
    encoded = urllib.parse.quote(svg, safe="(),:%#@?/=&;+-_.*'!~")
    return f"data:image/svg+xml;utf8,{encoded}"


_ICON_PIPELINE = ImageRankingPipeline(
    retrievers=[WikipediaRetriever(), WikimediaRetriever(), ArticleImageRetriever()],
    ranker=HeuristicImageRanker(),
    cache=SimpleTTLCache(default_ttl_s=3600.0),
)


def build_keyword_importance(issue: dict[str, Any]) -> dict[str, float]:
    """
    Try to derive keyword importance.
    - If issue['keywords'] is list[str], compute frequency across pressData keywords.
    - If issue['keywords'] is list[dict], use provided importance.
    """
    kws = issue.get("keywords") or []
    press_data = issue.get("pressData") or []

    # If dict keywords exist
    if kws and isinstance(kws, list) and isinstance(kws[0], dict):
        out = {}
        for k in kws:
            kw = (k or {}).get("keyword") or (k or {}).get("text") or ""
            imp = (k or {}).get("importance", (k or {}).get("score", 1.0))
            if kw:
                out[str(kw)] = _safe_float(imp, 1.0)
        return out

    # Otherwise strings
    out: dict[str, float] = {}
    counts: dict[str, int] = {}
    total = 0
    for p in press_data:
        ks = (p or {}).get("keywords") or []
        if not isinstance(ks, list):
            continue
        for kw in ks:
            if not kw:
                continue
            k = str(kw)
            counts[k] = counts.get(k, 0) + 1
            total += 1
    for kw in kws:
        if not kw:
            continue
        k = str(kw)
        counts.setdefault(k, 0)
    if total <= 0:
        # fallback uniform
        for kw in kws:
            if kw:
                out[str(kw)] = 1.0
        return out

    for k, c in counts.items():
        out[k] = c / total
    return out


def build_image_graph_payload(issue: dict[str, Any]) -> dict[str, Any]:
    """
    Return a keyword-only undirected graph payload with icon urls and relation labels.
    """
    issueid = str(issue.get("issueId") or issue.get("issueid") or "issue")
    title = str(issue.get("title") or "")
    summary = str(issue.get("summary") or "")
    issue_text = " ".join([title, summary]).strip()

    keywords: list[str] = [str(k) for k in (issue.get("keywords") or []) if k]
    # Baseline importance (freq + TF-IDF) in 0..1
    baseline_map = compute_baseline_importance([issue])[0] if keywords else {}
    # Fallback if baseline couldn't score (e.g., missing text)
    if not baseline_map:
        baseline_map = build_keyword_importance(issue)

    importance_map = dict(baseline_map)

    # If a trained graph-quality model exists, adjust importance using graph_score.
    # importance(k) = alpha * baseline(k) + beta * graph_score
    try:
        artifact = load_graph_quality_model("backend/data/graph_quality_model.joblib")
        graph_score = graph_score_from_issue(issue, model_artifact=artifact, baseline_importance=baseline_map)
        # Global trust in model based on its offline validation AUROC.
        metrics = load_graph_quality_metrics("backend/data/graph_quality_model.joblib.metrics.json") or {}
        auroc = metrics.get("cv_auroc_mean")
        w_global = blending_weight_from_auroc(auroc)

        # Per-issue adaptive beta based on baseline quality (spread).
        alpha_local, beta_local, mix_debug = adaptive_mix_weights(baseline_map)
        # Final beta combines both: if model is weak globally, beta shrinks toward 0.
        beta = float(beta_local) * float(w_global)
        alpha = float(1.0 - beta)
        for kw in list(importance_map.keys()):
            importance_map[kw] = alpha * float(importance_map.get(kw, 0.0)) + beta * float(graph_score)
        # renormalize to 0..1
        vals = list(importance_map.values())
        if vals:
            vmin, vmax = min(vals), max(vals)
            if vmax == vmin:
                importance_map = {k: 0.5 for k in importance_map}
            else:
                importance_map = {k: (v - vmin) / (vmax - vmin) for k, v in importance_map.items()}
    except Exception:
        graph_score = None
        alpha = None
        beta = None
        mix_debug = None
        metrics = None
        auroc = None
        w_global = None

    # Build issue context for relevance ranking
    issue_ctx = IssueContext(
        issue_id=issueid,
        title=title,
        summary=summary,
        text=issue_text,
        entities=[str(x) for x in (issue.get("keywords") or []) if x],  # lightweight placeholder
        keywords=keywords,
    )

    async def _select_all() -> dict[str, Any]:
        tasks = [
            _ICON_PIPELINE.select_icon(kw, issue_ctx, fallback_factory=lambda x: _svg_fallback_avatar(x))
            for kw in keywords
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, Any] = {}
        for kw, res in zip(keywords, results):
            if isinstance(res, Exception):
                out[kw] = {
                    "icon_url": _svg_fallback_avatar(kw),
                    "meta": {
                        "selected": False,
                        "score": 0.0,
                        "source": "fallback",
                        "reason": f"exception:{type(res).__name__}",
                        "fallback": True,
                        "candidatesCount": 0,
                    },
                }
            else:
                out[kw] = {
                    "icon_url": res.icon_url,
                    "meta": {
                        "selected": bool(res.selected),
                        "score": float(res.score),
                        "source": str(res.source),
                        "reason": str(res.reason),
                        "fallback": bool(res.fallback),
                        "candidatesCount": int(res.candidates_count),
                    },
                }
        return out

    try:
        kw_icon_map = asyncio.run(_select_all())
    except RuntimeError:
        # If an event loop already exists (rare here), fall back to sequential sync.
        kw_icon_map = {}
        for kw in keywords:
            kw_icon_map[kw] = {
                "icon_url": _svg_fallback_avatar(kw),
                "meta": {
                    "selected": False,
                    "score": 0.0,
                    "source": "fallback",
                    "reason": "event_loop_running",
                    "fallback": True,
                    "candidatesCount": 0,
                },
            }

    # nodes
    nodes = []
    for kw in keywords:
        imp = importance_map.get(kw, 0.0)
        icon = (kw_icon_map.get(kw) or {}).get("icon_url") or _svg_fallback_avatar(kw)
        icon_meta = (kw_icon_map.get(kw) or {}).get("meta") or None
        nodes.append(
            {
                "id": f"kw:{kw}",
                "type": "keyword",
                "label": kw,
                "importance": float(imp),
                "iconUrl": icon,
                "iconMeta": icon_meta,
            }
        )

    # edges via press co-occurrence
    press_data = issue.get("pressData") or []
    press_to_kws: dict[str, list[str]] = {}
    for p in press_data:
        press = (p or {}).get("press") or ""
        ks = (p or {}).get("keywords") or []
        if not press or not isinstance(ks, list):
            continue
        press_to_kws[str(press)] = [str(x) for x in ks if x]

    pair_w: dict[tuple[str, str], int] = {}
    for _, ks in press_to_kws.items():
        uniq = list(dict.fromkeys([k for k in ks if k in importance_map]))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                key = (a, b) if a < b else (b, a)
                pair_w[key] = pair_w.get(key, 0) + 1

    weights = list(pair_w.values())
    wmin = min(weights) if weights else 0
    wmax = max(weights) if weights else 0

    edges = []
    for (a, b), w in pair_w.items():
        if wmax == wmin:
            wn = 0.5 if weights else 0.0
        else:
            wn = (w - wmin) / (wmax - wmin)
        if wn < 0.15:
            continue
        edges.append(
            {
                "source": f"kw:{a}",
                "target": f"kw:{b}",
                "weight": float(w),
                "weightNorm": float(wn),
                "relation": "co_occurs",
            }
        )

    # pruning: drop isolated nodes
    deg: dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1
    nodes = [n for n in nodes if deg.get(n["id"], 0) > 0]

    # size scaling (importance -> radius-ish size)
    imps = [float(n.get("importance", 0.0)) for n in nodes]
    imin = min(imps) if imps else 0.0
    imax = max(imps) if imps else 0.0
    for n in nodes:
        imp = float(n.get("importance", 0.0))
        if imax == imin:
            s = 70.0
        else:
            t = (imp - imin) / (imax - imin)
            s = 20.0 + t * (120.0 - 20.0)
        n["size"] = float(s)

    return {
        "issueId": issueid,
        "issueText": issue_text,
        "graphScore": graph_score,
        "mixing": {
            "alpha": alpha,
            "beta": beta,
            "baselineQuality": mix_debug,
            "modelAuroc": auroc,
            "modelTrustW": w_global,
        },
        "imageRanking": {"pipeline": "relevance_ranking", "note": "see node.iconMeta for selection details"},
        "graph": {"nodes": nodes, "edges": edges},
    }

