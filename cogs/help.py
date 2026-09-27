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
        
        embed.set_thumbnail(url="https://i.imgur.com/example.png") # We will skip thumbnail or use a football emoji
        
        embed.add_field(name="📦 Packs & Economy", value="""
`> /quests` - View ways to earn Draft Vouchers
`> /quest_daily` - Claim your free daily Vouchers
`> /quest_skill_game` - Play a minigame for Vouchers
`> /draft` - Spend Vouchers to open Anniversary Packs! (Pity Timer at 70 packs guarantees a 120+ OVR)
`> /exchange` - Trade 25 unwanted cards for a Guaranteed 120+ Walkout!
`> /balance` - Check your Vouchers and Coins
        """, inline=False)
        
        embed.add_field(name="🛡️ Squad Building", value="""
`> /inventory` - View all players you own
`> /squad formation` - Change your team's tactical formation
`> /squad set` - Equip a player from your inventory into a position
`> /squad view` - Generate a visual image of your Starting 11!
        """, inline=False)
        
        embed.add_field(name="🏆 Matches & Ranked", value="""
`> /play <user>` - Challenge a friend to a 45-second Live H2H Match!
`> /leaderboard` - View the Global Division Rivals Fan leaderboard
`> /player <name>` - Search the FIFARenderZ database
        """, inline=False)
        
        embed.set_footer(text="Developed for FC Mobile Fans | DestiFC")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
