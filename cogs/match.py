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
        
        # Start simulation in background using the button interaction to edit the webhook
        asyncio.create_task(self.cog.simulate_live_match(interaction, self.challenger, self.opponent, self.ovr_a, self.ovr_b, self.squad_a, self.squad_b))

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

    async def simulate_live_match(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b):
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

                return {
                    "atk": atk, "mid": mid, "defn": defn, "gk": gk, "starters": starters,
                    "atk_p": atk_p, "mid_p": mid_p, "def_p": def_p, "gk_p": gk_p,
                    "tactic": tactic, "formation": formation, "is_synergy": is_synergy
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

            # Sector Battles (Attack vs Defense + GK)
            threat_a = (s_a["atk_p"] * 0.65 + s_a["mid_p"] * 0.35) - (s_b["def_p"] * 0.65 + s_b["gk_p"] * 0.35)
            threat_b = (s_b["atk_p"] * 0.65 + s_b["mid_p"] * 0.35) - (s_a["def_p"] * 0.65 + s_a["gk_p"] * 0.35)

            chances_a = max(2, int(4 + (threat_a * 0.35) + random.randint(-1, 2)))
            chances_b = max(2, int(4 + (threat_b * 0.35) + random.randint(-1, 2)))

            goals_a = 0
            for _ in range(chances_a):
                p_score = 0.28 + (threat_a * 0.035)
                if random.random() < max(0.08, min(0.60, p_score)):
                    goals_a += 1

            goals_b = 0
            for _ in range(chances_b):
                p_score = 0.28 + (threat_b * 0.035)
                if random.random() < max(0.08, min(0.60, p_score)):
                    goals_b += 1

            goals_a = min(5, goals_a)
            goals_b = min(5, goals_b)

            if goals_a > goals_b:
                winner = player_a
            elif goals_b > goals_a:
                winner = player_b
            else:
                winner = None
                
            # Distribute goals across 90 minutes
            all_goals = []
            for _ in range(goals_a): 
                # Weight goalscorer choice by individual player OVR
                scorer_cands = s_a["atk"] + s_a["mid"]
                if scorer_cands:
                    scorer_obj = max(random.sample(scorer_cands, min(3, len(scorer_cands))), key=lambda x: x['ovr'] + random.randint(-2, 3))
                    scorer = scorer_obj['name']
                else:
                    scorer = random.choice(atk_a + mid_a)
                all_goals.append((player_a, random.randint(8, 88), scorer))

            for _ in range(goals_b): 
                scorer_cands = s_b["atk"] + s_b["mid"]
                if scorer_cands:
                    scorer_obj = max(random.sample(scorer_cands, min(3, len(scorer_cands))), key=lambda x: x['ovr'] + random.randint(-2, 3))
                    scorer = scorer_obj['name']
                else:
                    scorer = random.choice(atk_b + mid_b)
                all_goals.append((player_b, random.randint(8, 88), scorer))

            all_goals.sort(key=lambda x: x[1])

            scoresheet_events = []
            player_scores = {p['name']: 0 for p in (starters_a + starters_b)}

            current_score_a = 0
            current_score_b = 0

            is_a_win = (winner == player_a)
            is_b_win = (winner == player_b)
            is_draw = (winner is None)

            # Generate realistic match statistics
            shots_on_target_a = goals_a + random.randint(2, 5)
            shots_total_a = shots_on_target_a + random.randint(3, 6)
            shots_on_target_b = goals_b + random.randint(2, 5)
            shots_total_b = shots_on_target_b + random.randint(3, 6)

            saves_a = max(0, shots_on_target_b - goals_b)
            saves_b = max(0, shots_on_target_a - goals_a)

            corners_a = random.randint(2, 7)
            corners_b = random.randint(2, 7)
            fouls_a = random.randint(2, 6)
            fouls_b = random.randint(2, 6)
            yellows_a = random.randint(0, 2)
            yellows_b = random.randint(0, 2)
            pass_acc_a = random.randint(83, 94)
            pass_acc_b = random.randint(81, 93)
            xg_a = round(goals_a * 0.65 + (shots_on_target_a * 0.16) + random.uniform(0.1, 0.3), 2)
            xg_b = round(goals_b * 0.65 + (shots_on_target_b * 0.16) + random.uniform(0.1, 0.3), 2)

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

            # Temporary pre-calculation for MOTM calculation
            for g in all_goals:
                player_scores[g[2]] = player_scores.get(g[2], 0) + 1

            ratings_a_est = calc_full_team_ratings(starters_a, is_a_win, is_draw, goals_b, goals_a)
            ratings_b_est = calc_full_team_ratings(starters_b, is_b_win, is_draw, goals_a, goals_b)
            all_rated = [(r, player_a.display_name) for r in ratings_a_est] + [(r, player_b.display_name) for r in ratings_b_est]
            motm_entry, motm_team = max(all_rated, key=lambda x: (x[0]["goals"] * 2 + x[0]["rating"]))

            # Reset player_scores for live commentary tracking
            player_scores = {p['name']: 0 for p in (starters_a + starters_b)}

            # Background AI analysis task (never delays the match)
            events_summary = [f"{g[1]}' {g[2]} ({g[0].display_name})" for g in all_goals]
            ai_analysis_task = asyncio.create_task(
                ai_engine.generate_post_match_analysis(
                    player_a.display_name,
                    player_b.display_name,
                    goals_a,
                    goals_b,
                    motm_entry['name'],
                    motm_entry['rating'],
                    events_summary
                )
            )

            # 1-minute match simulation (8 ticks x 7.5s = 60s total)
            ticks = [10, 25, 40, 45, 60, 75, 85, 90]
            
            for idx, current_minute in enumerate(ticks):
                prev_minute = ticks[idx - 1] if idx > 0 else 0
                events = []
                
                # Check for goals in this interval
                for g in all_goals:
                    if prev_minute < g[1] <= current_minute:
                        team_target = g[0]
                        minute = g[1]
                        scorer = g[2]
                        player_scores[scorer] = player_scores.get(scorer, 0) + 1
                        
                        if team_target == player_a:
                            current_score_a += 1
                            events.append(f"⚽ **GOAL FOR {player_a.display_name.upper()}!** Spectacular finish by **{scorer}**! 🔥 ({minute}')")
                            scoresheet_events.append(f"⚽ **{minute}'** - **{scorer}** ({player_a.display_name})")
                        else:
                            current_score_b += 1
                            events.append(f"⚽ **GOAL FOR {player_b.display_name.upper()}!** Clinical strike from **{scorer}**! 🔥 ({minute}')")
                            scoresheet_events.append(f"⚽ **{minute}'** - **{scorer}** ({player_b.display_name})")

                if not events and current_minute < 90:
                    if random.choice([True, False]):
                        t_atk, t_mid, t_def, t_gk = atk_a, mid_a, def_b, gk_b
                        att_team_name = player_a.display_name
                    else:
                        t_atk, t_mid, t_def, t_gk = atk_b, mid_b, def_a, gk_a
                        att_team_name = player_b.display_name
                        
                    a = random.choice(t_atk)
                    m = random.choice(t_mid)
                    d = random.choice(t_def)
                    g = random.choice(t_gk)
                    
                    commentary_pool = [
                        f"⚡ Fluid build-up orchestrated by **{m}** splitting the defensive line!",
                        f"🧤 WORLD-CLASS REFLEXES! **{g}** makes a fingertip diving save to deny a curled strike from **{a}**!",
                        f"🛡️ Rock-solid sliding interception from **{d}** thwarting a dangerous counter-attack.",
                        f"🎯 **{m}** delivers an inswinging cross into the box, cleared with authority by **{d}**.",
                        f"🚀 Long-range strike from **{a}**... it rattles violently off the crossbar!",
                        f"🔥 **{a}** executes a blistering step-over and cuts inside, but the shot is blocked behind for a corner.",
                        f"📐 Pinpoint corner whipped into the 6-yard box by **{m}**, headed just inches wide!",
                        f"🟨 Cynical tactical foul by **{d}** to halt {att_team_name}'s fast break."
                    ]
                    chosen_com = random.choice(commentary_pool)
                    events.append(f"🎙️ *{chosen_com}*")
                    
                    if "save" in chosen_com.lower():
                        scoresheet_events.append(f"🧤 **{current_minute}'** - **{g}** (Crucial Save)")
                    elif "foul" in chosen_com.lower():
                        scoresheet_events.append(f"🟨 **{current_minute}'** - **{d}** (Yellow Card)")
                
                event_text = "\n".join(events) if events else "🏁 *Final whistle blown by the referee!*"
                scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"
                time_label = "⏱️ **45' HALF TIME**" if current_minute == 45 else (f"⏱️ **90' FULL TIME**" if current_minute == 90 else f"⏱️ **{current_minute}' Min**")
                
                stats_mini = f"📊 Possession: `{possession_a}%` ⬝ `{possession_b}%` | Shots: `{current_score_a + random.randint(1,3)}` ⬝ `{current_score_b + random.randint(1,3)}`"
                
                if current_minute < 90:
                    await interaction.edit_original_response(
                        content=f"🏟️ **LIVE DIVISION RIVALS MATCH**\n\n{scoreboard}\n{time_label} • {stats_mini}\n\n{event_text}",
                        view=None
                    )
                    await asyncio.sleep(7.5)

            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, goals_b, goals_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, goals_a, goals_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0]["goals"] * 2 + x[0]["rating"]))
            motm_str = f"⭐ **{motm_entry['name']}** `({motm_entry['rating']} Rating)` — *{motm_team}*"

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
                bonus_a_str = "💰 **+10,000,000 Coins**\n🎫 **+1x Draft Voucher**"
                bonus_b_str = ""
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-8,000 Fans**"
                bonus_a_str = ""
                bonus_b_str = "💰 **+10,000,000 Coins**\n🎫 **+1x Draft Voucher**"

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Match Score Sheet & Key Events
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
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
                    icon = "🧤" if r["pos"] == "GK" else ("🛡️" if r["pos"] in ['CB', 'LB', 'RB', 'LWB', 'RWB'] else ("⚡" if r["pos"] in ['CAM', 'CM', 'CDM', 'LM', 'RM'] else "🔥"))
                    star = " ⭐" if r["name"] == motm_entry["name"] else ""
                    goal_badge = f" {'⚽' * r['goals']}" if r['goals'] > 0 else ""
                    lines.append(f"{icon} `[{r['pos']:<3}]` **{r['name'][:14]}** `{r['rating']}`{star}{goal_badge}")
                return "\n".join(lines)

            embed.add_field(name=f"👥 {player_a.display_name} XI", value=format_full_ratings(ratings_a), inline=True)
            embed.add_field(name=f"👥 {player_b.display_name} XI", value=format_full_ratings(ratings_b), inline=True)

            # 5. Fans & Rewards
            embed.add_field(
                name="📈 Fans & Rewards",
                value=fan_change_str + ("\n" + bonus_a_str if bonus_a_str else "") + ("\n" + bonus_b_str if bonus_b_str else ""),
                inline=False
            )
            embed.set_footer(text="DestiFC Match Engine • Stats recorded to /club_stats & /player_stats")
            
            # INSTANT SCOREBOARD PRESENTATION (0 delay)
            await interaction.edit_original_response(content=None, embed=embed, view=None)

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

                    win_coins = gp_cfg.get('match_win_coins', 25_000_000)
                    draw_coins = gp_cfg.get('match_draw_coins', 10_000_000)
                    loss_coins = gp_cfg.get('match_loss_coins', 5_000_000)
                    win_fans = gp_cfg.get('match_win_fans', 25)
                    draw_fans = gp_cfg.get('match_draw_fans', 0)
                    loss_fans = gp_cfg.get('match_loss_fans', -15)
                    win_xp = int(gp_cfg.get('match_win_xp', 75))

                    if winner is None:
                        await database.add_fans(player_a.id, draw_fans)
                        await database.add_fans(player_b.id, draw_fans)
                        await database.add_coins(player_a.id, draw_coins)
                        await database.add_coins(player_b.id, draw_coins)
                    elif winner == player_a:
                        await database.add_fans(player_a.id, win_fans)
                        await database.add_fans(player_b.id, loss_fans)
                        await database.add_coins(player_a.id, win_coins)
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
                        await database.add_coins(player_b.id, win_coins)
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
