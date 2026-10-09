import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio
import time

SPIN_COOLDOWN = 14400  # 4 Hours (seconds)

WHEEL_SLICES = [
    {"label": "🎟️ 1x Draft Voucher", "type": "vouchers", "val": 1, "weight": 30},
    {"label": "🎟️ 3x Draft Vouchers", "type": "vouchers", "val": 3, "weight": 20},
    {"label": "🎟️ 5x Draft Vouchers", "type": "vouchers", "val": 5, "weight": 12},
    {"label": "🎟️ 10x JACKPOT Vouchers!", "type": "vouchers", "val": 10, "weight": 5},
    {"label": "🪙 10,000,000 Coins", "type": "coins", "val": 10_000_000, "weight": 15},
    {"label": "🪙 25,000,000 Coins", "type": "coins", "val": 25_000_000, "weight": 8},
    {"label": "💎 50 Gems", "type": "gems", "val": 50, "weight": 7},
    {"label": "⭐ Mystery 118+ Superstar!", "type": "player", "val": 118, "weight": 3},
]

class SpinWheelView(discord.ui.View):
    def __init__(self, user: discord.Member, cog):
        super().__init__(timeout=60)
        self.user = user
        self.cog = cog

    @discord.ui.button(label="🎡 SPIN THE WHEEL!", style=discord.ButtonStyle.success, emoji="✨")
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your Lucky Wheel!", ephemeral=True)
        
        self.stop()
        button.disabled = True
        await self.cog.perform_spin(interaction, self.user)

class SpinCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="spin", description="Spin the Lucky Wheel for free Draft Vouchers, Millions of Coins & Superstar Cards!")
    async def spin(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        p = await database.get_db()
        last_spin = await p.fetchval('SELECT last_spin FROM users WHERE user_id = $1', user_id) or 0
        now = int(time.time())

        if last_spin and (now - last_spin < SPIN_COOLDOWN):
            rem = SPIN_COOLDOWN - (now - last_spin)
            hrs, rem_m = divmod(rem, 3600)
            mins, secs = divmod(rem_m, 60)
            embed = discord.Embed(
                title="⏳ Lucky Wheel on Cooldown",
                description=f"You already spun the wheel recently!\nNext free spin in: **{int(hrs)}h {int(mins)}m {int(secs)}s**.",
                color=discord.Color.orange()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="🎡 DESTIFC LUCKY WHEEL",
            description=(
                f"Welcome {interaction.user.mention} to the **Lucky Wheel**!\n\n"
                f"### 🎁 Possible Rewards:\n"
                f"• 🎟️ **1x to 10x Draft Vouchers** (High Chance!)\n"
                f"• 🪙 **10M to 25M Coins**\n"
                f"• 💎 **50 Gems**\n"
                f"• ⭐ **118+ OVR Superstar Card**\n\n"
                f"👉 **Click the button below to spin!**"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Free spin available every 4 hours!")
        view = SpinWheelView(interaction.user, self)
        await interaction.response.send_message(embed=embed, view=view)

    async def perform_spin(self, interaction: discord.Interaction, user: discord.Member):
        now = int(time.time())
        p = await database.get_db()
        await p.execute('''
            INSERT INTO users (user_id, last_spin) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET last_spin = $2
        ''', user.id, now)

        # Select prize
        weights = [s["weight"] for s in WHEEL_SLICES]
        chosen = random.choices(WHEEL_SLICES, weights=weights, k=1)[0]

        # Animate spin frames
        frames = [
            "🎡 `[ 🪙 10M Coins ]`  ──▶  **[ 🎟️ 3x Vouchers ]**  ──▶  `[ 💎 50 Gems ]`",
            "🎡 `[ 🎟️ 1x Voucher ]` ──▶  **[ ⭐ 118+ Player ]**  ──▶  `[ 🪙 25M Coins ]`",
            "🎡 `[ 💎 50 Gems ]`    ──▶  **[ 🎟️ 10x JACKPOT ]** ──▶  `[ 🎟️ 1x Voucher ]`",
            f"🎡  🎉 **POINTER STOPPED ON:**\n# 🌟 {chosen['label']} 🌟"
        ]

        spin_embed = discord.Embed(
            title="🎡 SPINNING THE LUCKY WHEEL...",
            description="The wheel is spinning at high speed...\n\n" + frames[0],
            color=discord.Color.purple()
        )
        await interaction.response.edit_message(embed=spin_embed, view=None)

        for i in range(1, len(frames)):
            await asyncio.sleep(0.9)
            spin_embed.description = "The wheel is slowing down...\n\n" + frames[i]
            if i == len(frames) - 1:
                spin_embed.title = "🎉 WHEEL STOPPED!"
                spin_embed.color = discord.Color.green()
            await interaction.edit_original_response(embed=spin_embed)

        # Apply rewards
        reward_detail = ""
        lucky_card = None
        if chosen["type"] == "vouchers":
            await database.add_vouchers(user.id, chosen["val"])
            reward_detail = f"🎟️ Added **+{chosen['val']} Draft Vouchers** to your balance!"
        elif chosen["type"] == "coins":
            await database.add_coins(user.id, chosen["val"])
            reward_detail = f"🪙 Added **+{chosen['val']:,} Coins** to your balance!"
        elif chosen["type"] == "gems":
            await p.execute("UPDATE users SET gems = COALESCE(gems, 0) + $1 WHERE user_id = $2", chosen["val"], user.id)
            reward_detail = f"💎 Added **+{chosen['val']} Gems** to your account!"
        elif chosen["type"] == "player":
            pool = await database.get_official_cards_by_rating(118, 122, limit=50)
            if pool:
                lucky_card = random.choice(pool)
                await database.add_player_to_inventory(user.id, lucky_card)
                c_name = lucky_card.get('cardName') or lucky_card.get('lastName', 'Superstar')
                c_ovr = lucky_card.get('rating', 118)
                reward_detail = f"⭐ Pulled a **{c_ovr} OVR {c_name}** into your inventory!"

        final_embed = discord.Embed(
            title="🎁 CONGRATULATIONS!",
            description=(
                f"### You won: {chosen['label']}!\n\n"
                f"{reward_detail}\n\n"
                f"⏰ *Next free spin unlocks in 4 hours!*"
            ),
            color=discord.Color.gold()
        )
        if lucky_card:
            img_url = lucky_card.get('images', {}).get('playerCardImage') or lucky_card.get('images', {}).get('playerImage')
            if img_url:
                final_embed.set_thumbnail(url=img_url)

        await asyncio.sleep(0.5)
        await interaction.edit_original_response(embed=final_embed)

async def setup(bot):
    await bot.add_cog(SpinCog(bot))
