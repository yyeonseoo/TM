from __future__ import annotations

from backend.services.job_service import new_job, run_in_thread, update_job
from backend.storage.run_repository import save_articles

from src.crawler import crawl_articles
from src.news_api import fetch_news_links


def start_collect_job(run_id: str, category_filter: str, target_count: int, link_pool_size: int) -> str:
    job_id = new_job("collect", run_id=run_id)

    def _work():
        update_job(job_id, progress=5, message="뉴스 링크 수집 중")
        query = "정치" if category_filter.lower() in ("politics", "정치") else category_filter
        links = fetch_news_links(query=query, target_count=link_pool_size)

        update_job(job_id, progress=35, message="기사 크롤링 중")
        articles = crawl_articles(links, max_articles=target_count, category_filter="정치" if category_filter.lower() in ("politics", "정치") else None)

        update_job(job_id, progress=80, message="기사 저장 중")
        mapped = []
        for idx, a in enumerate(articles, start=1):
            content = a.get("content", "")
            mapped.append(
                {
                    "articleId": f"a{idx:04d}",
                    "title": a.get("title", ""),
                    "press": a.get("press", ""),
                    "url": a.get("link", ""),
                    "publishedAt": "",
                    "contentPreview": (content[:160] + "...") if len(content) > 160 else content,
                    "content": content,
                    "category": a.get("category", ""),
                }
            )
        save_articles(run_id, mapped)
        update_job(job_id, progress=95, message=f"{len(mapped)}개 기사 저장 완료")

    run_in_thread(job_id, _work)
    return job_id

