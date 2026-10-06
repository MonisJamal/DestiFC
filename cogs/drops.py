import discord
from discord.ext import commands, tasks
from discord import app_commands
import database
import json
import time
import asyncio

DEFAULT_DROPS_CONFIG = {
    "enabled": True,
    "channel_id": None,           # Legacy single channel ID
    "channels": [],               # Multi-channel list: ["123", "456", "789"] across multiple servers
    "interval_mins": 60,
    "vouchers_per_drop": 3,
    "coins_per_drop": 5_000_000,
    "max_claims": 3,
    # Rare Gift Drop (Dropped at 2 random times in a day, editable from panel)
    "rare_drop_enabled": True,
    "rare_drop_vouchers": 25,
    "rare_drop_coins": 150_000_000,
    "rare_drop_max_claims": 5,
    "ping_everyone": False,       # Toggle @everyone ping for rare drops
    "rare_drop_role_id": "",      # Specific Discord Role ID to ping (e.g. "123456789")
    "rare_drop_ping_type": "none", # "none", "everyone", "here", or "role"
    "rare_drop_times_today": [],  # List of two timestamps [t1, t2] generated daily
    "rare_drop_date": "",         # YYYY-MM-DD
    "rare_drop_executed": []      # List of executed drop timestamps
}

class DropClaimView(discord.ui.View):
    def __init__(self, vouchers: int, coins: int, max_claims: int, is_rare: bool = False):
        super().__init__(timeout=600)
        self.vouchers = vouchers
        self.coins = coins
        self.max_claims = max_claims
        self.is_rare = is_rare
        self.claimed_users = set()

    @discord.ui.button(label="🎁 Claim Crate!", style=discord.ButtonStyle.success, custom_id="claim_drop_btn")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.claimed_users:
            return await interaction.response.send_message("❌ You already claimed from this drop!", ephemeral=True)

        if len(self.claimed_users) >= self.max_claims:
            return await interaction.response.send_message("❌ This crate has already been fully looted!", ephemeral=True)

        self.claimed_users.add(interaction.user.id)
        
        # Grant rewards
        await database.add_vouchers(interaction.user.id, self.vouchers)
        if self.coins > 0:
            await database.add_coins(interaction.user.id, self.coins)

        remaining = self.max_claims - len(self.claimed_users)
        label_prefix = "🌟 CLAIM RARE GIFT" if self.is_rare else "🎟️ Claim Crate!"
        button.label = f"{label_prefix} ({remaining}/{self.max_claims} left)"

        if remaining <= 0:
            button.disabled = True
            button.label = "🔒 Fully Looted!"
            self.stop()

        await interaction.response.edit_message(view=self)
        banner = "🌟 **RARE DAILY GIFT CLAIMED!**" if self.is_rare else "🎉 **Loot Claimed!**"
        await interaction.followup.send(
            f"{banner} You received **+{self.vouchers} Draft Vouchers**" + (f" & **+{self.coins:,} Coins**!" if self.coins > 0 else "!"),
            ephemeral=True
        )

class DropsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.random_drop_loop.start()

    def cog_unload(self):
        self.random_drop_loop.cancel()

    async def get_config(self) -> dict:
        p = await database.get_db()
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'drops_config'")
        if row and row['value']:
            val = row['value']
            cfg = json.loads(val) if isinstance(val, str) else val
            merged = dict(DEFAULT_DROPS_CONFIG)
            merged.update(cfg)
            return merged
        return dict(DEFAULT_DROPS_CONFIG)

    async def save_config(self, cfg: dict):
        p = await database.get_db()
        await p.execute(
            "INSERT INTO system_settings (key, value) VALUES ('drops_config', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            json.dumps(cfg)
        )

    async def update_last_drop_time(self, timestamp: float):
        cfg = await self.get_config()
        cfg['last_drop_time'] = int(timestamp)
        await self.save_config(cfg)

    def _ensure_daily_rare_schedule(self, cfg: dict) -> bool:
        """Schedules 2 random drop timestamps for today if not already scheduled."""
        import datetime, random
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        if cfg.get("rare_drop_date") != today_str:
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            start_of_day = datetime.datetime(now_dt.year, now_dt.month, now_dt.day, tzinfo=datetime.timezone.utc)
            start_ts = int(start_of_day.timestamp())
            
            # Split day into 2 windows: Window 1 (00:00 - 12:00 UTC), Window 2 (12:00 - 23:59 UTC)
            # Pick a random minute in each window
            offset_1 = random.randint(30 * 60, 11 * 3600 + 30 * 60)
            offset_2 = random.randint(12 * 3600 + 30 * 60, 23 * 3600 + 30 * 60)
            t1 = start_ts + offset_1
            t2 = start_ts + offset_2

            cfg["rare_drop_date"] = today_str
            cfg["rare_drop_times_today"] = [t1, t2]
            cfg["rare_drop_executed"] = []
            return True
        return False

    def get_target_channels(self, cfg: dict) -> list:
        """Retrieves list of all discord text channels configured across multiple servers."""
        ch_list = []
        raw_channels = cfg.get("channels") or []
        if isinstance(raw_channels, str):
            raw_channels = [c.strip() for c in raw_channels.replace(',', ' ').split() if c.strip()]
        
        # Include legacy channel_id if not in list
        legacy_id = str(cfg.get("channel_id") or "").strip()
        if legacy_id and legacy_id not in [str(c) for c in raw_channels]:
            raw_channels.append(legacy_id)

        for raw_id in raw_channels:
            try:
                cid = int(str(raw_id).strip())
                ch = self.bot.get_channel(cid)
                if ch:
                    ch_list.append(ch)
            except Exception:
                pass
        return ch_list

    @tasks.loop(seconds=30)
    async def random_drop_loop(self):
        try:
            cfg = await self.get_config()
            if not cfg.get("enabled", False):
                return
            
            channels = self.get_target_channels(cfg)
            if not channels:
                return

            now = int(time.time())

            # ----------------------------------------------------
            # 1. CHECK RARE DAILY GIFT DROPS (2x per day at random times)
            # ----------------------------------------------------
            if cfg.get("rare_drop_enabled", True):
                dirty = self._ensure_daily_rare_schedule(cfg)
                scheduled_times = cfg.get("rare_drop_times_today", [])
                executed_times = set(cfg.get("rare_drop_executed", []))

                for target_t in scheduled_times:
                    if target_t not in executed_times and now >= target_t:
                        # Execute rare gift drop!
                        executed_times.add(target_t)
                        cfg["rare_drop_executed"] = list(executed_times)
                        await self.save_config(cfg)

                        r_vouchers = int(cfg.get("rare_drop_vouchers", 25))
                        r_coins = int(cfg.get("rare_drop_coins", 150_000_000))
                        r_claims = int(cfg.get("rare_drop_max_claims", 5))

                        ping_type = str(cfg.get("rare_drop_ping_type") or "none").lower()
                        role_id = str(cfg.get("rare_drop_role_id") or "").strip()
                        
                        ping_str = ""
                        if ping_type == "everyone" or cfg.get("ping_everyone"):
                            ping_str = "@everyone "
                        elif ping_type == "here":
                            ping_str = "@here "
                        elif ping_type == "role" and role_id:
                            ping_str = f"<@&{role_id}> "

                        embed = discord.Embed(
                            title="🌟 EXCLUSIVE RARE GIFT DROP! 🌟",
                            description=(
                                f"🚨 **AN ULTRA-RARE MYSTERY GIFT HAS APPEARED IN THE STADIUM!** 🚨\n\n"
                                f"This legendary gift drops only **twice a day at random moments**!\n\n"
                                f"💎 **Huge Rewards:** `+{r_vouchers} Draft Vouchers` & `+{r_coins:,} Coins`\n"
                                f"⚡ **Availability:** First **{r_claims} lucky managers** to claim get the loot!\n\n"
                                f"👇 **Quick! Tap the button below to claim your Rare Gift!**"
                            ),
                            color=discord.Color.gold()
                        )
                        embed.set_footer(text="Daily Rare Gift Drop • DestiFC Stadium Special Event")

                        for ch in channels:
                            try:
                                view = DropClaimView(r_vouchers, r_coins, r_claims, is_rare=True)
                                msg_content = f"{ping_str}🌟 **RARE GIFT DROP HAS LANDED!**".strip()
                                await ch.send(content=msg_content, embed=embed, view=view)
                                print(f"[Drops] 🌟 Rare Gift Drop delivered to #{ch.name} (Guild: {ch.guild.name})!")
                            except Exception as ex:
                                print(f"[Drops] Error sending rare drop to #{ch.name}: {ex}")
                        return
                if dirty:
                    await self.save_config(cfg)

            # ----------------------------------------------------
            # 2. CHECK PERIODIC STANDARD SUPPLY CRATE DROPS
            # ----------------------------------------------------
            interval_mins = int(cfg.get("interval_mins", 60))
            if interval_mins < 1:
                interval_mins = 1
            interval = interval_mins * 60
            
            last_drop = float(cfg.get("last_drop_time", 0))

            if last_drop <= 0:
                await self.update_last_drop_time(now)
                print(f"[Drops] Initialized drops cycle timer (Interval: {interval_mins}m, {len(channels)} Channels)")
                return

            if now - last_drop < interval:
                return

            await self.update_last_drop_time(now)

            vouchers = int(cfg.get("vouchers_per_drop", 3))
            coins = int(cfg.get("coins_per_drop", 5_000_000))
            max_claims = int(cfg.get("max_claims", 3))

            embed = discord.Embed(
                title="🎁 A WILD SUPPLY CRATE HAS DROPPED!",
                description=(
                    f"A parachute supply crate just landed in the stadium turf!\n\n"
                    f"📦 **Contents:** `+{vouchers} Draft Vouchers`" + (f" & `+{coins:,} Coins`" if coins > 0 else "") + f"\n"
                    f"⚡ **Speed:** First **{max_claims} players** to click claim get the loot!\n\n"
                    f"👉 **Click the button below now to grab your vouchers!**"
                ),
                color=discord.Color.magenta()
            )
            embed.set_footer(text="Random Server Drop • DestiFC Stadium")

            for ch in channels:
                try:
                    view = DropClaimView(vouchers, coins, max_claims, is_rare=False)
                    await ch.send(embed=embed, view=view)
                    print(f"[Drops] ✅ Supply crate dropped into channel #{ch.name} (Guild: {ch.guild.name})!")
                except Exception as ex:
                    print(f"[Drops] Error sending crate to #{ch.name}: {ex}")
        except Exception as e:
            print(f"[Drops Loop Error] {e}")

    @random_drop_loop.before_loop
    async def before_drop_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="admin_drop", description="Admin: Manually drop a voucher loot crate into this channel")
    @app_commands.describe(
        vouchers="Vouchers per claim (default 3)",
        coins="Coins per claim (default 5,000,000)",
        max_claims="Number of players who can claim (default 3)"
    )
    async def admin_drop(self, interaction: discord.Interaction, vouchers: int = 3, coins: int = 5_000_000, max_claims: int = 3):
        await interaction.response.defer(ephemeral=True)
        try:
            from auth import is_team_admin_or_owner
            if not await is_team_admin_or_owner(self.bot, interaction.user):
                return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

            embed = discord.Embed(
                title="🎁 A WILD SUPPLY CRATE HAS DROPPED!",
                description=(
                    f"An admin summoned a mystery supply crate!\n\n"
                    f"📦 **Contents:** `+{vouchers} Draft Vouchers`" + (f" & `+{coins:,} Coins`" if coins > 0 else "") + f"\n"
                    f"⚡ **First {max_claims} players** to click claim get the loot!"
                ),
                color=discord.Color.magenta()
            )
            embed.set_footer(text="Random Server Drop • DestiFC Stadium")
            view = DropClaimView(vouchers, coins, max_claims)
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ Mystery voucher crate successfully dropped into this channel!", ephemeral=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error dropping crate: `{e}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DropsCog(bot))
