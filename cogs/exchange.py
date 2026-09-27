import discord
from discord.ext import commands
from discord import app_commands
import database
import random
from renderz_api import query_players_by_program, search_fifarenderz
from card_generator import generate_card
import io

class ExchangeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="exchange", description="Exchange lower OVR players for a 120+ OVR Walkout!")
    async def exchange(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        inventory = await database.get_inventory(user_id)
        squad = await database.get_squad(user_id)
        
        # Get list of inv_ids currently in the active squad
        active_inv_ids = []
        for pos, player in squad.get("players", {}).items():
            if player:
                active_inv_ids.append(player["inv_id"])
                
        # Filter available players
        available_players = [p for p in inventory if p["id"] not in active_inv_ids]
        
        # We need 20x (112-116) and 5x (117+) to equal 25 cards total
        tier_1_candidates = sorted([p for p in available_players if 112 <= p["ovr"] <= 116], key=lambda x: x["ovr"])
        tier_2_candidates = sorted([p for p in available_players if p["ovr"] >= 117], key=lambda x: x["ovr"])
        
        if len(tier_1_candidates) < 20 or len(tier_2_candidates) < 5:
            await interaction.followup.send(f"❌ **Exchange Requirements Not Met!**\nTo get a 120+ Walkout, you must exchange **25 Cards** total:\n• 20x Players (112-116 OVR) [You have {len(tier_1_candidates)}]\n• 5x Players (117+ OVR) [You have {len(tier_2_candidates)}]\n*(Note: Players in your active squad cannot be exchanged)*", ephemeral=True)
            return
            
        # Select the cheapest ones to consume
        consumed = tier_1_candidates[:20] + tier_2_candidates[:5]
        consumed_ids = [p["id"] for p in consumed]
        
        await database.remove_players_from_inventory(user_id, consumed_ids)
        
        msg = await interaction.followup.send("🔄 **SUBMITTING EXCHANGE...**\n*Consuming 25 players...*")
        
        import asyncio
        await asyncio.sleep(2)
        
        # 120+ Pack Roll
        roll = random.uniform(0, 100)
        
        if roll <= 10: min_ovr = 122
        elif roll <= 40: min_ovr = 121
        else: min_ovr = 120
            
        tier_name = "WALKOUT 🌟🌟🌟" if min_ovr == 122 else "WALKOUT 🌟🌟" if min_ovr == 121 else "WALKOUT 🌟"
            
        # Get ANY player of that rating
        players = query_players_by_program("", min_rating=min_ovr, max_rating=min_ovr, size=50)
        if not players:
            players = query_players_by_program("PROGRAM_ANN27", min_rating=120, max_rating=122, size=10)
            
        player_data = random.choice(players)
        pos = player_data.get('position', '??')
        
        # Maps for dynamic walkouts based on internal IDs
        from maps import nation_map, club_map
        
        n_id = player_data.get('nation', {}).get('id')
        c_id = player_data.get('club', {}).get('id')
        
        nation_str = nation_map.get(n_id, f"🌍 Nation ({n_id})")
        club_str = club_map.get(c_id, f"🛡️ Club ({c_id})")
        card_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
                
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}")
        await asyncio.sleep(1.5)
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}\n🔥 🏃 **POSITION REVEALED:** `{pos}`")
        await asyncio.sleep(1.5)
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}\n🔥 🏃 **POSITION REVEALED:** `{pos}`\n🔥 🛡️ **CLUB REVEALED:** {club_str}")
        await asyncio.sleep(1.5)
        
        await database.add_player_to_inventory(user_id, player_data)
        
        ovr = player_data.get('rating', '?')
        
        try:
            image = generate_card(player_data)
            with io.BytesIO() as image_binary:
                image.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='card.png')
                
                embed = discord.Embed(
                    title=f"🎉 120+ {tier_name} Pack Opened!",
                    description=f"You completed the exchange and drafted **{card_name} ({ovr})**!",
                    color=discord.Color.gold()
                )
                embed.set_author(name=f"{interaction.user.display_name}'s Exchange", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
                embed.set_image(url="attachment://card.png")
                embed.set_footer(text="13 players consumed. 1 Walkout added to your inventory.")
                
                await msg.delete()
                await interaction.followup.send(embed=embed, file=file)
                
        except Exception as e:
            await msg.delete()
            await interaction.followup.send(f"❌ Pack opened, but failed to generate card image: {e}")

async def setup(bot):
    await bot.add_cog(ExchangeCog(bot))
