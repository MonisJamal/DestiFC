import discord
from discord.ext import commands, tasks
from discord import app_commands
import database
import json
import time
import datetime
import random
import asyncio
from auth import is_team_admin_or_owner

class BlackMarketView(discord.ui.View):
    def __init__(self, bot, session_id: str, voucher_deals: list, player_deals: list):
        super().__init__(timeout=3600)
        self.bot = bot
        self.session_id = session_id
        self.voucher_deals = voucher_deals
        self.player_deals = player_deals

        # Add select menu for deals
        options = []
        for vd in voucher_deals:
            options.append(discord.SelectOption(
                label=f"🎟️ {vd['title']} (50% OFF)",
                value=f"voucher_{vd['id']}",
                description=f"{vd['vouchers']} Vouchers for {vd['discount_price']:,} coins (Orig: {vd['original_price']:,})"
            ))
        for pd in player_deals:
            options.append(discord.SelectOption(
                label=f"⭐ {pd['name']} ({pd['ovr']} OVR) -{pd['discount_pct']}% OFF",
                value=f"player_{pd['id']}",
                description=f"Price: {pd['discount_price']:,} coins (Orig: {pd['original_price']:,})"
            ))

        if options:
            self.select_menu = discord.ui.Select(
                placeholder="🛒 Select a Black Market item to purchase...",
                min_values=1,
                max_values=1,
                options=options[:25]
            )
            self.select_menu.callback = self.on_select_deal
            self.add_item(self.select_menu)

    async def on_select_deal(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        deal_key = self.select_menu.values[0]

        # Strictly check if market is still open and within 1-hour window
        cfg = await database.get_black_market_config()
        now = datetime.datetime.now(datetime.timezone.utc)
        closes_at_str = cfg.get("closes_at")
        is_closed = not cfg.get("is_active", False)
        if closes_at_str:
            try:
                closes_dt = datetime.datetime.fromisoformat(str(closes_at_str).replace("Z", "+00:00"))
                if now >= closes_dt:
                    is_closed = True
            except Exception:
                pass

        if is_closed:
            return await interaction.followup.send(
                "🔒 **THE BLACK MARKET HAS CLOSED!**\n"
                "The smuggler has already packed up and fled. This deal is no longer active!",
                ephemeral=True
            )

        # Atomically claim slot in database before charging or granting rewards
        claimed = await database.claim_black_market_purchase(user_id, self.session_id, deal_key)
        if not claimed:
            return await interaction.followup.send("❌ You have already claimed this limited Black Market deal during this session!", ephemeral=True)

        user = await database.get_user(user_id)
        balance = user.get("coins", 0)

        # Voucher deal purchase
        if deal_key.startswith("voucher_"):
            deal_id = deal_key.replace("voucher_", "")
            deal = next((d for d in self.voucher_deals if str(d['id']) == deal_id), None)
            if not deal:
                await database.cancel_black_market_purchase(user_id, self.session_id, deal_key)
                return await interaction.followup.send("❌ Deal no longer available.", ephemeral=True)

            cost = int(deal['discount_price'])
            if balance < cost:
                await database.cancel_black_market_purchase(user_id, self.session_id, deal_key)
                return await interaction.followup.send(f"❌ Insufficient coins! You need **{cost:,} Coins**, but you only have **{balance:,}**.", ephemeral=True)

            await database.add_coins(user_id, -cost)
            await database.add_vouchers(user_id, int(deal['vouchers']))

            return await interaction.followup.send(
                f"🎉 **BLACK MARKET DEAL PURCHASED!**\n"
                f"Purchased **{deal['title']}** (+{deal['vouchers']} Draft Vouchers) for **{cost:,} Coins** (50% OFF)!\n"
                f"Remaining Coins: **{balance - cost:,}** 💰",
                ephemeral=True
            )

        # Player deal purchase
        elif deal_key.startswith("player_"):
            deal_id = deal_key.replace("player_", "")
            deal = next((d for d in self.player_deals if str(d['id']) == deal_id), None)
            if not deal:
                await database.cancel_black_market_purchase(user_id, self.session_id, deal_key)
                return await interaction.followup.send("❌ Deal no longer available.", ephemeral=True)

            cost = int(deal['discount_price'])
            if balance < cost:
                await database.cancel_black_market_purchase(user_id, self.session_id, deal_key)
                return await interaction.followup.send(f"❌ Insufficient coins! You need **{cost:,} Coins**, but you only have **{balance:,}**.", ephemeral=True)

            player_data = deal.get("player_data")
            if not player_data:
                await database.cancel_black_market_purchase(user_id, self.session_id, deal_key)
                return await interaction.followup.send("❌ Card data unavailable.", ephemeral=True)

            await database.add_coins(user_id, -cost)
            await database.add_player_to_inventory(user_id, player_data)

            pos = player_data.get('position', 'ST')
            return await interaction.followup.send(
                f"🔥 **BLACK MARKET PLAYER SECURED!**\n"
                f"You bought **{deal['name']} ({deal['ovr']} OVR, {pos})** with a **{deal['discount_pct']}% discount** for **{cost:,} Coins**!\n"
                f"Card added to your Club inventory!",
                ephemeral=True
            )

class BlackMarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.market_scheduler.start()

    def cog_unload(self):
        self.market_scheduler.cancel()

    async def generate_random_deals(self) -> tuple[list, list]:
        """Generates 50% half-price vouchers and 5 random 120+ players with 30-45% discounts."""
        # 1. Voucher Deals (50% Half Price based on 20M/voucher: 10M discounted!)
        voucher_deals = [
            {"id": "v1", "title": "10x Draft Vouchers Pack", "vouchers": 10, "original_price": 200_000_000, "discount_price": 100_000_000, "discount_pct": 50},
            {"id": "v2", "title": "25x Draft Vouchers Bundle", "vouchers": 25, "original_price": 500_000_000, "discount_price": 250_000_000, "discount_pct": 50},
            {"id": "v3", "title": "50x Mega Voucher Hoard", "vouchers": 50, "original_price": 1_000_000_000, "discount_price": 500_000_000, "discount_pct": 50},
        ]

        # 2. Pick 5 random 120+ players with variable 30-45% discounts (guaranteeing at least 3 cards with OVR >= 122)
        cards_122_plus = await database.get_official_cards_by_rating(122, 125, 100)
        cards_120_plus = await database.get_official_cards_by_rating(120, 125, 100)
        random.shuffle(cards_122_plus)
        random.shuffle(cards_120_plus)

        player_deals = []
        seen = set()

        # Step A: Pick at least 3 cards with rating >= 122
        for c in cards_122_plus:
            p_name = (c.get('cardName') or c.get('lastName') or '').strip()
            if not p_name or p_name.lower() in seen:
                continue
            seen.add(p_name.lower())

            ovr = int(c.get('rating', 122))
            base_price = 4_000_000_000  # 122+ = 4.0B base
            discount_pct = random.randint(30, 45)  # 30-45% variable discount
            discount_price = int(base_price * (1.0 - (discount_pct / 100.0)))

            deal_id = f"p_{len(player_deals)+1}_{ovr}"
            player_deals.append({
                "id": deal_id,
                "name": p_name,
                "ovr": ovr,
                "original_price": base_price,
                "discount_price": discount_price,
                "discount_pct": discount_pct,
                "player_data": c
            })
            if len(player_deals) >= 3:
                break

        # Step B: Pick remaining 2 cards from 120+ pool (deduplicated)
        for c in cards_120_plus:
            p_name = (c.get('cardName') or c.get('lastName') or '').strip()
            if not p_name or p_name.lower() in seen:
                continue
            seen.add(p_name.lower())

            ovr = int(c.get('rating', 120))
            base_price = 1_000_000_000 if ovr == 120 else (2_000_000_000 if ovr == 121 else 4_000_000_000)
            discount_pct = random.randint(30, 45)
            discount_price = int(base_price * (1.0 - (discount_pct / 100.0)))

            deal_id = f"p_{len(player_deals)+1}_{ovr}"
            player_deals.append({
                "id": deal_id,
                "name": p_name,
                "ovr": ovr,
                "original_price": base_price,
                "discount_price": discount_price,
                "discount_pct": discount_pct,
                "player_data": c
            })
            if len(player_deals) >= 5:
                break

        return voucher_deals, player_deals

    async def trigger_market_opening(self, force: bool = False, custom_vouchers: list = None, custom_players: list = None):
        """Opens the Black Market for 1 hour, notifies users, and creates interactive shop."""
        cfg = await database.get_black_market_config()
        now = datetime.datetime.now(datetime.timezone.utc)
        session_id = now.strftime("%Y%m%d_%H%M")
        closes_at = now + datetime.timedelta(hours=1)

        # Always generate fresh random 120+ superstar deals on each opening session
        if custom_players is not None:
            p_deals = custom_players
        else:
            _, p_deals = await self.generate_random_deals()

        if custom_vouchers is not None:
            v_deals = custom_vouchers
        else:
            v_deals, _ = await self.generate_random_deals()

        await database.update_black_market_config(
            is_active=True,
            opens_at=now.isoformat(),
            closes_at=closes_at.isoformat(),
            voucher_packages=v_deals,
            player_deals=p_deals
        )

        # When manually or automatically opened, advance the schedule so today's drop time is refreshed/completed
        try:
            p_sched = await database.get_db()
            if now.hour < 20:
                next_hour = random.randint(now.hour + 2, 22)
                next_min = random.randint(0, 59)
                next_date_str = now.strftime("%Y-%m-%d")
            else:
                tomorrow = now + datetime.timedelta(days=1)
                next_date_str = tomorrow.strftime("%Y-%m-%d")
                next_hour = random.randint(2, 21)
                next_min = random.randint(0, 59)

            new_sched = {
                "date": next_date_str,
                "target_hour": next_hour,
                "target_min": next_min,
                "executed": False
            }
            await p_sched.execute(
                "INSERT INTO system_settings (key, value) VALUES ('black_market_schedule', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                json.dumps(new_sched)
            )
            print(f"[BlackMarket] Refreshed future drop schedule: {next_date_str} at {next_hour:02d}:{next_min:02d} UTC")
        except Exception as ex_sched:
            print(f"[BlackMarket] Error updating schedule on open: {ex_sched}")

        # Broadcast to all configured Black Market channels across multiple servers
        channels = []
        raw_channels = cfg.get("channels") or []
        if isinstance(raw_channels, str):
            raw_channels = [c.strip() for c in raw_channels.replace(',', ' ').split() if c.strip()]

        for raw_id in raw_channels:
            try:
                cid = int(str(raw_id).strip())
                ch = self.bot.get_channel(cid)
                if not ch:
                    try:
                        ch = await self.bot.fetch_channel(cid)
                    except Exception as fe:
                        print(f"[BlackMarket] Could not fetch channel {cid}: {fe}")
                if ch:
                    channels.append(ch)
            except Exception:
                pass

        # If no specific channels configured, fallback to drops channel or first available text channel
        if not channels:
            drops_cfg = await database.get_db()
            r = await drops_cfg.fetchrow("SELECT value FROM system_settings WHERE key = 'drops_config'")
            ch_id = None
            if r and r['value']:
                try:
                    dc = json.loads(r['value']) if isinstance(r['value'], str) else r['value']
                    ch_id = dc.get("channel_id")
                except Exception: pass
            if ch_id:
                try:
                    fb = self.bot.get_channel(int(ch_id)) or await self.bot.fetch_channel(int(ch_id))
                    if fb: channels.append(fb)
                except Exception: pass

        if not channels:
            for g in self.bot.guilds:
                for c in g.text_channels:
                    if c.permissions_for(g.me).send_messages:
                        channels.append(c)
                        break

        # Format ping string according to panel settings (separate role ping for Black Market)
        ping_type = str(cfg.get("ping_type") or "none").lower()
        role_id = str(cfg.get("role_id") or "").strip()

        ping_str = ""
        if ping_type == "everyone":
            ping_str = "@everyone "
        elif ping_type == "here":
            ping_str = "@here "
        elif ping_type == "role" and role_id:
            ping_str = f"<@&{role_id}> "

        embed = discord.Embed(
            title="🕵️‍♂️ THE SECRET BLACK MARKET HAS OPENED! 🕵️‍♂️",
            description=(
                f"🚨 **EMERGENCY SMUGGLER ALERT!** 🚨\n\n"
                f"The shadowy Black Market has surfaced in DestiFC! It will remain open for **EXACTLY 1 HOUR** before vanishing into the shadows.\n\n"
                f"🔥 **FLASH DEALS:**\n"
                f"• 🎟️ **Draft Vouchers at 50% HALF PRICE!**\n"
                f"• ⭐ **5 Rare 120+ Superstar Cards with 30%–45% DISCOUNTS!**\n\n"
                f"⏳ **CLOSES AT:** <t:{int(closes_at.timestamp())}:R> (<t:{int(closes_at.timestamp())}:t>)\n\n"
                f"👉 Select from the interactive menu below to grab your contraband loot!"
            ),
            color=discord.Color.dark_purple()
        )
        embed.set_footer(text="DestiFC Black Market • 1-Hour Flash Event")

        for ch in channels:
            try:
                view = BlackMarketView(self.bot, session_id, v_deals, p_deals)
                msg_content = f"{ping_str}🚨 **THE BLACK MARKET IS OPEN FOR 1 HOUR! (50% OFF Vouchers & Discounted 120+ Players)**".strip()
                await ch.send(content=msg_content, embed=embed, view=view)
                print(f"[BlackMarket] Announce message sent to #{ch.name} (Guild: {ch.guild.name})!")
            except Exception as e:
                print(f"[BlackMarket] Failed to send announce to #{ch.name}: {e}")

    @tasks.loop(minutes=1)
    async def market_scheduler(self):
        """Schedules random daily 1-hour opening and auto-closes when expired."""
        try:
            cfg = await database.get_black_market_config()
            now = datetime.datetime.now(datetime.timezone.utc)

            # 1. Auto close if past closes_at & immediately schedule the NEXT drop
            if cfg.get("is_active"):
                closes_at_str = cfg.get("closes_at")
                if closes_at_str:
                    try:
                        closes_dt = datetime.datetime.fromisoformat(str(closes_at_str).replace("Z", "+00:00"))
                        if now >= closes_dt:
                            # Close the market
                            await database.update_black_market_config(
                                is_active=False,
                                opens_at=None,
                                closes_at=None,
                                voucher_packages=cfg.get("voucher_packages", []),
                                player_deals=cfg.get("player_deals", [])
                            )
                            print("[BlackMarket] 1-hour session has concluded. Market closed.")

                            # AUTOMATICALLY generate the next random drop time in the future!
                            # If remaining hours in today allow (> 2 hours remaining before 22:00), schedule later today;
                            # Otherwise schedule for tomorrow.
                            p = await database.get_db()
                            if now.hour < 20:
                                next_hour = random.randint(now.hour + 2, 22)
                                next_min = random.randint(0, 59)
                                next_date_str = now.strftime("%Y-%m-%d")
                            else:
                                tomorrow = now + datetime.timedelta(days=1)
                                next_date_str = tomorrow.strftime("%Y-%m-%d")
                                next_hour = random.randint(2, 21)
                                next_min = random.randint(0, 59)

                            new_sched = {
                                "date": next_date_str,
                                "target_hour": next_hour,
                                "target_min": next_min,
                                "executed": False
                            }
                            await p.execute(
                                "INSERT INTO system_settings (key, value) VALUES ('black_market_schedule', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                                json.dumps(new_sched)
                            )
                            print(f"[BlackMarket] Automatically rolled NEXT drop time: {next_date_str} at {next_hour:02d}:{next_min:02d} UTC")
                            cfg["is_active"] = False
                    except Exception as e:
                        print(f"[BlackMarket] Error parsing close time: {e}")

            # 2. Check current schedule from DB
            p = await database.get_db()
            sched_row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'black_market_schedule'")
            today_str = now.strftime("%Y-%m-%d")
            
            sched = {}
            if sched_row and sched_row['value']:
                val = sched_row['value']
                sched = json.loads(val) if isinstance(val, str) else val

            # If no schedule exists at all or date is older than today, create a valid future schedule
            if not sched or sched.get("date", "") < today_str:
                # Pick a random future time today if possible
                min_hour = max(2, now.hour + 1)
                if min_hour <= 22:
                    rand_hour = random.randint(min_hour, 22)
                    sched_date = today_str
                else:
                    tomorrow = now + datetime.timedelta(days=1)
                    sched_date = tomorrow.strftime("%Y-%m-%d")
                    rand_hour = random.randint(2, 21)

                rand_min = random.randint(0, 59)
                sched = {
                    "date": sched_date,
                    "target_hour": rand_hour,
                    "target_min": rand_min,
                    "executed": False
                }
                await p.execute(
                    "INSERT INTO system_settings (key, value) VALUES ('black_market_schedule', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    json.dumps(sched)
                )
                print(f"[BlackMarket] Initialized schedule for {sched_date} at {rand_hour:02d}:{rand_min:02d} UTC")

            # 3. Check if scheduled drop moment has been reached
            if not sched.get("executed", False) and not cfg.get("is_active", False):
                sched_date = sched.get("date", "")
                target_h = int(sched.get("target_hour", 0))
                target_m = int(sched.get("target_min", 0))

                # Build exact scheduled target timestamp
                try:
                    s_year, s_month, s_day = [int(x) for x in sched_date.split("-")]
                    target_dt = datetime.datetime(s_year, s_month, s_day, target_h, target_m, 0, tzinfo=datetime.timezone.utc)
                    # ONLY fire when current time has actually reached or passed target_dt
                    if now >= target_dt:
                        sched["executed"] = True
                        await p.execute(
                            "INSERT INTO system_settings (key, value) VALUES ('black_market_schedule', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                            json.dumps(sched)
                        )
                        print(f"[BlackMarket] Scheduled time reached ({sched_date} {target_h:02d}:{target_m:02d} UTC). Triggering opening!")
                        await self.trigger_market_opening()
                except Exception as ex_dt:
                    print(f"[BlackMarket] Error comparing scheduled time: {ex_dt}")
        except Exception as e:
            print(f"[BlackMarket Loop Error] {e}")

    @market_scheduler.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()


    @app_commands.command(name="admin_blackmarket_open", description="Admin: Manually open the Black Market for 1 hour right now")
    async def admin_open(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

        await self.trigger_market_opening(force=True)
        await interaction.followup.send("✅ The Black Market has been opened for 1 hour and server-wide announcement broadcasted!", ephemeral=True)

    @app_commands.command(name="admin_blackmarket_close", description="Admin: Manually close the Black Market immediately")
    async def admin_close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

        cfg = await database.get_black_market_config()
        if not cfg.get("is_active"):
            return await interaction.followup.send("ℹ️ The Black Market is already closed.", ephemeral=True)

        await database.update_black_market_config(
            is_active=False,
            opens_at=None,
            closes_at=None,
            voucher_packages=cfg.get("voucher_packages", []),
            player_deals=cfg.get("player_deals", [])
        )
        await interaction.followup.send("🔒 The Black Market has been closed manually! Purchases and `/blackmarket` access are now locked.", ephemeral=True)

    # -----------------------------------------------------------------
    # OWNER VIP SPECIAL MARKET (MANUAL ONLY - NEVER RANDOM)
    # -----------------------------------------------------------------
    async def trigger_special_market_opening(self, duration_minutes: int = None):
        """Manually opens the VIP Special Market for customizable duration (default 60 mins)."""
        cfg = await database.get_special_market_config()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        mins = duration_minutes
        if mins is None:
            mins = int(cfg.get("duration_minutes") or 60)
        mins = max(1, min(1440, mins))  # between 1 min and 24 hours

        closes_at = now + datetime.timedelta(minutes=mins)
        session_id = now.strftime("%Y%m%d_%H%M")

        await database.update_special_market_config(
            is_active=True,
            opens_at=now.isoformat(),
            closes_at=closes_at.isoformat(),
            title=cfg.get("title", "👑 OWNER VIP SPECIAL MARKET 👑"),
            custom_rewards=cfg.get("custom_rewards", []),
            channels=cfg.get("channels", []),
            role_id=cfg.get("role_id", ""),
            ping_type=cfg.get("ping_type", "none"),
            duration_minutes=mins
        )

        channels = []
        raw_channels = cfg.get("channels") or []
        if isinstance(raw_channels, str):
            try:
                raw_channels = json.loads(raw_channels)
            except Exception:
                raw_channels = [c.strip() for c in raw_channels.replace(',', ' ').split() if c.strip()]

        for raw_id in (raw_channels if isinstance(raw_channels, list) else [raw_channels]):
            try:
                cid = int(str(raw_id).strip())
                ch = self.bot.get_channel(cid)
                if not ch:
                    try:
                        ch = await self.bot.fetch_channel(cid)
                    except Exception as fe:
                        print(f"[SpecialMarket] Could not fetch configured channel {cid}: {fe}")
                if ch:
                    channels.append(ch)
            except Exception as ex_parse:
                print(f"[SpecialMarket] Channel ID parse error ({raw_id}): {ex_parse}")

        if not channels:
            # Fallback to standard black market channels
            bm_cfg = await database.get_black_market_config()
            for raw_id in (bm_cfg.get("channels") or []):
                try:
                    cid = int(str(raw_id).strip())
                    ch = self.bot.get_channel(cid)
                    if not ch:
                        try:
                            ch = await self.bot.fetch_channel(cid)
                        except Exception:
                            pass
                    if ch: channels.append(ch)
                except Exception: pass

        if not channels:
            # Fallback to system drops channel
            drops_cfg = await database.get_db()
            r = await drops_cfg.fetchrow("SELECT value FROM system_settings WHERE key = 'drops_config'")
            ch_id = None
            if r and r['value']:
                try:
                    dc = json.loads(r['value']) if isinstance(r['value'], str) else r['value']
                    ch_id = dc.get("channel_id")
                except Exception: pass
            if ch_id:
                try:
                    fb = self.bot.get_channel(int(ch_id)) or await self.bot.fetch_channel(int(ch_id))
                    if fb: channels.append(fb)
                except Exception: pass

        if not channels:
            # Last resort fallback: first writable channel in connected guilds
            for g in self.bot.guilds:
                for c in g.text_channels:
                    if c.permissions_for(g.me).send_messages:
                        channels.append(c)
                        break

        ping_type = str(cfg.get("ping_type") or "none").lower()
        role_id = str(cfg.get("role_id") or "").strip()

        ping_str = ""
        if ping_type == "everyone":
            ping_str = "@everyone "
        elif ping_type == "here":
            ping_str = "@here "
        elif ping_type == "role" and role_id:
            ping_str = f"<@&{role_id}> "

        rewards = cfg.get("custom_rewards", [])
        title = cfg.get("title", "👑 OWNER VIP SPECIAL MARKET 👑")

        # Format duration string nicely
        if mins >= 60:
            hrs = mins // 60
            remaining_mins = mins % 60
            dur_str = f"{hrs} HOUR{'S' if hrs > 1 else ''}" + (f" {remaining_mins} MINS" if remaining_mins else "")
        else:
            dur_str = f"{mins} MINUTES"

        # Build itemized deal preview in embed
        deals_preview = []
        for r in rewards:
            cost = int(r.get("cost_coins", 0))
            deals_preview.append(f"• **{r.get('title', 'VIP Deal')}**: `🪙 {cost:,} Coins`")

        embed = discord.Embed(
            title=f"👑 {title} HAS SURFACED! 👑",
            description=(
                f"🚨 **EXCLUSIVE HIGH-ROLLER MARKET UNLOCKED!** 🚨\n\n"
                f"An exclusive VIP bazaar curated by the Owner is open for **{dur_str}**!\n\n"
                f"🔥 **FEATURED VIP DEALS:**\n" +
                ("\n".join(deals_preview) if deals_preview else "*Select items below to purchase!*") +
                f"\n\n⏳ **CLOSES AT:** <t:{int(closes_at.timestamp())}:R> (<t:{int(closes_at.timestamp())}:t>)\n\n"
                f"👉 Tap the menu below to purchase your exclusive items!"
            ),
            color=discord.Color.from_rgb(255, 215, 0)
        )
        embed.set_footer(text=f"DestiFC VIP Special Market • {dur_str} Event")

        for ch in channels:
            try:
                view = SpecialMarketView(self.bot, session_id, rewards)
                msg = f"{ping_str}🌟 **THE SPECIAL OWNER MARKET IS LIVE FOR {dur_str}!**".strip()
                await ch.send(content=msg, embed=embed, view=view)
                print(f"[SpecialMarket] Broadcast sent to #{ch.name}!")
            except Exception as e:
                print(f"[SpecialMarket] Failed to send broadcast to #{ch.name}: {e}")


    @app_commands.command(name="admin_special_market_open", description="Admin: Manually open the VIP Special Market")
    @app_commands.describe(duration_minutes="Duration in minutes (e.g. 30, 60, 120, 1440)")
    async def admin_special_open(self, interaction: discord.Interaction, duration_minutes: int = 60):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

        await self.trigger_special_market_opening(duration_minutes=duration_minutes)
        await interaction.followup.send(f"✅ The VIP Special Market has been opened for {duration_minutes} minutes and broadcasted!", ephemeral=True)

    @app_commands.command(name="admin_special_market_close", description="Admin: Manually close the VIP Special Market immediately")
    async def admin_special_close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

        cfg = await database.get_special_market_config()
        await database.update_special_market_config(
            is_active=False,
            opens_at=None,
            closes_at=None,
            title=cfg.get("title", ""),
            custom_rewards=cfg.get("custom_rewards", []),
            duration_minutes=cfg.get("duration_minutes", 60)
        )
        await interaction.followup.send("🔒 The VIP Special Market has been closed manually!", ephemeral=True)

class SpecialMarketView(discord.ui.View):
    def __init__(self, bot, session_id: str, rewards: list):
        super().__init__(timeout=3600)
        self.bot = bot
        self.session_id = session_id
        self.rewards = rewards

        options = []
        for idx, r in enumerate(rewards[:25]):
            cost = int(r.get("cost_coins", 0))
            r_id = str(r.get('id') or idx)
            options.append(discord.SelectOption(
                label=f"👑 {r.get('title', 'Deal')[:60]}",
                value=f"deal_{idx}_{r_id}",
                description=f"Cost: {cost:,} coins • {r.get('description', '')[:50]}"
            ))

        if options:
            self.select_menu = discord.ui.Select(
                placeholder="👑 Select a VIP Special Market item to purchase...",
                min_values=1,
                max_values=1,
                options=options
            )
            self.select_menu.callback = self.on_select_deal
            self.add_item(self.select_menu)

    async def on_select_deal(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        deal_key = self.select_menu.values[0]

        cfg = await database.get_special_market_config()
        now = datetime.datetime.now(datetime.timezone.utc)
        closes_at_str = cfg.get("closes_at")
        is_closed = not cfg.get("is_active", False)
        if closes_at_str:
            try:
                closes_dt = datetime.datetime.fromisoformat(str(closes_at_str).replace("Z", "+00:00"))
                if now >= closes_dt: is_closed = True
            except Exception: pass

        if is_closed:
            return await interaction.followup.send("🔒 **THE VIP SPECIAL MARKET HAS CLOSED!** This deal is no longer active.", ephemeral=True)

        # Parse deal identifier
        # Try finding in live cfg first, fallback to self.rewards
        live_rewards = cfg.get("custom_rewards") or self.rewards
        
        deal = None
        deal_id = ""
        # Check by structured format deal_{idx}_{r_id} or legacy vip_{r_id}
        if deal_key.startswith("deal_"):
            parts = deal_key.split("_", 2)
            idx_str = parts[1] if len(parts) > 1 else "-1"
            extracted_id = parts[2] if len(parts) > 2 else ""
            try:
                idx = int(idx_str)
                if 0 <= idx < len(live_rewards):
                    deal = live_rewards[idx]
                    deal_id = str(deal.get('id', idx))
            except Exception:
                pass
            if not deal:
                deal = next((r for r in live_rewards if str(r.get('id')) == extracted_id or str(r.get('id')) == f"vip_{extracted_id}"), None)
                if deal:
                    deal_id = str(deal.get('id'))
        else:
            raw_target = deal_key.replace("vip_", "")
            deal = next((r for r in live_rewards if str(r.get('id')) == raw_target or str(r.get('id')) == deal_key), None)
            if not deal:
                # Fallback to self.rewards
                deal = next((r for r in self.rewards if str(r.get('id')) == raw_target or str(r.get('id')) == deal_key), None)
            if deal:
                deal_id = str(deal.get('id', raw_target))

        if not deal:
            return await interaction.followup.send("❌ Deal no longer available.", ephemeral=True)

        # Atomically claim VIP deal slot before charging or granting rewards
        claimed = await database.claim_special_market_purchase(user_id, self.session_id, deal_id)
        if not claimed:
            return await interaction.followup.send("❌ You already claimed this VIP deal during this session!", ephemeral=True)

        cost = int(deal.get("cost_coins", 0))
        user = await database.get_user(user_id)
        balance = user.get("coins", 0)
        if balance < cost:
            await database.cancel_special_market_purchase(user_id, self.session_id, deal_id)
            return await interaction.followup.send(f"❌ Insufficient coins! You need **{cost:,} Coins**, but have **{balance:,}**.", ephemeral=True)

        # Process payment
        await database.add_coins(user_id, -cost)
        
        # Grant rewards (vouchers / player card)
        granted_msgs = []
        vouchers = int(deal.get("vouchers", 0))
        if vouchers > 0:
            await database.add_vouchers(user_id, vouchers)
            granted_msgs.append(f"🎟️ **+{vouchers} Draft Vouchers**")

        player_data = deal.get("player_data")
        if player_data:
            await database.add_player_to_inventory(user_id, player_data)
            pname = player_data.get('cardName') or player_data.get('lastName', 'Card')
            povr = player_data.get('rating', 0)
            granted_msgs.append(f"⚽ **{povr} OVR {pname}**")
        
        details = " & ".join(granted_msgs) if granted_msgs else "VIP rewards"
        await interaction.followup.send(
            f"👑 **VIP SPECIAL DEAL PURCHASED!**\n"
            f"You bought **{deal.get('title')}** for **{cost:,} Coins**!\n"
            f"Granted: {details}\nRemaining Coins: **{balance - cost:,}** 💰",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(BlackMarketCog(bot))
