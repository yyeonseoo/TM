from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import networkx as nx
import numpy as np
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold


@dataclass(frozen=True)
class SelfSupervisedEvalConfig:
    """
    Configuration for self-supervised evaluation:
    original vs corrupted graph discrimination.
    """

    random_state: int = 42
    n_splits: int = 5
    noise_edge_add_ratio: float = 0.05


def corrupt_edge_shuffle(G: nx.Graph, *, rng: random.Random) -> nx.Graph:
    """Shuffle endpoints of edges while keeping edge count."""
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    nodes = list(H.nodes())
    m = G.number_of_edges()
    # sample random pairs
    for _ in range(m):
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u == v:
            continue
        H.add_edge(u, v, weight=1.0, kind="corrupt-shuffle")
    return H


def corrupt_noise_addition(G: nx.Graph, *, rng: random.Random, add_ratio: float) -> nx.Graph:
    """Add random noise edges on top of original."""
    H = G.copy()
    nodes = list(H.nodes())
    add_m = max(1, int(G.number_of_edges() * add_ratio)) if G.number_of_edges() > 0 else max(1, int(len(nodes) * add_ratio))
    for _ in range(add_m):
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if u == v:
            continue
        if H.has_edge(u, v):
            continue
        H.add_edge(u, v, weight=1.0, kind="corrupt-noise")
    return H


def corrupt_random_graph_like(G: nx.Graph, *, rng: random.Random) -> nx.Graph:
    """Generate random graph with same #nodes and #edges (Erdos-Renyi)."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    if n <= 1:
        return G.copy()
    p = min(1.0, (2.0 * m) / (n * (n - 1))) if n > 1 else 0.0
    H = nx.erdos_renyi_graph(n=n, p=p, seed=rng.randint(0, 10_000))
    # relabel nodes to match original node ids (preserve attributes loosely)
    mapping = {i: node for i, node in enumerate(G.nodes())}
    H = nx.relabel_nodes(H, mapping)
    for node, attrs in G.nodes(data=True):
        if node in H:
            H.nodes[node].update(attrs)
    for u, v in H.edges():
        H.edges[u, v]["weight"] = 1.0
        H.edges[u, v]["kind"] = "corrupt-random"
    return H


def _as_matrix(feature_dicts: List[Dict[str, float]]) -> tuple[np.ndarray, list[str]]:
    keys = sorted({k for d in feature_dicts for k in d.keys()})
    X = np.array([[float(d.get(k, 0.0)) for k in keys] for d in feature_dicts], dtype=float)
    return X, keys


def _try_make_binary_model():
    """Prefer XGBoost, else LogisticRegression."""
    try:
        from xgboost import XGBClassifier  # type: ignore

        return "xgboost", XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
            eval_metric="logloss",
        )
    except Exception:
        from sklearn.linear_model import LogisticRegression

        return "logreg", LogisticRegression(max_iter=5000)


def evaluate_graphs_self_supervised(
    graphs: List[nx.Graph],
    feature_fn,
    *,
    config: SelfSupervisedEvalConfig | None = None,
) -> Dict[str, Any]:
    """
    Self-supervised evaluation: discriminate original graphs vs corrupted versions.

    Corruptions:
    - edge shuffle
    - noise edge addition
    - random graph with same node/edge counts

    Returns:
    - {'selfsupervisedauroc': ..., 'selfsupervisedf1': ..., 'model': ...}
    """
    cfg = config or SelfSupervisedEvalConfig()
    rng = random.Random(cfg.random_state)

    all_graphs: list[nx.Graph] = []
    y: list[int] = []

    for G in graphs:
        all_graphs.append(G)
        y.append(1)
        all_graphs.append(corrupt_edge_shuffle(G, rng=rng))
        y.append(0)
        all_graphs.append(corrupt_noise_addition(G, rng=rng, add_ratio=cfg.noise_edge_add_ratio))
        y.append(0)
        all_graphs.append(corrupt_random_graph_like(G, rng=rng))
        y.append(0)

    feats = [feature_fn(g) for g in all_graphs]
    X, _ = _as_matrix(feats)
    y_arr = np.array(y, dtype=int)

    model_name, model = _try_make_binary_model()

    # If dataset is tiny, CV can produce single-class folds; handle gracefully.
    n_splits = min(cfg.n_splits, int(np.sum(y_arr == 1)), int(np.sum(y_arr == 0)))
    n_splits = max(2, n_splits) if len(y_arr) >= 4 else 2
    skf = StratifiedKFold(n_splits=min(n_splits, len(y_arr)), shuffle=True, random_state=cfg.random_state)
    aucs = []
    f1s = []
    for tr, te in skf.split(X, y_arr):
        Xtr, Xte = X[tr], X[te]
        ytr, yte = y_arr[tr], y_arr[te]
        model.fit(Xtr, ytr)
        pred = model.predict(Xte)
        f1s.append(f1_score(yte, pred))
        try:
            proba = model.predict_proba(Xte)[:, 1]
            auc = float(roc_auc_score(yte, proba))
            if not (np.isnan(auc) or np.isinf(auc)):
                aucs.append(auc)
        except Exception:
            pass

    return {
        "model": model_name,
        "selfsupervisedauroc": float(np.mean(aucs)) if aucs else None,
        "selfsupervisedf1": float(np.mean(f1s)) if f1s else 0.0,
    }

