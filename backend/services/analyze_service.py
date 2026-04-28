from __future__ import annotations

import json

from backend.services.job_service import new_job, run_in_thread, update_job
from backend.storage.run_repository import load_article_contents_df, save_issues

from src.analyzer import analyze_issues
from src.clustering import cluster_sentences
from src.embedding import generate_embeddings
from src.preprocess import preprocess_articles


def _to_issue_response(issues_raw: list[dict], run_id: str) -> list[dict]:
    # src.analyzer returns CSV-oriented fields (some JSON strings). Convert to API JSON.
    converted = []
    for idx, issue in enumerate(issues_raw, start=1):
        press_data = {}
        try:
            press_data = json.loads(issue.get("press_data", "{}") or "{}")
        except Exception:
            press_data = {}

        press_items = []
        for press, data in press_data.items():
            press_items.append(
                {
                    "press": press,
                    "summary": "",
                    "emphasizedSentences": [data.get("emphasis_sentence", "")] if data.get("emphasis_sentence") else [],
                    "missingFacts": [],
                    "evidenceSentences": data.get("evidence", []) or [],
                    "keywords": data.get("keywords", []) or [],
                    "titles": data.get("titles", []) or [],
                    "links": data.get("links", []) or [],
                }
            )

        def _load_list(key: str):
            try:
                return json.loads(issue.get(key, "[]") or "[]")
            except Exception:
                return []

        converted.append(
            {
                "issueId": f"issue_{idx:03d}",
                "rank": idx,
                "title": issue.get("title", f"이슈 {idx}"),
                "keywords": _load_list("keywords"),
                "commonFacts": _load_list("common_facts"),
                "pressData": press_items,
                "evidenceSentences": _load_list("evidence_sentences"),
                "summary": issue.get("summary", ""),
                "controversies": _load_list("controversy_clusters"),
            }
        )
    return converted


def start_analyze_job(run_id: str) -> str:
    job_id = new_job("analyze", run_id=run_id)

    def _work():
        df_articles = load_article_contents_df(run_id)
        if df_articles.empty:
            raise ValueError("수집된 기사가 없습니다. 먼저 수집을 실행해 주세요.")

        update_job(job_id, progress=10, message="문장 분리 중")
        sentence_df = preprocess_articles(df_articles)

        update_job(job_id, progress=35, message="임베딩 생성 중")
        embeddings = generate_embeddings(sentence_df["sentence"].tolist())

        update_job(job_id, progress=65, message="클러스터링 중")
        clusters = cluster_sentences(embeddings, sentence_df)

        update_job(job_id, progress=85, message="이슈 TOP3 추출 중")
        issues_raw = analyze_issues(clusters)
        issues = _to_issue_response(issues_raw, run_id=run_id)
        save_issues(run_id, issues)

        update_job(job_id, progress=95, message="결과 저장 완료")

    run_in_thread(job_id, _work)
    return job_id

