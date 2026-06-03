"""Extract a news article's headline, image and source from a URL or RSS feed.

Two modes:
  - article(url): scrape a single page using Open Graph / Twitter / meta tags.
  - from_rss(feed_url): pull the latest (or Nth) entry from an RSS/Atom feed,
    then enrich it by scraping the entry's page for a better image.
"""
from __future__ import annotations

import calendar
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import feedparser
import requests
from bs4 import BeautifulSoup

# English URL/section slug -> Bangla section label (for the card kicker).
SECTION_MAP = {
    "bangladesh": "বাংলাদেশ", "country": "সারাদেশ", "national": "জাতীয়",
    "politics": "রাজনীতি", "election": "নির্বাচন",
    "international": "আন্তর্জাতিক", "foreign": "আন্তর্জাতিক", "world": "আন্তর্জাতিক",
    "middle-east": "মধ্যপ্রাচ্য", "asia": "এশিয়া",
    "sports": "খেলা", "sport": "খেলা", "cricket": "ক্রিকেট", "football": "ফুটবল",
    "economy": "অর্থনীতি", "business": "অর্থনীতি", "economics": "অর্থনীতি", "bank": "অর্থনীতি",
    "entertainment": "বিনোদন", "lifestyle": "লাইফস্টাইল",
    "technology": "প্রযুক্তি", "tech": "প্রযুক্তি", "science": "বিজ্ঞান",
    "education": "শিক্ষা", "health": "স্বাস্থ্য", "opinion": "মতামত", "feature": "ফিচার",
    "religion": "ধর্ম", "jobs": "চাকরি", "crime": "অপরাধ", "law": "আইন-আদালত",
    "court": "আইন-আদালত", "agriculture": "কৃষি", "weather": "আবহাওয়া",
}
# Bangla section labels we accept straight from an RSS <category> when the URL
# yields nothing (kept tight so we skip topic-tags like "ইরানে ইসরায়েলের হামলা").
_KNOWN_BN_SECTIONS = set(SECTION_MAP.values()) | {"বিশ্ব সংবাদ", "খেলাধুলা"}
_DHAKA_TZ = timezone(timedelta(hours=6))

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 20


@dataclass
class Article:
    title: str
    image_url: str | None
    source: str
    url: str
    description: str = ""
    category: str = ""                       # Bangla section label for the kicker
    published: datetime | None = None        # publish time (Asia/Dhaka), if known

    def __str__(self) -> str:
        img = (self.image_url[:60] + "...") if self.image_url else "(none)"
        return f"Article(source={self.source!r}, title={self.title!r}, image={img})"


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _category(url: str, entry=None) -> str:
    """Best-effort Bangla section label: URL path first, then RSS categories."""
    for seg in urlparse(url).path.lower().split("/"):
        if seg in SECTION_MAP:
            return SECTION_MAP[seg]
    if entry is not None:
        terms = [t.get("term", "") for t in entry.get("tags", [])] or [entry.get("category", "")]
        for term in terms:
            t = _clean(term)
            if t in _KNOWN_BN_SECTIONS:
                return t
    return ""


def _strip_overlay(url: str | None) -> str | None:
    """Drop প্রথম আলো's bottom logo-banner overlay from its CDN (imgix) image URLs."""
    if not url or "overlay=" not in url:
        return url
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("overlay")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q, safe=":,/%"), parts.fragment))


def is_baked_text_image(url: str | None) -> bool:
    """প্রথম আলো audio/video share-thumbnails have the headline burned into the image."""
    return bool(url) and bool(re.search(r"(audio|video)thumbnail", url, re.IGNORECASE))


def _published(entry) -> datetime | None:
    """Parsed publish time as an Asia/Dhaka datetime, or None."""
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return None
    return datetime.fromtimestamp(calendar.timegm(tm), tz=timezone.utc).astimezone(_DHAKA_TZ)


def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
    """Return the first matching <meta> content for property/name keys."""
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return _clean(tag["content"])
    return None


def _source_name(soup: BeautifulSoup, url: str) -> str:
    site = _meta(soup, "og:site_name", "application-name")
    if site:
        return site
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    # "bbc.com" -> "BBC", "prothomalo.com" -> "Prothomalo"
    name = host.split(".")[0]
    return name.upper() if len(name) <= 4 else name.capitalize()


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def article(url: str) -> Article:
    """Scrape a single article page using OG / Twitter / standard meta tags."""
    soup = BeautifulSoup(fetch_html(url), "html.parser")

    title = (
        _meta(soup, "og:title", "twitter:title")
        or _clean(soup.title.string if soup.title else None)
        or (_clean(soup.h1.get_text()) if soup.h1 else "")
    )

    image = _meta(
        soup,
        "og:image:secure_url",
        "og:image",
        "twitter:image",
        "twitter:image:src",
    )
    if image:
        image = _strip_overlay(urljoin(url, image))

    description = _meta(soup, "og:description", "twitter:description", "description")
    source = _source_name(soup, url)

    if not title:
        raise ValueError(f"Could not extract a headline from {url}")

    return Article(
        title=title,
        image_url=image,
        source=source,
        url=url,
        description=description or "",
        category=_category(url),
    )


def _entry_image(entry) -> str | None:
    """Best-effort image straight from an RSS entry, before falling back to scrape."""
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    # Sometimes the image is embedded as <img> in the summary HTML.
    summary = entry.get("summary", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if m:
        return m.group(1)
    return None


def from_rss(feed_url: str, index: int = 0) -> Article:
    """Return the article at `index` (0 = newest) of an RSS/Atom feed.

    Scrapes the entry's page to upgrade the image / source when possible,
    but falls back gracefully to the feed's own data.
    """
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        raise ValueError(f"No entries found in feed {feed_url}")
    if index >= len(feed.entries):
        raise IndexError(
            f"Feed has {len(feed.entries)} entries; index {index} out of range"
        )

    entry = feed.entries[index]
    link = entry.get("link", feed_url)
    feed_title = _clean(entry.get("title", ""))
    feed_image = _entry_image(entry)
    feed_source = _clean(feed.feed.get("title", "")) or _source_name(
        BeautifulSoup("", "html.parser"), link
    )
    category = _category(link, entry)
    published = _published(entry)

    # Try to enrich from the page; keep feed values if scraping fails.
    try:
        scraped = article(link)
        return Article(
            title=scraped.title or feed_title,
            image_url=scraped.image_url or feed_image,
            source=scraped.source or feed_source,
            url=link,
            description=scraped.description,
            category=category,
            published=published,
        )
    except Exception:
        return Article(
            title=feed_title,
            image_url=feed_image,
            source=feed_source,
            url=link,
            description=_clean(entry.get("summary", "")),
            category=category,
            published=published,
        )


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.bbc.com/news"
    if target.endswith((".xml", ".rss")) or "rss" in target or "feed" in target:
        print(from_rss(target))
    else:
        print(article(target))
