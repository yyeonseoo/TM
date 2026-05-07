from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd


@dataclass(frozen=True)
class IssueData:
    """
    Canonical in-memory representation for a single issue.

    This matches the prompt's schema, but allows missing optional fields.
    """

    issueid: str
    articles: list[dict[str, Any]]
    keywords: list[dict[str, Any]]
    label: Optional[str] = None


def read_json(path: str | Path) -> Any:
    """Read JSON from disk."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, obj: Any) -> None:
    """Write JSON to disk with UTF-8 encoding."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _try_parse_json_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    s = str(value).strip()
    if not s:
        return None
    # issues.csv uses doubled quotes inside a JSON string; json.loads handles it.
    try:
        return json.loads(s)
    except Exception:
        return value


def load_issues_from_csv(
    issues_csv_path: str | Path,
    *,
    issue_id_prefix: str = "issue",
    label_column: Optional[str] = None,
) -> list[IssueData]:
    """
    Load issues from the repo's `data/issues.csv` into the prompt's IssueData format.

    Notes:
    - The repo's CSV is issue-level aggregated output, so it does NOT contain per-article
      sentences/rawtext fields. We synthesize a lightweight `articles` list based on
      `press_data` and `titles/links/evidence`.
    - Keywords are taken from the CSV `keywords` JSON list if present.
    """
    df = pd.read_csv(issues_csv_path)
    out: list[IssueData] = []

    for idx, row in df.iterrows():
        issueid = f"{issue_id_prefix}{idx+1}"
        keywords_raw = _try_parse_json_cell(row.get("keywords"))
        keywords: list[dict[str, Any]] = []
        if isinstance(keywords_raw, list):
            # If it's a list[str], convert to uniform dict with importance=1.0.
            if keywords_raw and isinstance(keywords_raw[0], str):
                keywords = [{"keyword": k, "importance": 1.0} for k in keywords_raw]
            else:
                # already dict-ish, but normalize keys
                for k in keywords_raw:
                    if not isinstance(k, dict):
                        continue
                    kw = k.get("keyword") or k.get("text") or k.get("name") or ""
                    imp = k.get("importance")
                    if imp is None:
                        imp = k.get("score", 1.0)
                    keywords.append({"keyword": str(kw), "importance": float(imp)})

        press_data = _try_parse_json_cell(row.get("press_data"))
        articles: list[dict[str, Any]] = []

        # Synthesize article-like rows for downstream graph construction.
        if isinstance(press_data, dict):
            for press, pdata in press_data.items():
                titles = pdata.get("titles") or []
                links = pdata.get("links") or []
                evidence = pdata.get("evidence") or []
                # Create up to N pseudo-articles per press using titles/links as anchors.
                n = max(len(titles), len(links), 1)
                for j in range(n):
                    title = titles[j] if j < len(titles) else (titles[0] if titles else "")
                    link = links[j] if j < len(links) else (links[0] if links else "")
                    rawtext = " ".join(evidence) if isinstance(evidence, list) else str(evidence or "")
                    articles.append(
                        {
                            "title": title,
                            "sentences": evidence if isinstance(evidence, list) else [],
                            "publisher": press,
                            "rawtext": rawtext,
                            "date": None,
                            "url": link,
                        }
                    )

        label = None
        if label_column and label_column in df.columns:
            v = row.get(label_column)
            if v is not None and str(v).strip():
                label = str(v)

        out.append(IssueData(issueid=issueid, articles=articles, keywords=keywords, label=label))

    return out


def ensure_issue_dicts(issues: Iterable[IssueData | dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert `IssueData` objects or dicts into list[dict]."""
    out: list[dict[str, Any]] = []
    for it in issues:
        if isinstance(it, IssueData):
            out.append(
                {
                    "issueid": it.issueid,
                    "articles": it.articles,
                    "keywords": it.keywords,
                    **({"label": it.label} if it.label is not None else {}),
                }
            )
        else:
            out.append(dict(it))
    return out

