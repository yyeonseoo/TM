from __future__ import annotations

from fastapi import APIRouter

from backend.features.issue_graph.schemas import IssueGraphRequest, IssueGraphResponse
from backend.features.issue_graph.service import build_issue_image_graph


router = APIRouter(prefix="/issue-graph", tags=["issue-graph"])


@router.post("/extract", response_model=IssueGraphResponse)
def extract_issue_graph(payload: IssueGraphRequest):
    return build_issue_image_graph(payload)

