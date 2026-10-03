import discord
from discord.ext import commands
from discord import app_commands
import database
import random
import asyncio
import io
import datetime
import traceback
import maps
from card_generator import get_or_create_card_bytes

class SignatureBoxView(discord.ui.View):
    def __init__(self, user: discord.User, box_config: dict, user_box: dict, cog):
        super().__init__(timeout=180)
        self.user = user
        self.box_config = box_config
        self.user_box = user_box
        self.cog = cog
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        claimed = set(self.user_box.get('claimed_reward_ids', []))
        all_rewards = self.box_config.get('rewards_json', [])
        remaining = [r for r in all_rewards if r['id'] not in claimed]

        if not remaining:
            btn = discord.ui.Button(label="🎉 Box Fully Completed!", style=discord.ButtonStyle.secondary, disabled=True, emoji="🏆")
            self.add_item(btn)
            return

        draw_idx = len(claimed)
        costs = self.box_config.get('draw_costs_json', [])
        cost_obj = costs[draw_idx] if draw_idx < len(costs) else {"currency": "coins", "amount": 100000000}
        
        curr_icon = "🪙" if cost_obj.get('currency') == 'coins' else ("🎟️" if cost_obj.get('currency') == 'vouchers' else "💎")
        btn_label = f"Draw #{draw_idx + 1} ({cost_obj.get('amount', 0):,} {cost_obj.get('currency', 'coins').title()})"
        
        draw_btn = discord.ui.Button(label=btn_label[:80], style=discord.ButtonStyle.success, emoji=curr_icon, custom_id="sig_draw_btn")
        draw_btn.callback = self.on_draw_click
        self.add_item(draw_btn)

        prob_btn = discord.ui.Button(label="Odds / Rates", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="sig_prob_btn")
        prob_btn.callback = self.on_prob_click
        self.add_item(prob_btn)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item = None):
        print(f"[SignatureBox] View error: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            try: await interaction.response.send_message("❌ An error occurred in the Signature Box.", ephemeral=True)
            except Exception: pass

    async def on_prob_click(self, interaction: discord.Interaction):
        claimed = set(self.user_box.get('claimed_reward_ids', []))
        all_rewards = self.box_config.get('rewards_json', [])
        remaining = [r for r in all_rewards if r['id'] not in claimed]
        total_weight = sum(r.get('base_weight', 10.0) for r in remaining) or 1.0

        desc = "### 📊 Current Reward Probabilities (Dynamic Pool):\n"
        for r in all_rewards:
            r_id = r['id']
            name = r.get('name', 'Reward')
            icon = r.get('icon', '🎁')
            tier = r.get('tier', 'mid').upper()
            if r_id in claimed:
                desc += f"~~{icon} **{name}** ({tier})~~ ➔ **CLAIMED ✅**\n"
            else:
                prob = (r.get('base_weight', 10.0) / total_weight) * 100
                desc += f"{icon} **{name}** `[{tier}]` ➔ **{prob:.2f}%**\n"

        desc += "\n*Note: Each reward is non-repeatable. Odds increase for all remaining rewards after every draw!*"
        embed = discord.Embed(title="🎲 Signature Box Probabilities", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_draw_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This is not your Signature Box!", ephemeral=True)

        await interaction.response.defer()
        await self.cog.execute_draw(interaction, self)


class SignatureBoxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_box_embed(self, user: discord.Member, box: dict, user_box: dict) -> discord.Embed:
        claimed = set(user_box.get('claimed_reward_ids', []))
        all_rewards = box.get('rewards_json', [])
        remaining = [r for r in all_rewards if r['id'] not in claimed]
        
        draw_idx = len(claimed)
        costs = box.get('draw_costs_json', [])
        cost_obj = costs[draw_idx] if draw_idx < len(costs) else {"currency": "coins", "amount": 100000000}
        
        sig_card = box.get('signature_card_data', {})
        sig_name = sig_card.get('cardName') or sig_card.get('lastName', 'Superstar')
        sig_ovr = sig_card.get('rating', 124)
        sig_pos = sig_card.get('position', 'CAM')
        sig_club = maps.get_club_display(sig_card)
        sig_nation = maps.get_nation_display(sig_card)

        # Rewards grid status (10 items)
        reward_lines = []
        for r in all_rewards:
            is_claimed = r['id'] in claimed
            badge = "✅" if is_claimed else "🎁"
            tier_badge = "👑 [GOOD]" if r.get('tier') == 'good' else ("✨ [MID]" if r.get('tier') == 'mid' else "⚠️ [BAD]")
            line = f"{badge} `{r['id']:02d}.` **{r.get('name')}** {tier_badge}"
            if is_claimed:
                line = f"~~{line}~~"
            reward_lines.append(line)

        currency_str = f"`{cost_obj.get('amount', 0):,}` {cost_obj.get('currency', 'coins').title()}"
        status_header = f"🌟 **Featured Player:** **{sig_name}** `({sig_pos})` — `{sig_ovr} OVR`\n" \
                        f"🛡️ **Club:** {sig_club} | 🌍 **Nation:** {sig_nation}\n" \
                        f"⚡ **Special Perk:** *+15% In-Game Performance Boost & Custom Signature Aura*\n\n" \
                        f"### 📦 Box Progress: `{len(claimed)}/10 Claimed`\n" \
                        f"💰 **Next Draw #{draw_idx + 1} Cost:** {currency_str}\n\n" \
                        f"### 📋 10-Reward Pool Matrix:\n" + "\n".join(reward_lines)

        embed = discord.Embed(
            title=f"🎁 {box.get('title', 'FC SIGNATURE BOX')}",
            description=status_header,
            color=discord.Color.gold()
        )
        if box.get('banner_url'):
            embed.set_image(url=box['banner_url'])
        embed.set_footer(text=f"DestiFC Signature Box • Expires: {box.get('expires_at', 'Limited Time')}")
        return embed

    @app_commands.command(name="signature_box", description="Open the exclusive 10-Reward FC Signature Box with increasing draw costs")
    async def signature_box(self, interaction: discord.Interaction):
        await interaction.response.defer()
        box = await database.get_signature_box_config()
        if not box.get('is_active', True):
            return await interaction.followup.send("⚠️ The Signature Box is currently closed or under maintenance.", ephemeral=True)

        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # Check if start time is set and in the future
        starts_at = box.get('starts_at')
        if starts_at:
            try:
                st_str = str(starts_at).replace('Z', '+00:00')
                st_dt = datetime.datetime.fromisoformat(st_str)
                if st_dt.tzinfo is None:
                    st_dt = st_dt.replace(tzinfo=datetime.timezone.utc)
                if st_dt > now_dt:
                    ts = int(st_dt.timestamp())
                    return await interaction.followup.send(
                        f"⏳ **Upcoming Signature Box Event!**\nThis box will unlock <t:{ts}:R> (<t:{ts}:F>). Stay tuned!",
                        ephemeral=True
                    )
            except Exception as e:
                print(f"[Signature Box starts_at parse error]: {e}")

        # Check if expiration date has passed
        expires_at = box.get('expires_at')
        if expires_at:
            try:
                exp_str = str(expires_at).replace('Z', '+00:00')
                exp_dt = datetime.datetime.fromisoformat(exp_str)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                if exp_dt < now_dt:
                    return await interaction.followup.send(
                        "⌛ **Event Expired!**\nThis Signature Box event has concluded. Stay tuned for the next release!",
                        ephemeral=True
                    )
            except Exception as e:
                print(f"[Signature Box expires_at parse error]: {e}")

        user_box = await database.get_user_signature_box(interaction.user.id)
        embed = self.generate_box_embed(interaction.user, box, user_box)
        view = SignatureBoxView(interaction.user, box, user_box, self)
        await interaction.followup.send(embed=embed, view=view)

    async def execute_draw(self, interaction: discord.Interaction, view: SignatureBoxView):
        user_id = interaction.user.id
        box = await database.get_signature_box_config()
        user_box = await database.get_user_signature_box(user_id)
        
        claimed = set(user_box.get('claimed_reward_ids', []))
        all_rewards = box.get('rewards_json', [])
        remaining = [r for r in all_rewards if r['id'] not in claimed]

        if not remaining:
            return await interaction.followup.send("🎉 You have already claimed all 10 rewards in this Signature Box!", ephemeral=True)

        draw_idx = len(claimed)
        costs = box.get('draw_costs_json', [])
        cost_obj = costs[draw_idx] if draw_idx < len(costs) else {"currency": "coins", "amount": 100000000}
        
        curr_type = cost_obj.get('currency', 'coins').lower()
        amount_needed = int(cost_obj.get('amount', 0))

        # Check balance
        u_data = await database.get_user(user_id)
        curr_bal = u_data.get(curr_type, 0)
        if curr_bal < amount_needed:
            return await interaction.followup.send(
                f"❌ **Insufficient {curr_type.title()}!**\nDraw #{draw_idx + 1} requires **{amount_needed:,} {curr_type.title()}**, but you only have **{curr_bal:,}**.",
                ephemeral=True
            )

        # Deduct currency
        if curr_type == 'coins':
            await database.add_coins(user_id, -amount_needed)
        elif curr_type == 'vouchers':
            await database.add_vouchers(user_id, -amount_needed)
        elif curr_type == 'gems':
            await database.update_gems(user_id, -amount_needed)

        # Pick weighted random reward
        weights = [r.get('base_weight', 10.0) for r in remaining]
        chosen_reward = random.choices(remaining, weights=weights, k=1)[0]
        r_id = chosen_reward['id']
        r_type = chosen_reward.get('type', 'coins')
        r_tier = chosen_reward.get('tier', 'mid')
        r_amount = chosen_reward.get('amount', 0)

        # Record draw in DB
        await database.record_user_signature_box_draw(user_id, r_id)
        user_box['claimed_reward_ids'].append(r_id)
        user_box['draws_completed'] = len(user_box['claimed_reward_ids'])

        # Deliver reward
        sig_card_awarded = None
        if r_type == 'coins':
            await database.add_coins(user_id, r_amount)
        elif r_type == 'vouchers':
            await database.add_vouchers(user_id, r_amount)
        elif r_type == 'gems':
            await database.update_gems(user_id, r_amount)
        elif r_type == 'fans':
            await database.add_fans(user_id, r_amount)
        elif r_type == 'pack':
            min_r = chosen_reward.get('pack_rating_min', 115)
            max_r = chosen_reward.get('pack_rating_max', 118)
            cards = await database.get_official_cards_by_rating(min_r, max_r, 10)
            if cards:
                pulled = random.choice(cards)
                await database.add_player_to_inventory(user_id, pulled)
        elif r_type == 'signature_card':
            sig_card_awarded = box.get('signature_card_data', {})
            sig_card_awarded['is_signature_box'] = True
            sig_card_awarded['is_custom'] = True
            sig_card_awarded['performance_boost'] = 1.25
            sig_card_awarded['source'] = 'SIGNATURE_BOX'
            await database.add_player_to_inventory(user_id, sig_card_awarded)

        # Handle reveal presentation
        if sig_card_awarded:
            # 🌟 Grand 4-Stage Suspense Walkout for Signature Card!
            ovr = sig_card_awarded.get('rating', 124)
            pos = sig_card_awarded.get('position', 'CAM')
            nation_str = maps.get_nation_display(sig_card_awarded)
            club_str = maps.get_club_display(sig_card_awarded)
            name = sig_card_awarded.get('cardName', 'Superstar')

            # Stage 1
            s1 = discord.Embed(
                title="✨ SIGNATURE WALKOUT DETECTED! ✨",
                description=f"🚨 **GRAND PRIZE FROM SIGNATURE BOX!**\n\n🌍 **Nation:** **{nation_str}**\n🏃 **Position:** ⏳ `???`\n🛡️ **Club:** ⏳ `???`\n\n*(Building suspense...)*",
                color=discord.Color.gold()
            )
            msg = await interaction.followup.send(embed=s1)
            await asyncio.sleep(1.2)

            # Stage 2
            s2 = discord.Embed(
                title="🔥 SIGNATURE WALKOUT: POSITION! 🔥",
                description=f"🚨 **GRAND PRIZE FROM SIGNATURE BOX!**\n\n🌍 **Nation:** **{nation_str}**\n🏃 **Position:** **`{pos}`**\n🛡️ **Club:** ⏳ `???`\n\n*(Who could it be?!)*",
                color=discord.Color.gold()
            )
            try: await msg.edit(embed=s2)
            except Exception: pass
            await asyncio.sleep(1.2)

            # Stage 3
            s3 = discord.Embed(
                title="⚡ SIGNATURE WALKOUT: CLUB! ⚡",
                description=f"🚨 **GRAND PRIZE FROM SIGNATURE BOX!**\n\n🌍 **Nation:** **{nation_str}**\n🏃 **Position:** **`{pos}`**\n🛡️ **Club:** **{club_str}**\n\n💥 **HERE COMES THE LEGEND!**",
                color=discord.Color.gold()
            )
            try: await msg.edit(embed=s3)
            except Exception: pass
            await asyncio.sleep(1.2)

            # Stage 4: Card Image Generation
            image_binary, filename = await asyncio.to_thread(get_or_create_card_bytes, sig_card_awarded, 3, True)
            file = discord.File(fp=image_binary, filename=filename or 'card.png') if image_binary else None

            final_embed = discord.Embed(
                title=f"👑 SIGNATURE CARD UNLOCKED! ({ovr} OVR)",
                description=(
                    f"🔥 **{nation_str}** ➔ 🏃 **`{pos}`** ➔ **{club_str}**\n\n"
                    f"🎉 **CONGRATULATIONS!** You unlocked the exclusive **{name}** `({pos})` `{ovr} OVR`!\n\n"
                    f"⚡ **Innate Buff:** `+15% Match Influence & MoTM Synergy`\n"
                    f"🏆 **Obtained on Draw #{draw_idx + 1}** *(Cost: {amount_needed:,} {curr_type.title()})*"
                ),
                color=discord.Color.gold()
            )
            if file and filename:
                final_embed.set_image(url=f"attachment://{filename}")
            final_embed.set_footer(text="DestiFC Signature Box • Added to your inventory")

            if file:
                file.fp.seek(0)
                await msg.edit(embed=final_embed, attachments=[file])
            else:
                await msg.edit(embed=final_embed)
        else:
            # Standard reward reveal
            icon = chosen_reward.get('icon', '🎁')
            tier_name = "👑 GRAND REWARD" if r_tier == 'good' else ("✨ MID REWARD" if r_tier == 'mid' else "⚠️ BAD REWARD")
            color = discord.Color.green() if r_tier == 'good' else (discord.Color.blue() if r_tier == 'mid' else discord.Color.dark_grey())

            result_embed = discord.Embed(
                title=f"{icon} Signature Box Draw #{draw_idx + 1} Result!",
                description=(
                    f"### 🎉 You Won: **{chosen_reward.get('name')}**\n"
                    f"**Tier:** `{tier_name}`\n"
                    f"🪙 **Cost Paid:** `{amount_needed:,}` {curr_type.title()}\n\n"
                    f"📦 **Remaining Rewards in Box:** `{10 - len(user_box['claimed_reward_ids'])}/10`\n"
                    f"*Use `/signature_box` anytime to continue your progress!*"
                ),
                color=color
            )
            await interaction.followup.send(embed=result_embed)

        # Update the original view if possible
        try:
            view.user_box = user_box
            view.update_buttons()
            updated_box_embed = self.generate_box_embed(interaction.user, box, user_box)
            if interaction.message:
                await interaction.message.edit(embed=updated_box_embed, view=view)
        except Exception:
            pass

    @app_commands.command(name="signature_box_reset", description="Admin: Reset Signature Box progress for a user or globally")
    @app_commands.describe(user="User to reset (leave empty for global reset)")
    async def signature_box_reset(self, interaction: discord.Interaction, user: discord.Member = None):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)

        target_id = user.id if user else None
        await database.reset_user_signature_box(target_id)
        target_name = user.mention if user else "ALL USERS globally"
        await interaction.response.send_message(f"✅ Successfully reset Signature Box progress for **{target_name}**!")

async def setup(bot):
    await bot.add_cog(SignatureBoxCog(bot))
