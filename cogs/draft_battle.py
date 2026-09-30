import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio
import io
import time
from renderz_api import query_players_by_program
from lineup_generator import generate_lineup_image, set_cached_layouts

DRAFT_FORMATIONS = [
    "4-3-3 Attack",
    "4-1-2-1-2 Narrow",
    "4-4-2 Flat",
    "3-4-3 Flat",
    "5-3-2"
]

FORMATION_SLOTS = {
    "4-3-3 Attack": ["GK", "LB", "CB1", "CB2", "RB", "CM1", "CAM", "CM2", "LW", "ST", "RW"],
    "4-1-2-1-2 Narrow": ["GK", "LB", "CB1", "CB2", "RB", "CDM", "CM1", "CM2", "CAM", "ST1", "ST2"],
    "4-4-2 Flat": ["GK", "LB", "CB1", "CB2", "RB", "LM", "CM1", "CM2", "RM", "ST1", "ST2"],
    "3-4-3 Flat": ["GK", "CB1", "CB2", "CB3", "LM", "CM1", "CM2", "RM", "LW", "ST", "RW"],
    "5-3-2": ["GK", "LWB", "CB1", "CB2", "CB3", "RWB", "CM1", "CM2", "CM3", "ST1", "ST2"]
}

# Cache for 110+ OVR player pool
DRAFT_POOL_CACHE = []
LAST_CACHE_TIME = 0

def get_draft_pool():
    global DRAFT_POOL_CACHE, LAST_CACHE_TIME
    now = time.time()
    if not DRAFT_POOL_CACHE or now - LAST_CACHE_TIME > 1800:
        try:
            pool = []
            for r in [122, 121, 120, 118, 116, 115, 112, 110, 108]:
                batch = query_players_by_program("", min_rating=r, max_rating=r, size=40)
                if batch:
                    pool.extend(batch)
            if pool:
                DRAFT_POOL_CACHE = pool
                LAST_CACHE_TIME = now
        except Exception:
            pass
    return DRAFT_POOL_CACHE

def sample_position_cards(slot: str, count: int = 5):
    pool = get_draft_pool()
    base_pos = slot.rstrip("0123456789").upper()
    compat = {
        "GK": ["GK"],
        "CB": ["CB"],
        "LB": ["LB", "LWB"],
        "RB": ["RB", "RWB"],
        "LWB": ["LWB", "LB"],
        "RWB": ["RWB", "RB"],
        "LM": ["LM", "LW"],
        "RM": ["RM", "RW"],
        "LW": ["LW", "LM", "LF"],
        "RW": ["RW", "RM", "RF"],
        "LF": ["LF", "LW", "ST"],
        "RF": ["RF", "RW", "ST"],
        "CM": ["CM", "CAM", "CDM"],
        "CAM": ["CAM", "CM", "CF"],
        "CDM": ["CDM", "CM"],
        "ST": ["ST", "CF"],
        "CF": ["CF", "ST", "CAM"],
    }.get(base_pos, [base_pos])

    matching = [p for p in pool if str(p.get("position", "")).upper() in compat]
    
    if not matching:
        # Fallback card matching the exact required position
        matching = [
            {"rating": 120, "cardName": f"Superstar {base_pos}", "position": base_pos, "club": {"name": "FC"}, "nation": {"name": "World"}}
            for _ in range(count)
        ]

    num_picks = min(count, len(matching))
    return random.sample(matching, num_picks)

def calculate_draft_chemistry(players: dict):
    """Calculate Chemistry points and OVR boost like FC FUT Draft."""
    clubs = {}
    nations = {}
    total_ovr = 0
    count = 0

    for pos, p in players.items():
        if not p:
            continue
        total_ovr += p.get("rating", p.get("ovr", 110))
        count += 1
        club = p.get("club", {}).get("name") or "None"
        nation = p.get("nation", {}).get("name") or "None"
        clubs[club] = clubs.get(club, 0) + 1
        nations[nation] = nations.get(nation, 0) + 1

    avg_ovr = total_ovr / max(1, count)
    chem_score = 0
    for c, cnt in clubs.items():
        if cnt >= 2 and c != "None": chem_score += (cnt * 2)
    for n, cnt in nations.items():
        if cnt >= 2 and n != "None": chem_score += (cnt * 2)

    chem_boost = min(8, chem_score // 3)
    final_ovr = round(avg_ovr + chem_boost)
    return round(avg_ovr), chem_boost, final_ovr


# ================= UI Views =================

class DraftPickDropdown(discord.ui.Select):
    def __init__(self, slot: str, choices: list):
        self.slot = slot
        self.choices = choices
        options = []
        for i, p in enumerate(choices):
            name = p.get("cardName") or p.get("lastName") or "Player"
            ovr = p.get("rating", 110)
            pos = p.get("position", slot)
            club = p.get("club", {}).get("name", "Club")
            nation = p.get("nation", {}).get("name", "Nation")
            options.append(discord.SelectOption(
                label=f"{ovr} {name} ({pos})",
                description=f"{club} | {nation}",
                value=str(i),
                emoji="⭐" if ovr >= 120 else "⚽"
            ))
        super().__init__(placeholder=f"Pick your {slot}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_pick(interaction, self.slot, self.choices[int(self.values[0])])


class SinglePlayerDraftView(discord.ui.View):
    def __init__(self, user: discord.User, formation: str, on_complete_callback):
        super().__init__(timeout=300)
        self.user = user
        self.formation = formation
        self.slots = FORMATION_SLOTS[formation]
        self.current_idx = 0
        self.picked_players = {}
        self.on_complete_callback = on_complete_callback
        self.prompt_next_slot()

    def prompt_next_slot(self):
        self.clear_items()
        if self.current_idx >= len(self.slots):
            return
        slot = self.slots[self.current_idx]
        choices = sample_position_cards(slot, 5)
        self.add_item(DraftPickDropdown(slot, choices))

    async def handle_pick(self, interaction: discord.Interaction, slot: str, chosen_player: dict):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your draft board!", ephemeral=True)

        self.picked_players[slot] = chosen_player
        self.current_idx += 1

        name = chosen_player.get("cardName") or chosen_player.get("lastName") or "Player"
        ovr = chosen_player.get("rating", 110)

        if self.current_idx >= len(self.slots):
            self.clear_items()
            avg_ovr, chem_boost, final_ovr = calculate_draft_chemistry(self.picked_players)
            embed = discord.Embed(
                title=f"✅ Draft Squad Completed!",
                description=f"**Formation:** `{self.formation}`\n**Base OVR:** `{avg_ovr}` | **Chemistry Boost:** `+{chem_boost}`\n**Final Team OVR:** 🌟 **{final_ovr}**\n\n*Waiting for your opponent to complete their squad...*",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            await self.on_complete_callback(interaction, self.user.id, self.formation, self.picked_players, final_ovr)
        else:
            self.prompt_next_slot()
            next_slot = self.slots[self.current_idx]
            embed = discord.Embed(
                title=f"📋 Pick {next_slot} ({self.current_idx + 1}/{len(self.slots)})",
                description=f"Selected **{name}** ({ovr} OVR) for `{slot}`.\n\nChoose your next superstar from the 110+ OVR pool below:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=self)


class FormationSelectView(discord.ui.View):
    def __init__(self, user: discord.User, on_formation_chosen):
        super().__init__(timeout=180)
        self.user = user
        self.on_formation_chosen = on_formation_chosen
        
        options = [
            discord.SelectOption(label="4-3-3 Attack", description="Wingers + CAM offensive power", emoji="⚡"),
            discord.SelectOption(label="4-1-2-1-2 Narrow", description="Dual Strikers with CDM shield", emoji="🛡️"),
            discord.SelectOption(label="4-4-2 Flat", description="Classic balanced width & attack", emoji="⚖️"),
            discord.SelectOption(label="3-4-3 Flat", description="Ultra-attacking 3-back overload", emoji="🔥"),
            discord.SelectOption(label="5-3-2", description="Solid 5-at-the-back counter attack", emoji="🧱"),
        ]
        select = discord.ui.Select(placeholder="Choose your Draft Formation...", min_values=1, max_values=1, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your draft selection!", ephemeral=True)
        formation = interaction.data["values"][0]
        await self.on_formation_chosen(interaction, self.user, formation)


class DraftBattleRoomView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: int, bot, message: discord.Message = None):
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.bot = bot
        self.message = message
        self.channel_id = message.channel.id if (message and message.channel) else None
        self.draft_data = {}
        self.drafting_status = {
            challenger.id: "⏳ Not started",
            opponent.id: "⏳ Not started"
        }
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        
        btn_a_label = f"🔵 {self.challenger.display_name}'s Board"
        btn_a_style = discord.ButtonStyle.primary if self.challenger.id not in self.draft_data else discord.ButtonStyle.secondary
        btn_a = discord.ui.Button(label=btn_a_label, style=btn_a_style, custom_id="draft_btn_a", disabled=(self.challenger.id in self.draft_data))
        btn_a.callback = self.on_click_a
        self.add_item(btn_a)

        btn_b_label = f"🔴 {self.opponent.display_name}'s Board"
        btn_b_style = discord.ButtonStyle.danger if self.opponent.id not in self.draft_data else discord.ButtonStyle.secondary
        btn_b = discord.ui.Button(label=btn_b_label, style=btn_b_style, custom_id="draft_btn_b", disabled=(self.opponent.id in self.draft_data))
        btn_b.callback = self.on_click_b
        self.add_item(btn_b)

    def generate_status_embed(self):
        wager_text = f"\n🪙 **Coin Wager:** `{self.wager:,}` Coins each (Winner takes `{self.wager * 2:,}`)" if self.wager > 0 else ""
        
        embed = discord.Embed(
            title="⚔️ DRAFT BATTLE IN PROGRESS!",
            description=f"**{self.challenger.mention}** VS **{self.opponent.mention}**{wager_text}\n\n"
                        f"👉 **Click your personal button below** to enter your private draft room and draft your 11-man squad!\n\n"
                        f"### 📋 Squad Status:\n"
                        f"🔵 **{self.challenger.display_name}:** {self.drafting_status.get(self.challenger.id, '⏳ Waiting')}\n"
                        f"🔴 **{self.opponent.display_name}:** {self.drafting_status.get(self.opponent.id, '⏳ Waiting')}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Both players have 5 minutes to draft. Opponents cannot see your picks!")
        return embed

    async def on_click_a(self, interaction: discord.Interaction):
        if interaction.user.id != self.challenger.id:
            return await interaction.response.send_message(f"❌ This button is reserved for {self.challenger.mention}!", ephemeral=True)
        if self.challenger.id in self.draft_data:
            return await interaction.response.send_message("✅ You have already completed your draft squad!", ephemeral=True)
            
        self.drafting_status[self.challenger.id] = "🔄 Drafting squad..."
        view = FormationSelectView(self.challenger, self.on_formation_selected)
        embed = discord.Embed(
            title=f"📋 {self.challenger.display_name}'s Draft Room",
            description="**Step 1:** Select your tactical formation from the menu below:",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def on_click_b(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(f"❌ This button is reserved for {self.opponent.mention}!", ephemeral=True)
        if self.opponent.id in self.draft_data:
            return await interaction.response.send_message("✅ You have already completed your draft squad!", ephemeral=True)
            
        self.drafting_status[self.opponent.id] = "🔄 Drafting squad..."
        view = FormationSelectView(self.opponent, self.on_formation_selected)
        embed = discord.Embed(
            title=f"📋 {self.opponent.display_name}'s Draft Room",
            description="**Step 1:** Select your tactical formation from the menu below:",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def on_formation_selected(self, interaction: discord.Interaction, user: discord.User, formation: str):
        draft_view = SinglePlayerDraftView(user, formation, self.on_player_completed)
        slot1 = FORMATION_SLOTS[formation][0]
        embed = discord.Embed(
            title=f"📋 Pick {slot1} (1/{len(FORMATION_SLOTS[formation])})",
            description=f"**Formation:** `{formation}`\nChoose your first superstar from the 110+ OVR pool below:",
            color=discord.Color.blue() if user.id == self.challenger.id else discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=draft_view)

    async def on_player_completed(self, interaction: discord.Interaction, user_id: int, formation: str, players: dict, final_ovr: int):
        self.draft_data[user_id] = {
            "formation": formation,
            "players": players,
            "ovr": final_ovr
        }
        self.drafting_status[user_id] = f"✅ **Ready!** (🌟 {final_ovr} OVR)"
        self.update_buttons()

        # Update main match status room message
        try:
            if self.message:
                await self.message.edit(embed=self.generate_status_embed(), view=self)
            elif interaction.message:
                await interaction.message.edit(embed=self.generate_status_embed(), view=self)
        except Exception as e:
            print("[DraftBattle] Error editing draft room message:", e)

        # If both players finished -> simulate match!
        if len(self.draft_data) >= 2:
            self.stop()
            try:
                await self.simulate_match(interaction)
            except Exception as e:
                print(f"[DraftBattle] Error simulating match: {e}")
                import traceback
                traceback.print_exc()

    async def simulate_match(self, interaction: discord.Interaction = None):
        user_a = self.challenger
        user_b = self.opponent
        data_a = self.draft_data.get(user_a.id, {})
        data_b = self.draft_data.get(user_b.id, {})

        ovr_a = data_a.get("ovr", 115)
        ovr_b = data_b.get("ovr", 115)

        # Match calculation
        ovr_diff = ovr_a - ovr_b
        base_a_prob = 0.50 + (ovr_diff * 0.04)
        base_a_prob = max(0.20, min(0.80, base_a_prob))

        score_a = 0
        score_b = 0
        events = []

        attackers_a = [p.get("cardName", p.get("lastName", "Striker")) for pos, p in data_a.get("players", {}).items() if any(k in pos for k in ["ST", "RW", "LW", "CAM", "CF"])] or [user_a.display_name]
        attackers_b = [p.get("cardName", p.get("lastName", "Striker")) for pos, p in data_b.get("players", {}).items() if any(k in pos for k in ["ST", "RW", "LW", "CAM", "CF"])] or [user_b.display_name]

        # 5 match chances
        for minute in [15, 34, 52, 73, 88]:
            roll = random.random()
            if roll < base_a_prob:
                score_a += 1
                scorer = random.choice(attackers_a)
                events.append(f"⏱️ **{minute}'** ⚽ **GOAL!** {scorer} finds the net for **{user_a.display_name}**!")
            elif roll > 0.65:
                score_b += 1
                scorer = random.choice(attackers_b)
                events.append(f"⏱️ **{minute}'** ⚽ **GOAL!** {scorer} scores a screamer for **{user_b.display_name}**!")
            else:
                events.append(f"⏱️ **{minute}'** 🧤 Crucial save in the box keeps the scoreline tight!")

        # Record DB Result
        try:
            await database.record_draft_battle_result(user_a.id, user_b.id, score_a, score_b, self.wager)
        except Exception as e:
            print("[DraftBattle] Error recording draft battle DB result:", e)

        # Winner summary
        if score_a > score_b:
            result_title = f"🏆 {user_a.display_name} WINS THE DRAFT BATTLE!"
            winner_desc = f"👑 **{user_a.display_name}** defeated **{user_b.display_name}** (`{score_a} - {score_b}`)!\n📈 **{user_a.display_name}**: `+25 ELO` | `+3 Points`\n📉 **{user_b.display_name}**: `-15 ELO` | `+1 Point`"
            color = discord.Color.green()
        elif score_b > score_a:
            result_title = f"🏆 {user_b.display_name} WINS THE DRAFT BATTLE!"
            winner_desc = f"👑 **{user_b.display_name}** defeated **{user_a.display_name}** (`{score_b} - {score_a}`)!\n📈 **{user_b.display_name}**: `+25 ELO` | `+3 Points`\n📉 **{user_a.display_name}**: `-15 ELO` | `+1 Point`"
            color = discord.Color.green()
        else:
            result_title = f"🤝 DRAFT BATTLE ENDED IN A DRAW!"
            winner_desc = f"Both teams finished level (`{score_a} - {score_b}`)!\n📈 Both players receive `+5 ELO` & `+1 Point`."
            color = discord.Color.gold()

        if self.wager > 0:
            winner_desc += f"\n🪙 **Wager Payout:** `{self.wager * 2:,}` Coins!"

        match_embed = discord.Embed(
            title=result_title,
            description=f"### Final Score: **{user_a.display_name}** `{score_a}` ━ `{score_b}` **{user_b.display_name}**\n\n" + "\n".join(events) + f"\n\n---\n{winner_desc}",
            color=color
        )
        match_embed.add_field(name=f"🔵 {user_a.display_name}'s Draft", value=f"Formation: `{data_a.get('formation', 'N/A')}`\nRating: 🌟 **{ovr_a} OVR**", inline=True)
        match_embed.add_field(name=f"🔴 {user_b.display_name}'s Draft", value=f"Formation: `{data_b.get('formation', 'N/A')}`\nRating: 🌟 **{ovr_b} OVR**", inline=True)
        match_embed.set_footer(text="DestiFC Draft Battles • Use /draftbattle leaderboard to check rankings")

        squad_a = {"formation": data_a.get("formation", "4-3-3 Attack"), "players": {pos: {"name": p.get("cardName", p.get("lastName", pos)), "ovr": p.get("rating", 110)} for pos, p in data_a.get("players", {}).items()}}
        squad_b = {"formation": data_b.get("formation", "4-3-3 Attack"), "players": {pos: {"name": p.get("cardName", p.get("lastName", pos)), "ovr": p.get("rating", 110)} for pos, p in data_b.get("players", {}).items()}}

        # Try generating 3D image for Winner
        file = None
        try:
            winning_squad = squad_a if score_a >= score_b else squad_b
            img = generate_lineup_image(winning_squad, {})
            binary = io.BytesIO()
            img.save(binary, 'PNG')
            binary.seek(0)
            file = discord.File(fp=binary, filename='winning_draft.png')
            match_embed.set_image(url="attachment://winning_draft.png")
        except Exception as e:
            print("[DraftBattle] Error generating winning draft image:", e)

        # Resolve public target channel
        target_channel = None
        if self.message and self.message.channel:
            target_channel = self.message.channel
        elif interaction and interaction.channel:
            target_channel = interaction.channel
        elif self.channel_id:
            target_channel = self.bot.get_channel(self.channel_id)
            if not target_channel:
                try:
                    target_channel = await self.bot.fetch_channel(self.channel_id)
                except Exception:
                    pass

        # Update or complete lobby message
        try:
            if self.message:
                end_lobby_embed = discord.Embed(
                    title="⚔️ DRAFT BATTLE COMPLETE!",
                    description=f"Match between **{user_a.mention}** and **{user_b.mention}** has finished!\nFinal Score: `{score_a} - {score_b}`",
                    color=discord.Color.dark_grey()
                )
                await self.message.edit(embed=end_lobby_embed, view=None)
        except Exception as e:
            print("[DraftBattle] Error ending lobby view:", e)

        # Post results with ping into target channel
        if target_channel:
            try:
                if file:
                    file.fp.seek(0)
                    await target_channel.send(
                        content=f"🔔 {user_a.mention} {user_b.mention} — **Your Draft Battle Match is Complete!**",
                        embed=match_embed,
                        file=file
                    )
                else:
                    await target_channel.send(
                        content=f"🔔 {user_a.mention} {user_b.mention} — **Your Draft Battle Match is Complete!**",
                        embed=match_embed
                    )
            except Exception as e:
                print("[DraftBattle] Error sending result message:", e)

        if interaction:
            try:
                ch_mention = target_channel.mention if target_channel else "the channel"
                await interaction.followup.send(f"🏁 **Draft Battle Finished!** Check {ch_mention} to view full highlights and final score!", ephemeral=True)
            except Exception:
                pass


class DraftBattleChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: int, bot):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.bot = bot
        self.accepted = False

    @discord.ui.button(label="Accept Draft Battle ⚔️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ Only the challenged opponent can accept this match!", ephemeral=True)

        if self.wager > 0:
            user_a = await database.get_user(self.challenger.id)
            user_b = await database.get_user(self.opponent.id)
            if user_a.get("coins", 0) < self.wager:
                return await interaction.response.send_message(f"❌ {self.challenger.mention} no longer has enough coins for the **{self.wager:,}** coin wager!", ephemeral=True)
            if user_b.get("coins", 0) < self.wager:
                return await interaction.response.send_message(f"❌ You don't have enough coins for the **{self.wager:,}** coin wager!", ephemeral=True)
            
            # Escrow wager
            await database.add_coins(self.challenger.id, -self.wager)
            await database.add_coins(self.opponent.id, -self.wager)

        self.accepted = True
        self.stop()

        room_view = DraftBattleRoomView(self.challenger, self.opponent, self.wager, self.bot, interaction.message)
        await interaction.response.edit_message(embed=room_view.generate_status_embed(), view=room_view)

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id and interaction.user.id != self.challenger.id:
            return await interaction.response.send_message("❌ You are not part of this challenge.", ephemeral=True)

        self.stop()
        embed = discord.Embed(
            title="🚫 Draft Battle Cancelled",
            description=f"{interaction.user.mention} declined the draft battle challenge.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ================= Cog =================

class DraftBattleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    draftbattle_group = app_commands.Group(name="draftbattle", description="FC FUT Draft Battles 1v1 Mode")

    @app_commands.command(name="draft_challenge", description="Challenge another user to a live 1v1 Draft Battle with 110+ OVR cards")
    @app_commands.describe(user="Opponent to challenge", wager="Optional coin wager (winner takes all)")
    async def draft_challenge(self, interaction: discord.Interaction, user: discord.Member, wager: int = 0):
        await self.challenge(interaction, user, wager)

    @draftbattle_group.command(name="challenge", description="Challenge another user to a live 1v1 Draft Battle with 110+ OVR cards")
    @app_commands.describe(user="Opponent to challenge", wager="Optional coin wager (winner takes all)")
    async def challenge(self, interaction: discord.Interaction, user: discord.Member, wager: int = 0):
        if user.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot challenge yourself!", ephemeral=True)
        if user.bot:
            return await interaction.response.send_message("❌ You cannot challenge a bot to a draft battle!", ephemeral=True)
        if wager < 0:
            return await interaction.response.send_message("❌ Wager cannot be negative.", ephemeral=True)

        if wager > 0:
            user_data = await database.get_user(interaction.user.id)
            if user_data.get("coins", 0) < wager:
                return await interaction.response.send_message(f"❌ You don't have enough coins for a **{wager:,}** coin wager! Your balance: **{user_data.get('coins', 0):,}**", ephemeral=True)

        view = DraftBattleChallengeView(interaction.user, user, wager, self.bot)
        view.channel = interaction.channel
        wager_text = f"\n🪙 **Coin Wager:** `{wager:,}` Coins (Winner takes `{wager * 2:,}`)" if wager > 0 else ""

        embed = discord.Embed(
            title="⚔️ DRAFT BATTLE CHALLENGE!",
            description=f"{user.mention}, you have been challenged to an **FC Draft Battle 1v1** by **{interaction.user.mention}**!\n\n🎮 **Format:**\n• Pick Formations & 110+ OVR Superstars\n• Chemistry Synergy Boosts\n• Live 90-Minute Simulated Match\n• ELO & Leaderboard Points{wager_text}\n\n*Click Accept below within 60 seconds to enter the draft room:*",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(content=user.mention, embed=embed, view=view)

    @draftbattle_group.command(name="leaderboard", description="View the Top 10 Draft Battle Champions ranked by ELO Rating")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        lb = await database.get_draft_battle_leaderboard(10)

        if not lb:
            return await interaction.followup.send("🏆 No Draft Battle matches recorded yet! Use `/draftbattle challenge @user` to play the first match.")

        desc = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, row in enumerate(lb):
            medal = medals[i] if i < len(medals) else f"#{i+1}"
            u_id = row['user_id']
            elo = row['draft_battle_elo']
            wins = row['draft_battle_wins']
            losses = row['draft_battle_losses']
            draws = row['draft_battle_draws']
            pts = row['draft_battle_points']

            total_games = wins + losses + draws
            winrate = round((wins / total_games) * 100) if total_games > 0 else 0

            desc += f"{medal} <@{u_id}> — ⚡ **{elo} ELO** | **{pts} pts**\n   *(W: {wins} | L: {losses} | D: {draws} — {winrate}% Winrate)*\n\n"

        embed = discord.Embed(
            title="👑 DRAFT BATTLE GLOBAL LEADERBOARD",
            description=desc,
            color=discord.Color.gold()
        )
        embed.set_footer(text="Rankings update instantly after every /draftbattle match")
        await interaction.followup.send(embed=embed)

    @draftbattle_group.command(name="stats", description="View Draft Battle career stats for yourself or another player")
    @app_commands.describe(user="Target player (leave empty for yourself)")
    async def stats(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        await interaction.response.defer()

        data = await database.get_draft_battle_stats(target.id)
        wins = data.get("draft_battle_wins", 0)
        losses = data.get("draft_battle_losses", 0)
        draws = data.get("draft_battle_draws", 0)
        elo = data.get("draft_battle_elo", 1000)
        pts = data.get("draft_battle_points", 0)

        total = wins + losses + draws
        winrate = round((wins / total) * 100) if total > 0 else 0

        # Tier calculation based on ELO
        if elo >= 1400: rank_tier = "💎 Elite Draft Champion"
        elif elo >= 1250: rank_tier = "🥇 Master Division I"
        elif elo >= 1150: rank_tier = "🥈 Pro Division II"
        elif elo >= 1050: rank_tier = "🥉 Challenger Division III"
        else: rank_tier = "⚽ Division IV"

        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Draft Battle Career",
            description=f"**Division:** {rank_tier}\n**ELO Rating:** ⚡ **{elo}** | **Draft Points:** ⭐ **{pts}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Matches Played", value=str(total), inline=True)
        embed.add_field(name="Record (W-L-D)", value=f"{wins} - {losses} - {draws}", inline=True)
        embed.add_field(name="Win Rate", value=f"{winrate}%", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(DraftBattleCog(bot))
