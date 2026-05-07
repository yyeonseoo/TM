from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "done", "error"]


class CreateRunRequest(BaseModel):
    categoryFilter: str = Field(default="politics")
    targetCount: int = Field(default=30, ge=1)
    linkPoolSize: int = Field(default=100, ge=10)


class CreateRunResponse(BaseModel):
    runId: str
    collectJobId: str


class AnalyzeResponse(BaseModel):
    runId: str
    analyzeJobId: str


class JobStatusResponse(BaseModel):
    jobId: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str = ""
    runId: Optional[str] = None
    kind: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    error: Optional[str] = None


class Article(BaseModel):
    articleId: str
    title: str
    press: str
    url: str
    publishedAt: Optional[str] = None
    contentPreview: str = ""


class ArticlesResponse(BaseModel):
    runId: str
    articles: list[Article]


class PressData(BaseModel):
    press: str
    summary: str = ""
    emphasizedSentences: list[str] = Field(default_factory=list)
    missingFacts: list[str] = Field(default_factory=list)
    evidenceSentences: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    issueId: str
    rank: int
    title: str
    keywords: list[str]
    commonFacts: list[str]
    pressData: list[PressData]
    evidenceSentences: list[str] = Field(default_factory=list)
    summary: str = ""
    controversies: list[dict[str, Any]] = Field(default_factory=list)


class IssuesResponse(BaseModel):
    runId: str
    issues: list[Issue]

