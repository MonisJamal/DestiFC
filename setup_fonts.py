import os
import requests
from fontTools.ttLib.woff2 import decompress

FONT_DIR = "assets/fonts"
FONTS = {
    "CruyffSansCondensed-Bold": "https://fonts.frzdb.net/CruyffSansCondensed-Bold.woff2",
    "Numbers-Medium": "https://fonts.frzdb.net/Numbers-Medium.woff2"
}

def download_and_convert_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    
    for font_name, url in FONTS.items():
        woff2_path = os.path.join(FONT_DIR, f"{font_name}.woff2")
        ttf_path = os.path.join(FONT_DIR, f"{font_name}.ttf")
        
        if not os.path.exists(ttf_path):
            print(f"Downloading {font_name}...")
            response = requests.get(url)
            if response.status_code == 200:
                with open(woff2_path, "wb") as f:
                    f.write(response.content)
                print(f"Decompressing {font_name} to TTF...")
                decompress(woff2_path, ttf_path)
                os.remove(woff2_path) # Clean up woff2
            else:
                print(f"Failed to download {font_name}")
        else:
            print(f"Font {font_name}.ttf already exists.")

if __name__ == "__main__":
    download_and_convert_fonts()
