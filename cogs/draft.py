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
from maps import nation_map, club_map, extract_pos, get_nation_display, get_club_display
from auth import is_team_admin_or_owner

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
                max_ovr = await database.get_max_official_ovr()
                if not max_ovr or max_ovr < 115:
                    max_ovr = 122
                    
                print(f"[Draft] Rotating and generating new 2-Hour Draft Pools (Max OVR: {max_ovr})...")
                
                # Dynamic Pool Ratings:
                # Pool A = Top 3 OVRs: [max_ovr, max_ovr - 1, max_ovr - 2] (e.g. 124, 123, 122)
                # Pool B = 3 OVRs before Pool A: [max_ovr - 5, max_ovr - 3] (e.g. 119 to 121)
                # Pool C = 5 OVRs before Pool B: [max_ovr - 10, max_ovr - 6] (e.g. 114 to 118)
                ovr_a1, ovr_a2, ovr_a3 = max_ovr, max_ovr - 1, max_ovr - 2
                min_b, max_b = max_ovr - 5, max_ovr - 3
                min_c, max_c = max_ovr - 10, max_ovr - 6

                # Fetch top 3 rating tiers for Pool A
                pool_a1 = await database.get_official_cards_by_rating(ovr_a1, ovr_a1, 100)
                pool_a2 = await database.get_official_cards_by_rating(ovr_a2, ovr_a2, 100)
                pool_a3 = await database.get_official_cards_by_rating(ovr_a3, ovr_a3, 100)

                # Fallback to renderz_api if DB cache is warming up
                if not pool_a1: pool_a1 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a1, True)
                if not pool_a2: pool_a2 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a2, True)
                if not pool_a3: pool_a3 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a3, True)

                # Fallback chain if highest rating tier has sparse cards
                if not pool_a1 and pool_a2: pool_a1 = pool_a2
                if not pool_a2 and pool_a3: pool_a2 = pool_a3
                if not pool_a3 and pool_a2: pool_a3 = pool_a2

                def split_promo_icons(lst):
                    ev = [p for p in lst if 'ICON' not in p.get('source', '') and 'HERO' not in p.get('source', '')]
                    ic = [p for p in lst if 'ICON' in p.get('source', '') or 'HERO' in p.get('source', '')]
                    return ev, ic

                ev_a1, ic_a1 = split_promo_icons(pool_a1)
                ev_a2, ic_a2 = split_promo_icons(pool_a2)
                ev_a3, ic_a3 = split_promo_icons(pool_a3)
                
                pool_b = await database.get_official_cards_by_rating(min_b, max_b, 100)
                pool_c = await database.get_official_cards_by_rating(min_c, max_c, 100)
                
                if not pool_a1 and not pool_a2 and not pool_a3:
                    print(f"[Draft] Not enough {ovr_a3}+ players fetched, skipping rotation.")
                    return
                if not pool_b: pool_b = pool_a3  # fallback
                if not pool_c: pool_c = pool_b   # fallback
                
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
                        pick_unique(ev_a1, pool_a1),
                        pick_unique(ic_a1, pool_a1),
                        pick_unique(ev_a2, pool_a2),
                        pick_unique(ic_a2, pool_a2),
                        pick_unique(ev_a3, pool_a3),
                        pick_unique(ic_a3, pool_a3),
                    ]
                    new_drafts[i] = {
                        "pool_a": featured_a,
                        "pool_b": random.sample(pool_b, min(10, len(pool_b))),
                        "pool_c": random.sample(pool_c, min(30, len(pool_c))),
                        "expires_at": expires
                    }
                await database.set_active_drafts(new_drafts)
                print(f"[Draft] Successfully generated 3 dynamic drafts (Pool A: {ovr_a3}-{ovr_a1}, Pool B: {min_b}-{max_b}, Pool C: {min_c}-{max_c})! Expires: {expires}")
                
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

    async def refresh_single_draft(self, draft_num: int):
        """
        Refreshes a specific draft pack (e.g. Draft 1) immediately with new cards,
        while strictly preserving the active expiration timestamp matching the other drafts.
        """
        try:
            drafts = await database.get_active_drafts()
            if not drafts:
                return
            
            # Synchronize with current active draft expiry
            current_expiry = None
            for d in drafts.values():
                if d.get("expires_at"):
                    current_expiry = d.get("expires_at")
                    break
                    
            if not current_expiry:
                current_expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

            max_ovr = await database.get_max_official_ovr()
            if not max_ovr or max_ovr < 115:
                max_ovr = 122

            ovr_a1, ovr_a2, ovr_a3 = max_ovr, max_ovr - 1, max_ovr - 2
            min_b, max_b = max_ovr - 5, max_ovr - 3
            min_c, max_c = max_ovr - 10, max_ovr - 6

            pool_a1 = await database.get_official_cards_by_rating(ovr_a1, ovr_a1, 100)
            pool_a2 = await database.get_official_cards_by_rating(ovr_a2, ovr_a2, 100)
            pool_a3 = await database.get_official_cards_by_rating(ovr_a3, ovr_a3, 100)
            if not pool_a1: pool_a1 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a1, True)
            if not pool_a2: pool_a2 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a2, True)
            if not pool_a3: pool_a3 = await asyncio.to_thread(fetch_all_players_by_rating, ovr_a3, True)

            if not pool_a1 and pool_a2: pool_a1 = pool_a2
            if not pool_a2 and pool_a3: pool_a2 = pool_a3
            if not pool_a3 and pool_a2: pool_a3 = pool_a2

            def split_promo_icons(lst):
                ev = [p for p in lst if 'ICON' not in p.get('source', '') and 'HERO' not in p.get('source', '')]
                ic = [p for p in lst if 'ICON' in p.get('source', '') or 'HERO' in p.get('source', '')]
                return ev, ic

            ev_a1, ic_a1 = split_promo_icons(pool_a1)
            ev_a2, ic_a2 = split_promo_icons(pool_a2)
            ev_a3, ic_a3 = split_promo_icons(pool_a3)
            
            pool_b = await database.get_official_cards_by_rating(min_b, max_b, 100)
            pool_c = await database.get_official_cards_by_rating(min_c, max_c, 100)
            if not pool_b: pool_b = pool_a3
            if not pool_c: pool_c = pool_b

            # Avoid duplicating walkouts featured in the other active drafts
            used_featured_ids = set()
            for k, other_d in drafts.items():
                if str(k) != str(draft_num):
                    for p in other_d.get("pool_a", []):
                        used_featured_ids.add(p.get('assetId') or p.get('id'))

            def pick_unique(candidates, fallback_pool):
                pool_to_use = candidates if candidates else fallback_pool
                avail = [p for p in pool_to_use if (p.get('assetId') or p.get('id')) not in used_featured_ids]
                if not avail: avail = pool_to_use
                chosen = random.choice(avail)
                used_featured_ids.add(chosen.get('assetId') or chosen.get('id'))
                return chosen

            featured_a = [
                pick_unique(ev_a1, pool_a1),
                pick_unique(ic_a1, pool_a1),
                pick_unique(ev_a2, pool_a2),
                pick_unique(ic_a2, pool_a2),
                pick_unique(ev_a3, pool_a3),
                pick_unique(ic_a3, pool_a3),
            ]

            refreshed_draft = {
                "pool_a": featured_a,
                "pool_b": random.sample(pool_b, min(10, len(pool_b))),
                "pool_c": random.sample(pool_c, min(30, len(pool_c))),
                "expires_at": current_expiry  # Kept in exact sync with other drafts!
            }

            await database.update_single_draft(draft_num, refreshed_draft)
            print(f"[Draft] Refreshed Draft {draft_num} immediately! Rotation timer synchronized at: {current_expiry}")
        except Exception as e:
            print(f"[Draft] Error refreshing single draft {draft_num}: {e}")

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
        for p in d.get('pool_a', []):
            prog = p.get('source', '').replace('PROGRAM_', '')
            pos = p.get('position', 'ST')
            featured_lines.append(f"🌟 **{p.get('cardName') or p.get('lastName')}** `({pos})` ({p.get('rating')} OVR) — *{prog}*")
        
        pool_b_names = [f"{p.get('cardName') or p.get('lastName')} `({p.get('position', '??')})` ({p.get('rating')})" for p in d.get('pool_b', [])]
        
        pa_ovrs = [p.get('rating') for p in d.get('pool_a', []) if isinstance(p.get('rating'), int)]
        pb_ovrs = [p.get('rating') for p in d.get('pool_b', []) if isinstance(p.get('rating'), int)]
        pc_ovrs = [p.get('rating') for p in d.get('pool_c', []) if isinstance(p.get('rating'), int)]

        pa_label = f"({min(pa_ovrs)}-{max(pa_ovrs)})" if pa_ovrs else ""
        pb_label = f"({min(pb_ovrs)}-{max(pb_ovrs)})" if pb_ovrs else ""
        pc_label = f"({min(pc_ovrs)}-{max(pc_ovrs)})" if pc_ovrs else ""

        embed.add_field(name=f"🌟 Featured Walkouts {pa_label}", value="\n".join(featured_lines), inline=False)
        embed.add_field(name=f"✨ Elite Pulls {pb_label}", value=", ".join(pool_b_names), inline=False)
        embed.add_field(name=f"🟦 Standard Pulls {pc_label}", value=f"*{len(d.get('pool_c', []))} other players possible...*", inline=False)
        
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

        user_id = interaction.user.id
        inv_size, user, drafts = await asyncio.gather(
            database.get_inventory_size(user_id),
            database.get_user(user_id),
            database.get_active_drafts()
        )

        if inv_size + amount > 1000:
            return await interaction.followup.send(f"❌ **Inventory Full!**\nYou currently have {inv_size}/1000 cards. Please `/market sell` or `/exchange` some players before opening more packs.", ephemeral=True)
        
        if user.get('vouchers', 0) < amount:
            return await interaction.followup.send(f"❌ You need {amount} Draft Vouchers to open this pack!\nPlay `/quest_skill_game` or `/quest_h2h` to earn some.", ephemeral=True)

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

        # Helper to pick Pool A card with exact weightings (6% 122, 35% 121, 59% 120)
        def pick_pool_a_weighted(pool_a_list):
            if not pool_a_list:
                return {}
            cards_122 = [p for p in pool_a_list if (p.get('rating') or 0) >= 122]
            cards_121 = [p for p in pool_a_list if (p.get('rating') or 0) == 121]
            cards_120 = [p for p in pool_a_list if (p.get('rating') or 0) <= 120]
            
            tier_roll = random.uniform(0, 100)
            if tier_roll < 6.0 and cards_122:
                return random.choice(cards_122)
            elif tier_roll < 41.0 and cards_121:
                return random.choice(cards_121)
            elif cards_120:
                return random.choice(cards_120)
            elif cards_121:
                return random.choice(cards_121)
            elif cards_122:
                return random.choice(cards_122)
            return random.choice(pool_a_list)

        # Roll for all packs
        for _ in range(amount):
            current_drafts += 1
            pity_counter += 1
            roll = random.uniform(0, 100)
            is_walkout = False
            
            # Pity Triggers — 70th pack guaranteed Pool A, 10th pack guaranteed Pool B
            if pity_counter >= 70:
                roll = random.uniform(0.01, 2.49)  # Force Pool A
            elif pity_counter % 10 == 0:
                if roll > 32.5:
                    roll = random.uniform(2.6, 32.5)  # Force Pool B
            
            if roll <= 2.5:
                # Pool A (2.5% base chance: 6% for 122, 35% for 121, 59% for 120)
                is_walkout = True
                pity_counter = 0  # RESET PITY IMMEDIATELY
                tier_name = "WALKOUT 🌟🌟🌟"
                player_data = pick_pool_a_weighted(d['pool_a'])
            elif roll <= 32.5:
                # Pool B (30% chance: 117-119)
                tier_name = "Elite ✨✨"
                player_data = random.choice(d['pool_b']) if d.get('pool_b') else pick_pool_a_weighted(d['pool_a'])
            else:
                # Pool C (67.5% chance: 110-116)
                tier_name = "Standard"
                player_data = random.choice(d['pool_c']) if d.get('pool_c') else (random.choice(d.get('pool_b', d['pool_a'])))
                
            pulled_players.append(player_data)
            
            p_ovr = player_data.get('rating', 0)
            if p_ovr > highest_ovr:
                highest_ovr = p_ovr
                highest_player = player_data
                is_walkout_pack = is_walkout
                pack_tier_name = tier_name

        # Parallelize database updates and card image generation concurrently
        is_anim = bool(is_walkout_pack or (isinstance(highest_ovr, int) and highest_ovr >= 120))
        db_task = asyncio.gather(
            database.add_vouchers(user_id, -amount),
            database.add_players_to_inventory_batch(user_id, pulled_players),
            database.increment_drafts(user_id, amount),
            database.set_drafts_since_walkout(user_id, pity_counter)
        )
        card_gen_task = asyncio.to_thread(get_or_create_card_bytes, highest_player, 3, is_anim)

        image_result, _ = await asyncio.gather(card_gen_task, db_task)
        image_binary, filename = image_result
        file = discord.File(fp=image_binary, filename=filename or 'card.png') if image_binary else None

        # Check supply asynchronously in background so command response is instantaneous
        async def _check_supply_bg():
            custom_pulled = [p for p in pulled_players if 'custom_' in str(p.get('id', '')) or p.get('supply') is not None]
            if not custom_pulled: return
            exhausted_cards = []
            for p in custom_pulled:
                res = await database.decrement_custom_card_supply(p)
                if res.get('exhausted'):
                    exhausted_cards.append(res.get('card'))
            if exhausted_cards:
                active_drafts = await database.get_active_drafts()
                if active_drafts:
                    for d_num, d_data in list(active_drafts.items()):
                        card_found = False
                        for ex in exhausted_cards:
                            ex_id = str(ex.get('id') or ex.get('custom_id') or ex.get('assetId') or ex.get('cardName', ''))
                            for pool_key in ['pool_a', 'pool_b', 'pool_c']:
                                for card_in_pool in d_data.get(pool_key, []):
                                    pool_card_id = str(card_in_pool.get('id') or card_in_pool.get('custom_id') or card_in_pool.get('assetId') or card_in_pool.get('cardName', ''))
                                    if pool_card_id and pool_card_id == ex_id:
                                        card_found = True
                                        break
                                if card_found: break
                            if card_found: break
                        if card_found or int(d_num) == int(pack):
                            await self.refresh_single_draft(int(d_num))
        asyncio.create_task(_check_supply_bg())
        
        # --- Achievement & Season XP hooks (Non-blocking background) ---
        async def _award_stats_bg():
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
        asyncio.create_task(_award_stats_bg())

        pos = extract_pos(highest_player)
        nation_str = get_nation_display(highest_player)
        club_str = get_club_display(highest_player)
        best_name = highest_player.get('cardName') or highest_player.get('lastName', 'Unknown')
            
        try:
            is_walkout = bool(is_walkout_pack or (isinstance(highest_ovr, int) and highest_ovr >= 120))
            
            if is_walkout:
                walkout_prefix = f"🔥 **{nation_str}** ➔ 🏃 **`{pos}`** ➔ **{club_str}**\n\n"
                desc = f"{walkout_prefix}🌟 **Featured Walkout:** **{best_name}** `({pos})` ({highest_ovr} OVR)\n\n"
                embed_title = f"🌟 WALKOUT REVEAL! ({amount}x Pack)" if amount > 1 else f"🌟 WALKOUT REVEAL! ({highest_ovr} OVR)"
                embed_color = discord.Color.gold()
            else:
                desc = f"✨ **Best Pull:** **{best_name}** `({pos})` ({highest_ovr} OVR)\n\n"
                embed_title = f"🎉 {pack_tier_name} Pack Opened! ({amount}x)"
                embed_color = discord.Color.blue()
            
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
                title=embed_title,
                description=desc,
                color=embed_color
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Pack", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            if file and filename:
                embed.set_image(url=f"attachment://{filename}")
            
            pity_b = 10 - (pity_counter % 10)
            pity_a = max(0, 70 - pity_counter)
            embed.set_footer(text=f"Drafts to Guaranteed Pool B: {pity_b} | Drafts to Guaranteed Pool A: {pity_a}")
            
            if file:
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[Draft] Error presenting pack: {e}")
            await interaction.followup.send(f"🎉 **Pack Opened!** Successfully added **{len(pulled_players)}** cards to your inventory.")

async def setup(bot):
    await bot.add_cog(DraftCog(bot))
