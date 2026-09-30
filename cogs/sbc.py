import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import database
import json
import random
import time

from maps import extract_pos

# Templates for auto-generating SBCs
LEAGUES = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Eredivisie", "Liga Portugal", "MLS", "Saudi Pro League"]
NATIONS = ["Spain", "Brazil", "France", "Argentina", "Germany", "England", "Portugal", "Netherlands", "Italy", "Belgium"]
POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST", "CF"]

SBC_TEMPLATES = [
    {"rule": "min_avg_ovr",    "label": "Minimum Average OVR: {val}"},
    {"rule": "min_count",      "label": "Submit {val} players"},
    {"rule": "min_league",     "label": "At least {val} players from {extra}"},
    {"rule": "min_nations",    "label": "At least {val} different nations"},
    {"rule": "max_same_club",  "label": "Maximum {val} players from the same club"},
    {"rule": "min_ovr_cards",  "label": "At least {val} cards rated {extra}+"},
]


def generate_daily_sbcs():
    """Generate 3 unique SBCs with escalating difficulty."""
    sbcs = []

    # --- EASY SBC ---
    league = random.choice(LEAGUES)
    sbcs.append({
        "name": f"🟢 {league} Starter",
        "description": f"Build a squad using {league} players!",
        "card_count": 5,
        "rules": [
            {"type": "min_avg_ovr", "value": 112},
            {"type": "min_league_keyword", "value": 3, "keyword": league},
        ],
        "reward_min": 117, "reward_max": 118,
        "reward_label": "🃏 Random 117-118 Card"
    })

    # --- MEDIUM SBC ---
    nation = random.choice(NATIONS)
    sbcs.append({
        "name": f"🟡 {nation} National Team",
        "description": f"Assemble a team with {nation} players!",
        "card_count": 8,
        "rules": [
            {"type": "min_avg_ovr", "value": 114},
            {"type": "min_nations", "value": 3},
            {"type": "min_ovr_cards", "value": 2, "min_ovr": 116},
        ],
        "reward_min": 118, "reward_max": 119,
        "reward_label": "🃏 Random 118-119 Card"
    })

    # --- HARD SBC ---
    sbcs.append({
        "name": f"🔴 Elite Sacrifice",
        "description": "Sacrifice your best cards for a massive reward!",
        "card_count": 11,
        "rules": [
            {"type": "min_avg_ovr", "value": 116},
            {"type": "min_nations", "value": 4},
            {"type": "min_ovr_cards", "value": 3, "min_ovr": 118},
        ],
        "reward_min": 119, "reward_max": 120,
        "reward_label": "🃏 Random 119-120 Card"
    })

    return sbcs


async def ensure_sbc_table(db=None):
    p = await database.get_db()
    await p.execute('''
        CREATE TABLE IF NOT EXISTS active_sbcs (
            id BIGSERIAL PRIMARY KEY,
            sbc_json TEXT,
            expires_at BIGINT
        );
        CREATE TABLE IF NOT EXISTS sbc_completions (
            user_id BIGINT,
            sbc_id BIGINT,
            completed_at BIGINT,
            PRIMARY KEY (user_id, sbc_id)
        );
    ''')


async def get_active_sbcs():
    p = await database.get_db()
    now = int(time.time())
    rows = await p.fetch('SELECT id, sbc_json, expires_at FROM active_sbcs WHERE expires_at > $1', now)
    return [(row['id'], json.loads(row['sbc_json']), row['expires_at']) for row in rows]


async def refresh_sbcs_if_needed():
    active = await get_active_sbcs()
    if len(active) >= 3:
        return False  # Still have active SBCs

    p = await database.get_db()
    # Clear expired
    await p.execute('DELETE FROM active_sbcs WHERE expires_at <= $1', int(time.time()))
    # Also clear completions for expired SBCs
    await p.execute('DELETE FROM sbc_completions WHERE sbc_id NOT IN (SELECT id FROM active_sbcs)')

    expires = int(time.time()) + 86400  # 24 hours from now
    new_sbcs = generate_daily_sbcs()
    for sbc in new_sbcs:
        await p.execute('INSERT INTO active_sbcs (sbc_json, expires_at) VALUES ($1, $2)',
                         json.dumps(sbc), expires)
    print(f"[SBC] Generated 3 new daily SBCs!")
    return True


def check_submission(inventory_rows, sbc_data):
    """
    Given inventory rows (list of dicts) and sbc rules, try to auto-pick the cheapest
    cards that satisfy all rules. Returns (selected_cards, error_message).
    """
    needed = sbc_data["card_count"]
    rules = sbc_data["rules"]

    # Sort inventory by OVR ascending (sacrifice cheapest first)
    cards = sorted(inventory_rows, key=lambda c: c.get('ovr', 0))

    # Filter out custom/untradable cards from SBC submission
    cards = [c for c in cards if not json.loads(c.get('player_data', '{}')).get('is_custom', False)]

    if len(cards) < needed:
        return None, f"You need {needed} eligible cards but only have {len(cards)}."

    # Try all combinations? No, too expensive. Use greedy approach.
    # First pass: find cards that satisfy specific constraints, then fill rest

    selected = []
    remaining = list(cards)

    # Check for min_ovr_cards constraint first (hardest to satisfy)
    for rule in rules:
        if rule["type"] == "min_ovr_cards":
            min_ovr = rule["min_ovr"]
            count_needed = rule["value"]
            high_cards = [c for c in remaining if c.get('ovr', 0) >= min_ovr]
            if len(high_cards) < count_needed:
                return None, f"You need at least {count_needed} cards rated {min_ovr}+, but you only have {len(high_cards)}."
            # Add the cheapest high OVR cards
            for c in high_cards[:count_needed]:
                if c not in selected:
                    selected.append(c)
                    remaining.remove(c)

    # Fill remaining slots with cheapest cards
    while len(selected) < needed and remaining:
        selected.append(remaining.pop(0))

    if len(selected) < needed:
        return None, f"Not enough cards to fill {needed} slots."

    # Now validate all rules
    for rule in rules:
        if rule["type"] == "min_avg_ovr":
            avg = sum(c.get('ovr', 0) for c in selected) / len(selected)
            if avg < rule["value"]:
                return None, f"Average OVR is {avg:.1f}, but minimum required is {rule['value']}."

        elif rule["type"] == "min_nations":
            nations = set()
            for c in selected:
                pd = json.loads(c.get('player_data', '{}'))
                n_id = pd.get('nation', {}).get('id', 0)
                nations.add(n_id)
            if len(nations) < rule["value"]:
                return None, f"You have {len(nations)} different nations, but need at least {rule['value']}."

        elif rule["type"] == "min_ovr_cards":
            high = [c for c in selected if c.get('ovr', 0) >= rule["min_ovr"]]
            if len(high) < rule["value"]:
                return None, f"Need {rule['value']} cards rated {rule['min_ovr']}+, selected only has {len(high)}."

    return selected, None


class SBCCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sbc_refresh_loop.start()

    def cog_unload(self):
        self.sbc_refresh_loop.cancel()

    @tasks.loop(hours=1)
    async def sbc_refresh_loop(self):
        await refresh_sbcs_if_needed()

    @sbc_refresh_loop.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="sbc", description="View today's Squad Building Challenges!")
    async def sbc_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await refresh_sbcs_if_needed()
        active = await get_active_sbcs()

        if not active:
            return await interaction.followup.send("❌ No active SBCs right now. Check back soon!")

        # Check which ones user already completed
        user_id = interaction.user.id
        p = await database.get_db()
        rows = await p.fetch('SELECT sbc_id FROM sbc_completions WHERE user_id = $1', user_id)
        completed_ids = [row['sbc_id'] for row in rows]

        lines = []
        for sbc_id, sbc_data, expires_at in active:
            remaining = max(0, expires_at - int(time.time()))
            hours = remaining // 3600
            mins = (remaining % 3600) // 60
            status = "✅ Completed" if sbc_id in completed_ids else f"⏰ {hours}h {mins}m left"

            rule_lines = []
            for rule in sbc_data["rules"]:
                if rule["type"] == "min_avg_ovr":
                    rule_lines.append(f"  • Min Average OVR: {rule['value']}")
                elif rule["type"] == "min_nations":
                    rule_lines.append(f"  • At least {rule['value']} different nations")
                elif rule["type"] == "min_ovr_cards":
                    rule_lines.append(f"  • At least {rule['value']} cards rated {rule['min_ovr']}+")
                elif rule["type"] == "min_league_keyword":
                    rule_lines.append(f"  • At least {rule['value']} {rule['keyword']} players")

            lines.append(
                f"**{sbc_data['name']}** (ID: {sbc_id})\n"
                f"{sbc_data['description']}\n"
                f"📋 Submit **{sbc_data['card_count']}** players:\n" +
                "\n".join(rule_lines) +
                f"\n🎁 Reward: {sbc_data['reward_label']}\n{status}\n"
            )

        embed = discord.Embed(
            title="🧩 Squad Building Challenges",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Use /sbc_submit <id> to complete a challenge!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="sbc_submit", description="Submit cards to complete an SBC!")
    async def sbc_submit(self, interaction: discord.Interaction, sbc_id: int):
        await interaction.response.defer()
        user_id = interaction.user.id

        # Get the SBC
        active = await get_active_sbcs()
        target_sbc = None
        for sid, sdata, exp in active:
            if sid == sbc_id:
                target_sbc = sdata
                break

        if not target_sbc:
            return await interaction.followup.send("❌ That SBC doesn't exist or has expired.")

        # Check if already completed
        p = await database.get_db()
        already = await p.fetchval('SELECT 1 FROM sbc_completions WHERE user_id = $1 AND sbc_id = $2', user_id, sbc_id)
        if already:
            return await interaction.followup.send("❌ You've already completed this SBC!")

        # Get user inventory (exclude squad-locked players)
        inventory = await database.get_inventory(user_id)
        locked_ids = await database.get_squad_locked_ids(user_id)
        inventory = [row for row in inventory if int(row.get('id', -1)) not in locked_ids and not row.get('locked', 0)]
        selected, error = check_submission(inventory, target_sbc)

        if error:
            return await interaction.followup.send(f"❌ {error}")

        # Show preview
        avg_ovr = sum(c.get('ovr', 0) for c in selected) / len(selected)
        card_names = [f"{c.get('player_name', '?')} `({extract_pos(c)})` ({c.get('ovr', '?')})" for c in selected[:5]]
        preview = ", ".join(card_names)
        if len(selected) > 5:
            preview += f" ...and {len(selected) - 5} more"

        # Delete the cards
        ids_to_delete = [c['id'] for c in selected]
        await database.remove_players_from_inventory(user_id, ids_to_delete)

        # Generate reward
        from renderz_api import query_players_by_program
        reward_ovr = random.randint(target_sbc["reward_min"], target_sbc["reward_max"])
        players = query_players_by_program("", min_rating=reward_ovr, max_rating=reward_ovr, size=50)
        if not players:
            players = query_players_by_program("PROGRAM_ICONS", min_rating=reward_ovr, max_rating=reward_ovr, size=10)

        reward_card = random.choice(players) if players else None

        if reward_card:
            await database.add_player_to_inventory(user_id, reward_card)
            rname = reward_card.get('cardName', 'Unknown')
            rovr = reward_card.get('rating', '?')
            rpos = reward_card.get('position', '??')

        # Mark completed
        await p.execute('INSERT INTO sbc_completions (user_id, sbc_id, completed_at) VALUES ($1, $2, $3) ON CONFLICT (user_id, sbc_id) DO NOTHING',
                         user_id, sbc_id, int(time.time()))

        # Track stat for achievements
        try:
            from cogs.achievements import increment_stat, check_and_award
            await increment_stat(user_id, "sbcs_done")
            await check_and_award(user_id)
        except:
            pass

        # Season XP
        try:
            from cogs.season import add_season_xp
            await add_season_xp(user_id, 150)
        except:
            pass

        embed = discord.Embed(
            title=f"🧩 SBC Complete — {target_sbc['name']}!",
            description=f"**Sacrificed:** {len(selected)} cards (avg {avg_ovr:.1f} OVR)\n{preview}\n\n"
                        f"**Reward:** {'**' + rname + '** `(' + rpos + ')` (' + str(rovr) + ' OVR)' if reward_card else 'Card reward failed'}",
            color=discord.Color.green()
        )

        # Try to generate card image
        try:
            from card_generator import generate_card, save_card_to_bytes
            is_anim = (isinstance(rovr, int) and rovr >= 120)
            card_result = await asyncio.to_thread(generate_card, reward_card, 4, is_anim)
            image_binary, filename = save_card_to_bytes(card_result)
            file = discord.File(fp=image_binary, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(embed=embed, file=file)
        except:
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(SBCCog(bot))
