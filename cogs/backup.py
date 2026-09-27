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
        if not os.path.exists('backups'):
            os.makedirs('backups')
            
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backups/destifc_backup_{timestamp}.db"
        
        try:
            # We copy destifc.db to the backups folder safely
            shutil.copy2('destifc.db', backup_file)
            print(f"[Backup] Successfully backed up database to {backup_file}")
            
            # Clean up old backups (keep only last 24 backups)
            backups = sorted([f for f in os.listdir('backups') if f.endswith('.db')])
            if len(backups) > 24:
                for old_file in backups[:-24]:
                    os.remove(os.path.join('backups', old_file))
                    print(f"[Backup] Deleted old backup: {old_file}")
                    
        except Exception as e:
            print(f"[Backup Error] Failed to create backup: {e}")

    @backup_db.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BackupCog(bot))
