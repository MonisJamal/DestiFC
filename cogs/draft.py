import discord
from discord.ext import commands
from discord import app_commands
import io
import random
import asyncio

import database
from renderz_api import query_players_by_program, search_fifarenderz
from card_generator import generate_card

class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="draft", description="Open active draft packs")
    @app_commands.choices(draft_type=[
        app_commands.Choice(name="3rd Anniversary Draft A", value="ann_a"),
        app_commands.Choice(name="3rd Anniversary Draft B", value="ann_b"),
        app_commands.Choice(name="Stellar Series: Libra Draft", value="stellar")
    ])
    async def draft(self, interaction: discord.Interaction, draft_type: str, amount: int = 1):
        if amount < 1 or amount > 10:
            await interaction.response.send_message("❌ You can only open between 1 and 10 packs at a time.", ephemeral=True)
            return

        user_id = interaction.user.id
        user = await database.get_user(user_id)
        
        if user.get('vouchers', 0) < amount:
            await interaction.response.send_message(f"❌ You don't have enough Draft Vouchers! You need {amount}.", ephemeral=True)
            return
            
        await interaction.response.defer()
        await database.add_vouchers(user_id, -amount)
        
        pulled_players = []
        highest_player = None
        highest_ovr = 0
        is_walkout_pack = False
        pack_tier_name = "Standard"
        
        current_drafts = user.get('drafts_opened', 0)

        # Roll for all packs
        for _ in range(amount):
            current_drafts += 1
            roll = random.uniform(0, 100)
            is_walkout = False
            pool_a_name = ""
            
            # Pity Triggers
            if current_drafts % 70 == 0:
                roll = random.uniform(0, 3) # Force Pool A
            elif current_drafts % 10 == 0:
                if roll > 3: # If they didn't naturally hit Pool A
                    roll = random.uniform(3, 33) # Force Pool B
            
            # Balanced Luck Probabilities (Between actual FCM and the crazy boosted ones)
            if roll <= 0.10:
                min_ovr, max_ovr = 122, 122
                tier_name = "WALKOUT 🌟🌟🌟"
                is_walkout = True
                if draft_type == "ann_a": pool_a_name = "Mbappé"
                elif draft_type == "ann_b": pool_a_name = "Blanc"
                elif draft_type == "stellar": pool_a_name = "Charlton"
            elif roll <= 0.75:
                min_ovr, max_ovr = 121, 121
                tier_name = "WALKOUT 🌟🌟"
                is_walkout = True
                if draft_type == "ann_a": pool_a_name = "Davies"
                elif draft_type == "ann_b": pool_a_name = "Gilberto Silva"
                elif draft_type == "stellar": pool_a_name = "Shaqiri"
            elif roll <= 2.25:
                min_ovr, max_ovr = 120, 120
                tier_name = "WALKOUT 🌟"
                is_walkout = True
                if draft_type == "ann_a": pool_a_name = "Nesta"
                elif draft_type == "ann_b": pool_a_name = "Diomandé"
                elif draft_type == "stellar": pool_a_name = "Di Natale"
            elif roll <= 7.25:
                min_ovr, max_ovr = 119, 119
                tier_name = "Elite"
            elif roll <= 15.25:
                min_ovr, max_ovr = 118, 118
                tier_name = "Elite"
            elif roll <= 26.25:
                min_ovr, max_ovr = 117, 117
                tier_name = "Elite"
            else:
                min_ovr, max_ovr = 112, 116
                tier_name = "Standard"
                
            if pool_a_name:
                players = search_fifarenderz(pool_a_name, size=5)
                players = [p for p in players if p.get('rating') == min_ovr]
            else:
                players = query_players_by_program("PROGRAM_ANN27", min_rating=min_ovr, max_rating=max_ovr, size=50)
                if not players:
                    players = query_players_by_program("PROGRAM_ANN27", min_rating=112, max_rating=116, size=50)
                    
            if not players:
                players = search_fifarenderz("Messi", size=5) 
                
            if not players:
                # Ultimate fallback to prevent crash and buffering
                players = [{
                    "id": 999999, "cardName": "Error Recovery", "lastName": "Error Recovery", 
                    "rating": min_ovr, "position": "ST", "ovr": min_ovr,
                    "nation": {"name": "Unknown"}, "club": {"name": "Unknown"},
                    "images": {"playerCardImage": ""}
                }]
                
            player_data = random.choice(players)
            pulled_players.append(player_data)
            
            # Save to database
            await database.add_player_to_inventory(user_id, player_data)
            
            p_ovr = player_data.get('rating', 0)
            if p_ovr > highest_ovr:
                highest_ovr = p_ovr
                highest_player = player_data
                is_walkout_pack = is_walkout
                pack_tier_name = tier_name

        await database.increment_drafts(user_id, amount)

        # Better Walkout Animation
        msg = await interaction.followup.send(f"🚨 **{interaction.user.display_name} IS OPENING {amount}x PACKS...** 🚨")
        await asyncio.sleep(1)
        
        pos = highest_player.get('position', '??')
        
        # Hardcoded walkout data for the 120+ pool
        walkout_data = {
            "Mbappé": ("🇫🇷 France", "🛡️ Real Madrid"),
            "Blanc": ("🇫🇷 France", "🛡️ Icons"),
            "Charlton": ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 England", "🛡️ Icons"),
            "Davies": ("🇨🇦 Canada", "🛡️ Bayern Munich"),
            "Gilberto Silva": ("🇧🇷 Brazil", "🛡️ Icons"),
            "Shaqiri": ("🇨🇭 Switzerland", "🛡️ FC Basel"),
            "Nesta": ("🇮🇹 Italy", "🛡️ Icons"),
            "Diomandé": ("🇨🇮 Ivory Coast", "🛡️ Sporting CP"),
            "Di Natale": ("🇮🇹 Italy", "🛡️ Icons")
        }
        
        nation_str, club_str = "🌍 Unknown", "🛡️ Unknown"
        best_name = highest_player.get('cardName') or highest_player.get('lastName', 'Unknown')
        
        for k, v in walkout_data.items():
            if k in best_name:
                nation_str, club_str = v
                break
        
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}")
        await asyncio.sleep(1.5)
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}\n🔥 🏃 **POSITION REVEALED:** `{pos}`")
        await asyncio.sleep(1.5)
        await msg.edit(content=f"⬛⬛⬛⬛⬛⬛⬛⬛\n🔥 🌍 **NATION REVEALED:** {nation_str}\n🔥 🏃 **POSITION REVEALED:** `{pos}`\n🔥 🛡️ **CLUB REVEALED:** {club_str}")
        await asyncio.sleep(1.5)
            
        try:
            image = generate_card(highest_player)
            with io.BytesIO() as image_binary:
                image.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='card.png')
                
                desc = f"**Best Pull:** {best_name} ({highest_ovr})\n\n"
                
                # If multipack, list the others
                if amount > 1:
                    desc += "**Other Pulls:**\n"
                    # Sort others by OVR
                    others = sorted([p for p in pulled_players if p != highest_player], key=lambda x: x.get('rating', 0), reverse=True)
                    # Show up to 9 others so it doesn't break character limits
                    for p in others[:9]:
                        name = p.get('cardName') or p.get('lastName', 'Unknown')
                        desc += f"• {name} ({p.get('rating', 0)})\n"
                    if len(others) > 9:
                        desc += f"*...and {len(others) - 9} more.*"
                
                embed = discord.Embed(
                    title=f"🎉 {pack_tier_name} Pack Opened! ({amount}x)",
                    description=desc,
                    color=discord.Color.gold() if is_walkout_pack else discord.Color.blue()
                )
                embed.set_author(name=f"{interaction.user.display_name}'s Pack", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
                embed.set_image(url="attachment://card.png")
                
                pity_b = 10 - (current_drafts % 10)
                pity_a = 70 - (current_drafts % 70)
                embed.set_footer(text=f"Drafts to Guaranteed Pool B: {pity_b} | Drafts to Guaranteed Pool A: {pity_a}")
                
                await msg.delete()
                await interaction.followup.send(embed=embed, file=file)
                
        except Exception as e:
            await msg.delete()
            await interaction.followup.send(f"❌ Packs opened, but failed to generate card image: {e}")

async def setup(bot):
    await bot.add_cog(DraftCog(bot))
