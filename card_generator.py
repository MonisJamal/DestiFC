import os
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from functools import lru_cache

FONT_DIR = "assets/fonts"
CACHE_DIR = "assets/cache/images"
CARD_CACHE_DIR = "assets/cache/cards"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CARD_CACHE_DIR, exist_ok=True)

# High-performance persistent HTTP session with connection pooling
_session = requests.Session()
_retries = Retry(total=2, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
_adapter = HTTPAdapter(pool_connections=30, pool_maxsize=50, max_retries=_retries)
_session.mount('https://', _adapter)
_session.mount('http://', _adapter)

# In-memory fast image cache
_MEMORY_IMAGE_CACHE = {}
_MEMORY_CARD_CACHE = {}

@lru_cache(maxsize=64)
def get_font(name: str, size: int):
    path = os.path.join(FONT_DIR, f"{name}.ttf")
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()

def get_image_from_url(url: str, size=None) -> Image.Image:
    if not url:
        return None

    # Support direct base64 image data (e.g. from web portal file uploads)
    if url.startswith('data:image'):
        try:
            import base64
            head, base64_data = url.split(',', 1)
            img_bytes = base64.b64decode(base64_data)
            img = Image.open(BytesIO(img_bytes)).convert("RGBA")
            if size and img.size != size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            print(f"Error decoding base64 image data: {e}")
            return None
        
    # Ensure URL is absolute
    if url.startswith('/'):
        url = f"https://renderz.app{url}"
    
    cache_key = f"{url}_{size}"
    if cache_key in _MEMORY_IMAGE_CACHE:
        return _MEMORY_IMAGE_CACHE[cache_key].copy()

    # Disk Cache Check
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    disk_cache_path = os.path.join(CACHE_DIR, f"{url_hash}.png")
    
    img = None
    if os.path.exists(disk_cache_path):
        try:
            img = Image.open(disk_cache_path).convert("RGBA")
        except Exception:
            img = None

    if img is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://renderz.app/"
        }
        try:
            resp = _session.get(url, headers=headers, timeout=(0.8, 1.2))
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            # Save to disk cache for future instant loads
            try:
                img.save(disk_cache_path, "PNG")
            except Exception:
                pass
        except Exception:
            return None
    
    if size and img.size != size:
        img = img.resize(size, Image.Resampling.LANCZOS)

    if len(_MEMORY_IMAGE_CACHE) < 250:
        _MEMORY_IMAGE_CACHE[cache_key] = img.copy()
        
    return img

_MEMORY_CARD_BYTES_CACHE = {}

def generate_card(player: dict, scale: int = 3, animated: bool = False):
    """
    Generates a RenderZ-style card for a given player dictionary with multi-tier caching.
    Returns a single PIL Image (PNG) or a list of PIL Images (GIF frames).
    """
    SCALE = scale
    if animated:
        SCALE = 1.25  # 320x320 optimized for Discord embeds and lightning-fast GIF generation

    player_id = player.get("id") or player.get("player_id") or player.get("cardName") or player.get("lastName") or "unknown"
    rating = player.get("rating", "?")
    card_cache_key = f"{player_id}_{rating}_{SCALE}_{animated}"
    
    if card_cache_key in _MEMORY_CARD_CACHE:
        return _MEMORY_CARD_CACHE[card_cache_key]

    images = player.get("images") or {}
    anim = player.get("animation") or {}
    colors = anim.get("colors") or {}
    layout = anim.get("layout") or {}
    
    bg_url = images.get("playerCardBackground") or images.get("background") or player.get("bg_image") or player.get("playerCardBackground")
    player_url = images.get("playerCardImage") or images.get("playerImage") or player.get("imageUrl") or player.get("image") or player.get("playerCardImage")
    flag_url = images.get("flagImage") or player.get("flagImage")
    club_url = images.get("clubImage") or player.get("clubImage")
    
    # Fetch Images
    is_gif = False
    sprite_img = None
    max_frames = 1
    
    if animated:
        anim_data = player.get("animation") or {}
        for a in anim_data.get('animations', []):
            for sub_a in a.get('animations', []):
                if 'image' in sub_a:
                    sprite_url = sub_a['image']
                    if sprite_url.startswith('/'): sprite_url = f"https://renderz.app{sprite_url}"
                    try:
                        sprite_img = get_image_from_url(sprite_url)
                        max_frames = sub_a.get('maxFrames', 1)
                        if sprite_img:
                            is_gif = True
                            break
                    except Exception: pass
            if is_gif: break

    target_size = (int(256 * SCALE), int(256 * SCALE))
    card = get_image_from_url(bg_url, size=target_size) if bg_url else None
    if not card:
        card = Image.new("RGBA", target_size, (25, 30, 45, 255))
    
    overlay = Image.new("RGBA", target_size, (0,0,0,0))
    
    if player_url:
        try:
            player_img = get_image_from_url(player_url, size=target_size)
            if player_img:
                overlay.alpha_composite(player_img, (0, 0))
        except Exception as e:
            print(f"Failed to fetch player image: {e}")

    def draw_image_layer(url, layout_key):
        if url and layout_key in layout:
            l = layout[layout_key]
            try:
                img_size = (int(int(l["sizeX"]) * SCALE), int(int(l["sizeY"]) * SCALE))
                img = get_image_from_url(url, size=img_size)
                if img:
                    overlay.alpha_composite(img, (int(int(l["posX"]) * SCALE), int(int(l["posY"]) * SCALE)))
            except Exception as e:
                print(f"Failed to fetch {layout_key}: {e}")

    draw_image_layer(flag_url, "nation")
    league_url = images.get("leagueImage") or player.get("leagueImage")
    draw_image_layer(league_url, "league")
    draw_image_layer(club_url, "club")

    draw = ImageDraw.Draw(overlay)
    font_bold = lambda size: get_font("CruyffSansCondensed-Bold", size)
    
    rating_color = colors.get("rating", "#FDF6D1")
    position_color = colors.get("position", "#FDF6D1")
    name_color = colors.get("name", "#493721")

    def draw_centered_text(text, layout_key, color, y_offset=0):
        if layout_key in layout:
            l = layout[layout_key]
            x = (int(l["posX"]) + (int(l["sizeX"]) / 2)) * SCALE
            y = (int(l["posY"]) + (int(l["sizeY"]) / 2) + y_offset) * SCALE
            font = font_bold(int(int(l.get("fontSize", 24)) * SCALE))
            draw.text((x, y), str(text), fill=color, font=font, anchor='mm')

    draw_centered_text(player.get("rating", "?"), "rating", rating_color, y_offset=-2)
    draw_centered_text(player.get("position", "?").upper(), "position", position_color, y_offset=-1)
    
    name_layout = layout.get("name", {})
    if name_layout:
        name = player.get("cardName") or player.get("lastName", "?")
        font = font_bold(int(int(name_layout.get("fontSize", 22)) * SCALE))
        x = int(int(name_layout.get("posX", 128)) * SCALE)
        y = int(int(name_layout.get("posY", 178)) * SCALE)
        draw.text(
            (x, y),
            name.upper(),
            fill=name_color,
            font=font,
            anchor='mm'
        )
    else:
        # Fallback text rendering if layout dict is missing
        name = player.get("cardName") or player.get("lastName", "Player")
        font = font_bold(int(18 * SCALE))
        draw.text((target_size[0] // 2, int(target_size[1] * 0.85)), name.upper()[:14], fill=(255, 255, 255), font=font, anchor='mm')
        draw.text((int(target_size[0] * 0.22), int(target_size[1] * 0.28)), str(rating), fill=(255, 215, 0), font=font_bold(int(22 * SCALE)), anchor='mm')
        draw.text((int(target_size[0] * 0.22), int(target_size[1] * 0.38)), str(player.get("position", "ST")).upper(), fill=(220, 220, 220), font=font_bold(int(14 * SCALE)), anchor='mm')

    if not is_gif:
        card.alpha_composite(overlay)
        if len(_MEMORY_CARD_CACHE) < 300:
            _MEMORY_CARD_CACHE[card_cache_key] = card.copy()
        return card
        
    # Generate Fast Adaptive GIF frames
    frames = []
    frame_w, frame_h = 256, 256
    cols = max(1, sprite_img.width // frame_w) if sprite_img else 1
    step = max(2, max_frames // 10)
    
    for i in range(0, max_frames, step):
        if not sprite_img: break
        x = (i % cols) * frame_w
        y = (i // cols) * frame_h
        try:
            frame_bg = sprite_img.crop((x, y, x + frame_w, y + frame_h)).resize(target_size, Image.Resampling.BILINEAR)
            solid_bg = Image.new("RGBA", target_size, (49, 51, 56, 255))
            base = card.copy()
            base.alpha_composite(frame_bg)
            base.alpha_composite(overlay)
            solid_bg.alpha_composite(base)
            frames.append(solid_bg.convert("P", palette=Image.Palette.ADAPTIVE))
        except Exception as e:
            print("Sprite crop error:", e)
            break
            
    if not frames:
        card.alpha_composite(overlay)
        return card
        
    if len(_MEMORY_CARD_CACHE) < 300:
        _MEMORY_CARD_CACHE[card_cache_key] = frames
    return frames

def save_card_to_bytes(card_result):
    import io
    binary = io.BytesIO()
    if isinstance(card_result, list):
        card_result[0].save(binary, 'GIF', save_all=True, append_images=card_result[1:], duration=100, loop=0, optimize=True)
        binary.seek(0)
        return binary, 'card.gif'
    else:
        card_result.save(binary, 'PNG')
        binary.seek(0)
        return binary, 'card.png'

def get_or_create_card_bytes(player: dict, scale: int = 3, animated: bool = False):
    """
    Direct ultra-fast cache for Discord card attachments.
    Guaranteed to return a valid (BytesIO, filename) tuple.
    """
    import io
    if not player or not isinstance(player, dict):
        player = {"cardName": "Superstar", "rating": 115, "position": "ST"}

    player_id = player.get("id") or player.get("player_id") or player.get("cardName") or player.get("lastName") or "unknown"
    rating = player.get("rating", "?")
    key = f"{player_id}_{rating}_{scale}_{animated}"
    
    if key in _MEMORY_CARD_BYTES_CACHE:
        raw_bytes, filename = _MEMORY_CARD_BYTES_CACHE[key]
        return io.BytesIO(raw_bytes), filename
        
    card_result = None
    try:
        card_result = generate_card(player, scale=scale, animated=animated)
    except Exception as e:
        print(f"Error generating animated card: {e}")

    if card_result is None and animated:
        try:
            card_result = generate_card(player, scale=scale, animated=False)
        except Exception as e:
            print(f"Error generating static card fallback: {e}")

    if card_result is None:
        target_size = (int(256 * scale), int(256 * scale))
        card = Image.new("RGBA", target_size, (25, 30, 45, 255))
        d = ImageDraw.Draw(card)
        font = get_font("CruyffSansCondensed-Bold", int(24 * scale))
        d.text((target_size[0] // 2, target_size[1] // 2 - 20), str(rating), fill=(255, 215, 0), font=font, anchor="mm")
        d.text((target_size[0] // 2, target_size[1] // 2 + 20), str(player.get("cardName", "Player")), fill=(255, 255, 255), font=font, anchor="mm")
        card_result = card

    bio, filename = save_card_to_bytes(card_result)
    raw = bio.getvalue()
    if len(_MEMORY_CARD_BYTES_CACHE) < 200:
        _MEMORY_CARD_BYTES_CACHE[key] = (raw, filename)
    return io.BytesIO(raw), filename

