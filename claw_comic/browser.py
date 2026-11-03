"""Optional Playwright rendering for JS / lazy-load pages.

This renders the page in a real Chromium, scrolls to trigger
lazy loading, then returns the final HTML for the normal extractor.
It does not solve captchas: if a challenge page appears, the
caller receives bot_wall and must stop.
"""

from __future__ import annotations

from .adblock import is_ad_host
from .fetcher import detect_bot_wall


def render_html(url: str, *, scroll_steps: int = 10, timeout_ms: int = 30000, block_ads: bool = True) -> tuple[str, bool, str]:
    """Return (html, bot_wall, evidence). Raises if Playwright is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for --browser: pip install playwright && playwright install chromium") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        if block_ads:
            def _route(route):
                # Abort network requests to ad hosts while rendering,
                # so ad images/scripts never load into the page.
                if is_ad_host(route.request.url):
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", _route)
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            for _ in range(scroll_steps):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(600)
            html = page.content()
        finally:
            browser.close()
    evidence = detect_bot_wall(200, html)
    return html, bool(evidence), evidence
