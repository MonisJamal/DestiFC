import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import database
# aiosqlite migrated
import json

from maps import extract_pos
from cogs.market import format_price_short


class TradeConfirmView(discord.ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, 
                 give_cards: list, give_coins: int, give_vouchers: int,
                 recv_cards: list, recv_coins: int, recv_vouchers: int):
        super().__init__(timeout=120)
        self.sender = sender
        self.recipient = recipient
        self.give_cards = give_cards
        self.give_coins = give_coins
        self.give_vouchers = give_vouchers
        self.recv_cards = recv_cards
        self.recv_coins = recv_coins
        self.recv_vouchers = recv_vouchers

    @discord.ui.button(label="Accept Trade ✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.recipient.id:
            return await interaction.response.send_message("❌ Only the recipient can accept this trade proposal.", ephemeral=True)
            
        await interaction.response.defer()

        # Re-verify Sender Assets
        s_user = await database.get_user(self.sender.id)
        if s_user.get("coins", 0) < self.give_coins:
            return await interaction.followup.send(f"❌ Trade failed: {self.sender.mention} no longer has enough coins.")
        if s_user.get("vouchers", 0) < self.give_vouchers:
            return await interaction.followup.send(f"❌ Trade failed: {self.sender.mention} no longer has enough vouchers.")
            
        s_locked = await database.get_squad_locked_ids(self.sender.id)
        s_inv = await database.get_inventory(self.sender.id)
        s_inv_map = {p["id"]: p for p in s_inv}
        for c in self.give_cards:
            if c["id"] not in s_inv_map:
                return await interaction.followup.send(f"❌ Trade failed: {self.sender.mention} no longer owns **{c['player_name']}** (ID: `{c['id']}`).")
            if c["id"] in s_locked or s_inv_map[c["id"]].get("locked", 0):
                return await interaction.followup.send(f"❌ Trade failed: **{c['player_name']}** is locked or in {self.sender.mention}'s squad.")

        # Re-verify Recipient Assets
        r_user = await database.get_user(self.recipient.id)
        if r_user.get("coins", 0) < self.recv_coins:
            return await interaction.followup.send(f"❌ Trade failed: {self.recipient.mention} does not have enough coins ({self.recv_coins:,} required).")
        if r_user.get("vouchers", 0) < self.recv_vouchers:
            return await interaction.followup.send(f"❌ Trade failed: {self.recipient.mention} does not have enough vouchers ({self.recv_vouchers} required).")

        r_locked = await database.get_squad_locked_ids(self.recipient.id)
        r_inv = await database.get_inventory(self.recipient.id)
        r_inv_map = {p["id"]: p for p in r_inv}
        for c in self.recv_cards:
            if c["id"] not in r_inv_map:
                return await interaction.followup.send(f"❌ Trade failed: {self.recipient.mention} does not own **{c['player_name']}** (ID: `{c['id']}`).")
            if c["id"] in r_locked or r_inv_map[c["id"]].get("locked", 0):
                return await interaction.followup.send(f"❌ Trade failed: **{c['player_name']}** is locked or in {self.recipient.mention}'s squad.")

        # Execute Atomic Transfer
        p = await database.get_db()
        async with p.acquire() as conn:
            async with conn.transaction():
                # Transfer Coins
                if self.give_coins > 0:
                    await conn.execute("UPDATE users SET coins = GREATEST(0, coins - $1) WHERE user_id = $2", self.give_coins, self.sender.id)
                    await conn.execute("UPDATE users SET coins = coins + $1 WHERE user_id = $2", self.give_coins, self.recipient.id)
                if self.recv_coins > 0:
                    await conn.execute("UPDATE users SET coins = GREATEST(0, coins - $1) WHERE user_id = $2", self.recv_coins, self.recipient.id)
                    await conn.execute("UPDATE users SET coins = coins + $1 WHERE user_id = $2", self.recv_coins, self.sender.id)

                # Transfer Vouchers
                if self.give_vouchers > 0:
                    await conn.execute("UPDATE users SET vouchers = GREATEST(0, vouchers - $1) WHERE user_id = $2", self.give_vouchers, self.sender.id)
                    await conn.execute("UPDATE users SET vouchers = vouchers + $1 WHERE user_id = $2", self.give_vouchers, self.recipient.id)
                if self.recv_vouchers > 0:
                    await conn.execute("UPDATE users SET vouchers = GREATEST(0, vouchers - $1) WHERE user_id = $2", self.recv_vouchers, self.recipient.id)
                    await conn.execute("UPDATE users SET vouchers = vouchers + $1 WHERE user_id = $2", self.recv_vouchers, self.sender.id)

                # Transfer Sender Cards to Recipient
                for c in self.give_cards:
                    await conn.execute("UPDATE inventory SET user_id = $1 WHERE id = $2", self.recipient.id, c["id"])

                # Transfer Recipient Cards to Sender
                for c in self.recv_cards:
                    await conn.execute("UPDATE inventory SET user_id = $1 WHERE id = $2", self.sender.id, c["id"])

        # Immediately invalidate caches so cards appear instantly in inventory / squad
        database.invalidate_user_cache(self.sender.id)
        database.invalidate_user_cache(self.recipient.id)

        # Disable buttons
        for child in self.children:
            child.disabled = True
            
        success_embed = discord.Embed(
            title="🎉 Trade Completed Successfully!",
            description=f"**{self.sender.display_name}** and **{self.recipient.display_name}** have successfully swapped assets!",
            color=discord.Color.green()
        )
        try:
            await interaction.edit_original_response(embed=success_embed, view=self)
        except Exception:
            if interaction.message:
                await interaction.message.edit(embed=success_embed, view=self)
        self.stop()

    @discord.ui.button(label="Decline / Cancel ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.sender.id, self.recipient.id):
            return await interaction.response.send_message("❌ You are not involved in this trade.", ephemeral=True)
            
        for child in self.children:
            child.disabled = True
            
        cancel_embed = discord.Embed(
            title="❌ Trade Cancelled",
            description=f"The trade was cancelled by {interaction.user.mention}.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=cancel_embed, view=self)
        self.stop()


# ================== Interactive Trade Builder Views ==================

class TradeCurrencyModal(discord.ui.Modal, title="Set Coins & Vouchers"):
    give_coins_in = discord.ui.TextInput(
        label="Coins You Give (Optional)",
        placeholder="e.g. 50000000 (0 for none)",
        default="0",
        required=False
    )
    give_vouchers_in = discord.ui.TextInput(
        label="Draft Vouchers You Give (Optional)",
        placeholder="e.g. 2 (0 for none)",
        default="0",
        required=False
    )
    recv_coins_in = discord.ui.TextInput(
        label="Coins You Request From Them (Optional)",
        placeholder="e.g. 10000000 (0 for none)",
        default="0",
        required=False
    )
    recv_vouchers_in = discord.ui.TextInput(
        label="Vouchers You Request (Optional)",
        placeholder="e.g. 1 (0 for none)",
        default="0",
        required=False
    )

    def __init__(self, builder_view):
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.builder_view.give_coins = max(0, int(self.give_coins_in.value.replace(",", "").strip() or 0))
            self.builder_view.give_vouchers = max(0, int(self.give_vouchers_in.value.replace(",", "").strip() or 0))
            self.builder_view.recv_coins = max(0, int(self.recv_coins_in.value.replace(",", "").strip() or 0))
            self.builder_view.recv_vouchers = max(0, int(self.recv_vouchers_in.value.replace(",", "").strip() or 0))
        except ValueError:
            return await interaction.response.send_message("❌ Invalid number entered.", ephemeral=True)

        embed = self.builder_view.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self.builder_view)


class TradeCardSelect(discord.ui.Select):
    def __init__(self, builder_view, eligible_cards: list):
        self.builder_view = builder_view
        self.cards_map = {str(c['id']): c for c in eligible_cards}

        options = []
        for c in eligible_cards[:25]:
            pos = extract_pos(c)
            options.append(discord.SelectOption(
                label=f"{c['player_name']} ({pos}) — {c['ovr']} OVR",
                value=str(c['id']),
                description=f"ID: {c['id']}",
                emoji="🔥" if c['ovr'] >= 120 else "✨" if c['ovr'] >= 117 else "⚽"
            ))

        if not options:
            options.append(discord.SelectOption(
                label="No tradeable cards in inventory",
                value="none",
                description="Use the button below to offer Coins / Vouchers"
            ))
            super().__init__(
                placeholder="No cards available (Offer Coins/Vouchers below)...",
                min_values=0,
                max_values=1,
                options=options,
                disabled=True
            )
        else:
            super().__init__(
                placeholder="Select cards to offer (multi-select supported)...",
                min_values=0,
                max_values=min(25, len(options)),
                options=options
            )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder_view.sender.id:
            return await interaction.response.send_message("❌ This is not your trade session.", ephemeral=True)

        selected_cards = [self.cards_map[val] for val in self.values if val in self.cards_map]
        self.builder_view.selected_cards = selected_cards
        embed = self.builder_view.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self.builder_view)


class TradeBuilderView(discord.ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, eligible_cards: list):
        super().__init__(timeout=120)
        self.sender = sender
        self.recipient = recipient
        self.eligible_cards = eligible_cards
        self.selected_cards = []
        self.give_coins = 0
        self.give_vouchers = 0
        self.recv_coins = 0
        self.recv_vouchers = 0

        self.select_menu = TradeCardSelect(self, eligible_cards)
        self.add_item(self.select_menu)

    def generate_embed(self) -> discord.Embed:
        offer_lines = []
        if self.selected_cards:
            cards_str = ", ".join([f"**{c['player_name']}** `({extract_pos(c)})` ({c['ovr']} OVR)" for c in self.selected_cards])
            offer_lines.append(f"🎴 **Cards ({len(self.selected_cards)}):** {cards_str}")
        if self.give_coins > 0:
            offer_lines.append(f"🪙 **Coins:** {self.give_coins:,}")
        if self.give_vouchers > 0:
            offer_lines.append(f"🎫 **Vouchers:** {self.give_vouchers}")
        if not offer_lines:
            offer_lines.append("*(No cards or currency selected yet)*")

        req_lines = []
        if self.recv_coins > 0:
            req_lines.append(f"🪙 **Coins:** {self.recv_coins:,}")
        if self.recv_vouchers > 0:
            req_lines.append(f"🎫 **Vouchers:** {self.recv_vouchers}")
        if not req_lines:
            req_lines.append("*(None)*")

        embed = discord.Embed(
            title=f"🤝 Trade Builder ➔ {self.recipient.display_name}",
            description="Use the **dropdown menu** to select cards, and the buttons below to customize coins/vouchers:",
            color=discord.Color.gold()
        )
        embed.add_field(name=f"📤 {self.sender.display_name} Gives:", value="\n".join(offer_lines), inline=False)
        embed.add_field(name=f"📥 {self.recipient.display_name} Gives:", value="\n".join(req_lines), inline=False)
        embed.set_footer(text="Click 'Send Proposal' when you're ready to dispatch the trade.")
        return embed

    @discord.ui.button(label="Coins / Vouchers 🪙", style=discord.ButtonStyle.secondary, emoji="💰")
    async def set_currency(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ This is not your trade session.", ephemeral=True)
        modal = TradeCurrencyModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Send Proposal 🚀", style=discord.ButtonStyle.success)
    async def send_proposal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ This is not your trade session.", ephemeral=True)

        if not self.selected_cards and self.give_coins == 0 and self.give_vouchers == 0 and self.recv_coins == 0 and self.recv_vouchers == 0:
            return await interaction.response.send_message("❌ You cannot send an empty trade proposal.", ephemeral=True)

        # Defer immediately to guarantee 100% reliable 1st-click response
        await interaction.response.defer()

        # Sender balance validation
        sender_data = await database.get_user(self.sender.id)
        if sender_data.get("coins", 0) < self.give_coins:
            return await interaction.followup.send(f"❌ You don't have enough coins! Balance: **{sender_data.get('coins', 0):,}**", ephemeral=True)
        if sender_data.get("vouchers", 0) < self.give_vouchers:
            return await interaction.followup.send(f"❌ You don't have enough vouchers! Balance: **{sender_data.get('vouchers', 0)}**", ephemeral=True)

        # Create public trade confirmation view for recipient
        offer_lines = []
        if self.selected_cards:
            cards_str = ", ".join([f"**{c['player_name']}** `({extract_pos(c)})` ({c['ovr']} OVR) [ID:`{c['id']}`]" for c in self.selected_cards])
            offer_lines.append(f"🎴 **Cards:** {cards_str}")
        if self.give_coins > 0:
            offer_lines.append(f"🪙 **Coins:** {self.give_coins:,}")
        if self.give_vouchers > 0:
            offer_lines.append(f"🎫 **Vouchers:** {self.give_vouchers}")

        req_lines = []
        if self.recv_coins > 0:
            req_lines.append(f"🪙 **Coins:** {self.recv_coins:,}")
        if self.recv_vouchers > 0:
            req_lines.append(f"🎫 **Vouchers:** {self.recv_vouchers}")
        if not req_lines:
            req_lines.append("*(Nothing requested)*")

        proposal_embed = discord.Embed(
            title="🤝 Official Trade Proposal",
            description=f"{self.sender.mention} is proposing a trade to {self.recipient.mention}!",
            color=discord.Color.gold()
        )
        proposal_embed.add_field(name=f"📤 {self.sender.display_name} Offers:", value="\n".join(offer_lines), inline=False)
        proposal_embed.add_field(name=f"📥 {self.recipient.display_name} Gives:", value="\n".join(req_lines), inline=False)
        proposal_embed.set_footer(text="This trade offer expires in 2 minutes.")

        confirm_view = TradeConfirmView(
            sender=self.sender,
            recipient=self.recipient,
            give_cards=self.selected_cards,
            give_coins=self.give_coins,
            give_vouchers=self.give_vouchers,
            recv_cards=[],
            recv_coins=self.recv_coins,
            recv_vouchers=self.recv_vouchers
        )

        for child in self.children:
            child.disabled = True
            
        try:
            await interaction.edit_original_response(content="✅ Trade proposal dispatched!", view=self)
        except Exception:
            pass

        target_channel = interaction.channel
        if not target_channel and interaction.guild:
            target_channel = interaction.guild.get_channel(interaction.channel_id)

        if target_channel:
            await target_channel.send(content=f"{self.recipient.mention}, you have received a trade proposal!", embed=proposal_embed, view=confirm_view)
        else:
            await interaction.followup.send(content=f"{self.recipient.mention}, you have received a trade proposal!", embed=proposal_embed, view=confirm_view)


# ================== Trade Cog ==================

class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    trade_group = app_commands.Group(name="trade", description="Trade players, coins, and vouchers with other users")

    @trade_group.command(name="menu", description="Open an interactive dropdown menu to build and send a trade")
    @app_commands.describe(user="User you want to trade with")
    async def trade_menu(self, interaction: discord.Interaction, user: discord.Member):
        if user.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot trade with yourself!", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ You cannot trade with bots!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        inventory, locked_ids = await asyncio.gather(
            database.get_inventory(user_id),
            database.get_squad_locked_ids(user_id)
        )

        eligible = [
            p for p in inventory
            if p['id'] not in locked_ids and not p.get('locked', 0) and not (p.get('id', 0) < 0)
        ]

        view = TradeBuilderView(interaction.user, user, eligible)
        embed = view.generate_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @trade_group.command(name="send", description="Send a trade proposal to another user (or open interactive builder)")
    @app_commands.describe(
        user="User to trade with",
        give_card_ids="Comma-separated card IDs you give (e.g. 102, 105)",
        give_coins="Coins you give (optional)",
        give_vouchers="Draft vouchers you give (optional)",
        request_card_ids="Comma-separated card IDs you want (optional)",
        request_coins="Coins you want from them (optional)",
        request_vouchers="Vouchers you want from them (optional)"
    )
    async def send_trade(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        give_card_ids: str = None,
        give_coins: int = 0,
        give_vouchers: int = 0,
        request_card_ids: str = None,
        request_coins: int = 0,
        request_vouchers: int = 0
    ):
        if user.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot trade with yourself!", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ You cannot trade with bots!", ephemeral=True)

        # If no specific IDs or currency passed, route to interactive dropdown menu
        if not give_card_ids and give_coins == 0 and give_vouchers == 0 and not request_card_ids and request_coins == 0 and request_vouchers == 0:
            return await self.trade_menu.callback(self, interaction, user)

        await interaction.response.defer()

        # Validate Numbers
        give_coins = max(0, give_coins)
        give_vouchers = max(0, give_vouchers)
        request_coins = max(0, request_coins)
        request_vouchers = max(0, request_vouchers)

        # Sender balance validation
        sender_data = await database.get_user(interaction.user.id)
        if sender_data.get("coins", 0) < give_coins:
            return await interaction.followup.send(f"❌ You don't have enough coins! You have **{sender_data.get('coins', 0):,}** coins.", ephemeral=True)
        if sender_data.get("vouchers", 0) < give_vouchers:
            return await interaction.followup.send(f"❌ You don't have enough vouchers! You have **{sender_data.get('vouchers', 0)}** vouchers.", ephemeral=True)

        # Parse & Validate Sender Cards
        give_cards_list = []
        if give_card_ids:
            s_locked = await database.get_squad_locked_ids(interaction.user.id)
            for raw_id in give_card_ids.split(","):
                raw_id = raw_id.strip()
                if not raw_id: continue
                try:
                    cid = int(raw_id)
                except ValueError:
                    return await interaction.followup.send(f"❌ Invalid card ID: `{raw_id}`", ephemeral=True)
                
                player = await database.get_player_by_inv_id(interaction.user.id, cid)
                if not player:
                    return await interaction.followup.send(f"❌ Card ID `{cid}` not found in your inventory.", ephemeral=True)
                if cid in s_locked or player.get("locked", 0):
                    return await interaction.followup.send(f"❌ **{player['player_name']}** (`{cid}`) is locked or in your starting 11! Unlock/unequip first.", ephemeral=True)
                if cid < 0 or player.get("id", 0) < 0:
                    return await interaction.followup.send(f"❌ Custom cards cannot be traded on the market or in direct trades.", ephemeral=True)
                give_cards_list.append(player)

        # Parse & Validate Recipient Cards
        recv_cards_list = []
        if request_card_ids:
            r_locked = await database.get_squad_locked_ids(user.id)
            for raw_id in request_card_ids.split(","):
                raw_id = raw_id.strip()
                if not raw_id: continue
                try:
                    cid = int(raw_id)
                except ValueError:
                    return await interaction.followup.send(f"❌ Invalid requested card ID: `{raw_id}`", ephemeral=True)
                
                player = await database.get_player_by_inv_id(user.id, cid)
                if not player:
                    return await interaction.followup.send(f"❌ Card ID `{cid}` was not found in **{user.display_name}**'s inventory.", ephemeral=True)
                if cid in r_locked or player.get("locked", 0):
                    return await interaction.followup.send(f"❌ **{player['player_name']}** (`{cid}`) is locked or in **{user.display_name}**'s squad.", ephemeral=True)
                recv_cards_list.append(player)

        # Build Description
        offer_lines = []
        if give_cards_list:
            card_desc = ", ".join([f"**{p['player_name']}** `({extract_pos(p)})` ({p['ovr']} OVR) [ID:`{p['id']}`]" for p in give_cards_list])
            offer_lines.append(f"🎴 **Cards:** {card_desc}")
        if give_coins > 0:
            offer_lines.append(f"🪙 **Coins:** {give_coins:,}")
        if give_vouchers > 0:
            offer_lines.append(f"🎫 **Vouchers:** {give_vouchers}")
        if not offer_lines:
            offer_lines.append("*(Nothing)*")

        req_lines = []
        if recv_cards_list:
            card_desc = ", ".join([f"**{p['player_name']}** `({extract_pos(p)})` ({p['ovr']} OVR) [ID:`{p['id']}`]" for p in recv_cards_list])
            req_lines.append(f"🎴 **Cards:** {card_desc}")
        if request_coins > 0:
            req_lines.append(f"🪙 **Coins:** {request_coins:,}")
        if request_vouchers > 0:
            req_lines.append(f"🎫 **Vouchers:** {request_vouchers}")
        if not req_lines:
            req_lines.append("*(Nothing)*")

        embed = discord.Embed(
            title="🤝 Official Trade Proposal",
            description=f"{interaction.user.mention} is proposing a trade to {user.mention}!",
            color=discord.Color.gold()
        )
        embed.add_field(name=f"📤 {interaction.user.display_name} Offers:", value="\n".join(offer_lines), inline=False)
        embed.add_field(name=f"📥 {user.display_name} Gives:", value="\n".join(req_lines), inline=False)
        embed.set_footer(text="This trade offer expires in 2 minutes.")

        view = TradeConfirmView(
            sender=interaction.user,
            recipient=user,
            give_cards=give_cards_list,
            give_coins=give_coins,
            give_vouchers=give_vouchers,
            recv_cards=recv_cards_list,
            recv_coins=request_coins,
            recv_vouchers=request_vouchers
        )

        await interaction.followup.send(content=f"{user.mention}, you have received a trade proposal!", embed=embed, view=view)

    @app_commands.command(name="trade_menu", description="Open interactive trade builder menu with another user")
    @app_commands.describe(user="User you want to trade with")
    async def top_trade_menu(self, interaction: discord.Interaction, user: discord.Member):
        await self.trade_menu.callback(self, interaction, user)


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
