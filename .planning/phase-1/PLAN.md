# Phase 1: Data Extraction & Card Rendering

## Objective
Build the foundational data pipeline for DestiFC. We will create a Python module that interacts with the `renderz.app` undocumented API to fetch FC Mobile player data and a script that dynamically composites their card images identically to the website using Pillow.

## Step-by-Step Implementation

### Step 1: RenderZ API Client (`renderz_api.py`)
1. Create a Python script containing a function `fetch_players(query: str, limit: int = 10)`.
2. Implement the zlib DEFLATE compression and base64url encoding required by the RenderZ Elasticsearch proxy.
3. Make HTTP GET requests to `https://renderz.app/api/search/23?v=1&q={encoded_query}`.
4. Parse the JSON response and return a structured dictionary/object of players.

### Step 2: Font Acquisition & Prep
1. Create a setup script or manual step to download the `.woff2` fonts from `https://fonts.frzdb.net/`.
   - `CruyffSansCondensed-Bold.woff2`
   - `Numbers-Medium.woff2`
2. Write a short script using `fonttools` to decompress the `.woff2` files into `.ttf` format so Pillow can use them.

### Step 3: Card Generator (`card_generator.py`)
1. Create a function `generate_card(player_data: dict) -> BytesIO`.
2. Extract the layer URLs from the player data (`playerCardBackground`, `playerCardImage`, `flagImage`, `clubImage`).
3. Download these images into memory (using `requests`).
4. Use `PIL.Image` to alpha composite (overlay) the layers together.
   * Background -> Base
   * Player Render -> (0,0)
   * Nation Flag -> (83, 188)
   * Club Crest -> (147, 188)
5. Use `PIL.ImageDraw` and the decompressed TTF fonts to draw the OVR rating, Position, and Name using the colors and coordinates specified in `player["animation"]["colors"]`.
6. Save the final composed image to a BytesIO buffer (ready to be sent to Discord later) or save to disk for testing.

### Step 4: Verification
1. Run `renderz_api.py` to fetch a popular player (e.g., "Messi" or "Ronaldo").
2. Pass the resulting data dictionary into `generate_card()`.
3. Visually compare the output PNG file to the card shown on `renderz.app` to ensure exact parity in font, sizing, colors, and layout.
