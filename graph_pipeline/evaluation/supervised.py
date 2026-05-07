from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder


@dataclass(frozen=True)
class SupervisedEvalConfig:
    """
    Configuration for supervised evaluation.
    """

    n_splits: int = 5
    random_state: int = 42


def _try_make_models() -> list[tuple[str, Any]]:
    """
    Return at least two classifiers.

    Preference order:
    - xgboost.XGBClassifier (if available)
    - lightgbm.LGBMClassifier (if available)
    - sklearn LogisticRegression (always available)
    """
    models: list[tuple[str, Any]] = []

    try:
        from xgboost import XGBClassifier  # type: ignore

        models.append(
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=300,
                    max_depth=6,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    reg_lambda=1.0,
                    random_state=42,
                    eval_metric="logloss",
                ),
            )
        )
    except Exception:
        pass

    try:
        from lightgbm import LGBMClassifier  # type: ignore

        models.append(
            (
                "lightgbm",
                LGBMClassifier(
                    n_estimators=500,
                    learning_rate=0.05,
                    num_leaves=31,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    random_state=42,
                ),
            )
        )
    except Exception:
        pass

    from sklearn.linear_model import LogisticRegression

    models.append(("logreg", LogisticRegression(max_iter=5000, n_jobs=None)))

    # Ensure we have at least two.
    if len(models) == 1:
        from sklearn.ensemble import RandomForestClassifier

        models.append(("rf", RandomForestClassifier(n_estimators=400, random_state=42)))

    # If we have 3, keep top 2 per prompt (2 models).
    if len(models) > 2:
        return models[:2]
    return models


def _as_matrix(feature_dicts: List[Dict[str, float]]) -> tuple[np.ndarray, list[str]]:
    keys = sorted({k for d in feature_dicts for k in d.keys()})
    X = np.array([[float(d.get(k, 0.0)) for k in keys] for d in feature_dicts], dtype=float)
    return X, keys


def evaluate_graphs_supervised(
    feature_dicts: List[Dict[str, float]],
    labels: List[str],
    *,
    config: SupervisedEvalConfig | None = None,
) -> List[Dict[str, Any]]:
    """
    Train/evaluate 2 classifiers on graph feature vectors.

    Metrics:
    - macro-F1
    - accuracy
    - AUROC (one-vs-rest; only if >=2 classes and probability available)

    Returns list of model reports (one per model).
    """
    cfg = config or SupervisedEvalConfig()
    X, feature_names = _as_matrix(feature_dicts)

    le = LabelEncoder()
    y = le.fit_transform(labels)
    classes = list(le.classes_)

    skf = StratifiedKFold(n_splits=min(cfg.n_splits, len(labels)), shuffle=True, random_state=cfg.random_state)

    reports: list[dict[str, Any]] = []
    for model_name, model in _try_make_models():
        f1s = []
        accs = []
        aucs = []

        for train_idx, test_idx in skf.split(X, y):
            Xtr, Xte = X[train_idx], X[test_idx]
            ytr, yte = y[train_idx], y[test_idx]

            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            f1s.append(f1_score(yte, pred, average="macro"))
            accs.append(accuracy_score(yte, pred))

            # AUROC (multiclass OVR) if predict_proba exists
            try:
                proba = model.predict_proba(Xte)
                auc = roc_auc_score(yte, proba, multi_class="ovr")
                aucs.append(float(auc))
            except Exception:
                pass

        report: dict[str, Any] = {
            "model": model_name,
            "f1": float(np.mean(f1s)) if f1s else 0.0,
            "accuracy": float(np.mean(accs)) if accs else 0.0,
            "auroc": float(np.mean(aucs)) if aucs else None,
            "classes": classes,
        }

        # feature importance if available (fit on full data)
        try:
            model.fit(X, y)
            importances = None
            if hasattr(model, "feature_importances_"):
                importances = getattr(model, "feature_importances_")
            elif hasattr(model, "coef_"):
                coef = getattr(model, "coef_")
                importances = np.mean(np.abs(coef), axis=0)
            if importances is not None:
                pairs = sorted(
                    zip(feature_names, [float(v) for v in importances]),
                    key=lambda x: x[1],
                    reverse=True,
                )
                report["featureimportance"] = pairs[:50]
        except Exception:
            pass

        reports.append(report)

    return reports

