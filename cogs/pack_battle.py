import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio
import time
from card_generator import get_or_create_card_bytes

class PackBattleChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, vouchers: int, pack_num: int, cog):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.vouchers = vouchers
        self.pack_num = pack_num
        self.cog = cog

    @discord.ui.button(label="Accept Pack Battle ⚔️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ Only the challenged player can accept!", ephemeral=True)
        
        user_a = await database.get_user(self.challenger.id)
        user_b = await database.get_user(self.opponent.id)
        if user_a.get('vouchers', 0) < self.vouchers:
            return await interaction.response.send_message(f"❌ {self.challenger.mention} no longer has **{self.vouchers}** Draft Vouchers!", ephemeral=True)
        if user_b.get('vouchers', 0) < self.vouchers:
            return await interaction.response.send_message(f"❌ You do not have **{self.vouchers}** Draft Vouchers!", ephemeral=True)
        
        self.stop()
        await interaction.response.defer()
        await self.cog.execute_pack_battle(interaction, self.challenger, self.opponent, self.vouchers, self.pack_num)

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id and interaction.user.id != self.challenger.id:
            return await interaction.response.send_message("❌ You are not part of this battle.", ephemeral=True)
        self.stop()
        embed = discord.Embed(
            title="🚫 Pack Battle Declined",
            description=f"{interaction.user.mention} declined the pack battle challenge.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class PackBattleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _roll_pack(self, draft_dict, count: int, luck: dict = None):
        pulled = []
        highest_card = None
        highest_ovr = 0
        pool_a = draft_dict.get('pool_a', [])
        pool_b = draft_dict.get('pool_b', [])
        pool_c = draft_dict.get('pool_c', [])

        luck = luck or {}
        mult = max(0.1, float(luck.get("global_luck_multiplier", 1.0) or 1.0))
        pool_a_rate = min(99.0, max(0.1, float(luck.get("draft_pool_a_rate", 2.5) or 2.5) * mult))
        pool_b_rate = min(99.0, max(0.1, float(luck.get("draft_pool_b_rate", 30.0) or 30.0) * mult))
        cutoff_a = pool_a_rate
        cutoff_b = pool_a_rate + pool_b_rate

        share_122 = float(luck.get("walkout_122_share", 6.0) or 6.0)
        share_121 = float(luck.get("walkout_121_share", 35.0) or 35.0)

        def pick_pool_a_weighted(pool_a_list):
            if not pool_a_list:
                return {}
            cards_122 = [p for p in pool_a_list if (p.get('rating') or 0) >= 122]
            cards_121 = [p for p in pool_a_list if (p.get('rating') or 0) == 121]
            cards_120 = [p for p in pool_a_list if (p.get('rating') or 0) <= 120]
            
            tier_roll = random.uniform(0, 100)
            if tier_roll < share_122 and cards_122:
                return random.choice(cards_122)
            elif tier_roll < (share_122 + share_121) and cards_121:
                return random.choice(cards_121)
            elif cards_120:
                return random.choice(cards_120)
            elif cards_121:
                return random.choice(cards_121)
            elif cards_122:
                return random.choice(cards_122)
            return random.choice(pool_a_list)

        for _ in range(count):
            roll = random.uniform(0, 100)
            if roll <= cutoff_a and pool_a:
                card = pick_pool_a_weighted(pool_a)
            elif roll <= cutoff_b and pool_b:
                card = random.choice(pool_b)
            elif pool_c:
                card = random.choice(pool_c)
            elif pool_b:
                card = random.choice(pool_b)
            else:
                card = pick_pool_a_weighted(pool_a) if pool_a else {"cardName": "Mystery Star", "rating": 110, "position": "ST"}

            pulled.append(card)
            ovr = int(card.get('rating') or 110)
            if ovr > highest_ovr:
                highest_ovr = ovr
                highest_card = card

        return pulled, highest_card, highest_ovr

    async def execute_pack_battle(self, interaction: discord.Interaction, user_a: discord.Member, user_b, vouchers: int, pack_num: int):
        is_solo = isinstance(user_b, str) or (hasattr(user_b, 'id') and user_b.id == 0)
        drafts = await database.get_active_drafts()
        d_pack = drafts.get(pack_num) or drafts.get(str(pack_num)) or (next(iter(drafts.values())) if drafts else {})
        luck = await database.get_luck_settings()

        # Deduct vouchers
        await database.add_vouchers(user_a.id, -vouchers)
        if not is_solo:
            await database.add_vouchers(user_b.id, -vouchers)

        # Roll packs with draft luck settings
        cards_a, best_a, _ = self._roll_pack(d_pack, vouchers, luck)
        cards_b, best_b, _ = self._roll_pack(d_pack, vouchers, luck)

        # Sort all cards descending by rating
        sorted_a = sorted(cards_a, key=lambda c: int(c.get('rating') or 0), reverse=True)
        sorted_b = sorted(cards_b, key=lambda c: int(c.get('rating') or 0), reverse=True)

        # Compare ratings starting from highest (1st highest, 2nd highest, etc.)
        winner = None # 'a', 'b', or None (tie)
        deciding_rank = None
        deciding_ovr_a = None
        deciding_ovr_b = None

        for idx in range(min(len(sorted_a), len(sorted_b))):
            r_a = int(sorted_a[idx].get('rating') or 0)
            r_b = int(sorted_b[idx].get('rating') or 0)
            if r_a > r_b:
                winner = 'a'
                deciding_rank = idx + 1
                deciding_ovr_a = r_a
                deciding_ovr_b = r_b
                break
            elif r_b > r_a:
                winner = 'b'
                deciding_rank = idx + 1
                deciding_ovr_a = r_a
                deciding_ovr_b = r_b
                break

        total_pot = vouchers * 2
        name_b = user_b.display_name if hasattr(user_b, 'display_name') else "DestiFC AI 🤖"
        mention_b = user_b.mention if hasattr(user_b, 'mention') else "**DestiFC AI 🤖**"

        # Winner takes all cards + pot vouchers! Loser loses their cards!
        if winner == 'a':
            tiebreak_reason = f"👑 Decided on **#{deciding_rank} highest card**: ({deciding_ovr_a} vs {deciding_ovr_b} OVR)" if deciding_rank > 1 else f"⭐ Won with highest card: **{deciding_ovr_a} OVR**"
            winner_text = f"🏆 **{user_a.display_name} WINS THE PACK BATTLE!**\n{tiebreak_reason}\n🎉 Won the pot of **+{total_pot} Draft Vouchers** & claimed all **{len(cards_a) + (len(cards_b) if not is_solo else len(cards_a))} player cards**!"
            await database.add_vouchers(user_a.id, total_pot)
            # Winner keeps their cards + steals opponent's cards (or all pulled cards)
            all_won_cards = cards_a + (cards_b if not is_solo else [])
            await database.add_players_to_inventory_batch(user_a.id, all_won_cards)
            color = discord.Color.green()
            winning_card = sorted_a[0]
        elif winner == 'b':
            tiebreak_reason = f"👑 Decided on **#{deciding_rank} highest card**: ({deciding_ovr_b} vs {deciding_ovr_a} OVR)" if deciding_rank > 1 else f"⭐ Won with highest card: **{deciding_ovr_b} OVR**"
            if not is_solo:
                winner_text = f"🏆 **{name_b} WINS THE PACK BATTLE!**\n{tiebreak_reason}\n🎉 Won the pot of **+{total_pot} Draft Vouchers** & claimed all **{len(cards_a) + len(cards_b)} player cards**!"
                await database.add_vouchers(user_b.id, total_pot)
                await database.add_players_to_inventory_batch(user_b.id, cards_a + cards_b)
            else:
                winner_text = f"🤖 **DestiFC AI WINS THE PACK BATTLE!**\n{tiebreak_reason}\nYour wagered vouchers and opened cards were forfeited to the AI!"
            color = discord.Color.red()
            winning_card = sorted_b[0]
        else:
            winner_text = f"🤝 **PERFECT DRAW!** All cards matched ratings exactly!\nVouchers refunded ({vouchers} each) and each player keeps their own cards."
            await database.add_vouchers(user_a.id, vouchers)
            await database.add_players_to_inventory_batch(user_a.id, cards_a)
            if not is_solo:
                await database.add_vouchers(user_b.id, vouchers)
                await database.add_players_to_inventory_batch(user_b.id, cards_b)
            color = discord.Color.gold()
            winning_card = sorted_a[0]

        # Format full list of every single pack opened
        lines_a = []
        for i, c in enumerate(sorted_a, 1):
            c_name = c.get('cardName') or c.get('lastName', 'Card')
            pos = c.get('position', 'ST')
            ovr = c.get('rating', 110)
            star = "🔥 " if i == 1 else ""
            lines_a.append(f"`#{i:02d}` {star}**{ovr}** {pos} - {c_name}")

        lines_b = []
        for i, c in enumerate(sorted_b, 1):
            c_name = c.get('cardName') or c.get('lastName', 'Card')
            pos = c.get('position', 'ST')
            ovr = c.get('rating', 110)
            star = "🔥 " if i == 1 else ""
            lines_b.append(f"`#{i:02d}` {star}**{ovr}** {pos} - {c_name}")

        # Discord embed field character limit guard (1024 chars max per field)
        text_a = "\n".join(lines_a)
        if len(text_a) > 1000:
            text_a = "\n".join(lines_a[:15]) + f"\n*...and {len(lines_a) - 15} more cards*"

        text_b = "\n".join(lines_b)
        if len(text_b) > 1000:
            text_b = "\n".join(lines_b[:15]) + f"\n*...and {len(lines_b) - 15} more cards*"

        embed = discord.Embed(
            title="⚔️ PACK BATTLE DUEL RESULTS!",
            description=(
                f"**{user_a.mention}** VS {mention_b}\n"
                f"🎟️ **Wager:** `{vouchers} Vouchers each` | **Pot:** `{total_pot} Vouchers`\n"
                f"📦 **Pack Opened:** Draft Pack {pack_num} ({vouchers} Packs each)\n\n"
                f"---\n{winner_text}\n---"
            ),
            color=color
        )

        embed.add_field(name=f"🔵 {user_a.display_name}'s Pulls (Highest to Lowest)", value=text_a, inline=False)
        embed.add_field(name=f"🔴 {name_b}'s Pulls (Highest to Lowest)", value=text_b, inline=False)
        embed.set_footer(text=f"Opened {vouchers * 2} total packs • Winner takes all cards & vouchers!")

        # Render winning card
        file = None
        try:
            image_binary, filename = get_or_create_card_bytes(winning_card, 3, int(winning_card.get('rating', 0)) >= 120)
            if image_binary:
                file = discord.File(fp=image_binary, filename=filename or 'winner.png')
                embed.set_image(url=f"attachment://{filename or 'winner.png'}")
        except Exception:
            pass

        if interaction.response.is_done():
            if file:
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)
        else:
            if file:
                await interaction.response.send_message(embed=embed, file=file)
            else:
                await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pack_battle", description="Battle a friend or AI in a Draft Pack opening shootout (Up to 50 Vouchers)!")
    @app_commands.describe(
        vouchers="Vouchers to wager (1 to 50)",
        user="Player to challenge (leave empty to battle DestiFC AI)",
        pack="Which draft pack to open (1, 2, or 3)"
    )
    @app_commands.choices(pack=[
        app_commands.Choice(name="Draft Pack 1", value=1),
        app_commands.Choice(name="Draft Pack 2", value=2),
        app_commands.Choice(name="Draft Pack 3", value=3)
    ])
    async def pack_battle(self, interaction: discord.Interaction, vouchers: int = 1, user: discord.Member = None, pack: int = 1):
        if vouchers < 1 or vouchers > 50:
            return await interaction.response.send_message("❌ Voucher wager must be between **1 and 50** vouchers!", ephemeral=True)

        user_data = await database.get_user(interaction.user.id)
        if user_data.get('vouchers', 0) < vouchers:
            return await interaction.response.send_message(
                f"❌ You do not have enough Draft Vouchers! You have **{user_data.get('vouchers', 0)}**, but wager is **{vouchers}**.",
                ephemeral=True
            )

        if user is None or user.id == interaction.user.id or user.bot:
            # Solo battle vs AI
            await interaction.response.defer()
            await self.execute_pack_battle(interaction, interaction.user, "DestiFC AI 🤖", vouchers, pack)
        else:
            # PvP Challenge
            view = PackBattleChallengeView(interaction.user, user, vouchers, pack, self)
            embed = discord.Embed(
                title="⚔️ PACK BATTLE CHALLENGE!",
                description=(
                    f"{user.mention}, you have been challenged by **{interaction.user.mention}** to a **Pack Battle**!\n\n"
                    f"🎟️ **Wager:** `{vouchers} Draft Vouchers` each\n"
                    f"📦 **Pack:** Draft Pack {pack}\n"
                    f"🏆 **Winner takes all:** `{vouchers * 2} Draft Vouchers` & all pulled cards!\n\n"
                    f"*Click Accept below within 60 seconds to open packs!*"
                ),
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.response.send_message(content=user.mention, embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(PackBattleCog(bot))
