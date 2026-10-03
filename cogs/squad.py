import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import json

FORMATION_MAP = {
    "3-1-4-2": {"ST1": None, "ST2": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CDM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-4-1-2": {"ST1": None, "ST2": None, "CAM": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-4-2-1": {"ST": None, "LF": None, "RF": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-4-3 Flat": {"LW": None, "ST": None, "RW": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-4-3 Diamond": {"LW": None, "ST": None, "RW": None, "CAM": None, "LM": None, "RM": None, "CDM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-5-1-1": {"ST": None, "CF": None, "LM": None, "CM1": None, "CDM": None, "CM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "3-5-2": {"ST1": None, "ST2": None, "CAM": None, "LM": None, "CDM1": None, "CDM2": None, "RM": None, "CB1": None, "CB2": None, "CB3": None, "GK": None},
    "4-1-2-1-2 Narrow": {"ST1": None, "ST2": None, "CAM": None, "CM1": None, "CM2": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-1-2-1-2 Wide": {"ST1": None, "ST2": None, "CAM": None, "LM": None, "RM": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-1-3-2": {"ST1": None, "ST2": None, "LM": None, "CM": None, "RM": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-1-4-1": {"ST": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-2-1-3": {"LW": None, "ST": None, "RW": None, "CAM": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-2-2-2": {"ST1": None, "ST2": None, "CAM1": None, "CAM2": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-2-3-1 Narrow": {"ST": None, "CAM1": None, "CAM2": None, "CAM3": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-2-3-1 Wide": {"ST": None, "CAM": None, "LM": None, "RM": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-2-4": {"LW": None, "ST1": None, "ST2": None, "RW": None, "CM1": None, "CM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-1-2": {"ST1": None, "ST2": None, "CAM": None, "CM1": None, "CM2": None, "CM3": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-2-1": {"ST": None, "LF": None, "RF": None, "CM1": None, "CM2": None, "CM3": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-3 Flat": {"LW": None, "ST": None, "RW": None, "CM1": None, "CM2": None, "CM3": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-3 Attack": {"LW": None, "ST": None, "RW": None, "CAM": None, "CM1": None, "CM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-3 Defend": {"LW": None, "ST": None, "RW": None, "CM": None, "CDM1": None, "CDM2": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-3 False 9": {"LW": None, "CF": None, "RW": None, "CM1": None, "CM2": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-3-3 Holding": {"LW": None, "ST": None, "RW": None, "CM1": None, "CM2": None, "CDM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-4-1-1 Flat": {"ST": None, "CF": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-4-1-1 Attack": {"ST": None, "CAM": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-4-2 Flat": {"ST1": None, "ST2": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-4-2 Holding": {"ST1": None, "ST2": None, "LM": None, "CDM1": None, "CDM2": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-5-1 Flat": {"ST": None, "LM": None, "CM1": None, "CM2": None, "CM3": None, "RM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "4-5-1 Attack": {"ST": None, "LM": None, "CAM1": None, "CAM2": None, "RM": None, "CM": None, "LB": None, "CB1": None, "CB2": None, "RB": None, "GK": None},
    "5-2-1-2": {"ST1": None, "ST2": None, "CAM": None, "CM1": None, "CM2": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None},
    "5-2-2-1": {"LW": None, "ST": None, "RW": None, "CM1": None, "CM2": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None},
    "5-3-2": {"ST1": None, "ST2": None, "CM1": None, "CM2": None, "CM3": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None},
    "5-4-1 Flat": {"ST": None, "LM": None, "CM1": None, "CM2": None, "RM": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None},
    "5-4-1 Defend": {"ST": None, "LM": None, "CDM1": None, "CDM2": None, "RM": None, "LWB": None, "CB1": None, "CB2": None, "CB3": None, "RWB": None, "GK": None}
}

import database
from auth import is_team_admin_or_owner
from maps import extract_pos, TACTICS, is_position_compatible, get_player_official_positions, check_player_position_eligibility
from cogs.market import get_price_limits, format_price_short

async def formation_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=f, value=f)
        for f in FORMATION_MAP.keys() if current.lower() in f.lower()
    ][:25]

async def squad_position_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    try:
        squad = await database.get_squad(interaction.user.id)
        players = squad.get("players", {})
        choices = []
        for pos in players.keys():
            if not current or current.lower() in pos.lower():
                choices.append(app_commands.Choice(name=pos, value=pos))
                if len(choices) >= 25:
                    break
        return choices
    except Exception as e:
        print("Error in squad_position_autocomplete:", e)
        return [
            app_commands.Choice(name=p, value=p)
            for p in ["GK", "LB", "CB1", "CB2", "RB", "CM1", "CM2", "CAM", "LW", "ST", "RW"]
            if not current or current.lower() in p.lower()
        ]

async def player_card_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    try:
        cards = await database.get_inventory_autocomplete(interaction.user.id, current)
        if not cards:
            return []
            
        choices = []
        for p in cards:
            try:
                pos = extract_pos(p)
            except Exception:
                pos = "ST"
            p_name = p.get('player_name', 'Player')
            ovr = p.get('ovr', 100)
            pid = p.get('id', 0)
            
            label = f"{p_name} ({pos}) — {ovr} OVR [ID:{pid}]"
            choices.append(app_commands.Choice(name=label[:100], value=str(pid)))
            if len(choices) >= 25:
                break
        return choices
    except Exception as e:
        print("Error in player_card_autocomplete:", e)
        return []

async def locked_card_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    try:
        cards = await database.get_inventory_autocomplete(interaction.user.id, current)
        choices = []
        for p in cards:
            if p.get('locked', 0):
                try:
                    pos = extract_pos(p)
                except Exception:
                    pos = "ST"
                label = f"🔒 {p.get('player_name', 'Player')} ({pos}) — {p.get('ovr', 100)} OVR [ID:{p['id']}]"
                choices.append(app_commands.Choice(name=label[:100], value=p['id']))
                if len(choices) >= 25:
                    break
        return choices
    except Exception:
        return []

async def player_stats_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = []
    try:
        # 1. First add current starting XI
        squad = await database.get_squad(interaction.user.id)
        for pos, p in squad.get("players", {}).items():
            if p and (not current or current.lower() in p.get("name", "").lower()):
                p_name = p.get("name")
                choices.append(app_commands.Choice(name=f"⚽ {p_name} ({pos} - {p.get('ovr', '')}) [Starting XI]"[:100], value=p_name))
        
        # 2. Add players from player_stats table
        stats = await database.get_user_player_stats(interaction.user.id)
        existing_names = {c.value.lower() for c in choices}
        for st in stats:
            p_name = st.get("player_name", "")
            if p_name.lower() not in existing_names and (not current or current.lower() in p_name.lower()):
                pos = st.get("position", "")
                goals = st.get("goals", 0)
                matches = st.get("matches_played", 0)
                choices.append(app_commands.Choice(name=f"📊 {p_name} ({pos}) — {goals}G ({matches}M)"[:100], value=p_name))
                if len(choices) >= 25:
                    break
    except Exception as e:
        print("Error in player_stats_autocomplete:", e)
    return choices[:25]


class InventoryPagination(discord.ui.View):
    def __init__(self, user_id, inventory, current_page, max_pages):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.inventory = inventory
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
        
        lines = []
        for p in self.inventory[start_idx:end_idx]:
            min_p, max_p = get_price_limits(p['ovr'])
            lock_icon = "🔒 " if p.get('locked', 0) else ""
            ovr_icon = "🔥" if p['ovr'] >= 120 else ("✨" if p['ovr'] >= 117 else "⚽")
            pos = p.get('position') or extract_pos(p)
            lines.append(f"`ID:{p['id']}` {lock_icon}{ovr_icon} **{p['player_name']}** `({pos})` — `{p['ovr']} OVR` | 🪙 {format_price_short(min_p)}–{format_price_short(max_p)}")
            
        embed = discord.Embed(title="🎒 Player Club", description="\n".join(lines), color=discord.Color.green())
        embed.set_footer(text=f"Page {self.current_page}/{self.max_pages} | Total Players: {len(self.inventory)}")
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your inventory!", ephemeral=True)
        self.current_page -= 1
        await self.update_page(interaction)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your inventory!", ephemeral=True)
        self.current_page += 1
        await self.update_page(interaction)


class SquadCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.sync_formations.start()

    def cog_unload(self):
        self.sync_formations.cancel()

    @tasks.loop(seconds=30)
    async def sync_formations(self):
        try:
            import json
            import lineup_generator
            p = await database.get_db()
            rows = await p.fetch("SELECT formation_name, positions_json FROM formation_layouts")
            layouts = {}
            for r in rows:
                try:
                    positions = r['positions_json']
                    if isinstance(positions, str):
                        positions = json.loads(positions)
                    layouts[r['formation_name']] = positions
                except Exception:
                    pass
            if layouts:
                lineup_generator.set_cached_layouts(layouts)
        except Exception as e:
            print("Failed to sync formations:", e)

    @sync_formations.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()


    squad_group = app_commands.Group(name="squad", description="Manage your starting XI")

    @squad_group.command(name="view", description="View your or another player's starting XI")
    @app_commands.describe(user="User whose squad you want to view (leave empty for yours)")
    async def view_squad(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user

        # Parallel fetch squad, privacy, and layouts
        if target.id != interaction.user.id and not await is_team_admin_or_owner(self.bot, interaction.user):
            is_priv, squad, layouts = await asyncio.gather(
                database.is_profile_private(target.id),
                database.get_squad(target.id),
                database.get_formation_layouts()
            )
            if is_priv:
                return await interaction.followup.send(f"🔒 **{target.display_name}** has set their profile to **Private**.", ephemeral=True)
        else:
            squad, layouts = await asyncio.gather(
                database.get_squad(target.id),
                database.get_formation_layouts()
            )

        formation = squad.get("formation", "4-3-3 Flat")
        players = squad.get("players", {})
        
        # Targeted fetch: only get the 11 equipped inventory cards instead of downloading full inventory
        inv_ids = [int(p['inv_id']) for p in players.values() if p and p.get('inv_id') is not None]
        
        inv_dict = {}
        if inv_ids:
            cached_inv = database._USER_INVENTORY_CACHE.get(target.id)
            if cached_inv:
                for row in cached_inv.get("data", []):
                    if row.get("id") in inv_ids:
                        inv_dict[row["id"]] = row.get("player_data")
            
            missing_ids = [iid for iid in inv_ids if iid not in inv_dict]
            if missing_ids:
                p = await database.get_db()
                rows = await p.fetch('SELECT id, player_data FROM inventory WHERE user_id = $1 AND id = ANY($2::bigint[])', target.id, missing_ids)
                for r in rows:
                    try:
                        pdata = json.loads(r['player_data']) if isinstance(r['player_data'], str) else r['player_data']
                        inv_dict[r['id']] = pdata
                    except Exception: pass

        total_ovr = 0
        count = 0
        
        for pos, player in players.items():
            if player:
                total_ovr += player['ovr']
                count += 1
                
        team_ovr = round(total_ovr / 11) if count > 0 else 0
        
        from lineup_generator import generate_lineup_image, set_cached_layouts
        import io
        import hashlib
        
        try:
            cache_key = hashlib.md5(f"{target.id}_{formation}_{json.dumps(players, sort_keys=True)}_{squad.get('theme', 'default')}".encode()).hexdigest()
            
            if not hasattr(self, '_render_cache'):
                self._render_cache = {}

            png_bytes = self._render_cache.get(cache_key)
            if not png_bytes:
                if layouts:
                    set_cached_layouts(layouts)
                
                # Fetch all-time stats for the players to display on the 3D cards
                p_stats_rows = await database.get_user_player_stats(target.id)
                stats_map = {row['player_name'].lower(): row for row in p_stats_rows}
                
                # Attach stats to inv_dict for rendering
                for inv_id, pdata in inv_dict.items():
                    name_lower = pdata.get("cardName", pdata.get("lastName", "")).lower()
                    if name_lower in stats_map:
                        st = stats_map[name_lower]
                        pdata["_lifetime_goals"] = st.get("goals", 0)
                        pdata["_lifetime_assists"] = st.get("assists", 0)
                        pdata["_lifetime_matches"] = st.get("matches_played", 0)

                def _render():
                    img = generate_lineup_image(squad, inv_dict)
                    buf = io.BytesIO()
                    img.save(buf, format='PNG', optimize=False)
                    return buf.getvalue()
                    
                png_bytes = await asyncio.to_thread(_render)
                if len(self._render_cache) < 100:
                    self._render_cache[cache_key] = png_bytes

            file = discord.File(fp=io.BytesIO(png_bytes), filename='lineup.png')
            
            tactic_name = squad.get("tactic", "Tiki-Taka")
            t_data = TACTICS.get(tactic_name, TACTICS["Tiki-Taka"])
            is_synergy = any(f.lower() in formation.lower() for f in t_data["best_formations"])
            tactic_badge = f"{t_data['emoji']} **{tactic_name}**" + (" `[🌟 SYNERGY BOOST!]`" if is_synergy else "")
            
            embed = discord.Embed(
                title=f"🛡️ {target.display_name}'s Squad", 
                description=f"**Formation:** `{formation}` | **Team OVR:** `{team_ovr}`\n**Playstyle Tactic:** {tactic_badge}", 
                color=discord.Color.green() if is_synergy else discord.Color.blue()
            )
            embed.set_image(url="attachment://lineup.png")
            
            if count < 11:
                footer_msg = "Your squad is incomplete! Use /squad set to add players." if target.id == interaction.user.id else f"{target.display_name}'s squad is incomplete ({count}/11 players)."
                embed.set_footer(text=footer_msg)
            else:
                embed.set_footer(text=f"Tactical Focus: {t_data['boost_focus']} • Use /squad tactic to change")
                
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to generate lineup image: {e}")

    @squad_group.command(name="formation", description="Change your team's formation (Warning: Resets your squad)")
    @app_commands.autocomplete(new_formation=formation_autocomplete)
    async def set_formation(self, interaction: discord.Interaction, new_formation: str):
        await interaction.response.defer()
        if new_formation not in FORMATION_MAP:
            return await interaction.followup.send("❌ Invalid formation selected. Please use the autocomplete choices.", ephemeral=True)
            
        squad = await database.get_squad(interaction.user.id)
        positions = FORMATION_MAP[new_formation].copy()
        
        old_players = squad.get("players", {})
        if isinstance(old_players, list):
            old_players = {}
            
        new_players = {}
        kept_count = 0
        
        # Try to map old players to new slots
        for new_pos in positions:
            if new_pos in old_players and old_players[new_pos]:
                new_players[new_pos] = old_players[new_pos]
                old_players[new_pos] = None
                kept_count += 1
            else:
                new_players[new_pos] = None
                
        # For remaining old players, try to find an empty slot that matches their position loosely
        for old_pos, p_data in old_players.items():
            if p_data:
                for new_pos in positions:
                    if not new_players[new_pos]:
                        # Basic position match (e.g. CB1 and CB2)
                        if old_pos[:2] == new_pos[:2]:
                            new_players[new_pos] = p_data
                            kept_count += 1
                            break
            
        new_squad = {
            "formation": new_formation,
            "tactic": squad.get("tactic", "Tiki-Taka"),
            "theme": squad.get("theme", "default"),
            "players": new_players
        }
        
        await database.update_squad(interaction.user.id, new_squad)
        t_data = TACTICS.get(new_squad["tactic"], TACTICS["Tiki-Taka"])
        is_syn = any(f.lower() in new_formation.lower() for f in t_data["best_formations"])
        syn_msg = f"\n🌟 **Tactical Chemistry Synergy is ACTIVE with your {t_data['emoji']} {t_data['name']} tactic!**" if is_syn else f"\n💡 *Tip: Best suitable tactic for {new_formation}: Check `/squad tactic`.*"
        
        await interaction.followup.send(f"✅ Formation changed to **{new_formation}**! Kept **{kept_count}** previous players in their positions.{syn_msg}")

    @squad_group.command(name="tactic", description="Select or view your team's tactical playstyle & formation synergy")
    @app_commands.describe(tactic="Select playstyle tactic for your club")
    @app_commands.choices(tactic=[
        app_commands.Choice(name="Tiki-Taka (Best: 4-3-3 Holding, 4-1-4-1)", value="Tiki-Taka"),
        app_commands.Choice(name="Gegenpressing (Best: 4-3-3 Attack, 4-2-3-1)", value="Gegenpressing"),
        app_commands.Choice(name="Wing Play (Best: 4-4-2 Flat, 4-3-3 Flat)", value="Wing Play"),
        app_commands.Choice(name="Counter-Attack (Best: 5-2-1-2, 4-4-2 Holding)", value="Counter-Attack"),
        app_commands.Choice(name="Kick and Rush (Best: 4-4-2 Flat, 5-4-1)", value="Kick and Rush"),
        app_commands.Choice(name="Park the Bus (Best: 5-4-1, 4-5-1)", value="Park the Bus"),
        app_commands.Choice(name="Vertical Tiki-Taka (Best: 4-3-2-1, 4-1-2-1-2 Narrow)", value="Vertical Tiki-Taka"),
    ])
    async def set_tactic(self, interaction: discord.Interaction, tactic: str = None):
        await interaction.response.defer()
        squad = await database.get_squad(interaction.user.id)
        current_tactic = squad.get("tactic", "Tiki-Taka")
        formation = squad.get("formation", "4-3-3 Flat")
        
        if not tactic:
            t_data = TACTICS.get(current_tactic, TACTICS["Tiki-Taka"])
            is_synergy = any(f.lower() in formation.lower() for f in t_data["best_formations"])
            synergy_str = "✅ **Tactical Synergy Active! (+10% In-Match Gameplay Boost)**" if is_synergy else f"⚠️ *No Synergy with current formation ({formation}). Best formations:* `{', '.join(t_data['best_formations'])}`"
            embed = discord.Embed(
                title=f"{t_data['emoji']} Active Club Tactic: {t_data['name']}",
                description=f"{t_data['description']}\n\n**Specialty Focus:** {t_data['boost_focus']}\n\n{synergy_str}",
                color=discord.Color.green() if is_synergy else discord.Color.gold()
            )
            embed.set_footer(text="Use /squad tactic [tactic] to change your playstyle!")
            return await interaction.followup.send(embed=embed)

        if tactic not in TACTICS:
            return await interaction.followup.send("❌ Invalid tactic selected.", ephemeral=True)

        squad["tactic"] = tactic
        await database.update_squad(interaction.user.id, squad)
        t_data = TACTICS[tactic]
        is_synergy = any(f.lower() in formation.lower() for f in t_data["best_formations"])
        synergy_str = "🌟 **Tactical Chemistry Synergy Activated!**" if is_synergy else f"ℹ️ *Tip: Switch formation to `{', '.join(t_data['best_formations'])}` for maximum synergy boost.*"
        
        await interaction.followup.send(f"✅ Set club tactic to **{t_data['emoji']} {tactic}**!\n{synergy_str}")

    @squad_group.command(name="set", description="Set a player card in your starting 11 squad")
    @app_commands.describe(position="Position slot in your formation", player="Select player card from your inventory (or type card name/ID)")
    @app_commands.autocomplete(position=squad_position_autocomplete, player=player_card_autocomplete)
    async def set_player(self, interaction: discord.Interaction, position: str, player: str):
        await interaction.response.defer()
        import re
        squad = await database.get_squad(interaction.user.id)
        players = squad.get("players", {})
        valid_positions = list(players.keys())
        
        # Strip parentheses like "(Empty)" or "(Player 120)"
        pos_clean = re.sub(r'\(.*?\)', '', position).strip().upper()
        target_pos = None
        if pos_clean in valid_positions:
            target_pos = pos_clean
        else:
            matching_slots = [p for p in valid_positions if p == pos_clean or p.startswith(pos_clean) or pos_clean in p]
            if matching_slots:
                empty_slots = [p for p in matching_slots if not players.get(p)]
                target_pos = empty_slots[0] if empty_slots else matching_slots[0]
            else:
                return await interaction.followup.send(f"❌ Invalid position for **{squad.get('formation', 'your squad')}**!\nValid positions: `{', '.join(valid_positions)}`", ephemeral=True)
                
        user_inv = await database.get_inventory(interaction.user.id)
        if not user_inv:
            return await interaction.followup.send("❌ Your club inventory is empty! Open some packs with `/draft` first.", ephemeral=True)

        player_row = None
        raw_query = player.strip()

        # 1. Try resolving with [ID: 123] pattern
        id_match = re.search(r'\[ID:\s*(\d+)\]', raw_query, re.IGNORECASE)
        if id_match:
            target_id = int(id_match.group(1))
            for p in user_inv:
                if p['id'] == target_id:
                    player_row = p
                    break

        # 2. Try resolving as numerical inventory ID
        if not player_row and raw_query.isdigit():
            inv_id = int(raw_query)
            for p in user_inv:
                if p['id'] == inv_id:
                    player_row = p
                    break

        # 3. Try flexible name/OVR search
        if not player_row:
            tokens = raw_query.lower().split()
            target_ovr = None
            name_tokens = []
            for t in tokens:
                if t.isdigit() and len(t) in (2, 3):
                    target_ovr = int(t)
                else:
                    name_tokens.append(t)

            candidates = []
            for p in user_inv:
                p_name = p.get('player_name', '').lower()
                if all(nt in p_name for nt in name_tokens):
                    candidates.append(p)

            if candidates:
                if target_ovr:
                    exact_ovr = [p for p in candidates if p.get('ovr') == target_ovr]
                    if exact_ovr:
                        player_row = exact_ovr[0]
                if not player_row:
                    candidates.sort(key=lambda x: x.get('ovr', 0), reverse=True)
                    player_row = candidates[0]
                
        if not player_row:
            return await interaction.followup.send(f"❌ Could not find a card matching '**{player}**' in your inventory.\nPlease check your `/club` or select from the autocomplete menu.", ephemeral=True)
            
        inventory_id = player_row['id']
        new_name = player_row['player_name']
        new_ovr = player_row['ovr']
        
        # Check position compatibility against official card positions
        is_eligible, is_primary = check_player_position_eligibility(player_row, target_pos)
        main_p, alt_ps = get_player_official_positions(player_row)
        clean_target = ''.join([c for c in str(target_pos) if not c.isdigit()]).strip().upper()
        
        pos_warning = ""
        if not is_eligible:
            alt_str = ", ".join(alt_ps) if alt_ps else "None"
            pos_warning = (
                f"\n⚠️ **Out of Position!** **{new_name}**'s main position is `{main_p}` "
                f"(Alts: `{alt_str}`). They will suffer an OVR and stat penalty at `{clean_target}`."
            )

        # If card was equipped in another slot, automatically unequip from that slot (move/swap)
        repositioned_from = None
        for pos, active_p in list(players.items()):
            if active_p and pos != target_pos:
                if active_p.get('inv_id') == inventory_id:
                    players[pos] = None
                    repositioned_from = pos
                elif active_p.get('name') == new_name:
                    return await interaction.followup.send(f"❌ You already have another **{new_name}** equipped at **{pos}**! You cannot have duplicate players.", ephemeral=True)
            
        squad["players"][target_pos] = {
            "inv_id": inventory_id,
            "name": new_name,
            "ovr": new_ovr
        }
        await database.update_squad(interaction.user.id, squad)
        
        alt_note = f" *(Official Alt Position: `{main_p}` ➔ `{clean_target}` • 100% OVR)*" if not is_primary and is_eligible else ""
        reposition_note = f" (Moved from **{repositioned_from}**)" if repositioned_from else ""
        await interaction.followup.send(f"✅ Set **{new_name} ({new_ovr} OVR)** as your starting **{target_pos}**!{reposition_note}{alt_note}{pos_warning}")

    @squad_group.command(name="remove", description="Remove a player from a specific squad position")
    @app_commands.describe(position="Position slot to empty")
    @app_commands.autocomplete(position=squad_position_autocomplete)
    async def remove_player(self, interaction: discord.Interaction, position: str):
        await interaction.response.defer()
        squad = await database.get_squad(interaction.user.id)
        players = squad.get("players", {})
        pos_norm = position.upper().strip()
        
        if pos_norm not in players:
            return await interaction.followup.send(f"❌ Invalid position `{position}` for your formation.", ephemeral=True)
            
        prev = players.get(pos_norm)
        if not prev:
            return await interaction.followup.send(f"ℹ️ Position **{pos_norm}** is already empty.", ephemeral=True)
            
        squad["players"][pos_norm] = None
        await database.update_squad(interaction.user.id, squad)
        await interaction.followup.send(f"🗑️ Removed **{prev['name']}** from **{pos_norm}**.")

    @squad_group.command(name="autobuild", description="Auto-fill your squad with your highest OVR players")
    async def autobuild(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        squad = await database.get_squad(interaction.user.id)
        positions = list(squad.get("players", {}).keys())
        inventory = await database.get_inventory(interaction.user.id)
        
        if not inventory:
            await interaction.followup.send("❌ Your club is empty! Open some packs with `/draft` first.", ephemeral=True)
            return
        
        # Parse each inventory card's official Official Database main and alternate positions
        enriched = []
        for p in inventory:
            main_pos, alts = get_player_official_positions(p)
            enriched.append({
                **p,
                'main_pos': main_pos,
                'alt_positions': alts
            })
        
        # Sort by OVR descending so highest OVR gets prioritized
        enriched.sort(key=lambda x: x.get('ovr', 0), reverse=True)
        
        new_players = {slot: None for slot in positions}
        used_ids = set()
        used_names = set()
        
        # PASS 1 (HIGH PRIORITY): Fill slots with players whose PRIMARY / MAIN position matches!
        for slot in positions:
            clean_slot = ''.join([c for c in str(slot) if not c.isdigit()]).strip().upper()
            for p in enriched:
                if p['id'] in used_ids or p['player_name'] in used_names:
                    continue
                if p['main_pos'] == clean_slot:
                    new_players[slot] = {
                        "inv_id": p['id'],
                        "name": p['player_name'],
                        "ovr": p['ovr'],
                        "is_alt": False
                    }
                    used_ids.add(p['id'])
                    used_names.add(p['player_name'])
                    break
                    
        # PASS 2 (SECONDARY): Fill remaining empty slots with players who officially have this slot in potentialPositions!
        for slot in positions:
            if new_players[slot] is not None:
                continue
            clean_slot = ''.join([c for c in str(slot) if not c.isdigit()]).strip().upper()
            for p in enriched:
                if p['id'] in used_ids or p['player_name'] in used_names:
                    continue
                if clean_slot in p['alt_positions']:
                    new_players[slot] = {
                        "inv_id": p['id'],
                        "name": p['player_name'],
                        "ovr": p['ovr'],
                        "is_alt": True
                    }
                    used_ids.add(p['id'])
                    used_names.add(p['player_name'])
                    break
        
        # Clean dict for database
        saved_players = {
            slot: {"inv_id": p["inv_id"], "name": p["name"], "ovr": p["ovr"]} if p else None
            for slot, p in new_players.items()
        }
        squad["players"] = saved_players
        await database.update_squad(interaction.user.id, squad)
        
        filled = sum(1 for v in new_players.values() if v)
        total_ovr = sum(v['ovr'] for v in new_players.values() if v)
        team_ovr = round(total_ovr / 11) if filled > 0 else 0
        
        lines = []
        for pos, p in new_players.items():
            if p:
                alt_tag = " `(Alt Pos)`" if p.get('is_alt') else ""
                lines.append(f"**{pos}** → {p['name']} ({p['ovr']}){alt_tag}")
            else:
                lines.append(f"**{pos}** → ❌ No compatible player")
        
        embed = discord.Embed(
            title="⚡ Squad Auto-Built (Main Positions Prioritized)",
            description="\n".join(lines),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Team OVR: {team_ovr} | {filled}/11 Positions Filled • Official card positions applied")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="inventory", description="View your or another user's player club")
    @app_commands.describe(user="User whose inventory you want to view (leave empty for yours)")
    async def inventory(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        
        # Parallel fetch Privacy Check and Lightweight Inventory
        if target.id != interaction.user.id and not await is_team_admin_or_owner(self.bot, interaction.user):
            is_priv, inventory = await asyncio.gather(
                database.is_profile_private(target.id),
                database.get_inventory_light(target.id)
            )
            if is_priv:
                return await interaction.followup.send(f"🔒 **{target.display_name}** has set their club/inventory to **Private**.", ephemeral=True)
        else:
            inventory = await database.get_inventory_light(target.id)
        
        if not inventory:
            msg = "Your club is empty! Open some packs with `/draft`." if target == interaction.user else f"**{target.display_name}**'s club is empty."
            await interaction.followup.send(msg, ephemeral=True)
            return
            
        items_per_page = 15
        max_pages = max(1, (len(inventory) + items_per_page - 1) // items_per_page)
        
        start_idx = 0
        end_idx = items_per_page
        
        lines = []
        for p in inventory[start_idx:end_idx]:
            ovr = int(p.get('ovr') or 100)
            min_p, max_p = get_price_limits(ovr)
            lock_icon = "🔒 " if p.get('locked') else ""
            ovr_icon = "🔥" if ovr >= 120 else ("✨" if ovr >= 117 else "⚽")
            pos = p.get('position') or extract_pos(p) or "ST"
            p_name = p.get('player_name') or 'Player'
            lines.append(f"`ID:{p.get('id', '??')}` {lock_icon}{ovr_icon} **{p_name}** `({pos})` — `{ovr} OVR` | 🪙 {format_price_short(min_p)}–{format_price_short(max_p)}")
            
        embed = discord.Embed(title=f"🎒 {target.display_name}'s Club", description="\n".join(lines), color=discord.Color.green())
        embed.set_footer(text=f"Page 1/{max_pages} | Total Players: {len(inventory)}")
        
        view = InventoryPagination(target.id, inventory, 1, max_pages)
        await interaction.followup.send(embed=embed, view=view)


    @squad_group.command(name="theme", description="Equip a pitch theme you have unlocked")
    async def set_theme(self, interaction: discord.Interaction, theme_id: str):
        await interaction.response.defer()
        user_id = interaction.user.id
        squad = await database.get_squad(user_id)
        
        unlocked = squad.get("unlocked_themes", ["default"])
        theme_id = theme_id.lower()
        
        if theme_id not in unlocked:
            return await interaction.followup.send(f"❌ You haven't unlocked the `{theme_id}` theme yet! Buy it in `/store themes`.")
            
        squad["theme"] = theme_id
        await database.update_squad(user_id, squad)
        await interaction.followup.send(f"✅ Successfully equipped the **{theme_id}** pitch theme! Check it out in `/squad view`.")


    @squad_group.command(name="lock", description="Lock a player in your inventory (protects from exchange/SBC/quicksell)")
    @app_commands.describe(inventory_id="Select player card to lock")
    @app_commands.autocomplete(inventory_id=player_card_autocomplete)
    async def lock_player(self, interaction: discord.Interaction, inventory_id: int):
        await interaction.response.defer(ephemeral=True)
        player = await database.get_player_by_inv_id(interaction.user.id, inventory_id)
        if not player:
            return await interaction.followup.send("❌ Player not found in your inventory.", ephemeral=True)
        await database.lock_player(interaction.user.id, inventory_id)
        pos = extract_pos(player)
        await interaction.followup.send(f"🔒 **{player['player_name']} ({pos}) ({player['ovr']})** is now locked! They cannot be quick-sold, traded, or used in exchanges/SBCs.", ephemeral=True)

    @squad_group.command(name="unlock", description="Unlock a locked player in your inventory")
    @app_commands.describe(inventory_id="Select locked player card to unlock")
    @app_commands.autocomplete(inventory_id=locked_card_autocomplete)
    async def unlock_player(self, interaction: discord.Interaction, inventory_id: int):
        await interaction.response.defer(ephemeral=True)
        player = await database.get_player_by_inv_id(interaction.user.id, inventory_id)
        if not player:
            return await interaction.followup.send("❌ Player not found in your inventory.", ephemeral=True)
        await database.unlock_player(interaction.user.id, inventory_id)
        pos = extract_pos(player)
        await interaction.followup.send(f"🔓 **{player['player_name']} ({pos}) ({player['ovr']})** is now unlocked.", ephemeral=True)

    @app_commands.command(name="lock", description="Lock a player card (protects from exchange/SBC/quicksell)")
    @app_commands.describe(inventory_id="Select player card to lock")
    @app_commands.autocomplete(inventory_id=player_card_autocomplete)
    async def lock_alias(self, interaction: discord.Interaction, inventory_id: int):
        await self.lock_player(interaction, inventory_id)

    @app_commands.command(name="squad_set", description="Set a player card in your starting 11 squad")
    @app_commands.describe(position="Position slot in your formation", player="Select player card from your inventory (or type card name/ID)")
    @app_commands.autocomplete(position=squad_position_autocomplete, player=player_card_autocomplete)
    async def top_squad_set(self, interaction: discord.Interaction, position: str, player: str):
        await self.set_player(interaction, position, player)

    @app_commands.command(name="squad_view", description="View your or another user's current squad lineup in 3D")
    @app_commands.describe(user="User whose squad you want to view (leave empty for yours)")
    async def top_squad_view(self, interaction: discord.Interaction, user: discord.Member = None):
        await self.view_squad(interaction, user)

    @app_commands.command(name="club_stats", description="View your club's personal stats leaders (Top Scorer, Assists, Ratings, Clean Sheets, Cards)")
    @app_commands.describe(user="User whose club stats you want to view (leave empty for yours)")
    async def club_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user

        if target.id != interaction.user.id and not await is_team_admin_or_owner(self.bot, interaction.user):
            if await database.is_profile_private(target.id):
                return await interaction.followup.send(f"🔒 **{target.display_name}** has set their club profile to **Private**.", ephemeral=True)

        leaders = await database.get_club_leader_stats(target.id)
        if not leaders or leaders.get("tracked_count", 0) == 0:
            embed = discord.Embed(
                title=f"📊 {target.display_name}'s Club Performance",
                description=(
                    "❌ **No match statistics recorded yet!**\n\n"
                    "Play Division Rivals with `/play @user` or Draft Battles with `/draft_challenge` "
                    "to start tracking your squad's goals, assists, clean sheets, and ratings!"
                ),
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            return await interaction.followup.send(embed=embed)

        ts = leaders.get("top_scorer")
        ta = leaders.get("top_assists")
        br = leaders.get("best_rating")
        cs = leaders.get("top_clean_sheets")
        my = leaders.get("most_yellows")
        mr = leaders.get("most_reds")

        embed = discord.Embed(
            title=f"👑 {target.display_name}'s Club Stats & Records",
            description=f"Performance summary for **{leaders.get('tracked_count', 0)}** tracked players across **{leaders.get('total_matches', 0)}** matches.",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # 1. Top Goalscorer (Golden Boot)
        if ts:
            gpg = round(ts['goals'] / max(1, ts['matches_played']), 2)
            embed.add_field(
                name="⚽ Golden Boot (Top Scorer)",
                value=f"👑 **{ts['player_name']}** `({ts['position']})`\n🥅 **{ts['goals']} Goals** in {ts['matches_played']} matches (`{gpg}` GPG)",
                inline=False
            )
        else:
            embed.add_field(name="⚽ Golden Boot (Top Scorer)", value="*No goals scored yet*", inline=False)

        # 2. Playmaker (Most Assists)
        if ta:
            apg = round(ta['assists'] / max(1, ta['matches_played']), 2)
            embed.add_field(
                name="🎯 Master Playmaker (Most Assists)",
                value=f"🪄 **{ta['player_name']}** `({ta['position']})`\n🅰️ **{ta['assists']} Assists** in {ta['matches_played']} matches (`{apg}` APG)",
                inline=False
            )
        else:
            embed.add_field(name="🎯 Master Playmaker", value="*No assists recorded yet*", inline=False)

        # 3. Best Average Match Rating
        if br:
            embed.add_field(
                name="⭐ Highest Match Rating",
                value=f"🌟 **{br['player_name']}** `({br['position']})`\n📊 **{br['avg_rating']} / 10.0** Average Rating ({br['motm_count']}x MOTM)",
                inline=True
            )

        # 4. Clean Sheet Leader (Defenders & GK only)
        if cs:
            cs_pct = round((cs['clean_sheets'] / max(1, cs['matches_played'])) * 100)
            embed.add_field(
                name="🧤 Wall of the Club (Clean Sheets)",
                value=f"🧱 **{cs['player_name']}** `({cs['position']})`\n🛡️ **{cs['clean_sheets']} Clean Sheets** (`{cs_pct}%` CS rate)",
                inline=True
            )
        else:
            embed.add_field(
                name="🧤 Wall of the Club (Clean Sheets)",
                value="*No clean sheets yet (DF/GK)*",
                inline=True
            )

        # 5. Discipline & Cards
        discipline_parts = []
        if my and my['yellow_cards'] > 0:
            discipline_parts.append(f"🟨 **{my['player_name']}**: `{my['yellow_cards']}` Yellows")
        if mr and mr['red_cards'] > 0:
            discipline_parts.append(f"🟥 **{mr['player_name']}**: `{mr['red_cards']}` Reds")
        
        disc_text = " • ".join(discipline_parts) if discipline_parts else "😇 Clean record! No disciplinary cards."
        embed.add_field(name="🟨🟥 Disciplinary Record", value=disc_text, inline=False)

        # 6. Overall Club Totals
        embed.add_field(
            name="📊 Club Overview",
            value=f"🏟️ **Matches:** `{leaders.get('total_matches', 0)}` | ⚽ **Total Goals:** `{leaders.get('total_goals', 0)}` | 🎯 **Total Assists:** `{leaders.get('total_assists', 0)}`",
            inline=False
        )

        embed.set_footer(text="Use /player_stats [player] to inspect individual player cards")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="View club performance records (Top Scorer, Assists, Ratings, Clean Sheets)")
    @app_commands.describe(user="User whose club stats you want to view (leave empty for yours)")
    async def stats_alias(self, interaction: discord.Interaction, user: discord.Member = None):
        await self.club_stats.callback(self, interaction, user)

    @app_commands.command(name="player_stats", description="View lifetime match statistics of a specific player in your squad or club")
    @app_commands.describe(player="Select or search player name", user="Target user (leave empty for yourself)")
    @app_commands.autocomplete(player=player_stats_autocomplete)
    async def player_stats(self, interaction: discord.Interaction, player: str, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user

        if target.id != interaction.user.id and not await is_team_admin_or_owner(self.bot, interaction.user):
            if await database.is_profile_private(target.id):
                return await interaction.followup.send(f"🔒 **{target.display_name}** has set their club profile to **Private**.", ephemeral=True)

        stats_rows = await database.get_user_player_stats(target.id, player)
        
        if not stats_rows:
            squad = await database.get_squad(target.id)
            found_card = None
            for pos, p in squad.get("players", {}).items():
                if p and player.lower() in p.get("name", "").lower():
                    found_card = {"player_name": p["name"], "position": pos, "ovr": p.get("ovr", 100), "matches_played": 0, "goals": 0, "assists": 0, "clean_sheets": 0, "yellow_cards": 0, "red_cards": 0, "avg_rating": "N/A", "motm_count": 0}
                    break
            
            if not found_card:
                return await interaction.followup.send(f"❌ No match statistics found for **{player}** in {target.display_name}'s club.\nPlay matches with `/play` or `/draft_challenge` to track stats!", ephemeral=True)
            stats = found_card
        else:
            stats = stats_rows[0]

        p_name = stats.get("player_name", player)
        pos = stats.get("position", "N/A")
        ovr = stats.get("ovr", 100)
        matches = stats.get("matches_played", 0)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        clean_sheets = stats.get("clean_sheets", 0)
        yellows = stats.get("yellow_cards", 0)
        reds = stats.get("red_cards", 0)
        avg_rating = stats.get("avg_rating", "N/A")
        motm = stats.get("motm_count", 0)

        gpg = round(goals / max(1, matches), 2) if matches > 0 else 0
        apg = round(assists / max(1, matches), 2) if matches > 0 else 0

        is_def_gk = any(k in str(pos).upper() for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
        cs_line = f"🧤 **Clean Sheets:** `{clean_sheets}`" + (f" (`{round((clean_sheets/max(1, matches))*100)}%` CS Rate)" if (is_def_gk and matches > 0) else " *(Only tracked for GK & Defenders)*")

        embed = discord.Embed(
            title=f"📋 {p_name} — Lifetime Player Card",
            description=f"🏃 **Position:** `{pos}` | 🌟 **Rating:** `{ovr} OVR`\n🛡️ **Club:** {target.display_name}'s XI",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"{target.display_name}'s Player Stats", icon_url=target.display_avatar.url)

        embed.add_field(name="🏟️ Appearances", value=f"**{matches}** Matches Played", inline=True)
        embed.add_field(name="⭐ Match Rating", value=f"**{avg_rating} / 10.0**\n🎖️ `{motm}x` MOTM", inline=True)
        embed.add_field(name="⚽ Goals Scored", value=f"**{goals}** Goals\n`{gpg}` Goals / Match", inline=True)
        embed.add_field(name="🎯 Assists", value=f"**{assists}** Assists\n`{apg}` Assists / Match", inline=True)
        embed.add_field(name="🧤 Defensive Record", value=cs_line, inline=False)
        embed.add_field(name="🟨 Discipline", value=f"🟨 **{yellows}** Yellow Cards | 🟥 **{reds}** Red Cards", inline=False)

        embed.set_footer(text="DestiFC Player Performance Tracker • Stats update after every match")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SquadCog(bot))

