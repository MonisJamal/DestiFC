from PIL import Image, ImageDraw, ImageFont, ImageFilter
from card_generator import generate_card
import json
import io
import os
import sqlite3
import time

import concurrent.futures
from functools import lru_cache

# Wide 16:9 Canvas for realistic squad lineup view
W, H = 1600, 900
_PITCH_CACHE = {}

THEMES = {
    "default":     "assets/pitch_bg.jpg",
    "snow":        "assets/pitch_snow.jpg",
    "lava":        "assets/pitch_lava.jpg",
    "cyberpunk":   "assets/pitch_cyber.jpg",
    "galaxy":      "assets/pitch_galaxy.jpg",
    "gold":        "assets/pitch_gold.jpg",
    "desert":      "assets/pitch_desert.jpg",
    "bernabeu":    "assets/pitch_bernabeu.jpg",
    "campnou":     "assets/pitch_campnou.jpg",
    "oldtrafford": "assets/pitch_oldtrafford.jpg",
    "anfield":     "assets/pitch_anfield.jpg",
    "sansiro":     "assets/pitch_sansiro.jpg",
    "allianz":     "assets/pitch_allianz.jpg",
    "maracana":    "assets/pitch_maracana.jpg",
    "wembley":     "assets/pitch_wembley.jpg",
}

THEME_GLOW = {
    "default":     (0, 240, 255),    # Neon Cyan
    "snow":        (160, 235, 255),  # Ice Cyan
    "lava":        (255, 90, 10),    # Fiery Orange
    "cyberpunk":   (255, 0, 180),    # Neon Magenta
    "galaxy":      (190, 100, 255),  # Cosmic Purple
    "gold":        (255, 215, 0),    # Royal Gold
    "desert":      (255, 175, 45),   # Golden Sand
    "bernabeu":    (255, 255, 255),  # Pure Madrid White & Gold
    "campnou":     (0, 77, 152),     # Deep Blaugrana Blue
    "oldtrafford": (218, 41, 28),    # Red Devil Crimson
    "anfield":     (200, 16, 46),    # Liverpool Red
    "sansiro":     (255, 30, 30),    # Milan Rossoneri / Nerazzurri
    "allianz":     (220, 5, 45),     # Glowing Bayern Red
    "maracana":    (0, 156, 59),     # Verde e Amarela Emerald
    "wembley":     (200, 225, 255),  # Wembley Arch Platinum
}

# Portal edits are intentionally read from the same SQLite database as the bot.
# A small cache keeps image rendering fast while allowing a saved admin change to
# appear in Discord within a few seconds, without restarting the bot.
_PORTAL_CONFIG_CACHE = {"checked_at": 0.0, "layouts": {}, "themes": {}}

def set_cached_layouts(layouts: dict):
    """Dynamically updates cached tactical formation layouts (e.g. from Supabase)."""
    if isinstance(layouts, dict):
        if "layouts" not in _PORTAL_CONFIG_CACHE:
            _PORTAL_CONFIG_CACHE["layouts"] = {}
        _PORTAL_CONFIG_CACHE["layouts"].update(layouts)

def _load_portal_config():
    if time.monotonic() - _PORTAL_CONFIG_CACHE["checked_at"] < 3:
        return _PORTAL_CONFIG_CACHE

    _PORTAL_CONFIG_CACHE["checked_at"] = time.monotonic()
    try:
        with sqlite3.connect("destifc.db", timeout=1) as db:
            layouts = {}
            for formation_name, positions_json in db.execute(
                "SELECT formation_name, positions_json FROM formation_layouts"
            ):
                try:
                    layouts[formation_name] = json.loads(positions_json)
                except (TypeError, json.JSONDecodeError):
                    continue
            themes = {
                theme_id: background_path
                for theme_id, background_path in db.execute(
                    "SELECT theme_id, background_path FROM theme_overrides"
                )
            }
            _PORTAL_CONFIG_CACHE["layouts"].update(layouts)
            _PORTAL_CONFIG_CACHE["themes"].update(themes)
    except (sqlite3.Error, OSError):
        pass
    return _PORTAL_CONFIG_CACHE

# Dedicated tactical coordinates tailored for all 34 formations
FORMATION_TACTICAL_COORDS = {
    "4-3-3 Attack": {
        "ST": [
            0.5,
            0.08
        ],
        "LW": [
            0.14,
            0.16
        ],
        "RW": [
            0.86,
            0.16
        ],
        "CAM": [
            0.5,
            0.32
        ],
        "CM1": [
            0.26,
            0.48
        ],
        "CM2": [
            0.74,
            0.48
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-3 Flat": {
        "ST": [
            0.5,
            0.08
        ],
        "LW": [
            0.14,
            0.16
        ],
        "RW": [
            0.86,
            0.16
        ],
        "CM1": [
            0.22,
            0.46
        ],
        "CM2": [
            0.5,
            0.44
        ],
        "CM3": [
            0.78,
            0.46
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-3 Holding": {
        "ST": [
            0.5,
            0.08
        ],
        "LW": [
            0.14,
            0.16
        ],
        "RW": [
            0.86,
            0.16
        ],
        "CM1": [
            0.26,
            0.4
        ],
        "CM2": [
            0.74,
            0.4
        ],
        "CDM": [
            0.5,
            0.58
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-3 Defend": {
        "ST": [
            0.5,
            0.08
        ],
        "LW": [
            0.14,
            0.16
        ],
        "RW": [
            0.86,
            0.16
        ],
        "CM": [
            0.5,
            0.36
        ],
        "CDM1": [
            0.3,
            0.54
        ],
        "CDM2": [
            0.7,
            0.54
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-3 False 9": {
        "CF": [
            0.5,
            0.2
        ],
        "LW": [
            0.14,
            0.1
        ],
        "RW": [
            0.86,
            0.1
        ],
        "CM1": [
            0.25,
            0.44
        ],
        "CM2": [
            0.75,
            0.44
        ],
        "CDM": [
            0.5,
            0.6
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-4-2 Flat": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "LM": [
            0.08,
            0.42
        ],
        "CM1": [
            0.35,
            0.46
        ],
        "CM2": [
            0.65,
            0.46
        ],
        "RM": [
            0.92,
            0.42
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-4-2 Holding": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "LM": [
            0.08,
            0.38
        ],
        "RM": [
            0.92,
            0.38
        ],
        "CDM1": [
            0.38,
            0.48
        ],
        "CDM2": [
            0.62,
            0.48
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.32,
            0.77
        ],
        "CB2": [
            0.68,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-4-1-1 Flat": {
        "ST": [
            0.5,
            0.08
        ],
        "CF": [
            0.5,
            0.26
        ],
        "LM": [
            0.08,
            0.46
        ],
        "CM1": [
            0.34,
            0.49
        ],
        "CM2": [
            0.66,
            0.49
        ],
        "RM": [
            0.92,
            0.46
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-4-1-1 Attack": {
        "ST": [
            0.5,
            0.08
        ],
        "CAM": [
            0.5,
            0.26
        ],
        "LM": [
            0.08,
            0.46
        ],
        "CM1": [
            0.34,
            0.49
        ],
        "CM2": [
            0.66,
            0.49
        ],
        "RM": [
            0.92,
            0.46
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-2-3-1 Narrow": {
        "ST": [
            0.5,
            0.08
        ],
        "CAM1": [
            0.22,
            0.28
        ],
        "CAM2": [
            0.5,
            0.3
        ],
        "CAM3": [
            0.78,
            0.28
        ],
        "CDM1": [
            0.38,
            0.49
        ],
        "CDM2": [
            0.62,
            0.49
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.32,
            0.77
        ],
        "CB2": [
            0.68,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-2-3-1 Wide": {
        "ST": [
            0.5,
            0.08
        ],
        "LM": [
            0.08,
            0.3
        ],
        "CAM": [
            0.5,
            0.3
        ],
        "RM": [
            0.92,
            0.3
        ],
        "CDM1": [
            0.38,
            0.49
        ],
        "CDM2": [
            0.62,
            0.49
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.32,
            0.77
        ],
        "CB2": [
            0.68,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-2-2-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM1": [
            0.18,
            0.3
        ],
        "CAM2": [
            0.82,
            0.3
        ],
        "CDM1": [
            0.38,
            0.49
        ],
        "CDM2": [
            0.62,
            0.49
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.32,
            0.77
        ],
        "CB2": [
            0.68,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-2-4": {
        "LW": [
            0.08,
            0.12
        ],
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "RW": [
            0.92,
            0.12
        ],
        "CM1": [
            0.35,
            0.46
        ],
        "CM2": [
            0.65,
            0.46
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-1-2-1-2 Narrow": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.26
        ],
        "CM1": [
            0.24,
            0.44
        ],
        "CM2": [
            0.76,
            0.44
        ],
        "CDM": [
            0.5,
            0.6
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-1-2-1-2 Wide": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.26
        ],
        "LM": [
            0.08,
            0.44
        ],
        "RM": [
            0.92,
            0.44
        ],
        "CDM": [
            0.5,
            0.6
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-1-3-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "LM": [
            0.08,
            0.38
        ],
        "CM": [
            0.5,
            0.38
        ],
        "RM": [
            0.92,
            0.38
        ],
        "CDM": [
            0.5,
            0.58
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-1-4-1": {
        "ST": [
            0.5,
            0.08
        ],
        "LM": [
            0.08,
            0.38
        ],
        "CM1": [
            0.34,
            0.4
        ],
        "CM2": [
            0.66,
            0.4
        ],
        "RM": [
            0.92,
            0.38
        ],
        "CDM": [
            0.5,
            0.58
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-2-1-3": {
        "LW": [
            0.14,
            0.14
        ],
        "ST": [
            0.5,
            0.08
        ],
        "RW": [
            0.86,
            0.14
        ],
        "CAM": [
            0.5,
            0.3
        ],
        "CDM1": [
            0.38,
            0.49
        ],
        "CDM2": [
            0.62,
            0.49
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.32,
            0.77
        ],
        "CB2": [
            0.68,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-1-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.28
        ],
        "CM1": [
            0.22,
            0.48
        ],
        "CM2": [
            0.5,
            0.5
        ],
        "CM3": [
            0.78,
            0.48
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-3-2-1": {
        "ST": [
            0.5,
            0.08
        ],
        "LF": [
            0.28,
            0.24
        ],
        "RF": [
            0.72,
            0.24
        ],
        "CM1": [
            0.22,
            0.48
        ],
        "CM2": [
            0.5,
            0.5
        ],
        "CM3": [
            0.78,
            0.48
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-5-1 Flat": {
        "ST": [
            0.5,
            0.08
        ],
        "LM": [
            0.08,
            0.42
        ],
        "CM1": [
            0.3,
            0.46
        ],
        "CM2": [
            0.5,
            0.48
        ],
        "CM3": [
            0.7,
            0.46
        ],
        "RM": [
            0.92,
            0.42
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "4-5-1 Attack": {
        "ST": [
            0.5,
            0.08
        ],
        "CAM1": [
            0.3,
            0.28
        ],
        "CAM2": [
            0.7,
            0.28
        ],
        "LM": [
            0.08,
            0.44
        ],
        "CM": [
            0.5,
            0.48
        ],
        "RM": [
            0.92,
            0.44
        ],
        "LB": [
            0.08,
            0.74
        ],
        "CB1": [
            0.35,
            0.77
        ],
        "CB2": [
            0.65,
            0.77
        ],
        "RB": [
            0.92,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-1-4-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "LM": [
            0.06,
            0.3
        ],
        "CM1": [
            0.34,
            0.32
        ],
        "CM2": [
            0.66,
            0.32
        ],
        "RM": [
            0.94,
            0.3
        ],
        "CDM": [
            0.5,
            0.46
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.62
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-4-1-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.26
        ],
        "LM": [
            0.08,
            0.44
        ],
        "CM1": [
            0.34,
            0.46
        ],
        "CM2": [
            0.66,
            0.46
        ],
        "RM": [
            0.92,
            0.44
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-4-2-1": {
        "ST": [
            0.5,
            0.08
        ],
        "LF": [
            0.28,
            0.24
        ],
        "RF": [
            0.72,
            0.24
        ],
        "LM": [
            0.08,
            0.44
        ],
        "CM1": [
            0.34,
            0.46
        ],
        "CM2": [
            0.66,
            0.46
        ],
        "RM": [
            0.92,
            0.44
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-4-3 Flat": {
        "LW": [
            0.14,
            0.14
        ],
        "ST": [
            0.5,
            0.08
        ],
        "RW": [
            0.86,
            0.14
        ],
        "LM": [
            0.08,
            0.44
        ],
        "CM1": [
            0.34,
            0.46
        ],
        "CM2": [
            0.66,
            0.46
        ],
        "RM": [
            0.92,
            0.44
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-4-3 Diamond": {
        "LW": [
            0.14,
            0.14
        ],
        "ST": [
            0.5,
            0.08
        ],
        "RW": [
            0.86,
            0.14
        ],
        "CAM": [
            0.5,
            0.25
        ],
        "LM": [
            0.08,
            0.35
        ],
        "RM": [
            0.92,
            0.35
        ],
        "CDM": [
            0.5,
            0.46
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.62
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-5-1-1": {
        "ST": [
            0.5,
            0.08
        ],
        "CF": [
            0.5,
            0.22
        ],
        "LM": [
            0.08,
            0.34
        ],
        "CM1": [
            0.3,
            0.36
        ],
        "CDM": [
            0.5,
            0.48
        ],
        "CM2": [
            0.7,
            0.36
        ],
        "RM": [
            0.92,
            0.34
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.62
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "3-5-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.24
        ],
        "LM": [
            0.08,
            0.44
        ],
        "CDM1": [
            0.28,
            0.46
        ],
        "CDM2": [
            0.72,
            0.46
        ],
        "RM": [
            0.92,
            0.44
        ],
        "CB1": [
            0.22,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.78,
            0.74
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "5-2-1-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CAM": [
            0.5,
            0.26
        ],
        "CM1": [
            0.32,
            0.46
        ],
        "CM2": [
            0.68,
            0.46
        ],
        "LWB": [
            0.06,
            0.66
        ],
        "CB1": [
            0.24,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.76,
            0.74
        ],
        "RWB": [
            0.94,
            0.66
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "5-2-2-1": {
        "LW": [
            0.14,
            0.14
        ],
        "ST": [
            0.5,
            0.08
        ],
        "RW": [
            0.86,
            0.14
        ],
        "CM1": [
            0.32,
            0.46
        ],
        "CM2": [
            0.68,
            0.46
        ],
        "LWB": [
            0.06,
            0.66
        ],
        "CB1": [
            0.24,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.76,
            0.74
        ],
        "RWB": [
            0.94,
            0.66
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "5-3-2": {
        "ST1": [
            0.35,
            0.08
        ],
        "ST2": [
            0.65,
            0.08
        ],
        "CM1": [
            0.22,
            0.38
        ],
        "CM2": [
            0.5,
            0.38
        ],
        "CM3": [
            0.78,
            0.38
        ],
        "LWB": [
            0.06,
            0.66
        ],
        "CB1": [
            0.24,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.76,
            0.74
        ],
        "RWB": [
            0.94,
            0.66
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "5-4-1 Flat": {
        "ST": [
            0.5,
            0.08
        ],
        "LM": [
            0.08,
            0.42
        ],
        "CM1": [
            0.35,
            0.46
        ],
        "CM2": [
            0.65,
            0.46
        ],
        "RM": [
            0.92,
            0.42
        ],
        "LWB": [
            0.06,
            0.66
        ],
        "CB1": [
            0.24,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.76,
            0.74
        ],
        "RWB": [
            0.94,
            0.66
        ],
        "GK": [
            0.5,
            0.95
        ]
    },
    "5-4-1 Defend": {
        "ST": [
            0.5,
            0.08
        ],
        "LM": [
            0.08,
            0.38
        ],
        "RM": [
            0.92,
            0.38
        ],
        "CDM1": [
            0.38,
            0.48
        ],
        "CDM2": [
            0.62,
            0.48
        ],
        "LWB": [
            0.06,
            0.66
        ],
        "CB1": [
            0.24,
            0.74
        ],
        "CB2": [
            0.5,
            0.6
        ],
        "CB3": [
            0.76,
            0.74
        ],
        "RWB": [
            0.94,
            0.66
        ],
        "GK": [
            0.5,
            0.95
        ]
    }
}

FORMATION_LINES_FALLBACK = {
    "3-1-4-2": [
        (["ST1", "ST2"], 0.40),
        (["LM", "CM1", "CM2", "RM"], 0.59),
        (["CDM"], 0.71),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "3-4-1-2": [
        (["ST1", "ST2"], 0.40),
        (["CAM"], 0.53),
        (["LM", "CM1", "CM2", "RM"], 0.64),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "3-4-2-1": [
        (["ST"], 0.40),
        (["LF", "RF"], 0.50),
        (["LM", "CM1", "CM2", "RM"], 0.64),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "3-4-3 Flat": [
        (["LW", "ST", "RW"], 0.42),
        (["LM", "CM1", "CM2", "RM"], 0.63),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "3-4-3 Diamond": [
        (["LW", "ST", "RW"], 0.42),
        (["CAM"], 0.54),
        (["LM", "RM"], 0.62),
        (["CDM"], 0.71),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "3-5-1-1": [
        (["ST"], 0.40),
        (["CF"], 0.50),
        (["LM", "CM1", "CM2", "RM"], 0.62),
        (["CDM"], 0.71),
        (["CB1", "CB2", "CB3"], 0.82),
        (["GK"], 0.90),
    ],
    "4-1-3-2": [
        (["ST1", "ST2"], 0.40),
        (["LM", "CM", "RM"], 0.57),
        (["CDM"], 0.71),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-1-4-1": [
        (["ST"], 0.40),
        (["LM", "CM1", "CM2", "RM"], 0.59),
        (["CDM"], 0.71),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-2-1-3": [
        (["LW", "ST", "RW"], 0.42),
        (["CAM"], 0.55),
        (["CDM1", "CDM2"], 0.70),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-2-2-2": [
        (["ST1", "ST2"], 0.40),
        (["CAM1", "CAM2"], 0.54),
        (["CDM1", "CDM2"], 0.69),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-2-3-1 Narrow": [
        (["ST"], 0.40),
        (["CAM1", "CAM2", "CAM3"], 0.54),
        (["CDM1", "CDM2"], 0.70),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-2-3-1 Wide": [
        (["ST"], 0.40),
        (["LM", "CAM", "RM"], 0.54),
        (["CDM1", "CDM2"], 0.70),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-3-1-2": [
        (["ST1", "ST2"], 0.40),
        (["CAM"], 0.53),
        (["CM1", "CM2", "CM3"], 0.65),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-3-2-1": [
        (["ST"], 0.40),
        (["LF", "RF"], 0.50),
        (["CM1", "CM2", "CM3"], 0.65),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-4-1-1 Flat": [
        (["ST"], 0.40),
        (["CF"], 0.50),
        (["LM", "CM1", "CM2", "RM"], 0.63),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-4-1-1 Attack": [
        (["ST"], 0.40),
        (["CAM"], 0.51),
        (["LM", "CM1", "CM2", "RM"], 0.63),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-4-2 Holding": [
        (["ST1", "ST2"], 0.40),
        (["LM", "RM"], 0.59),
        (["CDM1", "CDM2"], 0.70),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-5-1 Flat": [
        (["ST"], 0.40),
        (["LM", "CM1", "CM2", "CM3", "RM"], 0.61),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "4-5-1 Attack": [
        (["ST"], 0.40),
        (["CAM1", "CAM2"], 0.53),
        (["LM", "CM", "RM"], 0.63),
        (["LB", "CB1", "CB2", "RB"], 0.81),
        (["GK"], 0.90),
    ],
    "5-2-2-1": [
        (["LW", "ST", "RW"], 0.42),
        (["CM1", "CM2"], 0.63),
        (["LWB", "CB1", "CB2", "CB3", "RWB"], 0.81),
        (["GK"], 0.90),
    ],
    "5-3-2": [
        (["ST1", "ST2"], 0.40),
        (["CM1", "CM2", "CM3"], 0.62),
        (["LWB", "CB1", "CB2", "CB3", "RWB"], 0.81),
        (["GK"], 0.90),
    ],
    "5-4-1 Flat": [
        (["ST"], 0.40),
        (["LM", "CM1", "CM2", "RM"], 0.63),
        (["LWB", "CB1", "CB2", "CB3", "RWB"], 0.81),
        (["GK"], 0.90),
    ],
    "5-4-1 Defend": [
        (["ST"], 0.40),
        (["LM", "RM"], 0.59),
        (["CDM1", "CDM2"], 0.70),
        (["LWB", "CB1", "CB2", "CB3", "RWB"], 0.81),
        (["GK"], 0.90),
    ],
}


def normalize_formation_name(name: str) -> str:
    """Maps shorthand aliases like '4-3-3' or '442' to canonical formation names."""
    s = str(name).strip()
    if s in ("4-3-3", "433", "4-3-3 Flat"):
        return "4-3-3 Flat"
    if s in ("4-3-3 Attack", "433 Attack"):
        return "4-3-3 Attack"
    if s in ("4-4-2", "442"):
        return "4-4-2 Flat"
    if s in ("3-4-3", "343"):
        return "3-4-3 Flat"
    if s in ("4-5-1", "451"):
        return "4-5-1 Flat"
    if s in ("5-4-1", "541"):
        return "5-4-1 Flat"
    return s


# Playable turf plane on the stadium art (fractions of canvas height).
# Far end starts well below the skybox ads; near end sits above the bottom UI.
PITCH_Y_TOP = 0.38
PITCH_Y_BOTTOM = 0.90



def project_3d_point(tactical_x: float, tactical_y: float) -> tuple[int, int, int]:
    """
    Project normalized tactical coordinates (0.0 - 1.0) onto 3D pitch perspective.
    Returns (screen_x, screen_y, card_size).
    """
    Y_TOP = 0.28 * H
    Y_BOTTOM = 0.82 * H
    y_factor = max(0.0, min(1.0, tactical_y)) ** 0.88
    screen_y = int(Y_TOP + (Y_BOTTOM - Y_TOP) * y_factor)
    left_x = (0.32 - (0.32 - 0.06) * (tactical_y ** 0.90)) * W
    right_x = (0.68 + (0.94 - 0.68) * (tactical_y ** 0.90)) * W
    screen_x = int(left_x + max(0.0, min(1.0, tactical_x)) * (right_x - left_x))
    card_size = int(96 + 46 * (tactical_y ** 0.85))
    return screen_x, screen_y, card_size

def get_tactical_coordinates(formation_name: str, slots: list) -> dict:
    """Return tactical X, Y (0.0-1.0) for each slot with dynamic DB / Portal sync."""
    layouts = _load_portal_config().get("layouts", {})
    norm = normalize_formation_name(formation_name)
    saved = layouts.get(formation_name) or layouts.get(norm)
    
    if not saved:
        for k, v in layouts.items():
            if normalize_formation_name(k) == norm:
                saved = v
                break

    if saved:
        tactical = {}
        if isinstance(saved, list):
            for item in saved:
                if isinstance(item, dict) and "id" in item:
                    sid = str(item["id"]).upper()
                    raw_x = float(item.get("x", 50))
                    raw_y = float(item.get("y", 50))
                    nx = raw_x / 100.0 if raw_x > 1.0 else raw_x
                    ny = raw_y / 100.0 if raw_y > 1.0 else raw_y
                    for slot in slots:
                        if str(slot).upper() == sid:
                            tactical[slot] = (nx, ny)
        elif isinstance(saved, dict):
            saved_upper = {str(k).upper(): v for k, v in saved.items()}
            for slot in slots:
                slot_key = str(slot).upper()
                if slot_key in saved_upper:
                    val = saved_upper[slot_key]
                    if isinstance(val, (list, tuple)) and len(val) >= 2:
                        raw_x, raw_y = float(val[0]), float(val[1])
                    elif isinstance(val, dict) and "x" in val and "y" in val:
                        raw_x, raw_y = float(val["x"]), float(val["y"])
                    else:
                        continue
                    nx = raw_x / 100.0 if raw_x > 1.0 else raw_x
                    ny = raw_y / 100.0 if raw_y > 1.0 else raw_y
                    tactical[slot] = (nx, ny)
        if len(tactical) >= 5:
            return tactical

    # Fallback to FORMATION_TACTICAL_COORDS
    if norm in FORMATION_TACTICAL_COORDS:
        coords = {}
        for s in slots:
            if s in FORMATION_TACTICAL_COORDS[norm]:
                coords[s] = tuple(FORMATION_TACTICAL_COORDS[norm][s])
        if len(coords) >= 5:
            return coords

    coords = {}
    lines = FORMATION_LINES_FALLBACK.get(norm)
    if lines:
        for slot_list, y_val in lines:
            n = len(slot_list)
            spreads = {
                1: [0.50],
                2: [0.35, 0.65],
                3: [0.20, 0.50, 0.80],
                4: [0.08, 0.35, 0.65, 0.92],
                5: [0.06, 0.24, 0.50, 0.76, 0.94],
            }
            fracs = spreads.get(n, [0.5] if n == 1 else [i / (n - 1) for i in range(n)])
            tactical_y = max(0.08, min(0.95, (y_val - 0.35) / (0.90 - 0.35) * 0.85 + 0.10)) if y_val > 0.30 else y_val
            for slot, frac in zip(slot_list, fracs):
                coords[slot] = (frac, tactical_y)
        return coords

    n = len(slots)
    for i, s in enumerate(slots):
        coords[s] = (0.5 if n == 1 else i / (n - 1), 0.5)
    return coords

def get_formation_coordinates(formation_name: str, slots: list) -> dict:
    tactical = get_tactical_coordinates(formation_name, slots)
    coords = {}
    for slot in slots:
        tx, ty = tactical.get(slot, (0.5, 0.5))
        sx, sy, _ = project_3d_point(tx, ty)
        coords[slot] = (sx, sy)
    return coords

def get_card_size_for_y(y_pos: int) -> int:
    y_ratio = y_pos / H
    progress = max(0.0, min(1.0, (y_ratio - 0.315) / (0.88 - 0.315)))
    return int(122 + 68 * (progress ** 0.85))

def draw_3d_pedestal(pitch: Image.Image, cx: int, cy: int, width: int, height: int, glow_color: tuple):
    """Draws an elliptical neon hologram pedestal on the stadium pitch turf."""
    r, g, b = glow_color
    overlay = Image.new("RGBA", (width + 40, height + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    ox, oy = 20, 20
    d.ellipse([ox, oy, ox + width, oy + height], fill=(r, g, b, 45), outline=(r, g, b, 180), width=2)
    d.ellipse([ox + 6, oy + 3, ox + width - 6, oy + height - 3], outline=(255, 255, 255, 120), width=1)
    
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.5))
    pitch.paste(overlay, (cx - (width + 40) // 2, cy - (height + 40) // 2), overlay)

def render_3d_card(card_image: Image.Image, target_width: int, glow_color: tuple) -> Image.Image:
    """Scales the card image and adds a sleek drop-shadow / 3D glow."""
    if not card_image:
        return None
    aspect = card_image.height / max(1, card_image.width)
    target_height = int(target_width * aspect)
    card_resized = card_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    pad = 16
    cw, ch = target_width + pad * 2, target_height + pad * 2
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([pad + 4, pad + 10, pad + target_width - 4, pad + target_height + 4], fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5))
    canvas.alpha_composite(shadow)
    
    canvas.alpha_composite(card_resized, (pad, pad))
    return canvas

def _render_fallback_card(name: str, ovr: str, pos: str, target_width: int, glow_color: tuple, font_name, font_pos) -> Image.Image:
    """Renders a fallback placeholder card when full renderz card is missing."""
    aspect = 1.45
    target_height = int(target_width * aspect)
    card = Image.new("RGBA", (target_width, target_height), (20, 25, 40, 235))
    d = ImageDraw.Draw(card)
    
    r, g, b = glow_color
    d.rectangle([0, 0, target_width - 1, target_height - 1], outline=(r, g, b, 200), width=2)
    
    d.text((target_width // 2, 25), str(ovr), fill=(255, 215, 0), font=font_pos, anchor="mm")
    d.text((target_width // 2, 50), str(pos), fill=(200, 220, 255), font=font_pos, anchor="mm")
    d.text((target_width // 2, target_height - 25), str(name)[:10], fill=(255, 255, 255), font=font_name, anchor="mm")
    
    return render_3d_card(card, target_width, glow_color)

@lru_cache(maxsize=32)
def load_font(size: int):
    paths = [
        "assets/fonts/CruyffSansCondensed-Bold.ttf",
        "assets/fonts/Roboto-Bold.ttf",
        "assets/fonts/arial.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _render_single_slot_card(pos, player_info, raw_data, c_size, glow_color, font_name, font_pos):
    import time; time.sleep(0.01)
    """Renders a single player's 3D card (executed in parallel worker threads)."""
    name = str(player_info.get("name", pos))[:12]
    ovr = str(player_info.get("ovr", ""))
    
    if not raw_data:
        raw_data = player_info.get("raw_data") or player_info.get("player_data") or player_info.get("player")
        if not raw_data and isinstance(player_info, dict) and ("images" in player_info or "rating" in player_info):
            raw_data = player_info

    card_3d = None
    if raw_data:
        player_json = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        try:
            card_raw = generate_card(player_json, scale=1, animated=False)
            if card_raw:
                card_3d = render_3d_card(card_raw, c_size, glow_color)
        except Exception as e:
            print(f"Error rendering card face for {name} ({pos}): {e}")

    if card_3d is None:
        card_3d = _render_fallback_card(name, ovr, pos, c_size, glow_color, font_name, font_pos)

    stats_str = ""
    if isinstance(raw_data, dict) and "_lifetime_matches" in raw_data:
        m = raw_data.get("_lifetime_matches", 0)
        if m > 0:
            g = raw_data.get("_lifetime_goals", 0)
            a = raw_data.get("_lifetime_assists", 0)
            stats_str = f"{g}G {a}A"

    return pos, card_3d, name, ovr, stats_str

def generate_lineup_image(squad_data: dict, inventory_dict: dict):
    """
    Renders the complete 11-player squad lineup onto the selected 3D stadium pitch.
    All cards are un-squashed, strictly on the pitch turf, and naturally spaced with true 3D depth.
    High-performance parallelized card generation with image caching.
    """
    theme_id = squad_data.get("theme", "default")
    bg_file = _load_portal_config().get("themes", {}).get(
        theme_id, THEMES.get(theme_id, "assets/pitch_bg.jpg")
    )
    glow_color = THEME_GLOW.get(theme_id, (0, 240, 255))

    # 1. Load Background Pitch (Cached)
    if bg_file in _PITCH_CACHE:
        pitch = _PITCH_CACHE[bg_file].copy()
    else:
        try:
            base_pitch = Image.open(bg_file).convert("RGBA")
        except Exception:
            base_pitch = Image.new("RGBA", (W, H), (15, 20, 35, 255))
        pitch = base_pitch.resize((W, H), Image.Resampling.LANCZOS)
        if len(_PITCH_CACHE) < 10:
            _PITCH_CACHE[bg_file] = pitch.copy()

    formation_name = squad_data.get("formation", "4-3-3 Attack")
    players = squad_data.get("players", {})
    slots = list(players.keys())

    tactical_coords = get_tactical_coordinates(formation_name, slots)
    projected = {}
    for pos in slots:
        tx, ty = tactical_coords.get(pos, (0.5, 0.5))
        sx, sy, c_size = project_3d_point(tx, ty)
        projected[pos] = (sx, sy, c_size)

    font_name = load_font(16)
    font_pos = load_font(18)
    draw = ImageDraw.Draw(pitch)

    # PASS 1: Draw ALL 3D Hologram Pedestals first (background layer)
    for pos in slots:
        cx, cy, c_size = projected[pos]
        player_info = players.get(pos)
        if player_info and (player_info.get("inv_id") is not None or player_info.get("name")):
            draw_3d_pedestal(pitch, cx, cy + c_size // 2 - 4, int(c_size * 0.95), 24, glow_color)
        else:
            draw_3d_pedestal(pitch, cx, cy + 18, int(c_size * 0.8), 24, glow_color)

    # PARALLEL CARD GENERATION: Render all 11 cards concurrently
    rendered_cards = {}
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
        for pos in slots:
            player_info = players.get(pos)
            if player_info and (player_info.get("inv_id") is not None or player_info.get("name")):
                inv_id = player_info.get("inv_id")
                raw_data = None
                if inv_id is not None:
                    raw_data = inventory_dict.get(inv_id)
                    if raw_data is None:
                        try: raw_data = inventory_dict.get(int(inv_id))
                        except Exception: pass
                    if raw_data is None:
                        try: raw_data = inventory_dict.get(str(inv_id))
                        except Exception: pass
                
                cx, cy, c_size = projected[pos]
                tasks.append(
                    executor.submit(_render_single_slot_card, pos, player_info, raw_data, c_size, glow_color, font_name, font_pos)
                )

        for future in concurrent.futures.as_completed(tasks):
            try:
                res = future.result()
                if len(res) == 5:
                    pos, card_3d, name, ovr, stats_str = res
                else:
                    pos, card_3d, name, ovr = res
                    stats_str = ""
                rendered_cards[pos] = (card_3d, name, ovr, stats_str)
            except Exception as e:
                print(f"Parallel card render failed: {e}")

    # PASS 2: Draw Cards / Empty Slots sorted by Y (far-to-near for true 3D occlusion)
    for pos in sorted(slots, key=lambda p: projected[p][1]):
        cx, cy, c_size = projected[pos]
        
        if pos in rendered_cards:
            val = rendered_cards[pos]
            if len(val) == 4:
                card_3d, name, ovr, stats_str = val
            else:
                card_3d, name, ovr = val
                stats_str = ""

            px = cx - card_3d.width // 2
            py = cy - card_3d.height // 2 - 6
            pitch.paste(card_3d, (px, py), card_3d)

            # Render 3D Name & OVR Pill Badge
            badge_text = f"{name} {ovr}".strip()
            bbox = draw.textbbox((0, 0), badge_text, font=font_name)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            bx = cx - tw // 2 - 7
            by = py + card_3d.height - 14

            r, g, b = glow_color
            draw.rounded_rectangle([bx, by, bx + tw + 14, by + th + 6], radius=5, fill=(10, 15, 25, 230), outline=(r, g, b, 220), width=1)
            draw.text((bx + 7, by + 2), badge_text, fill=(255, 255, 255, 255), font=font_name)
        else:
            _draw_empty_placeholder(draw, pitch, cx, cy, pos, c_size, glow_color, font_pos)

    return pitch.convert("RGBA")

def _draw_empty_placeholder(draw, pitch: Image.Image, cx: int, cy: int, pos: str, c_size: int, glow_color: tuple, font):
    """Draws a 3D empty position slot on the pitch turf."""
    r, g, b = glow_color
    cr = 30
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(12, 16, 26, 220), outline=(r, g, b, 240), width=2)
    draw.text((cx, cy - 10), pos, font=font, fill=(255, 255, 255, 255), anchor="mm")
