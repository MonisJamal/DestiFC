from utils import parse_number
import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio

DIRECTIONS = {
    "left": ("⬅️ Left", "left"),
    "middle": ("⬆️ Middle", "middle"),
    "right": ("➡️ Right", "right")
}

class ShootoutPvpView(discord.ui.View):
    def __init__(self, shooter: discord.Member, keeper: discord.Member, round_num: int, callback):
        super().__init__(timeout=45)
        self.shooter = shooter
        self.keeper = keeper
        self.round_num = round_num
        self.callback = callback
        self.shot_choice = None
        self.dive_choice = None

    @discord.ui.button(label="⬅️ Shoot / Dive Left", style=discord.ButtonStyle.primary, custom_id="pen_left")
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "left")

    @discord.ui.button(label="⬆️ Shoot / Dive Center", style=discord.ButtonStyle.secondary, custom_id="pen_mid")
    async def btn_mid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "middle")

    @discord.ui.button(label="➡️ Shoot / Dive Right", style=discord.ButtonStyle.primary, custom_id="pen_right")
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "right")

    async def _handle_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id == self.shooter.id:
            if self.shot_choice:
                return await interaction.response.send_message("You already locked in your shot!", ephemeral=True)
            self.shot_choice = choice
            await interaction.response.send_message(f"🎯 Shot locked towards **{choice.upper()}**!", ephemeral=True)
        elif interaction.user.id == self.keeper.id:
            if self.dive_choice:
                return await interaction.response.send_message("You already locked in your dive!", ephemeral=True)
            self.dive_choice = choice
            await interaction.response.send_message(f"🧤 Dive locked towards **{choice.upper()}**!", ephemeral=True)
        else:
            return await interaction.response.send_message("❌ You are not playing in this shootout!", ephemeral=True)

        if self.shot_choice and self.dive_choice:
            self.stop()
            await self.callback(self.shot_choice, self.dive_choice)

class ShootoutSoloView(discord.ui.View):
    def __init__(self, user: discord.Member, on_choice):
        super().__init__(timeout=45)
        self.user = user
        self.on_choice = on_choice

    @discord.ui.button(label="⬅️ Left Corner", style=discord.ButtonStyle.primary)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your penalty kick!", ephemeral=True)
        await interaction.response.defer()
        self.stop()
        await self.on_choice(interaction, "left")

    @discord.ui.button(label="⬆️ Down the Middle", style=discord.ButtonStyle.secondary)
    async def btn_mid(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your penalty kick!", ephemeral=True)
        await interaction.response.defer()
        self.stop()
        await self.on_choice(interaction, "middle")

    @discord.ui.button(label="➡️ Right Corner", style=discord.ButtonStyle.primary)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your penalty kick!", ephemeral=True)
        await interaction.response.defer()
        self.stop()
        await self.on_choice(interaction, "right")

class ShootoutChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager_coins: str, cog):
        if isinstance(wager_coins, str): wager_coins = parse_number(wager_coins)
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager_coins
        self.cog = cog
        self.accepted = False
        self.message = None

    async def on_timeout(self):
        if self.accepted:
            return
        database.ACTIVE_MATCH_USERS.discard(self.challenger.id)
        database.ACTIVE_MATCH_USERS.discard(self.opponent.id)
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content=f"⏱️ **Shootout Challenge Expired!** {self.opponent.display_name} did not respond.", view=self)
            except Exception:
                pass

    @discord.ui.button(label="Accept Shootout 🥅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ Only the challenged player can accept!", ephemeral=True)
        
        if self.accepted:
            return await interaction.response.send_message("❌ This shootout challenge has already been accepted!", ephemeral=True)

        user_a = await database.get_user(self.challenger.id)
        user_b = await database.get_user(self.opponent.id)
        if self.wager > 0:
            if user_a.get('coins', 0) < self.wager:
                database.ACTIVE_MATCH_USERS.discard(self.challenger.id)
                database.ACTIVE_MATCH_USERS.discard(self.opponent.id)
                return await interaction.response.send_message(f"❌ {self.challenger.mention} no longer has enough coins!", ephemeral=True)
            if user_b.get('coins', 0) < self.wager:
                database.ACTIVE_MATCH_USERS.discard(self.challenger.id)
                database.ACTIVE_MATCH_USERS.discard(self.opponent.id)
                return await interaction.response.send_message("❌ You do not have enough coins for this wager!", ephemeral=True)
            await database.add_coins(self.challenger.id, -self.wager)
            await database.add_coins(self.opponent.id, -self.wager)

        self.accepted = True
        self.stop()
        for child in self.children:
            child.disabled = True

        # Refresh lock for active shootout gameplay (300s = 5 mins)
        database.ACTIVE_MATCH_USERS.add(self.challenger.id, duration=300)
        database.ACTIVE_MATCH_USERS.add(self.opponent.id, duration=300)

        await interaction.response.defer()
        await self.cog.start_pvp_shootout(interaction, self.challenger, self.opponent, self.wager)

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id and interaction.user.id != self.challenger.id:
            return await interaction.response.send_message("❌ You are not part of this challenge.", ephemeral=True)
        self.stop()
        database.ACTIVE_MATCH_USERS.discard(self.challenger.id)
        database.ACTIVE_MATCH_USERS.discard(self.opponent.id)
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(title="🚫 Shootout Declined", description=f"{interaction.user.mention} declined the penalty shootout.", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=self)

class ShootoutCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shootout", description="Play an interactive 5-round Penalty Shootout against AI or a friend!")
    @app_commands.describe(
        user="Opponent to challenge (leave empty to play Solo vs AI)",
        wager="Coins to wager (winner takes all, optional)"
    )
    async def shootout(self, interaction: discord.Interaction, user: discord.Member = None, wager: str = "0"):
        if isinstance(wager, str): wager = parse_number(wager)
        if wager < 0:
            return await interaction.response.send_message("❌ Wager cannot be negative.", ephemeral=True)
        
        user_data = await database.get_user(interaction.user.id)
        if wager > 0 and user_data.get('coins', 0) < wager:
            return await interaction.response.send_message(f"❌ You don't have enough coins! Your balance: **{user_data.get('coins', 0):,}**", ephemeral=True)

        if user is None or user.id == interaction.user.id or user.bot:
            # Solo Shootout vs AI
            if not database.ACTIVE_MATCH_USERS.acquire(interaction.user.id, duration=300):
                return await interaction.response.send_message("❌ You already have an active match, shootout, or draft battle! Please finish it before starting another.", ephemeral=True)
            await interaction.response.defer()
            await self.start_solo_shootout(interaction, interaction.user, wager)
        else:
            # PvP Challenge
            if not database.ACTIVE_MATCH_USERS.acquire_both(interaction.user.id, user.id, duration=75):
                if interaction.user.id in database.ACTIVE_MATCH_USERS:
                    return await interaction.response.send_message("❌ You already have an active match, shootout, or draft battle! Please finish it before starting another.", ephemeral=True)
                else:
                    return await interaction.response.send_message(f"❌ **{user.display_name}** is already in an active match, lobby, or shootout! Please wait for them to finish.", ephemeral=True)

            view = ShootoutChallengeView(interaction.user, user, wager, self)
            embed = discord.Embed(
                title="🥅 PENALTY SHOOTOUT CHALLENGE!",
                description=(
                    f"{user.mention}, you have been challenged by **{interaction.user.mention}** to a **5-Round Penalty Shootout**!\n\n"
                    f"🪙 **Wager:** `{wager:,} Coins`\n"
                    f"🧤 **Format:** Choose your shot & dive direction every round!\n\n"
                    f"*Click Accept below within 60 seconds to step up to the penalty spot!*"
                ),
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.response.send_message(content=user.mention, embed=embed, view=view)
            view.message = await interaction.original_response()

    async def start_solo_shootout(self, interaction: discord.Interaction, user: discord.Member, wager: str):
        try:
            await self._run_solo_shootout(interaction, user, wager)
        finally:
            database.ACTIVE_MATCH_USERS.discard(user.id)

    async def _run_solo_shootout(self, interaction: discord.Interaction, user: discord.Member, wager: str):
        if isinstance(wager, str): wager = parse_number(wager)
        score_user = 0
        score_ai = 0
        rounds_user = []
        rounds_ai = []
        channel = interaction.channel

        # Initial reply acknowledging the deferred interaction
        init_embed = discord.Embed(
            title="🥅 PENALTY SHOOTOUT — WARMING UP!",
            description=f"Stepping onto the penalty spot against **DestiFC AI**...\nPrepare for **5 Rounds**!",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=init_embed)
        await asyncio.sleep(1.0)

        for r in range(1, 6):
            # User shoots
            ai_dive = random.choice(["left", "middle", "right"])
            fut = asyncio.get_event_loop().create_future()

            async def on_kick(btn_inter, choice):
                fut.set_result((btn_inter, choice))

            view = ShootoutSoloView(user, on_kick)
            embed = discord.Embed(
                title=f"🥅 Round {r}/5 — Your Penalty Kick!",
                description=(
                    f"**Score:** You `{score_user}` ━ `{score_ai}` DestiFC AI 🤖\n\n"
                    f"Your attempts: {' '.join(rounds_user) or '⚪'}\n"
                    f"AI attempts: {' '.join(rounds_ai) or '⚪'}\n\n"
                    f"👉 **Choose where to place your penalty kick below:**"
                ),
                color=discord.Color.blue()
            )
            msg = await channel.send(embed=embed, view=view)

            try:
                btn_inter, shot_choice = await asyncio.wait_for(fut, timeout=30)
                try:
                    await msg.delete()
                except Exception:
                    pass
            except asyncio.TimeoutError:
                shot_choice = "middle"
                try:
                    await msg.delete()
                except Exception:
                    pass

            # Result of user kick
            woodwork = random.random() < 0.08
            if woodwork:
                outcome_text = "💥 **OFF THE CROSSBAR!** The shot hits the woodwork and bounces away!"
                rounds_user.append("🔴")
            elif shot_choice == ai_dive:
                outcome_text = f"🧤 **SAVED!** The AI goalkeeper correctly dived **{ai_dive.upper()}** and parried it!"
                rounds_user.append("🔴")
            else:
                score_user += 1
                outcome_text = f"⚽ **GOAL!** You slotted it **{shot_choice.upper()}** while the keeper dived {ai_dive.upper()}!"
                rounds_user.append("🟢")

            # AI shoots
            await asyncio.sleep(1.0)
            ai_shot = random.choice(["left", "middle", "right"])
            user_dive = random.choice(["left", "middle", "right"])
            if ai_shot == user_dive:
                ai_text = f"🧤 **SAVED!** You read the AI's mind and saved the shot to the **{user_dive.upper()}**!"
                rounds_ai.append("🔴")
            else:
                score_ai += 1
                ai_text = f"⚽ **GOAL!** DestiFC AI converts into the **{ai_shot.upper()}** corner!"
                rounds_ai.append("🟢")

            round_embed = discord.Embed(
                title=f"⏱️ End of Round {r}",
                description=f"{outcome_text}\n{ai_text}\n\n**Current Score:** You `{score_user}` ━ `{score_ai}` AI",
                color=discord.Color.teal()
            )
            await channel.send(embed=round_embed)
            await asyncio.sleep(1.5)

        # Winner
        if score_user > score_ai:
            w_coins = 5_000_000 + (wager * 2 if wager > 0 else 0)
            w_vouchers = 2
            await database.add_coins(user.id, w_coins)
            await database.add_vouchers(user.id, w_vouchers)
            res_title = "🏆 YOU WON THE PENALTY SHOOTOUT!"
            res_desc = f"You defeated DestiFC AI **{score_user} - {score_ai}**!\n\n💰 **Rewards:** `+{w_coins:,} Coins` & `+{w_vouchers} Draft Vouchers`!"
            color = discord.Color.green()
        elif score_ai > score_user:
            res_title = "💔 DEFEAT IN PENALTY SHOOTOUT"
            res_desc = f"DestiFC AI defeated you **{score_ai} - {score_user}**! Practice your kicks and try again!"
            color = discord.Color.red()
        else:
            w_coins = 2_500_000 + wager
            await database.add_coins(user.id, w_coins)
            res_title = "🤝 PENALTY SHOOTOUT DRAW!"
            res_desc = f"Finished level **{score_user} - {score_ai}**!\n💰 Consolation: `+{w_coins:,} Coins`"
            color = discord.Color.gold()

        final_embed = discord.Embed(
            title=res_title,
            description=(
                f"### Final Score: `{score_user} - {score_ai}`\n"
                f"Your kicks: {' '.join(rounds_user)}\n"
                f"AI kicks:   {' '.join(rounds_ai)}\n\n{res_desc}"
            ),
            color=color
        )
        await channel.send(embed=final_embed)

    async def start_pvp_shootout(self, interaction: discord.Interaction, user_a: discord.Member, user_b: discord.Member, wager: str):
        try:
            await self._run_pvp_shootout(interaction, user_a, user_b, wager)
        finally:
            database.ACTIVE_MATCH_USERS.discard(user_a.id)
            database.ACTIVE_MATCH_USERS.discard(user_b.id)

    async def _run_pvp_shootout(self, interaction: discord.Interaction, user_a: discord.Member, user_b: discord.Member, wager: str):
        if isinstance(wager, str): wager = parse_number(wager)
        score_a = 0
        score_b = 0
        rounds_a = []
        rounds_b = []
        channel = interaction.channel

        for r in range(1, 6):
            # User A shoots, User B keeps
            fut_a = asyncio.get_event_loop().create_future()
            async def cb_a(shot, dive):
                fut_a.set_result((shot, dive))

            view_a = ShootoutPvpView(user_a, user_b, r, cb_a)
            embed_a = discord.Embed(
                title=f"🥅 Round {r}/5 — {user_a.display_name} Shooting!",
                description=(
                    f"**Score:** {user_a.mention} `{score_a}` ━ `{score_b}` {user_b.mention}\n\n"
                    f"🎯 **{user_a.display_name}**: Click where you want to **SHOOT**!\n"
                    f"🧤 **{user_b.display_name}**: Click where you want to **DIVE**!"
                ),
                color=discord.Color.blue()
            )
            msg = await channel.send(embed=embed_a, view=view_a)

            try:
                shot_a, dive_b = await asyncio.wait_for(fut_a, timeout=40)
            except asyncio.TimeoutError:
                shot_a = random.choice(["left", "middle", "right"])
                dive_b = random.choice(["left", "middle", "right"])
            await msg.delete()

            if shot_a == dive_b:
                text_a = f"🧤 **SAVED!** {user_b.mention} guessed correctly ({dive_b.upper()})!"
                rounds_a.append("🔴")
            else:
                score_a += 1
                text_a = f"⚽ **GOAL!** {user_a.mention} scores ({shot_a.upper()})!"
                rounds_a.append("🟢")

            # User B shoots, User A keeps
            fut_b = asyncio.get_event_loop().create_future()
            async def cb_b(shot, dive):
                fut_b.set_result((shot, dive))

            view_b = ShootoutPvpView(user_b, user_a, r, cb_b)
            embed_b = discord.Embed(
                title=f"🥅 Round {r}/5 — {user_b.display_name} Shooting!",
                description=(
                    f"**Score:** {user_a.mention} `{score_a}` ━ `{score_b}` {user_b.mention}\n\n"
                    f"🎯 **{user_b.display_name}**: Click where you want to **SHOOT**!\n"
                    f"🧤 **{user_a.display_name}**: Click where you want to **DIVE**!"
                ),
                color=discord.Color.red()
            )
            msg_b = await channel.send(embed=embed_b, view=view_b)

            try:
                shot_b, dive_a = await asyncio.wait_for(fut_b, timeout=40)
            except asyncio.TimeoutError:
                shot_b = random.choice(["left", "middle", "right"])
                dive_a = random.choice(["left", "middle", "right"])
            await msg_b.delete()

            if shot_b == dive_a:
                text_b = f"🧤 **SAVED!** {user_a.mention} saved the penalty ({dive_a.upper()})!"
                rounds_b.append("🔴")
            else:
                score_b += 1
                text_b = f"⚽ **GOAL!** {user_b.mention} scores ({shot_b.upper()})!"
                rounds_b.append("🟢")

            mid_embed = discord.Embed(
                title=f"⏱️ Round {r} Results",
                description=f"{text_a}\n{text_b}\n\n**Current Score:** {user_a.display_name} `{score_a}` ━ `{score_b}` {user_b.display_name}",
                color=discord.Color.purple()
            )
            await channel.send(embed=mid_embed)
            await asyncio.sleep(1.0)

        # Winner
        pot = wager * 2
        if score_a > score_b:
            if pot > 0: await database.add_coins(user_a.id, pot)
            res = f"🏆 **{user_a.mention} WINS THE SHOOTOUT!**\n💰 Prize: `{pot:,} Coins`"
            color = discord.Color.green()
        elif score_b > score_a:
            if pot > 0: await database.add_coins(user_b.id, pot)
            res = f"🏆 **{user_b.mention} WINS THE SHOOTOUT!**\n💰 Prize: `{pot:,} Coins`"
            color = discord.Color.green()
        else:
            if wager > 0:
                await database.add_coins(user_a.id, wager)
                await database.add_coins(user_b.id, wager)
            res = "🤝 **DRAW!** Both players tied in the penalty shootout. Wagers refunded."
            color = discord.Color.gold()

        final = discord.Embed(
            title="🏁 PENALTY SHOOTOUT FINAL SCORE",
            description=(
                f"### {user_a.display_name} `{score_a}` ━ `{score_b}` {user_b.display_name}\n\n"
                f"{user_a.display_name}: {' '.join(rounds_a)}\n"
                f"{user_b.display_name}: {' '.join(rounds_b)}\n\n---\n{res}"
            ),
            color=color
        )
        await channel.send(embed=final)

async def setup(bot):
    await bot.add_cog(ShootoutCog(bot))
