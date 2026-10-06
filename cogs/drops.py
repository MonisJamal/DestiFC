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

def get_card_thumbnail(player_data: dict) -> str | None:
    if not player_data:
        return None
    imgs = player_data.get("images")
    if isinstance(imgs, dict):
        return (
            imgs.get("playerCardImage")
            or imgs.get("playerImage")
            or imgs.get("cardImage")
        )
    return (
        player_data.get("playerCardImage")
        or player_data.get("playerImage")
        or player_data.get("cardImage")
    )

class DropClaimView(discord.ui.View):
    def __init__(self, vouchers: int, coins: int, max_claims: int, is_rare: bool = False, player_data: dict = None):
        super().__init__(timeout=600)
        self.vouchers = vouchers
        self.coins = coins
        self.max_claims = max_claims
        self.is_rare = is_rare
        self.player_data = player_data
        self.claimed_users = set()

    @discord.ui.button(label="🎁 Claim Crate!", style=discord.ButtonStyle.success, custom_id="claim_drop_btn")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.claimed_users:
            return await interaction.response.send_message("❌ You already claimed from this drop!", ephemeral=True)

        if len(self.claimed_users) >= self.max_claims:
            return await interaction.response.send_message("❌ This crate has already been fully looted!", ephemeral=True)

        self.claimed_users.add(interaction.user.id)
        
        # Grant rewards
        if self.vouchers > 0:
            await database.add_vouchers(interaction.user.id, self.vouchers)
        if self.coins > 0:
            await database.add_coins(interaction.user.id, self.coins)
        if self.player_data:
            await database.add_player_to_inventory(interaction.user.id, self.player_data)

        remaining = self.max_claims - len(self.claimed_users)
        label_prefix = "🌟 CLAIM RARE GIFT" if self.is_rare else "🎟️ Claim Crate!"
        button.label = f"{label_prefix} ({remaining}/{self.max_claims} left)"

        if remaining <= 0:
            button.disabled = True
            button.label = "🔒 Fully Looted!"
            self.stop()

        await interaction.response.edit_message(view=self)
        banner = "🌟 **RARE DAILY GIFT CLAIMED!**" if self.is_rare else "🎉 **Loot Claimed!**"
        
        rewards_text = []
        if self.player_data:
            pname = self.player_data.get('cardName') or self.player_data.get('lastName', 'Player')
            povr = self.player_data.get('rating', 0)
            ppos = self.player_data.get('position') or self.player_data.get('pos', 'ST')
            rewards_text.append(f"⚽ **{povr} OVR {pname} ({ppos})**")
        if self.vouchers > 0:
            rewards_text.append(f"🎟️ **+{self.vouchers} Draft Vouchers**")
        if self.coins > 0:
            rewards_text.append(f"🪙 **+{self.coins:,} Coins**")

        details = " & ".join(rewards_text) if rewards_text else "rewards"
        await interaction.followup.send(
            f"{banner} You received {details}!",
            ephemeral=True
        )

class AdminPlayerDropSelect(discord.ui.Select):
    def __init__(self, candidates: list, vouchers: int, coins: int, max_claims: int):
        self.candidates = candidates
        self.vouchers = vouchers
        self.coins = coins
        self.max_claims = max_claims

        options = []
        for idx, card in enumerate(candidates[:25]):
            name = card.get("cardName") or card.get("lastName", "Player")
            ovr = card.get("rating", 0)
            pos = card.get("position") or card.get("pos", "ST")
            prog = card.get("program") or ("CUSTOM" if card.get("is_custom") else "")
            desc = f"{pos} • {prog}" if prog else f"{pos} • Card"
            options.append(discord.SelectOption(
                label=f"{ovr} OVR - {name[:70]}",
                value=str(idx),
                description=desc[:100]
            ))

        super().__init__(
            placeholder="Select a player version to drop...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_idx = int(self.values[0])
        chosen_card = self.candidates[selected_idx]

        name = chosen_card.get("cardName") or chosen_card.get("lastName", "Player")
        ovr = chosen_card.get("rating", 0)
        pos = chosen_card.get("position") or chosen_card.get("pos", "ST")
        prog = chosen_card.get("program") or ("CUSTOM" if chosen_card.get("is_custom") else "")

        embed = discord.Embed(
            title="🎁 A WILD PLAYER CRATE HAS DROPPED!",
            description=(
                f"An admin summoned an elite player supply crate!\n\n"
                f"⭐ **Player:** `{ovr} OVR` **{name}** (`{pos}`)" + (f" [{prog}]" if prog else "") + f"\n"
                + (f"🎟️ **Vouchers:** `+{self.vouchers} Draft Vouchers`\n" if self.vouchers > 0 else "")
                + (f"🪙 **Coins:** `+{self.coins:,} Coins`\n" if self.coins > 0 else "")
                + f"\n⚡ **First {self.max_claims} players** to click claim get this player card!"
            ),
            color=discord.Color.gold()
        )
        thumb = get_card_thumbnail(chosen_card)
        if thumb:
            embed.set_thumbnail(url=thumb)
        embed.set_footer(text="Random Server Drop • DestiFC Stadium")

        view = DropClaimView(self.vouchers, self.coins, self.max_claims, player_data=chosen_card)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.edit_message(
            content=f"✅ Successfully dropped **{ovr} OVR {name}** into this channel!",
            view=None
        )


class AdminPlayerDropSelectView(discord.ui.View):
    def __init__(self, candidates: list, vouchers: int, coins: int, max_claims: int):
        super().__init__(timeout=180)
        self.add_item(AdminPlayerDropSelect(candidates, vouchers, coins, max_claims))


async def search_cards_for_drop(query: str, limit: int = 25) -> list:
    """Searches custom inventory, RenderZ API, and official_cards DB."""
    results = []
    seen = set()

    p = await database.get_db()

    # 1. Check custom cards in inventory first
    try:
        custom_rows = await p.fetch(
            "SELECT player_name, ovr, player_data FROM inventory WHERE player_data->>'is_custom' = 'true' AND player_name ILIKE $1 ORDER BY ovr DESC",
            f"%{query}%"
        )
        for r in custom_rows:
            pd = r["player_data"]
            if isinstance(pd, str):
                pd = json.loads(pd)
            pname = r["player_name"]
            povr = r["ovr"]
            card_id = str(pd.get("id") or f"custom_{pname}_{povr}")
            key = (card_id, povr)
            if key not in seen:
                seen.add(key)
                results.append(pd)
    except Exception as e:
        print(f"[Drops Search] Error searching custom inventory: {e}")

    # 2. Check RenderZ API
    try:
        from renderz_api import search_fifarenderz
        renderz_matches = await asyncio.to_thread(search_fifarenderz, query, 25)
        for card in renderz_matches:
            cid = str(card.get("id") or card.get("assetId") or "")
            covr = card.get("rating", 0)
            key = (cid, covr)
            if key not in seen:
                seen.add(key)
                results.append(card)
    except Exception as e:
        print(f"[Drops Search] Error querying RenderZ: {e}")

    # 3. Check official_cards DB if needed
    if len(results) < limit:
        try:
            db_rows = await p.fetch(
                "SELECT player_name, card_name, rating, player_data FROM official_cards WHERE card_name ILIKE $1 OR player_name ILIKE $1 ORDER BY rating DESC LIMIT $2",
                f"%{query}%", limit
            )
            for r in db_rows:
                pd = r["player_data"]
                if isinstance(pd, str):
                    pd = json.loads(pd)
                cid = str(pd.get("id") or pd.get("assetId") or "")
                covr = r["rating"]
                key = (cid, covr)
                if key not in seen:
                    seen.add(key)
                    results.append(pd)
        except Exception as e:
            print(f"[Drops Search] Error querying official_cards: {e}")

    results.sort(key=lambda x: x.get("rating", 0), reverse=True)
    return results[:limit]


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

    @app_commands.command(name="admin_drop", description="Admin: Manually drop a loot crate into this channel (with optional player)")
    @app_commands.describe(
        vouchers="Vouchers per claim (default 0)",
        coins="Coins per claim (default 0)",
        max_claims="Number of players who can claim (default 3)",
        player_name="Optional player name to drop (shows choice menu of versions)"
    )
    async def admin_drop(
        self,
        interaction: discord.Interaction,
        vouchers: int = 0,
        coins: int = 0,
        max_claims: int = 3,
        player_name: str | None = None
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            from auth import is_team_admin_or_owner
            if not await is_team_admin_or_owner(self.bot, interaction.user):
                return await interaction.followup.send("❌ Admin command only.", ephemeral=True)

            if max_claims < 1:
                max_claims = 1

            # If player_name is provided, search and show dropdown menu
            if player_name and player_name.strip():
                clean_query = player_name.strip()
                matches = await search_cards_for_drop(clean_query, limit=25)
                if not matches:
                    return await interaction.followup.send(
                        f"❌ No player versions found matching **'{clean_query}'**.",
                        ephemeral=True
                    )

                view = AdminPlayerDropSelectView(matches, vouchers=vouchers, coins=coins, max_claims=max_claims)
                return await interaction.followup.send(
                    f"🔍 Found **{len(matches)}** versions for **{clean_query}**.\nSelect the version you want to drop below:",
                    view=view,
                    ephemeral=True
                )

            # Otherwise, drop standard voucher/coin crate
            if vouchers == 0 and coins == 0:
                vouchers = 3
                coins = 5_000_000

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
            await interaction.followup.send("✅ Mystery loot crate successfully dropped into this channel!", ephemeral=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error dropping crate: `{e}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DropsCog(bot))

