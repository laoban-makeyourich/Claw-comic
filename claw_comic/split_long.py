"""Split one tall image that contains several stacked pages.

Use case: the "one frame holds many pages" layout where a single
file is actually several pages stacked vertically with a blank
(or near-uniform) gap between them.

Method: scan rows; a row counts as a gap when >=98% of its pixels
are near-white (or near-black). Cut at gaps, drop slices shorter
than 100px. Requires Pillow, which is optional.
"""

from __future__ import annotations

from pathlib import Path


def split_long_image(path: str | Path, out_dir: str | Path, *, min_slice: int = 100) -> list[str]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for --split-long: pip install Pillow") from exc

    img = Image.open(path).convert("L")
    w, h = img.size
    pixels = img.load()
    # Sample every 4th x pixel for speed.
    xs = list(range(0, w, max(1, w // 200)))
    gaps: list[int] = []
    for y in range(h):
        light = sum(1 for x in xs if pixels[x, y] > 245)
        dark = sum(1 for x in xs if pixels[x, y] < 10)
        if light / len(xs) >= 0.98 or dark / len(xs) >= 0.98:
            gaps.append(y)
    # Collapse consecutive gap rows into a single cut point.
    cuts = [0]
    prev = None
    for y in gaps:
        if prev is None or y - prev > 5:
            if y - cuts[-1] >= min_slice:
                cuts.append(y)
        prev = y
    if h - cuts[-1] >= min_slice:
        cuts.append(h)
    elif len(cuts) > 1:
        cuts[-1] = h

    orig = Image.open(path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem
    written: list[str] = []
    for i in range(len(cuts) - 1):
        top, bottom = cuts[i], cuts[i + 1]
        if bottom - top < min_slice:
            continue
        piece = orig.crop((0, top, w, bottom))
        dest = out_dir / f"{stem}_p{i+1:03d}.png"
        piece.save(dest)
        written.append(str(dest))
    return written
