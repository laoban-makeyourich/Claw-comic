"""Manual-verification handoff for bot walls.

Problem: the scraper cannot (and must not) solve a captcha. When a
chapter hits a bot wall, the only legitimate way forward is the
human who already has that exact chapter open in their own browser.

Flow implemented here — mirroring the browser handoff used before:

1. STOP. The scraper writes `handoff.json` (status
   `awaiting_user`) and prints a warning. It does not retry, does
   not reload, does not open a duplicate tab, and does not touch
   the user's session or cookies.
2. MATCH. The user (or Muse, from its browser window list) supplies
   the currently open tabs as JSON (`--tabs-file`). `find_matching_tab`
   only allows a handoff when one of those tabs holds *the same*
   chapter URL. Tracking parameters (utm_*, serviceZone,
   webtoon-platform-redirect, readingLanguageCode) are ignored for
   matching, but the chapter identity (host + path + title_no /
   episode_no / dlid / chapter id) must match. If no tab matches,
   the handoff is refused with a clear message: open the exact
   chapter URL first, do not open a second copy.
3. USER PASSES. In that exact tab only, the user ticks the captcha
   / challenge themselves, waits for the Success state, and does
   NOT reload or close the tab.
4. RESUME. Two honest resume paths, neither of which steals a
   session:
   a) `--html-file <saved page>`: after passing, the user saves
      the chapter page from that tab (or copies its HTML) and the
      tool extracts images from that file — no new fetch, no
      cookie reuse. This is the reliable path, because solving a
      challenge in the user's browser does not unblock the
      scraper's separate session.
   b) `--resume-from handoff.json`: the tool retries the fetch
      exactly once. If it is still a bot wall, it stops again —
      it does not loop, and it does not claim success.

A handoff never exports, copies, or reuses cookies, tokens, or
credentials from the user's browser.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlparse, urlunparse

# Query keys that identify a chapter — kept for matching.
CHAPTER_KEYS = ("title_no", "episode_no", "dlid", "chapter", "chapter_id", "id", "comicpage")
# Tracking / redirect noise — ignored for matching.
IGNORED_KEYS = (
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "servicezone", "webtoon-platform-redirect", "readinglanguagecode",
)


def normalize_url(url: str) -> str:
    """Host + path + chapter-identifying query, lowercased, no trailing slash."""
    p = urlparse(url.strip())
    query = [(k.lower(), v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() not in IGNORED_KEYS]
    # Keep only chapter keys when present; otherwise keep the full query.
    chapter_q = [(k, v) for k, v in query if k in CHAPTER_KEYS]
    keep = chapter_q if chapter_q else query
    keep.sort()
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", "&".join(f"{k}={v}" for k, v in keep), ""))


def urls_match(target: str, tab_url: str) -> bool:
    """True when a tab holds the same chapter as the target URL."""
    try:
        t, b = normalize_url(target), normalize_url(tab_url)
    except Exception:
        return False
    if t == b:
        return True
    # Same host + path, and the same chapter id in the query, is a match
    # even if one side carries extra (non-tracking) parameters.
    pt, pb = urlparse(t), urlparse(b)
    if pt.netloc == pb.netloc and pt.path == pb.path:
        qt = dict(parse_qsl(pt.query))
        qb = dict(parse_qsl(pb.query))
        shared = [k for k in CHAPTER_KEYS if k in qt and k in qb]
        if shared and all(qt[k] == qb[k] for k in shared):
            return True
    return False


@dataclass
class Tab:
    window: str = ""
    title: str = ""
    url: str = ""


def load_tabs(path: str | Path) -> list[Tab]:
    """Load open tabs from JSON: [{"window": ..., "title": ..., "url": ...}, ...]."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("tabs", [])
    return [Tab(str(t.get("window", "")), str(t.get("title", "")), str(t.get("url", ""))) for t in items if t.get("url")]


def find_matching_tab(tabs: list[Tab], target_url: str) -> Tab | None:
    for tab in tabs:
        if urls_match(target_url, tab.url):
            return tab
    return None


WARNING_TEMPLATE = """\
⚠️  BOT WALL — HỆ THỐNG ĐÃ DỪNG, KHÔNG TỰ VƯỢT CAPTCHA
URL cần scan: {url}
Bằng chứng chặn: {evidence}

Hệ thống KHÔNG tự tick captcha, KHÔNG dùng cookie/token của bạn,
KHÔNG mở tab mới trùng lặp, KHÔNG tải lại trang.

Cách tiếp tục (chỉ làm trong đúng tab đã khớp, nếu có):
  1. Mở đúng tab này: {tab_desc}
  2. Tự tick / hoàn thành captcha trong tab đó, chờ trạng thái Success.
  3. KHÔNG tải lại trang, KHÔNG đóng tab, KHÔNG mở thêm tab trùng.
  4. Sau khi pass, lưu trang đó thành file HTML rồi chạy lại:
       python -m claw_comic.cli "{url}" --html-file <file-ban-vua-luu> --metadata-only
     Hoặc thử lại 1 lần (thường vẫn bị chặn nếu session khác nhau):
       python -m claw_comic.cli "{url}" --resume-from {handoff_path} --metadata-only
"""


def write_handoff(url: str, evidence: str, out_dir: str | Path, matching_tab: Tab | None) -> Path:
    """Write handoff.json and return its path. Never includes cookies/tokens."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "status": "awaiting_user",
        "url": url,
        "bot_evidence": evidence,
        "matching_tab": (
            {"window": matching_tab.window, "title": matching_tab.title, "url": matching_tab.url}
            if matching_tab else None
        ),
        "instructions": [
            "Do NOT reload the page, close the tab, or open a duplicate tab.",
            "Pass the captcha yourself in the matched tab only, and wait for Success.",
            "Then resume with --html-file <saved page> (reliable) or --resume-from handoff.json (one retry).",
            "No cookies, tokens, or credentials are read from your browser.",
        ],
    }
    path = out_dir / "handoff.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tab_desc = (
        f"[{matching_tab.window}] {matching_tab.title} — {matching_tab.url}"
        if matching_tab
        else "(chưa tìm thấy tab nào khớp — hãy mở đúng URL truyện trước, rồi chạy lại với --tabs-file)"
    )
    print(WARNING_TEMPLATE.format(url=url, evidence=evidence, tab_desc=tab_desc, handoff_path=path), file=__import__("sys").stderr)
    return path
