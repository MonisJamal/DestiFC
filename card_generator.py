import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
import json

FONT_DIR = "assets/fonts"

def get_font(name: str, size: int):
    path = os.path.join(FONT_DIR, f"{name}.ttf")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Font {path} not found. Run setup_fonts.py first.")
    return ImageFont.truetype(path, size=size)

def get_image_from_url(url: str, size=None) -> Image.Image:
    # Ensure URL is absolute
    if url.startswith('/'):
        url = f"https://renderz.app{url}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://renderz.app/"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGBA")
    
    if size:
        img = img.resize(size)
    return img

def generate_card(player: dict, output_path: str = None) -> Image.Image:
    """
    Generates a RenderZ-style card for a given player dictionary.
    """
    SCALE = 2  # High Quality Output Multiplier

    images = player.get("images", {})
    anim = player.get("animation", {})
    colors = anim.get("colors", {})
    layout = anim.get("layout", {})
    
    bg_url = images.get("playerCardBackground")
    player_url = images.get("playerCardImage")
    flag_url = images.get("flagImage")
    club_url = images.get("clubImage")
    
    if not bg_url or not player_url:
        raise ValueError("Player data is missing essential image URLs")

    # Fetch Images
    card = get_image_from_url(bg_url, size=(256 * SCALE, 256 * SCALE))
    
    try:
        player_img = get_image_from_url(player_url)
        player_img = player_img.resize((256 * SCALE, 256 * SCALE), Image.Resampling.LANCZOS)
        card.alpha_composite(player_img, (0, 0))
    except Exception as e:
        print(f"Failed to fetch player image: {e}")

    # Helper for drawing components based on layout
    def draw_image_layer(url, layout_key):
        if url and layout_key in layout:
            l = layout[layout_key]
            try:
                img_size = (int(l["sizeX"]) * SCALE, int(l["sizeY"]) * SCALE)
                img = get_image_from_url(url, size=img_size)
                # Lanczos filter for better downscaling
                if img.size != img_size:
                    img = img.resize(img_size, Image.Resampling.LANCZOS)
                card.alpha_composite(img, (int(l["posX"]) * SCALE, int(l["posY"]) * SCALE))
            except Exception as e:
                print(f"Failed to fetch {layout_key}: {e}")

    draw_image_layer(flag_url, "nation")
    league_url = images.get("leagueImage")
    draw_image_layer(league_url, "league")
    draw_image_layer(club_url, "club")

    draw = ImageDraw.Draw(card)
    font_bold = lambda size: get_font("CruyffSansCondensed-Bold", size)
    
    rating_color = colors.get("rating", "#FDF6D1")
    position_color = colors.get("position", "#FDF6D1")
    name_color = colors.get("name", "#493721")

    # Helper for centered text
    def draw_centered_text(text, layout_key, color, y_offset=0):
        if layout_key in layout:
            l = layout[layout_key]
            x = (int(l["posX"]) + (int(l["sizeX"]) / 2)) * SCALE
            y = (int(l["posY"]) + (int(l["sizeY"]) / 2) + y_offset) * SCALE
            font = font_bold(int(l.get("fontSize", 24)) * SCALE)
            draw.text((x, y), str(text), fill=color, font=font, anchor='mm')

    # CSS vertical centering often requires a slight visual bump downwards in Pillow
    draw_centered_text(player.get("rating", "?"), "rating", rating_color, y_offset=-2)
    draw_centered_text(player.get("position", "?").upper(), "position", position_color, y_offset=-1)
    
    # Name usually doesn't have a bounding box size in layout, it just has posX/posY as the center
    name_layout = layout.get("name", {})
    if name_layout:
        name = player.get("cardName") or player.get("lastName", "?")
        font = font_bold(int(name_layout.get("fontSize", 22)) * SCALE)
        x = int(name_layout.get("posX", 128)) * SCALE
        y = int(name_layout.get("posY", 178)) * SCALE
        draw.text(
            (x, y),
            name.upper(),
            fill=name_color,
            font=font,
            anchor='mm'  # middle-middle handles dynamic padding better
        )

    if output_path:
        card.save(output_path)
        print(f"Saved card to {output_path}")

    return card

if __name__ == "__main__":
    if not os.path.exists("test_player.json"):
        print("test_player.json not found. Run renderz_api.py first.")
    else:
        with open("test_player.json", "r") as f:
            player_data = json.load(f)
            # Create output dir
            os.makedirs("output", exist_ok=True)
            output_file = f"output/{player_data.get('cardName', 'unknown')}_card.png"
            generate_card(player_data, output_file)
