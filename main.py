

import threading

import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import database
from auth import is_team_admin_or_owner

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class DestiFC(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all(),
            help_command=commands.DefaultHelpCommand()
        )
        self.last_presence_state = None

    async def setup_hook(self):
        await database.setup()
        asyncio.create_task(database.preload_official_cards_cache())
        
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                await self.load_extension(f'cogs.{filename[:-3]}')

        # Lightweight global interaction check — only maintenance mode and per-command disable.
        # No admin/owner API calls here (those caused the 3s timeout for non-admins).
        @self.tree.interaction_check
        async def global_maintenance_check(interaction: discord.Interaction) -> bool:
            try:
                bot_cfg = await database.get_bot_config()
                if bot_cfg.get('maintenance_mode', False):
                    msg = bot_cfg.get(
                        'maintenance_message',
                        "🛠️ DestiFC is currently undergoing scheduled maintenance. Commands are temporarily paused!"
                    )
                    # Admins bypass maintenance
                    try:
                        if await is_team_admin_or_owner(self, interaction.user):
                            return True
                    except Exception:
                        pass
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"🔒 **Maintenance Mode Active**\n{msg}", ephemeral=True)
                    return False

                cmd = interaction.command
                cmd_name = (cmd.name if cmd else "").lower()
                root_name = (cmd.root_parent.name if cmd and cmd.root_parent else cmd_name).lower()
                commands_enabled = bot_cfg.get('commands_enabled', {})
                if (cmd_name in commands_enabled and not commands_enabled[cmd_name]) or \
                   (root_name in commands_enabled and not commands_enabled[root_name]):
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"⚠️ The `/{cmd_name}` command is temporarily disabled by administrators. Please check back shortly!",
                            ephemeral=True
                        )
                    return False
            except Exception as e:
                print(f"[Maintenance Check Error] {e}")
            return True

        # Global command error handler
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            import traceback
            cmd_name = interaction.command.name if interaction.command else "command"
            print(f"[AppCommandError] Command '/{cmd_name}' failed for user {interaction.user.id} ({interaction.user.display_name}): {error}")
            traceback.print_exception(type(error), error, error.__traceback__)

            msg = f"❌ An unexpected error occurred while executing `/{cmd_name}`. Please try again in a moment."
            if isinstance(error, app_commands.CommandOnCooldown):
                msg = f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s."
            elif isinstance(error, app_commands.CheckFailure):
                msg = "❌ You do not have permission to execute this command."

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass

        # Sync slash commands
        await self.tree.sync()

        # Start dynamic presence and heartbeat sync loops
        self.sync_presence_loop.start()
        self.bot_heartbeat_loop.start()
        self.remote_signal_listener_loop.start()

    @tasks.loop(seconds=10)
    async def bot_heartbeat_loop(self):
        """Sends a high-precision live pulse to Supabase every 10s with real latency and stats."""
        try:
            import datetime
            import json
            import os

            heartbeat_data = {
                "last_ping": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "online",
                "latency_ms": round(self.latency * 1000, 1) if self.latency else 0,
                "guilds_count": len(self.guilds),
                "users_count": len(self.users),
                "pid": os.getpid(),
                "bot_user": str(self.user) if self.user else "DestiFC",
                "is_ready": self.is_ready()
            }
            await database.execute(
                """
                INSERT INTO system_settings (key, value)
                VALUES ('bot_heartbeat', $1::jsonb)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """,
                json.dumps(heartbeat_data)
            )
        except Exception as e:
            print(f"[Heartbeat Loop Error] {e}")

    @bot_heartbeat_loop.before_loop
    async def before_heartbeat_loop(self):
        await self.wait_until_ready()

    @tasks.loop(seconds=5)
    async def remote_signal_listener_loop(self):
        """Listens for remote process control commands (restart, reload cogs, shutdown) from Admin Panel."""
        try:
            jobs = await database.fetch_all(
                """
                SELECT id, job_type, payload
                FROM portal_jobs
                WHERE status = 'pending' AND job_type IN ('SIGNAL_RESTART', 'SIGNAL_SHUTDOWN', 'SIGNAL_RELOAD_COGS', 'SIGNAL_FLUSH_CACHES')
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            for job in jobs:
                job_id = job['id']
                job_type = job['job_type']
                
                await database.execute(
                    "UPDATE portal_jobs SET status = 'completed', result = 'Executed successfully' WHERE id = $1",
                    job_id
                )

                if job_type == 'SIGNAL_RELOAD_COGS':
                    print("[Remote Control] Flushing caches and reloading all bot cogs...")
                    database.flush_all_caches()
                    for filename in os.listdir('./cogs'):
                        if filename.endswith('.py') and not filename.startswith('__'):
                            try:
                                await self.reload_extension(f'cogs.{filename[:-3]}')
                            except Exception as re_err:
                                await self.load_extension(f'cogs.{filename[:-3]}')
                    print("[Remote Control] All caches flushed and cogs reloaded!")

                elif job_type == 'SIGNAL_RESTART':
                    print("[Remote Control] Received restart signal from Admin Panel. Gracefully rebooting...")
                    await self.close()
                    import sys
                    os.execv(sys.executable, [sys.executable] + sys.argv)

                elif job_type == 'SIGNAL_SHUTDOWN':
                    print("[Remote Control] Received shutdown signal from Admin Panel. Closing bot...")
                    await self.close()
                    import sys
                    sys.exit(0)

                elif job_type == 'SIGNAL_FLUSH_CACHES':
                    print("[Remote Control] Flushing all in-memory caches...")
                    database.flush_all_caches()
                    print("[Remote Control] All caches flushed!")
        except Exception as e:
            print(f"[Remote Signal Error] {e}")

    @remote_signal_listener_loop.before_loop
    async def before_signal_listener_loop(self):
        await self.wait_until_ready()

    @tasks.loop(seconds=30)
    async def sync_presence_loop(self):
        try:
            cfg = await database.get_bot_config()
            act_type = cfg.get('presence_activity_type', 'Playing')
            text = cfg.get('presence_status_text', 'FC Mobile 27')
            state = cfg.get('presence_status_state', 'online').lower()

            status_map = {
                'online': discord.Status.online,
                'idle': discord.Status.idle,
                'dnd': discord.Status.dnd
            }
            d_status = status_map.get(state, discord.Status.online)

            if act_type == 'Streaming':
                activity = discord.Streaming(name=text, url="https://twitch.tv/destifc")
            elif act_type == 'Watching':
                activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            elif act_type == 'Listening':
                activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            elif act_type == 'Competing':
                activity = discord.Activity(type=discord.ActivityType.competing, name=text)
            else:
                activity = discord.Game(name=text)

            current_key = f"{act_type}_{text}_{state}"
            if self.last_presence_state != current_key:
                await self.change_presence(activity=activity, status=d_status)
                self.last_presence_state = current_key
        except Exception as e:
            print(f"[Presence Sync Loop Error] {e}")

    @sync_presence_loop.before_loop
    async def before_presence_loop(self):
        await self.wait_until_ready()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = DestiFC()
        bot.run(TOKEN)

