import discord
from discord.ext import commands
from discord import app_commands
import database
import json

def get_price_limits(ovr: int):
    OVR_MAP = {
        122: (2_000_000_000, 4_000_000_000),      # 2B - 4B (QS: 1.5B)
        121: (900_000_000, 1_800_000_000),        # 900M - 1.8B (QS: 675M)
        120: (400_000_000, 800_000_000),          # 400M - 800M (QS: 300M)
        119: (70_000_000, 140_000_000),           # 70M - 140M (QS: 52.5M)
        118: (65_000_000, 130_000_000),           # 65M - 130M (QS: 48.75M)
        117: (60_000_000, 120_000_000),           # 60M - 120M (QS: 45M)
        116: (10_000_000, 20_000_000),            # 10M - 20M (QS: 7.5M)
        115: (9_000_000, 18_000_000),             # 9M - 18M (QS: 6.75M)
        114: (8_000_000, 16_000_000),             # 8M - 16M (QS: 6M)
        113: (7_000_000, 14_000_000),             # 7M - 14M (QS: 5.25M)
        112: (6_000_000, 12_000_000),             # 6M - 12M (QS: 4.5M)
    }
    if ovr in OVR_MAP:
        return OVR_MAP[ovr]
    if ovr > 122:
        max_p = 4_000_000_000 * (2 ** (ovr - 122))
        return max_p // 2, max_p
    if ovr >= 107:
        base = (ovr - 106) * 1_000_000
        return base, base * 2
    return 100, 200

def get_quicksell_value(ovr: int) -> int:
    min_p, _ = get_price_limits(ovr)
    return max(1, int(min_p * 0.70))

def format_price_short(val: int) -> str:
    if val >= 1_000_000_000:
        b = val / 1_000_000_000
        return f"{b:.2f}".rstrip('0').rstrip('.') + "B"
    elif val >= 1_000_000:
        m = val / 1_000_000
        return f"{m:.2f}".rstrip('0').rstrip('.') + "M"
    elif val >= 1_000:
        k = val / 1_000
        return f"{k:.1f}".rstrip('0').rstrip('.') + "K"
    return str(val)

from maps import extract_pos

async def sellable_inventory_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    user_id = interaction.user.id
    inventory = await database.get_inventory(user_id)
    locked_ids = await database.get_squad_locked_ids(user_id)
    
    choices = []
    for p in inventory:
        if p['id'] in locked_ids or p.get('locked', 0) or p.get('id', 0) < 0:
            continue
        pos = extract_pos(p)
        min_p, max_p = get_price_limits(p['ovr'])
        label = f"{p['player_name']} ({pos}) — {p['ovr']} OVR [{format_price_short(min_p)}-{format_price_short(max_p)}] (ID:{p['id']})"
        if current.lower() in label.lower() or current.lower() in str(p['id']):
            choices.append(app_commands.Choice(name=label[:100], value=p['id']))
            if len(choices) >= 25:
                break
    return choices

async def quicksell_inventory_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    user_id = interaction.user.id
    inventory = await database.get_inventory(user_id)
    locked_ids = await database.get_squad_locked_ids(user_id)
    
    choices = []
    for p in inventory:
        if p['id'] in locked_ids or p.get('locked', 0):
            continue
        pos = extract_pos(p)
        qs_val = get_quicksell_value(p['ovr'])
        label = f"{p['player_name']} ({pos}) — {p['ovr']} OVR [🪙 {format_price_short(qs_val)} Coins] (ID:{p['id']})"
        if current.lower() in label.lower() or current.lower() in str(p['id']):
            choices.append(app_commands.Choice(name=label[:100], value=p['id']))
            if len(choices) >= 25:
                break
    return choices


class MarketPagination(discord.ui.View):
    def __init__(self, user_id, market_rows, current_page, max_pages):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.market_rows = market_rows
        self.current_page = current_page
        self.max_pages = max_pages
        self.items_per_page = 15
        
        self.prev_button = discord.ui.Button(label="◀️ Prev", style=discord.ButtonStyle.primary, disabled=(self.current_page == 1))
        self.next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.primary, disabled=(self.current_page == self.max_pages))
        
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def update_page(self, interaction: discord.Interaction):
        self.prev_button.disabled = (self.current_page == 1)
        self.next_button.disabled = (self.current_page == self.max_pages)
        
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        desc = ""
        for r in self.market_rows[start_idx:end_idx]:
            pos = extract_pos(r)
            desc += f"**ID:** `{r['id']}` | **{r['player_name']}** `({pos})` ({r['ovr']} OVR) - 💰 **{r['price']:,}**\n"
            
        embed = discord.Embed(title="🌍 Global Transfer Market", description=desc, color=discord.Color.gold())
        embed.set_footer(text=f"Page {self.current_page}/{self.max_pages} | Total Listings: {len(self.market_rows)}\nUse /market buy <id> to purchase")
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your search session!", ephemeral=True)
        self.current_page -= 1
        await self.update_page(interaction)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your search session!", ephemeral=True)
        self.current_page += 1
        await self.update_page(interaction)


# ================== Interactive Market Dropdown Selling Views ==================

class CustomPriceModal(discord.ui.Modal, title="Custom Market Listing Price"):
    price_input = discord.ui.TextInput(
        label="Listing Price (Coins)",
        placeholder="Enter coin amount (e.g. 1500000000)",
        required=True
    )

    def __init__(self, user_id, card, min_p, max_p, pos):
        super().__init__()
        self.user_id = user_id
        self.card = card
        self.min_p = min_p
        self.max_p = max_p
        self.pos = pos
        self.price_input.placeholder = f"Between {min_p:,} and {max_p:,}"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val_str = self.price_input.value.replace(",", "").replace("_", "").replace(" ", "").strip()
            price = int(val_str)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid number entered.", ephemeral=True)

        if price < self.min_p or price > self.max_p:
            return await interaction.response.send_message(
                f"❌ Price out of range for {self.card['ovr']} OVR!\nAllowed Range: **{self.min_p:,}** to **{self.max_p:,}** coins.",
                ephemeral=True
            )

        await execute_market_list(interaction, self.user_id, self.card, price, self.pos)


async def execute_market_list(interaction: discord.Interaction, user_id: int, card: dict, price: int, pos: str):
    inventory_id = card['id']
    p = await database.get_db()
    row = await p.fetchrow('SELECT id FROM inventory WHERE id = $1 AND user_id = $2', inventory_id, user_id)
    if not row:
        return await interaction.response.send_message("❌ Card is no longer in your inventory.", ephemeral=True)

    await p.execute('''
        INSERT INTO market (seller_id, inventory_id, player_id, player_name, ovr, price, player_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    ''', user_id, inventory_id, card['player_id'], card['player_name'], card['ovr'], price, card['player_data'])
    await p.execute('DELETE FROM inventory WHERE id = $1', inventory_id)

    embed = discord.Embed(
        title="✅ Player Listed on Market!",
        description=f"Successfully listed **{card['player_name']}** `({pos})` ({card['ovr']} OVR) on the Transfer Market for **{price:,} Coins** 🪙!\n*(10% market tax applied on sale)*",
        color=discord.Color.green()
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.edit_message(embed=embed, view=None)


class SellPriceActionView(discord.ui.View):
    def __init__(self, user_id: int, card: dict, min_p: int, max_p: int, pos: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.card = card
        self.min_p = min_p
        self.max_p = max_p
        self.pos = pos

        self.min_button = discord.ui.Button(label=f"Min Price ({format_price_short(min_p)})", style=discord.ButtonStyle.secondary, emoji="📉")
        self.max_button = discord.ui.Button(label=f"Max Price ({format_price_short(max_p)})", style=discord.ButtonStyle.success, emoji="📈")
        self.custom_button = discord.ui.Button(label="Custom Price...", style=discord.ButtonStyle.primary, emoji="✍️")

        self.min_button.callback = self.list_min
        self.max_button.callback = self.list_max
        self.custom_button.callback = self.list_custom

        self.add_item(self.min_button)
        self.add_item(self.max_button)
        self.add_item(self.custom_button)

    async def list_min(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        await execute_market_list(interaction, self.user_id, self.card, self.min_p, self.pos)

    async def list_max(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        await execute_market_list(interaction, self.user_id, self.card, self.max_p, self.pos)

    async def list_custom(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        modal = CustomPriceModal(self.user_id, self.card, self.min_p, self.max_p, self.pos)
        await interaction.response.send_modal(modal)


class MarketSellSelect(discord.ui.Select):
    def __init__(self, user_id: int, eligible_cards: list):
        self.user_id = user_id
        self.cards_map = {str(c['id']): c for c in eligible_cards}
        
        options = []
        for c in eligible_cards[:25]:
            pos = extract_pos(c)
            min_p, max_p = get_price_limits(c['ovr'])
            options.append(discord.SelectOption(
                label=f"{c['player_name']} ({pos}) — {c['ovr']} OVR",
                value=str(c['id']),
                description=f"Range: {format_price_short(min_p)} – {format_price_short(max_p)} Coins | ID: {c['id']}",
                emoji="🔥" if c['ovr'] >= 120 else "✨" if c['ovr'] >= 117 else "⚽"
            ))
        super().__init__(placeholder="Select a player card from your club to list...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
            
        selected_id = self.values[0]
        card = self.cards_map.get(selected_id)
        if not card:
            return await interaction.response.send_message("❌ Card not found in inventory.", ephemeral=True)
            
        min_p, max_p = get_price_limits(card['ovr'])
        pos = extract_pos(card)
        
        view = SellPriceActionView(self.user_id, card, min_p, max_p, pos)
        embed = discord.Embed(
            title=f"🏷️ List {card['player_name']} `({pos})`",
            description=f"**OVR:** `{card['ovr']}` | **ID:** `{card['id']}`\n**Allowed Market Range:** 🪙 `{min_p:,}` to `{max_p:,}` Coins\n\nChoose an option to list this card:",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class MarketSellSelectView(discord.ui.View):
    def __init__(self, user_id: int, eligible_cards: list):
        super().__init__(timeout=90)
        self.add_item(MarketSellSelect(user_id, eligible_cards))


# ================== Interactive QuickSell Dropdown View ==================

class QuickSellSelectView(discord.ui.View):
    def __init__(self, user_id: int, eligible_cards: list, current_page: int = 1):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.eligible_cards = eligible_cards
        self.current_page = current_page
        self.items_per_page = 25
        self.max_pages = max(1, (len(eligible_cards) + self.items_per_page - 1) // self.items_per_page)
        self.setup_components()

    def setup_components(self):
        self.clear_items()
        start = (self.current_page - 1) * self.items_per_page
        page_cards = self.eligible_cards[start : start + self.items_per_page]
        
        if page_cards:
            options = []
            for c in page_cards:
                pos = extract_pos(c)
                qs_val = get_quicksell_value(c['ovr'])
                emoji = "🔥" if c['ovr'] >= 120 else "✨" if c['ovr'] >= 115 else "🪙"
                options.append(discord.SelectOption(
                    label=f"{c['player_name'][:25]} ({pos}) — {c['ovr']} OVR",
                    value=str(c['id']),
                    description=f"Quick Sell: 🪙 {format_price_short(qs_val)} Coins (ID: {c['id']})",
                    emoji=emoji
                ))
            select = discord.ui.Select(
                placeholder=f"Select cards to quick sell (Page {self.current_page}/{self.max_pages})...",
                min_values=1,
                max_values=len(options),
                options=options,
                row=0
            )
            select.callback = self.select_callback
            self.add_item(select)

        # Pagination buttons
        prev_btn = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary, disabled=(self.current_page <= 1), row=1)
        next_btn = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary, disabled=(self.current_page >= self.max_pages), row=1)
        prev_btn.callback = self.prev_page
        next_btn.callback = self.next_page
        self.add_item(prev_btn)
        self.add_item(next_btn)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
            
        select = [item for item in self.children if isinstance(item, discord.ui.Select)][0]
        selected_ids = [int(v) for v in select.values]
        
        cards_by_id = {c['id']: c for c in self.eligible_cards}
        sold_cards = [cards_by_id[cid] for cid in selected_ids if cid in cards_by_id]
        
        if not sold_cards:
            return await interaction.response.send_message("❌ Selected cards are no longer available in inventory.", ephemeral=True)
            
        total_coins = sum(get_quicksell_value(c['ovr']) for c in sold_cards)
        await database.remove_players_from_inventory(self.user_id, selected_ids)
        await database.add_coins(self.user_id, total_coins)
        
        # Remove sold cards from eligible list
        self.eligible_cards = [c for c in self.eligible_cards if c['id'] not in selected_ids]
        
        names_summary = "\n".join([f"• **{c['player_name']}** `({extract_pos(c)})` ({c['ovr']} OVR) — 🪙 {get_quicksell_value(c['ovr']):,} Coins" for c in sold_cards[:10]])
        if len(sold_cards) > 10:
            names_summary += f"\n*...and {len(sold_cards) - 10} more cards*"
            
        embed = discord.Embed(
            title="🪙 Quick Sell Successful!",
            description=f"Successfully quick sold **{len(sold_cards)} card(s)**:\n\n{names_summary}\n\n💰 **+{total_coins:,} Coins** added to your club balance!",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Valued at 75% of minimum market valuation. Remaining unlocked cards: {len(self.eligible_cards)}")
        
        if not self.eligible_cards:
            return await interaction.response.edit_message(embed=embed, view=None)
            
        self.max_pages = max(1, (len(self.eligible_cards) + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(self.current_page, self.max_pages)
        self.setup_components()
        await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        self.current_page -= 1
        self.setup_components()
        embed = discord.Embed(
            title="🪙 Quick Sell Dropdown Menu",
            description=f"Select one or multiple cards from the dropdown below to quick sell instantly for **75% of minimum market value**.\n\n📄 **Page {self.current_page}/{self.max_pages}** | Total Unlocked Cards: `{len(self.eligible_cards)}`",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        self.current_page += 1
        self.setup_components()
        embed = discord.Embed(
            title="🪙 Quick Sell Dropdown Menu",
            description=f"Select one or multiple cards from the dropdown below to quick sell instantly for **75% of minimum market value**.\n\n📄 **Page {self.current_page}/{self.max_pages}** | Total Unlocked Cards: `{len(self.eligible_cards)}`",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ================== Market Cog ==================

class MarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    market_group = app_commands.Group(name="market", description="Global Transfer Market")

    @market_group.command(name="sell", description="List a player on the transfer market (or open dropdown menu)")
    @app_commands.describe(
        inventory_id="Card to list (select from dropdown or leave empty to browse)",
        price="Price in coins (optional if using dropdown menu)"
    )
    @app_commands.autocomplete(inventory_id=sellable_inventory_autocomplete)
    async def sell(self, interaction: discord.Interaction, inventory_id: int = None, price: int = None):
        user_id = interaction.user.id

        # If user did not provide inventory_id or price, open interactive dropdown menu
        if inventory_id is None or price is None:
            await interaction.response.defer(ephemeral=True)
            inventory = await database.get_inventory(user_id)
            locked_ids = await database.get_squad_locked_ids(user_id)

            eligible = [
                p for p in inventory
                if p['id'] not in locked_ids and not p.get('locked', 0) and not (p.get('id', 0) < 0)
            ]
            if not eligible:
                return await interaction.followup.send("❌ You don't have any tradeable unlocked cards in your inventory.", ephemeral=True)

            view = MarketSellSelectView(user_id, eligible)
            embed = discord.Embed(
                title="🏷️ Transfer Market Listing Menu",
                description="Select a card from the dropdown menu below to choose your listing price:",
                color=discord.Color.gold()
            )
            return await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        player = await database.get_player_by_inv_id(user_id, inventory_id)
        if not player:
            return await interaction.followup.send("❌ Player not found in your inventory.", ephemeral=True)
            
        locked_ids = await database.get_squad_locked_ids(user_id)
        if inventory_id in locked_ids:
            return await interaction.followup.send("❌ You cannot sell a player that is in your active squad. Remove them first.", ephemeral=True)
        if player.get('locked', 0):
            return await interaction.followup.send("❌ This player is locked (🔒)! Unlock them with `/squad unlock` first.", ephemeral=True)
        if inventory_id < 0 or player.get('id', 0) < 0:
            return await interaction.followup.send("❌ Custom cards cannot be traded or listed on the market.", ephemeral=True)
            
        min_p, max_p = get_price_limits(player['ovr'])
        if price < min_p or price > max_p:
            return await interaction.followup.send(f"❌ Invalid price for a {player['ovr']} OVR card.\nAllowed Range: **{min_p:,}** to **{max_p:,}** coins.", ephemeral=True)
            
        pos = extract_pos(player)
        await execute_market_list(interaction, user_id, player, price, pos)

    @market_group.command(name="sell_menu", description="Open interactive dropdown menu to list cards on the market")
    async def sell_menu(self, interaction: discord.Interaction):
        await self.sell(interaction, inventory_id=None, price=None)

    @market_group.command(name="search", description="Search the global transfer market")
    @app_commands.describe(
        min_ovr="Minimum player OVR",
        max_ovr="Maximum player OVR",
        position="Filter by position (e.g. ST, CB, GK, CM, CAM, etc.)",
        name="Search player by name",
        sort="Sort listings by criteria"
    )
    @app_commands.choices(
        position=[
            app_commands.Choice(name="ST (Striker)", value="ST"),
            app_commands.Choice(name="CF (Centre Forward)", value="CF"),
            app_commands.Choice(name="LW (Left Wing)", value="LW"),
            app_commands.Choice(name="RW (Right Wing)", value="RW"),
            app_commands.Choice(name="CAM (Attacking Midfielder)", value="CAM"),
            app_commands.Choice(name="CM (Central Midfielder)", value="CM"),
            app_commands.Choice(name="CDM (Defensive Midfielder)", value="CDM"),
            app_commands.Choice(name="LM (Left Midfielder)", value="LM"),
            app_commands.Choice(name="RM (Right Midfielder)", value="RM"),
            app_commands.Choice(name="LB (Left Back)", value="LB"),
            app_commands.Choice(name="CB (Centre Back)", value="CB"),
            app_commands.Choice(name="RB (Right Back)", value="RB"),
            app_commands.Choice(name="LWB (Left Wing Back)", value="LWB"),
            app_commands.Choice(name="RWB (Right Wing Back)", value="RWB"),
            app_commands.Choice(name="GK (Goalkeeper)", value="GK"),
        ],
        sort=[
            app_commands.Choice(name="📈 Rating: High to Low (Default)", value="ovr_desc"),
            app_commands.Choice(name="📉 Rating: Low to High", value="ovr_asc"),
            app_commands.Choice(name="🪙 Price: Low to High (Cheapest)", value="price_asc"),
            app_commands.Choice(name="💰 Price: High to Low (Most Expensive)", value="price_desc"),
            app_commands.Choice(name="⏱️ Newest Listings", value="newest"),
        ]
    )
    async def search(
        self, 
        interaction: discord.Interaction, 
        min_ovr: int = 0, 
        max_ovr: int = 200, 
        position: str = None, 
        name: str = None,
        sort: str = "ovr_desc"
    ):
        await interaction.response.defer()
        
        query = "SELECT * FROM market WHERE ovr >= ? AND ovr <= ?"
        params = [min_ovr, max_ovr]
        
        if name:
            query += " AND LOWER(player_name) LIKE ?"
            params.append(f"%{name.lower().strip()}%")
            
        if sort == "price_asc":
            query += " ORDER BY price ASC, ovr DESC"
        elif sort == "price_desc":
            query += " ORDER BY price DESC, ovr DESC"
        elif sort == "ovr_asc":
            query += " ORDER BY ovr ASC, price ASC"
        elif sort == "newest":
            query += " ORDER BY id DESC"
        else: # ovr_desc
            query += " ORDER BY ovr DESC, price ASC"
            
        query += " LIMIT 150"
        
        p = await database.get_db()
        # Convert ? to $1, $2...
        pg_query = query
        for i in range(1, len(params) + 1):
            pg_query = pg_query.replace('?', f'${i}', 1)
        rows = await p.fetch(pg_query, *params)
        market_rows = [dict(r) for r in rows]
        
        if position:
            target_pos = position.upper().strip()
            market_rows = [r for r in market_rows if extract_pos(r).upper() == target_pos]
            
        if not market_rows:
            return await interaction.followup.send("🔍 No players found matching your search criteria.")
            
        items_per_page = 15
        max_pages = max(1, (len(market_rows) + items_per_page - 1) // items_per_page)
        
        view = MarketPagination(interaction.user.id, market_rows, 1, max_pages)
        
        desc = ""
        for r in market_rows[:items_per_page]:
            pos = extract_pos(r)
            desc += f"**ID:** `{r['id']}` | **{r['player_name']}** `({pos})` ({r['ovr']} OVR) - 💰 **{r['price']:,}**\n"
            
        embed = discord.Embed(title="🌍 Global Transfer Market Search", description=desc, color=discord.Color.gold())
        embed.set_footer(text=f"Page 1/{max_pages} | Found {len(market_rows)} Listings\nUse /market buy <id> to purchase")
        await interaction.followup.send(embed=embed, view=view)

    @market_group.command(name="buy", description="Buy a player from the transfer market")
    async def buy(self, interaction: discord.Interaction, listing_id: int):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        
        # Check inventory size
        inv_size = await database.get_inventory_size(user_id)
        if inv_size >= 1000:
            return await interaction.followup.send("❌ Your inventory is full! Quicksell or exchange some cards first.")
            
        user = await database.get_user(user_id)
        
        p = await database.get_db()
        listing = await p.fetchrow('SELECT * FROM market WHERE id = $1', listing_id)
        if not listing:
            return await interaction.followup.send("❌ This listing does not exist or has already been purchased.")
            
        listing = dict(listing)
        if listing['seller_id'] == user_id:
            return await interaction.followup.send("❌ You cannot buy your own listing! Use `/market cancel` instead.")
            
        price = listing['price']
        if user.get('coins', 0) < price:
            return await interaction.followup.send(f"❌ You cannot afford this player! You need **{price:,}** coins, but only have **{user.get('coins', 0):,}**.")
            
        seller_payout = int(price * 0.90)
        await p.execute('UPDATE users SET coins = GREATEST(0, coins - $1) WHERE user_id = $2', price, user_id)
        await p.execute('UPDATE users SET coins = coins + $1 WHERE user_id = $2', seller_payout, listing['seller_id'])
        await p.execute('DELETE FROM market WHERE id = $1', listing_id)
        
        player_data_raw = listing['player_data']
        p_data = json.loads(player_data_raw) if player_data_raw else {"id": listing['player_id'], "cardName": listing['player_name'], "rating": listing['ovr']}
        
        await p.execute('''
            INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data)
            VALUES ($1, $2, $3, $4, $5)
        ''', user_id, listing['player_id'], listing['player_name'], listing['ovr'], json.dumps(p_data))
            
        pos = extract_pos(listing)
        await interaction.followup.send(f"🎉 Congratulations! You purchased **{listing['player_name']}** `({pos})` ({listing['ovr']} OVR) for **{price:,}** coins!")

    @market_group.command(name="cancel", description="Cancel one of your market listings")
    async def cancel(self, interaction: discord.Interaction, listing_id: int):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        
        p = await database.get_db()
        listing = await p.fetchrow('SELECT * FROM market WHERE id = $1', listing_id)
        if not listing:
            return await interaction.followup.send("❌ Listing not found.")
            
        listing = dict(listing)
        if listing['seller_id'] != user_id:
            return await interaction.followup.send("❌ You do not own this listing.")
            
        await p.execute('''
            INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data)
            VALUES ($1, $2, $3, $4, $5)
        ''', user_id, listing['player_id'], listing['player_name'], listing['ovr'], listing['player_data'])
        await p.execute('DELETE FROM market WHERE id = $1', listing_id)
            
        pos = extract_pos(listing)
        await interaction.followup.send(f"✅ Listing cancelled! **{listing['player_name']}** `({pos})` ({listing['ovr']} OVR) has been returned to your inventory.")

    @market_group.command(name="sell_page", description="Bulk list all players on a page of your inventory at min price")
    @app_commands.describe(min_ovr="Only list cards at or above this OVR", max_ovr="Only list cards at or below this OVR")
    async def sell_page(self, interaction: discord.Interaction, min_ovr: int = 112, max_ovr: int = 119):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        inventory = await database.get_inventory(user_id)
        locked_ids = await database.get_squad_locked_ids(user_id)
        eligible = [
            p for p in inventory
            if min_ovr <= p.get("ovr", 0) <= max_ovr
            and int(p.get("id", -1)) not in locked_ids
            and not p.get("locked", 0)
            and not (p.get("id", 0) < 0)
        ]

        if not eligible:
            return await interaction.followup.send(f"❌ No eligible cards found between {min_ovr}-{max_ovr} OVR (excludes squad, locked & untradable cards).", ephemeral=True)

        listed = []
        p_db = await database.get_db()
        for p in eligible:
            min_p, _ = get_price_limits(p["ovr"])
            await p_db.execute(
                "INSERT INTO market (seller_id, inventory_id, player_id, player_name, ovr, price, player_data) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                user_id, p["id"], p["player_id"], p["player_name"], p["ovr"], min_p, p["player_data"]
            )
            await p_db.execute("DELETE FROM inventory WHERE id = $1", p["id"])
            listed.append(f"**{p['player_name']}** `({extract_pos(p)})` ({p['ovr']}) @ 🪙 {min_p:,}")

        lines = "\n".join(listed[:20])
        extra = f"\n*...and {len(listed)-20} more*" if len(listed) > 20 else ""
        embed = discord.Embed(
            title=f"📦 Bulk Listed {len(listed)} Players!",
            description=lines + extra,
            color=discord.Color.green()
        )
        embed.set_footer(text="All cards listed at minimum price. 10% tax on sale.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="quicksell", description="Quick sell a player for 70% of min market value (or open dropdown menu)")
    @app_commands.describe(inventory_id="Card to quick sell (select from dropdown or leave empty to browse)")
    @app_commands.autocomplete(inventory_id=quicksell_inventory_autocomplete)
    async def quicksell(self, interaction: discord.Interaction, inventory_id: int = None):
        user_id = interaction.user.id

        if inventory_id is None:
            await interaction.response.defer(ephemeral=True)
            inventory = await database.get_inventory(user_id)
            locked_ids = await database.get_squad_locked_ids(user_id)
            eligible = [
                p for p in inventory
                if p['id'] not in locked_ids and not p.get('locked', 0)
            ]
            if not eligible:
                return await interaction.followup.send("❌ You don't have any unlocked cards in your inventory to quick sell.", ephemeral=True)

            view = QuickSellSelectView(user_id, eligible)
            embed = discord.Embed(
                title="🪙 Quick Sell Menu",
                description="Select a card from the dropdown menu below to quick sell it instantly for **70% of its minimum market value**:",
                color=discord.Color.gold()
            )
            return await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        await interaction.response.defer()
        player = await database.get_player_by_inv_id(user_id, inventory_id)
        if not player:
            return await interaction.followup.send(f"❌ You don't own a card with ID `{inventory_id}` in your inventory.", ephemeral=True)

        locked_ids = await database.get_squad_locked_ids(user_id)
        if inventory_id in locked_ids:
            return await interaction.followup.send(f"❌ **{player['player_name']}** is in your active starting XI! Remove them with `/squad set` first.", ephemeral=True)

        if player.get("locked", 0):
            return await interaction.followup.send(f"❌ **{player['player_name']}** is locked (🔒)! Unlock them with `/squad unlock {inventory_id}` first.", ephemeral=True)

        ovr = player["ovr"]
        sell_val = get_quicksell_value(ovr)
        pos = extract_pos(player)

        await database.remove_players_from_inventory(user_id, [inventory_id])
        await database.add_coins(user_id, sell_val)

        embed = discord.Embed(
            title="🪙 Card Quick Sold!",
            description=f"Quick sold **{player['player_name']}** `({pos})` ({ovr} OVR) for **{sell_val:,} Coins** 💰\n*(70% of minimum market valuation)*",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quicksell_bulk", description="Bulk quick sell all unlocked, non-squad cards in an OVR range for 70% min value")
    @app_commands.describe(max_ovr="Maximum OVR to quick sell (e.g. 116)", min_ovr="Minimum OVR to quick sell (default 0)")
    async def quicksell_bulk(self, interaction: discord.Interaction, max_ovr: int, min_ovr: int = 0):
        await interaction.response.defer()
        user_id = interaction.user.id

        inventory = await database.get_inventory(user_id)
        locked_ids = await database.get_squad_locked_ids(user_id)

        eligible = [
            p for p in inventory
            if min_ovr <= p.get("ovr", 0) <= max_ovr
            and int(p.get("id", -1)) not in locked_ids
            and not p.get("locked", 0)
        ]

        if not eligible:
            return await interaction.followup.send(f"❌ No eligible cards found between OVR {min_ovr}–{max_ovr} to quick sell (starting XI and locked cards are protected).", ephemeral=True)

        total_coins = sum(get_quicksell_value(p["ovr"]) for p in eligible)
        to_delete = [p["id"] for p in eligible]

        await database.remove_players_from_inventory(user_id, to_delete)
        await database.add_coins(user_id, total_coins)

        embed = discord.Embed(
            title=f"🪙 Bulk Quick Sold {len(eligible)} Cards!",
            description=f"Successfully quick sold **{len(eligible)} cards** (OVR {min_ovr}–{max_ovr}) for a total of **{total_coins:,} Coins** 💰!\n*(75% of minimum market valuation each)*",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Active starting XI and locked cards were safely protected.")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MarketCog(bot))
