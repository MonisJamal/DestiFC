nation_map = {
    14: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", 18: "🇫🇷 France", 27: "🇮🇹 Italy", 54: "🇧🇷 Brazil", 
    34: "🇳🇱 Netherlands", 45: "🇪🇸 Spain", 35: "🍀 Northern Ireland", 50: "🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales", 
    108: "🇨🇮 Ivory Coast", 7: "🇧🇪 Belgium", 21: "🇩🇪 Germany", 38: "🇵🇹 Portugal", 
    52: "🇦🇷 Argentina", 60: "🇺🇾 Uruguay", 83: "🇲🇽 Mexico", 163: "🇯🇵 Japan", 
    95: "🇺🇸 USA", 10: "🇭🇷 Croatia", 36: "🇳🇴 Norway", 46: "🇸🇪 Sweden", 56: "🇨🇴 Colombia",
    106: "🇸🇳 Senegal", 111: "🇪🇬 Egypt", 13: "🇩🇰 Denmark", 104: "🇲🇦 Morocco",
    9: "🇧🇬 Bulgaria", 42: "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", 49: "🇺🇦 Ukraine", 133: "🇳🇬 Nigeria",
    39: "🇷🇴 Romania", 59: "🇵🇪 Peru", 70: "🇨🇦 Canada", 103: "🇨🇲 Cameroon",
    117: "🇬🇭 Ghana", 129: "🇲🇦 Morocco", 167: "🇰🇷 South Korea", 191: "🇺🇿 Uzbekistan",
    12: "🇨🇿 Czech Republic", 47: "🇨🇭 Switzerland", 20: "🇬🇪 Georgia", 48: "🇹🇷 Turkey",
    37: "🇵🇱 Poland", 4: "🇦🇹 Austria", 51: "🇷🇸 Serbia", 23: "🇭🇺 Hungary",
    25: "🇮🇪 Ireland", 97: "🇩🇿 Algeria", 183: "🇸🇦 Saudi Arabia", 195: "🇦🇺 Australia",
    55: "🇨🇱 Chile", 58: "🇵🇾 Paraguay", 57: "🇪🇨 Ecuador", 61: "🇻🇪 Venezuela",
    17: "🇫🇮 Finland", 22: "🇬🇷 Greece", 43: "🇸🇰 Slovakia", 44: "🇸🇮 Slovenia",
    161: "🇮🇷 Iran", 110: "🇨🇲 Cameroon", 112: "🇬🇶 Equatorial Guinea", 113: "🇬🇦 Gabon",
    115: "🇬🇲 Gambia", 116: "🇬🇳 Guinea", 120: "🇰🇪 Kenya", 123: "🇱🇷 Liberia",
    125: "🇲🇬 Madagascar", 126: "🇲🇼 Malawi", 127: "🇲🇱 Mali", 130: "🇲🇿 Mozambique",
    132: "🇳🇪 Niger", 136: "🇷🇼 Rwanda", 138: "🇸🇱 Sierra Leone", 140: "🇿🇦 South Africa",
    142: "🇸🇩 Sudan", 144: "🇹🇿 Tanzania", 145: "🇹🇬 Togo", 146: "🇹🇳 Tunisia",
    147: "🇺🇬 Uganda", 148: "🇿🇲 Zambia", 149: "🇿🇼 Zimbabwe"
}

COUNTRY_FLAGS = {
    "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "france": "🇫🇷", "italy": "🇮🇹", "brazil": "🇧🇷",
    "netherlands": "🇳🇱", "holland": "🇳🇱", "spain": "🇪🇸", "northern ireland": "🍀",
    "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "ivory coast": "🇨🇮", "côte d'ivoire": "🇨🇮", "belgium": "🇧🇪",
    "germany": "🇩🇪", "portugal": "🇵🇹", "argentina": "🇦🇷", "uruguay": "🇺🇾",
    "mexico": "🇲🇽", "japan": "🇯🇵", "united states": "🇺🇸", "usa": "🇺🇸",
    "croatia": "🇭🇷", "norway": "🇳🇴", "sweden": "🇸🇪", "colombia": "🇨🇴",
    "senegal": "🇸🇳", "egypt": "🇪🇬", "morocco": "🇲🇦", "bulgaria": "🇧🇬",
    "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "ukraine": "🇺🇦", "nigeria": "🇳🇬", "romania": "🇷🇴",
    "peru": "🇵🇪", "canada": "🇨🇦", "cameroon": "🇨🇲", "ghana": "🇬🇭",
    "korea republic": "🇰🇷", "korea": "🇰🇷", "south korea": "🇰🇷", "uzbekistan": "🇺🇿",
    "czech republic": "🇨🇿", "czechia": "🇨🇿", "switzerland": "🇨🇭", "georgia": "🇬🇪",
    "turkey": "🇹🇷", "türkiye": "🇹🇷", "poland": "🇵🇱", "austria": "🇦🇹",
    "serbia": "🇷🇸", "hungary": "🇭🇺", "ireland": "🇮🇪", "republic of ireland": "🇮🇪",
    "algeria": "🇩🇿", "saudi arabia": "🇸🇦", "australia": "🇦🇺", "chile": "🇨🇱",
    "paraguay": "🇵🇾", "ecuador": "🇪🇨", "venezuela": "🇻🇪", "finland": "🇫🇮",
    "greece": "🇬🇷", "slovakia": "🇸🇰", "slovenia": "🇸🇮", "iran": "🇮🇷",
    "mali": "🇲🇱", "guinea": "🇬🇳", "gabon": "🇬🇦", "togo": "🇹🇬", "tunisia": "🇹🇳",
    "south africa": "🇿🇦", "zambia": "🇿🇲", "denmark": "🇩🇰"
}

club_map = {
    114154: "🛡️ Icons", 115935: "🛡️ Heroes", 241: "🛡️ FC Barcelona", 243: "🛡️ Real Madrid",
    21: "🛡️ Bayern Munich", 11: "🛡️ Manchester United", 9: "🛡️ Liverpool", 10: "🛡️ Manchester City",
    5: "🛡️ Chelsea", 1: "🛡️ Arsenal", 73: "🛡️ Paris SG", 45: "🛡️ Juventus", 44: "🛡️ Inter", 
    47: "🛡️ AC Milan", 236: "🛡️ Sporting CP", 112139: "🛡️ Al Nassr", 112533: "🛡️ Inter Miami", 
    896: "🛡️ FC Basel", 175: "🛡️ Bayer Leverkusen", 112658: "🛡️ Al Hilal",
    325: "🛡️ Galatasaray", 1335: "🛡️ France (INT)", 1362: "🛡️ Spain (INT)",
    1318: "🛡️ England (INT)", 1325: "🛡️ Belgium (INT)", 1352: "🛡️ Norway (INT)", 
    1354: "🛡️ Portugal (INT)", 1364: "🛡️ Switzerland (INT)", 1369: "🛡️ Argentina (INT)",
    22: "🛡️ Borussia Dortmund", 327: "🛡️ VfB Stuttgart", 112606: "🛡️ Atletico Madrid",
    114640: "🛡️ Charlotte FC", 111111: "🛡️ PSV", 18: "🛡️ RB Leipzig", 689: "🛡️ NY Red Bulls",
    101014: "🛡️ CSKA Moscow", 111130: "🛡️ Liverpool", 1370: "🛡️ Brazil (INT)", 1328: "🛡️ Croatia (INT)",
    240: "🛡️ Atletico Madrid", 48: "🛡️ Napoli", 52: "🛡️ Roma", 1877: "🛡️ Aston Villa",
    18: "🛡️ Tottenham", 19: "🛡️ Newcastle", 110: "🛡️ Ajax", 234: "🛡️ FC Porto",
    237: "🛡️ Benfica", 112657: "🛡️ Al Ittihad", 112659: "🛡️ Al Ahli"
}

def get_nation_display(player_data: dict) -> str:
    if not isinstance(player_data, dict):
        return "🌍 World"

    # 1. Direct nation dict or object
    nation = player_data.get('nation') or player_data.get('country')
    n_id = None
    n_name = None

    if isinstance(nation, dict):
        n_id = nation.get('id')
        n_name = nation.get('name')
    elif isinstance(nation, int):
        n_id = nation
    elif isinstance(nation, str):
        if nation.isdigit():
            n_id = int(nation)
        else:
            n_name = nation

    # Secondary field fallbacks
    if not n_name:
        n_name = player_data.get('nation_name') or player_data.get('nationName') or player_data.get('country_name')
    if not n_id and player_data.get('nation_id'):
        try:
            n_id = int(player_data.get('nation_id'))
        except (ValueError, TypeError):
            pass

    if n_id and n_id in nation_map:
        return nation_map[n_id]

    if n_name:
        clean_name = str(n_name).strip()
        flag = COUNTRY_FLAGS.get(clean_name.lower())
        if flag:
            return f"{flag} {clean_name}"
        return f"🌍 {clean_name}"

    return "🌍 World"

def get_club_display(player_data: dict) -> str:
    if not isinstance(player_data, dict):
        return "🛡️ Club"

    source = str(player_data.get('source', '')).upper()
    if 'ICON' in source:
        return "🛡️ Icons"
    if 'HERO' in source:
        return "🛡️ Heroes"

    club = player_data.get('club') or player_data.get('team')
    c_id = None
    c_name = None

    if isinstance(club, dict):
        c_id = club.get('id')
        c_name = club.get('name')
    elif isinstance(club, int):
        c_id = club
    elif isinstance(club, str):
        if club.isdigit():
            c_id = int(club)
        else:
            c_name = club

    # Secondary field fallbacks
    if not c_name:
        c_name = player_data.get('club_name') or player_data.get('clubName') or player_data.get('team_name')
    if not c_id and player_data.get('club_id'):
        try:
            c_id = int(player_data.get('club_id'))
        except (ValueError, TypeError):
            pass

    if c_id and c_id in club_map:
        return club_map[c_id]

    if c_name:
        clean_name = str(c_name).strip()
        if clean_name.lower() in ("icons", "icon"):
            return "🛡️ Icons"
        if clean_name.lower() in ("heroes", "hero"):
            return "🛡️ Heroes"
        if clean_name.startswith("🛡️"):
            return clean_name
        return f"🛡️ {clean_name}"

    return "🛡️ Club"


import json

FAMOUS_PLAYER_POSITIONS = {
    # Defenders (CB / LB / RB / LWB / RWB)
    "maldini": "CB", "carvalho": "CB", "ricardo carvalho": "CB", "van dijk": "CB", "cannavaro": "CB", 
    "nesta": "CB", "puyol": "CB", "vidic": "CB", "vidić": "CB", "kompany": "CB", "ferdinand": "CB", 
    "blanc": "CB", "lucio": "CB", "lúcio": "CB", "baresi": "CB", "desailly": "CB", "koeman": "CB", 
    "hierro": "CB", "moore": "CB", "campbell": "CB", "cordoba": "CB", "córdoba": "CB", "kohler": "CB", 
    "marquez": "CB", "márquez": "CB", "saliba": "CB", "rudiger": "CB", "rüdiger": "CB", "dias": "CB", 
    "militao": "CB", "militão": "CB", "araujo": "CB", "bastoni": "CB", "bremer": "CB",
    "roberto carlos": "LB", "carlos": "LB", "zanetti": "RB", "cafu": "RB", "cafú": "RB", 
    "alberto": "RB", "carlos alberto": "RB", "lahm": "RB", "cole": "LB", "ashley cole": "LB", 
    "thuram": "RB", "walker": "RB", "frimpong": "RWB", "theo": "LB", "davies": "LB", "dimarco": "LWB", 
    "cancelo": "LB", "carvajal": "RB", "trent": "RB", "alexander-arnold": "RB", "hakimi": "RB",
    "lizarazu": "LB", "zambrotta": "RB", "riise": "LB", "capdevila": "LB",

    # Strikers / Forwards (ST / CF / LW / RW)
    "cantona": "ST", "mbappé": "ST", "mbappe": "ST", "haaland": "ST", "ronaldo": "ST", 
    "r9": "ST", "cr7": "ST", "cruyff": "CF", "cruijff": "CF", "bergkamp": "CF", "kanu": "ST", 
    "cha bum kun": "RW", "cha": "RW", "eusebio": "ST", "eusébio": "ST", "muller": "ST", 
    "müller": "ST", "shevchenko": "ST", "drogba": "ST", "henry": "ST", "van basten": "ST", 
    "raul": "CF", "raúl": "CF", "torres": "ST", "rooney": "ST", "etoo": "ST", "eto'o": "ST", 
    "butragueno": "ST", "butragueño": "ST", "del piero": "CF", "trezeguet": "ST", "crespo": "ST", 
    "larsson": "ST", "kluivert": "ST", "owen": "ST", "rush": "ST", "lineker": "ST", "suker": "ST", 
    "šuker": "ST", "morientes": "ST", "forlan": "ST", "forlán": "ST", "papin": "ST", "voller": "ST", 
    "völler": "ST", "di natale": "ST", "morata": "ST", "kane": "ST", "lewandowski": "ST", 
    "osimhen": "ST", "martinez": "ST", "martínez": "ST", "lautaro": "ST", "gyokeres": "ST", 
    "gyökeres": "ST", "ismael": "ST", "vlahovic": "ST", "vlahović": "ST", "alvarez": "ST", 
    "álvarez": "ST", "son": "LW", "garrincha": "RW", "jairzinho": "RW", "best": "RW", 
    "figo": "RW", "stoichkov": "LW", "pash": "ST", "nedved": "LM", "nedvěd": "LM", "ginola": "LM", 
    "hazard": "LW", "ribéry": "LM", "ribery": "LM", "robben": "RM", "bale": "RW", "messi": "RW", 
    "neymar": "LW", "vinicius": "LW", "vinícius": "LW", "salah": "RW", "rodrygo": "RW", 
    "saka": "RW", "foden": "LW", "kvaratskhelia": "LW", "leao": "LW", "leão": "LW", 
    "dembele": "RW", "dembélé": "RW", "yamal": "RW", "lamine": "RW", "williams": "LW", 
    "nico williams": "LW", "raphinha": "RW", "rashford": "LW", "gomez": "ST", "al-jaber": "ST", 
    "al jaber": "ST", "al-owairan": "RW", "al owairan": "RW",

    # Midfielders (CAM / CM / CDM / LM / RM)
    "pelé": "CAM", "pele": "CAM", "maradona": "CAM", "riquelme": "CAM", "donovan": "CAM", 
    "bellingham": "CAM", "zidane": "CAM", "ronaldinho": "LW", "kaka": "CAM", "kaká": "CAM", 
    "socrates": "CAM", "sócrates": "CAM", "zico": "CAM", "baggio": "CAM", "hagi": "CAM", 
    "mostovoi": "CAM", "okocha": "CAM", "nakata": "CAM", "rosicky": "CAM", "rosický": "CAM", 
    "sneijder": "CAM", "litmanen": "CAM", "rui costa": "CAM", "musiala": "CAM", "wirtz": "CAM", 
    "odegaard": "CAM", "ødegaard": "CAM", "palmer": "CAM", "bruno": "CAM", "fernandes": "CAM", 
    "gullit": "CM", "vieira": "CDM", "matthaus": "CM", "mätthaus": "CM", "yaya toure": "CM", 
    "toure": "CM", "touré": "CM", "scholes": "CM", "xavi": "CM", "iniesta": "CM", "modric": "CM", 
    "modrić": "CM", "de bruyne": "CM", "pirlo": "CM", "ballack": "CM", "gerrard": "CM", 
    "lampard": "CM", "seedorf": "CM", "veron": "CM", "verón": "CM", "keane": "CDM", 
    "rijkaard": "CDM", "makelele": "CDM", "makélélé": "CDM", "gattuso": "CDM", "essien": "CDM", 
    "xabi alonso": "CDM", "alonso": "CDM", "mascherano": "CDM", "marchisio": "CM", 
    "kivior": "CB", "kimmich": "CDM", "rodri": "CDM", "rice": "CDM", "valverde": "CM", 
    "camavinga": "CM", "tchouameni": "CDM", "tchouaméni": "CDM", "pedri": "CM", "gavi": "CM", 
    "vitinha": "CM", "barella": "CM", "tonali": "CDM", "maddison": "CAM", "park ji sung": "LM", 
    "park": "LM", "kuyt": "RM", "ljungberg": "RM", "govou": "RM", "smolarek": "ST", 
    "giuly": "RM", "mcmanaman": "RM", "futre": "LW", "abedi pele": "CAM",

    # Goalkeepers (GK)
    "casillas": "GK", "yashin": "GK", "van der sar": "GK", "schmeichel": "GK", "cech": "GK", 
    "čech": "GK", "courtois": "GK", "alisson": "GK", "ederson": "GK", "neuer": "GK", 
    "buffon": "GK", "donnarumma": "GK", "marmardashvili": "GK", "mamar": "GK", "oblak": "GK", 
    "ter stegen": "GK", "raya": "GK", "martinez gk": "GK", "dibu": "GK", "dudek": "GK", 
    "campos": "GK", "seaman": "GK", "baia": "GK", "baía": "GK", "kobel": "GK", "sommer": "GK", 
    "vicario": "GK", "unai simon": "GK", "simon": "GK"
}

_POS_CACHE = {}

def extract_pos(item) -> str:
    if not item:
        return "ST"
    
    # Safely convert sqlite3.Row / aiosqlite.Row or other Mapping to standard dict if possible
    if not isinstance(item, dict):
        try:
            item = dict(item)
        except Exception:
            pass

    # Helper getter for dict or object/row
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        try:
            return obj[key]
        except Exception:
            return getattr(obj, key, default)

    # 1. Direct key on row/dict
    for k in ('position', 'pos', 'cardPosition', 'primaryPosition'):
        v = _get(item, k)
        if isinstance(v, str) and v.strip() and not v.isdigit() and len(v.strip()) <= 4 and v.strip().upper() != '??':
            return v.strip().upper()

    # 2. Extract from player_data
    pd_raw = _get(item, 'player_data')
    if pd_raw:
        pd = pd_raw
        while isinstance(pd, str) and pd.strip():
            try:
                pd = json.loads(pd)
            except Exception:
                break
        
        if not isinstance(pd, dict):
            try:
                pd = dict(pd)
            except Exception:
                pass

        if isinstance(pd, dict):
            for k in ('position', 'cardPosition', 'primaryPosition', 'pos'):
                v = pd.get(k)
                if isinstance(v, str) and v.strip() and not v.isdigit() and len(v.strip()) <= 4 and v.strip().upper() != '??':
                    return v.strip().upper()

    # 3. Memory cache
    p_name = _get(item, 'player_name') or _get(item, 'name') or _get(item, 'cardName') or _get(item, 'lastName') or ''
    p_ovr = _get(item, 'ovr') or _get(item, 'rating') or 0
    clean_name = str(p_name).strip().lower()
    cache_key = f"{clean_name}_{p_ovr}"
    if cache_key in _POS_CACHE:
        return _POS_CACHE[cache_key]

    # 4. Known player positions mapping lookup
    for k, pos_val in FAMOUS_PLAYER_POSITIONS.items():
        if k in clean_name:
            _POS_CACHE[cache_key] = pos_val
            return pos_val

    return "ST"

# ================= Alternate Position Compatibility =================
# Players standing in their natural OR alternate positions play at 100% full OVR without penalty
POSITION_ALTERNATES = {
    "ST": {"ST", "CF", "CAM", "LF", "RF"},
    "CF": {"CF", "ST", "CAM", "LF", "RF"},
    "LF": {"LF", "CF", "ST", "LW"},
    "RF": {"RF", "CF", "ST", "RW"},
    "LW": {"LW", "LM", "RW", "ST", "LF"},
    "RW": {"RW", "RM", "LW", "ST", "RF"},
    "CAM": {"CAM", "CM", "CF", "ST", "LM", "RM"},
    "CM": {"CM", "CDM", "CAM", "LM", "RM"},
    "CDM": {"CDM", "CM", "CB"},
    "LM": {"LM", "LW", "CM", "LWB", "RM"},
    "RM": {"RM", "RW", "CM", "RWB", "LM"},
    "CB": {"CB", "LB", "RB", "CDM"},
    "LB": {"LB", "LWB", "CB", "LM"},
    "RB": {"RB", "RWB", "CB", "RM"},
    "LWB": {"LWB", "LB", "LM", "CB"},
    "RWB": {"RWB", "RB", "RM", "CB"},
    "GK": {"GK"}
}

def is_position_compatible(player_natural_pos: str, slot_pos: str) -> bool:
    """
    Returns True if slot_pos is the player's primary position or a natural alternate position.
    """
    if not player_natural_pos or not slot_pos:
        return True
    clean_slot = ''.join([c for c in str(slot_pos) if not c.isdigit()]).strip().upper()
    clean_nat = ''.join([c for c in str(player_natural_pos) if not c.isdigit()]).strip().upper()
    if clean_nat == clean_slot:
        return True
    return clean_slot in POSITION_ALTERNATES.get(clean_nat, set())

# ================= Tactics & Formations Synergy =================
TACTICS = {
    "Tiki-Taka": {
        "name": "Tiki-Taka",
        "description": "Short passing, dominant midfield possession & patient build-up.",
        "best_formations": ["4-3-3 Holding", "4-1-4-1"],
        "emoji": "🪄",
        "boost_focus": "Midfield Control & Possession (+8%)"
    },
    "Gegenpressing": {
        "name": "Gegenpressing",
        "description": "Aggressive high-press to win turnovers instantly in the opponent third.",
        "best_formations": ["4-3-3 Attack", "4-2-3-1 Narrow", "4-2-3-1 Wide"],
        "emoji": "⚡",
        "boost_focus": "Turnovers, High-Press & Fast Shots (+10%)"
    },
    "Wing Play": {
        "name": "Wing Play",
        "description": "Exploit wide flanks with pacey wingers delivering dangerous crosses.",
        "best_formations": ["4-4-2 Flat", "4-3-3 Flat"],
        "emoji": "🏃",
        "boost_focus": "Crossing & Corner Aerial Threat (+10%)"
    },
    "Counter-Attack": {
        "name": "Counter-Attack",
        "description": "Absorb opponent pressure and hit lightning-fast clinical breakaways.",
        "best_formations": ["5-2-1-2", "4-4-2 Holding", "4-3-3 Defend"],
        "emoji": "🏹",
        "boost_focus": "Breakaway Goals & Defensive Resilience (+12%)"
    },
    "Kick and Rush": {
        "name": "Kick and Rush",
        "description": "Direct long balls into the penalty box for powerful physical strikers.",
        "best_formations": ["4-4-2 Flat", "5-4-1 Flat", "5-4-1 Defend"],
        "emoji": "🚀",
        "boost_focus": "Direct Long Balls & Box Power (+10%)"
    },
    "Park the Bus": {
        "name": "Park the Bus",
        "description": "Impenetrable defensive low block in the box frustrating attacks.",
        "best_formations": ["5-4-1 Flat", "5-4-1 Defend", "4-5-1 Flat", "4-5-1 Attack"],
        "emoji": "🚌",
        "boost_focus": "Defensive Blocks & Clean Sheet Rate (+15%)"
    },
    "Vertical Tiki-Taka": {
        "name": "Vertical Tiki-Taka",
        "description": "Quick vertical triangles slicing through central defensive channels.",
        "best_formations": ["4-3-2-1", "4-1-2-1-2 Narrow"],
        "emoji": "🔺",
        "boost_focus": "Central Through Balls & xG Efficiency (+12%)"
    }
}

