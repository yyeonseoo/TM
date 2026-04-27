from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _text_or_empty(node):
    return node.get_text(" ", strip=True) if node else ""


def _extract_press(soup):
    logo = soup.select_one("a.media_end_head_top_logo img")
    if logo and logo.get("alt"):
        return logo["alt"].strip()

    text_logo = soup.select_one("a.media_end_head_top_logo")
    return _text_or_empty(text_logo) or "\uc5b8\ub860\uc0ac \ubbf8\uc0c1"


def _extract_category(soup):
    candidates = []
    selectors = [
        ".media_end_categorize_item",
        "em.media_end_categorize_item",
        ".Nlist_item._LNB_ITEM.is_active span",
        "meta[property='article:section']",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get("content", "") if node.name == "meta" else _text_or_empty(node)
            if text:
                candidates.append(text.strip())

    joined = " ".join(candidates)
    if "\uc815\uce58" in joined:
        return "\uc815\uce58"
    return candidates[0] if candidates else ""


def _matches_category(category, category_filter):
    if not category_filter:
        return True
    return category_filter in category


def _crawl_one(link, category_filter=None):
    try:
        response = requests.get(link, headers=HEADERS, timeout=6)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        body = soup.select_one("#dic_area")
        if not body:
            return None

        category = _extract_category(soup)
        if not _matches_category(category, category_filter):
            return None

        title = _text_or_empty(soup.select_one("#title_area")) or _text_or_empty(soup.select_one("h2"))
        content = _text_or_empty(body)
        press = _extract_press(soup)
        if not title or not content:
            return None

        return {
            "title": title,
            "content": content,
            "press": press,
            "category": category,
            "link": link,
        }
    except requests.RequestException as exc:
        print(f"crawl failed: {link}, error: {exc}")
        return None


def crawl_articles(links, max_articles=None, category_filter=None, max_workers=16):
    """Crawl Naver articles concurrently from #dic_area."""
    unique_links = []
    seen = set()
    for link in links:
        if link and link not in seen:
            seen.add(link)
            unique_links.append(link)

    articles = []
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = {
        executor.submit(_crawl_one, link, category_filter): link
        for link in unique_links
    }

    try:
        for future in as_completed(futures):
            article = future.result()
            if not article:
                continue

            articles.append(article)
            if max_articles and len(articles) >= max_articles:
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                break
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return articles[:max_articles] if max_articles else articles
