import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claw_comic.adblock import is_ad, is_ad_host, is_ad_url, filter_ad_images
from claw_comic.extract import extract_images
from claw_comic.handoff import Tab, find_matching_tab, normalize_url, urls_match

AD_HTML = """
<html><body><div class="reader">
<img src="https://cdn.example.com/c1/p1.jpg">
<img src="https://doubleclick.net/ad/banner.jpg">
<img src="https://cdn.example.com/ads/promo.png">
<img src="https://cdn.example.com/c1/p2.jpg">
</div>
<div class="ads-container">
<img src="https://cdn.example.com/clean-looking.jpg">
</div>
<a href="https://popads.net/click"><img src="https://cdn.example.com/c1/p3.jpg"></a>
</body></html>
"""


class TestAdblock(unittest.TestCase):
    def test_ad_host(self):
        self.assertTrue(is_ad_host("https://doubleclick.net/x.jpg"))
        self.assertTrue(is_ad_host("https://sub.popads.net/x.jpg"))
        self.assertFalse(is_ad_host("https://cdn.example.com/x.jpg"))

    def test_ad_url_and_filter(self):
        self.assertTrue(is_ad_url("https://cdn.example.com/ads/promo.png"))
        self.assertFalse(is_ad_url("https://cdn.example.com/c1/p1.jpg"))
        self.assertEqual(
            filter_ad_images(["https://cdn.example.com/c1/p1.jpg", "https://doubleclick.net/a.jpg"]),
            ["https://cdn.example.com/c1/p1.jpg"],
        )

    def test_extract_drops_ads(self):
        urls, _ = extract_images(AD_HTML, "https://example.com/")
        # p1, p2 kept; doubleclick, /ads/, ads-container image dropped.
        # The popads-wrapped p3 is dropped because its link is an ad host.
        self.assertEqual(urls, ["https://cdn.example.com/c1/p1.jpg", "https://cdn.example.com/c1/p2.jpg"])


class TestHandoff(unittest.TestCase):
    def test_exact_and_tracking_param_match(self):
        target = "https://www.webtoons.com/en/canvas/x/ep/viewer?title_no=123&episode_no=2&serviceZone=GLOBAL"
        tabs = [Tab("W1", "Other", "https://example.com/"), Tab("W1", "Ep", "https://www.webtoons.com/en/canvas/x/ep/viewer?title_no=123&episode_no=2")]
        self.assertIsNotNone(find_matching_tab(tabs, target))

    def test_no_match_different_episode(self):
        target = "https://www.webtoons.com/en/canvas/x/ep/viewer?title_no=123&episode_no=2"
        tabs = [Tab("W1", "Ep3", "https://www.webtoons.com/en/canvas/x/ep/viewer?title_no=123&episode_no=3")]
        self.assertIsNone(find_matching_tab(tabs, target))

    def test_no_match_different_site(self):
        self.assertFalse(urls_match("https://comicbookplus.com/?dlid=15452", "https://comicbookplus.com/?dlid=99999"))
        self.assertTrue(urls_match("https://comicbookplus.com/?dlid=15452", "https://comicbookplus.com/?dlid=15452&utm_source=x"))

    def test_normalize(self):
        self.assertEqual(normalize_url("https://Example.com/Path/?b=2&a=1&utm_source=x"), "https://example.com/Path?a=1&b=2")


if __name__ == "__main__":
    unittest.main()
