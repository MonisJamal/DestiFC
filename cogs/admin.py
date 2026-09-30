import discord
from discord.ext import commands
from discord import app_commands
import database
import time
from card_generator import generate_card, save_card_to_bytes
import io
from renderz_api import search_fifarenderz
from auth import is_team_admin_or_owner


class OfficialCardDropdown(discord.ui.Select):
    def __init__(self, target: discord.Member, players: list):
        self.target = target
        self.players = players
        
        options = []
        for i, p in enumerate(players[:25]):
            options.append(discord.SelectOption(
                label=f"{p.get('rating', '??')} {p.get('cardName', p.get('lastName', 'Unknown'))}",
                description=f"Pos: {p.get('position', 'UK')} | Program: {p.get('program', {}).get('name', 'None')}",
                value=str(i)
            ))
            
        super().__init__(placeholder="Select the exact version to give...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_idx = int(self.values[0])
        player_data = self.players[selected_idx]
        
        await database.add_player_to_inventory(self.target.id, player_data)
        name = player_data.get('cardName', player_data.get('lastName', 'Unknown'))
        ovr = player_data.get('rating', '??')
        
        embed = discord.Embed(
            title="🎁 Official Card Granted!", 
            description=f"Successfully dropped **{ovr} {name}** into {self.target.mention}'s inventory!",
            color=discord.Color.green()
        )
        img_url = player_data.get('images', {}).get('playerCardImage') or player_data.get('images', {}).get('playerImage')
        if img_url:
            embed.set_thumbnail(url=img_url)
        
        await interaction.followup.send(embed=embed)
        self.view.stop()

class OfficialCardView(discord.ui.View):
    def __init__(self, target: discord.Member, players: list):
        super().__init__(timeout=60)
        self.add_item(OfficialCardDropdown(target, players))

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Bot Developer Team commands")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ **Access Denied:** This command is strictly restricted to members of the Discord Application Team.", ephemeral=True)
            else:
                await interaction.followup.send("❌ **Access Denied:** This command is strictly restricted to members of the Discord Application Team.", ephemeral=True)
            return False
        return True

    @admin_group.command(name="give_custom", description="Create and give a custom card to a user")
    async def give_custom(
        self, 
        interaction: discord.Interaction, 
        target: discord.Member, 
        name: str, 
        ovr: int, 
        position: str, 
        player_image: discord.Attachment,
        background_image: discord.Attachment = None,
        nation_id: int = 38,
        club_id: int = 112139
    ):
        await interaction.response.defer()
        
        # Validate images
        if not player_image.content_type.startswith('image/'):
            return await interaction.followup.send("❌ The player image must be an image file (preferably a transparent PNG).")
            
        bg_url = background_image.url if background_image else "https://images-v2.renderz.app/bg_23_backgrounds_27_ANNIVERSARY27_LIVE_STATIC?verify=1"
        
        custom_id = -int(time.time()) # Unique negative ID to avoid official card collisions
        
        player_data = {
            "id": custom_id,
            "assetId": custom_id,
            "cardName": name,
            "lastName": name,
            "rating": ovr,
            "position": position.upper(),
            "nation": {"id": nation_id},
            "club": {"id": club_id},
            "images": {
                "playerCardImage": player_image.url,
                "playerCardBackground": bg_url
            },
            "stats": {
                "acc": ovr, "spd": ovr, "str": ovr, "fin": ovr, "sta": ovr, "sho": ovr, "dri": ovr, "def": ovr, "pas": ovr, "phy": ovr
            }
        }
        
        # Add to DB
        await database.add_player_to_inventory(target.id, player_data)
        
        # Generate the card preview
        try:
            image = generate_card(player_data, scale=4, animated=False)
            image_binary, filename = save_card_to_bytes(image)
            file = discord.File(fp=image_binary, filename=filename)
                
            embed = discord.Embed(title="✨ Custom Card Created!", description=f"Successfully granted a custom **{ovr} {name}** to {target.mention}!", color=discord.Color.magenta())
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"✅ Granted {name} to {target.mention}, but couldn't generate preview image: {e}")


    @admin_group.command(name="give_official", description="Search for an official FIFARenderZ card and give it to a user")
    async def give_official(self, interaction: discord.Interaction, target: discord.Member, search_query: str):
        await interaction.response.defer()
        
        players = search_fifarenderz(search_query)
        if not players:
            return await interaction.followup.send(f"❌ No official cards found for '{search_query}'. Try a different name.")
            
        view = OfficialCardView(target, players)
        await interaction.followup.send(f"Found {len(players)} results. Select the exact version to grant to {target.mention}:", view=view)


    @admin_group.command(name="add_custom_to_drafts", description="Create a custom card and add it to the global draft pool!")
    async def add_custom_to_drafts(
        self, 
        interaction: discord.Interaction, 
        name: str, 
        ovr: int, 
        position: str, 
        player_image: discord.Attachment,
        background_image: discord.Attachment = None,
        nation_id: int = 38,
        club_id: int = 112139
    ):
        await interaction.response.defer()
        
        # Validate images
        if not player_image.content_type.startswith('image/'):
            return await interaction.followup.send("❌ The player image must be an image file.")
            
        bg_url = background_image.url if background_image else "https://images-v2.renderz.app/bg_23_backgrounds_27_ANNIVERSARY27_LIVE_STATIC?verify=1"
        
        import time
        custom_id = -int(time.time()) # Unique negative ID
        
        player_data = {
            "id": custom_id,
            "assetId": custom_id,
            "cardName": name,
            "lastName": name,
            "rating": ovr,
            "position": position.upper(),
            "nation": {"id": nation_id},
            "club": {"id": club_id},
            "images": {
                "playerCardImage": player_image.url,
                "playerCardBackground": bg_url
            },
            "stats": {
                "acc": ovr, "spd": ovr, "str": ovr, "fin": ovr, "sta": ovr, "sho": ovr, "dri": ovr, "def": ovr, "pas": ovr, "phy": ovr
            },
            "is_custom": True
        }
        
        # Add to global draft pool
        await database.add_custom_draft_card(player_data)
        
        # Generate the card preview
        try:
            image = generate_card(player_data, scale=4, animated=False)
            image_binary, filename = save_card_to_bytes(image)
            file = discord.File(fp=image_binary, filename=filename)
            
            embed = discord.Embed(title="🌐 Added to Global Drafts!", description=f"Successfully injected the custom **{ovr} {name}** into the global draft pool! Players now have a random chance to pull this card from standard packs.", color=discord.Color.blue())
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"✅ Added {name} to global drafts, but couldn't generate preview image: {e}")


    @admin_group.command(name="restore_cards", description="Admin: Restore specific cards to a user by name and OVR")
    @app_commands.describe(user="Target user", cards_json="JSON list: [{\"name\":\"Kaka\",\"ovr\":122,\"qty\":1}]")
    async def restore_cards(self, interaction: discord.Interaction, user: discord.Member, cards_json: str):
        await interaction.response.defer(ephemeral=True)
        import json as _json
        from renderz_api import search_fifarenderz

        try:
            card_list = _json.loads(cards_json)
        except Exception:
            return await interaction.followup.send("\u274c Invalid JSON. Example: [{\"name\":\"Kaka\",\"ovr\":122,\"qty\":1}]", ephemeral=True)

        results = []
        failed = []

        for entry in card_list:
            name = entry.get("name", "")
            target_ovr = int(entry.get("ovr", 0))
            qty = int(entry.get("qty", 1))

            matches = search_fifarenderz(name, size=25)
            best = None
            for p in matches:
                if p.get("rating") == target_ovr:
                    best = p
                    break
            if not best and matches:
                best = min(matches, key=lambda p: abs(p.get("rating", 0) - target_ovr))

            if not best:
                failed.append(f"\u274c {name} ({target_ovr}) \u2014 not found on RenderZ")
                continue

            for _ in range(qty):
                await database.add_player_to_inventory(user.id, best)

            card_name = best.get("cardName") or best.get("lastName", name)
            actual_ovr = best.get("rating", target_ovr)
            results.append(f"\u2705 {qty}x **{card_name} ({actual_ovr})**")

        summary = "\n".join(results)
        if failed:
            summary += "\n\n" + "\n".join(failed)

        embed = discord.Embed(
            title=f"\U0001f6e0\ufe0f Cards Restored \u2192 {user.display_name}",
            description=summary or "Nothing was restored.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


    @admin_group.command(name="give", description="Admin: Give a player card to a user by name and OVR")
    @app_commands.describe(user="Target user", player_name="Player name to search", ovr="Exact OVR", quantity="How many copies (default 1)")
    async def give(self, interaction: discord.Interaction, user: discord.Member, player_name: str, ovr: int, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        import asyncio
        from renderz_api import search_fifarenderz

        matches = await asyncio.to_thread(search_fifarenderz, player_name, 25)
        best = None
        for p in matches:
            if p.get("rating") == ovr:
                best = p
                break
        if not best and matches:
            best = min(matches, key=lambda p: abs(p.get("rating", 0) - ovr))

        if not best:
            return await interaction.followup.send(f"❌ Could not find **{player_name}** on RenderZ.", ephemeral=True)

        for _ in range(quantity):
            await database.add_player_to_inventory(user.id, best)

        card_name = best.get("cardName") or best.get("lastName", player_name)
        actual_ovr = best.get("rating", ovr)
        embed = discord.Embed(
            title="🛠️ Card Given!",
            description=f"Gave **{quantity}x {card_name} ({actual_ovr})** to **{user.display_name}**.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="give_coins", description="Admin: Grant coins to a user")
    @app_commands.describe(user="Target user", amount="Amount of coins to give")
    async def give_coins(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount <= 0:
            return await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
        await database.add_coins(user.id, amount)
        embed = discord.Embed(
            title="🪙 Coins Granted!",
            description=f"Successfully added **{amount:,} Coins** to **{user.display_name}**'s balance.",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="give_vouchers", description="Admin: Grant draft vouchers to a user")
    @app_commands.describe(user="Target user", amount="Amount of vouchers to give")
    async def give_vouchers(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount <= 0:
            return await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
        await database.add_vouchers(user.id, amount)
        embed = discord.Embed(
            title="🎟️ Vouchers Granted!",
            description=f"Successfully added **{amount:,} Draft Vouchers** to **{user.display_name}**'s balance.",
            color=discord.Color.purple()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="remove_card", description="Admin: Remove a specific card from a user's inventory by ID")
    @app_commands.describe(user="Target user", inventory_id="The card ID in their inventory")
    async def remove_card(self, interaction: discord.Interaction, user: discord.Member, inventory_id: int):
        await interaction.response.defer(ephemeral=True)
        player = await database.get_player_by_inv_id(user.id, inventory_id)
        if not player:
            return await interaction.followup.send(f"❌ Card ID `{inventory_id}` not found in **{user.display_name}**'s inventory.", ephemeral=True)
            
        await database.remove_players_from_inventory(user.id, [inventory_id])
        from maps import extract_pos
        pos = extract_pos(player)
        embed = discord.Embed(
            title="🗑️ Card Removed",
            description=f"Successfully removed **{player['player_name']}** `({pos})` ({player['ovr']} OVR) [ID: `{inventory_id}`] from **{user.display_name}**'s inventory.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="remove_by_name", description="Admin: Remove cards from a user by player name and OVR")
    @app_commands.describe(user="Target user", player_name="Player name to remove", ovr="OVR of the card (optional)", quantity="How many copies to remove (default 1)")
    async def remove_by_name(self, interaction: discord.Interaction, user: discord.Member, player_name: str, ovr: int = None, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        inv = await database.get_inventory(user.id)
        
        matches = [
            p for p in inv 
            if player_name.lower() in str(p.get('player_name', '')).lower() 
            and (ovr is None or p.get('ovr') == ovr)
        ]
        
        if not matches:
            return await interaction.followup.send(f"❌ No matching cards found for '{player_name}' in **{user.display_name}**'s inventory.", ephemeral=True)
            
        to_remove = [p['id'] for p in matches[:quantity]]
        await database.remove_players_from_inventory(user.id, to_remove)
        
        embed = discord.Embed(
            title="🗑️ Cards Removed",
            description=f"Removed **{len(to_remove)}x {player_name}** from **{user.display_name}**'s inventory.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="clear_inventory", description="Admin: Clear a user's inventory (optionally only below a max OVR)")
    @app_commands.describe(user="Target user", max_ovr="Only remove cards at or below this OVR (leave empty for full wipe)")
    async def clear_inventory(self, interaction: discord.Interaction, user: discord.Member, max_ovr: int = None):
        await interaction.response.defer(ephemeral=True)
        inv = await database.get_inventory(user.id)
        if not inv:
            return await interaction.followup.send(f"**{user.display_name}**'s inventory is already empty.", ephemeral=True)
            
        if max_ovr is not None:
            to_remove = [p['id'] for p in inv if p.get('ovr', 0) <= max_ovr]
            action_desc = f"all cards rated **{max_ovr} OVR and below** ({len(to_remove)} cards)"
        else:
            to_remove = [p['id'] for p in inv]
            action_desc = f"**all {len(to_remove)} cards**"
            
        if not to_remove:
            return await interaction.followup.send(f"No cards found matching the criteria in **{user.display_name}**'s inventory.", ephemeral=True)
            
        await database.remove_players_from_inventory(user.id, to_remove)
        embed = discord.Embed(
            title="🧹 Inventory Cleared",
            description=f"Successfully wiped {action_desc} from **{user.display_name}**'s inventory.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # Top-level direct shortcuts
    @app_commands.command(name="give_card", description="Admin: Give a player card to a user by name and OVR")
    @app_commands.describe(user="Target user", player_name="Player name to search", ovr="Exact OVR", quantity="How many copies (default 1)")
    async def top_give_card(self, interaction: discord.Interaction, user: discord.Member, player_name: str, ovr: int, quantity: int = 1):
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.response.send_message("❌ **Access Denied:** Administrator command only.", ephemeral=True)
        await self.give(interaction, user, player_name, ovr, quantity)

    @app_commands.command(name="give_coins", description="Admin: Grant coins to a user")
    @app_commands.describe(user="Target user", amount="Amount of coins to give")
    async def top_give_coins(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.response.send_message("❌ **Access Denied:** Administrator command only.", ephemeral=True)
        await self.give_coins(interaction, user, amount)

    @app_commands.command(name="give_vouchers", description="Admin: Grant draft vouchers to a user")
    @app_commands.describe(user="Target user", amount="Amount of vouchers to give")
    async def top_give_vouchers(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            return await interaction.response.send_message("❌ **Access Denied:** Administrator command only.", ephemeral=True)
        await self.give_vouchers(interaction, user, amount)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
