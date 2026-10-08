import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

import database
import ai_engine
from maps import TACTICS

# Global tracking set to ensure only 1 active H2H match / challenge at a time per user
ACTIVE_MATCH_USERS = set()

class MatchRequestView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, cog, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b, timeout_secs: int = 60):
        super().__init__(timeout=timeout_secs)
        self.challenger = challenger
        self.opponent = opponent
        self.cog = cog
        self.squad_a = squad_a
        self.squad_b = squad_b
        self.fans_a = fans_a
        self.fans_b = fans_b
        self.ovr_a = ovr_a
        self.ovr_b = ovr_b
        self.timeout_secs = timeout_secs
        self.message = None
        self.accepted = False

    async def on_timeout(self):
        if self.accepted:
            return
        ACTIVE_MATCH_USERS.discard(self.challenger.id)
        ACTIVE_MATCH_USERS.discard(self.opponent.id)
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content=f"⏱️ **Match Challenge Expired!** {self.opponent.display_name} did not respond within {self.timeout_secs} seconds.", view=self)
            except Exception:
                pass

    @discord.ui.button(label="Accept Match", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept!", ephemeral=True)
            return
            
        self.accepted = True
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"⚔️ **Match Accepted!** The players are walking onto the pitch...", view=self)
        
        # Start simulation in background passing both the interaction and self.message
        asyncio.create_task(self.cog.simulate_live_match(interaction, self.challenger, self.opponent, self.ovr_a, self.ovr_b, self.squad_a, self.squad_b, message=self.message))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline!", ephemeral=True)
            return
            
        self.stop()
        ACTIVE_MATCH_USERS.discard(self.challenger.id)
        ACTIVE_MATCH_USERS.discard(self.opponent.id)
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ **{self.opponent.display_name}** declined the match.", view=self)

class MatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calculate_ovr(self, squad):
        total = 0
        count = 0
        players = squad.get("players", {})
        for pos, player in players.items():
            if player:
                total += player['ovr']
                count += 1
        return round(total / 11) if count == 11 else 0

    def get_division(self, fans: int, gp_cfg: dict = None):
        if gp_cfg and "division_tiers" in gp_cfg and gp_cfg["division_tiers"]:
            tiers = sorted(gp_cfg["division_tiers"], key=lambda x: int(x.get('min_fans', 0)))
            matched = tiers[0]
            for t in tiers:
                if fans >= int(t.get('min_fans', 0)):
                    matched = t
                else:
                    break
            badge = matched.get('badge', '')
            name = matched.get('name', 'Amateur')
            return f"{name} {badge}".strip()

        if fans < 10000: return "Amateur III 🥉"
        elif fans < 20000: return "Amateur II 🥉"
        elif fans < 30000: return "Amateur I 🥉"
        elif fans < 50000: return "Pro III 🥈"
        elif fans < 70000: return "Pro II 🥈"
        elif fans < 100000: return "Pro I 🥈"
        elif fans < 200000: return "World Class III 🥇"
        elif fans < 300000: return "World Class II 🥇"
        elif fans < 400000: return "World Class I 🥇"
        elif fans < 600000: return "Legendary III 💎"
        elif fans < 800000: return "Legendary II 💎"
        elif fans < 1000000: return "Legendary I 💎"
        else: return "FC Champion 🏆"

    def get_division_index(self, fans: int, gp_cfg: dict = None):
        if gp_cfg and "division_tiers" in gp_cfg and gp_cfg["division_tiers"]:
            tiers = sorted(gp_cfg["division_tiers"], key=lambda x: int(x.get('min_fans', 0)))
            idx = 0
            for i, t in enumerate(tiers):
                if fans >= int(t.get('min_fans', 0)):
                    idx = i
                else:
                    break
            return idx

        if fans < 10000: return 0
        elif fans < 20000: return 1
        elif fans < 30000: return 2
        elif fans < 50000: return 3
        elif fans < 70000: return 4
        elif fans < 100000: return 5
        elif fans < 200000: return 6
        elif fans < 300000: return 7
        elif fans < 400000: return 8
        elif fans < 600000: return 9
        elif fans < 800000: return 10
        elif fans < 1000000: return 11
        else: return 12

    def get_div_reward(self, index: int):
        if index <= 2: return 3
        elif index <= 5: return 5
        elif index <= 8: return 7
        elif index <= 11: return 9
        else: return 11

    @app_commands.command(name="play", description="Challenge another user to a H2H Division Rivals Match!")
    async def play(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            return await interaction.response.send_message("❌ You cannot challenge a Discord bot to a match!", ephemeral=True)
            
        if opponent.id == interaction.user.id:
            return await interaction.response.send_message("❌ You can't play against yourself!", ephemeral=True)

        if interaction.user.id in ACTIVE_MATCH_USERS:
            return await interaction.response.send_message("❌ You already have an active match or pending challenge! Please finish it before starting another.", ephemeral=True)
            
        if opponent.id in ACTIVE_MATCH_USERS:
            return await interaction.response.send_message(f"❌ **{opponent.display_name}** is already in an active match or pending challenge! Please wait for them to finish.", ephemeral=True)
            
        await interaction.response.defer()

        gp_cfg = await database.get_gameplay_config()
        cooldown_mins = int(gp_cfg.get('match_cooldown_mins', 0))
        if cooldown_mins > 0:
            import time
            now = int(time.time())
            cooldown_secs = cooldown_mins * 60
            p = await database.get_db()
            last_match_a = await p.fetchval('SELECT last_match_time FROM users WHERE user_id = $1', interaction.user.id) or 0
            if now - last_match_a < cooldown_secs:
                rem = cooldown_secs - (now - last_match_a)
                return await interaction.followup.send(f"⏳ Match cooldown active! You can challenge again in **{int(rem // 60)}m {int(rem % 60)}s**.")
        
        squad_a = await database.get_squad(interaction.user.id)
        squad_b = await database.get_squad(opponent.id)
        
        ovr_a = self.calculate_ovr(squad_a)
        ovr_b = self.calculate_ovr(squad_b)
        
        if ovr_a == 0:
            return await interaction.followup.send(f"❌ Your starting XI is incomplete! Use `/squad set` or `/squad autobuild` to fill all 11 positions.")
        if ovr_b == 0:
            return await interaction.followup.send(f"❌ {opponent.display_name}'s starting XI is incomplete! They must fill all 11 positions.")
            
        user_a = await database.get_user(interaction.user.id)
        user_b = await database.get_user(opponent.id)
        fans_a, fans_b = user_a.get('fans', 0), user_b.get('fans', 0)
        
        # Lock both users in active match pool
        ACTIVE_MATCH_USERS.add(interaction.user.id)
        ACTIVE_MATCH_USERS.add(opponent.id)
        
        timeout_secs = int(gp_cfg.get('match_challenge_timeout_secs', 60))
        view = MatchRequestView(interaction.user, opponent, self, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b, timeout_secs=timeout_secs)
        
        msg = await interaction.followup.send(
            f"⚔️ **DIVISION RIVALS CHALLENGE!** ⚔️\n\n**{interaction.user.display_name} ({ovr_a})** [{self.get_division(fans_a, gp_cfg)}]\n🆚\n**{opponent.display_name} ({ovr_b})** [{self.get_division(fans_b, gp_cfg)}]\n\nHey {opponent.mention}, you have been challenged! Do you accept? *(Expires in {timeout_secs}s)*",
            view=view
        )
        view.message = msg

    async def simulate_live_match(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b, message=None):
        try:
            # 1. Extract players, positions, and sectoral power ratings
            inv_a = await database.get_inventory(player_a.id) or []
            inv_b = await database.get_inventory(player_b.id) or []
            inv_map = {}
            for c in (inv_a + inv_b):
                inv_map[str(c.get('id', ''))] = c

            gp_cfg = await database.get_gameplay_config()
            default_custom_boost = float(gp_cfg.get('custom_card_match_boost', 1.15))

            def get_team_sectors(squad, team_avg_ovr):
                atk, mid, defn, gk = [], [], [], []
                starters = []
                for pos_raw, p in squad.get('players', {}).items():
                    if not p: continue
                    name = p.get('name') or p.get('player_name', 'Player')
                    pos = ''.join([c for c in pos_raw if not c.isdigit()]).strip().upper()
                    name_lower = (name or '').lower()
                    is_yashin = 'yashin' in name_lower
                    is_lewa = 'lewandowski' in name_lower or 'lewa' in name_lower
                    is_akari = 'akari' in name_lower or 'watanabe' in name_lower
                    
                    p_ovr = p.get('ovr', 100)
                    inv_id_str = str(p.get('inv_id', ''))
                    
                    # Apply custom card / signature card buffs directly to the player's OVR for the match engine
                    is_custom = False
                    boost_val = default_custom_boost
                    pd = {}
                    if inv_id_str in inv_map:
                        full_p = inv_map[inv_id_str]
                        # Parse inner player_data JSON if string
                        pd_raw = full_p.get('player_data')
                        if isinstance(pd_raw, str):
                            try:
                                pd = json.loads(pd_raw)
                            except Exception:
                                pd = {}
                        elif isinstance(pd_raw, dict):
                            pd = pd_raw

                        boost_val = float(pd.get('performance_boost') or full_p.get('performance_boost') or default_custom_boost)

                        pid_str = str(full_p.get('player_id', '') or pd.get('id', '')).lower()
                        src_str = (str(full_p.get('source', '') or pd.get('source', ''))).upper()
                        
                        is_custom = bool(
                            full_p.get('is_custom') or full_p.get('is_signature_box') or
                            pd.get('is_custom') or pd.get('is_signature_box') or
                            'CUSTOM' in src_str or 'SIGNATURE' in src_str or
                            pid_str.startswith('sig_') or pid_str.startswith('custom_') or
                            inv_id_str.startswith('custom_') or inv_id_str.startswith('sig_')
                        )
                    base_ovr = int(p.get('ovr', 100))
                    effective_ovr = base_ovr

                    # Check for custom card / buffed parameters
                    if is_custom:
                        card_buffed_ovr = (
                            (pd.get('buffed_ovr') or pd.get('performance_ovr')) if isinstance(pd, dict) else None
                        ) or full_p.get('buffed_ovr') if 'full_p' in locals() and isinstance(full_p, dict) else None
                        if card_buffed_ovr:
                            try:
                                effective_ovr = int(card_buffed_ovr)
                            except Exception:
                                effective_ovr = base_ovr
                        else:
                            if pos == 'GK' or is_yashin:
                                effective_ovr = int(base_ovr * min(1.10, boost_val))
                            else:
                                effective_ovr = int(base_ovr * boost_val)

                    # Exact custom specifications:
                    # Lewa: like 135 OVR | Yashin: 130 OVR | Akari: 200 OVR
                    if is_akari:
                        is_custom = True
                        effective_ovr = max(effective_ovr, 200)
                    elif is_lewa:
                        is_custom = True
                        effective_ovr = max(effective_ovr, 135)
                    elif is_yashin:
                        is_custom = True
                        effective_ovr = max(effective_ovr, 130)

                    # Store clean base_ovr for stats, records, and displays;
                    # use effective_ovr strictly for match engine physics calculations
                    entry = {
                        "name": name,
                        "pos": pos,
                        "raw_pos": pos_raw,
                        "ovr": base_ovr,
                        "effective_ovr": effective_ovr,
                        "is_custom": is_custom,
                        "boost_val": boost_val
                    }
                    starters.append(entry)
                    if pos in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF']:
                        atk.append(entry)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        mid.append(entry)
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        defn.append(entry)
                    elif pos == 'GK':
                        gk.append(entry)
                    else:
                        mid.append(entry)
                
                # Sector powers calculated directly from individual players using effective_ovr
                atk_p = sum(p.get('effective_ovr', p['ovr']) for p in atk) / len(atk) if atk else team_avg_ovr
                mid_p = sum(p.get('effective_ovr', p['ovr']) for p in mid) / len(mid) if mid else team_avg_ovr
                def_p = sum(p.get('effective_ovr', p['ovr']) for p in defn) / len(defn) if defn else team_avg_ovr
                
                # Goalkeeper power directly from keeper (with Yashin at 130 OVR wall)
                gk_p = gk[0].get('effective_ovr', gk[0]['ovr']) if gk else team_avg_ovr

                # Elite Attacking Customs Buff: Lewa & Akari dominate their zones
                if any('lewandowski' in p['name'].lower() for p in starters):
                    atk_p += 8.0  # Polish Sniper Lethality Surge
                if any('akari' in p['name'].lower() or 'watanabe' in p['name'].lower() for p in starters):
                    mid_p += 7.0  # Akari Maestro Playmaker dominance
                    atk_p += 4.0  # Akari Clinical Threat

                tactic = squad.get('tactic', 'Tiki-Taka')
                formation = squad.get('formation', '4-3-3 Flat')
                theme = squad.get('theme', 'default')
                t_data = TACTICS.get(tactic, TACTICS["Tiki-Taka"])
                is_synergy = any(f.lower() in formation.lower() for f in t_data.get('best_formations', []))
                
                # Apply tactical chemistry boost if formation matches tactic
                if is_synergy:
                    if tactic == "Tiki-Taka":
                        mid_p += 5.0
                    elif tactic == "Gegenpressing":
                        atk_p += 4.5
                        mid_p += 3.0
                    elif tactic == "Wing Play":
                        atk_p += 4.5
                    elif tactic == "Counter-Attack":
                        def_p += 4.5
                        atk_p += 2.0
                    elif tactic == "Kick and Rush":
                        atk_p += 4.0
                    elif tactic == "Park the Bus":
                        def_p += 6.0
                        gk_p += 4.0
                    elif tactic == "Vertical Tiki-Taka":
                        mid_p += 4.0
                        atk_p += 3.5
                    elif tactic == "Total Football":
                        atk_p += 3.0
                        mid_p += 3.5
                        def_p += 3.0
                    elif tactic == "Catenaccio":
                        def_p += 6.5
                        gk_p += 4.5
                    elif tactic == "Heavy Metal Football":
                        atk_p += 5.5
                        mid_p += 2.5
                    elif tactic == "Direct Play":
                        atk_p += 4.0
                        mid_p += 2.5
                        def_p += 2.0

                # Apply Stadium Turf Perks (Home Venue Advantage)
                stadium_name = "⚡ Neon Stadium"
                if theme == "snow":
                    def_p += 2.0
                    stadium_name = "❄️ Frostbite Arena"
                elif theme == "lava":
                    atk_p += 3.5
                    stadium_name = "🌋 Volcanic Caldera"
                elif theme == "cyberpunk":
                    mid_p += 3.0
                    stadium_name = "🤖 Neo-Tokyo Cyber City"
                elif theme == "desert":
                    def_p += 4.0
                    gk_p += 2.0
                    stadium_name = "🌙 Arabian Oasis Coliseum"
                elif theme == "galaxy":
                    atk_p += 3.0
                    mid_p += 3.0
                    def_p += 3.0
                    gk_p += 1.5
                    stadium_name = "🌌 Celestial Orbit Stadium"
                elif theme == "gold":
                    atk_p += 6.0
                    mid_p += 6.0
                    def_p += 6.0
                    gk_p += 2.5
                    stadium_name = "👑 Champions Royal Colosseum"
                elif theme == "bernabeu":
                    atk_p += 7.0
                    mid_p += 5.0
                    stadium_name = "⚪ Santiago Bernabéu"
                elif theme == "campnou":
                    mid_p += 8.0
                    atk_p += 5.0
                    stadium_name = "🔵🔴 Spotify Camp Nou"
                elif theme == "oldtrafford":
                    atk_p += 7.0
                    def_p += 5.0
                    stadium_name = "🔴 Old Trafford"
                elif theme == "anfield":
                    atk_p += 7.5
                    def_p += 5.5
                    stadium_name = "🔥 Anfield"
                elif theme == "sansiro":
                    def_p += 8.0
                    mid_p += 4.0
                    gk_p += 2.5
                    stadium_name = "⚔️ San Siro"
                elif theme == "allianz":
                    atk_p += 7.5
                    mid_p += 5.0
                    stadium_name = "🔴 Allianz Arena"
                elif theme == "maracana":
                    atk_p += 8.0
                    mid_p += 5.0
                    stadium_name = "🇧🇷 Maracanã Stadium"
                elif theme == "wembley":
                    atk_p += 6.0
                    mid_p += 6.0
                    def_p += 6.0
                    stadium_name = "🦁 Wembley Stadium"

                return {
                    "atk": atk, "mid": mid, "defn": defn, "gk": gk, "starters": starters,
                    "atk_p": atk_p, "mid_p": mid_p, "def_p": def_p, "gk_p": gk_p,
                    "tactic": tactic, "formation": formation, "is_synergy": is_synergy,
                    "theme": theme, "stadium_name": stadium_name
                }

            s_a = get_team_sectors(squad_a, ovr_a)
            s_b = get_team_sectors(squad_b, ovr_b)

            starters_a = s_a["starters"]
            starters_b = s_b["starters"]
            atk_a = [p['name'] for p in s_a["atk"]] or [p['name'] for p in starters_a]
            mid_a = [p['name'] for p in s_a["mid"]] or [p['name'] for p in starters_a]
            def_a = [p['name'] for p in s_a["defn"]] or [p['name'] for p in starters_a]
            gk_a = [p['name'] for p in s_a["gk"]] or ["Goalkeeper"]

            atk_b = [p['name'] for p in s_b["atk"]] or [p['name'] for p in starters_b]
            mid_b = [p['name'] for p in s_b["mid"]] or [p['name'] for p in starters_b]
            def_b = [p['name'] for p in s_b["defn"]] or [p['name'] for p in starters_b]
            gk_b = [p['name'] for p in s_b["gk"]] or ["Goalkeeper"]

            # Midfield Battle & Stadium Possession Perks
            mid_diff = s_a["mid_p"] - s_b["mid_p"]
            possession_a = int(50 + (mid_diff * 1.8) + random.randint(-2, 2))
            if s_a.get('theme') == 'campnou':
                possession_a += 6
            if s_b.get('theme') == 'campnou':
                possession_a -= 6
            possession_a = max(30, min(70, possession_a))
            possession_b = 100 - possession_a

            def calc_full_team_ratings(starters, is_winning_team, is_draw_match, goals_conceded, goals_scored, team_goals, team_assists, team_saves):
                ratings = []
                for s in starters:
                    p_name = s['name']
                    pos = s['pos']
                    goals = team_goals.get(p_name, 0)
                    assists = team_assists.get(p_name, 0)
                    
                    base = 6.8 + random.uniform(-0.2, 0.3)
                    if is_winning_team: base += 0.7
                    elif is_draw_match: base += 0.2
                    else: base -= 0.5
                    
                    base += goals * 1.3 + assists * 0.7
                    if pos == 'GK':
                        base += team_saves * 0.2
                        if goals_conceded == 0: base += 0.8
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        if goals_conceded == 0: base += 0.6
                        base += random.uniform(-0.1, 0.3)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        base += random.uniform(-0.1, 0.4)
                    if s.get('is_custom'):
                        base += 0.8
                            
                    rating = round(min(10.0, max(5.5, base)), 1)
                    ratings.append({"name": p_name, "pos": pos, "rating": rating, "goals": goals, "assists": assists, "ovr": s['ovr'], "is_custom": s.get('is_custom', False)})
                return ratings

            # Threat and goal probability calculations based on squad sectors & tactical synergy
            threat_a = (s_a["atk_p"] * 0.60 + s_a["mid_p"] * 0.40) - (s_b["def_p"] * 0.60 + s_b["gk_p"] * 0.40)
            threat_b = (s_b["atk_p"] * 0.60 + s_b["mid_p"] * 0.40) - (s_a["def_p"] * 0.60 + s_a["gk_p"] * 0.40)

            # Balanced exciting chances (5 to 8 chances per team)
            chances_a = max(4, int(5 + (threat_a * 0.15) + random.randint(0, 2)))
            chances_b = max(4, int(5 + (threat_b * 0.15) + random.randint(0, 2)))

            goals_a = 0
            for _ in range(chances_a):
                p_score = 0.38 + (threat_a * 0.015) + random.uniform(-0.04, 0.04)
                if random.random() < max(0.18, min(0.58, p_score)):
                    goals_a += 1

            goals_b = 0
            for _ in range(chances_b):
                p_score = 0.38 + (threat_b * 0.015) + random.uniform(-0.04, 0.04)
                if random.random() < max(0.18, min(0.58, p_score)):
                    goals_b += 1

            # Realistic exciting scoreline cap: 5 goals max (allowing thrillers like 4-3, 5-4, 5-3, 3-2)
            goals_a = min(5, goals_a)
            goals_b = min(5, goals_b)

            # Late Drama Roll: 35% chance for an 88'-90' thriller goal if match is tied or 1-goal gap
            late_drama = random.random() < 0.35
            if late_drama:
                if goals_a == goals_b and random.random() < 0.60:
                    # Someone grabs a dramatic 89' winner!
                    if random.random() < (0.5 + (threat_a - threat_b) * 0.02):
                        goals_a += 1
                    else:
                        goals_b += 1
                elif abs(goals_a - goals_b) == 1 and random.random() < 0.45:
                    # Trailing team grabs a last-gasp 90' equalizer!
                    if goals_a < goals_b:
                        goals_a += 1
                    else:
                        goals_b += 1

            # Distribute goals across 90 minutes with positional roles (attackers, midfielders, defenders)
            assists_pool_a = [p['name'] for p in starters_a if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
            assists_pool_b = [p['name'] for p in starters_b if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
            team_a_assists = {}
            team_b_assists = {}

            # Outfield players only (GOALKEEPERS NEVER SCORE GOALS)
            outfield_a = [p for p in starters_a if p.get('pos') != 'GK']
            outfield_b = [p for p in starters_b if p.get('pos') != 'GK']

            # Prioritize Lewandowski and Akari Watanabe as lethal primary goalscorers (outfield only)
            lewa_akari_a = [p for p in outfield_a if 'lewandowski' in p['name'].lower() or 'akari' in p['name'].lower() or 'watanabe' in p['name'].lower()]
            custom_scorers_a = [p for p in outfield_a if p.get('is_custom')]

            all_goals = []
            for idx in range(goals_a):
                if lewa_akari_a and random.random() < 0.65:
                    scorer_obj = random.choice(lewa_akari_a)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                elif custom_scorers_a and random.random() < 0.50:
                    scorer_obj = random.choice(custom_scorers_a)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                else:
                    r = random.random()
                    if r < 0.65 and s_a["atk"]:
                        cands, ptype = s_a["atk"], "atk"
                    elif r < 0.90 and s_a["mid"]:
                        cands, ptype = s_a["mid"], "mid"
                    elif s_a["defn"]:
                        cands, ptype = s_a["defn"], "def"
                    else:
                        cands, ptype = (s_a["atk"] or outfield_a), "atk"
                    cands = [p for p in cands if p.get('pos') != 'GK'] or outfield_a
                    scorer_obj = max(random.sample(cands, min(3, len(cands))), key=lambda x: x["ovr"] + random.randint(-2, 3))
                
                # Strict absolute guard: GKs never score
                if scorer_obj.get("pos") == "GK":
                    scorer_obj = random.choice(outfield_a)

                # If late drama, push the last goal to 88-90'
                min_g = random.randint(87, 90) if (late_drama and idx == goals_a - 1) else random.randint(7, 86)
                
                # Assign assister (70% probability if candidates exist)
                assister = None
                if random.random() < 0.75:
                    a_cands = [p for p in assists_pool_a if p != scorer_obj["name"]]
                    if a_cands:
                        assister = random.choice(a_cands)
                        team_a_assists[assister] = team_a_assists.get(assister, 0) + 1

                all_goals.append((player_a, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype, assister))

            lewa_akari_b = [p for p in outfield_b if 'lewandowski' in p['name'].lower() or 'akari' in p['name'].lower() or 'watanabe' in p['name'].lower()]
            custom_scorers_b = [p for p in outfield_b if p.get('is_custom')]

            for idx in range(goals_b):
                if lewa_akari_b and random.random() < 0.65:
                    scorer_obj = random.choice(lewa_akari_b)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                elif custom_scorers_b and random.random() < 0.50:
                    scorer_obj = random.choice(custom_scorers_b)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                else:
                    r = random.random()
                    if r < 0.65 and s_b["atk"]:
                        cands, ptype = s_b["atk"], "atk"
                    elif r < 0.90 and s_b["mid"]:
                        cands, ptype = s_b["mid"], "mid"
                    elif s_b["defn"]:
                        cands, ptype = s_b["defn"], "def"
                    else:
                        cands, ptype = (s_b["atk"] or outfield_b), "atk"
                    cands = [p for p in cands if p.get('pos') != 'GK'] or outfield_b
                    scorer_obj = max(random.sample(cands, min(3, len(cands))), key=lambda x: x["ovr"] + random.randint(-2, 3))
                
                # Strict absolute guard: GKs never score
                if scorer_obj.get("pos") == "GK":
                    scorer_obj = random.choice(outfield_b)

                min_g = random.randint(87, 90) if (late_drama and idx == goals_b - 1) else random.randint(7, 86)
                
                # Assign assister (70% probability if candidates exist)
                assister = None
                if random.random() < 0.75:
                    b_cands = [p for p in assists_pool_b if p != scorer_obj["name"]]
                    if b_cands:
                        assister = random.choice(b_cands)
                        team_b_assists[assister] = team_b_assists.get(assister, 0) + 1

                all_goals.append((player_b, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype, assister))

            all_goals.sort(key=lambda x: x[1])

            scoresheet_events = []
            team_a_player_goals = {}
            team_b_player_goals = {}
            current_score_a = 0
            current_score_b = 0

            # Realistic statistics totals
            shots_on_target_a = goals_a + random.randint(3, 7)
            shots_total_a = shots_on_target_a + random.randint(4, 8)
            shots_on_target_b = goals_b + random.randint(3, 7)
            shots_total_b = shots_on_target_b + random.randint(4, 8)

            saves_a = max(0, shots_on_target_b - goals_b)
            saves_b = max(0, shots_on_target_a - goals_a)

            # Match timeline: 90 real seconds (1 second = 1 match minute) + extra stoppage time
            stoppage_ht = random.randint(1, 3)  # +1' to +3' first half stoppage
            stoppage_ft = random.randint(2, 5)  # +2' to +5' second half stoppage

            # Distribute goals into match minutes (1 to 90 + stoppage)
            # Re-adjust goal times if needed so they fall across 1-90 and stoppage
            for i, g in enumerate(all_goals):
                if late_drama and i == len(all_goals) - 1:
                    # Score in 89-90 or extra time
                    stoppage_goal_min = 90 + random.randint(1, stoppage_ft) if random.random() < 0.4 else random.randint(88, 90)
                    all_goals[i] = (g[0], stoppage_goal_min, g[2], g[3], g[4], g[5] if len(g) > 5 else None)

            def render_clock_bar(min_val: int, is_extra: bool = False, extra_min: int = 0) -> str:
                progress_capped = min(90, min_val)
                blocks = min(10, max(1, int((progress_capped / 90.0) * 10)))
                bar = "▰" * blocks + "▱" * (10 - blocks)
                if min_val == 45 and is_extra:
                    return f"`[{bar}]` ⏱️ **45+{extra_min}' ET**"
                elif min_val == 45 and not is_extra:
                    return f"`[{bar}]` ⏱️ **45' HALF TIME ☕**"
                elif min_val >= 90 and is_extra:
                    return f"`[{bar}]` ⏱️ **90+{extra_min}' STOPPAGE TIME 🔥**"
                elif min_val >= 90:
                    return f"`[{bar}]` ⏱️ **90' FULL TIME 🏁**"
                else:
                    return f"`[{bar}]` ⏱️ **{min_val}' MIN**"

            async def safe_update_ui(content=None, embed=None, view=None):
                try:
                    await interaction.edit_original_response(content=content, embed=embed, view=view)
                    return True
                except Exception:
                    if message:
                        try:
                            await message.edit(content=content, embed=embed, view=view)
                            return True
                        except Exception:
                            pass
                    return False

            stadium_display = s_a.get("stadium_name", "⚡ Neon Stadium")
            latest_events_feed = []

            # Timeline execution loop: 1 to 90 seconds (1 second = 1 match minute)
            # Plus extra stoppage time
            curr_sim_min = 1
            last_edit_time = 0

            # Construct full progression sequence of minutes:
            # 1 to 45, 45+1..45+stoppage, HT pause, 46 to 90, 90+1..90+stoppage
            minute_sequence = []
            for m in range(1, 46):
                minute_sequence.append((m, False, 0, "1st Half"))
            for em in range(1, stoppage_ht + 1):
                minute_sequence.append((45, True, em, "1st Half Extra Time"))
            minute_sequence.append((45, False, 0, "Half Time Break"))
            for m in range(46, 91):
                minute_sequence.append((m, False, 0, "2nd Half"))
            for em in range(1, stoppage_ft + 1):
                minute_sequence.append((90, True, em, "2nd Half Extra Time"))

            # Discord rate-limit safety: edit roughly every 2.5 - 3 seconds or immediately on goals / HT
            for seq_idx, (m_val, is_et, et_val, phase_label) in enumerate(minute_sequence):
                time_now = asyncio.get_event_loop().time()
                time_label = f"45+{et_val}'" if (m_val == 45 and is_et) else (f"90+{et_val}'" if (m_val == 90 and is_et) else f"{m_val}'")

                # Check if a goal happens at this exact minute
                # For regular minutes match m_val. For stoppage time match 90+et_val or 45+et_val
                effective_min = (90 + et_val) if (m_val == 90 and is_et) else ((45 + et_val) if (m_val == 45 and is_et) else m_val)
                matched_goals = [g for g in all_goals if g[1] == effective_min]

                goal_happened = False
                for g in matched_goals:
                    goal_happened = True
                    team_target, min_scored, scorer, pos, ptype = g[0], g[1], g[2], g[3], g[4]
                    assister = g[5] if len(g) > 5 else None
                    if team_target == player_a:
                        current_score_a += 1
                        team_name = player_a.display_name
                        team_a_player_goals[scorer] = team_a_player_goals.get(scorer, 0) + 1
                    else:
                        current_score_b += 1
                        team_name = player_b.display_name
                        team_b_player_goals[scorer] = team_b_player_goals.get(scorer, 0) + 1

                    assist_comm = f" assisted by **{assister}**" if assister else ""
                    is_stoppage_goal = (is_et or min_scored >= 88)
                    s_lower = scorer.lower()
                    if 'lewandowski' in s_lower:
                        goal_commentary = f"⚽ **{time_label} GOAL! PURE LETHALITY!** Robert **Lewandowski** (`{pos}`){assist_comm} clinically hammers a thunderbolt into the bottom corner for **{team_name}**! 🎯🇵🇱"
                    elif 'akari' in s_lower or 'watanabe' in s_lower:
                        goal_commentary = f"✨ **{time_label} GOAL! MAGICAL MAESTRO!** Akari **Watanabe** (`{pos}`){assist_comm} dances through the backline and chips the keeper with sublime flair for **{team_name}**! 🌸⚡"
                    elif is_stoppage_goal:
                        goal_commentary = f"🚨 **{time_label} GOAL! UNBELIEVABLE DRAMA!** Stoppage-time pandemonium as **{scorer}** (`{pos}`){assist_comm} nets a breathless stunner for **{team_name}**! ⚡🔥"
                    elif ptype == "def":
                        goal_commentary = f"⚽ **{time_label} GOAL!** BULLET HEADER! Defender **{scorer}** (`{pos}`){assist_comm} rises highest from the corner and thumps it home for **{team_name}**! 📐🔥"
                    elif ptype == "mid":
                        goal_commentary = f"⚽ **{time_label} GOAL!** 30-YARD SCREAMER! **{scorer}** (`{pos}`){assist_comm} unleashes an unstoppable rocket into the top corner for **{team_name}**! ☄️"
                    else:
                        goal_commentary = f"⚽ **{time_label} GOAL!** PURE CLASS! **{scorer}** (`{pos}`){assist_comm} cuts past the keeper with silky footwork and finishes with ice in his veins for **{team_name}**! 🧊⚽"

                    latest_events_feed.insert(0, goal_commentary)
                    assist_str = f" *(🅰️ {assister})*" if assister else ""
                    scoresheet_events.append(f"⚽ **{time_label}** - **{scorer}**{assist_str} ({team_name})")

                # Random key event commentary every ~10-15 minutes if no goal
                if not matched_goals and (m_val % 8 == 0 or (is_et and et_val == 1)) and phase_label != "Half Time Break":
                    is_a_attack = random.random() < (possession_a / 100.0)
                    att_team_name = player_a.display_name if is_a_attack else player_b.display_name
                    atk_pool = atk_a if is_a_attack else atk_b
                    mid_pool = mid_a if is_a_attack else mid_b
                    def_pool = def_b if is_a_attack else def_a
                    gk_pool = gk_b if is_a_attack else gk_a
                    opp_mid_pool = mid_b if is_a_attack else mid_a

                    a_p = random.choice(atk_pool)
                    m_p = random.choice(mid_pool)
                    d_p = random.choice(def_pool)
                    g_p = random.choice(gk_pool)
                    om_p = random.choice(opp_mid_pool)

                    commentary_choices = [
                        f"⚡ **{time_label}** **{m_p}** threads an audacious through-ball, slicing open {att_team_name}'s defense!",
                        f"🧤 **{time_label}** FINGERTIP SAVE! **{g_p}** produces an acrobatic stop to deny a blistering volley from **{a_p}**!",
                        f"🚀 **{time_label}** WOODWORK! **{a_p}** rattles the crossbar with a ferocious 25-yard strike!",
                        f"🛡️ **{time_label}** GOAL-LINE CLEARANCE! **{d_p}** slides across the turf to hook **{a_p}**'s chip off the line!",
                        f"⚔️ **{time_label}** CRUNCHING TACKLE! **{om_p}** stops a dangerous breakaway with an inch-perfect challenge!",
                        f"🎯 **{time_label}** SILKY SKILLS! **{a_p}** beats two defenders with a roulette before curling just wide!",
                        f"🟨 **{time_label}** YELLOW CARD! Tactical foul by **{d_p}** to break up a lightning counter!"
                    ]
                    chosen_comm = random.choice(commentary_choices)
                    latest_events_feed.insert(0, f"🎙️ *{chosen_comm}*")
                    if "yellow card" in chosen_comm.lower():
                        scoresheet_events.append(f"🟨 **{time_label}** - **{d_p}** (Yellow Card)")
                    elif "fingertip save" in chosen_comm.lower():
                        scoresheet_events.append(f"🧤 **{time_label}** - **{g_p}** (Great Save)")

                # Keep latest events compact (top 3)
                events_display = "\n".join(latest_events_feed[:3]) if latest_events_feed else "🏁 *Intense battle for possession in midfield...*"

                # Determine if we should update Discord UI on this second
                # Always update if goal happened, or at half-time, or if >= 2.0 seconds elapsed
                time_since_edit = time_now - last_edit_time
                is_ht_break = (phase_label == "Half Time Break")
                is_last_step = (seq_idx == len(minute_sequence) - 1)

                should_update_ui = goal_happened or is_ht_break or (time_since_edit >= 2.0) or is_last_step

                if should_update_ui:
                    scoreboard = f"**{player_a.display_name}** `[ {current_score_a} - {current_score_b} ]` **{player_b.display_name}**"
                    clock_str = render_clock_bar(m_val, is_extra=is_et, extra_min=et_val)

                    live_shots_a = max(current_score_a, int(shots_total_a * (min(90, m_val) / 90.0)))
                    live_shots_b = max(current_score_b, int(shots_total_b * (min(90, m_val) / 90.0)))
                    stats_mini = f"📊 Possession: `{possession_a}%` ⬝ `{possession_b}%` | Shots: `{live_shots_a}` ⬝ `{live_shots_b}`"

                    recent_goals_str = ""
                    goals_only = [e for e in scoresheet_events if "⚽" in e]
                    if goals_only:
                        recent_goals_str = "📋 **Goals:** " + " • ".join(goals_only[-3:]) + "\n\n"

                    if is_ht_break:
                        status_footer = f"☕ **HALF TIME BREAK** • 1st Half Stoppage was +{stoppage_ht}'"
                    elif is_et:
                        status_footer = f"🔥 **+{stoppage_ft if m_val == 90 else stoppage_ht} MIN EXTRA STOPPAGE TIME ADDED!**"
                    elif m_val >= 85:
                        status_footer = "⚡ *Final minutes of regulation time! Huge tension on the pitch...*"
                    else:
                        status_footer = "⚡ *Ball in play... Match in progress!*"

                    msg_content = (
                        f"🏟️ **LIVE DIVISION RIVALS MATCH** • *{stadium_display}*\n\n"
                        f"{scoreboard}\n"
                        f"{clock_str}  •  {stats_mini}\n\n"
                        f"{recent_goals_str}"
                        f"{events_display}\n\n"
                        f"*{status_footer}*"
                    )

                    await safe_update_ui(content=msg_content, view=None)
                    last_edit_time = asyncio.get_event_loop().time()

                # Sleep 0.58 seconds per minute (1.5s for HT) for ~60 seconds total match length
                if is_ht_break:
                    await asyncio.sleep(1.5)
                else:
                    await asyncio.sleep(0.58)

            # Match winner resolution
            if current_score_a > current_score_b:
                winner = player_a
                is_a_win, is_b_win, is_draw = True, False, False
            elif current_score_b > current_score_a:
                winner = player_b
                is_a_win, is_b_win, is_draw = False, True, False
            else:
                winner = None
                is_a_win, is_b_win, is_draw = False, False, True

            possession_a = int(50 + ((s_a["mid_p"] - s_b["mid_p"]) * 1.6) + random.randint(-2, 2))
            possession_a = max(35, min(65, possession_a))
            possession_b = 100 - possession_a
            pass_acc_a = random.randint(84, 94)
            pass_acc_b = random.randint(82, 93)
            corners_a = random.randint(2, 6)
            corners_b = random.randint(2, 6)
            fouls_a = random.randint(4, 11)
            fouls_b = random.randint(4, 11)
            yellows_a = random.randint(0, min(3, fouls_a // 3))
            yellows_b = random.randint(0, min(3, fouls_b // 3))
            xg_a = round(current_score_a * 0.65 + (shots_on_target_a * 0.18) + random.uniform(0.1, 0.25), 2)
            xg_b = round(current_score_b * 0.65 + (shots_on_target_b * 0.18) + random.uniform(0.1, 0.25), 2)
            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, current_score_b, current_score_a, team_a_player_goals, team_a_assists, saves_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, current_score_a, current_score_b, team_b_player_goals, team_b_assists, saves_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            if all_rated_final:
                motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0].get("goals", 0) * 2 + x[0].get("assists", 0) * 1.5 + x[0].get("rating", 6.0)))
            else:
                motm_entry = {"name": "Match MVP", "rating": 8.0, "goals": 0, "assists": 0}
                motm_team = player_a.display_name

            motm_str = f"⭐ **{motm_entry['name']}** `({motm_entry['rating']} Rating)` — *{motm_team}*"
            # Background AI analysis task (never delays the match)
            events_summary = [f"{g[1]}' {g[2]} ({g[0].display_name})" for g in all_goals]
            ai_analysis_task = asyncio.create_task(
                ai_engine.generate_post_match_analysis(
                    player_a.display_name,
                    player_b.display_name,
                    current_score_a,
                    current_score_b,
                    motm_entry['name'],
                    motm_entry['rating'],
                    events_summary
                )
            )

            color = discord.Color.light_grey()
            if winner is None:
                result_text = f"🤝 **IT'S A DRAW!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                fan_change_str = "Both players gained **+2,000 Fans**"
                bonus_a_str = ""
                bonus_b_str = ""
            elif winner == player_a:
                result_text = f"🏆 **{player_a.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.green()
                fan_change_str = f"**{player_a.display_name}** gained **+10,000 Fans**\n**{player_b.display_name}** lost **-8,000 Fans**"
                coins_won_a = "💰 **+31,250,000 Coins** *(👑 +25% Stadium Bonus!)*" if s_a.get('theme') == 'gold' else "💰 **+25,000,000 Coins**"
                bonus_a_str = f"{coins_won_a}\n🎫 **+1x Draft Voucher**"
                bonus_b_str = ""
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-8,000 Fans**"
                coins_won_b = "💰 **+31,250,000 Coins** *(👑 +25% Stadium Bonus!)*" if s_b.get('theme') == 'gold' else "💰 **+25,000,000 Coins**"
                bonus_a_str = ""
                bonus_b_str = f"{coins_won_b}\n🎫 **+1x Draft Voucher**"

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Match Score Sheet & Key Events
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
            if len(sheet_text) > 1024:
                sheet_text = sheet_text[:1020] + "..."
            embed.add_field(name="📋 Match Events", value=sheet_text, inline=False)
            
            # 2. Detailed Real-Life Team Match Statistics (Mobile-friendly layout)
            tactic_a_badge = f"{TACTICS.get(s_a['tactic'], {}).get('emoji', '🪄')} {s_a['tactic']}" + (" (🌟)" if s_a['is_synergy'] else "")
            tactic_b_badge = f"{TACTICS.get(s_b['tactic'], {}).get('emoji', '🪄')} {s_b['tactic']}" + (" (🌟)" if s_b['is_synergy'] else "")
            
            name_a_trunc = player_a.display_name[:14]
            name_b_trunc = player_b.display_name[:14]
            stats_content = (
                f"**{name_a_trunc}** 🆚 **{name_b_trunc}**\n"
                f"📊 **Possession:** `{possession_a}%` ⬝ `{possession_b}%`\n"
                f"🎯 **xG:** `{xg_a}` ⬝ `{xg_b}`\n"
                f"🥅 **Shots (Target):** `{shots_total_a} ({shots_on_target_a})` ⬝ `{shots_total_b} ({shots_on_target_b})`\n"
                f"🧤 **GK Saves:** `{saves_a}` ⬝ `{saves_b}`\n"
                f"📐 **Corners:** `{corners_a}` ⬝ `{corners_b}`\n"
                f"🟨 **Fouls (Cards):** `{fouls_a} ({yellows_a}🟨)` ⬝ `{fouls_b} ({yellows_b}🟨)`\n"
                f"🎯 **Pass Accuracy:** `{pass_acc_a}%` ⬝ `{pass_acc_b}%`\n"
                f"🧠 **Tactics:** `{tactic_a_badge}` ⬝ `{tactic_b_badge}`"
            )
            embed.add_field(name="📊 Match Statistics", value=stats_content, inline=False)

            # 3. Man of the Match
            embed.add_field(name="🎖️ Man of the Match", value=motm_str, inline=False)

            # 4. Full Squad Player Ratings (All 11 Starters for both teams with goals & assists)
            def format_full_ratings(r_list, assists_dict, is_team_a=True):
                lines = []
                current_team_name = player_a.display_name if is_team_a else player_b.display_name
                for r in r_list:
                    icon = "🧤" if r.get("pos") == "GK" else ("🛡️" if r.get("pos") in ['CB', 'LB', 'RB', 'LWB', 'RWB'] else ("⚡" if r.get("pos") in ['CAM', 'CM', 'CDM', 'LM', 'RM'] else "🔥"))
                    star = " ⭐" if (r.get("name") == motm_entry.get("name") and motm_team == current_team_name) else ""
                    goals_cnt = r.get('goals', 0)
                    assists_cnt = assists_dict.get(r.get('name', ''), 0)
                    
                    stats_badge = ""
                    if r.get('is_custom'):
                        stats_badge += " ⚡"
                    if goals_cnt > 0:
                        stats_badge += f" {'⚽' * goals_cnt}"
                    if assists_cnt > 0:
                        stats_badge += f" {'🅰️' * assists_cnt}"
                        
                    lines.append(f"{icon} `[{r.get('pos', 'SUB'):<3}]` **{r.get('name', 'Player')[:13]}** `{r.get('rating', 6.0)}`{star}{stats_badge}")
                txt = "\n".join(lines) if lines else "*No rating data*"
                return txt[:1024]

            embed.add_field(name=f"👥 {player_a.display_name} XI", value=format_full_ratings(ratings_a, team_a_assists, is_team_a=True), inline=True)
            embed.add_field(name=f"👥 {player_b.display_name} XI", value=format_full_ratings(ratings_b, team_b_assists, is_team_a=False), inline=True)

            # 5. Fans & Rewards
            embed.add_field(
                name="📈 Fans & Rewards",
                value=fan_change_str + ("\n" + bonus_a_str if bonus_a_str else "") + ("\n" + bonus_b_str if bonus_b_str else ""),
                inline=False
            )
            embed.set_footer(text="DestiFC Match Engine • Stats recorded to /club_stats & /player_stats")
            
            # PRESENT FULL TIME EMBED SAFELY
            ft_sent = await safe_update_ui(content=None, embed=embed, view=None)
            if not ft_sent:
                try:
                    await interaction.channel.send(content=f"🏁 **FULL TIME** — {player_a.mention} vs {player_b.mention}", embed=embed)
                    ft_sent = True
                except Exception as e_send:
                    print(f"[Match] Fallback channel send failed: {e_send}")

            gp_cfg = await database.get_gameplay_config()
            step_delay = float(gp_cfg.get('match_sim_step_delay_secs', 0))
            if step_delay > 0:
                await asyncio.sleep(min(step_delay, 10.0))

            # Background task: Database saves & rewards
            async def _bg_save_and_ai():
                try:
                    import time
                    now = int(time.time())
                    p = await database.get_db()
                    await p.execute('UPDATE users SET last_match_time = $1 WHERE user_id = $2 OR user_id = $3', now, player_a.id, player_b.id)

                    win_coins = int(gp_cfg.get('match_win_coins', 25_000_000))
                    draw_coins = int(gp_cfg.get('match_draw_coins', 10_000_000))
                    loss_coins = int(gp_cfg.get('match_loss_coins', 5_000_000))
                    win_fans = int(gp_cfg.get('match_win_fans', 10_000))
                    draw_fans = int(gp_cfg.get('match_draw_fans', 2_000))
                    loss_fans = int(gp_cfg.get('match_loss_fans', -8_000))
                    win_xp = int(gp_cfg.get('match_win_xp', 75))

                    win_coins_a = int(win_coins * 1.25) if s_a.get('theme') == 'gold' else win_coins
                    win_coins_b = int(win_coins * 1.25) if s_b.get('theme') == 'gold' else win_coins

                    if winner is None:
                        await database.add_fans(player_a.id, draw_fans)
                        await database.add_fans(player_b.id, draw_fans)
                        await database.add_coins(player_a.id, draw_coins)
                        await database.add_coins(player_b.id, draw_coins)
                    elif winner == player_a:
                        await database.add_fans(player_a.id, win_fans)
                        await database.add_fans(player_b.id, loss_fans)
                        await database.add_coins(player_a.id, win_coins_a)
                        await database.add_coins(player_b.id, loss_coins)
                        await database.add_vouchers(player_a.id, 1)
                        try:
                            from cogs.achievements import increment_stat, check_and_award
                            await increment_stat(player_a.id, "matches_won")
                            await check_and_award(player_a.id)
                            from cogs.season import add_season_xp
                            await add_season_xp(player_a.id, win_xp)
                        except Exception: pass
                    else:
                        await database.add_fans(player_b.id, win_fans)
                        await database.add_fans(player_a.id, loss_fans)
                        await database.add_coins(player_b.id, win_coins_b)
                        await database.add_coins(player_a.id, loss_coins)
                        await database.add_vouchers(player_b.id, 1)
                        try:
                            from cogs.achievements import increment_stat, check_and_award
                            await increment_stat(player_b.id, "matches_won")
                            await check_and_award(player_b.id)
                            from cogs.season import add_season_xp
                            await add_season_xp(player_b.id, win_xp)
                        except Exception: pass

                    # Team A Stats (using pre-computed team_a_assists)
                    stats_list_a = []
                    for r in ratings_a:
                        p_name = r['name']
                        pos = r['pos']
                        is_df_gk = any(k in pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                        cs = 1 if (is_df_gk and current_score_b == 0) else 0
                        y_card = 1 if (yellows_a > 0 and random.random() < 0.25) else 0
                        stats_list_a.append({
                            "player_name": p_name,
                            "position": pos,
                            "ovr": r.get('ovr', 100),
                            "goals": r.get('goals', 0),
                            "assists": team_a_assists.get(p_name, 0),
                            "clean_sheets": cs,
                            "yellow_cards": y_card,
                            "red_cards": 0,
                            "rating": r.get('rating', 6.0),
                            "is_motm": 1 if (p_name == motm_entry['name'] and motm_team == player_a.display_name) else 0
                        })
                    await database.record_player_match_stats(player_a.id, stats_list_a)

                    # Team B Stats (using pre-computed team_b_assists)
                    stats_list_b = []
                    for r in ratings_b:
                        p_name = r['name']
                        pos = r['pos']
                        is_df_gk = any(k in pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                        cs = 1 if (is_df_gk and current_score_a == 0) else 0
                        y_card = 1 if (yellows_b > 0 and random.random() < 0.25) else 0
                        stats_list_b.append({
                            "player_name": p_name,
                            "position": pos,
                            "ovr": r.get('ovr', 100),
                            "goals": r.get('goals', 0),
                            "assists": team_b_assists.get(p_name, 0),
                            "clean_sheets": cs,
                            "yellow_cards": y_card,
                            "red_cards": 0,
                            "rating": r.get('rating', 6.0),
                            "is_motm": 1 if (p_name == motm_entry['name'] and motm_team == player_b.display_name) else 0
                        })
                    await database.record_player_match_stats(player_b.id, stats_list_b)

                    # Optional AI Pundit breakdown edit
                    try:
                        ai_text = await asyncio.wait_for(ai_analysis_task, timeout=4.0)
                        if ai_text:
                            embed.add_field(name="🎙️ AI Tactical Analysis", value=f"*{ai_text}*", inline=False)
                            await interaction.edit_original_response(embed=embed)
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[Match] Background save error: {ex}")

            asyncio.create_task(_bg_save_and_ai())

        except Exception as e:
            import traceback
            print(f"Error in simulate_live_match: {e}")
            traceback.print_exc()
            try:
                if message:
                    await message.edit(content=f"⚠️ **Match simulation error:** `{e}`. Match cancelled and slots cleared.", view=None)
                elif interaction:
                    await interaction.followup.send(f"⚠️ **Match simulation error:** `{e}`. Match cancelled and slots cleared.")
            except Exception:
                pass
        finally:
            ACTIVE_MATCH_USERS.discard(player_a.id)
            ACTIVE_MATCH_USERS.discard(player_b.id)

    @app_commands.command(name="leaderboard", description="View Global Leaderboards (Fans, Coins, or Vouchers)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🏆 Division Rivals (Fans)", value="fans"),
        app_commands.Choice(name="💰 Cash / Coins", value="coins"),
        app_commands.Choice(name="🎫 Draft Vouchers", value="vouchers")
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str = "fans"):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        if category == "coins":
            lb = await database.get_coins_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                coins = row['coins']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{coins:,}** Coins 💰")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="💰 Cash / Coins Global Leaderboard", description=desc, color=discord.Color.gold())
            
            if user_id not in top_ids:
                u_data = await database.get_user(user_id)
                embed.add_field(name="📍 Your Balance", value=f"🪙 **{u_data.get('coins', 0):,}** Coins", inline=False)
            
        elif category == "vouchers":
            lb = await database.get_vouchers_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                vouchers = row['vouchers']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{vouchers:,}** Vouchers 🎫")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🎫 Draft Vouchers Global Leaderboard", description=desc, color=discord.Color.blue())
            
            if user_id not in top_ids:
                u_data = await database.get_user(user_id)
                embed.add_field(name="📍 Your Inventory", value=f"🎫 **{u_data.get('vouchers', 0):,}** Draft Vouchers", inline=False)
            
        else:
            gp_cfg = await database.get_gameplay_config()
            lb = await database.get_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                div = self.get_division(row['fans'], gp_cfg)
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{row['fans']:,}** Fans `[{div}]`")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🌍 Division Rivals Leaderboard", description=desc, color=discord.Color.purple())

            if user_id not in top_ids:
                user_rank_info = await database.get_user_rank(user_id)
                user_fans = user_rank_info.get('fans', 0)
                user_div = self.get_division(user_fans, gp_cfg)
                embed.add_field(
                    name="📍 Your Global Rank",
                    value=f"**Rank #{user_rank_info.get('rank', 'N/A')}** of {user_rank_info.get('total_users', 1)} • **{user_fans:,}** Fans `[{user_div}]`",
                    inline=False
                )

        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

async def setup(bot):
    await bot.add_cog(MatchCog(bot))
