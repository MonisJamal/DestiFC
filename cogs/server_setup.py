import discord
from discord.ext import commands
from discord import app_commands
import database
import traceback

OWNER_DISCORD_ID = 1259402026782294051
BEASTLYFC_INVITE = "https://discord.gg/fVE7v6DNjt"
SUPPORT_INVITE = "https://discord.gg/W6YcPSGDMA"
DM_MONIS_URL = f"https://discord.com/users/{OWNER_DISCORD_ID}"

class CustomCardOrderModal(discord.ui.Modal, title="🎨 Order Custom Player Card"):
    player_name = discord.ui.TextInput(
        label="Player / Card Name",
        placeholder="e.g. Desti, Beastly King, Shadow Striker...",
        required=True,
        max_length=50
    )
    rating_position = discord.ui.TextInput(
        label="Rating OVR (110-125) & Position",
        placeholder="e.g. 124 OVR CAM, 122 ST, 125 CB",
        required=True,
        max_length=30
    )
    club_nation = discord.ui.TextInput(
        label="Club / Clan & Nation",
        placeholder="e.g. Real Madrid / Argentina, or Beastly FC / India",
        required=True,
        max_length=60
    )
    image_url = discord.ui.TextInput(
        label="Card Image / Photo URL",
        placeholder="Direct link to render/photo (or type 'Will DM on Discord')",
        required=False,
        max_length=200
    )
    notes_perks = discord.ui.TextInput(
        label="Perks / Boosts / Special Notes",
        placeholder="e.g. Wall perk, 1.25 boost, custom background style...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        guild = interaction.guild

        # Parse rating
        rating = 120
        pos = "ST"
        rp_text = self.rating_position.value.strip()
        parts = rp_text.replace("OVR", "").split()
        for p in parts:
            if p.isdigit():
                rating = min(126, max(100, int(p)))
            elif len(p) <= 4 and p.upper() in ["GK", "CB", "LB", "RB", "LWB", "RWB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST"]:
                pos = p.upper()

        club = "Custom FC"
        nation = "World"
        cn_text = self.club_nation.value.strip()
        if "/" in cn_text:
            c_p, n_p = cn_text.split("/", 1)
            club = c_p.strip() or club
            nation = n_p.strip() or nation
        elif "," in cn_text:
            c_p, n_p = cn_text.split(",", 1)
            club = c_p.strip() or club
            nation = n_p.strip() or nation
        elif cn_text:
            club = cn_text

        img = self.image_url.value.strip() if self.image_url.value else ""
        notes = self.notes_perks.value.strip() if self.notes_perks.value else ""

        # Save to database
        req_id = await database.create_custom_card_request(
            user_id=user.id,
            guild_id=guild.id if guild else None,
            player_name=self.player_name.value.strip(),
            rating=rating,
            position=pos,
            club=club,
            nation=nation,
            image_url=img,
            notes=notes
        )

        # Notify Owner via DM
        owner_alert_sent = False
        try:
            owner = self.bot.get_user(OWNER_DISCORD_ID) or await self.bot.fetch_user(OWNER_DISCORD_ID)
            if owner:
                alert_embed = discord.Embed(
                    title="🚨 New Custom Card Order Received!",
                    description=(
                        f"**Order ID:** `#{req_id}`\n"
                        f"**Requester:** {user.mention} (`{user.name}` | ID: `{user.id}`)\n"
                        f"**Server:** `{guild.name if guild else 'Direct DM'}` (ID: `{guild.id if guild else 'N/A'}`)\n\n"
                        f"🎴 **Card Name:** **{self.player_name.value.strip()}**\n"
                        f"⭐ **Rating & Pos:** **{rating} OVR {pos}**\n"
                        f"🛡️ **Club & Nation:** `{club}` / `{nation}`\n"
                        f"🖼️ **Image URL:** {img or '*Not provided (Requester will DM)*'}\n"
                        f"📝 **Notes / Perks:**\n```{notes or 'None specified'}```"
                    ),
                    color=0xFFD700
                )
                if img and (img.startswith("http://") or img.startswith("https://")):
                    try:
                        alert_embed.set_thumbnail(url=img)
                    except Exception:
                        pass
                await owner.send(embed=alert_embed)
                owner_alert_sent = True
        except Exception as dm_err:
            print(f"[CustomCardOrder] Could not DM owner: {dm_err}")

        # Send confirmation to user
        confirm_embed = discord.Embed(
            title="✅ Custom Card Order Submitted!",
            description=(
                f"Thank you, {user.mention}! Your custom card order (**#{req_id}**) has been sent directly to the development team.\n\n"
                f"📋 **Summary:**\n"
                f"• **Name:** `{self.player_name.value.strip()}`\n"
                f"• **OVR & Pos:** `{rating} OVR {pos}`\n"
                f"• **Club / Nation:** `{club}` / `{nation}`\n\n"
                f"📩 **Next Step:**\n"
                f"Please make sure your DMs are open and message **Desti** (<@{OWNER_DISCORD_ID}>) or join the **[Support Server]({SUPPORT_INVITE})** to finalize your card artwork and stats!"
            ),
            color=0x00FF88
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

class CustomOrderView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
        # Link buttons
        self.add_item(discord.ui.Button(
            label="📩 DM Desti / Developer",
            style=discord.ButtonStyle.link,
            url=DM_MONIS_URL,
            emoji="💬"
        ))
        self.add_item(discord.ui.Button(
            label="🏟️ BeastlyFC (Main)",
            style=discord.ButtonStyle.link,
            url=BEASTLYFC_INVITE,
            emoji="🦁"
        ))
        self.add_item(discord.ui.Button(
            label="🛠️ DestiFC Support",
            style=discord.ButtonStyle.link,
            url=SUPPORT_INVITE,
            emoji="🎫"
        ))

    @discord.ui.button(label="📝 Submit Order Form", style=discord.ButtonStyle.primary, emoji="📋", custom_id="custom_order_modal_btn")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomCardOrderModal(self.bot))


class ServerSetupCog(commands.Cog):
    """Cog for multi-server scaling, server configurations, and custom card ordering."""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """When DestiFC joins a new server, send an onboarding guide."""
        print(f"[Multi-Server] DestiFC joined new guild: '{guild.name}' (ID: {guild.id}, Members: {guild.member_count})")
        
        target_channel = guild.system_channel
        if not target_channel or not target_channel.permissions_for(guild.me).send_messages:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    target_channel = ch
                    break

        if not target_channel:
            return

        embed = discord.Embed(
            title="⚽ DestiFC — Thanks for inviting us!",
            description=(
                f"Welcome to **DestiFC**, the premier FC Mobile simulation bot for Discord!\n\n"
                f"🔥 **Features Ready in `{guild.name}`:**\n"
                f"• 🌟 **Dynamic FUT Drafts & Walkouts** (`/draft`, `/starterpack`)\n"
                f"• 🏟️ **High-Definition 3D Stadium Lineups** (`/squad view`)\n"
                f"• ⚔️ **Ranked Division Rivals & Draft Battles** (`/play`, `/draftbattle`)\n"
                f"• 📈 **Live Transfer Market & Trading** (`/market`, `/trade`)\n\n"
                f"📌 **Server Admin Setup:**\n"
                f"Use `/setchannel #channel` to bind DestiFC commands to a specific channel.\n\n"
                f"🎨 **Custom Cards for your Server / Members:**\n"
                f"Want custom-branded cards, server champion trophies, or personal avatars in the bot? "
                f"Type `/custom_order` or DM **<@{OWNER_DISCORD_ID}>**!\n\n"
                f"🔗 **Official Communities:**\n"
                f"• [BeastlyFC Main Server]({BEASTLYFC_INVITE})\n"
                f"• [DestiFC Support & Updates]({SUPPORT_INVITE})"
            ),
            color=0x1E90FF
        )
        embed.set_footer(text="DestiFC • Type /help to explore all commands!")
        try:
            view = CustomOrderView(self.bot)
            await target_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"[Multi-Server] Could not send welcome embed in {guild.name}: {e}")

    @app_commands.command(name="setchannel", description="Server Admins: Bind DestiFC commands to a specific channel")
    @app_commands.describe(channel="The channel to restrict DestiFC commands to")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ You need **Manage Server** permission to use this command.", ephemeral=True)

        success = await database.set_guild_bot_channel(interaction.guild_id, channel.id)
        if success:
            await interaction.response.send_message(
                f"✅ **Channel Bound!** DestiFC commands are now restricted to {channel.mention}.\n"
                f"*(Server administrators can still run commands anywhere. Use `/resetchannel` to remove restrictions.)*",
                ephemeral=False
            )
        else:
            await interaction.response.send_message("❌ Failed to update channel settings in database.", ephemeral=True)

    @app_commands.command(name="resetchannel", description="Server Admins: Allow DestiFC commands in all channels")
    async def reset_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ You need **Manage Server** permission to use this command.", ephemeral=True)

        success = await database.set_guild_bot_channel(interaction.guild_id, None)
        if success:
            await interaction.response.send_message("✅ **Restrictions Removed!** DestiFC commands can now be used in any permitted channel.", ephemeral=False)
        else:
            await interaction.response.send_message("❌ Failed to reset channel settings in database.", ephemeral=True)

    @app_commands.command(name="custom_order", description="Order your own Custom Card with custom stats, perks, and personal avatar!")
    async def custom_order(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎨 DestiFC Custom Cards — Official Order Hub",
            description=(
                "Bring yourself, your server owner, or your club mascot into DestiFC as a high-tier playable superstar!\n\n"
                "### 🌟 What Every Custom Card Includes:\n"
                "• ⚡ **Choose your OVR (110–125+) & Position**\n"
                "• 🛡️ **Exclusive Perks & Traits** (Wall, Sniper, Playmaker, Speedster)\n"
                "• 🎨 **Custom Artwork / Photo** with dynamic walkout frame\n"
                "• 🏟️ **Playable in Starting 11** on the 3D stadium pitch lineup\n"
                "• 📦 **Direct Inventory Drop** or exclusive in your server's Draft pool!\n\n"
                "### 📩 How to Order:\n"
                f"1. **DM Developer Desti directly:** <@{OWNER_DISCORD_ID}>\n"
                f"2. Join **[BeastlyFC (Main Server)]({BEASTLYFC_INVITE})**\n"
                f"3. Join **[DestiFC Support Server]({SUPPORT_INVITE})** to open an order ticket\n"
                "4. Or click **Submit Order Form** below to send your details right now!"
            ),
            color=0xFFD700
        )
        embed.set_footer(text="DestiFC Custom Cards • Designed, balanced, and minted within 24 hours!")
        view = CustomOrderView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ServerSetupCog(bot))
