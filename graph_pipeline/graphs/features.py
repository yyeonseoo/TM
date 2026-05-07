from __future__ import annotations

from typing import Any, Dict, Iterable

import networkx as nx
import numpy as np


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return float(default)
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return float(default)
        return v
    except Exception:
        return float(default)


def _avg(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(np.mean(vals))


def _var(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(np.var(vals))


def _avg_shortest_path_by_component(G: nx.Graph) -> float:
    if G.number_of_nodes() <= 1:
        return 0.0
    comps = [G.subgraph(c).copy() for c in nx.connected_components(G)] if not G.is_directed() else []
    if not comps:
        return 0.0
    vals = []
    for H in comps:
        if H.number_of_nodes() <= 1:
            continue
        try:
            vals.append(nx.average_shortest_path_length(H))
        except Exception:
            continue
    return _avg(vals)


def _community_stats(G: nx.Graph) -> tuple[int, float, float]:
    """
    Louvain if available in NetworkX, else greedy modularity as fallback.
    Returns (community_count, mean_size, var_size).
    """
    if G.number_of_nodes() == 0:
        return 0, 0.0, 0.0
    try:
        # networkx >= 2.8: louvain_communities
        communities = nx.algorithms.community.louvain_communities(G, weight="weight", seed=42)
    except Exception:
        try:
            communities = nx.algorithms.community.greedy_modularity_communities(G, weight="weight")
        except Exception:
            communities = [set(G.nodes())]
    sizes = [len(c) for c in communities]
    return len(communities), _avg(sizes), _var(sizes)


def extract_graph_features(G: nx.Graph, *, issue_data: dict[str, Any] | None = None) -> Dict[str, float]:
    """
    Extract a 1D feature vector from a graph.

    Features:
    - structural: nodes, edges, density, clustering, assortativity, avg shortest path (per component)
    - centrality: avg degree centrality, avg betweenness, avg pagerank
    - community: count, size mean/var (Louvain preferred)
    - semantic: keyword importance mean/std (from issue_data['keywords'] if provided)
    """
    n = G.number_of_nodes()
    m = G.number_of_edges()

    density = nx.density(G) if n > 1 else 0.0
    try:
        clustering = nx.average_clustering(G, weight="weight") if n > 1 else 0.0
    except Exception:
        clustering = 0.0

    try:
        assort = nx.degree_assortativity_coefficient(G) if n > 2 else 0.0
        assort = _safe_float(assort, 0.0)
    except Exception:
        assort = 0.0

    asp = _avg_shortest_path_by_component(G) if n > 1 else 0.0

    # centralities
    try:
        degc = nx.degree_centrality(G) if n > 1 else {}
    except Exception:
        degc = {}
    try:
        betw = nx.betweenness_centrality(G, normalized=True, weight="weight") if n > 2 else {}
    except Exception:
        betw = {}
    try:
        pr = nx.pagerank(G, weight="weight") if n > 0 else {}
    except Exception:
        pr = {}

    comm_count, comm_mean, comm_var = _community_stats(G) if n > 0 else (0, 0.0, 0.0)

    kw_mean = 0.0
    kw_std = 0.0
    if issue_data is not None:
        kws = issue_data.get("keywords") or []
        imps = []
        for k in kws:
            if isinstance(k, dict):
                v = k.get("importance", k.get("score", None))
                if v is None:
                    continue
                imps.append(_safe_float(v, 0.0))
        if imps:
            kw_mean = float(np.mean(imps))
            kw_std = float(np.std(imps))

    return {
        "num_nodes": float(n),
        "num_edges": float(m),
        "graph_density": float(density),
        "clustering_coefficient": float(clustering),
        "assortativity": float(assort),
        "avg_shortest_path": float(asp),
        "avg_degree_centrality": float(_avg(degc.values())),
        "avg_betweenness": float(_avg(betw.values())),
        "avg_pagerank": float(_avg(pr.values())),
        "community_count": float(comm_count),
        "community_size_mean": float(comm_mean),
        "community_size_var": float(comm_var),
        "keyword_importance_mean": float(kw_mean),
        "keyword_importance_std": float(kw_std),
    }

