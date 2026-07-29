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

# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL GENERATOR - VERSION 6.0 (Perfect Match Edition)
# Fixes: Custom drawn icons (No Emoji Font needed), Fixed text sizing
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
        # Fallback to system fonts if custom font is missing so text doesn't shrink
        fallbacks = ["arial.ttf", "DejaVuSans.ttf", "seguiemj.ttf"]
        for fb in fallbacks:
            try:
                return ImageFont.truetype(fb, size)
            except:
                pass
        try:
            return ImageFont.load_default(size=size) # For Pillow >= 10
        except:
            return ImageFont.load_default()

def _get_gradient(w, h):
    gradient = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(gradient)
    for x in range(w):
        ratio = x / w
        if ratio < 0.45:
            r1 = ratio / 0.45
            r = int(60 + (160 - 60) * r1)
            g = int(180 + (230 - 180) * r1)
            b = int(240 + (80 - 240) * r1)
        else:
            r1 = (ratio - 0.45) / 0.55
            r = int(160 + (240 - 160) * r1)
            g = int(230 + (100 - 230) * r1)
            b = int(80 + (160 - 80) * r1)
        draw.line([(x, 0), (x, h)], fill=(r, g, b, 255))
    return gradient

def _draw_neon_card(base, box, radius, gradient, stroke_width=4, glow_spread=18, is_image=False):
    if not is_image:
        card_bg = Image.new('RGBA', base.size, (0, 0, 0, 0))
        draw_bg = ImageDraw.Draw(card_bg)
        draw_bg.rounded_rectangle(box, radius=radius, fill=(20, 20, 20, 160))
        base = Image.alpha_composite(base.convert('RGBA'), card_bg)

    glow_mask = Image.new('L', base.size, 0)
    glow_draw = ImageDraw.Draw(glow_mask)
    glow_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width + 4)
    glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(glow_spread))
    glow_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    glow_layer.paste(gradient, mask=glow_mask)

    border_mask = Image.new('L', base.size, 0)
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width)
    border_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    border_layer.paste(gradient, mask=border_mask)

    base = Image.alpha_composite(base.convert('RGBA'), glow_layer)
    base = Image.alpha_composite(base, border_layer)
    return base

def _crop_center_square(img):
    w, h = img.size
    m = min(w, h)
    left, top = (w - m) / 2, (h - m) / 2
    return img.crop((left, top, left + m, top + m))

def _paste_rounded(base, img, x, y, size, r=20):
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=r, fill=255)
    img.putalpha(mask)
    base.paste(img, (x, y), img)
    return base

def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w: return text
    while text and draw.textlength(text + "...", font=font) > max_w: text = text[:-1]
    return text + "..."

# 🔥 Custom Icon Drawer (Emoji Font Ki Zarurat Nahi!)
def _draw_icon(draw, icon_name, x, y, color):
    if icon_name == "shuffle":
        draw.line([x-10, y-6, x+10, y+6], fill=color, width=3)
        draw.line([x-10, y+6, x+10, y-6], fill=color, width=3)
        draw.polygon([x+10, y+6, x+5, y+6, x+10, y+1], fill=color)
        draw.polygon([x+10, y-6, x+5, y-6, x+10, y-1], fill=color)
    elif icon_name == "repeat":
        draw.arc([x-10, y-10, x+10, y+10], 45, 315, fill=color, width=3)
        draw.polygon([x+6, y-14, x+13, y-9, x+5, y-5], fill=color)
    elif icon_name == "prev":
        draw.rectangle([x-14, y-8, x-10, y+8], fill=color)
        draw.polygon([x-10, y, x-2, y-8, x-2, y+8], fill=color)
        draw.polygon([x-2, y, x+6, y-8, x+6, y+8], fill=color)
    elif icon_name == "pause":
        draw.rectangle([x-8, y-9, x-2, y+9], fill=color)
        draw.rectangle([x+2, y-9, x+8, y+9], fill=color)
    elif icon_name == "next":
        draw.rectangle([x+10, y-8, x+14, y+8], fill=color)
        draw.polygon([x+10, y, x+2, y-8, x+2, y+8], fill=color)
        draw.polygon([x+2, y, x-6, y-8, x-6, y+8], fill=color)
    elif icon_name == "heart":
        draw.ellipse([x-10, y-10, x, y+2], fill=color)
        draw.ellipse([x, y-10, x+10, y+2], fill=color)
        draw.polygon([x-9, y-2, x+9, y-2, x, y+10], fill=color)
    elif icon_name == "headphone":
        draw.arc([x-12, y-12, x+12, y+4], 180, 0, fill=color, width=3)
        draw.rounded_rectangle([x-14, y-2, x-7, y+10], radius=3, fill=color)
        draw.rounded_rectangle([x+7, y-2, x+14, y+10], radius=3, fill=color)

async def get_thumb(videoid: str, user_name: str = "kirtiUser") -> str:
    output = f"cache/{videoid}.png"
    cache  = f"cache/thumb{videoid}.jpg"
    os.makedirs("cache", exist_ok=True)

    if os.path.exists(output):
        try: os.remove(output)
        except: pass

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

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(thumb_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                async with aiofiles.open(cache, "wb") as f:
                    await f.write(await r.read())
        song_img = Image.open(cache).convert("RGBA")
    except Exception:
        song_img = Image.new("RGBA", (1280, 720), (28, 10, 5))

    bg = song_img.resize((W, H), Image.LANCZOS).convert("RGB")
    bg = bg.filter(ImageFilter.GaussianBlur(55))
    dark_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 130))
    bg = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)
    base = bg.convert("RGBA")

    # Layout Coordinates setup
    card_box = [180, 130, 1100, 590]
    img_size = 380
    img_x, img_y = 220, 170
    text_x = 640
    
    gradient = _get_gradient(W, H)
    base = _draw_neon_card(base, card_box, radius=30, gradient=gradient)

    sq_img = _crop_center_square(song_img)
    base = _paste_rounded(base, sq_img, img_x, img_y, img_size, r=25)
    
    img_box = [img_x, img_y, img_x + img_size, img_y + img_size]
    base = _draw_neon_card(base, img_box, radius=25, gradient=gradient, stroke_width=3, glow_spread=10, is_image=True)

    draw = ImageDraw.Draw(base)
    
    # Fonts
    f_tit = _get_font(FONT_BOLD, 46)
    f_sub = _get_font(FONT_NORMAL, 30)
    f_time = _get_font(FONT_BOLD, 22)
    f_bg = _get_font(FONT_BOLD, 55)

    # Texts
    title_text = _truncate(draw, title.upper(), f_tit, 420)
    artist_text = _truncate(draw, channel, f_sub, 420)
    
    draw.text((text_x, 230), title_text, font=f_tit, fill=TEXT_WHITE)
    draw.text((text_x, 300), artist_text, font=f_sub, fill=TEXT_GRAY)

    # Progress Bar
    bar_y = 440
    bar_w = 420
    draw.rounded_rectangle([(text_x, bar_y), (text_x + bar_w, bar_y + 6)], radius=3, fill=(180, 180, 180, 120))
    prog_w = int(bar_w * 0.35) 
    draw.rounded_rectangle([(text_x, bar_y), (text_x + prog_w, bar_y + 6)], radius=3, fill=(150, 204, 57, 255))
    draw.ellipse([(text_x + prog_w - 7, bar_y - 4), (text_x + prog_w + 7, bar_y + 10)], fill=(255, 255, 255, 255))

    # Time
    draw.text((text_x, 465), "01:37", font=f_time, fill=TEXT_WHITE, anchor="ls")
    draw.text((text_x + bar_w, 465), duration, font=f_time, fill=TEXT_WHITE, anchor="rs")

    # CUSTOM ICONS (Drawn via code, no font needed!)
    icon_y = 510
    icons = [
        ("shuffle", (37, 180, 122)),
        ("repeat", (211, 150, 38)),
        ("prev", (255, 255, 255)),
        ("pause", (255, 255, 255)),
        ("next", (255, 255, 255)),
        ("heart", (216, 55, 55)),
        ("headphone", (255, 255, 255))
    ]
    
    spacing = bar_w // (len(icons) - 1)
    for i, (name, color) in enumerate(icons):
        ix = text_x + (i * spacing)
        _draw_icon(draw, name, ix, icon_y, color)

    # Background Texts (Blurred look)
    draw.text((120, 600), "25 M+", font=f_bg, fill=(255, 255, 255, 60))
    draw.text((120, 660), "VIEWS", font=f_bg, fill=(255, 255, 255, 60))
    draw.text((W - 120, 600), "OFFICIAL", font=f_bg, fill=(255, 255, 255, 60), anchor="ra")
    draw.text((W - 120, 660), "VIDEO", font=f_bg, fill=(255, 255, 255, 60), anchor="ra")

    base = base.convert("RGB")
    base.save(output, "PNG", optimize=True)

    try:
        if os.path.exists(cache): os.remove(cache)
    except: pass

    _thumb_memory[videoid] = output
    return output

