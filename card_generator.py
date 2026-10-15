import os
import re
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
try:
    from curl_cffi import requests
except ImportError:
    import requests
import json
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

try:
    from maps import nation_map, club_map
except ImportError:
    nation_map = {}
    club_map = {}

FONT_DIR = "assets/fonts"
CACHE_DIR = "assets/cache/images"
CARD_CACHE_DIR = "assets/cache/cards"

os.makedirs(FONT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CARD_CACHE_DIR, exist_ok=True)

# High-performance persistent HTTP session with connection pooling

# In-memory fast image cache (bounded to prevent container OOM)
_MEMORY_IMAGE_CACHE = {}
_MEMORY_CARD_CACHE = {}
_MEMORY_CARD_BYTES_CACHE = {}

DEFAULT_CARD_LAYOUT = {
    'player': {'sizeX': 256, 'sizeY': 256, 'posX': 0, 'posY': 0},
    'rating': {'sizeX': 80, 'sizeY': 80, 'posX': 36.167, 'posY': 4.083, 'fontSize': 36},
    'position': {'sizeX': 40, 'sizeY': 20, 'posX': 56, 'posY': 64, 'fontSize': 24},
    'nation': {'sizeX': 24, 'sizeY': 24, 'posX': 82.7, 'posY': 188},
    'club': {'sizeX': 24, 'sizeY': 24, 'posX': 146.6, 'posY': 188},
    'name': {'sizeX': 0, 'sizeY': 0, 'posX': 128, 'posY': 172, 'fontSize': 21},
    'level': {'sizeX': 64, 'sizeY': 32, 'posX': 128, 'posY': 233, 'fontSize': 23},
    'rank': {'sizeX': 32, 'sizeY': 32, 'posX': 128, 'posY': 232}
}

def resolve_nation_id(val):
    if not val:
        return None
    if isinstance(val, dict):
        if val.get('id'):
            return val['id']
        val = val.get('name') or ''
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s.isdigit():
        return int(s)
    clean_s = re.sub(r'[^\w\s]', '', s).strip().lower()
    if not clean_s:
        return None
    for nid, name in nation_map.items():
        clean_name = re.sub(r'[^\w\s]', '', name).strip().lower()
        if clean_s == clean_name or clean_s in clean_name or clean_name in clean_s:
            return nid
    return None

def resolve_club_id(val):
    if not val:
        return None
    if isinstance(val, dict):
        if val.get('id'):
            return val['id']
        val = val.get('name') or ''
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s.isdigit():
        return int(s)
    low = s.lower()
    if 'icon' in low:
        return 114154
    if 'hero' in low:
        return 115935
    clean_s = re.sub(r'[^\w\s]', '', s).strip().lower()
    if not clean_s:
        return None
    # 1. Exact match pass
    for cid, name in club_map.items():
        clean_name = re.sub(r'[^\w\s]', '', name).strip().lower()
        if clean_s == clean_name:
            return cid
    # 2. Substring match prioritizing longest match
    candidates = []
    for cid, name in club_map.items():
        clean_name = re.sub(r'[^\w\s]', '', name).strip().lower()
        if not clean_name:
            continue
        if clean_s in clean_name or clean_name in clean_s:
            candidates.append((len(clean_name), cid))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None

DEFAULT_CARD_COLORS = {
    'rating': '#FFFFFF',
    'position': '#FFFFFF',
    'name': '#FFFFFF',
    'level': '#FFFFFF'
}

def format_card_color(color_val, fallback='#FFFFFF'):
    """
    Returns the exact color defined by RenderZ, formatted cleanly as a valid hex string.
    Only falls back if no valid color is provided.
    """
    if not color_val or not isinstance(color_val, str):
        return fallback
    c = color_val.strip()
    if not c:
        return fallback
    if not c.startswith('#'):
        c = '#' + c
    clean_hex = c.lstrip('#')
    if len(clean_hex) in (3, 6) and all(ch in '0123456789abcdefABCDEF' for ch in clean_hex):
        return c.upper()
    return fallback


def _put_memory_cache(cache_dict, key, val, max_items=25):
    if len(cache_dict) >= max_items:
        try:
            cache_dict.pop(next(iter(cache_dict)), None)
        except Exception:
            pass
    cache_dict[key] = val

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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://renderz.app/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        for attempt in range(3):
            try:
                if "curl_cffi" in str(requests):
                    resp = requests.get(url, headers=headers, timeout=15.0, impersonate='chrome124')
                else:
                    resp = requests.get(url, headers=headers, timeout=15.0)
                    
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content)).convert("RGBA")
                    if img.width == 1 and img.height == 1:
                        raise Exception("Transparent pixel detected")
                        
                    try:
                        img.save(disk_cache_path, "PNG")
                    except Exception:
                        pass
                    break
                elif resp.status_code == 404:
                    break
            except Exception as e:
                import time
                time.sleep(1)
                if attempt == 2:
                    print(f"Failed to fetch {url} after 3 attempts: {e}")
    if img is not None:
        if size and img.size != size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        _put_memory_cache(_MEMORY_IMAGE_CACHE, cache_key, img.copy(), max_items=25)
        
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

    clean_id = "".join([c for c in player_id if c.isalnum() or c in ('-', '_')])
    disk_card_file = os.path.join(CARD_CACHE_DIR, f"{clean_id}_{rating}_{SCALE}.png")
    if not animated and os.path.exists(disk_card_file):
        try:
            img = Image.open(disk_card_file).convert("RGBA")
            _put_memory_cache(_MEMORY_CARD_CACHE, card_cache_key, img.copy(), max_items=25)
            return img
        except Exception:
            pass

    images = player.get("images") or {}
    anim = player.get("animation") or {}
    raw_colors = anim.get("colors") or player.get("colors") or {}
    if not isinstance(raw_colors, dict):
        raw_colors = {}
    raw_layout = anim.get("layout") or {}
    
    # Safely merge with DEFAULT_CARD_LAYOUT to guarantee all layout attributes exist
    layout = dict(DEFAULT_CARD_LAYOUT)
    if isinstance(raw_layout, dict):
        for k, v in raw_layout.items():
            if isinstance(v, dict):
                layout[k] = {**DEFAULT_CARD_LAYOUT.get(k, {}), **v}
            else:
                layout[k] = v

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
                            max_frames = int(sub.get("maxFrames") or 0)
                            break
                if sprite_url:
                    break

    bg_url = (
        images.get("playerCardBackground") or 
        images.get("background") or 
        player.get("bg_image") or 
        player.get("playerCardBackground") or 
        images.get("cardBackground")
    )
    player_url = (
        images.get("playerCardImage") or 
        images.get("playerImage") or 
        player.get("imageUrl") or 
        player.get("image") or 
        player.get("playerCardImage") or 
        images.get("playerCardAvatar") or 
        images.get("playerCardSpecialAvatar") or
        images.get("avatar")
    )
    flag_url = (
        images.get("flagImage") or 
        player.get("flagImage") or 
        images.get("flag") or
        (player.get("images") or {}).get("flagImage")
    )
    club_url = (
        images.get("clubImage") or 
        player.get("clubImage") or 
        images.get("club") or
        (player.get("images") or {}).get("clubImage")
    )
    league_url = (
        images.get("leagueImage") or 
        player.get("leagueImage") or 
        images.get("league") or
        (player.get("images") or {}).get("leagueImage")
    )

    is_custom_card = bool(
        player.get("is_custom") or 
        player.get("is_signature_box") or 
        player.get("custom_background_url") or 
        str(player_id).startswith("custom_") or 
        str(player_id).startswith("sig_")
    )

    # Smart fallback for nation flag and club badge URLs if omitted in images
    if not is_custom_card:
        if not flag_url:
            nid = resolve_nation_id(player.get("nation") or player.get("nation_name") or player.get("country"))
            if nid:
                flag_url = f"https://images-v2.renderz.app/flags_23_128x128_{nid}"
        if not club_url:
            cid = resolve_club_id(player.get("club") or player.get("club_name") or player.get("team"))
            if cid:
                club_url = f"https://images-v2.renderz.app/club_23_{cid}"
    
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
        tasks["flag"] = (flag_url, (int(float(l["sizeX"]) * SCALE), int(float(l["sizeY"]) * SCALE)))
    if club_url and "club" in layout:
        l = layout["club"]
        tasks["club"] = (club_url, (int(float(l["sizeX"]) * SCALE), int(float(l["sizeY"]) * SCALE)))
    if league_url and "league" in layout:
        l = layout["league"]
        tasks["league"] = (league_url, (int(float(l["sizeX"]) * SCALE), int(float(l["sizeY"]) * SCALE)))

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
        if not fetched_images.get("player"):
            return None # Force fallback if both BG and player are missing
        # Preserve full transparent alpha for standalone / custom card renders
        card = Image.new("RGBA", target_size, (0, 0, 0, 0))
    
    overlay = Image.new("RGBA", target_size, (0,0,0,0))
    
    player_img = fetched_images.get("player")
    if player_img:
        overlay.alpha_composite(player_img, (0, 0))

    if "flag" in fetched_images and fetched_images["flag"] and "nation" in layout:
        l = layout["nation"]
        overlay.alpha_composite(fetched_images["flag"], (int(float(l["posX"]) * SCALE), int(float(l["posY"]) * SCALE)))

    if "league" in fetched_images and fetched_images["league"] and "league" in layout:
        l = layout["league"]
        overlay.alpha_composite(fetched_images["league"], (int(float(l["posX"]) * SCALE), int(float(l["posY"]) * SCALE)))

    if "club" in fetched_images and fetched_images["club"] and "club" in layout:
        l = layout["club"]
        overlay.alpha_composite(fetched_images["club"], (int(float(l["posX"]) * SCALE), int(float(l["posY"]) * SCALE)))

    draw = ImageDraw.Draw(overlay)
    font_bold = lambda size: get_font("CruyffSansCondensed-Bold", size)
    
    # Authentic font colors matching RenderZ specifications directly
    rating_color = format_card_color(raw_colors.get("rating"), fallback="#FFFFFF")
    position_color = format_card_color(raw_colors.get("position"), fallback=rating_color)
    name_color = format_card_color(raw_colors.get("name"), fallback=rating_color)

    def draw_centered_text(text, layout_key, color, y_offset=0):
        if layout_key in layout:
            l = layout[layout_key]
            x = (float(l["posX"]) + (float(l["sizeX"]) / 2)) * SCALE
            y = (float(l["posY"]) + (float(l["sizeY"]) / 2) + y_offset) * SCALE
            font = font_bold(int(float(l.get("fontSize", 24)) * SCALE))
            draw.text((x, y), str(text), fill=color, font=font, anchor='mm')

    if not is_custom_card:
        draw_centered_text(player.get("rating", "?"), "rating", rating_color, y_offset=-2)
        draw_centered_text(str(player.get("position", "?")).upper(), "position", position_color, y_offset=-1)
        
        name_layout = layout.get("name", {})
        if name_layout:
            name = str(player.get("cardName") or player.get("lastName", "?"))
            base_font_size = float(name_layout.get("fontSize", 21))
            base_font_size = min(base_font_size, 21.0)
            font_size = int(base_font_size * SCALE)

            # Dynamic font fitting to ensure long names (e.g. Van Nistelrooy) fit proportionally within card frame
            font = font_bold(font_size)
            max_name_width = int(120 * SCALE)
            while font_size > int(10 * SCALE):
                bbox = font.getbbox(name.upper())
                text_w = bbox[2] - bbox[0]
                if text_w <= max_name_width:
                    break
                font_size -= 1
                font = font_bold(font_size)

            x_center = float(name_layout.get("posX", 128))
            if float(name_layout.get("sizeX", 0)) > 0:
                x_center += float(name_layout.get("sizeX")) / 2.0
            x = x_center * SCALE
            
            # Position name cleanly with proper clearance above badges
            raw_y = float(name_layout.get("posY", 174))
            y = min(raw_y, 174.0) * SCALE
            draw.text(
                (x, y),
                name.upper(),
                fill=name_color,
                font=font,
                anchor='mm'
            )
        elif bg_url:
            # Safe fallback text rendering matching official coordinates
            name = str(player.get("cardName") or player.get("lastName", "Player"))
            font = font_bold(int(18 * SCALE))
            draw.text((target_size[0] // 2, int(174 * SCALE)), name.upper()[:14], fill=(255, 255, 255), font=font, anchor='mm')
            draw.text((int(76 * SCALE), int(42 * SCALE)), str(rating), fill=(255, 255, 255), font=font_bold(int(36 * SCALE)), anchor='mm')
            draw.text((int(76 * SCALE), int(73 * SCALE)), str(player.get("position", "ST")).upper(), fill=(255, 255, 255), font=font_bold(int(24 * SCALE)), anchor='mm')

    # If animated and sprite exists, render animated GIF frames
    sprite_sheet = fetched_images.get("sprite")
    if animated and sprite_sheet:
        try:
            cols = sprite_sheet.width // 256
            rows = sprite_sheet.height // 256
            if cols > 0 and rows > 0:
                total_sheet_frames = cols * rows
                # Preserve full authentic animation loop from RenderZ / FC Mobile
                total_frames = max_frames if (max_frames and 0 < max_frames <= total_sheet_frames) else total_sheet_frames
                
                # Up to 45 frames: include every frame for a 100% seamless, smooth loop
                # If sheet exceeds 45 frames: step by 2 while spanning the full animation cycle
                step = 1 if total_frames <= 45 else 2
                frames = []
                
                # Sleek dark stadium walkout backdrop to prevent alpha distortion
                backdrop = Image.new("RGBA", target_size, (18, 20, 26, 255))
                d_back = ImageDraw.Draw(backdrop)
                d_back.ellipse([int(target_size[0]*0.12), int(target_size[1]*0.15), int(target_size[0]*0.88), int(target_size[1]*0.92)], fill=(38, 48, 72, 160))
                backdrop = backdrop.filter(ImageFilter.GaussianBlur(radius=int(14 * SCALE)))

                # Combined card silhouette (including background + player portrait) to never cut off outer card elements
                silhouette = card.copy()
                silhouette.alpha_composite(overlay)
                card_alpha = silhouette.split()[3] if len(silhouette.split()) == 4 else None

                for frame_idx in range(0, total_frames, step):
                    col = frame_idx % cols
                    row = frame_idx // cols
                    box = (col * 256, row * 256, (col + 1) * 256, (row + 1) * 256)
                    frame_sprite = sprite_sheet.crop(box)
                    if SCALE != 1.0:
                        frame_sprite = frame_sprite.resize(target_size, Image.Resampling.BILINEAR)
                    
                    if card_alpha:
                        # Mask sprite alpha to full card silhouette so outside particles/noise do not bleed beyond the card
                        sp_r, sp_g, sp_b, sp_a = frame_sprite.split()
                        sp_a = ImageChops.multiply(sp_a, card_alpha)
                        frame_sprite = Image.merge("RGBA", (sp_r, sp_g, sp_b, sp_a))

                    # Official layer compositing:
                    # 1. Background
                    # 2. Sprite animation effects
                    # 3. Player portrait & badges & typography
                    frame_card = card.copy()
                    frame_card.alpha_composite(frame_sprite)
                    frame_card.alpha_composite(overlay)
                    
                    # Composite cleanly onto the sleek spotlight backdrop
                    final_frame = backdrop.copy()
                    final_frame.alpha_composite(frame_card)
                    frames.append(final_frame.convert("RGB"))
                    
                if frames:
                    _put_memory_cache(_MEMORY_CARD_CACHE, card_cache_key, frames, max_items=5)
                    return frames
        except Exception as e:
            print(f"Error generating animated frames: {e}")

    card.alpha_composite(overlay)
    


    if not animated:
        try:
            card.save(disk_card_file, "PNG")
        except Exception:
            pass
    _put_memory_cache(_MEMORY_CARD_CACHE, card_cache_key, card.copy(), max_items=25)
    return card

def save_card_to_bytes(card_result):
    import io
    binary = io.BytesIO()
    if isinstance(card_result, list) and len(card_result) > 0:
        first_frame = card_result[0]
        w, h = first_frame.size
        
        # Build global adaptive palette from sample frames to prevent flickering & color distortion
        sample_step = max(1, len(card_result) // 8)
        sample_frames = card_result[::sample_step]
        palette_strip = Image.new('RGB', (w, h * len(sample_frames)))
        for idx, fr in enumerate(sample_frames):
            palette_strip.paste(fr, (0, idx * h))
            
        global_palette = palette_strip.quantize(colors=255, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
        
        quantized_frames = [
            fr.quantize(palette=global_palette, dither=Image.Dither.NONE)
            for fr in card_result
        ]
        
        # Dynamically calculate frame duration to maintain natural broadcast speed (~1.6s per loop)
        frame_duration = max(35, min(100, int(1600 / len(quantized_frames))))
        quantized_frames[0].save(
            binary,
            format='GIF',
            save_all=True,
            append_images=quantized_frames[1:],
            duration=frame_duration,
            loop=0,
            optimize=True
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
                if len(_MEMORY_CARD_BYTES_CACHE) < 50:
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

    if len(_MEMORY_CARD_BYTES_CACHE) < 50:
        _MEMORY_CARD_BYTES_CACHE[key] = (raw, filename)
    return io.BytesIO(raw), filename


