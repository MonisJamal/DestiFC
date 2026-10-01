import os
import time
import discord

AUTHORIZED_ADMIN_NAMES = {"7blank7"}
KNOWN_ADMIN_IDS = {
    1214258876434878548, 
    1259402026782294051, 
    982226459680706601, 
    485160482748235827, 
    1271513098565586944, 
    731503880654946365
}

_APP_TEAM_IDS_CACHE = set()
_APP_TEAM_CACHE_EXP = 0

async def is_team_admin_or_owner(bot, user: discord.User | discord.Member) -> bool:
    """
    Check if a user is authorized to use admin commands.
    Fully in-memory and cached to avoid blocking Discord API rate limits on interactions.
    """
    if not user:
        return False

    user_id = getattr(user, 'id', None)
    if not user_id:
        return False

    # 1. Check known static admin IDs (instant in-memory)
    if user_id in KNOWN_ADMIN_IDS:
        return True

    # 2. Check bot owner IDs from client instance
    if hasattr(bot, "owner_id") and bot.owner_id == user_id:
        return True
    if hasattr(bot, "owner_ids") and bot.owner_ids and user_id in bot.owner_ids:
        return True

    # 3. Check explicit username whitelist (e.g. 7blank7)
    u_name = str(getattr(user, "name", "") or "").lower()
    u_global = str(getattr(user, "global_name", "") or "").lower()
    u_display = str(getattr(user, "display_name", "") or "").lower()
    if u_name in AUTHORIZED_ADMIN_NAMES or u_global in AUTHORIZED_ADMIN_NAMES or u_display in AUTHORIZED_ADMIN_NAMES:
        return True

    # 4. Check explicit environment variable list
    admin_env = os.getenv("ADMIN_IDS", "") or os.getenv("ADMIN_USER_IDS", "") or os.getenv("TEAM_USER_IDS", "")
    if admin_env:
        allowed_ids = {int(x.strip()) for x in admin_env.replace(",", " ").split() if x.strip().isdigit()}
        if user_id in allowed_ids:
            return True

    # 5. Check cached Discord Developer Application Team
    global _APP_TEAM_IDS_CACHE, _APP_TEAM_CACHE_EXP
    now = time.time()
    if now > _APP_TEAM_CACHE_EXP:
        try:
            app = await bot.application_info()
            team_ids = set()
            if app.team:
                for member in app.team.members:
                    m_id = getattr(member, "id", None)
                    u_id = getattr(getattr(member, "user", None), "id", None)
                    if m_id: team_ids.add(m_id)
                    if u_id: team_ids.add(u_id)
            if app.owner:
                team_ids.add(app.owner.id)
            _APP_TEAM_IDS_CACHE = team_ids
            _APP_TEAM_CACHE_EXP = now + 3600  # Cache for 1 hour
        except Exception:
            _APP_TEAM_CACHE_EXP = now + 60  # Retry in 1 min on fail

    if user_id in _APP_TEAM_IDS_CACHE:
        return True

    # 6. Check Server Administrator permissions if user is interacting within a guild
    if isinstance(user, discord.Member):
        if getattr(user.guild_permissions, "administrator", False) or getattr(user.guild_permissions, "manage_guild", False):
            return True
        if getattr(user.guild, "owner_id", None) == user_id:
            return True

    return False
