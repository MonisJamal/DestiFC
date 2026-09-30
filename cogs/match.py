import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

import database
import ai_engine

# Global tracking set to ensure only 1 active H2H match / challenge at a time per user
ACTIVE_MATCH_USERS = set()

class MatchRequestView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, cog, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.cog = cog
        self.squad_a = squad_a
        self.squad_b = squad_b
        self.fans_a = fans_a
        self.fans_b = fans_b
        self.ovr_a = ovr_a
        self.ovr_b = ovr_b
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
                await self.message.edit(content=f"⏱️ **Match Challenge Expired!** {self.opponent.display_name} did not respond within 60 seconds.", view=self)
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

    def get_division(self, fans: int):
        if fans < 10000: return "Amateur III"
        elif fans < 20000: return "Amateur II"
        elif fans < 30000: return "Amateur I"
        elif fans < 50000: return "Pro III"
        elif fans < 70000: return "Pro II"
        elif fans < 100000: return "Pro I"
        elif fans < 200000: return "World Class III"
        elif fans < 300000: return "World Class II"
        elif fans < 400000: return "World Class I"
        elif fans < 600000: return "Legendary III"
        elif fans < 800000: return "Legendary II"
        elif fans < 1000000: return "Legendary I"
        else: return "FC Champion 🏆"

    def get_division_index(self, fans: int):
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
        
        view = MatchRequestView(interaction.user, opponent, self, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b)
        
        msg = await interaction.followup.send(
            f"⚔️ **DIVISION RIVALS CHALLENGE!** ⚔️\n\n**{interaction.user.display_name} ({ovr_a})** [{self.get_division(fans_a)}]\n🆚\n**{opponent.display_name} ({ovr_b})** [{self.get_division(fans_b)}]\n\nHey {opponent.mention}, you have been challenged! Do you accept?",
            view=view
        )
        view.message = msg

    async def simulate_live_match(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b):
        try:
            # Determine the winner and goals first
            diff = ovr_a - ovr_b
            win_chance_a = 50 + (diff * 2) 
            win_chance_a = max(10, min(90, win_chance_a)) 
            
            roll = random.uniform(0, 100)
            
            if abs(roll - win_chance_a) < 5:
                winner = None
                goals_a = random.randint(0, 3)
                goals_b = goals_a
            elif roll <= win_chance_a:
                winner = player_a
                goals_a = random.randint(1, 4)
                goals_b = random.randint(0, goals_a - 1)
            else:
                winner = player_b
                goals_b = random.randint(1, 4)
                goals_a = random.randint(0, goals_b - 1)
                
            # Extract players by position for realistic commentary and full squad ratings
            def categorize_players(squad):
                atk, mid, defn, gk = [], [], [], []
                all_starters = []
                for pos_raw, p in squad.get('players', {}).items():
                    if not p: continue
                    name = p.get('name') or p.get('player_name', 'Player')
                    pos = ''.join([c for c in pos_raw if not c.isdigit()]).strip().upper()
                    entry = {"name": name, "pos": pos, "raw_pos": pos_raw, "ovr": p.get('ovr', 100)}
                    all_starters.append(entry)
                    
                    if pos in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF']:
                        atk.append(name)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        mid.append(name)
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        defn.append(name)
                    elif pos == 'GK':
                        gk.append(name)
                    else:
                        mid.append(name)
                
                # Fallbacks if squad has unconventional positions
                names_all = [p['name'] for p in all_starters]
                if not atk: atk = mid if mid else (names_all if names_all else ["Star Striker"])
                if not mid: mid = atk if atk else (names_all if names_all else ["Playmaker"])
                if not defn: defn = mid if mid else (names_all if names_all else ["Defender"])
                if not gk: gk = [names_all[-1]] if names_all else ["Goalkeeper"]
                return atk, mid, defn, gk, all_starters
                
            atk_a, mid_a, def_a, gk_a, starters_a = categorize_players(squad_a)
            atk_b, mid_b, def_b, gk_b, starters_b = categorize_players(squad_b)
            
            # Distribute goals across 90 minutes
            all_goals = []
            for _ in range(goals_a): 
                scorer = random.choice(atk_a + mid_a)
                all_goals.append((player_a, random.randint(8, 88), scorer))
            for _ in range(goals_b): 
                scorer = random.choice(atk_b + mid_b)
                all_goals.append((player_b, random.randint(8, 88), scorer))
            all_goals.sort(key=lambda x: x[1])  # Sort by minute

            scoresheet_events = []
            player_scores = {p['name']: 0 for p in (starters_a + starters_b)}

            current_score_a = 0
            current_score_b = 0

            is_a_win = (winner == player_a)
            is_b_win = (winner == player_b)
            is_draw = (winner is None)

            # Generate realistic match statistics
            possession_a = int(50 + (ovr_a - ovr_b) * 1.5 + random.randint(-4, 4))
            possession_a = max(35, min(65, possession_a))
            possession_b = 100 - possession_a

            shots_on_target_a = goals_a + random.randint(2, 6)
            shots_total_a = shots_on_target_a + random.randint(3, 7)
            shots_on_target_b = goals_b + random.randint(2, 6)
            shots_total_b = shots_on_target_b + random.randint(3, 7)

            saves_a = max(0, shots_on_target_b - goals_b)
            saves_b = max(0, shots_on_target_a - goals_a)

            corners_a = random.randint(2, 8)
            corners_b = random.randint(2, 8)
            fouls_a = random.randint(2, 7)
            fouls_b = random.randint(2, 7)
            yellows_a = random.randint(0, 2)
            yellows_b = random.randint(0, 2)
            pass_acc_a = random.randint(82, 93)
            pass_acc_b = random.randint(80, 92)
            xg_a = round(goals_a * 0.65 + (shots_on_target_a * 0.18) + random.uniform(0.1, 0.4), 2)
            xg_b = round(goals_b * 0.65 + (shots_on_target_b * 0.18) + random.uniform(0.1, 0.4), 2)

            def calc_full_team_ratings(starters, is_winning_team, is_draw_match, goals_conceded, goals_scored):
                ratings = []
                for s in starters:
                    p_name = s['name']
                    pos = s['pos']
                    goals = player_scores.get(p_name, 0)
                    
                    base = 6.8 + random.uniform(-0.3, 0.4)
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

            # Temporary pre-calculation of player scores for goals
            for g in all_goals:
                player_scores[g[2]] = player_scores.get(g[2], 0) + 1

            ratings_a_est = calc_full_team_ratings(starters_a, is_a_win, is_draw, goals_b, goals_a)
            ratings_b_est = calc_full_team_ratings(starters_b, is_b_win, is_draw, goals_a, goals_b)
            all_rated = [(r, player_a.display_name) for r in ratings_a_est] + [(r, player_b.display_name) for r in ratings_b_est]
            motm_entry, motm_team = max(all_rated, key=lambda x: (x[0]["goals"] * 2 + x[0]["rating"]))

            # Reset player_scores for live commentary tracking
            player_scores = {p['name']: 0 for p in (starters_a + starters_b)}

            # Kick off async AI Pundit analysis in background
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

            # Exactly 1-minute match simulation (8 ticks x 7.5s = 60s total)
            # Ticks at: 10', 25', 40', 45' (HT), 60', 75', 85', 90' (FT)
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

                if not events:
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
                        f"⚡ Fluid tiki-taka build-up orchestrated by **{m}** splitting the defensive line!",
                        f"🧤 WORLD-CLASS REFLEXES! **{g}** makes a fingertip diving save to deny a thunderous curled strike from **{a}**!",
                        f"🛡️ Rock-solid sliding interception from **{d}** thwarting a dangerous counter-attack.",
                        f"🎯 **{m}** delivers an inswinging cross into the penalty box, but **{d}** clears with authority.",
                        f"🚀 Long-range screamer from **{a}**... it rattles violently off the crossbar!",
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
                
                event_text = "\n".join(events)
                scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"
                time_label = "⏱️ **45' HALF TIME**" if current_minute == 45 else (f"⏱️ **90' FULL TIME**" if current_minute == 90 else f"⏱️ **{current_minute}' Min**")
                
                stats_mini = f"📊 Possession: `{possession_a}%` ⬝ `{possession_b}%` | Shots: `{current_score_a + random.randint(1,3)}` ⬝ `{current_score_b + random.randint(1,3)}`"
                
                await interaction.edit_original_response(
                    content=f"🏟️ **LIVE DIVISION RIVALS MATCH**\n\n{scoreboard}\n{time_label} • {stats_mini}\n\n{event_text}",
                    view=None
                )
                
                if current_minute < 90:
                    await asyncio.sleep(7.5)

            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, goals_b, goals_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, goals_a, goals_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0]["goals"] * 2 + x[0]["rating"]))
            motm_str = f"⭐ **{motm_entry['name']}** `({motm_entry['rating']} Rating)` — *{motm_team}*"

            # Match Over - Apply Rewards
            color = discord.Color.light_grey()
            user_a = await database.get_user(player_a.id)
            user_b = await database.get_user(player_b.id)
            fans_a_old, fans_b_old = user_a.get('fans', 0), user_b.get('fans', 0)
            div_a_old, div_b_old = user_a.get('highest_div', 0), user_b.get('highest_div', 0)
            
            bonus_a_str = ""
            bonus_b_str = ""

            if winner is None:
                result_text = f"🤝 **IT'S A DRAW!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                await database.add_fans(player_a.id, 2000)
                await database.add_fans(player_b.id, 2000)
                fan_change_str = "Both players gained **+2,000 Fans**"
            elif winner == player_a:
                result_text = f"🏆 **{player_a.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.green()
                await database.add_fans(player_a.id, 10000)
                await database.add_fans(player_b.id, -8000)
                await database.add_coins(player_a.id, 10_000_000)
                await database.add_vouchers(player_a.id, 1)
                try:
                    from cogs.achievements import increment_stat, check_and_award
                    await increment_stat(player_a.id, "matches_won")
                    await check_and_award(player_a.id)
                    from cogs.season import add_season_xp
                    await add_season_xp(player_a.id, 75)
                except Exception: pass
                fan_change_str = f"**{player_a.display_name}** gained **+10,000 Fans**\n**{player_b.display_name}** lost **-8,000 Fans**"
                bonus_a_str = "💰 **+10,000,000 Coins**\n🎫 **+1x Draft Voucher**"
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                await database.add_fans(player_b.id, 10000)
                await database.add_fans(player_a.id, -8000)
                await database.add_coins(player_b.id, 10_000_000)
                await database.add_vouchers(player_b.id, 1)
                try:
                    from cogs.achievements import increment_stat, check_and_award
                    await increment_stat(player_b.id, "matches_won")
                    await check_and_award(player_b.id)
                    from cogs.season import add_season_xp
                    await add_season_xp(player_b.id, 75)
                except Exception: pass
                fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-8,000 Fans**"
                bonus_b_str = "💰 **+10,000,000 Coins**\n🎫 **+1x Draft Voucher**"

            # Record detailed player stats to database for both teams
            try:
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
            except Exception as e:
                print(f"[Match] Error recording player stats: {e}")


            # Check promotions
            def check_promo(old_fans, change, old_highest):
                new_fans = max(0, old_fans + change)
                new_index = self.get_division_index(new_fans)
                vouchers = 0
                if new_index > old_highest:
                    for i in range(old_highest + 1, new_index + 1):
                        vouchers += self.get_div_reward(i)
                    return vouchers, new_index
                return 0, old_highest
                
            promo_v_a, new_div_a = check_promo(fans_a_old, 10000 if winner == player_a else (2000 if winner is None else -8000), div_a_old)
            promo_v_b, new_div_b = check_promo(fans_b_old, 10000 if winner == player_b else (2000 if winner is None else -8000), div_b_old)
            
            if promo_v_a > 0:
                await database.set_highest_div(player_a.id, new_div_a)
                await database.add_vouchers(player_a.id, promo_v_a)
                bonus_a_str += f"\n🏅 **PROMOTION!** +{promo_v_a}x Vouchers!"
            if promo_v_b > 0:
                await database.set_highest_div(player_b.id, new_div_b)
                await database.add_vouchers(player_b.id, promo_v_b)
                bonus_b_str += f"\n🏅 **PROMOTION!** +{promo_v_b}x Vouchers!"

            # Instant timeout check for AI pundit so post-match never hangs
            ai_pundit_text = None
            try:
                ai_pundit_text = await asyncio.wait_for(ai_analysis_task, timeout=1.0)
            except Exception:
                ai_pundit_text = None

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Match Score Sheet & Key Events
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
            embed.add_field(name="📋 Match Events", value=sheet_text, inline=False)
            
            # 2. Detailed Real-Life Team Match Statistics
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
                f"```"
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

            # 5. AI Pundit Match Analysis
            if ai_pundit_text:
                embed.add_field(name="🎙️ AI Pundit Tactical Breakdown", value=f"*{ai_pundit_text}*", inline=False)
            
            # 6. Fans & Rewards
            embed.add_field(
                name="📈 Fans & Rewards",
                value=fan_change_str + ("\n" + bonus_a_str if bonus_a_str else "") + ("\n" + bonus_b_str if bonus_b_str else ""),
                inline=False
            )
            
            await interaction.edit_original_response(content=None, embed=embed, view=None)

        except Exception as e:
            print(f"Error in simulate_live_match: {e}")
        finally:
            # Guarantee players are always freed from the active match set
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
        
        if category == "coins":
            lb = await database.get_coins_leaderboard(10)
            lines = []
            for i, row in enumerate(lb):
                uid = row['user_id']
                coins = row['coins']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{coins:,}** Coins 💰")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="💰 Cash / Coins Global Leaderboard", description=desc, color=discord.Color.gold())
            
        elif category == "vouchers":
            lb = await database.get_vouchers_leaderboard(10)
            lines = []
            for i, row in enumerate(lb):
                uid = row['user_id']
                vouchers = row['vouchers']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{vouchers:,}** Vouchers 🎫")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🎫 Draft Vouchers Global Leaderboard", description=desc, color=discord.Color.blue())
            
        else:
            lb = await database.get_leaderboard(10)
            lines = []
            for i, row in enumerate(lb):
                uid = row['user_id']
                div = self.get_division(row['fans'])
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{row['fans']:,}** Fans `[{div}]`")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🌍 Division Rivals Leaderboard", description=desc, color=discord.Color.purple())

        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

async def setup(bot):
    await bot.add_cog(MatchCog(bot))
