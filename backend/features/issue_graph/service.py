from __future__ import annotations

import html
import os
import re
from typing import Any, Optional

import requests

from backend.features.issue_graph.schemas import IssueGraphRequest, IssueGraphResponse


NAVER_IMAGE_URL = "https://openapi.naver.com/v1/search/image"


def _get_credential(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets.get(name, "")
    except Exception:
        return ""


def _safe_id(prefix: str, value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value.strip()).strip("-")
    return f"{prefix}:{safe or 'unknown'}"


def _clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_representative_image(keyword: str) -> Optional[dict[str, Any]]:
    client_id = _get_credential("NAVER_CLIENT_ID")
    client_secret = _get_credential("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    response = requests.get(
        NAVER_IMAGE_URL,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        params={"query": keyword, "display": 1, "sort": "sim"},
        timeout=8,
    )
    response.raise_for_status()
    items = response.json().get("items", []) or []
    return items[0] if items else None


def build_issue_image_graph(payload: IssueGraphRequest) -> IssueGraphResponse:
    center_id = _safe_id("issue", payload.issueId)
    nodes: list[dict[str, Any]] = [{"id": center_id, "label": payload.title, "type": "issue", "weight": 2.0}]
    edges: list[dict[str, Any]] = []

    for keyword in payload.keywords[:10]:
        keyword_id = _safe_id("kw", keyword)
        image = _fetch_representative_image(keyword)
        node = {"id": keyword_id, "label": keyword, "type": "keyword", "weight": 1.4}
        if image:
            node.update(
                {
                    "imageUrl": image.get("link"),
                    "thumbnailUrl": image.get("thumbnail") or image.get("link"),
                    "sourceUrl": image.get("link"),
                    "label": keyword or _clean_text(image.get("title", "")),
                }
            )
        nodes.append(node)
        edges.append({"from": center_id, "to": keyword_id, "type": "issue-keyword", "weight": 1.0})

    for press in payload.presses[:8]:
        press_id = _safe_id("press", press)
        nodes.append({"id": press_id, "label": press, "type": "press", "weight": 1.0})
        edges.append({"from": center_id, "to": press_id, "type": "issue-press", "weight": 0.75})

    return IssueGraphResponse(issueId=payload.issueId, nodes=nodes, edges=edges)
