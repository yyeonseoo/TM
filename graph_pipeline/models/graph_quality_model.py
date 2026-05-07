from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import joblib  # type: ignore
import networkx as nx
import numpy as np
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from graph_pipeline.evaluation.self_supervised import (
    corrupt_edge_shuffle,
    corrupt_noise_addition,
    corrupt_random_graph_like,
)
from graph_pipeline.graphs.features import extract_graph_features


@dataclass(frozen=True)
class GraphQualityModelConfig:
    """
    Train a self-supervised graph-quality classifier: original vs corrupted.
    """

    random_state: int = 42
    noise_edge_add_ratio: float = 0.05
    n_estimators: int = 400
    max_depth: int = 6
    learning_rate: float = 0.05
    n_splits: int = 5


def _as_matrix(feature_dicts: List[Dict[str, float]]) -> tuple[np.ndarray, list[str]]:
    keys = sorted({k for d in feature_dicts for k in d.keys()})
    X = np.array([[float(d.get(k, 0.0)) for k in keys] for d in feature_dicts], dtype=float)
    return X, keys


def _make_xgb_classifier(cfg: GraphQualityModelConfig):
    from xgboost import XGBClassifier  # type: ignore

    return XGBClassifier(
        n_estimators=cfg.n_estimators,
        max_depth=cfg.max_depth,
        learning_rate=cfg.learning_rate,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=cfg.random_state,
        eval_metric="logloss",
    )


def build_keyword_cooccurrence_graph(issue: dict[str, Any], importance_map: dict[str, float]) -> nx.Graph:
    """
    Build a keyword-only undirected co-occurrence graph from API issue format.

    Nodes: kw:<keyword> with attribute 'importance'
    Edges: kw-kw weighted by shared press count.
    """
    kws = [str(k) for k in (issue.get("keywords") or []) if k]
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

    G = nx.Graph()
    for kw in kws:
        G.add_node(f"kw:{kw}", kind="keyword", label=kw, importance=float(importance_map.get(kw, 0.0)))
    for (a, b), w in pair_w.items():
        G.add_edge(f"kw:{a}", f"kw:{b}", weight=float(w), relation="co_occurs")

    # drop isolates
    isolates = [n for n, d in G.degree() if d == 0]
    if isolates:
        G.remove_nodes_from(isolates)
    return G


def compute_baseline_importance(issues: list[dict[str, Any]]) -> list[dict[str, float]]:
    """
    Baseline importance per issue using TF-IDF + press keyword frequency.

    Returns list aligned with issues: {keyword: importance01}
    """
    # Build texts for TF-IDF
    texts: list[str] = []
    issue_keywords: list[list[str]] = []
    freq_maps: list[dict[str, float]] = []
    for issue in issues:
        title = str(issue.get("title") or "")
        summary = str(issue.get("summary") or "")
        evidence = issue.get("evidenceSentences") or []
        ev_text = " ".join([s for s in evidence if isinstance(s, str)])[:4000]
        texts.append(" ".join([title, summary, ev_text]).strip())

        kws = [str(k) for k in (issue.get("keywords") or []) if k]
        issue_keywords.append(kws)

        # press keyword frequency
        press_data = issue.get("pressData") or []
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
        freq = {k: (c / total) for k, c in counts.items()} if total > 0 else {}
        freq_maps.append(freq)

    vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2))
    X = vec.fit_transform(texts) if texts else None
    vocab = vec.vocabulary_ or {}
    id2term = {i: t for t, i in vocab.items()}

    out: list[dict[str, float]] = []
    for idx, kws in enumerate(issue_keywords):
        scores: dict[str, float] = {}
        # TF-IDF score for keyword = sum tfidf of matching terms (best-effort substring)
        tfidf_map: dict[str, float] = {}
        if X is not None:
            row = X[idx]
            # sparse row indices / data
            inds = row.indices
            data = row.data
            for i, v in zip(inds, data):
                term = id2term.get(int(i))
                if term:
                    tfidf_map[term] = float(v)

        freq = freq_maps[idx]
        raw_vals: list[float] = []
        for kw in kws:
            tf = 0.0
            k_low = kw.lower()
            for term, v in tfidf_map.items():
                if k_low in term.lower() or term.lower() in k_low:
                    tf = max(tf, v)
            f = float(freq.get(kw, 0.0))
            s = 0.65 * tf + 0.35 * f
            scores[kw] = float(s)
            raw_vals.append(float(s))

        # normalize to 0..1
        if raw_vals:
            vmin = min(raw_vals)
            vmax = max(raw_vals)
            if vmax == vmin:
                scores = {k: 0.5 for k in scores}
            else:
                scores = {k: (v - vmin) / (vmax - vmin) for k, v in scores.items()}

        out.append(scores)
    return out


def train_graph_quality_model(
    issues: list[dict[str, Any]],
    *,
    cfg: GraphQualityModelConfig | None = None,
    return_metrics: bool = False,
) -> dict[str, Any]:
    """
    Train XGBoost classifier to discriminate original vs corrupted graphs.

    Returns artifact dict containing model + feature_names.
    If return_metrics=True, includes 'metrics' computed via StratifiedKFold CV.
    """
    cfg = cfg or GraphQualityModelConfig()

    baselines = compute_baseline_importance(issues)

    feats: list[dict[str, float]] = []
    y: list[int] = []
    for issue, imp_map in zip(issues, baselines):
        G = build_keyword_cooccurrence_graph(issue, imp_map)
        if G.number_of_nodes() < 3 or G.number_of_edges() < 2:
            continue
        feats.append(extract_graph_features(G))
        y.append(1)

        # corruptions
        import random

        rr = random.Random(cfg.random_state)
        feats.append(extract_graph_features(corrupt_edge_shuffle(G, rng=rr)))
        y.append(0)
        feats.append(extract_graph_features(corrupt_noise_addition(G, rng=rr, add_ratio=cfg.noise_edge_add_ratio)))
        y.append(0)
        feats.append(extract_graph_features(corrupt_random_graph_like(G, rng=rr)))
        y.append(0)

    if not feats:
        raise ValueError("Not enough graphs to train.")

    X, feature_names = _as_matrix(feats)
    y_arr = np.array(y, dtype=int)

    model = _make_xgb_classifier(cfg)
    metrics: dict[str, Any] | None = None
    if return_metrics:
        # CV metrics (handle tiny datasets)
        n_pos = int(np.sum(y_arr == 1))
        n_neg = int(np.sum(y_arr == 0))
        n_splits = min(cfg.n_splits, n_pos, n_neg, len(y_arr))
        n_splits = max(2, n_splits) if len(y_arr) >= 4 else 2
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=cfg.random_state)
        aucs: list[float] = []
        f1s: list[float] = []
        for tr, te in skf.split(X, y_arr):
            m = _make_xgb_classifier(cfg)
            m.fit(X[tr], y_arr[tr])
            pred = m.predict(X[te])
            f1s.append(float(f1_score(y_arr[te], pred)))
            try:
                proba = m.predict_proba(X[te])[:, 1]
                auc = float(roc_auc_score(y_arr[te], proba))
                if not (np.isnan(auc) or np.isinf(auc)):
                    aucs.append(auc)
            except Exception:
                pass
        metrics = {
            "cv_auroc_mean": float(np.mean(aucs)) if aucs else None,
            "cv_f1_mean": float(np.mean(f1s)) if f1s else 0.0,
            "cv_n_splits": int(n_splits),
            "num_samples": int(len(y_arr)),
            "num_pos": int(n_pos),
            "num_neg": int(n_neg),
        }

    model.fit(X, y_arr)

    artifact: dict[str, Any] = {"model": model, "feature_names": feature_names, "config": cfg.__dict__}
    if metrics is not None:
        artifact["metrics"] = metrics
    return artifact


def baseline_quality_for_adaptive_mix(baseline_importance: dict[str, float], *, eps: float = 1e-9) -> dict[str, float]:
    """
    Compute simple baseline quality signals used for adaptive mixing.

    Heuristic:
    - If baseline importance is nearly uniform (low std / low range), it's "weak/noisy".
    - If it has clear spread, it's "strong".
    Returns dict with:
    - spread01: 0..1 (higher => stronger baseline)
    """
    vals = [float(v) for v in baseline_importance.values() if v is not None]
    if len(vals) < 2:
        return {"spread01": 0.0}
    vmin, vmax = min(vals), max(vals)
    rng = max(eps, vmax - vmin)
    std = float(np.std(vals))
    # normalize std by range, cap to [0,1]
    spread = std / rng
    spread01 = float(min(1.0, max(0.0, spread / 0.35)))  # 0.35 ~ "decent" spread
    return {"spread01": spread01}


def adaptive_mix_weights(
    baseline_importance: dict[str, float],
    *,
    beta_min: float = 0.15,
    beta_max: float = 0.55,
) -> tuple[float, float, dict[str, float]]:
    """
    Choose (alpha, beta) for importance mixing:
      importance = alpha * baseline + beta * graphScore

    - When baseline spread is weak => increase beta (trust model more).
    - When baseline spread is strong => decrease beta.
    """
    q = baseline_quality_for_adaptive_mix(baseline_importance)
    spread01 = float(q.get("spread01", 0.0))
    beta = float(beta_max - (beta_max - beta_min) * spread01)
    beta = float(min(beta_max, max(beta_min, beta)))
    alpha = float(1.0 - beta)
    return alpha, beta, q


def blending_weight_from_auroc(auroc: float | None, *, steepness: float = 12.0) -> float:
    """
    Map AUROC to blending weight w in [0,1].

    - AUROC <= 0.5 => ~0 (ignore model)
    - AUROC high => close to 1 (trust model)
    """
    if auroc is None:
        return 0.0
    a = float(auroc)
    if not (0.0 <= a <= 1.0):
        return 0.0
    # center at 0.5; clamp low side to 0
    x = max(0.0, a - 0.5)
    # sigmoid-ish, but anchored so x=0 => 0.0
    # w = 1 - exp(-k*x) gives a smooth rise from 0
    w = 1.0 - math.exp(-steepness * x)
    return float(min(1.0, max(0.0, w)))


def load_graph_quality_metrics(metrics_path: str | Path) -> dict[str, Any] | None:
    """
    Load metrics JSON written by train_graph_quality_model.py.
    Returns None if missing/unreadable.
    """
    p = Path(metrics_path)
    if not p.exists():
        return None
    try:
        import json

        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def save_graph_quality_model(artifact: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, p)


def load_graph_quality_model(path: str | Path) -> dict[str, Any]:
    return joblib.load(Path(path))


def graph_score_from_issue(
    issue: dict[str, Any],
    *,
    model_artifact: dict[str, Any],
    baseline_importance: dict[str, float],
) -> float:
    """
    Compute graph quality score in [0,1] using trained artifact.
    """
    model = model_artifact["model"]
    feature_names: list[str] = model_artifact["feature_names"]
    G = build_keyword_cooccurrence_graph(issue, baseline_importance)
    f = extract_graph_features(G)
    X = np.array([[float(f.get(k, 0.0)) for k in feature_names]], dtype=float)
    proba = model.predict_proba(X)[0, 1]
    return float(proba)

