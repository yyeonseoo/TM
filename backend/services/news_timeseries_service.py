from collections import Counter
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from src.news_api import fetch_news_items


def _clean_text(text: str) -> str:
    """
    네이버 뉴스 API 결과에 HTML 강조 태그 제거
    """
    if not text:
        return ""

    return (
        text.replace("<b>", "")
        .replace("</b>", "")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def _parse_pub_date(pub_date: str) -> Optional[str]:
    """
    네이버 뉴스 API의 pubDate 형태 변환 : YYYY-MM-DD
    """
    try:
        dt = parsedate_to_datetime(pub_date)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def get_news_timeseries(keyword: str, display: int = 100) -> Dict:
    """
    선택된 이슈 키워드 -> 네이버 뉴스 재검색
    날짜별 기사 수 집계 -> 프론트 시계열 차트용 응답 생성
    """
    items = fetch_news_items(
        query=keyword,
        target_count=display,
        display=display,
        max_pages=1,
    )

    date_counter = Counter()
    articles: List[Dict] = []

    for item in items:
        pub_date = _parse_pub_date(item.get("pubDate", ""))

        if not pub_date:
            continue

        date_counter[pub_date] += 1

        articles.append(
            {
                "title": _clean_text(item.get("title", "")),
                "description": _clean_text(item.get("description", "")),
                "link": item.get("link", ""),
                "originallink": item.get("originallink", ""),
                "pubDate": item.get("pubDate", ""),
                "date": pub_date,
            }
        )

    series = [
        {
            "date": date,
            "count": count,
        }
        for date, count in sorted(date_counter.items())
    ]

    return {
        "keyword": keyword,
        "totalCount": len(articles),
        "series": series,
        "articles": articles,
    }