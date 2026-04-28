from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class IssueGraphRequest(BaseModel):
    issueId: str
    title: str
    keywords: list[str] = Field(default_factory=list)
    presses: list[str] = Field(default_factory=list)


class IssueGraphNode(BaseModel):
    id: str
    label: str
    type: Literal["issue", "keyword", "press"]
    imageUrl: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    sourceUrl: Optional[str] = None
    weight: float = 1.0


class IssueGraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: Literal["issue-keyword", "issue-press"]
    weight: float = 1.0


class IssueGraphResponse(BaseModel):
    issueId: str
    nodes: list[IssueGraphNode]
    edges: list[IssueGraphEdge]
