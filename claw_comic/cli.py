"""CLI: python -m claw_comic.cli <url> [--metadata-only] [--out DIR] ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .download import download_images
from .extract import ChapterResult, classify, extract_images, title_of
from .fetcher import origin
from .handoff import find_matching_tab, load_tabs, write_handoff
from .scraper import scrape


def _report(result: ChapterResult, out_dir: Path | None) -> None:
    data = result.to_dict()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="claw-comic")
    ap.add_argument("url", nargs="?", help="chapter URL")
    ap.add_argument("--scan-file", help="file with one URL per line")
    ap.add_argument("--mode", choices=["auto", "vertical", "paginated", "single_container"], default="auto")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--metadata-only", action="store_true", help="do not download images")
    ap.add_argument("--browser", action="store_true", help="render with Playwright (JS/lazy-load)")
    ap.add_argument("--split-long", action="store_true", help="split downloaded tall images at blank gaps")
    ap.add_argument("--handoff", action="store_true", help="on bot_wall, write handoff.json and warn instead of just stopping")
    ap.add_argument("--tabs-file", help="JSON file of currently open tabs [{window,title,url}] for handoff matching")
    ap.add_argument("--html-file", help="saved chapter page HTML (after you passed the captcha yourself) — extract from this instead of fetching")
    ap.add_argument("--resume-from", help="handoff.json from a previous bot_wall run — retry the fetch exactly once")
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)

    if args.resume_from:
        print(f"Resuming from {args.resume_from} — one retry only; if it is still a bot wall, it stops again.", file=sys.stderr)

    urls: list[str] = []
    if args.scan_file:
        urls = [l.strip() for l in Path(args.scan_file).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    elif args.url:
        urls = [args.url]
    else:
        ap.error("need a URL or --scan-file")

    def _do_handoff(result: ChapterResult) -> None:
        matching = None
        if args.tabs_file:
            try:
                matching = find_matching_tab(load_tabs(args.tabs_file), result.url)
            except Exception as exc:
                print(f"tabs-file error: {exc}", file=sys.stderr)
        if matching:
            print(f"Handoff: matched open tab [{matching.window}] {matching.title}", file=sys.stderr)
        else:
            print("Handoff: no open tab matches this chapter URL — open the exact chapter first, do not open a duplicate.", file=sys.stderr)
        write_handoff(result.url, result.bot_evidence, Path(args.out), matching)
        _report(result, Path(args.out))

    for url in urls:
        print(f"== {url}", file=sys.stderr)
        if args.html_file:
            # Resume path (a): extract from the page the user saved
            # after passing the captcha themselves in their own tab.
            html = Path(args.html_file).read_text(encoding="utf-8", errors="ignore")
            images, container = extract_images(html, url)
            result = ChapterResult(url=url, title=title_of(html), images=images, container=container, pages_fetched=1)
            result.layout = args.mode if args.mode != "auto" else classify([len(images)], False, container)
            print(f"Extracted {len(images)} images from saved HTML (ad-filtered).", file=sys.stderr)
            _report(result, None if args.metadata_only else Path(args.out))
            continue
        if args.browser:
            from .browser import render_html
            from .extract import extract_images as _ex
            try:
                html, bot_wall, evidence = render_html(url)
            except RuntimeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            result = ChapterResult(url=url, title=title_of(html))
            if bot_wall:
                result.status, result.bot_evidence = "bot_wall", evidence
                if args.handoff:
                    _do_handoff(result)
                    continue
            else:
                images, container = _ex(html, url)
                result.images, result.container = images, container
                result.pages_fetched = 1
                result.layout = args.mode if args.mode != "auto" else classify([len(images)], False, container)
            _report(result, None if args.metadata_only else Path(args.out))
        else:
            result = scrape(url, mode=args.mode, max_pages=args.max_pages, delay=args.delay)
            if result.status == "bot_wall":
                print(f"BOT WALL: {result.bot_evidence} — stopping, not bypassing.", file=sys.stderr)
                if args.handoff:
                    _do_handoff(result)
                else:
                    _report(result, None)
                continue
            if result.status != "ok":
                print(f"error: {result.error}", file=sys.stderr)
                _report(result, None)
                continue
            if args.metadata_only:
                _report(result, None)
            else:
                out_dir = Path(args.out)
                written = download_images(result.images, out_dir, referer=origin(url), delay=0.5)
                print(f"downloaded {len(written)} images to {out_dir}", file=sys.stderr)
                if args.split_long:
                    from .split_long import split_long_image
                    for f in written:
                        try:
                            pieces = split_long_image(f, out_dir / "split")
                            print(f"split {f} -> {len(pieces)} pieces", file=sys.stderr)
                        except RuntimeError as exc:
                            print(f"split skipped: {exc}", file=sys.stderr)
                _report(result, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
