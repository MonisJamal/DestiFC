# DestiFC

## Objective
Create a Discord bot named DestiFC in Python (using discord.py) that simulates the EA Sports FC Mobile experience, similar to the MadridistaaFC bot.

## Core Requirements
* Fetch all FC Mobile data from FIFARenderZ.
* Replicate card images exactly as they appear on FIFARenderZ with the correct fonts (like EA Sans/DIN Pro).
* Implement Drafts, Quests, Vouchers, Squad Building, and PvP.

## Tech Stack
* **Language:** Python
* **Library:** `discord.py`
* **Data Source:** FIFARenderZ (via API/Scraping)
* **Image Generation:** `Pillow` (PIL) for rendering dynamic cards.
* **Database:** SQLite/PostgreSQL for user data.
