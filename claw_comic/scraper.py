"""Orchestration: fetch -> extract -> (follow Next) -> classify."""

from __future__ import annotations

import requests

from .extract import ChapterResult, classify, extract_images, find_next_url, title_of
from .fetcher import fetch, make_session, origin


def scrape(
    url: str,
    *,
    mode: str = "auto",
    max_pages: int = 50,
    delay: float = 1.0,
    session: requests.Session | None = None,
) -> ChapterResult:
    sess = session or make_session(referer=origin(url))
    result = ChapterResult(url=url)
    seen_urls: set[str] = set()
    current = url
    images_per_page: list[int] = []
    has_next = False

    for page_no in range(max_pages):
        if current in seen_urls:
            break
        seen_urls.add(current)
        res = fetch(sess, current, delay=delay)
        if res.bot_wall:
            result.status = "bot_wall"
            result.bot_evidence = res.bot_evidence
            result.pages_fetched = page_no
            break
        if res.error or res.status_code is None:
            result.status = "error"
            result.error = res.error or f"HTTP {res.status_code}"
            result.pages_fetched = page_no
            break
        result.pages_fetched = page_no + 1
        if not result.title:
            result.title = title_of(res.text)
        images, container = extract_images(res.text, current)
        if page_no == 0:
            result.container = container
        images_per_page.append(len(images))
        for img in images:
            if img not in result.images:
                result.images.append(img)
        nxt = find_next_url(res.text, current, current)
        result.next_url = nxt
        has_next = bool(nxt)
        # Paginated mode: keep following. Other modes: one page is the chapter.
        if mode == "paginated" or (mode == "auto" and len(images) <= 2 and nxt):
            if not nxt:
                break
            current = nxt
            continue
        break

    if result.status == "ok":
        result.layout = mode if mode != "auto" else classify(images_per_page, has_next, result.container)
    return result
