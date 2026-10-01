nation_map = {
    1: "🇦🇱 Albania", 2: "🇦🇩 Andorra", 3: "🇦🇲 Armenia", 4: "🇦🇹 Austria", 5: "🇦🇿 Azerbaijan",
    6: "🇧🇾 Belarus", 7: "🇧🇪 Belgium", 8: "🇧🇦 Bosnia & Herzegovina", 9: "🇧🇬 Bulgaria", 10: "🇭🇷 Croatia",
    11: "🇨🇾 Cyprus", 12: "🇨🇿 Czech Republic", 13: "🇩🇰 Denmark", 14: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", 15: "🇪🇪 Estonia",
    16: "🇫🇴 Faroe Islands", 17: "🇫🇮 Finland", 18: "🇫🇷 France", 19: "🇲🇰 North Macedonia", 20: "🇬🇪 Georgia",
    21: "🇩🇪 Germany", 22: "🇬🇷 Greece", 23: "🇭🇺 Hungary", 24: "🇮🇸 Iceland", 25: "🇮🇪 Republic of Ireland",
    26: "🇮🇱 Israel", 27: "🇮🇹 Italy", 28: "🇱🇻 Latvia", 29: "🇱🇮 Liechtenstein", 30: "🇱🇹 Lithuania",
    31: "🇱🇺 Luxembourg", 32: "🇲🇹 Malta", 33: "🇲🇩 Moldova", 34: "🇳🇱 Netherlands", 35: "🍀 Northern Ireland",
    36: "🇳🇴 Norway", 37: "🇵🇱 Poland", 38: "🇵🇹 Portugal", 39: "🇷🇴 Romania", 40: "🇷🇺 Russia",
    41: "🇸🇲 San Marino", 42: "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", 43: "🇸🇰 Slovakia", 44: "🇸🇮 Slovenia", 45: "🇪🇸 Spain",
    46: "🇸🇪 Sweden", 47: "🇨🇭 Switzerland", 48: "🇹🇷 Turkey", 49: "🇺🇦 Ukraine", 50: "🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales",
    51: "🇷🇸 Serbia", 52: "🇦🇷 Argentina", 53: "🇧🇴 Bolivia", 54: "🇧🇷 Brazil", 55: "🇨🇱 Chile",
    56: "🇨🇴 Colombia", 57: "🇪🇨 Ecuador", 58: "🇵🇾 Paraguay", 59: "🇵🇪 Peru", 60: "🇺🇾 Uruguay",
    61: "🇻🇪 Venezuela", 62: "🇦🇮 Anguilla", 63: "🇦🇬 Antigua and Barbuda", 64: "🇦🇼 Aruba", 65: "🇧🇸 Bahamas",
    66: "🇧🇧 Barbados", 67: "🇧🇿 Belize", 68: "🇧🇲 Bermuda", 69: "🇻🇬 British Virgin Islands", 70: "🇨🇦 Canada",
    71: "🇰🇾 Cayman Islands", 72: "🇨🇷 Costa Rica", 73: "🇨🇺 Cuba", 74: "🇩🇲 Dominica", 75: "🇩🇴 Dominican Republic",
    76: "🇸🇻 El Salvador", 77: "🇬🇩 Grenada", 78: "🇬🇹 Guatemala", 79: "🇬🇾 Guyana", 80: "🇭🇹 Haiti",
    81: "🇭🇳 Honduras", 82: "🇯🇲 Jamaica", 83: "🇲🇽 Mexico", 84: "🇲🇸 Montserrat", 85: "🇳🇮 Nicaragua",
    86: "🇵🇦 Panama", 87: "🇵🇷 Puerto Rico", 88: "🇰🇳 Saint Kitts and Nevis", 89: "🇱🇨 Saint Lucia", 90: "🇻🇨 Saint Vincent",
    91: "🇸🇷 Suriname", 92: "🇹🇹 Trinidad and Tobago", 93: "🇹🇨 Turks and Caicos", 94: "🇻🇮 US Virgin Islands", 95: "🇺🇸 USA",
    96: "🇦🇫 Afghanistan", 97: "🇩🇿 Algeria", 98: "🇦🇴 Angola", 99: "🇧🇭 Bahrain", 100: "🇧🇩 Bangladesh",
    101: "🇧🇯 Benin", 102: "🇧🇼 Botswana", 103: "🇨🇲 Cameroon", 104: "🇲🇦 Morocco", 105: "🇨🇻 Cape Verde",
    106: "🇸🇳 Senegal", 107: "🇨🇫 Central African Rep.", 108: "🇨🇮 Ivory Coast", 109: "🇹🇩 Chad", 110: "🇰🇲 Comoros",
    111: "🇪🇬 Egypt", 112: "🇬🇶 Equatorial Guinea", 113: "🇬🇦 Gabon", 114: "🇬🇲 Gambia", 115: "🇬🇭 Ghana",
    116: "🇬🇳 Guinea", 117: "🇬🇼 Guinea-Bissau", 118: "🇰🇪 Kenya", 119: "🇱🇸 Lesotho", 120: "🇱🇷 Liberia",
    121: "🇱🇾 Libya", 122: "🇲🇬 Madagascar", 123: "🇲🇼 Malawi", 124: "🇲🇱 Mali", 125: "🇲🇷 Mauritania",
    126: "🇲🇺 Mauritius", 127: "🇲🇦 Morocco", 128: "🇲🇿 Mozambique", 129: "🇳🇦 Namibia", 130: "🇳🇪 Niger",
    131: "🇳🇬 Nigeria", 132: "🇷🇼 Rwanda", 133: "🇳🇬 Nigeria", 134: "🇸🇹 Sao Tome and Principe", 135: "🇸🇨 Seychelles",
    136: "🇸🇱 Sierra Leone", 137: "🇸🇴 Somalia", 138: "🇿🇦 South Africa", 139: "🇸🇸 South Sudan", 140: "🇿🇦 South Africa",
    141: "🇸🇩 Sudan", 142: "🇸🇿 Eswatini", 143: "🇹🇿 Tanzania", 144: "🇹🇬 Togo", 145: "🇹🇳 Tunisia",
    146: "🇹🇳 Tunisia", 147: "🇺🇬 Uganda", 148: "🇿🇲 Zambia", 149: "🇿🇼 Zimbabwe", 155: "🇨🇳 China PR",
    156: "🇹🇼 Chinese Taipei", 157: "🇬🇺 Guam", 158: "🇭🇰 Hong Kong", 159: "🇮🇳 India", 160: "🇮🇩 Indonesia",
    161: "🇮🇷 Iran", 162: "🇮🇶 Iraq", 163: "🇯🇵 Japan", 164: "🇯🇴 Jordan", 165: "🇰🇿 Kazakhstan",
    166: "🇰🇵 North Korea", 167: "🇰🇷 South Korea", 168: "🇰🇼 Kuwait", 169: "🇰🇬 Kyrgyzstan", 170: "🇱🇦 Laos",
    171: "🇱🇧 Lebanon", 172: "🇲🇴 Macau", 173: "🇲🇾 Malaysia", 174: "🇲🇻 Maldives", 175: "🇲🇳 Mongolia",
    176: "🇲🇲 Myanmar", 177: "🇳🇵 Nepal", 178: "🇴🇲 Oman", 179: "🇵🇰 Pakistan", 180: "🇵🇸 Palestine",
    181: "🇵🇭 Philippines", 182: "🇶🇦 Qatar", 183: "🇸🇦 Saudi Arabia", 184: "🇸🇬 Singapore", 185: "🇱🇰 Sri Lanka",
    186: "🇸🇾 Syria", 187: "🇹🇯 Tajikistan", 188: "🇹🇭 Thailand", 189: "🇹🇲 Turkmenistan", 190: "🇦🇪 UAE",
    191: "🇺🇿 Uzbekistan", 192: "🇻🇳 Vietnam", 193: "🇾🇪 Yemen", 194: "🇦🇸 American Samoa", 195: "🇦🇺 Australia",
    196: "🇨🇰 Cook Islands", 197: "🇫🇯 Fiji", 198: "🇳🇿 New Zealand", 199: "🇵🇬 Papua New Guinea", 200: "🇼🇸 Samoa",
    201: "🇸🇧 Solomon Islands", 202: "🇵🇫 Tahiti", 203: "🇹🇴 Tonga", 204: "🇻🇺 Vanuatu", 208: "🇲🇪 Montenegro",
    214: "🇽🇰 Kosovo", 219: "🇬🇮 Gibraltar"
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
    "south africa": "🇿🇦", "zambia": "🇿🇲", "denmark": "🇩🇰", "china": "🇨🇳",
    "china pr": "🇨🇳", "jordan": "🇯🇴", "uae": "🇦🇪", "qatar": "🇶🇦", "iraq": "🇮🇶",
    "costa rica": "🇨🇷", "jamaica": "🇯🇲", "panama": "🇵🇦", "albania": "🇦🇱",
    "bosnia & herzegovina": "🇧🇦", "bosnia": "🇧🇦", "iceland": "🇮🇸", "israel": "🇮🇱",
    "montenegro": "🇲🇪", "kosovo": "🇽🇰", "new zealand": "🇳🇿", "india": "🇮🇳"
}

club_map = {
    # Special Promo Classes
    114154: "🛡️ Icons", 115935: "🛡️ Heroes",
    
    # Premier League
    1: "🛡️ Arsenal", 2: "🛡️ Aston Villa", 3: "🛡️ Blackburn", 5: "🛡️ Chelsea", 
    7: "🛡️ Everton", 9: "🛡️ Liverpool", 10: "🛡️ Manchester City", 11: "🛡️ Manchester United", 
    13: "🛡️ Newcastle United", 14: "🛡️ Nottingham Forest", 17: "🛡️ Southampton", 18: "🛡️ Tottenham Hotspur", 
    19: "🛡️ West Ham United", 1795: "🛡️ Fulham", 1808: "🛡️ Brighton", 1877: "🛡️ Aston Villa", 
    1884: "🛡️ Crystal Palace", 1886: "🛡️ Wolverhampton", 1896: "🛡️ Brentford", 111130: "🛡️ Liverpool",

    # La Liga
    240: "🛡️ Atletico Madrid", 241: "🛡️ FC Barcelona", 243: "🛡️ Real Madrid",
    448: "🛡️ Real Betis", 449: "🛡️ Athletic Club", 457: "🛡️ Real Sociedad",
    461: "🛡️ Sevilla FC", 472: "🛡️ Valencia CF", 481: "🛡️ Villarreal CF",
    479: "🛡️ Girona FC", 112606: "🛡️ Atletico Madrid",

    # Bundesliga
    21: "🛡️ Bayern Munich", 22: "🛡️ Borussia Dortmund", 23: "🛡️ Borussia M'gladbach",
    31: "🛡️ Bayer Leverkusen", 32: "🛡️ Schalke 04", 34: "🛡️ VfB Stuttgart",
    36: "🛡️ VfL Wolfsburg", 38: "🛡️ Werder Bremen", 175: "🛡️ Bayer Leverkusen",
    112172: "🛡️ RB Leipzig", 327: "🛡️ VfB Stuttgart", 1824: "🛡️ Eintracht Frankfurt",

    # Serie A
    44: "🛡️ Inter", 45: "🛡️ Juventus", 47: "🛡️ AC Milan", 48: "🛡️ Napoli",
    52: "🛡️ AS Roma", 54: "🛡️ SS Lazio", 55: "🛡️ Fiorentina", 64: "🛡️ Atalanta",
    1842: "🛡️ Bologna", 1843: "🛡️ Torino",

    # Ligue 1
    73: "🛡️ Paris Saint-Germain", 74: "🛡️ Marseille", 76: "🛡️ Lyon",
    79: "🛡️ AS Monaco", 81: "🛡️ Lille OSC", 84: "🛡️ OGC Nice",

    # Saudi Pro League
    605: "🛡️ Al Hilal", 673: "🛡️ Al Hilal", 112658: "🛡️ Al Hilal",
    112139: "🛡️ Al Nassr", 112657: "🛡️ Al Ittihad", 112659: "🛡️ Al Ahli",
    112093: "🛡️ Al Shabab", 112660: "🛡️ Al Ettifaq",

    # MLS & Americas
    112533: "🛡️ Inter Miami", 689: "🛡️ NY Red Bulls", 693: "🛡️ LA Galaxy",
    112885: "🛡️ LAFC", 114640: "🛡️ Charlotte FC", 111111: "🛡️ PSV",
    1876: "🛡️ River Plate", 1877: "🛡️ Boca Juniors", 101014: "🛡️ CSKA Moscow",

    # Portugal, Netherlands, Turkey & Europe
    110: "🛡️ Ajax", 111: "🛡️ Feyenoord", 112: "🛡️ PSV Eindhoven",
    234: "🛡️ FC Porto", 236: "🛡️ Sporting CP", 237: "🛡️ SL Benfica",
    325: "🛡️ Galatasaray", 326: "🛡️ Fenerbahce", 327: "🛡️ Besiktas",
    896: "🛡️ FC Basel", 1013: "🛡️ Celtic", 1014: "🛡️ Rangers",

    # National Teams (International)
    1318: "🛡️ England (INT)", 1325: "🛡️ Belgium (INT)", 1328: "🛡️ Croatia (INT)",
    1335: "🛡️ France (INT)", 1352: "🛡️ Norway (INT)", 1354: "🛡️ Portugal (INT)", 
    1362: "🛡️ Spain (INT)", 1364: "🛡️ Switzerland (INT)", 1369: "🛡️ Argentina (INT)",
    1370: "🛡️ Brazil (INT)", 1337: "🛡️ Germany (INT)", 1343: "🛡️ Italy (INT)",
    1357: "🛡️ Netherlands (INT)"
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

    # Clean placeholder strings like "NationName_37" or "Nation 37"
    if n_name and isinstance(n_name, str):
        cleaned = n_name.strip()
        if "nationname_" in cleaned.lower() or "nation_" in cleaned.lower():
            # Extract ID if present in string
            digits = "".join([c for c in cleaned if c.isdigit()])
            if digits and not n_id:
                try: n_id = int(digits)
                except Exception: pass
            n_name = None
        elif cleaned.isdigit():
            if not n_id:
                try: n_id = int(cleaned)
                except Exception: pass
            n_name = None

    # Check ID lookup in nation_map first
    if n_id and int(n_id) in nation_map:
        return nation_map[int(n_id)]

    # Check explicit valid name
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

    # Clean placeholder strings like "TeamName_21" or "Club_21"
    if c_name and isinstance(c_name, str):
        cleaned = c_name.strip()
        if "teamname_" in cleaned.lower() or "club_" in cleaned.lower() or "team_" in cleaned.lower():
            digits = "".join([c for c in cleaned if c.isdigit()])
            if digits and not c_id:
                try: c_id = int(digits)
                except Exception: pass
            c_name = None
        elif cleaned.isdigit():
            if not c_id:
                try: c_id = int(cleaned)
                except Exception: pass
            c_name = None

    # Check ID in club_map first
    if c_id and int(c_id) in club_map:
        return club_map[int(c_id)]

    # Check explicit valid name
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

    # 1. Authoritative check: Extract from player_data JSON if available
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

    # 2. Direct key on row/dict
    for k in ('position', 'pos', 'cardPosition', 'primaryPosition'):
        v = _get(item, k)
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

# ================= Official Card Database Position Compatibility =================
# Players play with 100% full OVR at their primary position, official potentialPositions, or natural alternate positions

NATURAL_ALT_POSITIONS = {
    "CF": ["ST", "CAM"],
    "ST": ["CF"],
    "LW": ["LM", "LF", "RW"],
    "RW": ["RM", "RF", "LW"],
    "LM": ["LW", "RM"],
    "RM": ["RW", "LM"],
    "CAM": ["CM", "CF", "LM", "RM"],
    "CM": ["CAM", "CDM"],
    "CDM": ["CM", "CB"],
    "CB": ["CDM", "LB", "RB"],
    "LB": ["LWB", "LM", "RB", "LW"],
    "RB": ["RWB", "RM", "LB", "RW"],
    "LWB": ["LB", "LM"],
    "RWB": ["RB", "RM"],
    "GK": []
}

def get_player_official_positions(player_item) -> tuple[str, list[str]]:
    """
    Extracts the official main position and alternate positions (potentialPositions)
    directly from the player's card data.
    """
    if not player_item:
        return "ST", []
    
    # If wrapped in DB row
    if isinstance(player_item, dict) and 'player_data' in player_item:
        raw_pd = player_item['player_data']
        if isinstance(raw_pd, str):
            try: raw_pd = json.loads(raw_pd)
            except Exception: raw_pd = {}
        if isinstance(raw_pd, dict):
            clean_item = {**raw_pd}
            for k, v in player_item.items():
                if k != 'player_data' and v is not None:
                    # Do not overwrite valid position from player_data
                    if k == 'position' and clean_item.get('position'):
                        continue
                    clean_item[k] = v
            player_item = clean_item

    main_pos = extract_pos(player_item)
    
    # 1. Extract potentialPositions from official card data
    alt_raw = (
        player_item.get('potentialPositions') 
        or player_item.get('potential_positions') 
        or player_item.get('altPositions') 
        or player_item.get('alternatePositions')
        or []
    )
    if isinstance(alt_raw, str):
        try: alt_raw = json.loads(alt_raw)
        except Exception: alt_raw = [alt_raw]
    
    clean_alts = []
    if isinstance(alt_raw, (list, tuple)):
        for ap in alt_raw:
            if ap:
                clean_ap = ''.join([c for c in str(ap) if not c.isdigit()]).strip().upper()
                if clean_ap and clean_ap != main_pos and clean_ap not in clean_alts:
                    clean_alts.append(clean_ap)
                    
    # 2. Append Natural Alternate Positions if not already included
    for nat_ap in NATURAL_ALT_POSITIONS.get(main_pos, []):
        if nat_ap != main_pos and nat_ap not in clean_alts:
            clean_alts.append(nat_ap)
            
    return main_pos, clean_alts

def check_player_position_eligibility(player_item, slot_pos: str) -> tuple[bool, bool]:
    """
    Returns (is_eligible, is_primary) based on official database positions.
    - is_primary: True if slot is player's main natural position.
    - is_eligible: True if slot is player's main position OR in their official potentialPositions / natural alts.
    """
    if not slot_pos:
        return True, True
    clean_slot = ''.join([c for c in str(slot_pos) if not c.isdigit()]).strip().upper()
    main_pos, alts = get_player_official_positions(player_item)
    
    if clean_slot == main_pos:
        return True, True
    if clean_slot in alts:
        return True, False
    return False, False

def is_position_compatible(player_item_or_pos, slot_pos: str) -> bool:
    """
    Returns True if slot_pos is the player's primary position or an alternate position.
    """
    if not player_item_or_pos or not slot_pos:
        return True
    if isinstance(player_item_or_pos, dict):
        eligible, _ = check_player_position_eligibility(player_item_or_pos, slot_pos)
        return eligible
    # String fallback
    clean_slot = ''.join([c for c in str(slot_pos) if not c.isdigit()]).strip().upper()
    clean_nat = ''.join([c for c in str(player_item_or_pos) if not c.isdigit()]).strip().upper()
    return clean_nat == clean_slot

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

