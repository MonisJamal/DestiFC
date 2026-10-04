import discord
from discord.ext import commands
from discord import app_commands
import database
import json
import datetime

class CompensationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="compensation", description="Claim active compensation rewards")
    async def compensation(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            p = await database.get_db()
            row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'compensation_config'")
            if not row:
                return await interaction.followup.send("There is no active compensation event right now.")
            
            config = json.loads(row['value'])
            
            if not config.get('is_active', False):
                return await interaction.followup.send("There is no active compensation event right now.")
            
            now = datetime.datetime.now().timestamp()
            start_time = config.get('start_timestamp', 0)
            end_time = config.get('end_timestamp', 0)
            
            if now < start_time:
                return await interaction.followup.send(f"This compensation event hasn't started yet! It begins <t:{int(start_time)}:R>.")
            if end_time > 0 and now > end_time:
                return await interaction.followup.send(f"This compensation event has expired. It ended <t:{int(end_time)}:R>.")
                
            event_id = config.get('event_id', 'default_event')
            coins_reward = int(config.get('coins', 0))
            vouchers_reward = int(config.get('vouchers', 0))
            
            user_id = interaction.user.id
            await database.get_user(user_id) # Ensure user exists
            
            stat_row = await p.fetchrow("SELECT stats FROM user_stats WHERE user_id = $1", user_id)
            stats = {}
            if stat_row and stat_row['stats']:
                stats = json.loads(stat_row['stats']) if isinstance(stat_row['stats'], str) else stat_row['stats']
                
            claimed_events = stats.get('claimed_compensations', [])
            if event_id in claimed_events:
                return await interaction.followup.send("You have already claimed this compensation!")
                
            if coins_reward > 0: await database.add_coins(user_id, coins_reward)
            if vouchers_reward > 0: await database.add_vouchers(user_id, vouchers_reward)
                
            claimed_events.append(event_id)
            stats['claimed_compensations'] = claimed_events
            await p.execute("INSERT INTO user_stats (user_id, stats) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET stats = EXCLUDED.stats", user_id, json.dumps(stats))
            
            rewards_str = []
            if coins_reward > 0: rewards_str.append(f"🪙 **{coins_reward:,} Coins**")
            if vouchers_reward > 0: rewards_str.append(f"🎫 **{vouchers_reward:,} Vouchers**")
            
            embed = discord.Embed(title="🎁 Compensation Claimed!", description=f"{config.get('message', 'Thank you for your patience!')}\n\n**You received:**\n" + "\n".join(rewards_str), color=discord.Color.green())
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="admin_compensation", description="[ADMIN] Configure the active compensation event")
    @app_commands.describe(
        is_active="Turn the event ON or OFF",
        event_id="Unique name (e.g. season2_launch). Change this to allow users to claim again.",
        coins="Amount of coins to give",
        vouchers="Amount of draft vouchers to give",
        message="Message shown when claimed",
        hours_to_last="How many hours should this event stay active for?"
    )
    async def admin_compensation(self, interaction: discord.Interaction, is_active: bool, event_id: str, coins: int, vouchers: int, message: str, hours_to_last: int = 48):
        import os
        owner_id = int(os.getenv("OWNER_ID", "877073286079037501"))
        if interaction.user.id != owner_id:
            return await interaction.response.send_message("You are not authorized.", ephemeral=True)
            
        now = datetime.datetime.now().timestamp()
        config = {
            "is_active": is_active,
            "event_id": event_id,
            "coins": coins,
            "vouchers": vouchers,
            "message": message,
            "start_timestamp": now,
            "end_timestamp": now + (hours_to_last * 3600)
        }
        
        p = await database.get_db()
        await p.execute("INSERT INTO system_settings (key, value) VALUES ('compensation_config', $1) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", json.dumps(config))
        
        embed = discord.Embed(title="⚙️ Compensation Configured", color=discord.Color.blue())
        embed.add_field(name="Status", value="Active 🟢" if is_active else "Inactive 🔴")
        embed.add_field(name="Event ID", value=event_id)
        embed.add_field(name="Rewards", value=f"🪙 {coins:,} | 🎫 {vouchers:,}")
        embed.add_field(name="Ends", value=f"<t:{int(config['end_timestamp'])}:R>")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CompensationCog(bot))
