from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class IssueContext:
    issue_id: str
    title: str
    summary: str
    text: str
    entities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    source: str
    title: Optional[str] = None
    caption: Optional[str] = None
    page_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageFeatures:
    keyword_match: float
    entity_match: float
    text_similarity: float
    source_reliability: float
    quality_score: float
    generic_penalty: float
    duplicate_penalty: float
    clip_issue_similarity: Optional[float] = None
    clip_keyword_similarity: Optional[float] = None


@dataclass(frozen=True)
class RankedImage:
    candidate: ImageCandidate
    features: ImageFeatures
    score: float
    reason: str


@dataclass(frozen=True)
class IconSelection:
    icon_url: str
    selected: bool
    score: float
    source: str
    reason: str
    fallback: bool
    candidates_count: int

