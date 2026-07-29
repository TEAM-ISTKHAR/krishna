import os
import re
import random
import aiohttp
import aiofiles
import colorsys
from unidecode import unidecode
from functools import lru_cache
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ASSETS      = os.path.join(BASE_DIR, "..", "assets")
FONT_BOLD   = os.path.join(ASSETS, "f.ttf")
FONT_NORMAL = os.path.join(ASSETS, "cfont.ttf")

def clean_username(name: str) -> str:
    import unicodedata
    import re
    if not name:
        return "IstkharUser"
    name = unicodedata.normalize("NFKC", name)
    decoded = unidecode(name)
    if re.match(r'^[A-Za-z0-9 _.-]{3,}$', decoded):
        return decoded.strip()
    cleaned = re.sub(r'[^A-Za-z0-9 ]+', ' ', decoded)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) < 3:
        return "AxiomUser"
    return cleaned

FONT_FALLBACKS = []
for file in os.listdir(ASSETS):
    if file.lower().endswith((".ttf", ".otf")):
        FONT_FALLBACKS.append(os.path.join(ASSETS, file))

emoji_font = os.path.join(ASSETS, "seguiemj.ttf")
if os.path.exists(emoji_font):
    FONT_FALLBACKS.insert(0, emoji_font)
FONT_FALLBACKS.append(FONT_NORMAL)

@lru_cache(maxsize=10)
def _get_fallback_fonts(size: int):
    fonts = []
    for path in FONT_FALLBACKS:
        try:
            fonts.append(ImageFont.truetype(path, size))
        except:
            continue
    if not fonts:
        fonts.append(ImageFont.load_default())
    return fonts

# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL GENERATOR - VERSION 5.0 (Glassmorphism & Neon Edition)
# ═══════════════════════════════════════════════════════════════════

W, H = 1280, 720
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY  = (200, 200, 200)

_thumb_memory: dict = {}

@lru_cache(maxsize=4)
def _get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _get_gradient(w, h):
    """Creates a horizontal cyan-green-pink gradient map."""
    gradient = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(gradient)
    for x in range(w):
        ratio = x / w
        if ratio < 0.45:
            # Cyan to Greenish-yellow
            r1 = ratio / 0.45
            r = int(60 + (160 - 60) * r1)
            g = int(180 + (230 - 180) * r1)
            b = int(240 + (80 - 240) * r1)
        else:
            # Greenish-yellow to Pink/Purple
            r1 = (ratio - 0.45) / 0.55
            r = int(160 + (240 - 160) * r1)
            g = int(230 + (100 - 230) * r1)
            b = int(80 + (160 - 80) * r1)
        draw.line([(x, 0), (x, h)], fill=(r, g, b, 255))
    return gradient

def _draw_neon_card(base, box, radius, gradient, stroke_width=3, glow_spread=15, is_image=False):
    """Draws a card/border with a glowing neon gradient."""
    # Dark transparent background for main card
    if not is_image:
        card_bg = Image.new('RGBA', base.size, (0, 0, 0, 0))
        draw_bg = ImageDraw.Draw(card_bg)
        draw_bg.rounded_rectangle(box, radius=radius, fill=(20, 20, 20, 140))
        base = Image.alpha_composite(base.convert('RGBA'), card_bg)

    # Outer Glow layer
    glow_mask = Image.new('L', base.size, 0)
    glow_draw = ImageDraw.Draw(glow_mask)
    glow_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width + 4)
    glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(glow_spread))
    
    glow_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    glow_layer.paste(gradient, mask=glow_mask)

    # Solid Stroke layer
    border_mask = Image.new('L', base.size, 0)
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width)
    
    border_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    border_layer.paste(gradient, mask=border_mask)

    # Combine
    base = Image.alpha_composite(base.convert('RGBA'), glow_layer)
    base = Image.alpha_composite(base, border_layer)
    return base

def _crop_center_square(img):
    w, h = img.size
    m = min(w, h)
    left = (w - m) / 2
    top = (h - m) / 2
    right = (w + m) / 2
    bottom = (h + m) / 2
    return img.crop((left, top, right, bottom))

def _paste_rounded(base, img, x, y, size, r=20):
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=r, fill=255)
    img.putalpha(mask)
    base.paste(img, (x, y), img)
    return base

def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w: return text
    while text and draw.textlength(text + "…", font=font) > max_w: text = text[:-1]
    return text + "…"

async def get_thumb(videoid: str, user_name: str = "kirtiUser") -> str:
    output = f"cache/{videoid}.png"
    cache  = f"cache/thumb{videoid}.jpg"
    os.makedirs("cache", exist_ok=True)

    if os.path.exists(output):
        try:
            os.remove(output)
        except:
            pass

    # Fetch metadata
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        from py_yt import VideosSearch
        data      = (await VideosSearch(url, limit=1).next())["result"][0]
        title     = re.sub(r"[\x00-\x1f\x7f]", "", data.get("title", "Unknown")).strip()
        duration  = data.get("duration", "00:00") or "00:00"
        thumb_url = data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0]
        channel   = data.get("channel", {}).get("name", "Unknown")
    except Exception:
        title = "Unknown Track"
        duration = "00:00"
        channel = "Unknown Artist"
        thumb_url = "https://o.uguu.se/snWhWXPT.jpg"

    # Download thumbnail image
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(thumb_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                async with aiofiles.open(cache, "wb") as f:
                    await f.write(await r.read())
        song_img = Image.open(cache).convert("RGBA")
    except Exception:
        song_img = Image.new("RGBA", (1280, 720), (28, 10, 5))

    # Compose Background (Heavily Blurred)
    bg = song_img.resize((W, H), Image.LANCZOS).convert("RGB")
    bg = bg.filter(ImageFilter.GaussianBlur(60))
    
    # Darken background slightly to make card pop
    dark_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 100))
    bg = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)
    base = bg.convert("RGBA")

    # Layout Coordinates
    card_box = [200, 150, 1080, 570]
    img_size = 360
    img_x, img_y = 240, 180
    
    gradient = _get_gradient(W, H)

    # Draw Main Card
    base = _draw_neon_card(base, card_box, radius=30, gradient=gradient)

    # Paste Square Thumbnail
    sq_img = _crop_center_square(song_img)
    base = _paste_rounded(base, sq_img, img_x, img_y, img_size, r=25)
    
    # Draw Thumbnail Border (Neon)
    img_box = [img_x, img_y, img_x + img_size, img_y + img_size]
    base = _draw_neon_card(base, img_box, radius=25, gradient=gradient, stroke_width=3, glow_spread=10, is_image=True)

    draw = ImageDraw.Draw(base)
    
    # Fonts
    f_tit = _get_font(FONT_BOLD, 42)
    f_sub = _get_font(FONT_BOLD, 28)
    f_time = _get_font(FONT_BOLD, 20)
    f_icon = _get_font(emoji_font, 32) if os.path.exists(emoji_font) else _get_font(FONT_NORMAL, 32)

    # Text Placement
    text_x = 640
    title_text = _truncate(draw, title.upper(), f_tit, 400)
    artist_text = _truncate(draw, channel, f_sub, 400)
    
    draw.text((text_x, 240), title_text, font=f_tit, fill=TEXT_WHITE)
    draw.text((text_x, 305), artist_text, font=f_sub, fill=TEXT_GRAY)

    # Progress Bar
    bar_y = 420
    bar_w = 380
    draw.rounded_rectangle([(text_x, bar_y), (text_x + bar_w, bar_y + 6)], radius=3, fill=(180, 180, 180, 180))
    
    # Active Progress (Greenish)
    prog_w = int(bar_w * 0.35) # 35% progress randomly set for visual
    draw.rounded_rectangle([(text_x, bar_y), (text_x + prog_w, bar_y + 6)], radius=3, fill=(150, 204, 57, 255))
    
    # Progress Knob
    draw.ellipse([(text_x + prog_w - 6, bar_y - 3), (text_x + prog_w + 6, bar_y + 9)], fill=(255, 255, 255, 255))

    # Time Text
    draw.text((text_x, 445), "01:37", font=f_time, fill=TEXT_WHITE, anchor="ls")
    draw.text((text_x + bar_w, 445), duration, font=f_time, fill=TEXT_WHITE, anchor="rs")

    # Control Icons (using text/unicode as fallback for images)
    # Colors matching the reference image: Shuffle(Green), Repeat(Orange), Heart(Red)
    icon_y = 485
    icons_data = [
        ("🔀", (37, 180, 122)),  # Shuffle - Green
        ("🔁", (211, 150, 38)),  # Repeat - Orange
        ("⏮", (255, 255, 255)), # Prev - White
        ("⏸", (255, 255, 255)), # Pause - White
        ("⏭", (255, 255, 255)), # Next - White
        ("❤️", (216, 55, 55)),   # Heart - Red
        ("🎧", (255, 255, 255))  # Headphone - White
    ]
    
    spacing = bar_w // (len(icons_data) - 1)
    for i, (icon_char, color) in enumerate(icons_data):
        ix = text_x + (i * spacing)
        # Drop shadow for icons
        draw.text((ix+1, icon_y+1), icon_char, font=f_icon, fill=(0,0,0,100), anchor="ms")
        draw.text((ix, icon_y), icon_char, font=f_icon, fill=color, anchor="ms")

    # Add background views/video tag (blurred effect in reference)
    f_bg = _get_font(FONT_BOLD, 55)
    draw.text((100, 600), "25 M+", font=f_bg, fill=(255, 255, 255, 80))
    draw.text((100, 660), "VIEWS", font=f_bg, fill=(255, 255, 255, 80))
    
    draw.text((W - 100, 600), "OFFICIAL", font=f_bg, fill=(255, 255, 255, 80), anchor="ra")
    draw.text((W - 100, 660), "VIDEO", font=f_bg, fill=(255, 255, 255, 80), anchor="ra")

    # Save
    base = base.convert("RGB")
    base.save(output, "PNG", optimize=True)

    try:
        if os.path.exists(cache): os.remove(cache)
    except: pass

    _thumb_memory[videoid] = output
    return output

