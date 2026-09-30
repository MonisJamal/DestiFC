import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import random
import io
import json
import datetime
from renderz_api import query_players_by_program, fetch_all_players_by_rating
from card_generator import get_or_create_card_bytes
from maps import nation_map, club_map, extract_pos
from auth import is_team_admin_or_owner
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
        self.exchange_rotator.start()

    def cog_unload(self):
        self.exchange_rotator.cancel()

    @tasks.loop(minutes=1)
    async def exchange_rotator(self):
        try:
            pool = await database.get_active_exchange_pool()
            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            needs_refresh = False
            if not pool or not pool.get("expires_at") or now > pool["expires_at"]:
                needs_refresh = True
            elif not pool.get("cards_120") or not pool.get("cards_121") or not pool.get("cards_122"):
                needs_refresh = True

            if needs_refresh:
                max_ovr = await database.get_max_official_ovr()
                if not max_ovr or max_ovr < 115:
                    max_ovr = 122

                ovr_top = max_ovr           # e.g. 122 (or 124) -> 2 cards
                ovr_mid = max_ovr - 1       # e.g. 121 (or 123) -> 5 cards
                ovr_low = max_ovr - 2       # e.g. 120 (or 122) -> 5 cards

                print(f"[Exchange] Rotating and generating new 2-Hour Exchange Pool ({ovr_low}: 5, {ovr_mid}: 5, {ovr_top}: 2)...")

                pool_top = await database.get_official_cards_by_rating(ovr_top, ovr_top, 100)
                pool_mid = await database.get_official_cards_by_rating(ovr_mid, ovr_mid, 100)
                pool_low = await database.get_official_cards_by_rating(ovr_low, ovr_low, 100)

                if not pool_top: pool_top = await asyncio.to_thread(fetch_all_players_by_rating, ovr_top, True)
                if not pool_mid: pool_mid = await asyncio.to_thread(fetch_all_players_by_rating, ovr_mid, True)
                if not pool_low: pool_low = await asyncio.to_thread(fetch_all_players_by_rating, ovr_low, True)

                # Fallback chain if a tier is temporarily sparse
                if not pool_top and pool_mid: pool_top = pool_mid
                if not pool_mid and pool_low: pool_mid = pool_low
                if not pool_low and pool_mid: pool_low = pool_mid

                if not pool_top or not pool_mid or not pool_low:
                    print("[Exchange] Not enough players found for exchange pool, skipping rotation.")
                    return

                # Sample required composition: 5 of 120s, 5 of 121s, 2 of 122s
                sampled_top = random.sample(pool_top, min(2, len(pool_top)))
                sampled_mid = random.sample(pool_mid, min(5, len(pool_mid)))
                sampled_low = random.sample(pool_low, min(5, len(pool_low)))

                expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

                new_exchange_pool = {
                    "ovr_top": ovr_top,
                    "ovr_mid": ovr_mid,
                    "ovr_low": ovr_low,
                    "cards_122": sampled_top,
                    "cards_121": sampled_mid,
                    "cards_120": sampled_low,
                    "expires_at": expires
                }

                await database.set_active_exchange_pool(new_exchange_pool)
                print(f"[Exchange] Successfully rotated Exchange Pool! Total: {len(sampled_top) + len(sampled_mid) + len(sampled_low)} cards. Expires: {expires}")

                # Pre-warm animated cards in background for zero-lag walkouts
                async def _prewarm():
                    for p in sampled_top + sampled_mid + sampled_low:
                        try:
                            await asyncio.to_thread(get_or_create_card_bytes, p, 3, True)
                        except Exception: pass
                asyncio.create_task(_prewarm())
        except Exception as e:
            print(f"[Exchange] Error in exchange rotator: {e}")

    @exchange_rotator.before_loop
    async def before_exchange_rotator(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="exchange_info", description="View the current 2-hour Exchange Pool (5x 120s, 5x 121s, 2x 122s)")
    async def exchange_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pool = await database.get_active_exchange_pool()
        if not pool or not pool.get("cards_122") or not pool.get("cards_121") or not pool.get("cards_120"):
            return await interaction.followup.send("❌ Exchange pool is currently rotating. Please try again in a moment.", ephemeral=True)

        dt = datetime.datetime.strptime(pool['expires_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        unix = int(dt.timestamp())
        expires_display = f"<t:{unix}:f> (<t:{unix}:R>)"

        ovr_top = pool.get('ovr_top', 122)
        ovr_mid = pool.get('ovr_mid', 121)
        ovr_low = pool.get('ovr_low', 120)

        embed = discord.Embed(
            title="🔄 2-Hour Guaranteed Exchange Pool",
            description=f"Exchange 25 cards using `/exchange` to win one of these guaranteed featured walkouts!\n\n**Expires:** {expires_display}",
            color=0xF59E0B
        )

        def format_player_line(p):
            name = p.get('cardName') or p.get('lastName', 'Unknown')
            pos = p.get('position', 'ST')
            prog = p.get('source', '').replace('PROGRAM_', '')
            ovr = p.get('rating', '??')
            return f"🌟 **{name}** `({pos})` `{ovr} OVR` — *{prog}*"

        top_lines = [format_player_line(p) for p in pool.get('cards_122', [])]
        mid_lines = [format_player_line(p) for p in pool.get('cards_121', [])]
        low_lines = [format_player_line(p) for p in pool.get('cards_120', [])]

        embed.add_field(name=f"👑 Grand Master Walkouts ({ovr_top} OVR — 2 Cards • 10% Chance)", value="\n".join(top_lines) if top_lines else "*Rotating...*", inline=False)
        embed.add_field(name=f"✨ Elite Master Walkouts ({ovr_mid} OVR — 5 Cards • 40% Chance)", value="\n".join(mid_lines) if mid_lines else "*Rotating...*", inline=False)
        embed.add_field(name=f"🌟 Prime Walkouts ({ovr_low} OVR — 5 Cards • 50% Chance)", value="\n".join(low_lines) if low_lines else "*Rotating...*", inline=False)

        embed.set_footer(text="Trade 25 club cards in /exchange • Guaranteed 120+ Walkout Every Time!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="exchange_refresh", description="[ADMIN] Force refresh the 2-Hour Exchange Pool right now")
    async def exchange_refresh(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ **Access Denied:** Only Discord Application Team members can use this command.", ephemeral=True)
            
        p = await database.get_db()
        await p.execute("DELETE FROM global_exchange_pool")
        database._EXCHANGE_POOL_CACHE = None
            
        await self.exchange_rotator()
        await interaction.followup.send("✅ **Exchange Pool Force-Refreshed (5x 120s, 5x 121s, 2x 122s)!**")

    async def exchange_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [
            app_commands.Choice(name="Standard Exchange (25 Any Cards -> Active 120-122 Walkout Pool)", value="standard"),
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
            return await interaction.followup.send("❌ Your inventory is full! You cannot open more packs until you quicksell or use cards in `/squad`.", ephemeral=True)
            
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
                return await interaction.followup.send(f"❌ You don't have enough Fodder cards! You need {cost} cards rated between 110-116, but you only have {len(fodder_cards)}.", ephemeral=True)
                
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
            # Standard Exchange (25 cards -> Guaranteed Pool of 5x 120s, 5x 121s, 2x 122s)
            cost = 25
            if len(inventory) < cost:
                return await interaction.followup.send(f"❌ You don't have enough cards! The Standard Exchange requires {cost} cards, but you only have {len(inventory)}.", ephemeral=True)
                
            inventory.sort(key=get_ovr)
            to_delete = [row['id'] if isinstance(row, dict) else row[0] for row in inventory[:cost]]
            
            await database.remove_players_from_inventory(user_id, to_delete)

            pool = await database.get_active_exchange_pool()
            if not pool or not pool.get("cards_120") or not pool.get("cards_121") or not pool.get("cards_122"):
                # Emergency generation if empty
                await self.exchange_rotator()
                pool = await database.get_active_exchange_pool()

            roll = random.random()
            if roll < 0.10 and pool.get("cards_122"):
                player_data = random.choice(pool["cards_122"])
                tier_name = "GRAND MASTER WALKOUT 👑👑👑"
            elif roll < 0.50 and pool.get("cards_121"):
                player_data = random.choice(pool["cards_121"])
                tier_name = "ELITE MASTER WALKOUT 🌟🌟"
            elif pool.get("cards_120"):
                player_data = random.choice(pool["cards_120"])
                tier_name = "PRIME WALKOUT 🌟"
            else:
                fallback = (pool.get("cards_122", []) + pool.get("cards_121", []) + pool.get("cards_120", []))
                player_data = random.choice(fallback) if fallback else None
                tier_name = "WALKOUT 🌟"

            if not player_data:
                # Absolute fallback
                fb_players = await database.get_official_cards_by_rating(120, 122, 10)
                player_data = random.choice(fb_players)

        try:
            ovr = player_data.get('rating', 0)
            card_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
            pos = extract_pos(player_data)
            
            nation_str = get_nation_display(player_data)
            club_str = get_club_display(player_data)
            
            is_walkout = (isinstance(ovr, int) and ovr >= 120)
            
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
            embed.set_footer(text=f"{cost} players consumed • 1 card added to your inventory • Check /exchange_info for current pool")
            
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
