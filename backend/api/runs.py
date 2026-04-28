from fastapi import APIRouter, HTTPException

from backend.storage.schemas import (
    AnalyzeResponse,
    ArticlesResponse,
    CreateRunRequest,
    CreateRunResponse,
    IssuesResponse,
)
from backend.services.collect_service import start_collect_job
from backend.services.analyze_service import start_analyze_job
from backend.storage.run_repository import (
    get_run_meta,
    list_articles,
    load_issues,
    new_run,
)


router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=CreateRunResponse)
def create_run(payload: CreateRunRequest):
    run_id = new_run(payload.categoryFilter, payload.targetCount, payload.linkPoolSize)
    job_id = start_collect_job(
        run_id=run_id,
        category_filter=payload.categoryFilter,
        target_count=payload.targetCount,
        link_pool_size=payload.linkPoolSize,
    )
    return CreateRunResponse(runId=run_id, collectJobId=job_id)


@router.get("/runs/{runId}", summary="Get run metadata")
def get_run(runId: str):
    meta = get_run_meta(runId)
    if not meta:
        raise HTTPException(status_code=404, detail="run not found")
    return meta


@router.get("/runs/{runId}/articles", response_model=ArticlesResponse)
def get_articles(runId: str):
    return ArticlesResponse(runId=runId, articles=list_articles(runId))


@router.post("/runs/{runId}/analyze", response_model=AnalyzeResponse)
def analyze_run(runId: str):
    meta = get_run_meta(runId)
    if not meta:
        raise HTTPException(status_code=404, detail="run not found")
    job_id = start_analyze_job(run_id=runId)
    return AnalyzeResponse(runId=runId, analyzeJobId=job_id)


@router.get("/runs/{runId}/issues", response_model=IssuesResponse)
def get_issues(runId: str):
    issues = load_issues(runId)
    if issues is None:
        raise HTTPException(status_code=404, detail="issues not found for run")
    return IssuesResponse(runId=runId, issues=issues)

