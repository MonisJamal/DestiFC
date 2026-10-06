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

            def get_team_sectors(squad, team_avg_ovr):
                atk, mid, defn, gk = [], [], [], []
                starters = []
                for pos_raw, p in squad.get('players', {}).items():
                    if not p: continue
                    name = p.get('name') or p.get('player_name', 'Player')
                    pos = ''.join([c for c in pos_raw if not c.isdigit()]).strip().upper()
                    
                    p_ovr = p.get('ovr', 100)
                    inv_id_str = str(p.get('inv_id', ''))
                    
                    # Apply custom card / signature card buffs directly to the player's OVR for the match engine
                    is_custom = False
                    boost_val = 1.15
                    if inv_id_str in inv_map:
                        full_p = inv_map[inv_id_str]
                        is_custom = full_p.get('is_custom') or full_p.get('is_signature_box') or 'CUSTOM' in str(full_p.get('source', '')).upper() or 'SIGNATURE' in str(full_p.get('source', '')).upper()
                        boost_val = full_p.get('performance_boost', 1.15)
                    elif inv_id_str.startswith('custom_') or inv_id_str.startswith('sig_'):
                        is_custom = True
                        
                    if is_custom:
                        p_ovr = int(p_ovr * boost_val)
                    
                    entry = {"name": name, "pos": pos, "raw_pos": pos_raw, "ovr": p_ovr, "is_custom": is_custom}
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
                
                # Sector powers calculated directly from individual players
                atk_p = sum(p['ovr'] for p in atk) / len(atk) if atk else team_avg_ovr
                mid_p = sum(p['ovr'] for p in mid) / len(mid) if mid else team_avg_ovr
                def_p = sum(p['ovr'] for p in defn) / len(defn) if defn else team_avg_ovr
                gk_p = gk[0]['ovr'] if gk else team_avg_ovr
                
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

                # Apply Stadium Turf Perks (Home Venue Advantage)
                stadium_name = "⚡ Neon Stadium"
                if theme == "snow":
                    def_p += 1.5
                    stadium_name = "❄️ Frostbite Arena"
                elif theme == "lava":
                    atk_p += 2.5
                    stadium_name = "🌋 Volcanic Caldera"
                elif theme == "cyberpunk":
                    mid_p += 2.0
                    stadium_name = "🤖 Neo-Tokyo Cyber City"
                elif theme == "desert":
                    def_p += 3.0
                    gk_p += 1.5
                    stadium_name = "🌙 Arabian Oasis Coliseum"
                elif theme == "galaxy":
                    atk_p += 2.0
                    mid_p += 2.0
                    def_p += 2.0
                    gk_p += 2.0
                    stadium_name = "🌌 Celestial Orbit Stadium"
                elif theme == "gold":
                    atk_p += 3.0
                    mid_p += 3.0
                    def_p += 3.0
                    gk_p += 3.0
                    stadium_name = "👑 Champions Royal Colosseum"

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

            # Midfield Battle
            mid_diff = s_a["mid_p"] - s_b["mid_p"]
            possession_a = int(50 + (mid_diff * 1.8) + random.randint(-3, 3))
            possession_a = max(35, min(65, possession_a))
            possession_b = 100 - possession_a

            def calc_full_team_ratings(starters, is_winning_team, is_draw_match, goals_conceded, goals_scored):
                ratings = []
                for s in starters:
                    p_name = s['name']
                    pos = s['pos']
                    goals = player_scores.get(p_name, 0)
                    
                    base = 6.8 + random.uniform(-0.2, 0.3)
                    if is_winning_team: base += 0.7
                    elif is_draw_match: base += 0.2
                    else: base -= 0.5
                    
                    base += goals * 1.3
                    if pos == 'GK':
                        base += (saves_a if is_winning_team else saves_b) * 0.2
                        if goals_conceded == 0: base += 0.8
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        if goals_conceded == 0: base += 0.6
                        base += random.uniform(-0.1, 0.3)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        base += random.uniform(-0.1, 0.4)
                    elif pos in ['ST', 'CF', 'LW', 'RW']:
                        if goals == 0 and goals_scored > 0:
                            base += random.uniform(-0.2, 0.2)
                            
                    rating = round(min(10.0, max(5.5, base)), 1)
                    ratings.append({"name": p_name, "pos": pos, "rating": rating, "goals": goals, "ovr": s['ovr']})
                return ratings

            # Threat and goal probability calculations based on squad sectors & tactical synergy
            threat_a = (s_a["atk_p"] * 0.65 + s_a["mid_p"] * 0.35) - (s_b["def_p"] * 0.65 + s_b["gk_p"] * 0.35)
            threat_b = (s_b["atk_p"] * 0.65 + s_b["mid_p"] * 0.35) - (s_a["def_p"] * 0.65 + s_a["gk_p"] * 0.35)

            # High-intensity chances (5 to 8 chances per team for high excitement & realistic end-to-end action)
            chances_a = max(3, int(5 + (threat_a * 0.30) + random.randint(0, 2)))
            chances_b = max(3, int(5 + (threat_b * 0.30) + random.randint(0, 2)))

            goals_a = 0
            for _ in range(chances_a):
                p_score = 0.38 + (threat_a * 0.03) + random.uniform(-0.05, 0.08)
                if random.random() < max(0.12, min(0.68, p_score)):
                    goals_a += 1

            goals_b = 0
            for _ in range(chances_b):
                p_score = 0.38 + (threat_b * 0.03) + random.uniform(-0.05, 0.08)
                if random.random() < max(0.12, min(0.68, p_score)):
                    goals_b += 1

            # Cap goals realistically at 6
            goals_a = min(6, goals_a)
            goals_b = min(6, goals_b)

            # Late Drama Roll: 30% chance for an 88'-90' thriller goal if match is tied or 1-goal gap
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
            all_goals = []
            for idx in range(goals_a):
                r = random.random()
                if r < 0.65 and s_a["atk"]:
                    cands, ptype = s_a["atk"], "atk"
                elif r < 0.90 and s_a["mid"]:
                    cands, ptype = s_a["mid"], "mid"
                elif s_a["defn"]:
                    cands, ptype = s_a["defn"], "def"
                else:
                    cands, ptype = starters_a, "atk"
                scorer_obj = max(random.sample(cands, min(3, len(cands))), key=lambda x: x["ovr"] + random.randint(-2, 3))
                # If late drama, push the last goal to 88-90'
                min_g = random.randint(87, 90) if (late_drama and idx == goals_a - 1) else random.randint(7, 86)
                all_goals.append((player_a, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype))

            for idx in range(goals_b):
                r = random.random()
                if r < 0.65 and s_b["atk"]:
                    cands, ptype = s_b["atk"], "atk"
                elif r < 0.90 and s_b["mid"]:
                    cands, ptype = s_b["mid"], "mid"
                elif s_b["defn"]:
                    cands, ptype = s_b["defn"], "def"
                else:
                    cands, ptype = starters_b, "atk"
                scorer_obj = max(random.sample(cands, min(3, len(cands))), key=lambda x: x["ovr"] + random.randint(-2, 3))
                min_g = random.randint(87, 90) if (late_drama and idx == goals_b - 1) else random.randint(7, 86)
                all_goals.append((player_b, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype))

            all_goals.sort(key=lambda x: x[1])

            scoresheet_events = []
            player_scores = {p["name"]: 0 for p in (starters_a + starters_b)}
            current_score_a = 0
            current_score_b = 0

            # Realistic statistics totals
            shots_on_target_a = goals_a + random.randint(3, 7)
            shots_total_a = shots_on_target_a + random.randint(4, 8)
            shots_on_target_b = goals_b + random.randint(3, 7)
            shots_total_b = shots_on_target_b + random.randint(4, 8)

            saves_a = max(0, shots_on_target_b - goals_b)
            saves_b = max(0, shots_on_target_a - goals_a)

            # Match intervals with dynamic live clock animation across 90 minutes
            ticks = [12, 25, 38, 45, 58, 72, 84, 90]

            def render_clock_bar(min_val: int) -> str:
                blocks = min(10, max(1, int((min_val / 90.0) * 10)))
                bar = "▰" * blocks + "▱" * (10 - blocks)
                if min_val == 45:
                    return f"`[{bar}]` ⏱️ **45' HALF TIME ☕**"
                elif min_val >= 90:
                    return f"`[{bar}]` ⏱️ **90' FULL TIME 🏁**"
                else:
                    return f"`[{bar}]` ⏱️ **{min_val}' MIN**"

            for idx, current_minute in enumerate(ticks):
                prev_minute = ticks[idx - 1] if idx > 0 else 0
                tick_events = []

                # Check if any goals were scored in this interval
                interval_goals = [g for g in all_goals if prev_minute < g[1] <= current_minute]
                for g in interval_goals:
                    team_target, minute, scorer, pos, ptype = g[0], g[1], g[2], g[3], g[4]
                    player_scores[scorer] = player_scores.get(scorer, 0) + 1

                    if team_target == player_a:
                        current_score_a += 1
                        team_name = player_a.display_name
                    else:
                        current_score_b += 1
                        team_name = player_b.display_name

                    is_stoppage = (minute >= 88)
                    if is_stoppage:
                        goal_commentary = f"🚨 **{minute}' GOAL! UNBELIEVABLE DRAMA!** Stoppage-time pandemonium as **{scorer}** (`{pos}`) nets a breathless stunner for **{team_name}**! ⚡🔥"
                    elif ptype == "def":
                        goal_commentary = f"⚽ **{minute}' GOAL!** BULLET CORNER HEADER! Defender **{scorer}** (`{pos}`) rises above everyone and thumps it home for **{team_name}**! 📐🔥"
                    elif ptype == "mid":
                        goal_commentary = f"⚽ **{minute}' GOAL!** 30-YARD SCREAMER! **{scorer}** (`{pos}`) unleashes an unstoppable rocket into the top corner for **{team_name}**! ☄️"
                    else:
                        goal_commentary = f"⚽ **{minute}' GOAL!** PURE CLASS! **{scorer}** (`{pos}`) cuts past the keeper with filthy footwork and finishes with ice in his veins for **{team_name}**! 🧊⚽"

                    tick_events.append(goal_commentary)
                    scoresheet_events.append(f"⚽ **{minute}'** - **{scorer}** ({team_name})")

                # If no goals in this interval, generate contextual live play commentary
                if not tick_events and current_minute < 90:
                    is_a_attack = random.random() < (possession_a / 100.0)
                    if is_a_attack:
                        att_team_name = player_a.display_name
                        atk_pool, mid_pool, def_pool, gk_pool = atk_a, mid_a, def_b, gk_b
                        opp_mid_pool = mid_b
                    else:
                        att_team_name = player_b.display_name
                        atk_pool, mid_pool, def_pool, gk_pool = atk_b, mid_b, def_a, gk_a
                        opp_mid_pool = mid_a

                    a = random.choice(atk_pool)
                    m = random.choice(mid_pool)
                    d = random.choice(def_pool)
                    g = random.choice(gk_pool)
                    om = random.choice(opp_mid_pool)

                    commentary_choices = [
                        f"⚡ **ELECTRIC COUNTER-ATTACK!** **{m}** threads an audacious trivela through-ball, slicing {att_team_name}'s midfield wide open!",
                        f"🧤 **FINGERTIP HEROICS!** **{g}** produces an acrobatic top-corner save to deny a blistering volley from **{a}**!",
                        f"🚀 **CROSSBAR SHUDDER!** **{a}** connects sweetly on the half-volley from 25 yards... the woodwork is still vibrating!",
                        f"🛡️ **DESPERATE GOAL-LINE CLEARANCE!** Defender **{d}** slides across the goal-line to hook **{a}**'s chipped effort to safety!",
                        f"⚔️ **CRUNCHING TACKLE!** Anchor **{om}** flies in with an inch-perfect sliding challenge, stopping a certain 1-on-1 break!",
                        f"🎯 **MAGIC FOOTWORK!** **{a}** leaves two defenders grasping for air with a silky roulette before firing just wide of the post!",
                        f"📐 **WHIPPED INSWINGER!** **{m}** whips a treacherous curled set-piece towards the back stick, headed out for another corner!",
                        f"🟨 **CYNICAL TACTICAL FOUL!** **{d}** drags down **{a}** on the breakaway — yellow card shown by the referee!"
                    ]
                    chosen_comm = random.choice(commentary_choices)
                    tick_events.append(f"🎙️ *{chosen_comm}*")

                    if "fingertip heroics" in chosen_comm.lower() or "save" in chosen_comm.lower():
                        scoresheet_events.append(f"🧤 **{current_minute}'** - **{g}** (Heroic Save)")
                    elif "yellow card" in chosen_comm.lower():
                        scoresheet_events.append(f"🟨 **{current_minute}'** - **{d}** (Yellow Card)")

                # Build live scoreboard message
                scoreboard = f"**{player_a.display_name}** `[ {current_score_a} - {current_score_b} ]` **{player_b.display_name}**"
                clock_str = render_clock_bar(current_minute)

                live_shots_a = max(current_score_a, int(shots_total_a * (current_minute / 90.0)))
                live_shots_b = max(current_score_b, int(shots_total_b * (current_minute / 90.0)))
                stats_mini = f"📊 Possession: `{possession_a}%` ⬝ `{possession_b}%` | Shots: `{live_shots_a}` ⬝ `{live_shots_b}`"

                events_display = "\n".join(tick_events) if tick_events else "🏁 *Action unfolding on the pitch...*"

                recent_goals_str = ""
                if scoresheet_events:
                    goals_only = [e for e in scoresheet_events if "⚽" in e]
                    if goals_only:
                        recent_goals_str = "📋 **Goals:** " + " • ".join(goals_only[-3:]) + "\n\n"

                stadium_display = s_a.get("stadium_name", "⚡ Neon Stadium")
                status_footer = "🏁 *Final moments of the match...*" if current_minute >= 84 else ("☕ *Half time team talk underway...*" if current_minute == 45 else "⚡ *Ball in play...*")

                msg_content = (
                    f"🏟️ **LIVE DIVISION RIVALS MATCH** • *{stadium_display}*\n\n"
                    f"{scoreboard}\n"
                    f"{clock_str}  •  {stats_mini}\n\n"
                    f"{recent_goals_str}"
                    f"{events_display}\n\n"
                    f"*{status_footer}*"
                )

                async def safe_update_ui(content=None, embed=None, view=None):
                    try:
                        await interaction.edit_original_response(content=content, embed=embed, view=view)
                        return True
                    except Exception as e_resp:
                        if message:
                            try:
                                await message.edit(content=content, embed=embed, view=view)
                                return True
                            except Exception:
                                pass
                        return False

                if current_minute < 90:
                    await safe_update_ui(content=msg_content, view=None)
                    await asyncio.sleep(4.2)

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
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, current_score_b, current_score_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, current_score_a, current_score_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            if all_rated_final:
                motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0].get("goals", 0) * 2 + x[0].get("rating", 6.0)))
            else:
                motm_entry = {"name": "Match MVP", "rating": 8.0, "goals": 0}
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
                fan_change_str = f"**{player_a.display_name}** gained **+10,000 Fans**\n**{player_b.display_name}** lost **-2,000 Fans**"
                coins_won_a = "💰 **+28,750,000 Coins** *(👑 +15% Stadium Bonus!)*" if s_a.get('theme') == 'gold' else "💰 **+25,000,000 Coins**"
                bonus_a_str = f"{coins_won_a}\n🎫 **+1x Draft Voucher**"
                bonus_b_str = ""
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-2,000 Fans**"
                coins_won_b = "💰 **+28,750,000 Coins** *(👑 +15% Stadium Bonus!)*" if s_b.get('theme') == 'gold' else "💰 **+25,000,000 Coins**"
                bonus_a_str = ""
                bonus_b_str = f"{coins_won_b}\n🎫 **+1x Draft Voucher**"

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Match Score Sheet & Key Events
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
            if len(sheet_text) > 1024:
                sheet_text = sheet_text[:1020] + "..."
            embed.add_field(name="📋 Match Events", value=sheet_text, inline=False)
            
            # 2. Detailed Real-Life Team Match Statistics
            tactic_a_badge = f"{TACTICS.get(s_a['tactic'], {}).get('emoji', '🪄')} {s_a['tactic']}" + (" (🌟 Synergy)" if s_a['is_synergy'] else "")
            tactic_b_badge = f"{TACTICS.get(s_b['tactic'], {}).get('emoji', '🪄')} {s_b['tactic']}" + (" (🌟 Synergy)" if s_b['is_synergy'] else "")
            
            stats_table = (
                f"```\n"
                f"{player_a.display_name[:12]:<12}      STATISTIC      {player_b.display_name[:12]:>12}\n"
                f"{str(possession_a) + '%':<12}     Possession     {str(possession_b) + '%':>12}\n"
                f"{str(xg_a):<12}         xG          {str(xg_b):>12}\n"
                f"{f'{shots_total_a} ({shots_on_target_a})':<12}   Shots (Target)   {f'{shots_total_b} ({shots_on_target_b})':>12}\n"
                f"{str(saves_a):<12}       GK Saves       {str(saves_b):>12}\n"
                f"{str(corners_a):<12}       Corners        {str(corners_b):>12}\n"
                f"{f'{fouls_a} ({yellows_a}🟨)':<12}     Fouls (Cards)    {f'{fouls_b} ({yellows_b}🟨)':>12}\n"
                f"{str(pass_acc_a) + '%':<12}    Pass Accuracy   {str(pass_acc_b) + '%':>12}\n"
                f"```\n"
                f"🧠 **Tactics:** {player_a.display_name}: `{tactic_a_badge}` ⬝ {player_b.display_name}: `{tactic_b_badge}`"
            )
            embed.add_field(name="📊 Match Statistics", value=stats_table, inline=False)

            # 3. Man of the Match
            embed.add_field(name="🎖️ Man of the Match", value=motm_str, inline=False)

            # 4. Full Squad Player Ratings (All 11 Starters for both teams)
            def format_full_ratings(r_list):
                lines = []
                for r in r_list:
                    icon = "🧤" if r.get("pos") == "GK" else ("🛡️" if r.get("pos") in ['CB', 'LB', 'RB', 'LWB', 'RWB'] else ("⚡" if r.get("pos") in ['CAM', 'CM', 'CDM', 'LM', 'RM'] else "🔥"))
                    star = " ⭐" if r.get("name") == motm_entry.get("name") else ""
                    goals_cnt = r.get('goals', 0)
                    goal_badge = f" {'⚽' * goals_cnt}" if goals_cnt > 0 else ""
                    lines.append(f"{icon} `[{r.get('pos', 'SUB'):<3}]` **{r.get('name', 'Player')[:14]}** `{r.get('rating', 6.0)}`{star}{goal_badge}")
                txt = "\n".join(lines) if lines else "*No rating data*"
                return txt[:1024]

            embed.add_field(name=f"👥 {player_a.display_name} XI", value=format_full_ratings(ratings_a), inline=True)
            embed.add_field(name=f"👥 {player_b.display_name} XI", value=format_full_ratings(ratings_b), inline=True)

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
                    loss_fans = int(gp_cfg.get('match_loss_fans', -2_000))
                    win_xp = int(gp_cfg.get('match_win_xp', 75))

                    win_coins_a = int(win_coins * 1.15) if s_a.get('theme') == 'gold' else win_coins
                    win_coins_b = int(win_coins * 1.15) if s_b.get('theme') == 'gold' else win_coins

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

                    # Team A Assists & Stats
                    assists_pool_a = [p['name'] for p in starters_a if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
                    team_a_assists = {}
                    for g in all_goals:
                        if g[0] == player_a:
                            candidates = [p for p in assists_pool_a if p != g[2]]
                            if candidates:
                                assister = random.choice(candidates)
                                team_a_assists[assister] = team_a_assists.get(assister, 0) + 1

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

                    # Team B Assists & Stats
                    assists_pool_b = [p['name'] for p in starters_b if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
                    team_b_assists = {}
                    for g in all_goals:
                        if g[0] == player_b:
                            candidates = [p for p in assists_pool_b if p != g[2]]
                            if candidates:
                                assister = random.choice(candidates)
                                team_b_assists[assister] = team_b_assists.get(assister, 0) + 1

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
            print(f"Error in simulate_live_match: {e}")
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
