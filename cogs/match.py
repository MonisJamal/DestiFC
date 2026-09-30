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

    async def on_timeout(self):
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
                
            # Extract players by position for realistic commentary
            def categorize_players(squad):
                atk, mid, defn, gk = [], [], [], []
                all_players = []
                for pos_raw, p in squad.get('players', {}).items():
                    if not p: continue
                    name = p.get('name') or p.get('player_name', 'Player')
                    all_players.append(name)
                    
                    # Strip digits (ST1 -> ST, CAM2 -> CAM, CB3 -> CB)
                    pos = ''.join([c for c in pos_raw if not c.isdigit()]).strip().upper()
                    
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
                
                # Fallbacks: Always use real squad players instead of generic placeholders
                if not atk: atk = mid if mid else (all_players if all_players else ["Star Player"])
                if not mid: mid = atk if atk else (all_players if all_players else ["Midfielder"])
                if not defn: defn = mid if mid else (all_players if all_players else ["Defender"])
                if not gk: gk = [all_players[-1]] if all_players else ["Goalkeeper"]
                return atk, mid, defn, gk
                
            atk_a, mid_a, def_a, gk_a = categorize_players(squad_a)
            atk_b, mid_b, def_b, gk_b = categorize_players(squad_b)
            
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
            player_scores = {p: 0 for p in (atk_a + mid_a + def_a + gk_a + atk_b + mid_b + def_b + gk_b)}

            current_score_a = 0
            current_score_b = 0

            # Pre-calculate MOTM early to kick off background AI analysis concurrently with the live ticks
            is_a_win = (winner == player_a)
            is_b_win = (winner == player_b)
            is_draw = (winner is None)

            def calc_team_ratings(squad, is_winning_team, is_draw_match):
                ratings = []
                for pos, p in squad.get("players", {}).items():
                    if not p: continue
                    p_name = p.get("name", "Player")
                    goals = player_scores.get(p_name, 0)
                    
                    base = 7.0 + random.uniform(-0.4, 0.4)
                    if is_winning_team: base += 0.8
                    elif is_draw_match: base += 0.3
                    else: base -= 0.4
                    
                    base += goals * 1.4
                    if pos in ['GK', 'CB', 'LB', 'RB'] and (goals_b == 0 if is_winning_team else goals_a == 0):
                        base += 0.6
                        
                    rating = round(min(10.0, max(5.5, base)), 1)
                    ratings.append({"name": p_name, "pos": pos, "rating": rating, "goals": goals})
                ratings.sort(key=lambda x: (x["goals"], x["rating"]), reverse=True)
                return ratings

            # Temporary pre-calculation of player scores for goals
            for g in all_goals:
                player_scores[g[2]] = player_scores.get(g[2], 0) + 1

            ratings_a_est = calc_team_ratings(squad_a, is_a_win, is_draw)
            ratings_b_est = calc_team_ratings(squad_b, is_b_win, is_draw)
            all_rated = [(r, player_a.display_name) for r in ratings_a_est] + [(r, player_b.display_name) for r in ratings_b_est]
            motm_entry, motm_team = max(all_rated, key=lambda x: (x[0]["goals"], x[0]["rating"]))

            # Reset player_scores for the live simulation step
            player_scores = {p: 0 for p in (atk_a + mid_a + def_a + gk_a + atk_b + mid_b + def_b + gk_b)}

            # Kick off async AI Pundit analysis in the background to consume tokens from http://localhost:20128/v1
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

            # Fast 6-tick match simulation (~27-28 seconds total)
            # Ticks at: 15', 30', 45' (HT), 60', 75', 90' (FT)
            ticks = [15, 30, 45, 60, 75, 90]
            
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
                    else:
                        t_atk, t_mid, t_def, t_gk = atk_b, mid_b, def_a, gk_a
                        
                    a = random.choice(t_atk)
                    m = random.choice(t_mid)
                    d = random.choice(t_def)
                    g = random.choice(t_gk)
                    
                    commentary_pool = [
                        f"⚡ Fluid tiki-taka movement in midfield orchestrated by **{m}**!",
                        f"🧤 Tremendous diving save by **{g}** denying a curled effort from **{a}**!",
                        f"🛡️ Rock-solid sliding interception from **{d}** stopping the counter-attack.",
                        f"🎯 **{m}** whips a cross into the box, but **{d}** clears with authority.",
                        f"🚀 Long-range screamer from **{a}**... rattles off the crossbar!",
                        f"🟨 Tactical foul by **{d}** to break up the fast break."
                    ]
                    chosen_com = random.choice(commentary_pool)
                    events.append(f"🎙️ *{chosen_com}*")
                    
                    # Add key defensive save to score sheet if triggered
                    if "save" in chosen_com.lower():
                        scoresheet_events.append(f"🧤 **{current_minute}'** - **{g}** (Crucial Save)")
                    elif "foul" in chosen_com.lower():
                        scoresheet_events.append(f"🟨 **{current_minute}'** - **{d}** (Yellow Card)")
                
                event_text = "\n".join(events)
                scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"
                time_label = "⏱️ **45' HALF TIME**" if current_minute == 45 else f"⏱️ **{current_minute}' Min**"
                
                await interaction.edit_original_response(content=f"🏟️ **LIVE MATCH IN PROGRESS**\n\n{scoreboard}\n{time_label}\n\n{event_text}", view=None)
                
                if current_minute < 90:
                    await asyncio.sleep(4.5)

            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_team_ratings(squad_a, is_a_win, is_draw)
            ratings_b = calc_team_ratings(squad_b, is_b_win, is_draw)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0]["goals"], x[0]["rating"]))
            motm_str = f"⭐ **{motm_entry['name']}** ({motm_entry['rating']} Rating) — *{motm_team}*"

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

            # Await background AI pundit analysis (with a fast 2-second timeout window if not done)
            ai_pundit_text = None
            try:
                ai_pundit_text = await asyncio.wait_for(ai_analysis_task, timeout=2.5)
            except Exception:
                ai_pundit_text = None

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Score Sheet Timeline Field
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
            embed.add_field(name="📋 Match Score Sheet", value=sheet_text, inline=False)
            
            # 2. Man of the Match
            embed.add_field(name="🎖️ Man of the Match", value=motm_str, inline=False)
            
            # 3. AI Pundit Match Analysis (Powered by Local AI tokens)
            if ai_pundit_text:
                embed.add_field(name="🎙️ AI Pundit Tactical Analysis", value=f"*{ai_pundit_text}*", inline=False)
            
            # 4. Top Player Ratings
            def format_ratings(r_list):
                lines = []
                for r in r_list[:4]:  # Top 4 performers
                    icon = "⭐ " if r["name"] == motm_entry["name"] else ("⚽ " if r["goals"] > 0 else "• ")
                    lines.append(f"{icon}**{r['name']}** `{r['rating']}`")
                return "\n".join(lines)

            embed.add_field(name=f"📊 {player_a.display_name} Ratings", value=format_ratings(ratings_a), inline=True)
            embed.add_field(name=f"📊 {player_b.display_name} Ratings", value=format_ratings(ratings_b), inline=True)
            
            # 5. Fans & Rewards
            embed.add_field(name="📈 Fans & Rewards", value=fan_change_str + ("\n" + bonus_a_str if bonus_a_str else "") + ("\n" + bonus_b_str if bonus_b_str else ""), inline=False)
            
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
