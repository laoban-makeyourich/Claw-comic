"""Ad blocking for comic extraction.

Goal, as requested by the user: no ad images should ever end up in
the chapter image list, even when a reader page injects them between
real pages.

Three layers, all conservative (a real comic page is never dropped
just for looking like an ad):

1. Host blocklist — well-known ad / tracking / popunder networks.
   A URL on one of these hosts is an ad, whatever its filename is.
2. Path / filename signals — /ads/, ad-banner, popunder, sponsored,
   tracking pixel, 1x1.gif-style names. These only fire when the
   signal is in the image URL or in the img tag's own id/class.
3. Container signals — an img inside a div/section whose id/class
   says ads, advertisement, sponsored, popunder, or banner-ad is
   dropped even if its own URL looks clean. This catches reader
   pages that serve ads from their own CDN.

What this module does NOT do: it does not hide ads in the user's
browser, it does not modify a site, and it does not block a whole
domain — only image candidates during extraction, plus (in
browser mode) network requests to ad hosts while rendering.
"""

from __future__ import annotations

from urllib.parse import urlparse

AD_DOMAINS = (
    # General ad networks
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "adsystem.com", "adservice.google.com", "adnxs.com", "criteo.com",
    "taboola.com", "outbrain.com", "mgid.com", "revcontent.com",
    # Pop / push ad networks common on reader sites
    "popads.net", "popcash.net", "adcash.com", "propellerads.com",
    "adsterra.com", "exoclick.com", "trafficjunky.com", "juicyads.com",
    "adform.net", "smartadserver.com", "rubiconproject.com",
    "pubmatic.com", "openx.net", "moatads.com", "scorecardresearch.com",
)

AD_PATH_SIGNALS = (
    "/ads/", "/ad/", "/advert", "/sponsored", "/popunder", "/pop-up",
    "ad-banner", "ad_banner", "banner-ad", "banner_ad", "ad-slot",
    "adslot", "sponsored-", "sponsor-", "tracking-pixel", "pixel.gif",
    "1x1.gif", "beacon.gif", "blank-ad",
)

AD_TAG_SIGNALS = (
    "ads", "advert", "advertisement", "sponsored", "popunder",
    "banner-ad", "banner_ad", "ad-slot", "adslot", "ad-container",
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_ad_host(url: str) -> bool:
    host = _host(url)
    return any(host == d or host.endswith("." + d) for d in AD_DOMAINS)


def is_ad_url(url: str) -> bool:
    """True if the URL itself looks like an ad/tracking image."""
    if is_ad_host(url):
        return True
    low = url.lower()
    return any(s in low for s in AD_PATH_SIGNALS)


def _tag_signals(tag) -> str:
    try:
        cls = " ".join(tag.get("class", [])).lower()
        ident = (tag.get("id") or "").lower()
    except Exception:
        return ""
    return f" {cls} {ident} "


def is_ad_tag(tag) -> bool:
    """True if the img tag, its link, or an ancestor says 'ad'."""
    node = tag
    for _ in range(4):  # img -> parent -> grandparent -> great-grandparent
        if node is None:
            break
        sig = _tag_signals(node)
        if any(s in sig for s in AD_TAG_SIGNALS):
            return True
        # An <a> wrapping the image that points at an ad host is an ad.
        if getattr(node, "name", None) == "a" and node.get("href") and is_ad_host(node["href"]):
            return True
        node = getattr(node, "parent", None)
    return False


def is_ad(url: str, tag=None) -> bool:
    if is_ad_url(url):
        return True
    if tag is not None and is_ad_tag(tag):
        return True
    return False


def filter_ad_images(urls: list[str]) -> list[str]:
    """Drop ad URLs from a plain list (no tags available)."""
    return [u for u in urls if not is_ad_url(u)]
