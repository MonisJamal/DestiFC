import discord
from discord.ext import commands, tasks
from discord import app_commands
import io
import random
import asyncio
import datetime

import database
from renderz_api import query_players_by_program, fetch_all_players_by_rating
from card_generator import generate_card, save_card_to_bytes, get_or_create_card_bytes
from maps import nation_map, club_map, extract_pos
from auth import is_team_admin_or_owner

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

class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.draft_rotator.start()

    def cog_unload(self):
        self.draft_rotator.cancel()

    @tasks.loop(minutes=1)
    async def draft_rotator(self):
        try:
            drafts = await database.get_active_drafts()
            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            
            needs_refresh = False
            if not drafts:
                needs_refresh = True
            else:
                # Check if expired
                for d in drafts.values():
                    if not d.get("expires_at") or now > d["expires_at"]:
                        needs_refresh = True
                        break
                        
            if needs_refresh:
                print("[Draft] Rotating and generating new 2-Hour Draft Pools from official database...")
                
                # Fetch 122, 121, and 120 cards from local DB cache instantly (<10ms)
                pool_122 = await database.get_official_cards_by_rating(122, 122, 100)
                pool_121 = await database.get_official_cards_by_rating(121, 121, 100)
                pool_120 = await database.get_official_cards_by_rating(120, 120, 100)

                # Fallback to renderz_api if DB cache is warming up
                if not pool_122: pool_122 = await asyncio.to_thread(fetch_all_players_by_rating, 122, True)
                if not pool_121: pool_121 = await asyncio.to_thread(fetch_all_players_by_rating, 121, True)
                if not pool_120: pool_120 = await asyncio.to_thread(fetch_all_players_by_rating, 120, True)

                def split_promo_icons(lst):
                    ev = [p for p in lst if 'ICON' not in p.get('source', '') and 'HERO' not in p.get('source', '')]
                    ic = [p for p in lst if 'ICON' in p.get('source', '') or 'HERO' in p.get('source', '')]
                    return ev, ic

                ev122, ic122 = split_promo_icons(pool_122)
                ev121, ic121 = split_promo_icons(pool_121)
                ev120, ic120 = split_promo_icons(pool_120)
                
                pool_117 = await database.get_official_cards_by_rating(117, 119, 100)
                pool_112 = await database.get_official_cards_by_rating(112, 116, 100)
                
                if not pool_122 or not pool_121 or not pool_120:
                    print("[Draft] Not enough 120+ players fetched, skipping rotation.")
                    return
                if not pool_117: pool_117 = pool_120  # fallback
                if not pool_112: pool_112 = pool_117  # fallback
                
                new_drafts = {}
                # 2-Hour draft rotation for active pool refreshes
                expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
                
                used_featured_ids = set()
                for i in range(1, 4):
                    def pick_unique(candidates, fallback_pool):
                        pool_to_use = candidates if candidates else fallback_pool
                        avail = [p for p in pool_to_use if p.get('assetId') not in used_featured_ids]
                        if not avail: avail = pool_to_use
                        chosen = random.choice(avail)
                        used_featured_ids.add(chosen.get('assetId'))
                        return chosen

                    featured_a = [
                        pick_unique(ev122, pool_122),
                        pick_unique(ic122, pool_122),
                        pick_unique(ev121, pool_121),
                        pick_unique(ic121, pool_121),
                        pick_unique(ev120, pool_120),
                        pick_unique(ic120, pool_120),
                    ]
                    new_drafts[i] = {
                        "pool_a": featured_a,
                        "pool_b": random.sample(pool_117, min(10, len(pool_117))),
                        "pool_c": random.sample(pool_112, min(30, len(pool_112))),
                        "expires_at": expires
                    }
                await database.set_active_drafts(new_drafts)
                print(f"[Draft] Successfully generated 3 lightweight drafts! Expires: {expires}")
                
                # Pre-warm animated cards in background for zero-lag instant pack opening
                async def _prewarm_cards():
                    for pack_info in new_drafts.values():
                        for p in pack_info.get("pool_a", []):
                            try:
                                await asyncio.to_thread(get_or_create_card_bytes, p, 3, True)
                            except Exception:
                                pass
                asyncio.create_task(_prewarm_cards())
        except Exception as e:
            print(f"[Draft] Error in draft rotator: {e}")

    @draft_rotator.before_loop
    async def before_rotator(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="draft_info", description="See which players are featured in a specific draft")
    @app_commands.choices(pack=[
        app_commands.Choice(name="Draft Pack 1", value=1),
        app_commands.Choice(name="Draft Pack 2", value=2),
        app_commands.Choice(name="Draft Pack 3", value=3)
    ])
    async def draft_info(self, interaction: discord.Interaction, pack: int):
        await interaction.response.defer()
        drafts = await database.get_active_drafts()
        if not drafts or (str(pack) not in drafts and pack not in drafts):
            return await interaction.followup.send("❌ Drafts are currently rotating. Please wait a minute.", ephemeral=True)
            
        d = drafts.get(pack) or drafts.get(str(pack))
        
        # Convert UTC string time to Discord Local Time format
        dt = datetime.datetime.strptime(d['expires_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        unix = int(dt.timestamp())
        expires_display = f"<t:{unix}:f> (<t:{unix}:R>)"
        
        embed = discord.Embed(title=f"📦 Draft Pack {pack} Info", description=f"**Expires:** {expires_display}", color=0x00ff00)
        
        featured_lines = []
        for p in d['pool_a']:
            prog = p.get('source', '').replace('PROGRAM_', '')
            pos = p.get('position', 'ST')
            featured_lines.append(f"🌟 **{p.get('cardName') or p.get('lastName')}** `({pos})` ({p.get('rating')} OVR) — *{prog}*")
        
        pool_b_names = [f"{p.get('cardName') or p.get('lastName')} `({p.get('position', '??')})` ({p.get('rating')})" for p in d['pool_b']]
        
        embed.add_field(name="🌟 Featured Walkouts (120-122)", value="\n".join(featured_lines), inline=False)
        embed.add_field(name="✨ Elite Pulls (117-119)", value=", ".join(pool_b_names), inline=False)
        embed.add_field(name="🟦 Standard Pulls (112-116)", value=f"*{len(d['pool_c'])} other players possible...*", inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="draft_refresh", description="[ADMIN] Force refresh the drafts right now")
    async def draft_refresh(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ **Access Denied:** Only Discord Application Team members can use this command.", ephemeral=True)
            
        p = await database.get_db()
        await p.execute("DELETE FROM global_drafts")
        database._DRAFTS_CACHE = None
            
        await self.draft_rotator()
        await interaction.followup.send("✅ **Drafts Force-Refreshed!**")


    @app_commands.command(name="draft", description="Open a specific draft pack")
    @app_commands.choices(pack=[
        app_commands.Choice(name="Draft Pack 1", value=1),
        app_commands.Choice(name="Draft Pack 2", value=2),
        app_commands.Choice(name="Draft Pack 3", value=3)
    ])
    async def draft(self, interaction: discord.Interaction, pack: int, amount: int = 1):
        await interaction.response.defer()
        if amount < 1 or amount > 10:
            return await interaction.followup.send("❌ You can only open between 1 and 10 packs at a time.", ephemeral=True)

        inv_size = await database.get_inventory_size(interaction.user.id)
        if inv_size + amount > 1000:
            return await interaction.followup.send(f"❌ **Inventory Full!**\nYou currently have {inv_size}/1000 cards. Please `/market sell` or `/exchange` some players before opening more packs.", ephemeral=True)

        user_id = interaction.user.id
        user = await database.get_user(user_id)
        
        if user.get('vouchers', 0) < amount:
            return await interaction.followup.send(f"❌ You need {amount} Draft Vouchers to open this pack!\nPlay `/quest_skill_game` or `/quest_h2h` to earn some.", ephemeral=True)

        drafts = await database.get_active_drafts()
        if not drafts or (str(pack) not in drafts and pack not in drafts):
            return await interaction.followup.send("❌ Drafts are currently rotating. Please wait a minute.", ephemeral=True)
            
        d = drafts.get(pack) or drafts.get(str(pack))
        
        # Validate pools aren't empty
        if not d.get('pool_a') or not d.get('pool_b') or not d.get('pool_c'):
            return await interaction.followup.send("❌ This draft pack has empty pools. The bot will refresh them shortly!", ephemeral=True)
        
        pulled_players = []
        highest_player = None
        highest_ovr = 0
        is_walkout_pack = False
        pack_tier_name = "Standard"
        
        current_drafts = user.get('drafts_opened', 0)
        pity_counter = user.get('drafts_since_walkout')
        if pity_counter is None:
            pity_counter = 0

        custom_draft_pool = await database.get_all_custom_draft_cards()

        # Roll for all packs
        for _ in range(amount):
            current_drafts += 1
            pity_counter += 1
            roll = random.uniform(0, 100)
            is_walkout = False
            
            # Pity Triggers — 70th pack guaranteed Pool A, 10th pack guaranteed Pool B
            if pity_counter >= 70:
                roll = random.uniform(0.01, 2.99)  # Force Pool A
            elif pity_counter % 10 == 0:
                if roll > 33.0:
                    roll = random.uniform(3.1, 33.0)  # Force Pool B
            
            if custom_draft_pool and random.random() < 0.03:
                player_data = random.choice(custom_draft_pool)
                is_walkout = (player_data.get('rating', 0) >= 120)
                tier_name = "CUSTOM LEGEND 👑" if is_walkout else "CUSTOM ELITE 💎"
                if is_walkout:
                    pity_counter = 0
            elif roll <= 3.0:
                # Pool A (3% base chance: 1.5x boosted)
                is_walkout = True
                pity_counter = 0  # RESET PITY IMMEDIATELY
                tier_name = "WALKOUT 🌟🌟🌟"
                player_data = random.choice(d['pool_a'])
            elif roll <= 33.0:
                # Pool B (30% chance: 117-119)
                tier_name = "Elite ✨✨"
                player_data = random.choice(d['pool_b']) if d.get('pool_b') else random.choice(d['pool_a'])
            else:
                # Pool C (68% chance: 112-116)
                tier_name = "Standard"
                player_data = random.choice(d['pool_c']) if d.get('pool_c') else (random.choice(d.get('pool_b', d['pool_a'])))
                
            pulled_players.append(player_data)
            
            p_ovr = player_data.get('rating', 0)
            if p_ovr > highest_ovr:
                highest_ovr = p_ovr
                highest_player = player_data
                is_walkout_pack = is_walkout
                pack_tier_name = tier_name

        # Parallel ultra-fast database operations
        await asyncio.gather(
            database.add_vouchers(user_id, -amount),
            database.add_players_to_inventory_batch(user_id, pulled_players),
            database.increment_drafts(user_id, amount),
            database.set_drafts_since_walkout(user_id, pity_counter)
        )
        
        # --- Achievement & Season XP hooks ---
        try:
            from cogs.achievements import increment_stat, check_and_award
            if is_walkout_pack:
                await increment_stat(user_id, "walkouts_pulled")
                if highest_ovr >= 122:
                    from cogs.achievements import try_award
                    await try_award(user_id, "legendary_pull")
            await check_and_award(user_id)
        except Exception: pass
        try:
            from cogs.season import add_season_xp
            await add_season_xp(user_id, 50 * amount)
        except Exception: pass

        pos = extract_pos(highest_player)
        nation_str = get_nation_display(highest_player)
        club_str = get_club_display(highest_player)
        best_name = highest_player.get('cardName') or highest_player.get('lastName', 'Unknown')
            
        try:
            is_anim = (isinstance(highest_ovr, int) and highest_ovr >= 120)
            is_walkout = is_walkout_pack or is_anim
            
            # Start image generation task concurrently with walkout sequence
            card_gen_task = asyncio.create_task(asyncio.to_thread(get_or_create_card_bytes, highest_player, 3, is_anim))
            
            if is_walkout:
                # Step 1: Flag / Nation
                msg = await interaction.followup.send(
                    f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n\n*(Walking onto the stage...)*"
                )
                await asyncio.sleep(1.2)
                
                # Step 2: Position
                await interaction.followup.edit_message(
                    msg.id,
                    content=f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n# 🏃 **`{pos}`**\n\n*(Entering the stadium tunnel...)*"
                )
                await asyncio.sleep(1.2)
                
                # Step 3: Club
                await interaction.followup.edit_message(
                    msg.id,
                    content=f"🌟 **WALKOUT INITIATED!** 🌟\n\n# {nation_str.upper()}\n# 🏃 **`{pos}`**\n# {club_str.upper()}\n\n🔥 **PYROTECHNICS EXPLODING!**"
                )
                await asyncio.sleep(1.2)

            image_binary, filename = await card_gen_task
            if not image_binary:
                image_binary, filename = await asyncio.to_thread(get_or_create_card_bytes, highest_player, 3, False)
                
            file = discord.File(fp=image_binary, filename=filename or 'card.png') if image_binary else None
                
            walkout_prefix = f"🔥 **{nation_str}** | 🏃 **`{pos}`** | **{club_str}**\n\n" if is_walkout else ""
            desc = f"{walkout_prefix}🌟 **Featured Walkout:** **{best_name}** `({pos})` ({highest_ovr} OVR)\n\n"
            
            if amount > 1:
                desc += "📋 **Other Pack Pulls:**\n"
                others = sorted([p for p in pulled_players if p != highest_player], key=lambda x: x.get('rating', 0), reverse=True)
                for p in others[:9]:
                    name = p.get('cardName') or p.get('lastName', 'Unknown')
                    ovr = p.get('rating', 0)
                    p_pos = extract_pos(p)
                    icon = "🔥" if ovr >= 120 else ("✨" if ovr >= 117 else "⚽")
                    desc += f"{icon} **{name}** `({p_pos})` — `{ovr} OVR`\n"
                if len(others) > 9:
                    desc += f"*...and {len(others) - 9} more cards added to your club!*"
            
            embed = discord.Embed(
                title=f"🎉 {pack_tier_name} Pack Opened! ({amount}x)",
                description=desc,
                color=discord.Color.gold() if is_walkout else discord.Color.blue()
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Pack", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            if file and filename:
                embed.set_image(url=f"attachment://{filename}")
            
            pity_b = 10 - (pity_counter % 10)
            pity_a = max(0, 70 - pity_counter)
            embed.set_footer(text=f"Drafts to Guaranteed Pool B: {pity_b} | Drafts to Guaranteed Pool A: {pity_a}")
            
            if is_walkout:
                if file:
                    await interaction.followup.edit_message(msg.id, content=None, embed=embed, attachments=[file])
                else:
                    await interaction.followup.edit_message(msg.id, content=None, embed=embed)
            else:
                if file:
                    await interaction.followup.send(embed=embed, file=file)
                else:
                    await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[Draft] Error presenting pack: {e}")
            await interaction.followup.send(f"🎉 **Pack Opened!** Successfully added **{len(pulled_players)}** cards to your inventory.")

async def setup(bot):
    await bot.add_cog(DraftCog(bot))
