"""Curated list of Bangladeshi (Bangla-language) news RSS feeds.

All feeds verified to parse and to enrich with an Open Graph image when the
entry page is scraped. Order matters: the rotation engine cycles through these
top-to-bottom so the page mixes sources evenly. Add/remove freely — keys are
the (Bangla) source labels shown on the card credit and in the source comment.
"""

BD_FEEDS = {
    "প্রথম আলো": "https://www.prothomalo.com/feed/",
    "বাংলা ট্রিবিউন": "https://www.banglatribune.com/feed/",
    "জাগো নিউজ": "https://www.jagonews24.com/rss/rss.xml",
    "ঢাকা পোস্ট": "https://www.dhakapost.com/rss/rss.xml",
    "রাইজিংবিডি": "https://www.risingbd.com/rss/rss.xml",
    "চ্যানেল আই": "https://www.channelionline.com/feed/",
}
