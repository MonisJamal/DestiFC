import os
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

FONT_DIR = "assets/fonts"
CACHE_DIR = "assets/cache/images"
CARD_CACHE_DIR = "assets/cache/cards"

os.makedirs(FONT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CARD_CACHE_DIR, exist_ok=True)

# High-performance persistent HTTP session with connection pooling
_session = requests.Session()
_retries = Retry(total=2, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
_adapter = HTTPAdapter(pool_connections=40, pool_maxsize=80, max_retries=_retries)
_session.mount('https://', _adapter)
_session.mount('http://', _adapter)

# In-memory fast image cache
_MEMORY_IMAGE_CACHE = {}
_MEMORY_CARD_CACHE = {}
_MEMORY_CARD_BYTES_CACHE = {}

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

    if len(_MEMORY_IMAGE_CACHE) < 500:
        _MEMORY_IMAGE_CACHE[cache_key] = img.copy()
        
    return img

def generate_card(player: dict, scale: int = 3, animated: bool = False):
    """
    Generates a RenderZ-style card for a given player dictionary with multi-tier caching.
    Returns a single PIL Image (PNG) or a list of PIL Images (GIF frames).
    """
    SCALE = scale
    if animated:
        SCALE = 1.25  # 320x320 optimized for Discord embeds and lightning-fast GIF generation

    player_id = str(player.get("id") or player.get("player_id") or player.get("cardName") or player.get("lastName") or "unknown")
    rating = player.get("rating", "?")
    card_cache_key = f"{player_id}_{rating}_{SCALE}_{animated}"
    
    if card_cache_key in _MEMORY_CARD_CACHE:
        return _MEMORY_CARD_CACHE[card_cache_key]

    images = player.get("images") or {}
    anim = player.get("animation") or {}
    colors = anim.get("colors") or {}
    layout = anim.get("layout") or {}
    
    # Extract sprite animation if animated is requested
    sprite_url = None
    max_frames = 0
    if animated:
        anims_list = anim.get("animations") or []
        if anims_list and isinstance(anims_list, list):
            for a_entry in anims_list:
                sub_anims = a_entry.get("animations") or []
                if sub_anims and isinstance(sub_anims, list):
                    for sub in sub_anims:
                        if sub.get("image"):
                            sprite_url = sub.get("image")
                            max_frames = sub.get("maxFrames", 30)
                            break
                if sprite_url:
                    break

    bg_url = images.get("playerCardBackground") or images.get("background") or player.get("bg_image") or player.get("playerCardBackground")
    player_url = images.get("playerCardImage") or images.get("playerImage") or player.get("imageUrl") or player.get("image") or player.get("playerCardImage")
    flag_url = images.get("flagImage") or player.get("flagImage")
    club_url = images.get("clubImage") or player.get("clubImage")
    league_url = images.get("leagueImage") or player.get("leagueImage")
    
    target_size = (int(256 * SCALE), int(256 * SCALE))

    # Parallel pre-fetching of all card assets concurrently
    tasks = {
        "bg": (bg_url, target_size),
        "player": (player_url, target_size),
    }
    if sprite_url:
        tasks["sprite"] = (sprite_url, None)
    if flag_url and "nation" in layout:
        l = layout["nation"]
        tasks["flag"] = (flag_url, (int(int(l["sizeX"]) * SCALE), int(int(l["sizeY"]) * SCALE)))
    if club_url and "club" in layout:
        l = layout["club"]
        tasks["club"] = (club_url, (int(int(l["sizeX"]) * SCALE), int(int(l["sizeY"]) * SCALE)))
    if league_url and "league" in layout:
        l = layout["league"]
        tasks["league"] = (league_url, (int(int(l["sizeX"]) * SCALE), int(int(l["sizeY"]) * SCALE)))

    fetched_images = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {
            executor.submit(get_image_from_url, url_sz[0], url_sz[1]): k 
            for k, url_sz in tasks.items() if url_sz[0]
        }
        for future in future_map:
            k = future_map[future]
            try:
                fetched_images[k] = future.result()
            except Exception:
                fetched_images[k] = None

    card = fetched_images.get("bg")
    if not card:
        card = Image.new("RGBA", target_size, (25, 30, 45, 255))
    
    overlay = Image.new("RGBA", target_size, (0,0,0,0))
    
    player_img = fetched_images.get("player")
    if player_img:
        overlay.alpha_composite(player_img, (0, 0))

    if "flag" in fetched_images and fetched_images["flag"] and "nation" in layout:
        l = layout["nation"]
        overlay.alpha_composite(fetched_images["flag"], (int(int(l["posX"]) * SCALE), int(int(l["posY"]) * SCALE)))

    if "league" in fetched_images and fetched_images["league"] and "league" in layout:
        l = layout["league"]
        overlay.alpha_composite(fetched_images["league"], (int(int(l["posX"]) * SCALE), int(int(l["posY"]) * SCALE)))

    if "club" in fetched_images and fetched_images["club"] and "club" in layout:
        l = layout["club"]
        overlay.alpha_composite(fetched_images["club"], (int(int(l["posX"]) * SCALE), int(int(l["posY"]) * SCALE)))

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

    # If animated and sprite exists, render animated GIF frames
    sprite_sheet = fetched_images.get("sprite")
    if animated and sprite_sheet:
        try:
            cols = sprite_sheet.width // 256
            if cols > 0:
                capped_frames = min(max_frames or 30, 30)
                step = 2 if capped_frames > 18 else 1
                frames = []
                for frame_idx in range(0, capped_frames, step):
                    col = frame_idx % cols
                    row = frame_idx // cols
                    box = (col * 256, row * 256, (col + 1) * 256, (row + 1) * 256)
                    frame_sprite = sprite_sheet.crop(box)
                    if SCALE != 1.0:
                        frame_sprite = frame_sprite.resize(target_size, Image.Resampling.BILINEAR)
                    
                    frame_card = card.copy()
                    frame_card.alpha_composite(frame_sprite)
                    frame_card.alpha_composite(overlay)
                    frames.append(frame_card)
                    
                if frames:
                    if len(_MEMORY_CARD_CACHE) < 500:
                        _MEMORY_CARD_CACHE[card_cache_key] = frames
                    return frames
        except Exception as e:
            print(f"Error generating animated frames: {e}")

    card.alpha_composite(overlay)
    if len(_MEMORY_CARD_CACHE) < 500:
        _MEMORY_CARD_CACHE[card_cache_key] = card.copy()
    return card

def save_card_to_bytes(card_result):
    import io
    binary = io.BytesIO()
    if isinstance(card_result, list) and len(card_result) > 0:
        card_result[0].save(
            binary,
            format='GIF',
            save_all=True,
            append_images=card_result[1:],
            duration=80,
            loop=0,
            optimize=True,
            disposal=2
        )
        binary.seek(0)
        return binary, 'card.gif'
    else:
        if isinstance(card_result, list):
            card_result = card_result[0]
        card_result.save(binary, 'PNG')
        binary.seek(0)
        return binary, 'card.png'

def get_or_create_card_bytes(player: dict, scale: int = 3, animated: bool = False):
    """
    Direct ultra-fast multi-tier cache for Discord card attachments.
    Tier 1: In-memory RAM cache (<0.1ms)
    Tier 2: Persistent Disk cache (<1ms)
    Tier 3: Parallel rendering & disk persistence (<50ms)
    """
    import io
    if not player or not isinstance(player, dict):
        player = {"cardName": "Superstar", "rating": 115, "position": "ST"}

    player_id = str(player.get("id") or player.get("player_id") or player.get("cardName") or player.get("lastName") or "unknown")
    rating = player.get("rating", "?")
    clean_id = "".join([c for c in player_id if c.isalnum() or c in ('-', '_')])
    key = f"{clean_id}_{rating}_{scale}_{animated}"
    
    # Tier 1: In-memory cache
    if key in _MEMORY_CARD_BYTES_CACHE:
        raw_bytes, filename = _MEMORY_CARD_BYTES_CACHE[key]
        return io.BytesIO(raw_bytes), filename

    # Tier 2: Persistent Disk Cache
    ext = "gif" if animated else "png"
    disk_file = os.path.join(CARD_CACHE_DIR, f"{clean_id}_{rating}_{scale}.{ext}")
    if os.path.exists(disk_file):
        try:
            with open(disk_file, "rb") as f:
                raw = f.read()
            if raw and len(raw) > 100:
                filename = f"card.{ext}"
                if len(_MEMORY_CARD_BYTES_CACHE) < 500:
                    _MEMORY_CARD_BYTES_CACHE[key] = (raw, filename)
                return io.BytesIO(raw), filename
        except Exception:
            pass
        
    # Tier 3: Render card and save to disk
    card_result = None
    try:
        card_result = generate_card(player, scale=scale, animated=animated)
    except Exception as e:
        print(f"Error generating card: {e}")

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
    
    # Persist to disk cache
    actual_ext = "gif" if filename.endswith(".gif") else "png"
    actual_disk_file = os.path.join(CARD_CACHE_DIR, f"{clean_id}_{rating}_{scale}.{actual_ext}")
    try:
        with open(actual_disk_file, "wb") as f:
            f.write(raw)
    except Exception:
        pass

    if len(_MEMORY_CARD_BYTES_CACHE) < 500:
        _MEMORY_CARD_BYTES_CACHE[key] = (raw, filename)
    return io.BytesIO(raw), filename


