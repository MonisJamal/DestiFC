import discord
from discord.ext import commands
from discord import app_commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Learn how to play DestiFC and view all available commands!")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="⚽ DestiFC — Official Command Center",
            description="Welcome to **DestiFC**, the premier FC Mobile simulation experience on Discord! Build your ultimate squad, open walkout packs, and dominate Division Rivals.",
            color=0x1E90FF
        )
        
        embed.add_field(name="📦 Packs, Drafts & Exchanges", value=(
            "`> /starterpack` — 🎁 Claim your one-time 300 Million Coins & Starter Squad!\n"
            "`> /draft [pack] [amount]` — 🌟 Open active Draft Packs (Dynamic rotating walkout pools!)\n"
            "`> /draft_info <pack>` — 🔍 View featured superstars, odds, and pool expiry timers\n"
            "`> /exchange` — ⚡ Sacrifice lower-tier cards for a **Guaranteed 120+ Walkout**!\n"
            "`> /signature_box draw` — 🎁 Exclusive 10-Reward Signature Box draw\n"
        ), inline=False)

        embed.add_field(name="🛡️ Squad Management & 3D Pitch", value=(
            "`> /squad view [user]` — 🏟️ Render high-definition 3D stadium pitch lineup of your Starting 11!\n"
            "`> /squad set <pos> <player>` — 📌 Place player into starting squad (Supports main & alternate positions at 100% OVR!)\n"
            "`> /squad autobuild` — ⚡ Auto-equip highest OVR cards into optimal formation slots!\n"
            "`> /squad formation <name>` — 📐 Choose from 34 tactical formations (e.g. 4-3-3, 4-1-2-1-2, 3-5-2)\n"
            "`> /squad tactic <tactic>` — 🧠 Set team playstyle for tactical synergy boosts!\n"
            "`> /squad lock <id>` — 🔒 Lock a player to protect from quicksell, market, or exchange\n"
            "`> /inventory [user]` — 🃏 Browse your or another player's club card collection\n"
        ), inline=False)
        
        embed.add_field(name="⚔️ Head-to-Head Matches & Draft Battles", value=(
            "`> /play <user>` — 🎮 Challenge another player to live Division Rivals with tactical simulation!\n"
            "`> /draftbattle challenge <user> [wager]` — 🏆 Live 1v1 FUT Draft tournament match with live card picks!\n"
            "`> /draftbattle leaderboard` — 👑 Global Draft Champions ranked by ELO & points\n"
            "`> /leaderboard [type]` — 🌍 View Global Leaderboards (Fans, Coins, or Vouchers)\n"
        ), inline=False)

        embed.add_field(name="🌍 Transfer Market, QuickSell & Trading", value=(
            "`> /market search` — 🔎 Search global listings by OVR, position, or name\n"
            "`> /market buy <id>` — 🛒 Purchase a player card from the market\n"
            "`> /market sell [id] [price]` — 🏷️ List card (or open paginated interactive sell menu)\n"
            "`> /market sell_menu` — 📋 Interactive dropdown menu with page browsing to list cards\n"
            "`> /quicksell [id]` — 🪙 Instantly sell a card for 70% min market value\n"
            "`> /quicksell_bulk <max_ovr>` — 🪙 Bulk quicksell low OVR cards at once\n"
            "`> /trade send <user>` — 🤝 Trade cards, coins & vouchers directly with another user\n"
        ), inline=False)

        embed.add_field(name="🏪 Store, Season Pass & Club Records", value=(
            "`> /store players` — 🛒 Rotating direct player store with prime superstars & icons\n"
            "`> /store themes` — 🎨 Unlock custom 3D stadium pitch visual themes\n"
            "`> /season` — 🎖️ Progress through Season Pass milestones for exclusive rewards\n"
            "`> /sbc` — 🧩 Solve daily Squad Building Challenges\n"
            "`> /club_stats` (or `/stats`) — 📊 View club performance leaders (Golden Boot, Assists, Ratings)\n"
            "`> /player_stats <player>` — 📈 View lifetime match statistics of an individual player\n"
        ), inline=False)

        embed.add_field(name="🪙 Economy, Minigames & Balance", value=(
            "`> /daily` — ☀️ Claim daily coins & vouchers with 15% jackpot chance\n"
            "`> /work` — 💼 Complete mini-shifts for quick coin rewards\n"
            "`> /penalty`, `/freekick`, `/dribble` — 🎯 Skill games to earn free coins & vouchers\n"
            "`> /balance [user]` — 💰 Check your or another user's Coins & Vouchers balance\n"
            "`> /privacy` — 🔒 Toggle private/public profile & squad visibility\n"
        ), inline=False)
        
        embed.add_field(name="💬 Community & Support", value=(
            "Join the official DestiFC Support Server for bot updates, announcements, giveaways, and help:\n"
            "🔗 [Join DestiFC Support Server](https://discord.gg/wSMWDyscQY)\n"
        ), inline=False)
        
        embed.set_footer(text="DestiFC • Type /guide for the complete gameplay walkthrough!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="guide", description="Complete Master Guide: How to master DestiFC, build your squad & earn vouchers!")
    async def guide_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="📖 DestiFC — Official Master Gameplay Guide",
            description="Welcome to **DestiFC**! This master handbook covers everything from opening your first walkout packs to building a champion Starting 11.",
            color=0x00FF88
        )

        embed.add_field(
            name="1️⃣ Getting Started & Daily Progression",
            value=(
                "• `/starterpack` — Claim your **300 Million Coins** and an instant 11-player Starter Squad!\n"
                "• `/daily` — Claim daily coins with a **15% jackpot bonus**.\n"
                "• `/work` — Take quick hourly job shifts to earn extra coins.\n"
                "• `/season` — Earn XP from matches to unlock high-tier Season Pass cards."
            ),
            inline=False
        )

        embed.add_field(
            name="2️⃣ Opening Packs & The Dynamic Draft Rotator",
            value=(
                "• `/draft` — Open Standard, Premium, or Ultimate Draft packs!\n"
                "• **Pity Counter**: Every 10 packs guarantees an Elite/Pool B pull, and 60 packs guarantees a **Featured Pool A Walkout** (120+ OVR).\n"
                "• **Dynamic Pool Rotation**: Draft pools automatically rotate every few hours featuring rotating superstars and icons!\n"
                "• `/draft_info` — View currently featured walkout cards, probabilities, and expiration timers."
            ),
            inline=False
        )

        embed.add_field(
            name="3️⃣ Building Your Squad & Alternate Positions",
            value=(
                "• `/squad formation <name>` — Pick from 34 formations (e.g. `4-3-3 Attack`, `4-1-2-1-2 Narrow`, `3-5-2`).\n"
                "• `/squad set <pos> <player>` — Place any card into your lineup. **Players can play in their primary position OR any natural/official alternate position at 100% full OVR!**\n"
                "• `/squad autobuild` — One-click automatic optimization that places your highest OVR cards into your formation.\n"
                "• `/squad tactic <tactic>` — Set playstyle tactics (Tiki-Taka, Gegenpressing, Counter-Attack, etc.) for synergy boosts in matches!\n"
                "• `/squad view` — Render a high-resolution 3D stadium pitch showing your complete squad."
            ),
            inline=False
        )

        embed.add_field(
            name="4️⃣ Head-to-Head & 1v1 FUT Draft Battles",
            value=(
                "• `/play @user` — Challenge another user to a Division Rivals ranked match. Watch live tactical play-by-play commentary and earn Fans & Coins!\n"
                "• `/draftbattle challenge @user [wager]` — Live 1v1 Draft Tournament. Pick cards slot-by-slot, manage chemistry, and battle for the coin pot!\n"
                "• `/leaderboard` & `/draftbattle leaderboard` — Climb from Amateur to FC Champion ELO."
            ),
            inline=False
        )

        embed.add_field(
            name="5️⃣ Transfer Market, QuickSell & Exchanges",
            value=(
                "• `/market sell_menu` — Open the interactive dropdown menu with page browsing to list club cards at min, max, or custom prices.\n"
                "• `/market search` & `/market buy <id>` — Browse global listings and buy cards with coins.\n"
                "• `/quicksell [id]` & `/quicksell_bulk` — Instantly liquidate duplicate or unused cards for coins.\n"
                "• `/exchange` — Sacrifice lower-tier cards to craft guaranteed 120+ Walkout superstars!"
            ),
            inline=False
        )

        embed.add_field(
            name="6️⃣ Minigames & Skill Training",
            value=(
                "Earn free **Draft Vouchers** and Coins through interactive minigames:\n"
                "• `/penalty` — 3-zone penalty shootout (pick your spot, read the keeper's dive!)\n"
                "• `/freekick` — Whipped curlers, knuckleballs, and low-driven free kicks.\n"
                "• `/dribble` — Reflex obstacle course past defenders.\n"
                "• `/trivia` — Football trivia challenges with huge cash rewards."
            ),
            inline=False
        )

        embed.set_footer(text="DestiFC Official Guide • Support: https://discord.gg/wSMWDyscQY")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
