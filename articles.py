"""Open article links and extract their text."""

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import trafilatura

from mail import SKIP_URL

MIN_WORDS = 300
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
}


def fetch_article(link: dict) -> dict:
    """Return the link with final url, text and word count; text is None if unusable."""
    result = {**link, "final_url": link["url"], "text": None, "words": 0, "error": None}
    try:
        resp = requests.get(link["url"], headers=HEADERS, timeout=15)  # follows redirects
        resp.raise_for_status()
        result["final_url"] = resp.url
        if SKIP_URL.search(resp.url):
            result["error"] = "service link after redirect"
            return result
        if urlparse(resp.url).path in ("", "/"):
            result["error"] = "homepage"
            return result
        text = trafilatura.extract(resp.text, url=resp.url) or ""
    except requests.RequestException as e:
        result["error"] = type(e).__name__
        return result
    result["words"] = len(text.split())
    if result["words"] < MIN_WORDS:
        result["error"] = f"too short ({result['words']} words)"
    else:
        result["text"] = text
    return result


def fetch_articles(links: list[dict]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        articles = list(pool.map(fetch_article, links))
    # Different tracking links often lead to the same article.
    seen = set()
    for a in articles:
        key = a["final_url"].split("?")[0]
        if not a["text"]:
            continue
        if key in seen:
            a["text"], a["error"] = None, "duplicate"
        seen.add(key)
    return articles
