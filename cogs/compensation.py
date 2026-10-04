import discord
from discord.ext import commands
import database
import json
import datetime
from discord import app_commands

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
            gems_reward = int(config.get('gems', 0))
            message = config.get('message', 'Here is your compensation reward!')
            
            user_id = interaction.user.id
            await database.get_user(user_id) # Ensure user exists
            
            # Fetch user stats
            stat_row = await p.fetchrow("SELECT stats FROM user_stats WHERE user_id = $1", user_id)
            stats = {}
            if stat_row and stat_row['stats']:
                stats = json.loads(stat_row['stats']) if isinstance(stat_row['stats'], str) else stat_row['stats']
                
            claimed_events = stats.get('claimed_compensations', [])
            
            if event_id in claimed_events:
                return await interaction.followup.send("You have already claimed this compensation!")
                
            # Grant rewards
            if coins_reward > 0:
                await database.add_coins(user_id, coins_reward)
            if vouchers_reward > 0:
                await database.add_vouchers(user_id, vouchers_reward)
            if gems_reward > 0:
                await database.update_gems(user_id, gems_reward)
                
            # Update claims
            claimed_events.append(event_id)
            stats['claimed_compensations'] = claimed_events
            
            await p.execute("INSERT INTO user_stats (user_id, stats) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET stats = EXCLUDED.stats", user_id, json.dumps(stats))
            
            rewards_str = []
            if coins_reward > 0: rewards_str.append(f"🪙 **{coins_reward:,} Coins**")
            if vouchers_reward > 0: rewards_str.append(f"🎫 **{vouchers_reward:,} Vouchers**")
            if gems_reward > 0: rewards_str.append(f"💎 **{gems_reward:,} Gems**")
            
            embed = discord.Embed(title="🎁 Compensation Claimed!", description=f"{message}\n\n**You received:**\n" + "\n".join(rewards_str), color=discord.Color.green())
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Compensation error: {e}")
            await interaction.followup.send(f"An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(CompensationCog(bot))
