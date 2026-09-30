nation_map = {
    14: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", 18: "🇫🇷 France", 27: "🇮🇹 Italy", 54: "🇧🇷 Brazil", 
    34: "🇳🇱 Netherlands", 45: "🇪🇸 Spain", 35: "🍀 Northern Ireland", 50: "🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales", 
    108: "🇨🇮 Ivory Coast", 7: "🇧🇪 Belgium", 21: "🇩🇪 Germany", 38: "🇵🇹 Portugal", 
    52: "🇦🇷 Argentina", 60: "🇺🇾 Uruguay", 83: "🇲🇽 Mexico", 163: "🇯🇵 Japan", 
    95: "🇺🇸 USA", 10: "🇭🇷 Croatia", 36: "🇳🇴 Norway", 46: "🇸🇪 Sweden", 56: "🇨🇴 Colombia",
    106: "🇸🇳 Senegal", 111: "🇪🇬 Egypt", 13: "🇩🇰 Denmark", 104: "🇲🇦 Morocco",
    9: "🇧🇬 Bulgaria", 42: "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", 49: "🇺🇦 Ukraine", 133: "🇳🇬 Nigeria",
    39: "🇷🇴 Romania", 59: "🇵🇪 Peru", 70: "🇨🇦 Canada", 103: "🇨🇲 Cameroon",
    117: "🇬🇭 Ghana", 129: "🇲🇦 Morocco", 167: "🇰🇷 Korea Republic", 191: "🇺🇿 Uzbekistan",
    12: "🇨🇿 Czech Republic", 47: "🇨🇭 Switzerland", 20: "🇬🇪 Georgia", 48: "🇹🇷 Turkey"
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
    101014: "🛡️ CSKA Moscow", 111130: "🛡️ Liverpool", 1370: "🛡️ Brazil (INT)", 1328: "🛡️ Croatia (INT)"
}

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

