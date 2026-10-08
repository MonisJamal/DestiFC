import discord
from discord.ext import commands, tasks
from discord import app_commands
import database
import json
import time
import random

# Season Pass Rewards (Advanced Integration)
SEASON_REWARDS = {
    1:  {"coins": 12_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 12,000,000 Coins"},
    2:  {"coins": 0,           "vouchers": 5,  "fans": 5000,   "desc": "🎟️ 5 Draft Vouchers + 🏆 5,000 Fans (Rivals Points)"},
    3:  {"coins": 15_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 15,000,000 Coins"},
    4:  {"coins": 0,           "vouchers": 8,  "fans": 10000,  "desc": "🎟️ 8 Draft Vouchers + 🏆 10,000 Fans"},
    5:  {"coins": 20_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🃏 Guaranteed 110+ Player + 🪙 20M Coins", "card_reward": 110},
    6:  {"coins": 30_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 30,000,000 Coins"},
    7:  {"coins": 0,           "vouchers": 10, "fans": 15000,  "desc": "🎟️ 10 Draft Vouchers + 🏆 15,000 Fans"},
    8:  {"coins": 40_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 40,000,000 Coins"},
    9:  {"coins": 0,           "vouchers": 12, "fans": 20000,  "desc": "🎟️ 12 Draft Vouchers + 🏆 20,000 Fans"},
    10: {"coins": 50_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🃏 Guaranteed 114+ Player + 🪙 50M Coins", "card_reward": 114},
    11: {"coins": 60_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 60,000,000 Coins"},
    12: {"coins": 0,           "vouchers": 15, "fans": 30000,  "desc": "🎟️ 15 Draft Vouchers + 🏆 30,000 Fans + Badge: ⭐ Season Grinder", "badge": "season_grinder"},
    13: {"coins": 70_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 70,000,000 Coins"},
    14: {"coins": 0,           "vouchers": 20, "fans": 40000,  "desc": "🎟️ 20 Draft Vouchers + 🏆 40,000 Fans"},
    15: {"coins": 80_000_000,  "vouchers": 0,  "fans": 0,      "desc": "✨ RARE CUSTOM DRAFT CARD + 🪙 80M Coins", "custom_card": True},
    16: {"coins": 90_000_000,  "vouchers": 0,  "fans": 0,      "desc": "🪙 90,000,000 Coins"},
    17: {"coins": 0,           "vouchers": 25, "fans": 50000,  "desc": "🎟️ 25 Draft Vouchers + 🏆 50,000 Fans"},
    18: {"coins": 100_000_000, "vouchers": 0,  "fans": 0,      "desc": "🪙 100,000,000 Coins"},
    19: {"coins": 0,           "vouchers": 30, "fans": 60000,  "desc": "🎟️ 30 Draft Vouchers + 🏆 60,000 Fans"},
    20: {"coins": 120_000_000, "vouchers": 0,  "fans": 0,      "desc": "🃏 Guaranteed 118+ Player + 🪙 120M Coins + Badge: 🏅 Season Veteran", "badge": "season_veteran", "card_reward": 118},
    21: {"coins": 150_000_000, "vouchers": 0,  "fans": 80000,  "desc": "🪙 150,000,000 Coins + 🏆 80,000 Fans"},
    22: {"coins": 0,           "vouchers": 35, "fans": 100000, "desc": "🎟️ 35 Draft Vouchers + 🏆 100,000 Fans (Guaranteed Rank Up)"},
    23: {"coins": 200_000_000, "vouchers": 0,  "fans": 0,      "desc": "🪙 200,000,000 Coins"},
    24: {"coins": 0,           "vouchers": 50, "fans": 150000, "desc": "🎟️ 50 Draft Vouchers + 🏆 150,000 Fans"},
    25: {"coins": 250_000_000, "vouchers": 0,  "fans": 200000, "desc": "✨ RARE CUSTOM DRAFT CARD + 🪙 250M Coins + 🏆 200K Fans + 👑 Season Champion", "badge": "season_champion", "custom_card": True},
}

async def fetch_season_config():
    config = await database.get_season_config()
    if not config:
        return {
            "season_number": 1,
            "season_title": "Star Pass",
            "xp_per_tier": 1000,
            "tiers_count": 25,
            "tiers": [
                {"tier": k, "reward_type": "coins" if v["coins"] > 0 else "vouchers" if v["vouchers"] > 0 else "card", 
                 "reward_value": v["coins"] or v["vouchers"] or 1, "reward_name": v["desc"]}
                for k, v in SEASON_REWARDS.items()
            ]
        }
    return config


async def ensure_season_table(db=None):
    p = await database.get_db()
    await p.execute('''
        CREATE TABLE IF NOT EXISTS season_pass (
            user_id BIGINT PRIMARY KEY,
            season_id INTEGER DEFAULT 1,
            xp BIGINT DEFAULT 0,
            claimed_tiers TEXT DEFAULT '[]',
            started_at BIGINT DEFAULT 0
        );
    ''')


async def get_season_data(user_id):
    p = await database.get_db()
    await p.execute('INSERT INTO season_pass (user_id, started_at) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING', user_id, int(time.time()))
    row = await p.fetchrow('SELECT user_id, season_id, xp, claimed_tiers, started_at FROM season_pass WHERE user_id = $1', user_id)
    if row:
        ct = row['claimed_tiers']
        return {
            "user_id": row['user_id'], "season_id": row['season_id'], "xp": row['xp'],
            "claimed_tiers": json.loads(ct) if isinstance(ct, str) else ct, "started_at": row['started_at']
        }
    return None


async def add_season_xp(user_id, amount):
    p = await database.get_db()
    await p.execute('INSERT INTO season_pass (user_id, started_at) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING', user_id, int(time.time()))
    await p.execute('UPDATE season_pass SET xp = xp + $1 WHERE user_id = $2', amount, user_id)


def get_current_tier(xp, config):
    return min(xp // config.get('xp_per_tier', 500), config.get('tiers_count', 10))


def xp_for_next_tier(xp, config):
    current = get_current_tier(xp, config)
    if current >= config.get('tiers_count', 10):
        return 0
    return ((current + 1) * config.get('xp_per_tier', 500)) - xp


class SeasonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.season_reset_loop.start()

    def cog_unload(self):
        self.season_reset_loop.cancel()

    @tasks.loop(hours=1)
    async def season_reset_loop(self):
        """Check if any user's season has expired (10 days) and reset them."""
        p = await database.get_db()
        cutoff = int(time.time()) - (10 * 86400)  # 10 days ago
        await p.execute('UPDATE season_pass SET xp = 0, claimed_tiers = $1, season_id = season_id + 1, started_at = $2 WHERE started_at < $3 AND started_at > 0',
                         '[]', int(time.time()), cutoff)

    @season_reset_loop.before_loop
    async def before_reset(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="season", description="View your Season Pass progress and claim rewards!")
    async def season(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        data = await get_season_data(user_id)
        config = await fetch_season_config()
        if not data:
            return await interaction.followup.send("❌ Could not load season data.")

        xp = data["xp"]
        current_tier = get_current_tier(xp, config)
        claimed = data["claimed_tiers"]

        # Calculate time remaining
        elapsed = int(time.time()) - data["started_at"]
        remaining_secs = max(0, (10 * 86400) - elapsed)
        days_left = remaining_secs // 86400
        hours_left = (remaining_secs % 86400) // 3600

        # Build progress bar
        xp_per_tier = config.get("xp_per_tier", 500)
        tiers_count = config.get("tiers_count", 10)
        
        progress_pct = (xp % xp_per_tier) / xp_per_tier if current_tier < tiers_count else 1.0
        filled = int(progress_pct * 20)
        bar = "█" * filled + "░" * (20 - filled)

        lines = []
        for t_data in config.get("tiers", []):
            tier_num = t_data["tier"]
            if tier_num in claimed:
                status = "✅"
            elif tier_num <= current_tier:
                status = "🟡"  # Available to claim
            else:
                status = "🔒"
            lines.append(f"{status} **Tier {tier_num}** — {t_data.get('reward_name', 'Reward')}")

        embed = discord.Embed(
            title=f"🎫 {config.get('season_title', 'Season Pass')} (Season #{data['season_id']})",
            description=f"**XP:** {xp} / {(current_tier + 1) * xp_per_tier if current_tier < tiers_count else 'MAX'}\n"
                        f"**Progress:** [{bar}]\n"
                        f"**Current Tier:** {current_tier}/{tiers_count}\n"
                        f"⏰ **Resets in:** {days_left}d {hours_left}h\n\n" +
                        "\n".join(lines),
            color=discord.Color.purple()
        )
        embed.set_footer(text="🟡 = Ready to claim! Use /season_claim <tier>")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="season_claim", description="Claim a Season Pass tier reward!")
    async def season_claim(self, interaction: discord.Interaction, tier: int):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        config = await fetch_season_config()
        tiers_count = config.get("tiers_count", 10)

        if tier < 1 or tier > tiers_count:
            return await interaction.followup.send(f"❌ Tier must be between 1 and {tiers_count}.")

        data = await get_season_data(user_id)
        current_tier = get_current_tier(data["xp"], config)
        claimed = data["claimed_tiers"]

        if tier > current_tier:
            return await interaction.followup.send(f"❌ You haven't reached Tier {tier} yet! You're at Tier {current_tier}.")

        if tier in claimed:
            return await interaction.followup.send(f"❌ You already claimed Tier {tier}!")

        reward = SEASON_REWARDS[tier]

        # Give coins
        if reward["coins"] > 0:
            await database.add_coins(user_id, reward["coins"])

        # Give vouchers
        if reward["vouchers"] > 0:
            await database.add_vouchers(user_id, reward["vouchers"])

        # Give badge
        if "badge" in reward:
            from cogs.achievements import try_award, ACHIEVEMENTS
            # Add season badges to achievements dynamically
            season_badges = {
                "season_grinder":  {"emoji": "⭐", "name": "Season Grinder",   "desc": "Reach Tier 5 in a Season Pass", "coins": 0},
                "season_veteran":  {"emoji": "🏅", "name": "Season Veteran",   "desc": "Reach Tier 9 in a Season Pass", "coins": 0},
                "season_champion": {"emoji": "👑", "name": "Season Champion",  "desc": "Complete a full Season Pass",   "coins": 0},
            }
            if reward["badge"] not in ACHIEVEMENTS:
                ACHIEVEMENTS[reward["badge"]] = season_badges.get(reward["badge"], {})
            await try_award(user_id, reward["badge"])

        # Fans
        if reward.get("fans", 0) > 0:
            await database.add_fans(user_id, reward["fans"])

        card_name = None
        card_ovr = None
        custom_flag = False

        # Custom Card Reward
        if reward.get("custom_card"):
            custom_cards = await database.get_all_custom_draft_cards()
            if custom_cards:
                c_card = random.choice(custom_cards)
                await database.add_player_to_inventory(user_id, c_card)
                card_name = c_card.get('cardName') or c_card.get('player_name') or 'Unknown Custom Card'
                card_ovr = c_card.get('rating') or c_card.get('ovr') or 120
                custom_flag = True

        # Give specific player OVR for card rewards (if not a custom card, or custom card fallback failed)
        if reward.get("card_reward") or (reward.get("custom_card") and not custom_flag):
            from renderz_api import query_players_by_program
            ovr_req = reward.get("card_reward", 120)
            players = query_players_by_program("", min_rating=ovr_req, max_rating=120, size=50)
            if players:
                card = random.choice(players)
                await database.add_player_to_inventory(user_id, card)
                card_name = card.get('cardName', 'Unknown')
                card_ovr = card.get('rating', ovr_req)

        # Mark claimed
        claimed.append(tier)
        p = await database.get_db()
        await p.execute('UPDATE season_pass SET claimed_tiers = $1 WHERE user_id = $2', json.dumps(claimed), user_id)

        desc = f"**Tier {tier} Claimed!**\n{reward['desc']}"
        if card_name:
            if custom_flag:
                desc += f"\n\n✨ You unlocked a rare **CUSTOM CARD**: **{card_name} ({card_ovr})**!"
            else:
                desc += f"\n\n🃏 You received **{card_name} ({card_ovr})**!"

        embed = discord.Embed(title="🎫 Season Reward Claimed!", description=desc, color=discord.Color.green())
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(SeasonCog(bot))
