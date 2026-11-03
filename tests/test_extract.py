import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claw_comic.extract import classify, extract_images, find_next_url
from claw_comic.fetcher import detect_bot_wall

VERTICAL = """
<html><head><title>Chap 1 - Vertical</title></head><body>
<img src="/logo.png" class="logo">
<div id="chapter-content">
<img data-src="https://cdn.example.com/c1/p1.jpg">
<img data-src="https://cdn.example.com/c1/p2.jpg">
<img data-src="https://cdn.example.com/c1/p3.jpg">
<img data-src="https://cdn.example.com/c1/p4.jpg">
</div></body></html>
"""

PAGINATED = """
<html><head><title>Chap 2 p1</title></head><body>
<div class="reader"><img src="https://cdn.example.com/c2/p1.jpg"></div>
<a class="next" href="/manga/chap2?page=2">Next</a>
</body></html>
"""

SINGLE_CONTAINER = """
<html><head><title>Chap 3 - All pages</title></head><body>
<div class="reader-viewer">
<img src="https://cdn.example.com/c3/01.jpg">
<img src="https://cdn.example.com/c3/02.jpg">
<img src="https://cdn.example.com/c3/03.jpg">
<img src="https://cdn.example.com/c3/04.jpg">
<img src="https://cdn.example.com/c3/05.jpg">
</div></body></html>
"""


class TestExtract(unittest.TestCase):
    def test_vertical(self):
        urls, container = extract_images(VERTICAL, "https://example.com/")
        self.assertEqual(len(urls), 4)  # logo filtered out
        self.assertTrue(urls[0].endswith("p1.jpg"))
        self.assertEqual(classify([len(urls)], False, container), "vertical")

    def test_paginated(self):
        urls, _ = extract_images(PAGINATED, "https://example.com/")
        self.assertEqual(len(urls), 1)
        nxt = find_next_url(PAGINATED, "https://example.com/", "https://example.com/manga/chap2?page=1")
        self.assertIn("page=2", nxt)
        self.assertEqual(classify([1], True, ""), "paginated")

    def test_single_container(self):
        urls, container = extract_images(SINGLE_CONTAINER, "https://example.com/")
        self.assertEqual(len(urls), 5)
        self.assertEqual(classify([len(urls)], False, container), "single_container")

    def test_bot_wall_detected_not_bypassed(self):
        html = "<html><head><title>Just a moment...</title></head><body>Checking your browser</body></html>"
        self.assertTrue(detect_bot_wall(503, html))
        self.assertTrue(detect_bot_wall(403, "<html>forbidden</html>"))

    def test_split_long(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        import tempfile
        from claw_comic.split_long import split_long_image
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "long.png"
            img = Image.new("RGB", (100, 660), "white")
            # black page blocks separated by white gaps
            for top in (0, 220, 440):
                for y in range(top, top + 200):
                    for x in range(100):
                        img.putpixel((x, y), (20, 20, 20))
            img.save(p)
            pieces = split_long_image(p, Path(td) / "out")
            self.assertEqual(len(pieces), 3)


if __name__ == "__main__":
    unittest.main()
