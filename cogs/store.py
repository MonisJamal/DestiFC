import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import database
import datetime
import random
import json
from renderz_api import query_players_by_program, fetch_all_players_by_rating
from auth import is_team_admin_or_owner

THEMES = {
    "default":   {"name": "⚡ Neon Stadium",         "price": 0,           "file": "pitch_bg.jpg"},
    "snow":      {"name": "❄️ Frostbite Winter",      "price": 250_000_000, "file": "pitch_snow.jpg"},
    "lava":      {"name": "🌋 Volcanic Inferno",       "price": 400_000_000, "file": "pitch_lava.jpg"},
    "cyberpunk": {"name": "🤖 Cyberpunk City",         "price": 600_000_000, "file": "pitch_cyber.jpg"},
    "desert":    {"name": "🌙 Arabian Nights",         "price": 750_000_000, "file": "pitch_desert.jpg"},
    "galaxy":    {"name": "🌌 Galaxy Edition",         "price": 1_000_000_000, "file": "pitch_galaxy.jpg"},
    "gold":      {"name": "👑 Champions Final",        "price": 1_500_000_000, "file": "pitch_gold.jpg"},
}

def calculate_player_store_price(player_data: dict) -> int:
    """
    Calculate store price for Pool A players based on OVR, Icon status, and player aura/prestige.
    - 122 Zidane / Mbappe: 5.0B
    - 122 Bellingham: 4.5B
    - Other 122s: 4.0B
    - 121 Superstars/Icons (Ribery, Quaresma, Gerrard, Neuer, Messi, Ronaldo): 2.0B - 2.5B
    - Other 121s: 1.4B - 1.8B
    - 120 Icons/Stars (Totti, Beckham, Kaka, Ronaldinho): 900M - 1.2B
    - Other 120s: 600M - 800M
    """
    name = (player_data.get('cardName') or player_data.get('lastName') or '').strip().lower()
    ovr = int(player_data.get('rating', 120))
    is_icon = 'ICON' in player_data.get('source', '') or 'HERO' in player_data.get('source', '')

    tier_1_aura = ["zidane", "mbappé", "mbappe", "messi", "ronaldo", "pelé", "pele", "cruyff", "nazario", "maradona", "r9"]
    tier_2_aura = ["bellingham", "haaland", "vinicius", "vini", "ronaldinho", "henry", "gullit", "maldini", "yashin", "roberto carlos", "beckham", "totti", "quaresma", "ribery", "riberý", "gerrard", "neuer", "cafu", "kaka", "kaká", "huijsen", "dest"]

    if ovr >= 122:
        if any(s in name for s in tier_1_aura):
            return 5_000_000_000
        elif any(s in name for s in tier_2_aura) or is_icon:
            return 4_500_000_000
        else:
            return 4_000_000_000
    elif ovr == 121:
        if any(s in name for s in tier_1_aura):
            return 2_500_000_000
        elif any(s in name for s in tier_2_aura) or is_icon:
            return 2_000_000_000
        else:
            return 1_500_000_000
    else:  # 120 and other Pool A ratings
        if any(s in name for s in tier_1_aura):
            return 1_200_000_000
        elif any(s in name for s in tier_2_aura) or is_icon:
            return 900_000_000
        else:
            return 650_000_000

class PlayerShopView(discord.ui.View):
    def __init__(self, offers: list, user_id: int):
        super().__init__(timeout=90)
        self.offers = offers
        self.user_id = user_id

        # Add buttons for available slots
        for offer in offers:
            slot = offer["slot"]
            p = offer["player"]
            p_name = p.get('cardName') or p.get('lastName', 'Unknown')
            ovr = p.get('rating', '??')
            price = offer["price"]
            
            price_fmt = f"{price / 1_000_000_000:.1f}B" if price >= 1_000_000_000 else f"{price // 1_000_000}M"
            
            button = discord.ui.Button(
                label=f"Buy Slot {slot}: {ovr} {p_name} ({price_fmt})",
                style=discord.ButtonStyle.success if slot == 1 else discord.ButtonStyle.primary,
                emoji="🛒",
                custom_id=f"buy_slot_{slot}"
            )
            button.callback = self.make_callback(slot, offer)
            self.add_item(button)

    def make_callback(self, slot: int, offer: dict):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ This is not your store session! Use `/store players` to open your own.", ephemeral=True)
            
            await interaction.response.defer()
            user_id = interaction.user.id
            user = await database.get_user(user_id)
            balance = user.get("coins", 0)
            price = offer["price"]
            player = offer["player"]
            p_name = player.get('cardName') or player.get('lastName', 'Unknown')
            ovr = player.get('rating', '??')

            if balance < price:
                return await interaction.followup.send(f"❌ You need **{price:,} Coins** to buy **{ovr} {p_name}**! You only have **{balance:,} Coins**.", ephemeral=True)

            inv_size = await database.get_inventory_size(user_id)
            if inv_size >= 1000:
                return await interaction.followup.send("❌ Your inventory is full (1000/1000 cards). Please quicksell or list cards before buying.", ephemeral=True)

            # Deduct coins and add player
            await database.add_coins(user_id, -price)
            await database.add_player_to_inventory(user_id, player)

            embed = discord.Embed(
                title="🛍️ Player Purchased from Store!",
                description=f"Congratulations! You bought **{ovr} {p_name}** for **{price:,} Coins**!\nCard has been added to your inventory.",
                color=discord.Color.gold()
            )
            img_url = player.get('images', {}).get('playerCardImage') or player.get('images', {}).get('playerImage')
            if img_url:
                embed.set_thumbnail(url=img_url)

            await interaction.followup.send(embed=embed)
        return callback

class StoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.player_shop_rotator.start()

    def cog_unload(self):
        self.player_shop_rotator.cancel()

    async def rotate_player_shop(self, force: bool = False) -> bool:
        """Rotates the 3 Pool A player store offers (scheduled every 4 hours or forced by admin)."""
        try:
            shop_items = await database.get_store_player_shop()
            now = datetime.datetime.now(datetime.timezone.utc)
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")

            needs_refresh = force
            if not shop_items or len(shop_items) < 3:
                needs_refresh = True
            elif not force:
                for item in shop_items:
                    if now_str > item.get("expires_at", ""):
                        needs_refresh = True
                        break

            if not needs_refresh:
                return False

            print("[Store] Rotating 3-hour Pool A Player Shop...")
            # Fetch Pool A candidates (120-122) directly from Supabase database
            pool_a_candidates = await database.get_official_cards_by_rating(120, 122, 100)
            if not pool_a_candidates or len(pool_a_candidates) < 3:
                pool_a_candidates = await database.get_official_cards_by_rating(118, 122, 100)

            if not pool_a_candidates:
                return False

            # Pick 3 unique players across 120-122 with balanced selection
            chosen = []
            seen_names = set()

            high_ovrs = [p for p in pool_a_candidates if int(p.get("rating", 120)) >= 121]
            standard_120s = [p for p in pool_a_candidates if int(p.get("rating", 120)) == 120]
            
            random.shuffle(high_ovrs)
            random.shuffle(standard_120s)
            
            combined_pool = high_ovrs + standard_120s
            random.shuffle(combined_pool)

            for p in combined_pool:
                p_name = (p.get('cardName') or p.get('lastName') or '').strip().lower()
                if p_name and p_name not in seen_names:
                    seen_names.add(p_name)
                    chosen.append(p)
                    if len(chosen) == 3:
                        break

            cfg = await database.get_bot_config()
            rot_hours = float(cfg.get('store_rotation_hours', 3.0))
            expires_at = (now + datetime.timedelta(hours=rot_hours)).strftime("%Y-%m-%d %H:%M:%S")
            new_offers = []
            for i, p in enumerate(chosen, start=1):
                price = calculate_player_store_price(p)
                new_offers.append({
                    "slot": i,
                    "player": p,
                    "price": price,
                    "expires_at": expires_at
                })

            await database.set_store_player_shop(new_offers)
            print(f"[Store] 3-hour Player Shop updated with {len(new_offers)} Pool A players (Expires at {expires_at})")
            return True
        except Exception as e:
            print(f"[Store] Error rotating player shop: {e}")
            return False

    @tasks.loop(minutes=5)
    async def player_shop_rotator(self):
        """Background task checking 4-hour expiration."""
        # The web admin portal queues the same action as /store refresh. The
        # bot owns the actual rotation so its RenderZ selection and pricing
        # rules remain the single source of truth.
        force = await database.consume_portal_job("refresh_store")
        await self.rotate_player_shop(force=force)

    @player_shop_rotator.before_loop
    async def before_player_shop_rotator(self):
        await self.bot.wait_until_ready()

    store_group = app_commands.Group(name="store", description="Official DestiFC Store (Players & Stadium Themes)")

    @store_group.command(name="refresh", description="[Admin/Team] Force refresh the 4-hour Pool A player store immediately")
    async def refresh_store(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ Only Bot Owners & Developer Team Admins can force refresh the store.", ephemeral=True)

        refreshed = await self.rotate_player_shop(force=True)
        if refreshed:
            await interaction.followup.send("✅ Successfully refreshed the 4-hour Pool A Player Store! New 120-122 stars are now live in `/store players`.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Store rotation encountered an issue or pool is currently updating. Please try again in a few seconds.", ephemeral=True)

    @store_group.command(name="players", description="Browse and buy exclusive rotating Pool A players (Refreshes every 4 hours)")
    async def view_players(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Ensure shop is populated
        offers = await database.get_store_player_shop()
        if not offers:
            await self.rotate_player_shop(force=True)
            offers = await database.get_store_player_shop()

        if not offers:
            return await interaction.followup.send("❌ The Player Shop is currently refreshing. Please try again in a few moments.")

        # Calculate time remaining
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_str = offers[0].get("expires_at", "")
        time_rem_str = "4 hours"
        try:
            if isinstance(expires_str, datetime.datetime):
                exp_dt = expires_str.replace(tzinfo=datetime.timezone.utc) if expires_str.tzinfo is None else expires_str
            else:
                exp_dt = datetime.datetime.strptime(str(expires_str), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            diff = exp_dt - now
            if diff.total_seconds() > 0:
                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                time_rem_str = f"{hours}h {minutes}m"
        except Exception:
            pass

        embed = discord.Embed(
            title="🌟 DestiFC Exclusive Player Shop",
            description=(
                f"Directly buy world-class **Pool A Players (120-122 OVR)** using your Coins!\n"
                f"Prices are tuned to player aura, rating, and meta prestige.\n\n"
                f"⏳ **Store Rotation:** Refreshes in `{time_rem_str}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold()
        )

        for offer in offers:
            slot = offer["slot"]
            p = offer["player"]
            name = p.get('cardName') or p.get('lastName', 'Unknown')
            ovr = p.get('rating', '??')
            pos = p.get('position', 'UK')
            prog = str(p.get('source') or 'Special Event').replace('PROGRAM_', '').replace('_', ' ').title()
            price = offer["price"]
            price_fmt = f"{price / 1_000_000_000:.2f}B" if price >= 1_000_000_000 else f"{price // 1_000_000}M"

            embed.add_field(
                name=f"**Slot {slot}:** ⭐ {ovr} {name}",
                value=f"📍 **Position:** `{pos}` | 🏆 **Event:** `{prog}`\n💰 **Price:** **{price_fmt} Coins** (`{price:,}`)",
                inline=False
            )

        # Set thumbnail of slot 1 player
        first_img = offers[0]["player"].get('images', {}).get('playerCardImage') or offers[0]["player"].get('images', {}).get('playerImage')
        if first_img:
            embed.set_thumbnail(url=first_img)

        embed.set_footer(text="Click the buttons below or use /store buy_player <slot> to purchase!")
        view = PlayerShopView(offers, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)

    @store_group.command(name="buy_player", description="Buy a specific player from the store by slot number (1, 2, or 3)")
    @app_commands.choices(slot=[
        app_commands.Choice(name="Slot 1", value=1),
        app_commands.Choice(name="Slot 2", value=2),
        app_commands.Choice(name="Slot 3", value=3),
    ])
    async def buy_player(self, interaction: discord.Interaction, slot: int):
        await interaction.response.defer()
        offers = await database.get_store_player_shop()
        if not offers:
            return await interaction.followup.send("❌ The Player Shop is currently refreshing. Please try again.")

        selected = next((o for o in offers if o["slot"] == slot), None)
        if not selected:
            return await interaction.followup.send(f"❌ Invalid slot `{slot}`. Please check `/store players` for available slots.")

        user_id = interaction.user.id
        user = await database.get_user(user_id)
        balance = user.get("coins", 0)
        price = selected["price"]
        player = selected["player"]
        name = player.get('cardName') or player.get('lastName', 'Unknown')
        ovr = player.get('rating', '??')

        if balance < price:
            return await interaction.followup.send(f"❌ You need **{price:,} Coins** to buy **{ovr} {name}**! You only have **{balance:,} Coins**.", ephemeral=True)

        inv_size = await database.get_inventory_size(user_id)
        if inv_size >= 1000:
            return await interaction.followup.send("❌ Your inventory is full (1000/1000 cards). Please quicksell or list cards before buying.", ephemeral=True)

        # Deduct coins and add player
        await database.add_coins(user_id, -price)
        await database.add_player_to_inventory(user_id, player)

        embed = discord.Embed(
            title="🛍️ Player Purchased from Store!",
            description=f"Congratulations! You bought **{ovr} {name}** for **{price:,} Coins**!\nCard has been added to your inventory.",
            color=discord.Color.green()
        )
        img_url = player.get('images', {}).get('playerCardImage') or player.get('images', {}).get('playerImage')
        if img_url:
            embed.set_thumbnail(url=img_url)

        await interaction.followup.send(embed=embed)

    @store_group.command(name="themes", description="Browse and buy Pitch Themes for your Squad Lineup")
    async def view_themes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        squad = await database.get_squad(user_id)
        unlocked = squad.get("unlocked_themes", ["default"])
        active = squad.get("theme", "default")
        
        desc = "Buy stunning custom pitches for your `/squad view`!\n\n"
        for key, theme in THEMES.items():
            if key in unlocked:
                status = "✅ **Unlocked**"
                if key == active:
                    status += " (Active)"
            else:
                status = f"💰 **{theme['price']:,} Coins**"
                
            desc += f"**{theme['name']}**\nID: `{key}` | Status: {status}\n\n"
            
        embed = discord.Embed(title="🏟️ Pitch Theme Store", description=desc, color=discord.Color.gold())
        embed.set_footer(text="Use /store buy_theme <id> to purchase!")
        await interaction.followup.send(embed=embed)
        
    @store_group.command(name="buy_theme", description="Purchase a pitch theme")
    async def buy_theme(self, interaction: discord.Interaction, theme_id: str):
        await interaction.response.defer()
        theme_id = theme_id.lower()
        
        if theme_id not in THEMES:
            return await interaction.followup.send("❌ Invalid Theme ID. Use `/store themes` to see available options.")
            
        theme = THEMES[theme_id]
        user_id = interaction.user.id
        
        squad = await database.get_squad(user_id)
        unlocked = squad.get("unlocked_themes", ["default"])
        
        if theme_id in unlocked:
            return await interaction.followup.send(f"❌ You already own the **{theme['name']}**! Equip it with `/squad theme {theme_id}`")
            
        user = await database.get_user(user_id)
        balance = user.get("coins", 0)
        price = theme["price"]
        
        if balance < price:
            return await interaction.followup.send(f"❌ You need **{price:,} Coins** to buy this theme! You only have {balance:,}.")
            
        # Deduct coins
        await database.add_coins(user_id, -price)
            
        # Unlock theme
        unlocked.append(theme_id)
        squad["unlocked_themes"] = unlocked
        await database.update_squad(user_id, squad)
        
        await interaction.followup.send(f"🎉 Successfully purchased **{theme['name']}** for {price:,} Coins!\nEquip it now using `/squad theme {theme_id}`!")

    @store_group.command(name="vouchers", description="Exchange Coins for Draft Vouchers (1 for 30M, 10 for 250M!)")
    async def view_vouchers(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        user = await database.get_user(user_id)
        coins = user.get("coins", 0)
        vouchers = user.get("vouchers", 0)
        daily_bought = await database.get_daily_vouchers_bought(user_id)
        
        econ = await database.get_economy_config()
        daily_limit = int(econ.get("voucher_daily_limit", 70) or 70)
        single_price = int(econ.get("voucher_coin_price", 30_000_000) or 30_000_000)
        bundle_price = int(single_price * 8.333333) # ~250M for 30M, approx 17% discount
        if single_price == 30_000_000:
            bundle_price = 250_000_000
        
        daily_left = max(0, daily_limit - daily_bought)

        embed = discord.Embed(
            title="🎟️ Draft Voucher Exchange Shop",
            description=(
                f"Buy **Draft Vouchers 🎫** with your Coins to open more packs in `/draft`!\n\n"
                f"🪙 **Your Balance:** `{coins:,} Coins`\n"
                f"🎟️ **Your Vouchers:** `{vouchers:,} Vouchers`\n"
                f"📊 **Daily Purchase Quota:** `{daily_bought}/{daily_limit}` (Remaining: **{daily_left}**)\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 **Single Voucher:** `{single_price:,} Coins`\n"
                f"🔥 **10x Mega Bundle:** `{bundle_price:,} Coins` — *Save on bulk!*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Click the buttons below or use /store buy_vouchers <amount> | Daily Limit: {daily_limit}")

        view = VoucherShopView(user_id, single_price, bundle_price, daily_limit)
        await interaction.followup.send(embed=embed, view=view)

    @store_group.command(name="buy_vouchers", description="Buy Draft Vouchers with Coins (30M each, 10 for 250M | Max 70/day)")
    @app_commands.describe(amount="Number of Draft Vouchers to purchase")
    async def buy_vouchers_subcmd(self, interaction: discord.Interaction, amount: int):
        await self._process_buy_vouchers(interaction, amount)

    @app_commands.command(name="buy_vouchers", description="Buy Draft Vouchers with Coins (30M each, 10 for 250M | Max 70/day)")
    @app_commands.describe(amount="Number of Draft Vouchers to purchase")
    async def buy_vouchers_rootcmd(self, interaction: discord.Interaction, amount: int):
        await self._process_buy_vouchers(interaction, amount)

    async def _process_buy_vouchers(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send("❌ Please enter a positive number of vouchers.", ephemeral=True)
        
        user_id = interaction.user.id
        econ = await database.get_economy_config()
        daily_limit = int(econ.get("voucher_daily_limit", 70) or 70)
        single_price = int(econ.get("voucher_coin_price", 30_000_000) or 30_000_000)
        bundle_price = 250_000_000 if single_price == 30_000_000 else int(single_price * 8.333333)

        daily_bought = await database.get_daily_vouchers_bought(user_id)
        daily_left = max(0, daily_limit - daily_bought)

        if daily_left <= 0:
            return await interaction.followup.send(
                f"❌ **Daily Limit Reached!**\nYou have reached the limit of **{daily_limit} Draft Vouchers per day**.\nLimit resets daily at 00:00 UTC.",
                ephemeral=True
            )

        if amount > daily_left:
            return await interaction.followup.send(
                f"❌ **Daily Limit Exceeded!**\nYou have bought **{daily_bought}/{daily_limit}** vouchers today.\nYou can only buy **{daily_left} more** vouchers today (Limit resets at 00:00 UTC).",
                ephemeral=True
            )

        user = await database.get_user(user_id)
        balance = user.get("coins", 0)

        # 10 for bundle_price, single for single_price
        bundles_10 = amount // 10
        remainder = amount % 10
        total_cost = (bundles_10 * bundle_price) + (remainder * single_price)

        if balance < total_cost:
            return await interaction.followup.send(
                f"❌ You need **{total_cost:,} Coins** to buy **{amount}x Draft Vouchers**!\nYour current balance: **{balance:,} Coins**.",
                ephemeral=True
            )

        await database.add_coins(user_id, -total_cost)
        await database.add_vouchers(user_id, amount)
        await database.record_vouchers_bought(user_id, amount)

        new_daily_bought = daily_bought + amount
        new_daily_left = max(0, daily_limit - new_daily_bought)

        savings_msg = f" *(Bundle Discount Applied!)*" if bundles_10 > 0 else ""
        embed = discord.Embed(
            title="🎟️ Vouchers Purchased!",
            description=(
                f"Successfully purchased **{amount}x Draft Vouchers 🎫** for **{total_cost:,} Coins**!{savings_msg}\n\n"
                f"📊 **Daily Quota:** `{new_daily_bought}/{daily_limit}` (Remaining Allowance: **{new_daily_left}**)\n"
                f"Use `/draft` to open packs now!"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


class VoucherShopView(discord.ui.View):
    def __init__(self, user_id: int, single_price: int = 30_000_000, bundle_price: int = 250_000_000, daily_limit: int = 70):
        super().__init__(timeout=90)
        self.user_id = user_id
        self.single_price = single_price
        self.bundle_price = bundle_price
        self.daily_limit = daily_limit

    async def execute_purchase(self, interaction: discord.Interaction, amount: int, cost: int):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your shop menu. Use `/store vouchers` to open your own.", ephemeral=True)

        await interaction.response.defer()
        user_id = interaction.user.id
        daily_bought = await database.get_daily_vouchers_bought(user_id)
        daily_left = max(0, self.daily_limit - daily_bought)

        if daily_left <= 0:
            return await interaction.followup.send(
                f"❌ **Daily Limit Reached!**\nYou have already purchased your maximum allowance of **{self.daily_limit} Draft Vouchers** today.\nLimit resets daily at 00:00 UTC.",
                ephemeral=True
            )

        if amount > daily_left:
            return await interaction.followup.send(
                f"❌ **Daily Limit Exceeded!**\nYou have bought **{daily_bought}/{self.daily_limit}** vouchers today.\nYou can only buy **{daily_left} more** vouchers today (Limit: {self.daily_limit}/day).",
                ephemeral=True
            )

        user = await database.get_user(user_id)
        balance = user.get("coins", 0)

        if balance < cost:
            return await interaction.followup.send(f"❌ You need **{cost:,} Coins** to buy **{amount}x Vouchers**! You have **{balance:,} Coins**.", ephemeral=True)

        await database.add_coins(user_id, -cost)
        await database.add_vouchers(user_id, amount)
        await database.record_vouchers_bought(user_id, amount)

        new_daily_bought = daily_bought + amount
        new_daily_left = max(0, self.daily_limit - new_daily_bought)

        embed = discord.Embed(
            title="🎉 Vouchers Purchased!",
            description=(
                f"You successfully bought **{amount}x Draft Vouchers 🎫** for **{cost:,} Coins**!\n\n"
                f"🪙 **New Balance:** `{(balance - cost):,} Coins`\n"
                f"🎟️ **Total Vouchers:** `{user.get('vouchers', 0) + amount} Vouchers`\n"
                f"📊 **Daily Quota:** `{new_daily_bought}/{self.daily_limit}` (Remaining: **{new_daily_left}**)"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Buy 1x Voucher", style=discord.ButtonStyle.primary, emoji="🎟️")
    async def buy_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_purchase(interaction, 1, self.single_price)

    @discord.ui.button(label="Buy 10x Vouchers (Save on Bundle!)", style=discord.ButtonStyle.success, emoji="🔥")
    async def buy_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_purchase(interaction, 10, self.bundle_price)

    @discord.ui.button(label="Buy 20x Vouchers", style=discord.ButtonStyle.success, emoji="👑")
    async def buy_20(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_purchase(interaction, 20, self.bundle_price * 2)


async def setup(bot):
    await bot.add_cog(StoreCog(bot))

