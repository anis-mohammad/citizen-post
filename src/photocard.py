"""Render a 720x900 (4:5) news photocard from an Article.

Layout (top -> bottom):
  - Full-bleed article image, cover-cropped, darkened with a bottom gradient.
  - Top brand bar: source name + a small accent rule.
  - Bottom block: wrapped headline + date footer.

If the article has no image, a clean dark gradient is used instead.
"""
from __future__ import annotations

import datetime as _dt
import io
import math
import os
from dataclasses import dataclass

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .scraper import Article, HEADERS, TIMEOUT

W, H = 1000, 1000             # default card size (1:1 square)
_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
FONT_PATH = os.path.join(_ASSETS, "fonts", "Montserrat.ttf")           # Latin: brand, LIVE, date
BN_FONT_PATH = os.path.join(_ASSETS, "fonts", "NotoSansBengali.ttf")   # Bangla: headline + credit
LOGO_PATH = os.path.join(_ASSETS, "logo.png")   # optional; used if present

# Brand colours (tweak freely).
ACCENT = (230, 30, 45)        # red accent bar
TEXT = (255, 255, 255)
MUTED = (210, 210, 215)

BRAND = "THE CITIZEN POST"    # main brand/logo shown on every card
PANEL = (18, 19, 26)          # solid dark panel behind the headline


@dataclass
class CardStyle:
    accent: tuple = ACCENT
    brand: str = BRAND                  # main brand/logo (text fallback)
    show_credit: bool = True            # show small "SOURCE: ..." credit
    headline_size: int | None = None    # px; auto-scaled to width when None
    max_chars_per_line: int = 22
    width: int = W
    height: int | None = None            # None = auto: square, grown by a standfirst
    show_kicker: bool = True             # category pill above the headline
    show_standfirst: bool = False        # one-line summary under the headline (off)


def _font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def _bn_font(size: int, weight: str = "Medium") -> ImageFont.FreeTypeFont:
    """Bengali-capable font (Noto Sans Bengali) for Bangla headlines + credit."""
    f = ImageFont.truetype(BN_FONT_PATH, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_BN_MONTHS = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
              "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"]


def _bn_num(n) -> str:
    """Western digits -> Bangla digits ('2026' -> '২০২৬')."""
    return str(n).translate(_BN_DIGITS)


def _bn_date(dt) -> str:
    """Format a date as Bangla '৪ জুন ২০২৬' (today if dt is None)."""
    import datetime as _d
    dt = dt or _d.datetime.now()
    return f"{_bn_num(dt.day)} {_BN_MONTHS[dt.month - 1]} {_bn_num(dt.year)}"


def _load_image(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize + center-crop to exactly fill w x h (object-fit: cover)."""
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        new_h = h
        new_w = int(h * src_ratio)
    else:
        new_w = w
        new_h = int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _contain(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize to fit fully within w x h, preserving aspect (object-fit: contain)."""
    scale = min(w / img.width, h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)


def _fit_with_blur(img: Image.Image, w: int, h: int, gap_reduce: float = 0.0) -> Image.Image:
    """Show the image over a blurred, darkened cover background.

    gap_reduce interpolates between contain (0.0 = full image, max letterbox)
    and cover (1.0 = no gap, max crop). gap_reduce=0.4 shrinks the letterbox by
    exactly 40%, center-cropping the overflowing dimension.
    """
    bg = _cover(img, w, h).filter(ImageFilter.GaussianBlur(max(8, int(0.04 * w))))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (8, 8, 10)), 0.45)

    contain = min(w / img.width, h / img.height)
    cover = max(w / img.width, h / img.height)
    scale = contain + (cover - contain) * max(0.0, min(1.0, gap_reduce))
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    fg = img.resize((nw, nh), Image.LANCZOS)
    if nw > w or nh > h:                       # center-crop any overflow
        left, top = max(0, (nw - w) // 2), max(0, (nh - h) // 2)
        fg = fg.crop((left, top, left + min(nw, w), top + min(nh, h)))
        nw, nh = fg.size
    # centre the photo: equal gap top and bottom
    y_off = (h - nh) // 2
    bg.paste(fg, ((w - nw) // 2, y_off))
    return bg, y_off                            # y_off = where the sharp image starts


def _top_scrim(w: int, height: int, peak: int = 170) -> Image.Image:
    """Dark gradient at the very top (for logo legibility over light photos)."""
    grad = Image.new("L", (1, height), 0)
    for y in range(height):
        grad.putpixel((0, y), int(peak * (1 - y / height) ** 1.4))
    grad = grad.resize((w, height))
    overlay = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    overlay.putalpha(grad)
    return overlay


def _wrap_px(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Word-wrap so each line fits within max_w pixels."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _draw_wordmark(draw, style: "CardStyle", margin: int, top: int, brand_size: int, s: float) -> None:
    """Draw the text brand 'THE CITIZEN POST' with a red accent bar, at vertical `top`."""
    brand_font = _font(brand_size, "ExtraBold")
    bar_w = max(4, int(14 * s))
    draw.rectangle(
        [margin, top, margin + bar_w, top + int(56 * s)], fill=style.accent
    )
    draw.text(
        (margin + bar_w + int(20 * s), top + int(2 * s)),
        style.brand.upper(),
        font=brand_font,
        fill=TEXT,
    )


def _blink_alpha(t: float, hz: float = 1.0) -> float:
    """Pulsing 0.15..1.0 opacity for the live icon (squared dip = crisper blink)."""
    base = 0.5 + 0.5 * math.cos(2 * math.pi * hz * t)   # 1 -> 0 -> 1
    return 0.15 + 0.85 * (base ** 2)


def _draw_live_icon(base: Image.Image, geom, color, alpha: float) -> Image.Image:
    """Composite an anti-aliased 'record' icon (ring + inner dot) onto a copy of base."""
    cx, cy, R, ring_th, inner_r = geom
    ss = 4
    box = R * 2 + 2
    big = box * ss
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = (*color, int(255 * alpha))
    d.ellipse([ss, ss, big - ss, big - ss], outline=col, width=ring_th * ss)
    c = big // 2
    rr = inner_r * ss
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=col)
    layer = layer.resize((box, box), Image.LANCZOS)
    out = base.convert("RGBA")
    out.alpha_composite(layer, (cx - R - 1, cy - R - 1))
    return out.convert("RGB")


_STOP = {"THE", "A", "AN", "OF", "IN", "ON", "AT", "TO", "FOR", "AND", "OR",
         "AS", "IS", "BY", "WITH", "FROM", "OVER", "AFTER", "AMID"}


def _is_emphasis(word: str) -> bool:
    """Heuristic: bold proper nouns / acronyms (capitalised, non-stopword)."""
    core = word.strip(".,;:!?'\"’“”()-—–")
    if not core:
        return False
    if core.isupper() and len(core) > 1:        # acronyms: UN, US, FBI
        return True
    if core[0].isupper() and core.upper() not in _STOP:
        return True
    return False


def _layout_headline(title, max_w, base_font, bold_font):
    """Wrap into lines of (word, font) tuples, bolding emphasis words."""
    space_w = base_font.getlength(" ")
    lines, cur, cur_w = [], [], 0.0
    for word in title.split():
        f = bold_font if _is_emphasis(word) else base_font
        ww = f.getlength(word)
        add = ww + (space_w if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
            add = ww
        cur.append((word, f))
        cur_w += add
    if cur:
        lines.append(cur)
    return lines or [[("", base_font)]]


def _compose(article: Article, style: CardStyle):
    """Render everything except the blinking icon. Returns (image, icon_geom)."""
    w = style.width
    s = w / 1080.0                       # scale factor relative to the 1080 baseline

    margin = int(70 * s)
    brand_size = max(14, int(40 * s))
    foot_size = max(11, int(24 * s))
    pad = margin
    gap = int(20 * s)
    space_w_extra = int(2 * s)
    text_w = w - 2 * margin

    # --- "সর্বশেষ" badge + optional category pill share one row ---
    R = max(8, int(17 * s))              # record-icon outer radius
    ring_th = max(2, int(4 * s))
    inner_r = max(3, int(7 * s))
    live_font = _bn_font(int(34 * s), "ExtraBold")
    badge_h = live_font.getbbox("সর্বশেষ")[3]

    kicker = article.category if style.show_kicker else ""
    kicker_font = _bn_font(int(28 * s), "SemiBold")
    pill_pad = int(16 * s)
    pill_h = (kicker_font.getbbox("আমিগ")[3] + 2 * int(9 * s)) if kicker else 0
    row_h = max(2 * R, badge_h, pill_h)

    # red footer bar (date + photo credit)
    bar_h = int(52 * s)
    accent_h = max(2, int(6 * s))

    # --- fit the headline (cap at 6 lines) ---
    hl_size = style.headline_size or int(56 * s)
    min_size = int(30 * s)
    while True:
        base_font = _bn_font(hl_size, "Medium")
        bold_font = _bn_font(hl_size, "SemiBold")
        lines = _layout_headline(article.title, text_w, base_font, bold_font)
        if len(lines) <= 6 or hl_size <= min_size:
            break
        hl_size -= max(1, int(3 * s))
    line_h = int(hl_size * 1.42)        # Bangla matras sit above/below — needs room
    block_h = line_h * len(lines)

    # --- optional standfirst (≤2 summary lines) under the headline ---
    desc = article.description if style.show_standfirst else ""
    std_font = _bn_font(int(30 * s), "Regular")
    std_lines, std_block_h, std_gap, std_line_h = [], 0, 0, 0
    if desc:
        std_line_h = int(30 * s * 1.5)
        std_gap = int(16 * s)
        wrapped = _wrap_px(desc, std_font, text_w)
        std_lines = wrapped[:2]
        if len(wrapped) > 2:            # truncate with an ellipsis
            last = std_lines[-1]
            while last and std_font.getlength(last + "…") > text_w:
                last = last[:-1]
            std_lines[-1] = last.rstrip() + "…"
        std_block_h = std_line_h * len(std_lines)

    # --- canvas height: square by default; grown by exactly the standfirst, so
    #     the photo area (and its letterbox gap) is identical with or without it. ---
    h = style.height or (w + std_gap + std_block_h)
    bar_top = h - bar_h

    live_top_gap = int(40 * s)
    text_block_h = row_h + gap + block_h + std_gap + std_block_h
    row_top = bar_top - pad - text_block_h
    img_h = max(1, row_top - live_top_gap - accent_h)

    # --- compose: full photo on top (centred), panel below ---
    card = Image.new("RGB", (w, h), PANEL)
    src = _load_image(article.image_url)
    if src is not None:
        photo, photo_top = _fit_with_blur(src, w, img_h, gap_reduce=0.0)
        card.paste(photo, (0, 0))
    else:
        card.paste(Image.new("RGB", (w, img_h), (30, 31, 38)), (0, 0))
        photo_top = 0
    card = card.convert("RGBA")
    card.alpha_composite(_top_scrim(w, int(160 * s)))
    draw = ImageDraw.Draw(card)

    # accent line directly above the title + red footer bar
    draw.rectangle([0, img_h, w, img_h + accent_h], fill=style.accent)
    draw.rectangle([0, bar_top, w, h], fill=style.accent)

    # --- top brand: anchored onto the sharp image (below the top gap) ---
    brand_top = max(margin, photo_top + int(22 * s))
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            target_h = int(64 * s)
            target_w = int(logo.width * (target_h / logo.height))
            logo = logo.resize((target_w, target_h), Image.LANCZOS)
            card.alpha_composite(logo, (margin, brand_top))
        except Exception:
            _draw_wordmark(draw, style, margin, brand_top, brand_size, s)
    else:
        _draw_wordmark(draw, style, margin, brand_top, brand_size, s)

    # --- badge row: ● সর্বশেষ + category pill ---
    icon_cx = margin + R
    icon_cy = row_top + row_h // 2
    icon_geom = (icon_cx, icon_cy, R, ring_th, inner_r)
    live_x = margin + 2 * R + int(16 * s)
    draw.text((live_x, icon_cy - badge_h // 2), "সর্বশেষ", font=live_font, fill=TEXT)
    if kicker:
        kx = live_x + live_font.getlength("সর্বশেষ") + int(22 * s)
        kw = kicker_font.getlength(kicker)
        draw.rounded_rectangle(
            [kx, icon_cy - pill_h // 2, kx + kw + 2 * pill_pad, icon_cy + pill_h // 2],
            radius=pill_h // 2, fill=style.accent,
        )
        draw.text((kx + pill_pad, icon_cy - kicker_font.getbbox("আমিগ")[3] // 2 - int(2 * s)),
                  kicker, font=kicker_font, fill=TEXT)

    # --- headline (mixed weight) ---
    y = row_top + row_h + gap
    for line in lines:
        x = margin
        for word, f in line:
            draw.text((x, y), word, font=f, fill=TEXT)
            x += f.getlength(word) + f.getlength(" ") + space_w_extra
        y += line_h

    # --- standfirst (muted) under the headline ---
    if std_lines:
        y += std_gap
        for ln in std_lines:
            draw.text((margin, y), ln, font=std_font, fill=MUTED)
            y += std_line_h

    # --- footer bar: Bangla date+time left, photo credit right (white on red) ---
    foot_font = _bn_font(foot_size, "SemiBold")
    foot_h = foot_font.getbbox("তারিখ")[3]
    fy = bar_top + (bar_h - foot_h) // 2
    draw.text((margin, fy), _bn_date(article.published), font=foot_font, fill=TEXT)
    if style.show_credit and article.source:
        credit = f"ছবি: {article.source}"
        cw = foot_font.getlength(credit)
        draw.text((w - margin - cw, fy), credit, font=foot_font, fill=TEXT)

    return card.convert("RGB"), icon_geom


def build_card(article: Article, style: CardStyle | None = None) -> Image.Image:
    """Static card (live icon shown solid). Used for PNG previews."""
    style = style or CardStyle()
    img, geom = _compose(article, style)
    return _draw_live_icon(img, geom, style.accent, 1.0)


def make_frames(article: Article, style: CardStyle | None, n_frames: int, fps: int = 30):
    """Render `n_frames` with the LIVE icon blinking; everything else still."""
    style = style or CardStyle()
    base, geom = _compose(article, style)
    return [
        _draw_live_icon(base, geom, style.accent, _blink_alpha(i / fps))
        for i in range(n_frames)
    ]


def save_card(article: Article, out_path: str, style: CardStyle | None = None) -> str:
    img = build_card(article, style)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


if __name__ == "__main__":
    demo = Article(
        title="ডেমো শিরোনাম: সংবাদ থেকে স্বয়ংক্রিয়ভাবে তৈরি হলো ফেসবুক রিল",
        image_url=None,
        source="দ্য সিটিজেন পোস্ট",
        url="https://example.com",
    )
    save_card(demo, "output/demo_card.png")
    print("wrote output/demo_card.png")
