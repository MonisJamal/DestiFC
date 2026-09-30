import discord
from discord.ext import commands
from discord import app_commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Learn how to play DestiFC!")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="⚽ Welcome to DestiFC!",
            description="The ultimate FC Mobile Discord Bot! Build your dream squad, open massive packs, and dominate Division Rivals.",
            color=0x1E90FF
        )
        
        embed.add_field(name="📦 Packs & Drafts", value="""
`> /starterpack` - 🎁 Claim your one-time 300 Million Coins & Starter Squad!
`> /draft` - Open active Draft Packs (pools rotate every 2 hours!)
`> /draft_info` - See which players are featured in each draft
`> /exchange` - Trade 25 unwanted cards for a Guaranteed 120+ Walkout!
        """, inline=False)
        
        embed.add_field(name="⚔️ FC Draft Battles 1v1 (New!)", value="""
`> /draftbattle challenge <user> [wager]` - 🎮 Challenge a player to a live 1v1 FUT Draft match with 110+ OVR cards!
`> /draftbattle leaderboard` - 👑 View Global Draft Champions ranked by ELO & Points!
`> /draftbattle stats [user]` - 📊 Check Draft Battle win/loss record and rank division.
        """, inline=False)

        embed.add_field(name="🌍 Transfer Market & Quick Sell", value="""
`> /market search` - Search players by OVR, position, or name
`> /market buy <id>` - Buy a player listed on the market using Coins
`> /market sell [id] [price]` - List a player (or leave blank for dropdown menu)
`> /market sell_page` - Bulk list all cards on a page at min price
`> /quicksell [id]` - 🪙 Instantly sell a card for 70% min market value
`> /quicksell_bulk <max_ovr>` - 🪙 Bulk quicksell low cards (e.g. `<= 116`)
`> /trade send <user>` - 🤝 Trade cards, coins & vouchers directly with another user!
        """, inline=False)

        embed.add_field(name="🛡️ Squad & Themes", value="""
`> /squad autobuild` - ⚡ Auto-fill your squad with your highest OVR players!
`> /squad view [user]` - Generate 3D stadium pitch lineup of your or another user's Starting 11!
`> /squad lock <id>` - 🔒 Lock a player to protect from exchange/SBC/quicksell
`> /inventory [user]` - View your or another user's club cards
`> /store themes` - Buy epic custom 3D stadium pitches
`> /squad theme <id>` - Equip an unlocked pitch theme
        """, inline=False)
        
        embed.add_field(name="🏆 Economy, Rivals & Pass", value="""
`> /play <user>` - Challenge a friend to Live H2H! (Win = +10M Coins, +1 Voucher, +10k Fans)
`> /leaderboard [type]` - 🌍 View Global Leaderboards for Fans, Coins, or Vouchers!
`> /daily` - Claim daily coins & 15% jackpot chance
`> /season` - View Season Pass tiers and claim rewards
`> /sbc` - Complete daily Squad Building Challenges
`> /badges` - View your unlocked achievement badges
`> /balance [user]` - Check your or another user's balance
`> /privacy` - Toggle private/public profile & inventory
        """, inline=False)
        
        embed.add_field(name="💬 Community & Support", value="""
Join the official DestiFC Support Server for updates, pack flex, giveaways, and reporting issues:
🔗 [Join DestiFC Support Server](https://discord.gg/wSMWDyscQY)
        """, inline=False)
        
        embed.set_footer(text="Developed for FC Mobile Fans | Support: https://discord.gg/wSMWDyscQY")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="guide", description="Complete Master Guide: How to master DestiFC, build your squad & earn vouchers!")
    async def guide_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="📖 DestiFC — Official Master Guide & Handbook",
            description="Welcome to **DestiFC**, the premier FC Mobile simulation experience on Discord! Here is everything you need to know from starter packs to dominating Division Rivals.",
            color=0x00FF88
        )

        embed.add_field(
            name="1️⃣ Getting Started",
            value=(
                "• `/starterpack` — Claim **300 Million Coins** and an instant 11-player Starter Squad!\n"
                "• `/daily` — Claim your daily coins + **15% jackpot chance**.\n"
                "• `/balance` — Check your Coins and Draft Vouchers.\n"
                "• `/season` — Track your Season Pass milestones and claim bonus rewards."
            ),
            inline=False
        )

        embed.add_field(
            name="2️⃣ 1v1 FUT Draft Battles",
            value=(
                "• `/draftbattle challenge @user [wager]` — Enter live draft battle with 110+ OVR cards.\n"
                "• Pick formations, select superstars, gain Chemistry boosts, and simulate 90-minute matches!\n"
                "• `/draftbattle leaderboard` — Climb from Division IV to Elite Draft Champion ELO."
            ),
            inline=False
        )

        embed.add_field(
            name="3️⃣ Drafts, Packs & The 2-Hour Rotator",
            value=(
                "• `/draft` — Open Standard (10M), Premium (50M), or Ultimate Draft (1 Voucher) packs!\n"
                "• **Pity System**: Every 10–15 packs guarantees a top **Pool A Walkout** (120–122 OVR).\n"
                "• **2-Hour Pool Rotations**: Draft pools rotate every 2 hours featuring different 120–122 superstars across all 357 top cards!\n"
                "• `/draft_info` — Inspect currently featured event players and probabilities."
            ),
            inline=False
        )

        embed.add_field(
            name="4️⃣ Skill Games — Earn Free Vouchers & Coins",
            value=(
                "Play interactive minigames with cooldowns to earn free **Draft Vouchers** & Millions of Coins:\n"
                "• `/penalty` — Classic penalty shootout (Aim Top/Bottom Corners, guess the keeper's dive!)\n"
                "• `/freekick` — Curve the ball past defensive walls & beat the keeper!\n"
                "• `/dribble` — 3-lane reflex rush past defenders!\n"
                "• `/trivia` — AI football & FC Mobile trivia for huge coin bonuses!\n"
                "• `/passmaster` & `/crossvolley` — Timing & sequence drills for quick vouchers!"
            ),
            inline=False
        )

        embed.add_field(
            name="5️⃣ Squads, 34 Formations & 3D Pitch View",
            value=(
                "• `/squad formation <name>` — Choose from 34 tactical setups (e.g. `4-1-2-1-2 Narrow`, `4-3-3 Attack`, `3-5-2`, `5-2-1-2`).\n"
                "• `/squad autobuild` — Automatically place your highest OVR cards into optimal positions!\n"
                "• `/squad view [user]` — Render a photorealistic 3D holographic stadium pitch with transparent cards!\n"
                "• `/squad lock <id>` — Lock your favorite cards so they cannot be accidentally quicksold or exchanged.\n"
                "• `/store themes` & `/squad theme <id>` — Unlock snow, lava, cyberpunk, galaxy, gold, and desert pitches!"
            ),
            inline=False
        )

        embed.add_field(
            name="6️⃣ Exchanges, SBCs & 4-Hour Player Store",
            value=(
                "• `/exchange` — Trade **25 unwanted cards** (100–119 OVR) for a **Guaranteed 120–122 Walkout**!\n"
                "• `/sbc` — Solve daily squad challenges for coins, vouchers, and exclusive packs.\n"
                "• `/store players` — Direct 4-hour shop featuring 3 rotating 120–122 Prime Icons/Superstars!\n"
                "• `/market` — Buy and list players on the global user transfer market.\n"
                "• `/quicksell` & `/quicksell_bulk` — Instantly cash in cards at 70% market value."
            ),
            inline=False
        )

        embed.set_footer(text="DestiFC Guide | Need help? Join https://discord.gg/wSMWDyscQY")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
