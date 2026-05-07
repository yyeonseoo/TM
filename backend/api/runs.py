from fastapi import APIRouter, HTTPException, Query

from backend.storage.schemas import (
    AnalyzeResponse,
    ArticlesResponse,
    CreateRunRequest,
    CreateRunResponse,
    IssuesResponse,
)
from backend.services.collect_service import start_collect_job
from backend.services.analyze_service import start_analyze_job
from backend.services.news_timeseries_service import get_news_timeseries
from backend.storage.run_repository import (
    get_run_meta,
    list_articles,
    load_issues,
    new_run,
)

from graph_pipeline.graphs.weighted_graph import build_weighted_graph
from backend.services.image_graph_service import build_image_graph_payload


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


@router.get("/runs/{runId}/issues/{issueId}/graph")
def get_issue_graph(runId: str, issueId: str):
    """
    Build and return a weighted relationship graph for a single issue, for the web UI.

    This uses the analyzed issue JSON (pressData/keywords/evidence) and constructs a
    prompt-shaped `issue_data` object for the graph builder.
    """
    issues = load_issues(runId)
    if issues is None:
        raise HTTPException(status_code=404, detail="issues not found for run")

    issue = next((it for it in issues if str(it.get("issueId")) == str(issueId)), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="issue not found")

    # Synthesize minimal prompt-shaped issue data
    press_data = issue.get("pressData") or []
    articles = []
    for p in press_data:
        press = (p or {}).get("press") or "unknown"
        titles = (p or {}).get("titles") or []
        links = (p or {}).get("links") or []
        evidence = (p or {}).get("evidenceSentences") or []
        n = max(len(titles), len(links), 1)
        for j in range(n):
            articles.append(
                {
                    "title": titles[j] if j < len(titles) else (titles[0] if titles else ""),
                    "sentences": evidence if isinstance(evidence, list) else [],
                    "publisher": press,
                    "rawtext": " ".join(evidence) if isinstance(evidence, list) else str(evidence or ""),
                    "date": None,
                }
            )

    issue_data = {
        "issueid": issueId,
        "articles": articles,
        "keywords": [{"keyword": k, "importance": 1.0} for k in (issue.get("keywords") or []) if k],
    }

    _, export_json = build_weighted_graph(issue_data)
    return {"runId": runId, "issueId": issueId, "graph": export_json}


@router.get("/runs/{runId}/issues/{issueId}/image-graph")
def get_issue_image_graph(runId: str, issueId: str):
    """
    Keyword-only undirected issue graph with icon image urls, relation labels,
    ranking + adaptive cutoff + pruning.
    """
    issues = load_issues(runId)
    if issues is None:
        raise HTTPException(status_code=404, detail="issues not found for run")

    issue = next((it for it in issues if str(it.get("issueId")) == str(issueId)), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="issue not found")

    payload = build_image_graph_payload(issue)
    # rewrite icon urls to go through proxy (avoid CORS)
    from urllib.parse import quote

    for n in payload.get("graph", {}).get("nodes", []):
        icon = n.get("iconUrl")
        if isinstance(icon, str) and icon.startswith("http"):
            n["iconUrl"] = f"/api/image-proxy?url={quote(icon, safe='')}"

    return {"runId": runId, **payload}


@router.get("/runs/{runId}/issues/timeseries")
def get_issue_timeseries(
    runId: str,
    keyword: str = Query(..., description="재검색할 이슈 키워드"),
    display: int = Query(100, ge=1, le=100, description="가져올 기사 수"),
):
    """
    선택된 이슈 키워드 기반 네이버 뉴스 재검색
    날짜별 기사 수를 집계 -> 프론트 시계열 차트용 데이터로 반환
    """

    meta = get_run_meta(runId)
    if not meta:
        raise HTTPException(status_code=404, detail="run not found")

    try:
        result = get_news_timeseries(keyword=keyword, display=display)

        return {
            "runId": runId,
            **result,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"news timeseries failed: {str(e)}",
        )