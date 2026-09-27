import discord
from discord.ext import commands
from discord import app_commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Learn how to play DestiFC!")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚽ Welcome to DestiFC!",
            description="The ultimate FC Mobile Discord Bot! Build your dream squad, open massive packs, and dominate Division Rivals.",
            color=0x1E90FF
        )
        
        embed.add_field(name="📦 Packs & Drafts", value="""
`> /draft` - Open one of the 3 active Draft Packs (rotates every 12 hours!)
`> /draft_info` - See which players are featured in each draft
`> /exchange` - Trade 25 unwanted cards for a Guaranteed 120+ Walkout!
`> /quests` - View ways to earn Draft Vouchers
`> /quest_daily` - Claim your free daily Vouchers
`> /quest_skill_game` - Play a minigame for Vouchers
`> /balance` - Check your Vouchers and Coins
        """, inline=False)
        
        embed.add_field(name="🛡️ Squad Building", value="""
`> /squad autobuild` - ⚡ Auto-fill your squad with your best players!
`> /squad set` - Manually equip a player into a position
`> /squad formation` - Change your team's tactical formation
`> /squad view` - Generate a visual image of your Starting 11!
`> /inventory` - View all players you own
        """, inline=False)
        
        embed.add_field(name="🏆 Matches & Ranked", value="""
`> /play <user>` - Challenge a friend to a 45-second Live H2H Match!
`> /leaderboard` - View the Global Division Rivals Fan leaderboard
`> /player <name>` - Search the FIFARenderZ database
        """, inline=False)
        
        embed.add_field(name="💬 Community & Support", value="""
Join the official DestiFC Support Server for updates, pack flex, giveaways, and reporting issues:
🔗 [Join DestiFC Support Server](https://discord.gg/wSMWDyscQY)
        """, inline=False)
        
        embed.set_footer(text="Developed for FC Mobile Fans | Support: https://discord.gg/wSMWDyscQY")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
