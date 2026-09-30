import discord
from discord.ext import commands, tasks
import shutil
import os
import datetime

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_db.start()

    def cog_unload(self):
        self.backup_db.cancel()

    @tasks.loop(hours=1.0)
    async def backup_db(self):
        try:
            p = await database.get_db()
            # Perform a lightweight ping to verify Supabase cloud connectivity
            await p.fetchval("SELECT 1")
            print("[Cloud DB] Supabase PostgreSQL health verified successfully.")
        except Exception as e:
            print(f"[Cloud DB Warning] Supabase health check issue: {e}")

    @backup_db.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BackupCog(bot))
