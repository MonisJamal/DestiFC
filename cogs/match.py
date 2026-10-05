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

class MatchMomentView(discord.ui.View):
    def __init__(self, attacker_member: discord.Member, defender_member: discord.Member, minute: int, atk_player: dict, def_player: dict, scenario_desc: str):
        super().__init__(timeout=8)
        self.attacker_member = attacker_member
        self.defender_member = defender_member
        self.minute = minute
        self.atk_player = atk_player
        self.def_player = def_player
        self.scenario_desc = scenario_desc
        self.attacker_action = None
        self.defender_action = None

    # Row 0: Primary Attacker Moves
    @discord.ui.button(label="🎯 Pass", style=discord.ButtonStyle.primary, row=0, custom_id="btn_pass")
    async def btn_pass(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "pass", "🎯 Through Pass")

    @discord.ui.button(label="⚡ Dribble", style=discord.ButtonStyle.success, row=0, custom_id="btn_dribble")
    async def btn_dribble(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "dribble", "⚡ Skill Dribble")

    @discord.ui.button(label="🚀 Power Shot", style=discord.ButtonStyle.danger, row=0, custom_id="btn_shoot")
    async def btn_shoot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "shoot", "🚀 Power Shot")

    @discord.ui.button(label="💫 Finesse Curl", style=discord.ButtonStyle.primary, row=0, custom_id="btn_finesse")
    async def btn_finesse(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "finesse", "💫 Finesse Curl")

    @discord.ui.button(label="🪄 Chip Shot", style=discord.ButtonStyle.secondary, row=0, custom_id="btn_chip")
    async def btn_chip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "chip", "🪄 Chip Shot")

    # Row 1: Primary Defender Counter-Moves
    @discord.ui.button(label="🛡️ Cut Pass", style=discord.ButtonStyle.primary, row=1, custom_id="btn_intercept")
    async def btn_intercept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "intercept", "🛡️ Cut Pass Lane")

    @discord.ui.button(label="⚔️ Crunch Tackle", style=discord.ButtonStyle.danger, row=1, custom_id="btn_tackle")
    async def btn_tackle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "tackle", "⚔️ Crunch Tackle")

    @discord.ui.button(label="🧤 Rush GK", style=discord.ButtonStyle.danger, row=1, custom_id="btn_save")
    async def btn_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "save", "🧤 Rush GK")

    @discord.ui.button(label="🧱 Jockey Block", style=discord.ButtonStyle.success, row=1, custom_id="btn_jockey")
    async def btn_jockey(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "jockey", "🧱 Jockey Block")

    @discord.ui.button(label="🚩 Offside Trap", style=discord.ButtonStyle.secondary, row=1, custom_id="btn_trap")
    async def btn_trap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_click(interaction, "trap", "🚩 Offside Trap")

    async def _handle_click(self, interaction: discord.Interaction, action_key: str, action_label: str):
        uid = interaction.user.id
        atk_keys = ["pass", "dribble", "shoot", "finesse", "chip"]
        def_keys = ["intercept", "tackle", "save", "jockey", "trap"]
        if uid == self.attacker_member.id:
            if action_key not in atk_keys:
                return await interaction.response.send_message("❌ You are **Attacking**! Use the top row buttons (`Pass`, `Dribble`, `Power Shot`, `Finesse`, `Chip`).", ephemeral=True)
            self.attacker_action = action_key
            await interaction.response.send_message(f"✅ Locked in: **{action_label}**! Waiting for defending manager...", ephemeral=True)
        elif uid == self.defender_member.id:
            if action_key not in def_keys:
                return await interaction.response.send_message("❌ You are **Defending**! Use the bottom row buttons (`Cut Pass`, `Tackle`, `Rush GK`, `Jockey`, `Trap`).", ephemeral=True)
            self.defender_action = action_key
            await interaction.response.send_message(f"✅ Locked in: **{action_label}**! Counter-action ready...", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You are a spectator in this match!", ephemeral=True)

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

            # Interactive H2H match moments (5 high-stakes moments across 90 minutes)
            moments_minutes = [18, 38, 55, 74, 88]
            
            all_goals = []
            current_score_a = 0
            current_score_b = 0
            scoresheet_events = []
            player_scores = {p['name']: 0 for p in (starters_a + starters_b)}
            shots_total_a, shots_on_target_a, saves_a = 0, 0, 0
            shots_total_b, shots_on_target_b, saves_b = 0, 0, 0
            yellows_a, yellows_b = 0, 0
            fouls_a, fouls_b = 0, 0

            # Match moments loop
            for m_idx, minute in enumerate(moments_minutes):
                # 1. Determine attacking team based on midfield battle + momentum
                mid_diff = (s_a["mid_p"] - s_b["mid_p"])
                prob_a_attack = max(0.25, min(0.75, 0.50 + (mid_diff * 0.02) + random.uniform(-0.1, 0.1)))
                is_a_attack = (random.random() < prob_a_attack)

                if is_a_attack:
                    att_member, def_member = player_a, player_b
                    att_starters, def_starters = starters_a, starters_b
                    att_atks, def_defs = s_a["atk"] or starters_a, s_b["defn"] or starters_b
                    def_gks = s_b["gk"] or [{"name": "Goalkeeper", "ovr": 100}]
                    att_team_name, def_team_name = player_a.display_name, player_b.display_name
                else:
                    att_member, def_member = player_b, player_a
                    att_starters, def_starters = starters_b, starters_a
                    att_atks, def_defs = s_b["atk"] or starters_b, s_a["defn"] or starters_a
                    def_gks = s_a["gk"] or [{"name": "Goalkeeper", "ovr": 100}]
                    att_team_name, def_team_name = player_b.display_name, player_a.display_name

                # Pick key actor cards
                active_atk = random.choice(att_atks)
                active_def = random.choice(def_defs)
                active_gk = def_gks[0]

                # Scenario flavor
                scenarios = [
                    f"⚡ **{active_atk['name']}** ({active_atk['ovr']} OVR) bursts into the final third on a rapid counter-attack!",
                    f"🎯 **{active_atk['name']}** cuts inside across the edge of the penalty box against **{active_def['name']}** ({active_def['ovr']} OVR)!",
                    f"🔥 High-pressing turnover! **{active_atk['name']}** pounces on a loose ball in the danger zone!",
                    f"🚀 Delicate chipped through-ball leaves **{active_atk['name']}** bearing down on the defense!",
                    f"⚡ 1-on-1 duel in the box! **{active_atk['name']}** isolates **{active_def['name']}**!"
                ]
                scenario_text = scenarios[m_idx % len(scenarios)]

                scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"
                time_label = f"⏱️ **{minute}' MINUTE — KEY MATCH MOMENT!**"

                view = MatchMomentView(att_member, def_member, minute, active_atk, active_def, scenario_text)

                prompt_content = (
                    f"🏟️ **LIVE DIVISION RIVALS MATCH**\n\n"
                    f"{scoreboard}\n{time_label}\n\n"
                    f"🎙️ *{scenario_text}*\n\n"
                    f"⚽ **{att_team_name} (Attacker)**: `🎯 Pass` | `⚡ Dribble` | `🚀 Power Shot` | `💫 Finesse` | `🪄 Chip`\n"
                    f"🛡️ **{def_team_name} (Defender)**: `🛡️ Cut Pass` | `⚔️ Tackle` | `🧤 Rush GK` | `🧱 Jockey` | `🚩 Offside Trap`\n"
                    f"*(Quick 7s to lock in your play!)*"
                )

                await interaction.edit_original_response(content=prompt_content, view=view)
                await asyncio.sleep(7.0)

                # Default fallback actions if not selected
                atk_act = view.attacker_action or random.choice(["pass", "dribble", "shoot", "finesse", "chip"])
                def_act = view.defender_action or random.choice(["intercept", "tackle", "save", "jockey", "trap"])

                # Resolve circumstance outcome matrix
                ovr_delta = active_atk['ovr'] - active_def['ovr']
                gk_delta = active_atk['ovr'] - active_gk['ovr']
                success_chance = 0.50 + (ovr_delta * 0.015)

                is_goal = False
                is_foul = False
                is_offside = False
                outcome_text = ""

                # Tactical rock-paper-scissors matchup resolution:
                if atk_act == "pass":
                    if def_act == "intercept":
                        success_chance -= 0.40
                    elif def_act == "trap":
                        if random.random() < 0.50:
                            is_offside = True
                        else:
                            success_chance += 0.35  # Trap sprung open!
                    elif def_act in ["tackle", "save", "jockey"]:
                        success_chance += 0.25

                elif atk_act == "dribble":
                    if def_act == "jockey":
                        success_chance -= 0.35  # Disciplined defending halts dribble
                    elif def_act == "intercept":
                        success_chance += 0.30  # Defender guessing pass leaves lane open
                    elif def_act == "tackle":
                        if random.random() < 0.32:
                            is_foul = True
                        success_chance += 0.15
                    elif def_act in ["save", "trap"]:
                        success_chance += 0.25

                elif atk_act == "shoot":
                    success_chance = 0.46 + (gk_delta * 0.02)
                    if def_act == "save":
                        success_chance -= 0.25
                    elif def_act == "jockey":
                        success_chance -= 0.20  # Center-back blocks shooting angle
                    elif def_act in ["tackle", "intercept", "trap"]:
                        success_chance += 0.20

                elif atk_act == "finesse":
                    success_chance = 0.48 + (gk_delta * 0.018)
                    if def_act == "save":
                        # Finesse curls around a stationary or rushing keeper
                        success_chance += 0.10
                    elif def_act == "jockey":
                        success_chance -= 0.30  # Jockeying defender closes the bend angle
                    elif def_act in ["tackle", "intercept"]:
                        success_chance += 0.15

                elif atk_act == "chip":
                    if def_act == "save":
                        # Perfect counter to keeper rushing off their line!
                        success_chance = 0.85
                    elif def_act in ["jockey", "trap"]:
                        success_chance = 0.25  # Defender tracks back or keeper was on goal line
                    else:
                        success_chance = 0.45 + (gk_delta * 0.015)

                success_chance = max(0.10, min(0.90, success_chance))

                if is_a_attack:
                    shots_total_a += 1
                else:
                    shots_total_b += 1

                if is_offside:
                    outcome_text = f"🚩 **OFFSIDE TRAP SPRUNG!** {def_team_name}'s backline steps up in sync, catching **{active_atk['name']}** straying beyond the last defender!"
                    scoresheet_events.append(f"🚩 **{minute}'** - **{active_atk['name']}** (Offside Flag Raised)")
                elif is_foul:
                    if is_a_attack:
                        fouls_b += 1
                        yellows_b += 1
                    else:
                        fouls_a += 1
                        yellows_a += 1
                    outcome_text = f"🟨 **CLATTERED!** {active_def['name']} dives in with a reckless crunch tackle taking down **{active_atk['name']}**! Yellow card shown!"
                    scoresheet_events.append(f"🟨 **{minute}'** - **{active_def['name']}** (Foul on {active_atk['name']})")
                elif random.random() < success_chance:
                    # Attack succeeded!
                    if is_a_attack:
                        shots_on_target_a += 1
                    else:
                        shots_on_target_b += 1

                    is_goal = True
                    scorer_name = active_atk['name']
                    player_scores[scorer_name] = player_scores.get(scorer_name, 0) + 1
                    all_goals.append((att_member, minute, scorer_name))

                    if is_a_attack:
                        current_score_a += 1
                    else:
                        current_score_b += 1

                    if atk_act == "pass":
                        outcome_text = f"🎯 **SURGICAL PASS!** {active_atk['name']} threads an inch-perfect through ball, tapping it past {active_def['name']} into the empty net! ⚽🔥"
                    elif atk_act == "dribble":
                        outcome_text = f"⚡ **SAMBA FLAIR!** {active_atk['name']} hits an insane roulette skill move, sits {active_def['name']} on the turf, and tucks it home! ⚽🔥"
                    elif atk_act == "finesse":
                        outcome_text = f"💫 **PURE ARTISTRY!** {active_atk['name']} curls a delightful finesse strike right into the postage stamp top corner! Unstoppable! ⚽🔥"
                    elif atk_act == "chip":
                        outcome_text = f"🪄 **AUDACIOUS CHIP!** Seeing {active_gk['name']} off their line, {active_atk['name']} dinks a glorious rainbow chip into the net! World class! ⚽🔥"
                    else:
                        outcome_text = f"🚀 **THUNDERBOLT!** {active_atk['name']} unleashes an absolute rocket that almost rips through the netting! Top bins! ⚽🔥"

                    scoresheet_events.append(f"⚽ **{minute}'** - **{scorer_name}** ({att_team_name})")
                else:
                    # Defense stood firm!
                    if is_a_attack:
                        saves_b += 1
                    else:
                        saves_a += 1

                    if def_act == "intercept":
                        outcome_text = f"🛡️ **READ LIKE A BOOK!** {active_def['name']} cuts the passing lane with a masterclass anticipation!"
                    elif def_act == "jockey":
                        outcome_text = f"🧱 **STANDS TALL!** {active_def['name']} holds their ground with patient jockeying, blocking {active_atk['name']}'s effort!"
                    elif def_act == "trap":
                        outcome_text = f"🛡️ **DEFENSIVE COMPACTNESS!** The backline swarms {active_atk['name']}, neutralizing the attacking wave!"
                    elif def_act == "tackle":
                        outcome_text = f"⚔️ **TIMED TO PERFECTION!** {active_def['name']} executes a picture-perfect sliding challenge, hooking the ball away cleanly!"
                    else:
                        outcome_text = f"🧤 **REFLEX MASTERCLASS!** {active_gk['name']} reacts with feline reflexes to deny {active_atk['name']} from point-blank range!"
                        scoresheet_events.append(f"🧤 **{minute}'** - **{active_gk['name']}** (Crucial Save)")

                action_summary = f"*(Attacker chose `{atk_act.upper()}` vs Defender `{def_act.upper()}`)*"
                interim_scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"

                await interaction.edit_original_response(
                    content=(
                        f"🏟️ **LIVE DIVISION RIVALS MATCH**\n\n"
                        f"{interim_scoreboard}\n⏱️ **{minute}' Outcome**\n\n"
                        f"{outcome_text}\n{action_summary}\n\n"
                        f"⏳ *Match continuing...*"
                    ),
                    view=None
                )
                await asyncio.sleep(3.5)

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
            xg_a = round(current_score_a * 0.65 + (shots_on_target_a * 0.18) + random.uniform(0.1, 0.25), 2)
            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, current_score_b, current_score_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, current_score_a, current_score_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0]["goals"] * 2 + x[0]["rating"]))
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
                bonus_a_str = "💰 **+25,000,000 Coins**\n🎫 **+1x Draft Voucher**"
                bonus_b_str = ""
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-2,000 Fans**"
                bonus_a_str = ""
                bonus_b_str = "💰 **+25,000,000 Coins**\n🎫 **+1x Draft Voucher**"

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

                    win_coins = int(gp_cfg.get('match_win_coins', 25_000_000))
                    draw_coins = int(gp_cfg.get('match_draw_coins', 10_000_000))
                    loss_coins = int(gp_cfg.get('match_loss_coins', 5_000_000))
                    win_fans = int(gp_cfg.get('match_win_fans', 10_000))
                    draw_fans = int(gp_cfg.get('match_draw_fans', 2_000))
                    loss_fans = int(gp_cfg.get('match_loss_fans', -2_000))
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
