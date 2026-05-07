from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph


@dataclass(frozen=True)
class WeightedGraphBuildConfig:
    """
    Configuration for weighted undirected graph construction.
    """

    # pruning
    keyword_importance_threshold: float = 0.15
    min_degree_non_issue: int = 1

    # node size scaling
    keyword_size_min: float = 20.0
    keyword_size_max: float = 120.0
    issue_size: float = 160.0
    press_size_min: float = 35.0
    press_size_max: float = 90.0

    # press size components (before min/max mapping)
    press_size_article_weight: float = 1.0
    press_size_keyword_weight: float = 1.0

    # edge weight normalization
    normalize_edge_weights: bool = True


def _safe_norm(values: list[float]) -> list[float]:
    """
    Normalize to [0, 1]. If max == min, return 0.5 for non-empty lists.
    """
    if not values:
        return []
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    if vmax == vmin:
        return [0.5 for _ in values]
    return [float((v - vmin) / (vmax - vmin)) for v in values]


def _map_range(norm01: float, out_min: float, out_max: float) -> float:
    return float(out_min + (out_max - out_min) * float(norm01))


def _iterative_prune(G: nx.Graph, *, min_degree_non_issue: int) -> None:
    """
    Remove non-issue nodes whose degree is below threshold. Repeat until stable.
    """
    if min_degree_non_issue <= 0:
        return
    changed = True
    while changed:
        changed = False
        to_drop = []
        for n, deg in G.degree():
            if G.nodes[n].get("kind") == "issue":
                continue
            if deg < min_degree_non_issue:
                to_drop.append(n)
        if to_drop:
            G.remove_nodes_from(to_drop)
            changed = True


def build_weighted_graph(
    issue_data: dict[str, Any],
    *,
    config: WeightedGraphBuildConfig | None = None,
) -> Tuple[nx.Graph, Dict[str, Any]]:
    """
    Build an undirected weighted graph for a single issue.

    Nodes:
    - issue node: size = #articles
    - keyword nodes: size = normalized importance * scale
    - press nodes: size = (#articles_by_press * w1) + (#connected_keywords * w2)

    Edges (with 'weight'):
    - issue -- keyword: keyword importance
    - press -- keyword: (keyword occurrence in press articles) / (total keyword occurrences)
    - press -- issue: #articles_by_press

    Noise handling:
    - remove keywords with importance < threshold
    - remove degree-0 nodes after edge creation
    - normalization exception max=min -> 0.5

    Returns:
    - (G, export_json) where export_json is NetworkX node-link data.
    """
    cfg = config or WeightedGraphBuildConfig()

    issueid = str(issue_data.get("issueid") or issue_data.get("issueId") or issue_data.get("issue_id") or "issue")
    articles = issue_data.get("articles") or []
    keywords = issue_data.get("keywords") or []

    # Normalize keyword list
    kw_list: list[tuple[str, float]] = []
    for k in keywords:
        if isinstance(k, dict):
            kw = k.get("keyword") or k.get("text") or k.get("name")
            imp = k.get("importance", k.get("score", 1.0))
            if kw is None:
                continue
            try:
                imp_f = float(imp)
            except Exception:
                imp_f = 1.0
            if imp_f < cfg.keyword_importance_threshold:
                continue
            kw_list.append((str(kw), imp_f))
        elif isinstance(k, str):
            kw_list.append((k, 1.0))

    # Build graph
    G = nx.Graph()

    issue_node = f"issue:{issueid}"
    G.add_node(issue_node, kind="issue", label=issueid, size=float(cfg.issue_size), articleCount=int(len(articles)))

    # Keyword nodes with normalized importance
    kw_imps = [imp for _, imp in kw_list]
    kw_norm = _safe_norm(kw_imps)
    for (kw, imp), nrm in zip(kw_list, kw_norm):
        node = f"kw:{kw}"
        G.add_node(
            node,
            kind="keyword",
            label=kw,
            importance=float(imp),
            size=_map_range(float(nrm), cfg.keyword_size_min, cfg.keyword_size_max),
        )
        G.add_edge(issue_node, node, weight=float(imp), kind="issue-keyword")

    # Press stats and press-keyword co-occurrence
    press_articles: dict[str, list[dict[str, Any]]] = {}
    for a in articles:
        if not isinstance(a, dict):
            continue
        press = a.get("publisher") or a.get("press") or a.get("source") or ""
        press = str(press).strip() if press is not None else ""
        if not press:
            press = "unknown"
        press_articles.setdefault(press, []).append(a)

    # Count keyword mentions per press based on raw text / sentences / title.
    total_kw_hits: dict[str, int] = {kw: 0 for kw, _ in kw_list}
    press_kw_hits: dict[tuple[str, str], int] = {}

    def _text_blob(a: dict[str, Any]) -> str:
        parts = []
        for key in ("title", "rawtext", "content"):
            v = a.get(key)
            if isinstance(v, str) and v:
                parts.append(v)
        sent = a.get("sentences")
        if isinstance(sent, list):
            parts.extend([s for s in sent if isinstance(s, str)])
        return " ".join(parts)

    for press, plist in press_articles.items():
        for a in plist:
            blob = _text_blob(a)
            for kw, _ in kw_list:
                if not kw:
                    continue
                # naive count: substring hits
                hits = blob.count(kw)
                if hits <= 0:
                    continue
                total_kw_hits[kw] += hits
                press_kw_hits[(press, kw)] = press_kw_hits.get((press, kw), 0) + hits

    # Add press nodes and edges
    press_raw_sizes: list[float] = []
    press_nodes: list[str] = []
    for press, plist in press_articles.items():
        press_node = f"press:{press}"
        num_articles = len(plist)

        # connected keywords
        connected = 0
        for kw, _ in kw_list:
            if press_kw_hits.get((press, kw), 0) > 0:
                connected += 1

        size = float(num_articles) * cfg.press_size_article_weight + float(connected) * cfg.press_size_keyword_weight
        press_raw_sizes.append(size)
        press_nodes.append(press_node)
        G.add_node(press_node, kind="press", label=press, size=size, articleCount=num_articles, keywordCount=connected)

        # press-issue edge
        G.add_edge(press_node, issue_node, weight=float(num_articles), kind="press-issue")

        # press-keyword edges
        for kw, _ in kw_list:
            hits = press_kw_hits.get((press, kw), 0)
            denom = total_kw_hits.get(kw, 0)
            if hits <= 0 or denom <= 0:
                continue
            w = float(hits) / float(denom)
            G.add_edge(press_node, f"kw:{kw}", weight=w, kind="press-keyword")

    # Map press node sizes to a bounded range for visualization
    if press_nodes:
        press_norm = _safe_norm(press_raw_sizes)
        for pn, nrm in zip(press_nodes, press_norm):
            if pn in G.nodes:
                G.nodes[pn]["size"] = _map_range(float(nrm), cfg.press_size_min, cfg.press_size_max)

    # Optional edge weight normalization (per kind)
    if cfg.normalize_edge_weights and G.number_of_edges() > 0:
        by_kind: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
        for u, v, d in G.edges(data=True):
            k = str(d.get("kind", ""))
            by_kind.setdefault(k, []).append((u, v, d))
        for k, edges in by_kind.items():
            ws = [float(d.get("weight", 1.0)) for _, _, d in edges]
            nrm = _safe_norm(ws)
            for (u, v, d), w01 in zip(edges, nrm):
                d["weight_norm"] = float(w01)

    # Remove isolated nodes (degree 0) and apply degree-based pruning
    isolates = [n for n, d in G.degree() if d == 0]
    if isolates:
        G.remove_nodes_from(isolates)

    _iterative_prune(G, min_degree_non_issue=cfg.min_degree_non_issue)

    export = json_graph.node_link_data(G)
    return G, export

