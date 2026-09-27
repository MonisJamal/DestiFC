# Phase 1: FIFARenderZ Data & Card Extraction Research

## 1. Data Extraction (API Discovery)
FIFARenderZ has migrated to `renderz.app`. While there is no official API, their frontend uses an internal Elasticsearch REST API (`GET https://renderz.app/api/search/23?v=1&q={encoded_query}`) which is fully accessible without authentication.
* **Mechanism:** The `q` parameter expects a JSON Elasticsearch query, compressed with raw DEFLATE (`zlib`, `wbits=-15`) and base64url-encoded.
* **Response:** Returns JSON with full player stats, traits, prices, image URLs, and precise layout coordinates for card rendering.
* **Strategy:** Use Python's `urllib` or `requests` alongside `zlib` to compress queries and fetch player data directly. This avoids slow and fragile Playwright/BeautifulSoup scraping.

## 2. Card Generation & Fonts
FIFARenderZ cards are **not** static images. They are dynamically rendered using individual image layers (background, player render, club crest, nation flag) and text drawn with specific fonts.
* **Assets:** The API returns URLs for `playerCardBackground`, `playerCardImage`, `flagImage`, and `clubImage`.
* **Coordinates & Colors:** The API payload (`player["animation"]["layout"]` and `player["animation"]["colors"]`) provides the exact X/Y coordinates and hex colors for the text overlays.
* **Fonts used:** 
  * `Cruyff Sans Condensed Bold` (for Rating, Position, Name)
  * `Cruyff Sans Condensed Medium` (for Search Names)
  * `Numbers Medium` (for Ranks/Levels)
* **Strategy:** Download `.woff2` fonts from their CDN, decompress them to `.ttf` using the `fonttools` Python package, and use Python's `Pillow` library (`PIL`) to combine the image layers and draw the text overlays exactly at the given coordinates.

## 3. Alternative Generation Strategy (Playwright)
If Pillow rendering proves too difficult for animated sprite cards or complex CSS overlays, an alternative is rendering a local HTML template with the data and taking a screenshot using Playwright headless browser. We will prioritize the pure Pillow approach first for speed and efficiency in a Discord Bot environment.
