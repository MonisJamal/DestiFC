

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

class DestiFC(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all(),
            help_command=commands.DefaultHelpCommand()
        )
        self.last_presence_state = None
        self.user_command_cooldowns = {}   # user_id -> timestamp of last command
        self.active_user_commands = set()     # set of user_ids currently running a command

    async def setup_hook(self):
        await database.setup()
        
        async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
            if isinstance(error, discord.app_commands.CommandOnCooldown):
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"⏳ **Cooldown active!** Please wait **{error.retry_after:.1f}s** before using this command again.", ephemeral=True)
            elif isinstance(error, discord.app_commands.MissingPermissions):
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ You lack the permissions to use this command.", ephemeral=True)
            else:
                print(f"[Command Error] {error}")
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)
                    except Exception:
                        pass
        self.tree.on_error = on_tree_error

        # Load all cogs on startup
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"[Startup] Loaded cog: {filename}")
                except Exception as e:
                    print(f"[Startup] Failed to load cog {filename}: {e}")
        asyncio.create_task(database.preload_official_cards_cache())

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

                # Server-Specific Channel Restriction Check
                if interaction.guild and interaction.channel:
                    g_cfg = await database.get_guild_config(interaction.guild.id)
                    bot_chan = g_cfg.get('bot_channel_id')
                    if bot_chan and interaction.channel.id != bot_chan:
                        is_mgr = interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
                        if not is_mgr and cmd_name not in ['setchannel', 'resetchannel', 'help', 'custom_order']:
                            if not interaction.response.is_done():
                                await interaction.response.send_message(
                                    f"⚠️ **Channel Restricted:** In this server, DestiFC commands are restricted to <#{bot_chan}>! Please run your command there.",
                                    ephemeral=True
                                )
                            return False

                # Rate Limiting & Concurrency Guard for application commands (slash commands)
                if interaction.type == discord.InteractionType.application_command:
                    uid = interaction.user.id

                    # 1. Concurrency Guard: prevent running another command while one is still in progress
                    if uid in self.active_user_commands:
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "⏳ **Please wait!** You already have another command running. Please let it finish before running a new one.",
                                ephemeral=True
                            )
                        return False

                    # 2. Command Slowdown Rate Limit: 6 seconds cooldown between commands
                    import time
                    now = time.time()
                    last_cmd_time = self.user_command_cooldowns.get(uid, 0)
                    cooldown_duration = 6.0

                    if now - last_cmd_time < cooldown_duration:
                        rem = round(cooldown_duration - (now - last_cmd_time), 1)
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                f"⏳ **Slow down!** You can use another command in **{rem}s**.",
                                ephemeral=True
                            )
                        return False

                    # Mark user as currently running a command
                    self.active_user_commands.add(uid)

                # Auto-Role Grant for any registered user executing a command
                if bot_cfg.get('auto_role_enabled'):
                    async def _assign_role():
                        try:
                            # 1. Assign in the interaction guild if configured
                            role_id_str = bot_cfg.get('auto_role_id')
                            if interaction.guild and role_id_str:
                                try:
                                    role_id = int(str(role_id_str).strip())
                                    role = interaction.guild.get_role(role_id)
                                    member = interaction.user
                                    if not isinstance(member, discord.Member) or member.guild.id != interaction.guild.id:
                                        try:
                                            member = await interaction.guild.fetch_member(interaction.user.id)
                                        except Exception:
                                            member = interaction.guild.get_member(interaction.user.id)
                                    if member and role and role not in member.roles:
                                        await member.add_roles(role, reason="DestiFC Auto-Role: Registered player command")
                                except Exception as e:
                                    print(f"[Auto-Role Guild Error] {e}")

                            # 2. Specifically ensure BeastlyFC player role is granted to all registered players
                            beastly_id = 1222195412295745536
                            beastly_role_id = 1557010712013045860
                            beastly_guild = self.get_guild(beastly_id)
                            if not beastly_guild:
                                try:
                                    beastly_guild = await self.fetch_guild(beastly_id)
                                except Exception:
                                    pass
                            if beastly_guild:
                                beastly_role = beastly_guild.get_role(beastly_role_id)
                                if beastly_role:
                                    b_member = beastly_guild.get_member(interaction.user.id)
                                    if not b_member:
                                        try:
                                            b_member = await beastly_guild.fetch_member(interaction.user.id)
                                        except Exception:
                                            pass
                                    if b_member and beastly_role not in b_member.roles:
                                        await b_member.add_roles(beastly_role, reason="DestiFC Auto-Role: Registered player in BeastlyFC")
                                        print(f"[Auto-Role] Granted BeastlyFC player role to {b_member.display_name} ({b_member.id})")
                        except Exception as e:
                            print(f"[Auto-Role Exception] Failed to assign role: {e}")

                    asyncio.create_task(_assign_role())

            except Exception as e:
                print(f"[Maintenance Check Error] {e}")
            return True

        # Global command error handler
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            import traceback
            import time
            uid = interaction.user.id
            self.active_user_commands.discard(uid)
            # Only set cooldown if it wasn't a check failure (e.g. cooldown/concurrency checks themselves)
            if not isinstance(error, app_commands.CheckFailure):
                self.user_command_cooldowns[uid] = time.time()

            cmd_name = interaction.command.name if interaction.command else "command"
            if isinstance(error, (app_commands.CheckFailure, app_commands.CommandOnCooldown)):
                print(f"[AppCommand] Command '/{cmd_name}' blocked for user {interaction.user.id} ({interaction.user.display_name}): {error}")
            else:
                print(f"[AppCommandError] Command '/{cmd_name}' failed for user {interaction.user.id} ({interaction.user.display_name}): {error}")
                traceback.print_exception(type(error), error, error.__traceback__)

            msg = f"❌ An unexpected error occurred while executing `/{cmd_name}`. Please try again in a moment."
            if isinstance(error, app_commands.CommandOnCooldown):
                msg = f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s."
            elif isinstance(error, app_commands.CheckFailure):
                msg = "❌ You do not have permission to execute this command."

            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                elif not isinstance(error, app_commands.CheckFailure):
                    await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass

        # Clear any lingering duplicate guild commands so only global commands exist
        for g in self.guilds:
            try:
                self.tree.clear_commands(guild=g)
                await self.tree.sync(guild=g)
            except Exception as e:
                print(f"[Command Sync] Note clearing guild commands for {g.id}: {e}")

        # Sync slash commands globally
        await self.tree.sync()

        # Start dynamic presence and heartbeat sync loops
        self.sync_presence_loop.start()
        self.bot_heartbeat_loop.start()
        self.remote_signal_listener_loop.start()
        self.memory_hygiene_loop.start()
        self.scheduled_renderz_sync_loop.start()

    @tasks.loop(minutes=5)
    async def memory_hygiene_loop(self):
        """Periodically cleans up memory caches and triggers garbage collection to keep container RAM minimal."""
        try:
            import gc, card_generator
            card_generator._MEMORY_IMAGE_CACHE.clear()
            card_generator._MEMORY_CARD_CACHE.clear()
            card_generator._MEMORY_CARD_BYTES_CACHE.clear()
            database.flush_all_caches(silent=True)
            gc.collect()
        except Exception as e:
            print(f"[Memory Hygiene Error] {e}")

    @memory_hygiene_loop.before_loop
    async def before_memory_hygiene_loop(self):
        await self.wait_until_ready()

    @tasks.loop(seconds=10)
    async def bot_heartbeat_loop(self):
        """Sends a high-precision live pulse to Supabase every 10s with real latency and stats."""
        try:
            import datetime
            import json
            import os
            import sys
            import resource

            # Calculate process RSS memory in MB
            try:
                raw_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss_mb = round(raw_rss / (1024 * 1024 if sys.platform == 'darwin' else 1024), 1)
            except Exception:
                rss_mb = 0

            heartbeat_data = {
                "last_ping": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "online",
                "latency_ms": round(self.latency * 1000, 1) if self.latency else 0,
                "guilds_count": len(self.guilds),
                "users_count": len(self.users),
                "pid": os.getpid(),
                "ram_mb": rss_mb,
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
        """Listens for remote process control commands (restart, reload cogs, shutdown, market triggers) from Admin Panel."""
        try:
            jobs = await database.fetch_all(
                """
                SELECT id, job_type, payload
                FROM portal_jobs
                WHERE status = 'pending' AND job_type IN ('mass_dm', 'SIGNAL_RESTART', 'SIGNAL_SHUTDOWN', 'SIGNAL_RELOAD_COGS', 'SIGNAL_FLUSH_CACHES', 'open_black_market', 'open_special_market', 'ANNOUNCE_TOURNAMENT', 'TRIGGER_TOURNAMENT_MATCH', 'SYNC_ALL_MEMBERS_ROLE', 'SYNC_RENDERZ_CARDS')
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            for job in jobs:
                job_id = job['id']
                job_type = job['job_type']

                if job_type == 'ANNOUNCE_TOURNAMENT':
                    match_cog = self.get_cog('MatchCog')
                    if match_cog:
                        res = await match_cog.announce_tournament(job['payload'])
                        is_success = "Successfully" in str(res)
                        await database.execute(
                            "UPDATE portal_jobs SET status = $2, result = $3 WHERE id = $1",
                            job_id, 'completed' if is_success else 'failed', str(res)
                        )
                    else:
                        print("[Remote Control] MatchCog not found in bot cogs!")
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'failed', result = 'MatchCog not found in bot cogs' WHERE id = $1",
                            job_id
                        )
                elif job_type == 'TRIGGER_TOURNAMENT_MATCH':
                    match_cog = self.get_cog('MatchCog')
                    if match_cog:
                        asyncio.create_task(match_cog.trigger_tournament_match(job['payload']))
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'completed', result = 'Match simulation initiated' WHERE id = $1",
                            job_id
                        )
                    else:
                        print("[Remote Control] MatchCog not found in bot cogs!")
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'failed', result = 'MatchCog not found in bot cogs' WHERE id = $1",
                            job_id
                        )
                elif job_type == 'SYNC_ALL_MEMBERS_ROLE':
                    async def bg_sync_members():
                        try:
                            guild_id = 1222195412295745536
                            target_guild = self.get_guild(guild_id)
                            if not target_guild:
                                print(f"[Sync Roles] Guild {guild_id} not cached, fetching...")
                                target_guild = await self.fetch_guild(guild_id)
                            if not target_guild:
                                print(f"[Sync Roles] Guild {guild_id} not found!")
                                return
                            role = discord.utils.get(target_guild.roles, name="DestiFC Players") or target_guild.get_role(1557010712013045860)
                            if not role:
                                print("[Sync Roles] Role DestiFC Players not found!")
                                return
                            count = 0
                            skipped = 0
                            print(f"[Sync Roles] Starting mass role grant for '{role.name}' in {target_guild.name}...")
                            async for m in target_guild.fetch_members(limit=None):
                                if m.bot or role in m.roles:
                                    skipped += 1
                                    continue
                                try:
                                    await m.add_roles(role, reason="DestiFC Mass Auto-Role Sync")
                                    count += 1
                                    if count % 50 == 0:
                                        print(f"[Sync Roles Progress] Assigned to {count} members (skipped {skipped})...")
                                    await asyncio.sleep(0.25)
                                except discord.HTTPException as err:
                                    if err.status == 429:
                                        retry_after = getattr(err, 'retry_after', 2.0)
                                        await asyncio.sleep(retry_after + 0.5)
                                    else:
                                        await asyncio.sleep(0.5)
                                except Exception:
                                    await asyncio.sleep(0.5)
                            print(f"[Sync Roles Complete] Finished! Granted '{role.name}' to {count} members (skipped {skipped}).")
                        except Exception as ex:
                            print(f"[Sync Roles Fatal Error] {ex}")
                    asyncio.create_task(bg_sync_members())
                    await database.execute(
                        "UPDATE portal_jobs SET status = 'completed', result = 'Mass role sync background task started' WHERE id = $1",
                        job_id
                    )
                elif job_type == 'mass_dm':
                    import asyncio
                    import json
                    try:
                        data = json.loads(job['payload'])
                        title = data.get('title', 'Announcement')
                        message = data.get('message', '')
                        
                        async def bg_mass_dm():
                            try:
                                import traceback
                                with open("mass_dm.log", "w") as f:
                                    f.write(f"Starting mass DM for {title}\n")
                                users = await database.fetch_all("SELECT user_id FROM users")
                                count = 0
                                errs = 0
                                for u in users:
                                    try:
                                        user = await self.fetch_user(int(u['user_id']))
                                        if user:
                                            embed = discord.Embed(
                                                title=title,
                                                description=message,
                                                color=discord.Color.purple()
                                            )
                                            await user.send(embed=embed)
                                            count += 1
                                            await asyncio.sleep(2.0) # Rate limit protection
                                    except Exception as e:
                                        errs += 1
                                        with open("mass_dm.log", "a") as f:
                                            f.write(f"Failed to DM {u['user_id']}: {e}\n")
                                        pass
                                with open("mass_dm.log", "a") as f:
                                    f.write(f"[Mass DM] Successfully sent to {count} users. Failed: {errs}\n")
                            except Exception as ex:
                                with open("mass_dm.log", "a") as f:
                                    f.write(f"[Mass DM] Fatal Error: {ex}\n{traceback.format_exc()}\n")
                                
                        asyncio.create_task(bg_mass_dm())
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'completed', result = 'Mass DM blast queued' WHERE id = $1",
                            job_id
                        )
                        print(f"[Mass DM] Queued DM blast for {title}")
                    except Exception as e:
                        print(f"Error parsing mass_dm payload: {e}")
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'failed', result = $2 WHERE id = $1",
                            job_id, f"Error parsing mass_dm payload: {e}"
                        )
                        
                elif job_type == 'SIGNAL_RELOAD_COGS':
                    print("[Remote Control] Flushing caches and reloading all bot cogs...")
                    database.flush_all_caches()
                    reloaded_cogs = []
                    reload_errors = []
                    for filename in os.listdir('./cogs'):
                        if filename.endswith('.py') and not filename.startswith('__'):
                            cog_name = f'cogs.{filename[:-3]}'
                            try:
                                await self.reload_extension(cog_name)
                                reloaded_cogs.append(cog_name)
                            except Exception as re_err:
                                try:
                                    await self.load_extension(cog_name)
                                    reloaded_cogs.append(cog_name)
                                except Exception as le_err:
                                    reload_errors.append(f"{cog_name}: {le_err}")
                                    print(f"[Remote Control] Failed reloading {cog_name}: {le_err}")

                    sync_needed = True
                    synced_info = []

                    # Purge duplicate guild commands so Discord only keeps global commands
                    for g in self.guilds:
                        try:
                            self.tree.clear_commands(guild=g)
                            await self.tree.sync(guild=g)
                        except Exception as g_err:
                            pass

                    try:
                        g_cmds = await self.tree.sync()
                        synced_info.append(f"Global: {len(g_cmds)} commands")
                    except Exception as sync_err:
                        synced_info.append(f"Global sync error: {sync_err}")

                    all_cmds = [c.name for c in self.tree.get_commands()]
                    res_msg = f"Reloaded {len(reloaded_cogs)} cogs. Commands in tree: {all_cmds}. Sync: {synced_info}."
                    if reload_errors:
                        res_msg += f" Errors: {reload_errors}"
                    print(f"[Remote Control] {res_msg}")
                    try:
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'completed', result = $2 WHERE id = $1",
                            job_id, res_msg
                        )
                    except Exception:
                        pass
                    print("[Remote Control] All caches flushed and cogs reloaded successfully!")

                elif job_type == 'SIGNAL_RESTART':
                    print("[Remote Control] Received restart signal from Admin Panel. Gracefully rebooting...")
                    try:
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'completed', result = 'Bot process reboot initiated' WHERE id = $1",
                            job_id
                        )
                    except Exception:
                        pass
                    try:
                        await self.close()
                    except Exception:
                        pass
                    import os
                    os._exit(0)

                elif job_type == 'SIGNAL_SHUTDOWN':
                    print("[Remote Control] Received shutdown signal from Admin Panel. Closing bot...")
                    try:
                        await database.execute(
                            "UPDATE portal_jobs SET status = 'completed', result = 'Bot shutdown executed' WHERE id = $1",
                            job_id
                        )
                    except Exception:
                        pass
                    try:
                        await self.close()
                    except Exception:
                        pass
                    import os
                    os._exit(0)

                elif job_type == 'open_black_market':
                    print("[Remote Control] Received open_black_market signal from Admin Panel! Triggering opening...")
                    try:
                        bm_cog = self.get_cog('BlackMarketCog')
                        if bm_cog:
                            await bm_cog.trigger_market_opening(force=True)
                            print("[Remote Control] Black Market successfully opened and announced via remote signal!")
                            await database.execute("UPDATE portal_jobs SET status = 'completed', result = 'Black Market opened successfully' WHERE id = $1", job_id)
                        else:
                            print("[Remote Control] BlackMarketCog not loaded!")
                            await database.execute("UPDATE portal_jobs SET status = 'failed', result = 'BlackMarketCog not loaded' WHERE id = $1", job_id)
                    except Exception as bm_err:
                        import traceback
                        err_str = f"{type(bm_err).__name__}: {bm_err}"
                        print(f"[Remote Control] Error triggering Black Market opening: {err_str}\n{traceback.format_exc()}")
                        await database.execute("UPDATE portal_jobs SET status = 'failed', result = $2 WHERE id = $1", job_id, err_str or "Unknown error")

                elif job_type == 'open_special_market':
                    print("[Remote Control] Received open_special_market signal from Admin Panel! Triggering VIP market...")
                    try:
                        import json
                        p_data = {}
                        if job.get('payload'):
                            try:
                                p_data = json.loads(job['payload']) if isinstance(job['payload'], str) else job['payload']
                            except Exception:
                                pass
                        dur = p_data.get('duration_minutes') if isinstance(p_data, dict) else None
                        bm_cog = self.get_cog('BlackMarketCog')
                        if bm_cog:
                            await bm_cog.trigger_special_market_opening(duration_minutes=dur)
                            print(f"[Remote Control] VIP Special Market successfully opened (duration: {dur or 'default'}m) and announced via remote signal!")
                            await database.execute("UPDATE portal_jobs SET status = 'completed', result = 'VIP Special Market opened successfully' WHERE id = $1", job_id)
                        else:
                            print("[Remote Control] BlackMarketCog not loaded!")
                            await database.execute("UPDATE portal_jobs SET status = 'failed', result = 'BlackMarketCog not loaded' WHERE id = $1", job_id)
                    except Exception as bm_err:
                        import traceback
                        err_str = f"{type(bm_err).__name__}: {bm_err}"
                        print(f"[Remote Control] Error triggering VIP Special Market opening: {err_str}\n{traceback.format_exc()}")
                        await database.execute("UPDATE portal_jobs SET status = 'failed', result = $2 WHERE id = $1", job_id, err_str or "Unknown error")

                elif job_type == 'SIGNAL_FLUSH_CACHES':
                    print("[Remote Control] Flushing all in-memory caches...")
                    database.flush_all_caches()
                    await database.execute("UPDATE portal_jobs SET status = 'completed', result = 'All caches flushed' WHERE id = $1", job_id)
                    print("[Remote Control] All caches flushed!")

                elif job_type == 'SYNC_RENDERZ_CARDS':
                    print("[Remote Control] Received SYNC_RENDERZ_CARDS signal! Starting background RenderZ sync...")
                    async def bg_sync(jid):
                        try:
                            from renderz_sync import sync_renderz_cards
                            res = await sync_renderz_cards(min_ovr=105, max_ovr=125, fetch_leaks=True)
                            msg = f"Synced {res['scraped']} cards ({res['new_cards_added']} new). Total in DB: {res['total_official_cards']}"
                            await database.execute("UPDATE portal_jobs SET status = 'completed', result = $2 WHERE id = $1", jid, msg)
                            print(f"[Remote Control] RenderZ sync completed: {msg}")
                        except Exception as e:
                            print(f"[Remote Control] RenderZ sync error: {e}")
                            await database.execute("UPDATE portal_jobs SET status = 'failed', result = $2 WHERE id = $1", jid, str(e))
                    asyncio.create_task(bg_sync(job_id))
        except Exception as e:
            print(f"[Remote Signal Error] {e}")

    @remote_signal_listener_loop.before_loop
    async def before_signal_listener_loop(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def scheduled_renderz_sync_loop(self):
        """Automatically runs twice a day at 10:00 AM IST and 10:00 PM IST (04:30 UTC and 16:30 UTC)."""
        try:
            import datetime
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            # IST = UTC + 5h30m
            ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)

            # Trigger at 10:00 AM (10:00) or 10:00 PM (22:00) IST
            is_10am = (ist_now.hour == 10 and ist_now.minute == 0)
            is_10pm = (ist_now.hour == 22 and ist_now.minute == 0)

            current_slot = f"{ist_now.strftime('%Y-%m-%d')}_{ist_now.hour}"
            if (is_10am or is_10pm) and getattr(self, 'last_renderz_sync_slot', None) != current_slot:
                self.last_renderz_sync_slot = current_slot
                print(f"[RenderZ Scheduler] Triggering automatic card sync at {ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST...")
                from renderz_sync import sync_renderz_cards
                res = await sync_renderz_cards(min_ovr=105, max_ovr=125, fetch_leaks=True)
                print(f"[RenderZ Scheduler] Auto-sync finished: {res}")
        except Exception as e:
            print(f"[RenderZ Scheduler Error] {e}")

    @scheduled_renderz_sync_loop.before_loop
    async def before_renderz_sync_loop(self):
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

    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command):
        import time
        uid = interaction.user.id
        self.active_user_commands.discard(uid)
        self.user_command_cooldowns[uid] = time.time()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = DestiFC()
        bot.run(TOKEN)

