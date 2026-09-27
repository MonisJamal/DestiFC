from PIL import Image, ImageDraw
from card_generator import generate_card
import json
import io

def draw_pitch(width=800, height=1200):
    img = Image.new('RGB', (width, height), (34, 139, 34))
    draw = ImageDraw.Draw(img)
    
    # Border
    draw.rectangle([20, 20, width-20, height-20], outline="white", width=5)
    
    # Halfway line
    draw.line([(20, height//2), (width-20, height//2)], fill="white", width=5)
    
    # Center circle
    cx, cy = width//2, height//2
    r = 80
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline="white", width=5)
    
    # Center spot
    draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill="white")
    
    # Penalty boxes (top and bottom)
    box_w = 400
    box_h = 150
    draw.rectangle([width//2 - box_w//2, 20, width//2 + box_w//2, 20 + box_h], outline="white", width=5)
    draw.rectangle([width//2 - box_w//2, height-20-box_h, width//2 + box_w//2, height-20], outline="white", width=5)
    
    # Goal boxes
    g_w = 200
    g_h = 60
    draw.rectangle([width//2 - g_w//2, 20, width//2 + g_w//2, 20 + g_h], outline="white", width=5)
    draw.rectangle([width//2 - g_w//2, height-20-g_h, width//2 + g_w//2, height-20], outline="white", width=5)
    
    return img

def get_coordinates(formation, width=800, height=1200):
    # Returns a dict mapping position string to (x, y) center points
    coords = {}
    
    # Goalkeeper is always bottom center
    coords['GK'] = (width//2, height - 120)
    
    if formation == "4-3-3":
        coords['LB'] = (width * 0.15, height * 0.75)
        coords['CB1'] = (width * 0.35, height * 0.8)
        coords['CB2'] = (width * 0.65, height * 0.8)
        coords['RB'] = (width * 0.85, height * 0.75)
        
        coords['CM1'] = (width * 0.25, height * 0.5)
        coords['CM2'] = (width * 0.5, height * 0.5)
        coords['CM3'] = (width * 0.75, height * 0.5)
        
        coords['LW'] = (width * 0.2, height * 0.2)
        coords['ST'] = (width * 0.5, height * 0.15)
        coords['RW'] = (width * 0.8, height * 0.2)
        
    elif formation == "4-4-2":
        coords['LB'] = (width * 0.15, height * 0.75)
        coords['CB1'] = (width * 0.35, height * 0.8)
        coords['CB2'] = (width * 0.65, height * 0.8)
        coords['RB'] = (width * 0.85, height * 0.75)
        
        coords['LM'] = (width * 0.15, height * 0.5)
        coords['CM1'] = (width * 0.35, height * 0.5)
        coords['CM2'] = (width * 0.65, height * 0.5)
        coords['RM'] = (width * 0.85, height * 0.5)
        
        coords['ST1'] = (width * 0.35, height * 0.2)
        coords['ST2'] = (width * 0.65, height * 0.2)
        
    elif formation == "4-2-3-1":
        coords['LB'] = (width * 0.15, height * 0.75)
        coords['CB1'] = (width * 0.35, height * 0.8)
        coords['CB2'] = (width * 0.65, height * 0.8)
        coords['RB'] = (width * 0.85, height * 0.75)
        
        coords['CDM1'] = (width * 0.35, height * 0.6)
        coords['CDM2'] = (width * 0.65, height * 0.6)
        
        coords['LM'] = (width * 0.2, height * 0.4)
        coords['CAM'] = (width * 0.5, height * 0.35)
        coords['RM'] = (width * 0.8, height * 0.4)
        
        coords['ST'] = (width * 0.5, height * 0.15)
        
    elif formation == "3-4-3":
        coords['CB1'] = (width * 0.25, height * 0.8)
        coords['CB2'] = (width * 0.5, height * 0.8)
        coords['CB3'] = (width * 0.75, height * 0.8)
        
        coords['LM'] = (width * 0.15, height * 0.5)
        coords['CM1'] = (width * 0.35, height * 0.5)
        coords['CM2'] = (width * 0.65, height * 0.5)
        coords['RM'] = (width * 0.85, height * 0.5)
        
        coords['LW'] = (width * 0.2, height * 0.2)
        coords['ST'] = (width * 0.5, height * 0.15)
        coords['RW'] = (width * 0.8, height * 0.2)
        
    elif formation == "5-3-2":
        coords['LWB'] = (width * 0.1, height * 0.7)
        coords['CB1'] = (width * 0.3, height * 0.8)
        coords['CB2'] = (width * 0.5, height * 0.8)
        coords['CB3'] = (width * 0.7, height * 0.8)
        coords['RWB'] = (width * 0.9, height * 0.7)
        
        coords['CM1'] = (width * 0.25, height * 0.5)
        coords['CM2'] = (width * 0.5, height * 0.5)
        coords['CM3'] = (width * 0.75, height * 0.5)
        
        coords['ST1'] = (width * 0.35, height * 0.2)
        coords['ST2'] = (width * 0.65, height * 0.2)
        
    elif formation == "4-1-2-1-2 (Wide)":
        coords['LB'] = (width * 0.15, height * 0.75)
        coords['CB1'] = (width * 0.35, height * 0.8)
        coords['CB2'] = (width * 0.65, height * 0.8)
        coords['RB'] = (width * 0.85, height * 0.75)
        
        coords['CDM'] = (width * 0.5, height * 0.65)
        coords['LM'] = (width * 0.15, height * 0.45)
        coords['RM'] = (width * 0.85, height * 0.45)
        coords['CAM'] = (width * 0.5, height * 0.3)
        
        coords['ST1'] = (width * 0.35, height * 0.15)
        coords['ST2'] = (width * 0.65, height * 0.15)
        
    return coords

def generate_lineup_image(squad_data, inventory_dict):
    """
    squad_data: The JSON squad object (formation and players)
    inventory_dict: Map of inv_id to full player_data JSON string
    """
    width = 800
    height = 1200
    pitch = draw_pitch(width, height)
    
    formation = squad_data.get("formation", "4-3-3")
    players = squad_data.get("players", {})
    coords = get_coordinates(formation, width, height)
    
    # Card size to paste
    cw, ch = 128, 128
    
    for pos, coord in coords.items():
        player_info = players.get(pos)
        if player_info and player_info.get("inv_id"):
            inv_id = player_info["inv_id"]
            raw_data = inventory_dict.get(inv_id)
            if raw_data:
                player_json = json.loads(raw_data)
                try:
                    card_img = generate_card(player_json)
                    # Resize card to fit nicely on the pitch
                    card_img = card_img.resize((cw, ch), Image.Resampling.LANCZOS)
                    # Paste using alpha channel
                    pitch.paste(card_img, (int(coord[0] - cw//2), int(coord[1] - ch//2)), card_img)
                except Exception as e:
                    print(f"Error drawing card for {pos}: {e}")
        else:
            # Draw an empty placeholder
            draw = ImageDraw.Draw(pitch)
            px, py = int(coord[0]), int(coord[1])
            draw.ellipse([px-30, py-30, px+30, py+30], fill="gray", outline="white", width=3)
            # draw text?
            
    return pitch
