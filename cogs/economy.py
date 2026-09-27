import discord
from discord.ext import commands
from discord import app_commands
import database



class PenaltyView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_shot(self, interaction: discord.Interaction, direction: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)
            return

        # Disable buttons
        for child in self.children:
            child.disabled = True

        import random
        gk_dive = random.choice(["Left", "Middle", "Right"])
        
        if gk_dive == direction:
            # GK Saved it
            await interaction.response.edit_message(content=f"🧤 **GK dived {gk_dive} and SAVED your shot to the {direction}!**\n❌ **Skill Game Failed!** You get 0 vouchers. Try again in an hour!", view=self)
        else:
            # Goal
            import database
            await database.add_vouchers(interaction.user.id, 1)
            await interaction.response.edit_message(content=f"⚽ **You shot {direction}, GK dived {gk_dive}... GOAL!!!**\n🎯 **Skill Game Passed!** You earned **1x Draft Voucher 🎫**!", view=self)
            
    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="◀️")
    async def shoot_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Left")

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="🔼")
    async def shoot_middle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Middle")
        
    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="▶️")
    async def shoot_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Right")


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quest_daily", description="Claim your daily login Draft Vouchers")
    @app_commands.checks.cooldown(1, 86400, key=lambda i: i.user.id) # 24 hour cooldown
    async def quest_daily(self, interaction: discord.Interaction):
        await database.add_vouchers(interaction.user.id, 3)
        await interaction.response.send_message("🎁 **Daily Reward!** You received **3x Draft Vouchers 🎫** for logging in today!")

    @app_commands.command(name="quest_skill_game", description="Play a Penalty Shootout skill game for a voucher")
    @app_commands.checks.cooldown(1, 3600, key=lambda i: i.user.id) # 1 hour cooldown
    async def quest_skill_game(self, interaction: discord.Interaction):
        view = PenaltyView(interaction.user.id)
        await interaction.response.send_message("🥅 **Penalty Shootout!**\nWhere are you going to shoot? Choose quickly!", view=view)

    @app_commands.command(name="quest_h2h", description="Play a quick Head to Head match against AI")
    @app_commands.checks.cooldown(1, 7200, key=lambda i: i.user.id) # 2 hour cooldown
    async def quest_h2h(self, interaction: discord.Interaction):
        import random
        if random.random() < 0.50: # 50% chance to win
            await database.add_vouchers(interaction.user.id, 2)
            await interaction.response.send_message("⚔️ **H2H Victory!** You beat the AI 2-1 and earned **2x Draft Vouchers 🎫**!")
        else:
            await interaction.response.send_message("💀 **H2H Loss!** The AI scored a sweaty cutback in the 90th minute. Better luck next time!")

    @app_commands.command(name="quests", description="View all available ways to earn Draft Vouchers")
    async def quests_list(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Active Quests", 
            description="Complete these quests to earn **Draft Vouchers 🎫** so you can open more packs!",
            color=discord.Color.gold()
        )
        embed.add_field(name="🎁 `/quest_daily`", value="**Reward:** 3x Vouchers\n**Cooldown:** 24 Hours\nGuaranteed reward just for logging in!", inline=False)
        embed.add_field(name="🎯 `/quest_skill_game`", value="**Reward:** 1x Voucher\n**Cooldown:** 1 Hour\n70% chance to win. Don't miss!", inline=False)
        embed.add_field(name="⚔️ `/quest_h2h`", value="**Reward:** 2x Vouchers\n**Cooldown:** 2 Hours\n50% chance to win. Beat the sweaty AI!", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="balance", description="Check your balance and inventory")
    async def balance(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user = await database.get_user(user_id)
        
        embed = discord.Embed(
            title=f"🏦 {interaction.user.display_name}'s Balance",
            color=discord.Color.blue()
        )
        embed.add_field(name="Coins 🪙", value=user.get('coins', 0), inline=True)
        embed.add_field(name="Gems 💎", value=user.get('gems', 0), inline=True)
        embed.add_field(name="Vouchers 🎫", value=user.get('vouchers', 0), inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="give", description="[Owner Only] Give currency to yourself or a user")
    @app_commands.choices(item=[
        app_commands.Choice(name="Coins", value="coins"),
        app_commands.Choice(name="Gems", value="gems"),
        app_commands.Choice(name="Draft Vouchers", value="vouchers")
    ])
    async def give(self, interaction: discord.Interaction, item: str, amount: int, member: discord.Member = None):
        if not await interaction.client.is_owner(interaction.user):
            await interaction.response.send_message("❌ This command is restricted to the bot owner only.", ephemeral=True)
            return
            
        target = member or interaction.user
        
        if item == "coins":
            await database.add_coins(target.id, amount)
        elif item == "gems":
            await database.add_gems(target.id, amount)
        elif item == "vouchers":
            await database.add_vouchers(target.id, amount)
            
        await interaction.response.send_message(f"👑 Owner Command: Gave **{amount:,} {item}** to {target.mention}!", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            # Calculate hours/minutes
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
            await interaction.response.send_message(f"⏳ **Cooldown!** You must wait **{time_str}** before doing this quest again.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
