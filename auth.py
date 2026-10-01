import os
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

async def is_team_admin_or_owner(bot, user: discord.User | discord.Member) -> bool:
    """
    Check if a user is authorized to use admin commands.
    Checks:
    1. Bot Owner (bot.is_owner, bot.owner_id, bot.owner_ids)
    2. Explicit Authorized Usernames / Whitelist (e.g. 7blank7)
    3. Discord Developer Portal Team Members (all team members)
    4. Server Administrators (users with Administrator or Manage Guild permissions in the server)
    5. Explicit ADMIN_IDS / TEAM_IDS in environment variables
    """
    if not user:
        return False

    user_id = user.id
    if user_id in KNOWN_ADMIN_IDS:
        return True

    # 1. Check explicit username whitelist
    u_name = str(getattr(user, "name", "")).lower()
    u_global = str(getattr(user, "global_name", "") or "").lower()
    u_display = str(getattr(user, "display_name", "") or "").lower()
    if u_name in AUTHORIZED_ADMIN_NAMES or u_global in AUTHORIZED_ADMIN_NAMES or u_display in AUTHORIZED_ADMIN_NAMES:
        return True

    # 2. Check explicit env list if provided
    admin_env = os.getenv("ADMIN_IDS", "") or os.getenv("ADMIN_USER_IDS", "") or os.getenv("TEAM_USER_IDS", "")
    if admin_env:
        allowed_ids = {int(x.strip()) for x in admin_env.replace(",", " ").split() if x.strip().isdigit()}
        if user_id in allowed_ids:
            return True

    # 3. Check bot owner in discord.py
    try:
        if await bot.is_owner(user):
            return True
    except Exception:
        pass

    if hasattr(bot, "owner_id") and bot.owner_id == user_id:
        return True
    if hasattr(bot, "owner_ids") and bot.owner_ids and user_id in bot.owner_ids:
        return True

    # 4. Check Discord Developer Portal Application Team (both accepted & all team members)
    try:
        app = await bot.application_info()
        if app.team:
            for member in app.team.members:
                m_id = getattr(member, "id", None)
                u_id = getattr(getattr(member, "user", None), "id", None)
                if user_id in (m_id, u_id):
                    return True
        elif app.owner and app.owner.id == user_id:
            return True
    except Exception:
        pass

    # 5. Check Server Administrator permissions if user is interacting within a guild
    if isinstance(user, discord.Member):
        if getattr(user.guild_permissions, "administrator", False) or getattr(user.guild_permissions, "manage_guild", False):
            return True
        if getattr(user.guild, "owner_id", None) == user_id:
            return True

    return False
