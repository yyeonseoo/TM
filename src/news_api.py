import html
import os

import requests


NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
DEFAULT_POLITICS_QUERY = "\uc815\uce58"


def _try_load_dotenv() -> None:
    """
    Best-effort dotenv load.
    This module can run inside background job threads where app-startup dotenv
    loading might not have executed in the same process (e.g. reloaders).
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        load_dotenv(os.path.join(root, "backend", ".env"), override=False)
        load_dotenv(os.path.join(root, ".env"), override=False)
    except Exception:
        return


_try_load_dotenv()


def _get_credential(name):
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        return st.secrets.get(name, "")
    except Exception:
        return ""


def fetch_news_links(query=DEFAULT_POLITICS_QUERY, target_count=300, display=100, max_pages=10):
    """Fetch enough Naver news links for downstream politics-only crawling."""
    client_id = _get_credential("NAVER_CLIENT_ID")
    client_secret = _get_credential("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("NAVER_CLIENT_ID\uc640 NAVER_CLIENT_SECRET\uc744 \ud658\uacbd\ubcc0\uc218 \ub610\ub294 Streamlit secrets\uc5d0 \uc124\uc815\ud574\uc57c \ud569\ub2c8\ub2e4.")

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    links = []
    seen = set()

    display = min(int(display), 100)
    for page in range(max_pages):
        params = {
            "query": query,
            "display": display,
            "start": page * display + 1,
            "sort": "date",
        }
        response = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        items = response.json().get("items", [])
        if not items:
            break

        for item in items:
            for link in [item.get("link", ""), item.get("originallink", "")]:
                link = html.unescape(link)
                if "news.naver.com" not in link or link in seen:
                    continue
                seen.add(link)
                links.append(link)
                if len(links) >= target_count:
                    return links

    return links

#
def fetch_news_items(query, target_count=100, display=100, max_pages=1):
    """
    선택된 이슈 키워드 -> 재검색 -> 기사 item 전체 반환
    """
    client_id = _get_credential("NAVER_CLIENT_ID")
    client_secret = _get_credential("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 환경변수 또는 Streamlit secrets에 설정해야 합니다."
        )

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    items_result = []
    seen_links = set()

    display = min(int(display), 100)

    for page in range(max_pages):
        params = {
            "query": query,
            "display": display,
            "start": page * display + 1,
            "sort": "date",
        }

        response = requests.get(
            NAVER_NEWS_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        items = response.json().get("items", [])
        if not items:
            break

        for item in items:
            link = html.unescape(item.get("link", ""))
            originallink = html.unescape(item.get("originallink", ""))

            unique_key = link or originallink
            if not unique_key or unique_key in seen_links:
                continue

            seen_links.add(unique_key)

            items_result.append(
                {
                    "title": html.unescape(item.get("title", "")),
                    "description": html.unescape(item.get("description", "")),
                    "link": link,
                    "originallink": originallink,
                    "pubDate": item.get("pubDate", ""),
                }
            )

            if len(items_result) >= target_count:
                return items_result

    return items_result
