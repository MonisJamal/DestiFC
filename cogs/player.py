import discord
from discord.ext import commands
from discord import app_commands
import io
import json

from renderz_api import search_fifarenderz
from card_generator import generate_card

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="player", description="Search for an FC Mobile player card")
    @app_commands.describe(name="The name of the player")
    async def player(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        
        # 1. Fetch data
        players = search_fifarenderz(name, size=1)
        if not players:
            await interaction.followup.send(f"❌ No player found matching `{name}`.", ephemeral=True)
            return
            
        player_data = players[0]
        
        # 2. Generate card image
        try:
            image = generate_card(player_data)
            
            # Save to BytesIO to send to Discord without writing to disk
            with io.BytesIO() as image_binary:
                image.save(image_binary, 'PNG')
                image_binary.seek(0)
                
                # Create discord File object
                file = discord.File(fp=image_binary, filename='card.png')
                
                # 3. Create embed with some stats
                card_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
                ovr = player_data.get('rating', '?')
                pos = player_data.get('position', '?')
                
                embed = discord.Embed(
                    title=f"{card_name} - {ovr} {pos}",
                    color=discord.Color.gold()
                )
                
                # Extract some stats if they exist
                stats = player_data.get('stats', {})
                if stats:
                    pac = stats.get('pac', '?')
                    sho = stats.get('sho', '?')
                    pas = stats.get('pas', '?')
                    dri = stats.get('dri', '?')
                    def_stat = stats.get('def', '?')
                    phy = stats.get('phy', '?')
                    
                    stat_str = f"🏃 PAC: **{pac}** | 👟 SHO: **{sho}** | 🎯 PAS: **{pas}**\n" \
                               f"🪄 DRI: **{dri}** | 🛡️ DEF: **{def_stat}** | 💪 PHY: **{phy}**"
                    embed.add_field(name="Base Stats", value=stat_str, inline=False)
                
                embed.set_image(url="attachment://card.png")
                
                await interaction.followup.send(embed=embed, file=file)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating card: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PlayerCog(bot))
