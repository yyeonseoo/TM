from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import Any, Optional


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNS_DIR = os.path.join(ROOT, "data", "runs")


def _run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)


def _ensure_run_dir(run_id: str) -> str:
    path = _run_dir(run_id)
    os.makedirs(path, exist_ok=True)
    return path


def new_run(category_filter: str, target_count: int, link_pool_size: int) -> str:
    os.makedirs(RUNS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{ts}"
    path = _ensure_run_dir(run_id)
    meta = {
        "runId": run_id,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "categoryFilter": category_filter,
        "targetCount": target_count,
        "linkPoolSize": link_pool_size,
    }
    with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    return run_id


def get_run_meta(run_id: str) -> Optional[dict[str, Any]]:
    path = os.path.join(_run_dir(run_id), "meta.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def save_articles(run_id: str, articles: list[dict[str, Any]]):
    path = _ensure_run_dir(run_id)
    csv_path = os.path.join(path, "articles.csv")
    fieldnames = ["articleId", "title", "press", "url", "publishedAt", "contentPreview", "content", "category"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for idx, a in enumerate(articles, start=1):
            writer.writerow(
                {
                    "articleId": a.get("articleId") or f"a{idx:04d}",
                    "title": a.get("title", ""),
                    "press": a.get("press", ""),
                    "url": a.get("url", ""),
                    "publishedAt": a.get("publishedAt", ""),
                    "contentPreview": a.get("contentPreview", ""),
                    "content": a.get("content", ""),
                    "category": a.get("category", ""),
                }
            )


def list_articles(run_id: str) -> list[dict[str, Any]]:
    csv_path = os.path.join(_run_dir(run_id), "articles.csv")
    if not os.path.exists(csv_path):
        return []
    rows: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(
                {
                    "articleId": row.get("articleId", ""),
                    "title": row.get("title", ""),
                    "press": row.get("press", ""),
                    "url": row.get("url", ""),
                    "publishedAt": row.get("publishedAt") or None,
                    "contentPreview": row.get("contentPreview", ""),
                }
            )
    return rows


def load_article_contents_df(run_id: str):
    import pandas as pd

    csv_path = os.path.join(_run_dir(run_id), "articles.csv")
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    return pd.read_csv(csv_path).fillna("")


def save_issues(run_id: str, issues: list[dict[str, Any]]):
    path = _ensure_run_dir(run_id)
    with open(os.path.join(path, "issues.json"), "w", encoding="utf-8") as fp:
        json.dump(issues, fp, ensure_ascii=False, indent=2)


def load_issues(run_id: str) -> Optional[list[dict[str, Any]]]:
    path = os.path.join(_run_dir(run_id), "issues.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)

