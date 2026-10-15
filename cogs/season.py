import discord
from discord.ext import commands, tasks
from discord import app_commands
import database
import json
import time
import random

# Season Pass Rewards (Balanced Inflation Scale)
SEASON_REWARDS = {
    1:  {"coins": 500_000_000,    "vouchers": 0,  "fans": 0, "desc": "🪙 500 Million Coins"},
    2:  {"coins": 0,              "vouchers": 25, "fans": 0, "desc": "🎟️ 25 Draft Vouchers"},
    3:  {"coins": 1_250_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 1.25 Billion Coins"},
    4:  {"coins": 0,              "vouchers": 50, "fans": 0, "desc": "🎟️ 50 Draft Vouchers"},
    5:  {"coins": 2_500_000_000,  "vouchers": 0,  "fans": 0, "desc": "🃏 Guaranteed 115+ Player + 🪙 2.5 Billion Coins", "card_reward": 115},
    6:  {"coins": 375_000_000,    "vouchers": 0,  "fans": 0, "desc": "🪙 375 Million Coins"},
    7:  {"coins": 0,              "vouchers": 8,  "fans": 0, "desc": "🎟️ 8 Draft Vouchers"},
    8:  {"coins": 500_000_000,    "vouchers": 0,  "fans": 0, "desc": "🪙 500 Million Coins"},
    9:  {"coins": 0,              "vouchers": 10, "fans": 0, "desc": "🎟️ 10 Draft Vouchers"},
    10: {"coins": 750_000_000,    "vouchers": 0,  "fans": 0, "desc": "🃏 Guaranteed 118+ Player + 🪙 750 Million Coins", "card_reward": 118},
    11: {"coins": 1_000_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 1 Billion Coins"},
    12: {"coins": 0,              "vouchers": 15, "fans": 0, "desc": "🎟️ 15 Draft Vouchers + Badge: ⭐ Season Grinder", "badge": "season_grinder"},
    13: {"coins": 1_250_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 1.25 Billion Coins"},
    14: {"coins": 0,              "vouchers": 20, "fans": 0, "desc": "🎟️ 20 Draft Vouchers"},
    15: {"coins": 1_500_000_000,  "vouchers": 0,  "fans": 0, "desc": "🃏 Guaranteed 120+ Player + 🪙 1.5 Billion Coins", "card_reward": 120},
    16: {"coins": 2_000_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 2 Billion Coins"},
    17: {"coins": 0,              "vouchers": 25, "fans": 0, "desc": "🎟️ 25 Draft Vouchers"},
    18: {"coins": 2_500_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 2.5 Billion Coins"},
    19: {"coins": 0,              "vouchers": 30, "fans": 0, "desc": "🎟️ 30 Draft Vouchers"},
    20: {"coins": 3_000_000_000,  "vouchers": 0,  "fans": 0, "desc": "🃏 Guaranteed 121+ Player + 🪙 3 Billion Coins + Badge: 🏅 Season Veteran", "badge": "season_veteran", "card_reward": 121},
    21: {"coins": 3_750_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 3.75 Billion Coins"},
    22: {"coins": 0,              "vouchers": 40, "fans": 0, "desc": "🎟️ 40 Draft Vouchers"},
    23: {"coins": 4_250_000_000,  "vouchers": 0,  "fans": 0, "desc": "🪙 4.25 Billion Coins"},
    24: {"coins": 0,              "vouchers": 50, "fans": 0, "desc": "🎟️ 50 Draft Vouchers"},
    25: {"coins": 5_000_000_000,  "vouchers": 0,  "fans": 0, "desc": "🃏 Guaranteed MAX 122+ Player + 🪙 5 Billion Coins + 👑 Season Champion", "badge": "season_champion", "card_reward": 122},
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
    return min(xp // config.get('xp_per_tier', 1000), config.get('tiers_count', 25))


def xp_for_next_tier(xp, config):
    current = get_current_tier(xp, config)
    if current >= config.get('tiers_count', 25):
        return 0
    return ((current + 1) * config.get('xp_per_tier', 1000)) - xp


class SeasonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.season_reset_loop.start()

    def cog_unload(self):
        self.season_reset_loop.cancel()

    @tasks.loop(hours=1)
    async def season_reset_loop(self):
        """Check if any user's season has expired (15 days) and reset them."""
        p = await database.get_db()
        cutoff = int(time.time()) - (15 * 86400)  # 15 days ago
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
        remaining_secs = max(0, (15 * 86400) - elapsed)
        days_left = remaining_secs // 86400
        hours_left = (remaining_secs % 86400) // 3600

        # Build progress bar
        xp_per_tier = config.get("xp_per_tier", 1000)
        tiers_count = config.get("tiers_count", 25)
        
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
        embed.set_footer(text="🟡 = Ready to claim! Use /season_claim <tier> or /season_claim_all")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="season_claim_all", description="Claim all unlocked and unclaimed Season Pass tier rewards at once!")
    async def season_claim_all(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id

        config = await fetch_season_config()
        tiers_count = config.get("tiers_count", 25)

        data = await get_season_data(user_id)
        current_tier = get_current_tier(data["xp"], config)
        claimed = set(data["claimed_tiers"])

        unclaimed_tiers = [t for t in range(1, min(current_tier, tiers_count) + 1) if t not in claimed]

        if not unclaimed_tiers:
            if current_tier == 0:
                return await interaction.followup.send("❌ You haven't reached Tier 1 yet! Earn Season XP by playing matches and opening packs.")
            return await interaction.followup.send(f"❌ You have no unclaimed Season Pass rewards! (Reached Tier {current_tier}/{tiers_count})")

        total_coins = 0
        total_vouchers = 0
        total_fans = 0
        awarded_badges = []
        cards_received = []

        from cogs.achievements import try_award, ACHIEVEMENTS
        season_badges = {
            "season_grinder":  {"emoji": "⭐", "name": "Season Grinder",   "desc": "Reach Tier 5 in a Season Pass", "coins": 0},
            "season_veteran":  {"emoji": "🏅", "name": "Season Veteran",   "desc": "Reach Tier 9 in a Season Pass", "coins": 0},
            "season_champion": {"emoji": "👑", "name": "Season Champion",  "desc": "Complete a full Season Pass",   "coins": 0},
        }

        custom_cards_pool = None

        for t in unclaimed_tiers:
            reward = SEASON_REWARDS.get(t)
            if not reward:
                continue

            total_coins += reward.get("coins", 0)
            total_vouchers += reward.get("vouchers", 0)
            total_fans += reward.get("fans", 0)

            if "badge" in reward:
                b_key = reward["badge"]
                if b_key not in ACHIEVEMENTS:
                    ACHIEVEMENTS[b_key] = season_badges.get(b_key, {})
                await try_award(user_id, b_key)
                b_info = season_badges.get(b_key, {})
                awarded_badges.append(f"{b_info.get('emoji', '🎖️')} {b_info.get('name', b_key)}")

            custom_flag = False
            card_name = None
            card_ovr = None

            if reward.get("custom_card"):
                if custom_cards_pool is None:
                    custom_cards_pool = await database.get_all_custom_draft_cards()
                if custom_cards_pool:
                    c_card = random.choice(custom_cards_pool)
                    await database.add_player_to_inventory(user_id, c_card)
                    card_name = c_card.get('cardName') or c_card.get('player_name') or 'Unknown Custom Card'
                    card_ovr = c_card.get('rating') or c_card.get('ovr') or 120
                    custom_flag = True

            if reward.get("card_reward") or (reward.get("custom_card") and not custom_flag):
                ovr_req = int(reward.get("card_reward", 120))
                players = await database.get_official_cards_by_rating(ovr_req, 125, 50)
                if not players:
                    try:
                        from renderz_api import query_players_by_program
                        players = query_players_by_program("", min_rating=ovr_req, max_rating=125, size=50)
                    except Exception as ex:
                        print(f"[Season] Error querying renderz_api fallback: {ex}")
                        players = []
                if players:
                    card = random.choice(players)
                    await database.add_player_to_inventory(user_id, card)
                    card_name = card.get('cardName') or card.get('lastName') or card.get('name') or f"Player ({ovr_req} OVR)"
                    card_ovr = card.get('rating') or card.get('ovr') or ovr_req

            if card_name:
                prefix = "✨ [CUSTOM]" if custom_flag else "🃏"
                cards_received.append(f"{prefix} **{card_name}** ({card_ovr} OVR)")

            claimed.add(t)

        if total_coins > 0:
            await database.add_coins(user_id, total_coins)
        if total_vouchers > 0:
            await database.add_vouchers(user_id, total_vouchers)
        if total_fans > 0:
            await database.add_fans(user_id, total_fans)

        claimed_list = sorted(list(claimed))
        p = await database.get_db()
        await p.execute('UPDATE season_pass SET claimed_tiers = $1 WHERE user_id = $2', json.dumps(claimed_list), user_id)

        tiers_str = ", ".join(f"Tier {t}" for t in unclaimed_tiers)
        if len(unclaimed_tiers) > 6:
            tiers_str = f"Tiers {unclaimed_tiers[0]} - {unclaimed_tiers[-1]} ({len(unclaimed_tiers)} tiers)"

        summary_lines = [
            f"Successfully claimed **{len(unclaimed_tiers)}** tiers ({tiers_str})!\n",
            f"**Total Rewards Received:**"
        ]
        if total_coins > 0:
            summary_lines.append(f"🪙 **{total_coins:,} Coins**")
        if total_vouchers > 0:
            summary_lines.append(f"🎟️ **{total_vouchers} Draft Vouchers**")
        if total_fans > 0:
            summary_lines.append(f"👥 **{total_fans:,} Fans**")
        if awarded_badges:
            summary_lines.append(f"🎖️ Badges: {', '.join(awarded_badges)}")
        if cards_received:
            summary_lines.append("\n**Players Unlocked:**")
            for c in cards_received:
                summary_lines.append(f"• {c}")

        embed = discord.Embed(
            title="🎫 Season Pass Rewards Claimed All!",
            description="\n".join(summary_lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Current Season Progress: Tier {current_tier}/{tiers_count}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="season_claim", description="Claim a Season Pass tier reward!")
    async def season_claim(self, interaction: discord.Interaction, tier: int):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        config = await fetch_season_config()
        tiers_count = config.get("tiers_count", 25)

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
            ovr_req = int(reward.get("card_reward", 120))
            players = await database.get_official_cards_by_rating(ovr_req, 125, 50)
            if not players:
                try:
                    from renderz_api import query_players_by_program
                    players = query_players_by_program("", min_rating=ovr_req, max_rating=125, size=50)
                except Exception as ex:
                    print(f"[Season] Error querying renderz_api fallback: {ex}")
                    players = []
            if players:
                card = random.choice(players)
                await database.add_player_to_inventory(user_id, card)
                card_name = card.get('cardName') or card.get('lastName') or card.get('name') or f"Player ({ovr_req} OVR)"
                card_ovr = card.get('rating') or card.get('ovr') or ovr_req

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
