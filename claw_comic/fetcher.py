"""Fetching with polite, browser-like behaviour.

What this module does:
- a persistent session with a real-browser User-Agent, Accept-Language
  and a Referer pointing at the chapter's own origin;
- retries with exponential backoff on 429 / 5xx, honouring Retry-After;
- a hard stop on bot walls (Cloudflare challenge, captcha, access
  denied). It never solves a captcha, forges a token, or logs in
  on the user's behalf.

What it deliberately does NOT do: captcha solving, Cloudflare
bypass services, header/token forgery, credential reuse, or
ignoring a 403/429 by switching identity.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

USER_AGENTS = [
    # Current, real desktop browsers. Rotated per session, not per
    # request, so a chapter fetch looks like one browser session.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
    "Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

BOT_WALL_MARKERS = [
    "just a moment",
    "checking your browser",
    "attention required",
    "please verify you are human",
    "verify you are human",
    "captcha",
    "cf-challenge",
    "cloudflare",
    "access denied",
    "forbidden",
    "ddos protection",
    "enable javascript and cookies to continue",
]


@dataclass
class FetchResult:
    url: str
    status_code: int | None
    text: str = ""
    content_type: str = ""
    bot_wall: bool = False
    bot_evidence: str = ""
    error: str = ""


def detect_bot_wall(status_code: int | None, text: str, content_type: str = "") -> str:
    """Return evidence string if this looks like a bot wall, else ''."""
    hay = (text or "")[:8000].lower()
    if status_code == 403:
        return "HTTP 403"
    if status_code == 503 and ("cloudflare" in hay or "just a moment" in hay):
        return "HTTP 503 + Cloudflare challenge page"
    for marker in BOT_WALL_MARKERS:
        if marker in hay:
            # 'forbidden' / 'access denied' alone in a normal page body
            # can be a false positive, so require it in title / early text.
            if marker in ("forbidden", "access denied") and marker not in hay[:2000]:
                continue
            return f"marker: {marker!r}"
    # Cloudflare challenge pages are usually served with this title.
    m = re.search(r"<title>(.*?)</title>", hay, re.S)
    if m and "just a moment" in m.group(1):
        return "title: Just a moment..."
    return ""


def make_session(referer: str | None = None) -> requests.Session:
    s = requests.Session()
    ua = random.choice(USER_AGENTS)
    s.headers.update(
        {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            # NOTE: do NOT advertise "br" — requests/urllib3 here does not
            # decode Brotli, so a br response arrives as garbled bytes
            # and the extractor finds 0 images (found live on xkcd).
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
    )
    if referer:
        s.headers["Referer"] = referer
    return s


def fetch(
    session: requests.Session,
    url: str,
    *,
    delay: float = 1.0,
    max_retries: int = 3,
    timeout: int = 30,
) -> FetchResult:
    """GET with polite retries. Stops (no identity switch) on bot walls."""
    last_error = ""
    for attempt in range(max_retries + 1):
        if attempt:
            wait = delay * (2 ** (attempt - 1))
            time.sleep(wait)
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException as exc:  # network error: retry
            last_error = str(exc)
            continue
        text = resp.text if "text/html" in (resp.headers.get("Content-Type") or "") else ""
        evidence = detect_bot_wall(resp.status_code, text)
        if evidence:
            return FetchResult(url, resp.status_code, text, resp.headers.get("Content-Type", ""),
                               bot_wall=True, bot_evidence=evidence)
        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(min(int(retry_after), 30))
            last_error = f"HTTP {resp.status_code}"
            continue
        if resp.status_code >= 400:
            return FetchResult(url, resp.status_code, text, resp.headers.get("Content-Type", ""),
                               error=f"HTTP {resp.status_code}")
        if delay:
            time.sleep(delay)
        return FetchResult(url, resp.status_code, text, resp.headers.get("Content-Type", ""))
    return FetchResult(url, None, error=f"failed after {max_retries} retries: {last_error}")


def origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
