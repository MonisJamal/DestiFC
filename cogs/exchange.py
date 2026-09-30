import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import random
import io
import json
from renderz_api import query_players_by_program, fetch_all_players_by_rating
from card_generator import get_or_create_card_bytes
from maps import nation_map, club_map, extract_pos
import database

def get_nation_display(player_data):
    nation = player_data.get('nation')
    if isinstance(nation, dict):
        n_id = nation.get('id')
        if n_id in nation_map: return nation_map[n_id]
        if nation.get('name'): return f"🌍 {nation['name']}"
    elif isinstance(nation, str):
        return f"🌍 {nation}"
    return "🌍 World"

def get_club_display(player_data):
    club = player_data.get('club')
    if isinstance(club, dict):
        c_id = club.get('id')
        if c_id in club_map: return club_map[c_id]
        if club.get('name'): return f"🛡️ {club['name']}"
    elif isinstance(club, str):
        return f"🛡️ {club}"
    return "🛡️ Club"

class ExchangeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def exchange_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [
            app_commands.Choice(name="Standard Exchange (25 Any Cards -> 120+ Walkout)", value="standard"),
            app_commands.Choice(name="Fodder Exchange (20x 110-116 Cards -> 117-119 Card)", value="fodder")
        ]
        return [c for c in choices if current.lower() in c.name.lower()]

    @app_commands.command(name="exchange", description="Trade useless cards for guaranteed high OVR players!")
    @app_commands.autocomplete(exchange_type=exchange_autocomplete)
    async def exchange(self, interaction: discord.Interaction, exchange_type: str = "standard"):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        # Check inventory size
        inv_size = await database.get_inventory_size(user_id)
        if inv_size >= 1000:
            return await interaction.followup.send("❌ Your inventory is full! You cannot open more packs until you quicksell or use cards in `/squad`.")
            
        inventory = await database.get_inventory(user_id)
        
        # Lock squad players — never sacrifice your main 11!
        locked_ids = await database.get_squad_locked_ids(user_id)
        inventory = [row for row in inventory if int(row.get('id', -1)) not in locked_ids and not row.get('locked', 0)]
        
        def get_ovr(row):
            try:
                if isinstance(row, dict): return int(row.get('ovr', 0))
                return json.loads(row[1]).get('rating', 0)
            except: return 0
            
        if exchange_type == "fodder":
            cost = 20
            # Filter for 110-116
            fodder_cards = [row for row in inventory if 110 <= get_ovr(row) <= 116]
            if len(fodder_cards) < cost:
                return await interaction.followup.send(f"❌ You don't have enough Fodder cards! You need {cost} cards rated between 110-116, but you only have {len(fodder_cards)}.")
                
            fodder_cards.sort(key=get_ovr)
            to_delete = [row['id'] if isinstance(row, dict) else row[0] for row in fodder_cards[:cost]]
            
            await database.remove_players_from_inventory(user_id, to_delete)
                
            # Reward: 117-119
            roll = random.random()
            if roll < 0.10: min_ovr = 119
            elif roll < 0.40: min_ovr = 118
            else: min_ovr = 117
            
            tier_name = "FODDER UPGRADE ✨"
            players = await database.get_official_cards_by_rating(min_ovr, min_ovr, 50)
            if not players:
                players = await asyncio.to_thread(fetch_all_players_by_rating, min_ovr)
            if not players:
                players = await asyncio.to_thread(query_players_by_program, "", min_rating=min_ovr, max_rating=min_ovr, size=50)
            
            player_data = random.choice(players)
            
        else:
            # Standard Exchange
            cost = 25
            if len(inventory) < cost:
                return await interaction.followup.send(f"❌ You don't have enough cards! The Standard Exchange requires {cost} cards, but you only have {len(inventory)}.")
                
            inventory.sort(key=get_ovr)
            to_delete = [row['id'] if isinstance(row, dict) else row[0] for row in inventory[:cost]]
            
            await database.remove_players_from_inventory(user_id, to_delete)
                
            roll = random.random()
            if roll < 0.08: min_ovr = 122
            elif roll < 0.50: min_ovr = 121
            else: min_ovr = 120
                
            tier_name = "WALKOUT 🌟🌟🌟" if min_ovr == 122 else "WALKOUT 🌟🌟" if min_ovr == 121 else "WALKOUT 🌟"
            
            # Fetch from comprehensive pool of ALL 120-122 cards in existence from fast local DB cache
            players = await database.get_official_cards_by_rating(min_ovr, min_ovr, 50)
            if not players:
                players = await asyncio.to_thread(fetch_all_players_by_rating, min_ovr)
            if not players:
                players = await asyncio.to_thread(query_players_by_program, "", min_rating=min_ovr, max_rating=min_ovr, size=100)
                
            player_data = random.choice(players)

        try:
            ovr = player_data.get('rating', 0)
            card_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
            pos = extract_pos(player_data)
            
            nation_str = get_nation_display(player_data)
            club_str = get_club_display(player_data)
            
            is_walkout = (isinstance(ovr, int) and ovr >= 120)
            is_anim = is_walkout
            
            # Start image generation task in background during walkout animation
            card_gen_task = asyncio.create_task(asyncio.to_thread(get_or_create_card_bytes, player_data, 3, False))
            
            if is_walkout:
                # Step 1: Flag / Nation
                msg = await interaction.followup.send(
                    f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n\n*(Walking onto the stage...)*"
                )
                await asyncio.sleep(0.5)
                
                # Step 2: Position
                await interaction.followup.edit_message(
                    msg.id,
                    content=f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n# 🏃 **`{pos}`**\n\n*(Entering the tunnel spotlight...)*"
                )
                await asyncio.sleep(0.5)
                
                # Step 3: Club
                await interaction.followup.edit_message(
                    msg.id,
                    content=f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n# 🏃 **`{pos}`**\n# {club_str.upper()}\n\n🔥 **PYROTECHNICS EXPLODING!**"
                )
                await asyncio.sleep(0.5)

            image_binary, filename = await card_gen_task
            file = discord.File(fp=image_binary, filename=filename)
            
            walkout_prefix = f"🔥 **{nation_str}** | 🏃 **`{pos}`** | **{club_str}**\n\n" if is_walkout else ""
            desc = f"{walkout_prefix}🌟 **Exchange Walkout Reward:** **{card_name}** `({pos})` ({ovr} OVR)\n\n*Successfully swapped `{cost}` cards from your club!*"
            
            embed = discord.Embed(
                title=f"🎉 {tier_name} Completed!",
                description=desc,
                color=discord.Color.gold() if is_walkout else discord.Color.blue()
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Exchange", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            embed.set_image(url=f"attachment://{filename}")
            embed.set_footer(text=f"{cost} players consumed • 1 card added to your inventory")
            
            await database.add_player_to_inventory(user_id, player_data)
            
            # --- Achievement & Season XP hooks ---
            try:
                from cogs.achievements import increment_stat, check_and_award
                await increment_stat(user_id, "exchanges_done")
                if ovr >= 120:
                    await increment_stat(user_id, "walkouts_pulled")
                await check_and_award(user_id)
            except Exception: pass
            try:
                from cogs.season import add_season_xp
                await add_season_xp(user_id, 100)
            except Exception: pass

            if is_walkout:
                await interaction.followup.edit_message(msg.id, content=None, embed=embed, attachments=[file])
            else:
                await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            print(f"Error in exchange: {e}")
            await interaction.followup.send(f"✅ Exchange successful! Drafted **{card_name} ({ovr})**, but failed to generate card image.")

async def setup(bot):
    await bot.add_cog(ExchangeCog(bot))
