import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio
import io
import time
import traceback
import maps
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
    
    # Check if database official cache has cards (instant RAM lookup)
    if database._OFFICIAL_CARDS_CACHE:
        all_ram_cards = []
        for r, cards in database._OFFICIAL_CARDS_CACHE.items():
            if r >= 108:
                all_ram_cards.extend(cards)
        if all_ram_cards:
            DRAFT_POOL_CACHE = all_ram_cards
            LAST_CACHE_TIME = now
            return DRAFT_POOL_CACHE

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
        club = maps.get_club_display(p)
        nation = maps.get_nation_display(p)
        clubs[club] = clubs.get(club, 0) + 1
        nations[nation] = nations.get(nation, 0) + 1

    avg_ovr = total_ovr / max(1, count)
    chem_score = 0
    for c, cnt in clubs.items():
        if cnt >= 2 and c != "🛡️ Club": chem_score += (cnt * 2)
    for n, cnt in nations.items():
        if cnt >= 2 and n != "🌍 World": chem_score += (cnt * 2)

    chem_boost = min(8, chem_score // 3)
    final_ovr = round(avg_ovr + chem_boost)
    return round(avg_ovr), chem_boost, final_ovr

def generate_ai_draft_squad():
    """Generates a competitive 11-man AI Draft squad."""
    formation = random.choice(DRAFT_FORMATIONS)
    slots = FORMATION_SLOTS[formation]
    players = {}
    for slot in slots:
        choices = sample_position_cards(slot, 5)
        chosen = max(choices, key=lambda x: x.get('rating', 110))
        players[slot] = chosen
    avg_ovr, chem_boost, final_ovr = calculate_draft_chemistry(players)
    return {
        "formation": formation,
        "players": players,
        "ovr": final_ovr
    }

class AIDraftUser:
    def __init__(self):
        self.id = 0
        self.display_name = "DestiFC AI Bot 🤖"
        self.mention = "**DestiFC AI Bot 🤖**"
        self.bot = True
        self.avatar = type("Avatar", (), {"url": "https://cdn.discordapp.com/embed/avatars/0.png"})()
        self.display_avatar = self.avatar

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
            club = maps.get_club_display(p)
            nation = maps.get_nation_display(p)
            options.append(discord.SelectOption(
                label=f"{ovr} {name} ({pos})"[:100],
                description=f"{club} | {nation}"[:100],
                value=str(i),
                emoji="⭐" if ovr >= 120 else "⚽"
            ))
        super().__init__(placeholder=f"Pick your {slot}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.view.handle_pick(interaction, self.slot, self.choices[int(self.values[0])])
        except Exception as e:
            print(f"[DraftBattle] Error in DraftPickDropdown callback: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred selecting this player.", ephemeral=True)


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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item = None):
        print(f"[DraftBattle] Error in SinglePlayerDraftView: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred on your draft board.", ephemeral=True)

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
                description=f"**Formation:** `{self.formation}`\n**Base OVR:** `{avg_ovr}` | **Chemistry Boost:** `+{chem_boost}`\n**Final Team OVR:** 🌟 **{final_ovr}**\n\n*Simulating match highlights... Check the battle channel!*",
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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item = None):
        print(f"[DraftBattle] Error in FormationSelectView: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred selecting your formation.", ephemeral=True)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your draft selection!", ephemeral=True)
        formation = interaction.data["values"][0]
        await self.on_formation_chosen(interaction, self.user, formation)


class DraftBattleRoomView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: int, bot, message: discord.Message = None, channel_id: int = None, is_solo: bool = False):
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.bot = bot
        self.message = message
        self.channel_id = channel_id or (message.channel.id if (message and message.channel) else None)
        self.is_solo = is_solo
        self.draft_data = {}
        self.drafting_status = {
            challenger.id: "⏳ Not started",
            opponent.id: ("🤖 AI Ready" if is_solo else "⏳ Not started")
        }
        self.update_buttons()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item = None):
        print(f"[DraftBattle] Error in DraftBattleRoomView: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("❌ An error occurred in the draft room.", ephemeral=True)
            except Exception:
                pass

    def update_buttons(self):
        self.clear_items()
        
        btn_a_label = f"🔵 {self.challenger.display_name}'s Board"
        btn_a_style = discord.ButtonStyle.primary if self.challenger.id not in self.draft_data else discord.ButtonStyle.secondary
        btn_a = discord.ui.Button(label=btn_a_label[:80], style=btn_a_style, custom_id="draft_btn_a", disabled=(self.challenger.id in self.draft_data))
        btn_a.callback = self.on_click_a
        self.add_item(btn_a)

        if not self.is_solo:
            btn_b_label = f"🔴 {self.opponent.display_name}'s Board"
            btn_b_style = discord.ButtonStyle.danger if self.opponent.id not in self.draft_data else discord.ButtonStyle.secondary
            btn_b = discord.ui.Button(label=btn_b_label[:80], style=btn_b_style, custom_id="draft_btn_b", disabled=(self.opponent.id in self.draft_data))
            btn_b.callback = self.on_click_b
            self.add_item(btn_b)

            # Auto-fill button if opponent is AFK
            if self.challenger.id in self.draft_data and self.opponent.id not in self.draft_data:
                auto_btn = discord.ui.Button(label="🤖 Auto-Draft for Opponent & Play", style=discord.ButtonStyle.success, custom_id="draft_btn_auto")
                auto_btn.callback = self.on_auto_fill
                self.add_item(auto_btn)

    def generate_status_embed(self):
        wager_text = f"\n🪙 **Coin Wager:** `{self.wager:,}` Coins each (Winner takes `{self.wager * 2:,}`)" if self.wager > 0 else ""
        
        opp_name = self.opponent.mention if not self.is_solo else "**DestiFC AI Bot 🤖**"
        opp_display = self.opponent.display_name if not self.is_solo else "DestiFC AI Bot 🤖"
        
        embed = discord.Embed(
            title="⚔️ DRAFT BATTLE IN PROGRESS!",
            description=f"**{self.challenger.mention}** VS {opp_name}{wager_text}\n\n"
                        f"👉 **Click your personal button below** to enter your private draft room and draft your 11-man squad!\n\n"
                        f"### 📋 Squad Status:\n"
                        f"🔵 **{self.challenger.display_name}:** {self.drafting_status.get(self.challenger.id, '⏳ Waiting')}\n"
                        f"🔴 **{opp_display}:** {self.drafting_status.get(self.opponent.id, '⏳ Waiting')}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Draft your 11 superstars! The match simulates immediately once ready.")
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
        if self.is_solo:
            return await interaction.response.send_message("🤖 Opponent is AI in solo mode!", ephemeral=True)
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

    async def on_auto_fill(self, interaction: discord.Interaction):
        if interaction.user.id != self.challenger.id:
            return await interaction.response.send_message("❌ Only the challenger can trigger auto-draft!", ephemeral=True)
        
        await interaction.response.send_message("🤖 Auto-drafting squad for opponent...", ephemeral=True)
        ai_squad = generate_ai_draft_squad()
        self.draft_data[self.opponent.id] = ai_squad
        self.drafting_status[self.opponent.id] = f"✅ **Auto-Drafted!** (🌟 {ai_squad['ovr']} OVR)"
        self.stop()
        await self.simulate_match(interaction)

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

        # If Solo Mode -> Auto-draft AI and simulate match immediately!
        if self.is_solo:
            ai_squad = generate_ai_draft_squad()
            self.draft_data[self.opponent.id] = ai_squad
            self.drafting_status[self.opponent.id] = f"✅ **Ready!** (🌟 {ai_squad['ovr']} OVR)"
            self.stop()
            try:
                await self.simulate_match(interaction)
            except Exception as e:
                print(f"[DraftBattle] Error simulating solo match: {e}")
                import traceback
                traceback.print_exc()
            return

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

        def is_boosted_card(p_dict):
            if not isinstance(p_dict, dict): return False
            p_id = str(p_dict.get('id') or p_dict.get('assetId') or '')
            src = str(p_dict.get('source') or '').upper()
            return bool(p_dict.get('is_custom') or p_dict.get('is_signature_box') or 'CUSTOM' in src or 'SIGNATURE' in src or p_id.startswith('custom_') or p_id.startswith('sig_'))

        # Build candidate pools with weighted boost for custom / signature cards
        attackers_a_cards = [p for pos, p in data_a.get("players", {}).items() if any(k in pos for k in ["ST", "RW", "LW", "CAM", "CF"])]
        attackers_b_cards = [p for pos, p in data_b.get("players", {}).items() if any(k in pos for k in ["ST", "RW", "LW", "CAM", "CF"])]
        
        midfielders_a_cards = [p for pos, p in data_a.get("players", {}).items() if any(k in pos for k in ["CM", "CDM", "CAM", "LM", "RM"])]
        midfielders_b_cards = [p for pos, p in data_b.get("players", {}).items() if any(k in pos for k in ["CM", "CDM", "CAM", "LM", "RM"])]

        def pick_weighted_player(cards_list, fallback_name):
            if not cards_list:
                return fallback_name, False
            weights = [2.0 if is_boosted_card(c) else 1.0 for c in cards_list]
            chosen = random.choices(cards_list, weights=weights, k=1)[0]
            p_name = chosen.get("cardName") or chosen.get("lastName", fallback_name)
            return p_name, is_boosted_card(chosen)

        goals_breakdown_a = {}
        goals_breakdown_b = {}
        assists_breakdown_a = {}
        assists_breakdown_b = {}

        # 5 match chances
        for minute in [15, 34, 52, 73, 88]:
            roll = random.random()
            if roll < base_a_prob:
                score_a += 1
                scorer, is_boost = pick_weighted_player(attackers_a_cards, user_a.display_name)
                goals_breakdown_a[scorer] = goals_breakdown_a.get(scorer, 0) + 1
                
                # Assign assist
                mid_candidates = [c for c in midfielders_a_cards if (c.get('cardName') or c.get('lastName')) != scorer] or attackers_a_cards
                assister, _ = pick_weighted_player(mid_candidates, None) if mid_candidates else (None, False)
                
                aura = "⚡ **[SIGNATURE STRIKE]**" if is_boost else "⚽ **GOAL!**"
                if assister:
                    assists_breakdown_a[assister] = assists_breakdown_a.get(assister, 0) + 1
                    events.append(f"⏱️ **{minute}'** {aura} {scorer} finds the net! (Assist: {assister})")
                else:
                    events.append(f"⏱️ **{minute}'** {aura} {scorer} scores a solo stunner for **{user_a.display_name}**!")
            elif roll > 0.65:
                score_b += 1
                scorer, is_boost = pick_weighted_player(attackers_b_cards, user_b.display_name)
                goals_breakdown_b[scorer] = goals_breakdown_b.get(scorer, 0) + 1
                
                mid_candidates = [c for c in midfielders_b_cards if (c.get('cardName') or c.get('lastName')) != scorer] or attackers_b_cards
                assister, _ = pick_weighted_player(mid_candidates, None) if mid_candidates else (None, False)
                
                aura = "⚡ **[SIGNATURE STRIKE]**" if is_boost else "⚽ **GOAL!**"
                if assister:
                    assists_breakdown_b[assister] = assists_breakdown_b.get(assister, 0) + 1
                    events.append(f"⏱️ **{minute}'** {aura} {scorer} strikes! (Assist: {assister})")
                else:
                    events.append(f"⏱️ **{minute}'** {aura} {scorer} scores a screamer for **{user_b.display_name}**!")
            else:
                events.append(f"⏱️ **{minute}'** 🧤 Crucial save in the box keeps the scoreline tight!")

        # Record DB Result for PVP & ELO
        if not self.is_solo:
            try:
                await database.record_draft_battle_result(user_a.id, user_b.id, score_a, score_b, self.wager)
            except Exception as e:
                print("[DraftBattle] Error recording draft battle DB result:", e)
        else:
            # Solo Rewards
            if score_a > score_b:
                await database.add_coins(user_a.id, 5_000_000)
                try:
                    from cogs.season import add_season_xp
                    await add_season_xp(user_a.id, 50)
                except Exception: pass

        # Record Player Performance Stats for User A's Squad with Custom/Signature Boost
        try:
            stats_list_a = []
            for pos, p in data_a.get("players", {}).items():
                p_name = p.get("cardName") or p.get("lastName") or pos
                clean_pos = ''.join([c for c in pos if not c.isdigit()]).strip().upper()
                is_df_gk = any(k in clean_pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                cs = 1 if (is_df_gk and score_b == 0) else 0
                g_count = goals_breakdown_a.get(p_name, 0)
                a_count = assists_breakdown_a.get(p_name, 0)
                boost_bonus = 1.0 if is_boosted_card(p) else 0.0
                base_rating = 7.0 + (g_count * 1.2) + (a_count * 0.8) + (0.5 if score_a > score_b else (-0.5 if score_b > score_a else 0)) + boost_bonus
                rating = round(min(10.0, max(5.5, base_rating)), 1)
                stats_list_a.append({
                    "player_name": p_name,
                    "position": clean_pos,
                    "ovr": p.get("rating", 110),
                    "goals": g_count,
                    "assists": a_count,
                    "clean_sheets": cs,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "rating": rating,
                    "is_motm": 1 if (score_a >= score_b and (g_count >= 1 or is_boosted_card(p))) else 0
                })
            await database.record_player_match_stats(user_a.id, stats_list_a)

            # Record for User B if human
            if not self.is_solo and user_b.id != 0:
                stats_list_b = []
                for pos, p in data_b.get("players", {}).items():
                    p_name = p.get("cardName") or p.get("lastName") or pos
                    clean_pos = ''.join([c for c in pos if not c.isdigit()]).strip().upper()
                    is_df_gk = any(k in clean_pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                    cs = 1 if (is_df_gk and score_a == 0) else 0
                    g_count = goals_breakdown_b.get(p_name, 0)
                    a_count = assists_breakdown_b.get(p_name, 0)
                    base_rating = 7.0 + (g_count * 1.2) + (a_count * 0.8) + (0.5 if score_b > score_a else (-0.5 if score_a > score_b else 0))
                    rating = round(min(10.0, max(5.5, base_rating)), 1)
                    stats_list_b.append({
                        "player_name": p_name,
                        "position": clean_pos,
                        "ovr": p.get("rating", 110),
                        "goals": g_count,
                        "assists": a_count,
                        "clean_sheets": cs,
                        "yellow_cards": 0,
                        "red_cards": 0,
                        "rating": rating,
                        "is_motm": 1 if (score_b > score_a and g_count >= 1) else 0
                    })
                await database.record_player_match_stats(user_b.id, stats_list_b)
        except Exception as e:
            print(f"[DraftBattle] Error recording player stats: {e}")

        # Winner summary
        if score_a > score_b:
            result_title = f"🏆 {user_a.display_name} WINS THE DRAFT BATTLE!"
            winner_desc = f"👑 **{user_a.display_name}** defeated **{user_b.display_name}** (`{score_a} - {score_b}`)!\n📈 **{user_a.display_name}**: `+25 ELO` | `+3 Points`"
            if not self.is_solo:
                winner_desc += f"\n📉 **{user_b.display_name}**: `-15 ELO` | `+1 Point`"
            else:
                winner_desc += f"\n💰 **Reward:** `+5,000,000 Coins` | `+50 Season XP`"
            color = discord.Color.green()
        elif score_b > score_a:
            result_title = f"🏆 {user_b.display_name} WINS THE DRAFT BATTLE!"
            winner_desc = f"👑 **{user_b.display_name}** defeated **{user_a.display_name}** (`{score_b} - {score_a}`)!\n📈 **{user_b.display_name}**: `+25 ELO` | `+3 Points`\n📉 **{user_a.display_name}**: `-15 ELO` | `+1 Point`"
            color = discord.Color.red()
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
        match_embed.set_footer(text="DestiFC Draft Battles • Stats & records recorded to /club_stats")

        squad_a = {"formation": data_a.get("formation", "4-3-3 Attack"), "players": {pos: {"name": p.get("cardName", p.get("lastName", pos)), "ovr": p.get("rating", 110)} for pos, p in data_a.get("players", {}).items()}}
        squad_b = {"formation": data_b.get("formation", "4-3-3 Attack"), "players": {pos: {"name": p.get("cardName", p.get("lastName", pos)), "ovr": p.get("rating", 110)} for pos, p in data_b.get("players", {}).items()}}

        # Try generating 3D image for Winner
        file = None
        try:
            winning_squad = squad_a if score_a >= score_b else squad_b
            img = await asyncio.to_thread(generate_lineup_image, winning_squad, {})
            binary = io.BytesIO()
            img.save(binary, 'PNG')
            binary.seek(0)
            file = discord.File(fp=binary, filename='winning_draft.png')
            match_embed.set_image(url="attachment://winning_draft.png")
        except Exception as e:
            print("[DraftBattle] Error generating winning draft image:", e)

        # Resolve public target channel
        target_channel = None
        if self.channel_id:
            target_channel = self.bot.get_channel(self.channel_id)
            if not target_channel:
                try:
                    target_channel = await self.bot.fetch_channel(self.channel_id)
                except Exception:
                    pass
        if not target_channel and self.message and self.message.channel:
            target_channel = self.message.channel
        if not target_channel and interaction and interaction.channel:
            target_channel = interaction.channel

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
        ping_content = f"🔔 {user_a.mention} {user_b.mention} — **Your Draft Battle Match is Complete!**" if not self.is_solo else f"🔔 {user_a.mention} — **Your Solo Draft Battle is Complete!**"
        
        if target_channel:
            try:
                if file:
                    file.fp.seek(0)
                    await target_channel.send(content=ping_content, embed=match_embed, file=file)
                else:
                    await target_channel.send(content=ping_content, embed=match_embed)
            except Exception as e:
                print("[DraftBattle] Error sending result message:", e)
        else:
            print(f"[DraftBattle] Warning: Could not resolve target_channel (channel_id={self.channel_id})")

        if interaction:
            try:
                ch_mention = target_channel.mention if target_channel else "the channel"
                await interaction.followup.send(f"🏁 **Draft Battle Finished!** Check {ch_mention} to view the match highlights and final score!", ephemeral=True)
            except Exception:
                pass


class DraftBattleChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: int, bot, channel_id: int = None):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.bot = bot
        self.channel_id = channel_id
        self.accepted = False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item = None):
        print(f"[DraftBattle] Error in DraftBattleChallengeView: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("❌ An error occurred processing this draft battle challenge.", ephemeral=True)
            except Exception:
                pass

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

        ch_id = interaction.channel_id or self.channel_id
        room_view = DraftBattleRoomView(self.challenger, self.opponent, self.wager, self.bot, interaction.message, channel_id=ch_id, is_solo=False)
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
        asyncio.create_task(self._prewarm_draft_pool())

    async def _prewarm_draft_pool(self):
        global DRAFT_POOL_CACHE, LAST_CACHE_TIME
        try:
            cards = await database.get_official_cards_by_rating(108, 125, limit=500)
            if cards:
                DRAFT_POOL_CACHE = cards
                LAST_CACHE_TIME = time.time()
                print(f"[DraftBattle] Prewarmed {len(cards)} 108+ OVR cards in RAM draft pool!")
        except Exception as e:
            print(f"[DraftBattle] Prewarm draft pool note: {e}")

    draftbattle_group = app_commands.Group(name="draftbattle", description="FC FUT Draft Battles 1v1 Mode")

    @app_commands.command(name="draft_challenge", description="Challenge another user or AI to a live Draft Battle with 110+ OVR cards")
    @app_commands.describe(user="Opponent to challenge (leave empty to play Solo vs AI)", wager="Optional coin wager for PvP (winner takes all)")
    async def draft_challenge(self, interaction: discord.Interaction, user: discord.Member = None, wager: int = 0):
        if user is None or user.id == interaction.user.id or user.bot:
            # Solo Draft Challenge vs AI
            ai_user = AIDraftUser()
            room_view = DraftBattleRoomView(interaction.user, ai_user, 0, self.bot, channel_id=interaction.channel_id, is_solo=True)
            embed = discord.Embed(
                title="⚔️ SOLO DRAFT CHALLENGE (VS AI)",
                description=(
                    f"Welcome {interaction.user.mention}! Draft your ultimate 11-player squad to take on the **DestiFC AI Bot 🤖**!\n\n"
                    f"👉 **Click '🔵 {interaction.user.display_name}'s Board' below** to start drafting!"
                ),
                color=discord.Color.gold()
            )
            embed.set_footer(text="Pick your formation and 11 superstars. Match simulates upon squad completion!")
            msg = await interaction.response.send_message(embed=embed, view=room_view)
            room_view.message = await interaction.original_response()
            return

        # PvP Draft Battle
        if wager < 0:
            return await interaction.response.send_message("❌ Wager cannot be negative.", ephemeral=True)

        if wager > 0:
            user_data = await database.get_user(interaction.user.id)
            if user_data.get("coins", 0) < wager:
                return await interaction.response.send_message(f"❌ You don't have enough coins for a **{wager:,}** coin wager! Your balance: **{user_data.get('coins', 0):,}**", ephemeral=True)

        view = DraftBattleChallengeView(interaction.user, user, wager, self.bot, channel_id=interaction.channel_id)
        wager_text = f"\n🪙 **Coin Wager:** `{wager:,}` Coins (Winner takes `{wager * 2:,}`)" if wager > 0 else ""

        embed = discord.Embed(
            title="⚔️ DRAFT BATTLE CHALLENGE!",
            description=f"{user.mention}, you have been challenged to an **FC Draft Battle 1v1** by **{interaction.user.mention}**!\n\n🎮 **Format:**\n• Pick Formations & 110+ OVR Superstars\n• Chemistry Synergy Boosts\n• Live Simulated Match with Highlights\n• ELO & Player Stats Tracking{wager_text}\n\n*Click Accept below within 60 seconds to enter the draft room:*",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(content=user.mention, embed=embed, view=view)
        view.message = await interaction.original_response()

    @draftbattle_group.command(name="solo", description="Play a Solo Draft Battle against the DestiFC AI")
    async def solo_draft(self, interaction: discord.Interaction):
        await self.draft_challenge(interaction, user=None, wager=0)

    @draftbattle_group.command(name="challenge", description="Challenge another user to a live 1v1 Draft Battle with 110+ OVR cards")
    @app_commands.describe(user="Opponent to challenge", wager="Optional coin wager (winner takes all)")
    async def challenge(self, interaction: discord.Interaction, user: discord.Member, wager: int = 0):
        await self.draft_challenge(interaction, user=user, wager=wager)

    @draftbattle_group.command(name="leaderboard", description="View the Top 10 Draft Battle Champions ranked by ELO Rating")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        lb = await database.get_draft_battle_leaderboard(10)

        if not lb:
            return await interaction.followup.send("🏆 No Draft Battle matches recorded yet! Use `/draft_challenge` to play the first match.")

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
