"""Download chapter images in order, with the chapter's Referer."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import requests


def download_images(
    images: list[str],
    out_dir: str | Path,
    *,
    session: requests.Session | None = None,
    referer: str | None = None,
    delay: float = 0.5,
) -> list[str]:
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    if referer:
        sess.headers["Referer"] = referer
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for i, url in enumerate(images, start=1):
        ext = urlparse(url).path.rsplit(".", 1)[-1].lower().split("?")[0]
        if ext not in ("jpg", "jpeg", "png", "webp", "gif", "avif"):
            ext = "jpg"
        dest = out_dir / f"{i:03d}.{ext}"
        try:
            with sess.get(url, timeout=30, stream=True) as r:
                if r.status_code != 200:
                    continue
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(64 * 1024):
                        f.write(chunk)
            written.append(str(dest))
        except requests.RequestException:
            continue
        if delay:
            time.sleep(delay)
    return written
