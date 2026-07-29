import os
import re
import aiohttp
import aiofiles
from unidecode import unidecode
from functools import lru_cache
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ASSETS      = os.path.join(BASE_DIR, "..", "assets")
FONT_BOLD   = os.path.join(ASSETS, "f.ttf")
FONT_NORMAL = os.path.join(ASSETS, "cfont.ttf")

# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL GENERATOR - ULTIMATE PIXEL-PERFECT CLONE
# ═══════════════════════════════════════════════════════════════════

W, H = 1280, 720
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY  = (190, 195, 200)

_thumb_memory: dict = {}

@lru_cache(maxsize=4)
def _get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try: return ImageFont.load_default(size=size)
        except: return ImageFont.load_default()

def _get_gradient(w, h):
    gradient = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(gradient)
    for x in range(w):
        ratio = x / w
        if ratio < 0.5:
            # Cyan to Yellow-Green
            rat = ratio / 0.5
            r = int(50 + (160 - 50) * rat)
            g = int(190 + (230 - 190) * rat)
            b = int(250 + (80 - 250) * rat)
        else:
            # Yellow-Green to Pinkish-Red
            rat = (ratio - 0.5) / 0.5
            r = int(160 + (240 - 160) * rat)
            g = int(230 + (90 - 230) * rat)
            b = int(80 + (140 - 80) * rat)
        draw.line([(x, 0), (x, h)], fill=(r, g, b, 255))
    return gradient

def _draw_neon_card(base, box, radius, gradient, stroke_width=6, glow_spread=35, is_image=False):
    if not is_image:
        card_bg = Image.new('RGBA', base.size, (0, 0, 0, 0))
        draw_bg = ImageDraw.Draw(card_bg)
        # Perfect Glass transparency (Alpha 95)
        draw_bg.rounded_rectangle(box, radius=radius, fill=(18, 18, 20, 95)) 
        base = Image.alpha_composite(base.convert('RGBA'), card_bg)

    # Neon Glow
    glow_mask = Image.new('L', base.size, 0)
    glow_draw = ImageDraw.Draw(glow_mask)
    glow_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width + 12)
    glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(glow_spread))
    glow_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    glow_layer.paste(gradient, mask=glow_mask)

    # Solid Border
    border_mask = Image.new('L', base.size, 0)
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.rounded_rectangle(box, radius=radius, outline=255, width=stroke_width)
    border_layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    border_layer.paste(gradient, mask=border_mask)

    base = Image.alpha_composite(base.convert('RGBA'), glow_layer)
    base = Image.alpha_composite(base, border_layer)
    return base

def _get_square_thumb(img, size):
    # Perfect Center Zoom Crop (Guaranteed 0% Black Bars)
    w, h = img.size
    m = min(w, h)
    crop_size = int(m * 0.85) # Zoom in by 15% to cut letterboxes safely
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    trimmed = img.crop((left, top, left + crop_size, top + crop_size))
    return trimmed.resize((size, size), Image.LANCZOS)

def _paste_rounded(base, img, x, y, size, r=25):
    img = img.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=r, fill=255)
    img.putalpha(mask)
    base.paste(img, (x, y), img)
    return base

def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w: return text
    while text and draw.textlength(text + "...", font=font) > max_w: text = text[:-1]
    return text + "..."

def _draw_vector_icon(draw, icon_name, x, y, color):
    w = 3
    if icon_name == "shuffle":
        draw.line([x-12, y-6, x+10, y+6], fill=color, width=w)
        draw.line([x-12, y+6, x+10, y-6], fill=color, width=w)
        draw.polygon([x+12, y+8, x+5, y+9, x+9, y+2], fill=color)
        draw.polygon([x+12, y-8, x+5, y-9, x+9, y-2], fill=color)
    elif icon_name == "repeat":
        draw.arc([x-12, y-10, x+12, y+10], 45, 315, fill=color, width=w)
        draw.polygon([x+8, y-15, x+15, y-9, x+6, y-5], fill=color)
    elif icon_name == "prev":
        draw.rectangle([x-14, y-8, x-10, y+8], fill=color)
        draw.polygon([x-8, y, x+2, y-8, x+2, y+8], fill=color)
        draw.polygon([x+2, y, x+12, y-8, x+12, y+8], fill=color)
    elif icon_name == "pause":
        draw.rectangle([x-7, y-9, x-2, y+9], fill=color)
        draw.rectangle([x+2, y-9, x+7, y+9], fill=color)
    elif icon_name == "next":
        draw.rectangle([x+10, y-8, x+14, y+8], fill=color)
        draw.polygon([x+8, y, x-2, y-8, x-2, y+8], fill=color)
        draw.polygon([x-2, y, x-12, y-8, x-12, y+8], fill=color)
    elif icon_name == "heart":
        draw.ellipse([x-11, y-10, x, y+1], fill=color)
        draw.ellipse([x, y-10, x+11, y+1], fill=color)
        draw.polygon([x-10, y-1, x+10, y-1, x, y+10], fill=color)
    elif icon_name == "headphone":
        draw.arc([x-13, y-12, x+13, y+4], 180, 0, fill=color, width=w)
        draw.rounded_rectangle([x-15, y-2, x-7, y+10], radius=3, fill=color)
        draw.rounded_rectangle([x+7, y-2, x+15, y+10], radius=3, fill=color)

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
        
        # Clean title perfectly
        raw_title = data.get("title", "Unknown")
        safe_title = unidecode(raw_title)
        title = re.sub(r'[^a-zA-Z0-9\s\-\.\,\(\)\[\]\|&!]', '', safe_title).strip()
        
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

    # --- BG GENERATION ---
    bg = ImageOps.fit(song_img, (W, H), Image.LANCZOS).convert("RGBA")
    bg = bg.filter(ImageFilter.GaussianBlur(35)) # Optimized Blur
    
    # Dark overlay to make everything pop
    dark_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 100)) 
    bg = Image.alpha_composite(bg, dark_overlay)

    # Bright Background Text Layer
    txt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)
    f_bg = _get_font(FONT_BOLD, 75)
    
    txt_draw.text((80, 560), "25 M+", font=f_bg, fill=(255, 255, 255, 220))
    txt_draw.text((80, 630), "VIEWS", font=f_bg, fill=(255, 255, 255, 220))
    txt_draw.text((W - 80, 560), "OFFICIAL", font=f_bg, fill=(255, 255, 255, 220), anchor="ra")
    txt_draw.text((W - 80, 630), "VIDEO", font=f_bg, fill=(255, 255, 255, 220), anchor="ra")
    
    txt_layer = txt_layer.filter(ImageFilter.GaussianBlur(3))
    base = Image.alpha_composite(bg, txt_layer)

    # --- CARD LAYOUT ---
    card_box = [160, 140, 1120, 580]
    img_size = 380
    img_x, img_y = 190, 170
    text_x = 610
    bar_w = 460
    
    gradient = _get_gradient(W, H)
    
    # Outer Card Glow
    base = _draw_neon_card(base, card_box, radius=40, gradient=gradient, stroke_width=6, glow_spread=40)

    # Inner Square Thumbnail
    sq_img = _get_square_thumb(song_img, img_size)
    base = _paste_rounded(base, sq_img, img_x, img_y, img_size, r=30)
    
    # Inner Thumbnail Glow
    img_box = [img_x, img_y, img_x + img_size, img_y + img_size]
    base = _draw_neon_card(base, img_box, radius=30, gradient=gradient, stroke_width=4, glow_spread=20, is_image=True)

    draw = ImageDraw.Draw(base)
    
    # Fonts
    f_tit = _get_font(FONT_BOLD, 44)
    f_sub = _get_font(FONT_NORMAL, 28)
    f_time = _get_font(FONT_BOLD, 22)

    # Main Texts
    title_text = _truncate(draw, title.upper(), f_tit, 460)
    artist_text = _truncate(draw, channel, f_sub, 460)
    
    draw.text((text_x, 240), title_text, font=f_tit, fill=TEXT_WHITE)
    draw.text((text_x, 310), artist_text, font=f_sub, fill=TEXT_GRAY)

    # Progress Bar
    bar_y = 450
    draw.rounded_rectangle([(text_x, bar_y), (text_x + bar_w, bar_y + 6)], radius=3, fill=(180, 180, 180, 150))
    prog_w = int(bar_w * 0.35) 
    draw.rounded_rectangle([(text_x, bar_y), (text_x + prog_w, bar_y + 6)], radius=3, fill=(157, 205, 59, 255))
    draw.ellipse([(text_x + prog_w - 7, bar_y - 4), (text_x + prog_w + 7, bar_y + 10)], fill=(255, 255, 255, 255))

    # Time Stamps
    draw.text((text_x, 475), "01:37", font=f_time, fill=TEXT_WHITE, anchor="ls")
    draw.text((text_x + bar_w, 475), duration, font=f_time, fill=TEXT_WHITE, anchor="rs")

    # Clean UI Icons
    icon_y = 525
    icons = [
        ("shuffle", (37, 180, 122)),
        ("repeat", (211, 150, 38)),
        ("prev", (255, 255, 255)),
        ("pause", (255, 255, 255)),
        ("next", (255, 255, 255)),
        ("heart", (216, 55, 55)),
        ("headphone", (255, 255, 255))
    ]
    
    spacing = bar_w / (len(icons) - 1)
    for i, (name, color) in enumerate(icons):
        ix = int(text_x + (i * spacing))
        _draw_vector_icon(draw, name, ix, icon_y, color)

    base = base.convert("RGB")
    base.save(output, "PNG", optimize=True)

    try:
        if os.path.exists(cache): os.remove(cache)
    except: pass

    _thumb_memory[videoid] = output
    return output
