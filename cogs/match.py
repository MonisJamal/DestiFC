import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

import database

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

    @app_commands.command(name="play", description="Play a Division Rivals H2H Match!")
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
            await interaction.followup.send(f"❌ {opponent.display_name}'s starting XI is incomplete!")
            return
            
        user_a = await database.get_user(interaction.user.id)
        user_b = await database.get_user(opponent.id)
        fans_a, fans_b = user_a.get('fans', 0), user_b.get('fans', 0)
            
        msg = await interaction.followup.send(f"⚔️ **DIVISION RIVALS MATCH!** ⚔️\n\n**{interaction.user.display_name} ({ovr_a})** [{self.get_division(fans_a)}]\n🆚\n**{opponent.display_name} ({ovr_b})** [{self.get_division(fans_b)}]\n\n*Simulating match... ⚽*")
        
        await asyncio.sleep(3)
        
        # Simple Match Simulation
        diff = ovr_a - ovr_b
        win_chance_a = 50 + (diff * 2) 
        win_chance_a = max(10, min(90, win_chance_a)) 
        
        roll = random.uniform(0, 100)
        
        fan_change_str = ""
        
        if abs(roll - win_chance_a) < 5:
            # Draw
            goals = random.randint(0, 3)
            result_text = f"🤝 **IT'S A DRAW!**\nThe match ended `{goals} - {goals}`."
            color = discord.Color.light_grey()
            
            await database.add_fans(interaction.user.id, 2000)
            await database.add_fans(opponent.id, 2000)
            fan_change_str = f"Both players gained **+2,000 Fans**"
            
        elif roll <= win_chance_a:
            winner, loser = interaction.user, opponent
            score = f"{random.randint(1,4)} - {random.randint(0,2)}"
            result_text = f"🏆 **{winner.display_name} WINS!**\nFinal Score: `{score}`"
            color = discord.Color.green()
            
            await database.add_fans(interaction.user.id, 10000)
            await database.add_fans(opponent.id, -8000)
            fan_change_str = f"**{winner.display_name}** gained **+10,000 Fans**\n**{loser.display_name}** lost **-8,000 Fans**"
            
        else:
            winner, loser = opponent, interaction.user
            score = f"{random.randint(0,2)} - {random.randint(1,4)}"
            result_text = f"🏆 **{winner.display_name} WINS!**\nFinal Score: `{score}`"
            color = discord.Color.red()
            
            await database.add_fans(opponent.id, 10000)
            await database.add_fans(interaction.user.id, -8000)
            fan_change_str = f"**{winner.display_name}** gained **+10,000 Fans**\n**{loser.display_name}** lost **-8,000 Fans**"
            
        embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
        embed.add_field(name="Fans Update", value=fan_change_str, inline=False)
        
        await msg.edit(content=None, embed=embed)

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
