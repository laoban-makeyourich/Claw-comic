"""Generic chapter extraction for the 3 layouts.

Strategy, in order:
1. Score every container (div/section/article/main) by how many
   comic-like images it holds; the best container wins. This covers
   both vertical strips and single-container readers without a
   site-specific selector.
2. Fall back to all images in the document, then to image URLs
   embedded in <script> JSON (Next.js / Nuxt / reader APIs).
3. Classify the layout from structure, not from the site name:
   paginated = 1-2 images per page + a Next link;
   single_container = many images inside one reader/viewer frame;
   vertical = many images in a chapter page with no Next link.
4. For paginated chapters, follow Next links (rel=next, .next,
   pagination, or ?page=/page/ URL patterns) until no Next,
   a loop, or max_pages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
BAD_SUBSTRINGS = (
    "logo", "avatar", "banner", "ads/", "/ad-", "advert",
    "icon", "sprite", "placeholder", "loading", "blank.gif",
    "bg_transparency", "transparency.png",
    "facebook", "twitter", "discord", "telegram", "qr-code",
)
CONTAINER_HINTS = (
    "reader", "read", "chapter", "comic", "page", "viewer",
    "content", "images", "imagelist", "strip", "scroll", "manga", "manhwa",
)


def _is_image_url(url: str) -> bool:
    u = url.lower().split("?")[0]
    return u.endswith(IMAGE_EXT)


def _is_bad(url: str, tag) -> bool:
    low = url.lower()
    if any(b in low for b in BAD_SUBSTRINGS):
        return True
    cls = " ".join(tag.get("class", [])).lower()
    ident = (tag.get("id") or "").lower()
    if any(b in cls or b in ident for b in ("logo", "avatar", "banner", "ads", "icon")):
        return True
    return False


def _img_url(tag, base: str) -> str | None:
    # data-url is how WEBTOON stores the real episode image while
    # src is just a transparent placeholder (found live, 2026-11-03).
    for attr in ("data-src", "data-original", "data-lazy-src", "data-url", "data-srcset", "src"):
        val = tag.get(attr)
        if not val:
            continue
        if attr == "data-srcset":
            # srcset: take the largest candidate
            val = val.split(",")[-1].strip().split(" ")[0]
        if val.startswith("data:"):
            continue
        return urljoin(base, val.strip())
    # <picture><source srcset>
    parent = tag.parent
    if parent and parent.name == "picture":
        for src in parent.find_all("source"):
            s = src.get("srcset") or src.get("data-srcset")
            if s:
                return urljoin(base, s.split(",")[-1].strip().split(" ")[0])
    return None


def _json_image_urls(html: str, base: str) -> list[str]:
    found: list[str] = []
    for m in re.finditer(r'https?://[^\s"\'\\]+\.(?:jpg|jpeg|png|webp|gif|avif)(?:\?[^\s"\'\\]*)?', html, re.I):
        url = m.group(0)
        if not _is_bad(url, type("T", (), {"get": lambda self, k, d=None: ""})()):
            found.append(url)
    # Deduplicate, preserve order
    seen, out = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _score_container(tag) -> int:
    score = 0
    ident = ((tag.get("id") or "") + " " + " ".join(tag.get("class", []))).lower()
    for hint in CONTAINER_HINTS:
        if hint in ident:
            score += 10
    score += len(tag.find_all("img"))
    return score


def extract_images(html: str, base: str) -> tuple[list[str], str]:
    """Return (image URLs in reading order, best container selector)."""
    soup = BeautifulSoup(html, "lxml")
    # A dedicated image-list frame (e.g. WEBTOON #_imageList) beats
    # any ancestor wrapper: ancestors also contain episode lists,
    # thumbnails and site chrome, which pollute the result.
    for el in soup.find_all(["div", "section", "figure"]):
        ident = ((el.get("id") or "") + " " + " ".join(el.get("class", []))).lower()
        if "imagelist" in ident or "image-list" in ident:
            urls = []
            for tag in el.find_all("img"):
                u = _img_url(tag, base)
                if u and _is_image_url(u) and not _is_bad(u, tag) and u not in urls:
                    urls.append(u)
            if urls:
                return urls, f"{el.name}#{el.get('id') or '.'.join(el.get('class', []))}"
    candidates = []
    for container in soup.find_all(["div", "section", "article", "main", "figure"]):
        imgs = [t for t in container.find_all("img") if _img_url(t, base)]
        if imgs:
            candidates.append((_score_container(container), container))
    best_selector = ""
    if candidates:
        candidates.sort(key=lambda x: -x[0])
        best_score, best = candidates[0]
        total_imgs = len(soup.find_all("img"))
        best_imgs = best.find_all("img")
        # A container explicitly named comic/reader/chapter/viewer is
        # trusted even for a single paginated page: site chrome images
        # live outside it, so a majority rule would wrongly fall back
        # to the whole document (found live on xkcd: 5 images, only
        # 1 of them the comic itself).
        best_ident = ((best.get("id") or "") + " " + " ".join(best.get("class", []))).lower()
        specific = any(h in best_ident for h in ("comic", "reader", "viewer", "chapter", "manga", "manhwa"))
        if best_score >= 10 and (specific or len(best_imgs) >= max(2, total_imgs // 2)):
            ident = (best.get("id") or "") or ".".join(best.get("class", []))
            best_selector = f"{best.name}#{ident}" if ident else best.name
            urls = []
            for tag in best_imgs:
                u = _img_url(tag, base)
                if u and _is_image_url(u) and not _is_bad(u, tag) and u not in urls:
                    urls.append(u)
            if urls:
                return urls, best_selector
    # Fallback: whole document, in order.
    urls: list[str] = []
    for tag in soup.find_all("img"):
        u = _img_url(tag, base)
        if u and _is_image_url(u) and not _is_bad(u, tag) and u not in urls:
            urls.append(u)
    if not urls:
        urls = _json_image_urls(html, base)
    return urls, best_selector


def find_next_url(html: str, base: str, current: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        rel = " ".join(a.get("rel", [])).lower()
        cls = " ".join(a.get("class", [])).lower()
        text = (a.get_text() or "").strip().lower()
        # "Next Episode" / "Next Chapter" is chapter navigation, not
        # pagination inside a chapter — following it would crawl the
        # whole series (found live on WEBTOON, 2026-11-03).
        if "episode" in text or "chapter" in text or "chap " in text:
            continue
        if rel == "next" or "next" in cls or text in ("next", "next page", ">", ">>", "trang sau", "tiếp"):
            nxt = urljoin(base, a["href"])
            if nxt != current:
                return nxt
    # URL pattern: ?page=N or /page/N or /N at the end
    m = re.search(r"([?&]page=)(\d+)", current)
    if m:
        return current[: m.start(2)] + str(int(m.group(2)) + 1) + current[m.end(2):]
    m = re.search(r"(/page/)(\d+)(/?)$", current)
    if m:
        return current[: m.start(2)] + str(int(m.group(2)) + 1) + (m.group(3) or "")
    return None


def classify(images_per_page: list[int], has_next: bool, container: str) -> str:
    """Layout classification from observed structure."""
    # A dedicated vertical image-list frame (e.g. WEBTOON #_imageList)
    # is vertical even for a 1-2 strip episode (a cover, a short list).
    if "imagelist" in container.lower() or "viewer_img" in container.lower():
        return "vertical"
    if has_next and images_per_page and max(images_per_page) <= 2:
        return "paginated"
    if images_per_page and max(images_per_page) >= 3:
        low = container.lower()
        if any(h in low for h in ("reader", "viewer", "frame")):
            return "single_container"
        if has_next:
            return "single_container"
        return "vertical"
    if images_per_page and max(images_per_page) >= 1 and has_next:
        return "paginated"
    return "unknown"


@dataclass
class ChapterResult:
    url: str
    title: str = ""
    layout: str = "unknown"
    images: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    status: str = "ok"  # ok | bot_wall | error
    bot_evidence: str = ""
    error: str = ""
    container: str = ""
    next_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "layout": self.layout,
            "images_found": len(self.images),
            "images": self.images,
            "pages_fetched": self.pages_fetched,
            "status": self.status,
            "bot_evidence": self.bot_evidence,
            "error": self.error,
            "container": self.container,
            "next_url": self.next_url,
        }


def title_of(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""
