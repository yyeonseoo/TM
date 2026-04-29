from __future__ import annotations

import html
import os
import re
from typing import Any, Optional
from urllib.parse import unquote, urlparse

import requests

from backend.features.issue_graph.schemas import IssueGraphRequest, IssueGraphResponse


NAVER_IMAGE_URL = "https://openapi.naver.com/v1/search/image"
IMAGE_CANDIDATE_COUNT = 10
POSITIVE_TERMS = ("공식", "로고", "대표", "홈페이지", "logo", "official")
NEGATIVE_TERMS = ("쇼핑", "판매", "중고", "광고", "가격", "구매", "shopping", "sale", "used", "ad")

RELATION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("공천", ("공천", "전략공천", "후보로 냈", "후보로 내세", "후보를 냈", "후보를 내세", "후보로 확정", "후보로 선정")),
    ("출마", ("출마", "출사표", "후보 등록", "후보등록", "후보로 나섰", "선거에 나섰", "도전")),
    ("후보", ("후보", "후보자", "시장 후보", "구청장 후보", "의원 후보")),
    ("지역", ("지역", "선거구", "부산시장", "시장", "구청장", "재보선 지역")),
    ("당선", ("당선", "선출", "승리")),
    ("낙선", ("낙선", "패배")),
    ("비판", ("비판", "비난", "공세", "질타", "규탄", "공격")),
    ("반박", ("반박", "해명", "부인", "반발")),
    ("수사", ("수사", "조사", "압수수색", "기소", "고발")),
    ("발표", ("발표", "공개", "밝혔", "밝히", "선언")),
    ("추진", ("추진", "검토", "논의", "계획")),
    ("지원", ("지원", "협력", "연대", "지지")),
    ("방문", ("방문", "참석", "찾았", "찾아")),
    ("경쟁", ("대결", "경쟁", "맞붙", "공방")),
)

MAX_RELATION_SENTENCES = 40
MAX_EVIDENCE_PER_EDGE = 3
MAX_KEYWORD_PAIR_DISTANCE = 180


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


def _keyword_tokens(keyword: str) -> list[str]:
    tokens = re.findall(r"[\uac00-\ud7a3A-Za-z0-9]{2,}", keyword)
    if keyword and keyword not in tokens:
        tokens.insert(0, keyword)
    return list(dict.fromkeys(tokens))


def _candidate_text(item: dict[str, Any]) -> str:
    parts = [
        _clean_text(str(item.get("title", ""))),
        unquote(str(item.get("link", ""))),
        unquote(str(item.get("thumbnail", ""))),
    ]
    return " ".join(parts).lower()


def _score_image_candidate(keyword: str, item: dict[str, Any], index: int) -> float:
    text = _candidate_text(item)
    keyword_lower = keyword.lower()
    score = 0.0

    if keyword_lower and keyword_lower in text:
        score += 12

    for token in _keyword_tokens(keyword):
        token_lower = token.lower()
        if token_lower and token_lower in text:
            score += 3

    for term in POSITIVE_TERMS:
        if term.lower() in text:
            score += 2

    for term in NEGATIVE_TERMS:
        if term.lower() in text:
            score -= 6

    link = str(item.get("link", ""))
    thumbnail = str(item.get("thumbnail", ""))
    if link.startswith("https://"):
        score += 0.5
    if thumbnail:
        score += 0.5

    domain = urlparse(link).netloc.lower()
    if any(blocked in domain for blocked in ("shopping", "smartstore", "auction", "gmarket")):
        score -= 5

    score -= index * 0.15
    return score


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
        params={"query": keyword, "display": IMAGE_CANDIDATE_COUNT, "sort": "sim"},
        timeout=8,
    )
    response.raise_for_status()
    items = response.json().get("items", []) or []
    if not items:
        return None
    return max(enumerate(items), key=lambda pair: _score_image_candidate(keyword, pair[1], pair[0]))[1]


def _sentence_sources(payload: IssueGraphRequest) -> list[str]:
    seen: set[str] = set()
    sentences: list[str] = []
    for text in [payload.title, *payload.commonFacts, *payload.evidenceSentences]:
        sentence = _clean_text(text)
        if not sentence or sentence in seen:
            continue
        seen.add(sentence)
        sentences.append(sentence)
    return sentences[:MAX_RELATION_SENTENCES]


def _keyword_aliases(keyword: str) -> list[str]:
    aliases = [keyword.strip()]
    compact = re.sub(r"\s+", "", keyword)
    if compact and compact not in aliases:
        aliases.append(compact)
    return [alias for alias in aliases if alias]


def _find_keyword_position(sentence: str, keyword: str) -> int:
    for alias in _keyword_aliases(keyword):
        position = sentence.find(alias)
        if position >= 0:
            return position

    compact_sentence = re.sub(r"\s+", "", sentence)
    compact_keyword = re.sub(r"\s+", "", keyword)
    if compact_keyword and compact_keyword in compact_sentence:
        first_token = _keyword_tokens(keyword)[0] if _keyword_tokens(keyword) else keyword
        fallback = sentence.find(first_token)
        return fallback if fallback >= 0 else 0

    return -1


def _keyword_mentions(sentence: str, keywords: list[str]) -> list[tuple[int, str]]:
    mentions: list[tuple[int, str]] = []
    for keyword in keywords:
        position = _find_keyword_position(sentence, keyword)
        if position >= 0:
            mentions.append((position, keyword))
    mentions.sort(key=lambda item: item[0])
    return mentions


def _is_location_like(keyword: str) -> bool:
    return keyword.endswith(("시", "도", "군", "구", "읍", "면", "동")) or keyword in {
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
        "아산",
    }


def _relation_context(sentence: str, left: str, right: str) -> str:
    left_pos = _find_keyword_position(sentence, left)
    right_pos = _find_keyword_position(sentence, right)
    if left_pos < 0 or right_pos < 0:
        return sentence

    start = max(0, min(left_pos, right_pos) - 40)
    end = min(len(sentence), max(left_pos + len(left), right_pos + len(right)) + 60)
    return sentence[start:end]


def _relation_label(sentence: str, left: str, right: str) -> Optional[str]:
    context = _relation_context(sentence, left, right)

    if (_is_location_like(left) or _is_location_like(right)) and any(term in context for term in ("후보", "출마", "선거", "재보선")):
        return "출마 지역"

    for label, patterns in RELATION_PATTERNS:
        if any(pattern in context or pattern in sentence for pattern in patterns):
            return label
    return None


def _relation_edges(payload: IssueGraphRequest, keyword_ids: dict[str, str]) -> list[dict[str, Any]]:
    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    keywords = list(keyword_ids.keys())

    for sentence in _sentence_sources(payload):
        mentions = _keyword_mentions(sentence, keywords)
        if len(mentions) < 2:
            continue

        for left_index in range(len(mentions)):
            for right_index in range(left_index + 1, len(mentions)):
                left_pos, left = mentions[left_index]
                right_pos, right = mentions[right_index]
                if left == right or abs(right_pos - left_pos) > MAX_KEYWORD_PAIR_DISTANCE:
                    continue

                label = _relation_label(sentence, left, right)
                if not label:
                    continue

                from_id = keyword_ids[left]
                to_id = keyword_ids[right]
                key = (from_id, to_id, label)
                if key not in edge_map:
                    edge_map[key] = {
                        "from": from_id,
                        "to": to_id,
                        "type": "keyword-relation",
                        "label": label,
                        "evidence": [],
                        "weight": 0.0,
                    }
                edge = edge_map[key]
                edge["weight"] += 1.0
                if len(edge["evidence"]) < MAX_EVIDENCE_PER_EDGE and sentence not in edge["evidence"]:
                    edge["evidence"].append(sentence)

    return list(edge_map.values())


def build_issue_image_graph(payload: IssueGraphRequest) -> IssueGraphResponse:
    nodes: list[dict[str, Any]] = []
    keyword_ids: dict[str, str] = {}

    for keyword in payload.keywords[:10]:
        keyword_id = _safe_id("kw", keyword)
        keyword_ids[keyword] = keyword_id
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

    edges = _relation_edges(payload, keyword_ids)

    return IssueGraphResponse(issueId=payload.issueId, nodes=nodes, edges=edges)
