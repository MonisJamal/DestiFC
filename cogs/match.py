import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

import database

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

    @discord.ui.button(label="Accept Match", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept!", ephemeral=True)
            return
            
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content=f"⚔️ **Match Accepted!** The players are walking onto the pitch...", view=self)
        
        # Start simulation in background using the button interaction to edit the webhook
        asyncio.create_task(self.cog.simulate_live_match(interaction, self.challenger, self.opponent, self.ovr_a, self.ovr_b, self.squad_a, self.squad_b))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline!", ephemeral=True)
            return
            
        for child in self.children: child.disabled = True
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

    @app_commands.command(name="play", description="Challenge another user to a H2H Division Rivals Match!")
    async def play(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't play against yourself!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        squad_a = await database.get_squad(interaction.user.id)
        squad_b = await database.get_squad(opponent.id)
        
        ovr_a = self.calculate_ovr(squad_a)
        ovr_b = self.calculate_ovr(squad_b)
        
        if ovr_a == 0:
            await interaction.followup.send(f"❌ Your starting XI is incomplete! Use `/squad set` to fill all 11 positions.")
            return
        if ovr_b == 0:
            await interaction.followup.send(f"❌ {opponent.display_name}'s starting XI is incomplete! They must fill all 11 positions.")
            return
            
        user_a = await database.get_user(interaction.user.id)
        user_b = await database.get_user(opponent.id)
        fans_a, fans_b = user_a.get('fans', 0), user_b.get('fans', 0)
        
        view = MatchRequestView(interaction.user, opponent, self, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b)
        
        await interaction.followup.send(
            f"⚔️ **DIVISION RIVALS CHALLENGE!** ⚔️\n\n**{interaction.user.display_name} ({ovr_a})** [{self.get_division(fans_a)}]\n🆚\n**{opponent.display_name} ({ovr_b})** [{self.get_division(fans_b)}]\n\nHey {opponent.mention}, you have been challenged! Do you accept?",
            view=view
        )

    async def simulate_live_match(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b):
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
            for pos, p in squad.get('players', {}).items():
                if not p: continue
                name = p['name']
                if pos in ['ST', 'LW', 'RW', 'CF']: atk.append(name)
                elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']: mid.append(name)
                elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']: defn.append(name)
                elif pos == 'GK': gk.append(name)
            
            # Fallbacks just in case
            if not atk: atk = ["Attacker"]
            if not mid: mid = atk
            if not defn: defn = mid
            if not gk: gk = ["Goalkeeper"]
            return atk, mid, defn, gk
            
        atk_a, mid_a, def_a, gk_a = categorize_players(squad_a)
        atk_b, mid_b, def_b, gk_b = categorize_players(squad_b)
        
        # We need to distribute these goals across 90 virtual minutes.
        # 9 loops * 5 seconds real-time sleep = 45 seconds total match time!
        all_goals = []
        for _ in range(goals_a): all_goals.append((player_a, random.randint(5, 89)))
        for _ in range(goals_b): all_goals.append((player_b, random.randint(5, 89)))
        all_goals.sort(key=lambda x: x[1]) # Sort by minute
        
        current_score_a = 0
        current_score_b = 0
        
        for loop in range(1, 10):
            current_minute = loop * 10
            events = []
            
            # Check for goals in this 10-minute bracket
            for g in all_goals:
                if current_minute - 10 < g[1] <= current_minute:
                    if g[0] == player_a:
                        current_score_a += 1
                        scorer = random.choice(atk_a + mid_a)
                        events.append(f"⚽ **GOAL! A stunning strike by {scorer} puts {player_a.display_name} ahead!** ({g[1]}')")
                    else:
                        current_score_b += 1
                        scorer = random.choice(atk_b + mid_b)
                        events.append(f"⚽ **GOAL! {scorer} finds the back of the net for {player_b.display_name}!** ({g[1]}')")
                        
            if not events:
                # Randomize who has possession for the commentary
                if random.choice([True, False]):
                    t_atk, t_mid, t_def, t_gk = atk_a, mid_a, def_b, gk_b
                else:
                    t_atk, t_mid, t_def, t_gk = atk_b, mid_b, def_a, gk_a
                    
                a = random.choice(t_atk)
                m = random.choice(t_mid)
                d = random.choice(t_def)
                g = random.choice(t_gk)
                
                general_commentary = [
                    f"Great possession play in the midfield controlled by {m}...",
                    f"A dangerous through ball to {a}, but the offside flag goes up!",
                    f"Tough sliding tackle by {d}! The referee says play on.",
                    f"A brilliant cross into the box by {m}, but {a} heads it just wide!",
                    f"{a} drives forward with pace, but {d} intercepts beautifully.",
                    f"A long range rocket from {m}! What a diving save by {g}!",
                    f"Corner kick whipped in towards {a}... cleared out by {d}.",
                    f"Foul given in a dangerous area. {a} takes the free kick... it hits the wall.",
                    f"{a} goes 1-on-1 with the keeper... but {g} makes a crucial block!"
                ]
                events.append(f"🎙️ *{random.choice(general_commentary)}*")
                
            event_text = "\n".join(events)
            
            # Format the live scoreboard
            scoreboard = f"**{player_a.display_name}** `{current_score_a} - {current_score_b}` **{player_b.display_name}**"
            time_str = f"⏱️ **{current_minute}' Min**"
            
            await interaction.edit_original_response(content=f"🏟️ **LIVE MATCH ONGOING**\n\n{scoreboard}\n{time_str}\n\n{event_text}", view=None)
            
            if loop < 9:
                await asyncio.sleep(5)
                
        # Match Over - Apply Rewards
        color = discord.Color.light_grey()
        if winner == None:
            result_text = f"🤝 **IT'S A DRAW!**\nThe match ended `{current_score_a} - {current_score_b}`."
            await database.add_fans(player_a.id, 2000)
            await database.add_fans(player_b.id, 2000)
            fan_change_str = f"Both players gained **+2,000 Fans**"
        elif winner == player_a:
            result_text = f"🏆 **{player_a.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
            color = discord.Color.green()
            await database.add_fans(player_a.id, 10000)
            await database.add_fans(player_b.id, -8000)
            fan_change_str = f"**{player_a.display_name}** gained **+10,000 Fans**\n**{player_b.display_name}** lost **-8,000 Fans**"
        else:
            result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
            color = discord.Color.red()
            await database.add_fans(player_b.id, 10000)
            await database.add_fans(player_a.id, -8000)
            fan_change_str = f"**{player_b.display_name}** gained **+10,000 Fans**\n**{player_a.display_name}** lost **-8,000 Fans**"
            
        embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
        embed.add_field(name="Fans Update", value=fan_change_str, inline=False)
        
        await interaction.edit_original_response(content=None, embed=embed, view=None)

    @app_commands.command(name="leaderboard", description="View the Division Rivals Global Leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        lb = await database.get_leaderboard(10)
        
        desc = ""
        for i, row in enumerate(lb):
            user = self.bot.get_user(row['user_id'])
            name = user.display_name if user else f"Unknown ({row['user_id']})"
            div = self.get_division(row['fans'])
            
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
            desc += f"{medal} **{name}** - {row['fans']:,} Fans [{div}]\n"
            
        if not desc:
            desc = "No ranked players yet!"
            
        embed = discord.Embed(title="🌍 Division Rivals Leaderboard", description=desc, color=discord.Color.purple())
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MatchCog(bot))
