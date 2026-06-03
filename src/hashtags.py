"""100 Bangladesh news hashtags, used 5 per post in rotating blocks.

Post 1 -> tags 1-5, post 2 -> 6-10, ... post 20 -> 96-100, then it wraps.
`#thecitizenpost` is added to every post on top of the rotating 5 (see main.py).
"""

BRAND_TAG = "thecitizenpost"        # always included, on top of the rotating 5
PER_POST = 5

HASHTAGS = [
    # core BD news (1-20)
    "bangladesh", "bangladeshnews", "bdnews", "newsbangladesh", "banglanews",
    "dhaka", "bd", "ঢাকা", "বাংলাদেশ", "সংবাদ",
    "খবর", "বাংলাখবর", "তাজাখবর", "ব্রেকিংনিউজ", "সর্বশেষসংবাদ",
    "দেশেরখবর", "জাতীয়", "অনলাইননিউজ", "সংবাদমাধ্যম", "গণমাধ্যম",
    # politics / nation (21-40)
    "bdpolitics", "bangladeshpolitics", "politics", "election", "nirbachon",
    "নির্বাচন", "রাজনীতি", "সরকার", "জাতীয়সংসদ", "ভোট",
    "আওয়ামীলীগ", "বিএনপি", "জামায়াত", "আন্দোলন", "প্রশাসন",
    "policy", "parliament", "government", "vote", "democracy",
    # cities / geography (41-55)
    "chittagong", "chattogram", "sylhet", "khulna", "rajshahi",
    "barishal", "rangpur", "mymensingh", "চট্টগ্রাম", "সিলেট",
    "খুলনা", "রাজশাহী", "দেশজুড়ে", "স্থানীয়সংবাদ", "সারাদেশ",
    # economy / business (56-68)
    "economy", "business", "bdbusiness", "অর্থনীতি", "ব্যবসা",
    "বাণিজ্য", "শেয়ারবাজার", "ব্যাংক", "রেমিট্যান্স", "বাজেট",
    "market", "trade", "taka",
    # sports / entertainment (69-80)
    "cricket", "bdcricket", "tigers", "football", "ক্রিকেট",
    "খেলা", "ফুটবল", "বিনোদন", "ঢালিউড", "সংস্কৃতি",
    "sports", "entertainment",
    # topics (81-90)
    "weather", "আবহাওয়া", "শিক্ষা", "স্বাস্থ্য", "আইন",
    "অপরাধ", "দুর্নীতি", "আন্তর্জাতিক", "প্রযুক্তি", "কৃষি",
    # engagement (91-100)
    "viral", "trending", "ভাইরাল", "ট্রেন্ডিং", "আজকেরখবর",
    "এইমাত্র", "চলমান", "বিশেষপ্রতিবেদন", "সরাসরি", "আপডেট",
]

assert len(HASHTAGS) == 100, f"expected 100 hashtags, got {len(HASHTAGS)}"


def block_at(cursor: int) -> list[str]:
    """Return the 5 hashtags starting at `cursor` (wrapping around the 100)."""
    n = len(HASHTAGS)
    c = cursor % n
    return [HASHTAGS[(c + i) % n] for i in range(PER_POST)]


def render(cursor: int) -> str:
    """'#thecitizenpost #tag1 #tag2 #tag3 #tag4 #tag5' for the given block."""
    tags = [BRAND_TAG] + block_at(cursor)
    return " ".join(f"#{t}" for t in tags)
