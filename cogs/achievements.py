import discord
from discord.ext import commands
from discord import app_commands
import database
import json

# All achievements defined here
ACHIEVEMENTS = {
    "first_steps":    {"emoji": "🐣", "name": "First Steps",       "desc": "Open your very first draft",         "coins": 2_000_000},
    "pack_opener":    {"emoji": "📦", "name": "Pack Opener",       "desc": "Open 50 drafts",                     "coins": 5_000_000},
    "pack_addict":    {"emoji": "🔥", "name": "Pack Addict",       "desc": "Open 200 drafts",                    "coins": 10_000_000},
    "diamond":        {"emoji": "💎", "name": "Diamond Collector",  "desc": "Own 100 cards at once",              "coins": 5_000_000},
    "walkout_king":   {"emoji": "👑", "name": "Walkout King",       "desc": "Pull 10 walkouts (120+)",            "coins": 15_000_000},
    "legendary_pull": {"emoji": "🌟", "name": "Legendary Pull",     "desc": "Pull a 122 OVR card",               "coins": 10_000_000},
    "warrior":        {"emoji": "⚔️", "name": "Warrior",            "desc": "Win 10 matches",                    "coins": 5_000_000},
    "gladiator":      {"emoji": "🗡️", "name": "Gladiator",          "desc": "Win 50 matches",                    "coins": 15_000_000},
    "market_shark":   {"emoji": "🏪", "name": "Market Shark",       "desc": "Buy 10 cards from market",          "coins": 3_000_000},
    "millionaire":    {"emoji": "💰", "name": "Millionaire",         "desc": "Have 50M+ coins at once",           "coins": 10_000_000},
    "fodder_lord":    {"emoji": "🗑️", "name": "Fodder Lord",        "desc": "Complete 10 exchanges",             "coins": 8_000_000},
    "sbc_master":     {"emoji": "🧩", "name": "SBC Master",          "desc": "Complete 20 SBCs",                  "coins": 20_000_000},
    "loyal_fan":      {"emoji": "📅", "name": "Loyal Fan",            "desc": "Claim /daily 7 days in a row",     "coins": 10_000_000},
    "full_squad":     {"emoji": "🎯", "name": "Full Squad",           "desc": "Fill all 11 slots in your squad",  "coins": 5_000_000},
}


async def ensure_tables(db=None):
    p = await database.get_db()
    await p.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            user_id BIGINT,
            badge_id TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, badge_id)
        );
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id BIGINT PRIMARY KEY,
            walkouts_pulled INTEGER DEFAULT 0,
            matches_won INTEGER DEFAULT 0,
            exchanges_done INTEGER DEFAULT 0,
            sbcs_done INTEGER DEFAULT 0,
            market_buys INTEGER DEFAULT 0,
            daily_streak INTEGER DEFAULT 0
        );
    ''')


async def get_user_badges(user_id):
    p = await database.get_db()
    rows = await p.fetch('SELECT badge_id FROM achievements WHERE user_id = $1', user_id)
    return [row['badge_id'] for row in rows]


async def get_user_stats(user_id):
    p = await database.get_db()
    await p.execute('INSERT INTO user_stats (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id)
    row = await p.fetchrow('SELECT * FROM user_stats WHERE user_id = $1', user_id)
    if row:
        return dict(row)
    return {}


async def increment_stat(user_id, stat_name, amount=1):
    p = await database.get_db()
    await p.execute('INSERT INTO user_stats (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id)
    # Whitelist valid column names to avoid SQL injection
    valid_cols = {"walkouts_pulled", "matches_won", "exchanges_done", "sbcs_done", "market_buys", "daily_streak"}
    if stat_name in valid_cols:
        await p.execute(f'UPDATE user_stats SET {stat_name} = COALESCE({stat_name}, 0) + $1 WHERE user_id = $2', amount, user_id)


async def try_award(user_id, badge_id):
    """Award a badge if not already earned. Returns the achievement dict if newly awarded, else None."""
    if badge_id not in ACHIEVEMENTS:
        return None
    p = await database.get_db()
    has_badge = await p.fetchval('SELECT 1 FROM achievements WHERE user_id = $1 AND badge_id = $2', user_id, badge_id)
    if has_badge:
        return None  # Already has it
        
    await p.execute('INSERT INTO achievements (user_id, badge_id) VALUES ($1, $2) ON CONFLICT (user_id, badge_id) DO NOTHING', user_id, badge_id)
    # Award coins
    reward = ACHIEVEMENTS[badge_id]["coins"]
    if reward > 0:
        await database.add_coins(user_id, reward)
    return ACHIEVEMENTS[badge_id]


async def check_and_award(user_id, channel=None):
    """Check all achievement conditions and award any that are met. Returns list of newly awarded."""
    newly_awarded = []

    user = await database.get_user(user_id)
    if not user:
        return newly_awarded

    stats = await get_user_stats(user_id)
    drafts = int(user.get('drafts_opened') or 0)
    coins = int(user.get('coins') or 0)

    # Draft-based
    if drafts >= 1:
        r = await try_award(user_id, "first_steps")
        if r: newly_awarded.append(r)
    if drafts >= 50:
        r = await try_award(user_id, "pack_opener")
        if r: newly_awarded.append(r)
    if drafts >= 200:
        r = await try_award(user_id, "pack_addict")
        if r: newly_awarded.append(r)

    # Inventory size
    inv_size = int(await database.get_inventory_size(user_id) or 0)
    if inv_size >= 100:
        r = await try_award(user_id, "diamond")
        if r: newly_awarded.append(r)

    # Coins
    if coins >= 50_000_000:
        r = await try_award(user_id, "millionaire")
        if r: newly_awarded.append(r)

    # Stats-based (with full null-safety)
    walkouts = int(stats.get('walkouts_pulled') or 0)
    matches_won = int(stats.get('matches_won') or 0)
    exchanges = int(stats.get('exchanges_done') or 0)
    sbcs = int(stats.get('sbcs_done') or 0)
    buys = int(stats.get('market_buys') or 0)
    streak = int(stats.get('daily_streak') or 0)

    if walkouts >= 10:
        r = await try_award(user_id, "walkout_king")
        if r: newly_awarded.append(r)
    if matches_won >= 10:
        r = await try_award(user_id, "warrior")
        if r: newly_awarded.append(r)
    if matches_won >= 50:
        r = await try_award(user_id, "gladiator")
        if r: newly_awarded.append(r)
    if exchanges >= 10:
        r = await try_award(user_id, "fodder_lord")
        if r: newly_awarded.append(r)
    if buys >= 10:
        r = await try_award(user_id, "market_shark")
        if r: newly_awarded.append(r)
    if sbcs >= 20:
        r = await try_award(user_id, "sbc_master")
        if r: newly_awarded.append(r)
    if streak >= 7:
        r = await try_award(user_id, "loyal_fan")
        if r: newly_awarded.append(r)

    return newly_awarded


async def retroactive_scan(bot):
    """Scan ALL existing users and award any achievements they already qualify for."""
    print("[Achievements] Running retroactive scan for existing users...")
    p = await database.get_db()
    users = await p.fetch('SELECT user_id, drafts_opened, coins FROM users')

    count = 0
    for row in users:
        uid = row['user_id']
        awarded = await check_and_award(uid)
        if awarded:
            count += len(awarded)

    print(f"[Achievements] Retroactive scan complete. Awarded {count} badges across {len(users)} users.")


class AchievementsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await retroactive_scan(self.bot)

    @app_commands.command(name="badges", description="View your unlocked achievement badges!")
    async def badges(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user
        user_badges = await get_user_badges(target.id)

        if not user_badges:
            if target == interaction.user:
                return await interaction.followup.send("You haven't unlocked any badges yet! Keep playing to earn them.", ephemeral=True)
            return await interaction.followup.send(f"{target.display_name} hasn't unlocked any badges yet.", ephemeral=True)

        badge_line = " ".join(ACHIEVEMENTS[b]["emoji"] for b in user_badges if b in ACHIEVEMENTS)
        desc_lines = []
        for b in user_badges:
            if b in ACHIEVEMENTS:
                a = ACHIEVEMENTS[b]
                desc_lines.append(f"{a['emoji']} **{a['name']}** — {a['desc']}")

        embed = discord.Embed(
            title=f"🏆 {target.display_name}'s Badges",
            description=badge_line + "\n\n" + "\n".join(desc_lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{len(user_badges)}/{len(ACHIEVEMENTS)} unlocked")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="achievements", description="View all available achievements and your progress!")
    async def achievements_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_badges = await get_user_badges(interaction.user.id)

        lines = []
        for bid, a in ACHIEVEMENTS.items():
            status = "✅" if bid in user_badges else "🔒"
            lines.append(f"{status} {a['emoji']} **{a['name']}** — {a['desc']} → 🪙 {a['coins']:,}")

        embed = discord.Embed(
            title="🏆 All Achievements",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{len(user_badges)}/{len(ACHIEVEMENTS)} unlocked")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))
