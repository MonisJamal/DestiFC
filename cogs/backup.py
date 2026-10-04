import discord
from discord.ext import commands, tasks
import json
import io
import datetime
import database
import os

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()

    def cog_unload(self):
        self.daily_backup.cancel()

    @tasks.loop(hours=24)
    async def daily_backup(self):
        try:
            print("[Backup] Generating daily database backup...")
            p = await database.get_db()
            
            # Fetch essential data
            users = await p.fetch("SELECT * FROM users")
            inventory = await p.fetch("SELECT * FROM inventory")
            squads = await p.fetch("SELECT * FROM squads")
            market = await p.fetch("SELECT * FROM market")
            system_settings = await p.fetch("SELECT * FROM system_settings")
            
            backup_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "users": [dict(u) for u in users],
                "inventory": [dict(i) for i in inventory],
                "squads": [dict(s) for s in squads],
                "market": [dict(m) for m in market],
                "system_settings": [dict(s) for s in system_settings]
            }
            
            # Convert to JSON string
            json_str = json.dumps(backup_data, default=str)
            file_obj = io.BytesIO(json_str.encode('utf-8'))
            
            # Send to owner
            owner_id = int(os.getenv("OWNER_ID", "877073286079037501"))
            owner = await self.bot.fetch_user(owner_id)
            if owner:
                file = discord.File(fp=file_obj, filename=f"destifc_backup_{datetime.datetime.now().strftime('%Y-%m-%d')}.json")
                await owner.send("📦 **Daily Database Backup**\nHere is your Aiven database backup. Keep this safe! If the database ever crashes, we can restore everything from this file.", file=file)
                print("[Backup] Daily backup sent to owner successfully!")
        except Exception as e:
            print(f"[Backup Error] Failed to generate backup: {e}")

    @daily_backup.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()
        
    @discord.app_commands.command(name="force_backup", description="Force an immediate database backup (Admin only)")
    async def force_backup(self, interaction: discord.Interaction):
        owner_id = int(os.getenv("OWNER_ID", "877073286079037501"))
        if interaction.user.id != owner_id:
            return await interaction.response.send_message("You do not have permission to run backups.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        try:
            p = await database.get_db()
            users = await p.fetch("SELECT * FROM users")
            inventory = await p.fetch("SELECT * FROM inventory")
            backup_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "users": [dict(u) for u in users],
                "inventory": [dict(i) for i in inventory]
            }
            json_str = json.dumps(backup_data, default=str)
            file_obj = io.BytesIO(json_str.encode('utf-8'))
            file = discord.File(fp=file_obj, filename=f"destifc_manual_backup_{datetime.datetime.now().strftime('%Y-%m-%d')}.json")
            await interaction.followup.send("📦 **Manual Database Backup**\nHere is your full database backup.", file=file)
        except Exception as e:
            await interaction.followup.send(f"Backup failed: {e}")

async def setup(bot):
    await bot.add_cog(BackupCog(bot))
