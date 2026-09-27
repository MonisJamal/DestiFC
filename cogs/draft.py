import discord
from discord.ext import commands, tasks
from discord import app_commands
import io
import random
import asyncio
import datetime

import database
from renderz_api import query_players_by_program
from card_generator import generate_card
from maps import nation_map, club_map

class DraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.draft_rotator.start()

    def cog_unload(self):
        self.draft_rotator.cancel()

    @tasks.loop(hours=1)
    async def draft_rotator(self):
        drafts = await database.get_active_drafts()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        needs_refresh = False
        if not drafts:
            needs_refresh = True
        else:
            # Check if expired
            for d in drafts.values():
                if now > d["expires_at"]:
                    needs_refresh = True
                    break
                    
        if needs_refresh:
            print("[Draft] Rotating and generating new Draft Pools...")
            
            # Fetch across the entire catalog (both old and new events/programs)
            def fetch_all(min_r, max_r, max_target=100):
                all_p = []
                # Fetch newest first
                for offset in range(0, max_target, 24):
                    batch = query_players_by_program("", min_rating=min_r, max_rating=max_r, size=24, from_offset=offset)
                    if not batch: break
                    all_p.extend(batch)
                # Also sample from deeper/older pages so older promo cards appear
                for offset in [100, 200, 300, 500, 800]:
                    batch = query_players_by_program("", min_rating=min_r, max_rating=max_r, size=24, from_offset=offset)
                    if batch:
                        all_p.extend(batch)
                return all_p
            
            pool_122 = fetch_all(122, 122, max_target=80)
            pool_121 = fetch_all(121, 121, max_target=80)
            pool_120 = fetch_all(120, 120, max_target=150)
            pool_117 = fetch_all(117, 119, max_target=150)
            pool_112 = fetch_all(112, 116, max_target=150)
            
            if not pool_122 or not pool_121 or not pool_120:
                print("[Draft] Not enough 120+ players fetched, skipping rotation.")
                return
            if not pool_117: pool_117 = pool_120  # fallback
            if not pool_112: pool_112 = pool_117  # fallback
            
            new_drafts = {}
            expires = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            
            for i in range(1, 4):
                # Each draft gets exactly 1x 122, 1x 121, 1x 120
                featured_a = [
                    random.choice(pool_122),
                    random.choice(pool_121),
                    random.choice(pool_120)
                ]
                new_drafts[i] = {
                    "pool_a": featured_a,
                    "pool_b": random.sample(pool_117, min(10, len(pool_117))),
                    "pool_c": random.sample(pool_112, min(30, len(pool_112))),
                    "expires_at": expires
                }
            await database.set_active_drafts(new_drafts)
            print(f"[Draft] Successfully generated 3 new drafts! Expires: {expires}")

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
        drafts = await database.get_active_drafts()
        if not drafts or str(pack) not in drafts and pack not in drafts:
            await interaction.response.send_message("❌ Drafts are currently rotating. Please wait a minute.", ephemeral=True)
            return
            
        d = drafts.get(pack) or drafts.get(str(pack))
        
        embed = discord.Embed(title=f"📦 Draft Pack {pack} Info", description=f"**Expires:** {d['expires_at']}", color=0x00ff00)
        
        pool_a_names = [f"**{p.get('cardName') or p.get('lastName')} ({p.get('rating')})**" for p in d['pool_a']]
        pool_b_names = [f"{p.get('cardName') or p.get('lastName')} ({p.get('rating')})" for p in d['pool_b']]
        
        embed.add_field(name="🌟 Featured Walkouts (120-122)", value="\n".join(pool_a_names), inline=False)
        embed.add_field(name="✨ Elite Pulls (117-119)", value=", ".join(pool_b_names), inline=False)
        embed.add_field(name="🟦 Standard Pulls (112-116)", value=f"*{len(d['pool_c'])} other players possible...*", inline=False)
        
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="draft", description="Open a specific draft pack")
    @app_commands.choices(pack=[
        app_commands.Choice(name="Draft Pack 1", value=1),
        app_commands.Choice(name="Draft Pack 2", value=2),
        app_commands.Choice(name="Draft Pack 3", value=3)
    ])
    async def draft(self, interaction: discord.Interaction, pack: int, amount: int = 1):
        if amount < 1 or amount > 10:
            await interaction.response.send_message("❌ You can only open between 1 and 10 packs at a time.", ephemeral=True)
            return

        user_id = interaction.user.id
        user = await database.get_user(user_id)
        
        if user.get('vouchers', 0) < amount:
            await interaction.response.send_message(f"❌ You need {amount} Draft Vouchers to open this pack!\nPlay `/quest_skill_game` or `/quest_h2h` to earn some.", ephemeral=True)
            return

        drafts = await database.get_active_drafts()
        if not drafts or (str(pack) not in drafts and pack not in drafts):
            await interaction.response.send_message("❌ Drafts are currently rotating. Please wait a minute.", ephemeral=True)
            return
            
        d = drafts.get(pack) or drafts.get(str(pack))
        
        # Validate pools aren't empty
        if not d.get('pool_a') or not d.get('pool_b') or not d.get('pool_c'):
            await interaction.response.send_message("❌ This draft pack has empty pools. The bot will refresh them shortly!", ephemeral=True)
            return

        await interaction.response.defer()
        
        # Deduct vouchers
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
            
            # Pity Triggers
            if current_drafts % 70 == 0:
                roll = random.uniform(0, 0.1) # Force Pool A
            elif current_drafts % 10 == 0:
                if roll > 0.1: # If they didn't naturally hit Pool A
                    roll = random.uniform(0.1, 5.0) # Force Pool B
            
            if roll <= 0.10:
                is_walkout = True
                tier_name = "WALKOUT 🌟🌟🌟"
                player_data = random.choice(d['pool_a'])
            elif roll <= 5.10:
                tier_name = "Elite"
                player_data = random.choice(d['pool_b'])
            else:
                tier_name = "Standard"
                player_data = random.choice(d['pool_c'])
                
            pulled_players.append(player_data)
            await database.add_player_to_inventory(user_id, player_data)
            
            p_ovr = player_data.get('rating', 0)
            if p_ovr > highest_ovr:
                highest_ovr = p_ovr
                highest_player = player_data
                is_walkout_pack = is_walkout
                pack_tier_name = tier_name

        await database.increment_drafts(user_id, amount)

        msg = await interaction.followup.send(f"🚨 **{interaction.user.display_name} IS OPENING {amount}x PACKS...** 🚨")
        await asyncio.sleep(1)
        
        pos = highest_player.get('position', '??')
        n_id = highest_player.get('nation', {}).get('id')
        c_id = highest_player.get('club', {}).get('id')
        
        nation_str = nation_map.get(n_id, f"🌍 Nation ({n_id})")
        club_str = club_map.get(c_id, f"🛡️ Club ({c_id})")
        best_name = highest_player.get('cardName') or highest_player.get('lastName', 'Unknown')
        
        if is_walkout_pack:
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
                
                if amount > 1:
                    desc += "**Other Pulls:**\n"
                    others = sorted([p for p in pulled_players if p != highest_player], key=lambda x: x.get('rating', 0), reverse=True)
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
