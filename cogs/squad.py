import discord
from discord.ext import commands
from discord import app_commands
import json

import database

class SquadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    squad_group = app_commands.Group(name="squad", description="Manage your starting XI")

    @squad_group.command(name="view", description="View your current starting XI")
    async def view_squad(self, interaction: discord.Interaction):
        await interaction.response.defer()
        squad = await database.get_squad(interaction.user.id)
        formation = squad.get("formation", "4-3-3")
        players = squad.get("players", {})
        
        inventory = await database.get_inventory(interaction.user.id)
        inv_dict = {p['id']: p['player_data'] for p in inventory}
        
        total_ovr = 0
        count = 0
        
        for pos, player in players.items():
            if player:
                total_ovr += player['ovr']
                count += 1
                
        team_ovr = round(total_ovr / 11) if count > 0 else 0
        
        from lineup_generator import generate_lineup_image
        import io
        
        try:
            img = generate_lineup_image(squad, inv_dict)
            with io.BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='lineup.png')
                
                embed = discord.Embed(title=f"🛡️ {interaction.user.display_name}'s Squad", description=f"**Formation:** {formation} | **Team OVR:** {team_ovr}", color=discord.Color.blue())
                embed.set_image(url="attachment://lineup.png")
                
                if count < 11:
                    embed.set_footer(text="Your squad is incomplete! Use /squad set to add players.")
                    
                await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to generate lineup image: {e}")

    @squad_group.command(name="formation", description="Change your team's formation (Warning: Resets your squad)")
    @app_commands.choices(new_formation=[
        app_commands.Choice(name="4-3-3 (Attack)", value="4-3-3"),
        app_commands.Choice(name="4-4-2 (Flat)", value="4-4-2"),
        app_commands.Choice(name="4-2-3-1 (Wide)", value="4-2-3-1"),
        app_commands.Choice(name="3-4-3 (Flat)", value="3-4-3"),
        app_commands.Choice(name="5-3-2 (Flat)", value="5-3-2"),
        app_commands.Choice(name="4-1-2-1-2 (Wide)", value="4-1-2-1-2 (Wide)")
    ])
    async def set_formation(self, interaction: discord.Interaction, new_formation: str):
        if new_formation == "4-3-3":
            positions = {"LW": None, "ST": None, "RW": None, "CM1": None, "CM2": None, "CM3": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None}
        elif new_formation == "4-4-2":
            positions = {"ST1": None, "ST2": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None}
        elif new_formation == "4-2-3-1":
            positions = {"ST": None, "CAM": None, "LM": None, "RM": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None}
        elif new_formation == "3-4-3":
            positions = {"LW": None, "ST": None, "RW": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None}
        elif new_formation == "5-3-2":
            positions = {"ST1": None, "ST2": None, "CM1": None, "CM2": None, "CM3": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None}
        elif new_formation == "4-1-2-1-2 (Wide)":
            positions = {"ST1": None, "ST2": None, "CAM": None, "LM": None, "RM": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None}
            
        new_squad = {
            "formation": new_formation,
            "players": positions
        }
        
        await database.update_squad(interaction.user.id, new_squad)
        await interaction.response.send_message(f"✅ Formation changed to **{new_formation}**! Your squad has been reset, please set your players again.")

    @squad_group.command(name="set", description="Set a player in your squad")
    async def set_player(self, interaction: discord.Interaction, position: str, inventory_id: int):
        squad = await database.get_squad(interaction.user.id)
        players = squad.get("players", {})
        valid_positions = list(players.keys())
        
        position = position.upper()
        
        if position not in valid_positions:
            await interaction.response.send_message(f"❌ Invalid position for {squad['formation']}! Valid positions: {', '.join(valid_positions)}", ephemeral=True)
            return
            
        player_row = await database.get_player_by_inv_id(interaction.user.id, inventory_id)
        if not player_row:
            await interaction.response.send_message(f"❌ You don't have a player with ID `{inventory_id}` in your inventory.", ephemeral=True)
            return
        # Prevent Duplicates
        new_name = player_row['player_name']
        for pos, active_p in players.items():
            if active_p and pos != position:
                if active_p['inv_id'] == inventory_id:
                    await interaction.response.send_message(f"❌ That exact card is already equipped at **{pos}**! Remove it first.", ephemeral=True)
                    return
                if active_p['name'] == new_name:
                    await interaction.response.send_message(f"❌ You already have **{new_name}** equipped at **{pos}**! You cannot have duplicate players.", ephemeral=True)
                    return
            
        squad["players"][position] = {
            "inv_id": inventory_id,
            "name": new_name,
            "ovr": player_row['ovr']
        }
        
        await database.update_squad(interaction.user.id, squad)
        await interaction.response.send_message(f"✅ Set **{new_name} ({player_row['ovr']})** as your starting {position}!")

    @app_commands.command(name="inventory", description="View all players in your club")
    async def inventory(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer(ephemeral=False)
        inventory = await database.get_inventory(interaction.user.id)
        
        if not inventory:
            await interaction.followup.send("Your club is empty! Open some packs with `/draft`.", ephemeral=True)
            return
            
        items_per_page = 15
        max_pages = max(1, (len(inventory) + items_per_page - 1) // items_per_page)
        
        if page < 1 or page > max_pages:
            await interaction.followup.send(f"❌ Invalid page! You only have {max_pages} pages.", ephemeral=True)
            return
            
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        lines = []
        for p in inventory[start_idx:end_idx]:
            lines.append(f"`ID: {p['id']}` | **{p['player_name']}** - {p['ovr']} OVR")
            
        embed = discord.Embed(title=f"🎒 {interaction.user.display_name}'s Club", description="\n".join(lines), color=discord.Color.green())
        embed.set_footer(text=f"Page {page}/{max_pages} | Total Players: {len(inventory)}")
            
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SquadCog(bot))
