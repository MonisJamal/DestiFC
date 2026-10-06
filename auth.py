import os
import time
import discord

# Strictly restricted: Only the bot owner and co-owner ID 1214258876434878548
AUTHORIZED_ADMIN_IDS = {
    1259402026782294051,  # Owner (_destinix_)
    1214258876434878548   # Co-Owner
}

_APP_OWNER_ID_CACHE = None
_APP_OWNER_CACHE_EXP = 0

async def is_team_admin_or_owner(bot, user: discord.User | discord.Member) -> bool:
    """
    Check if a user is authorized to use admin commands.
    Strictly exclusive to the bot owner and co-owner (1214258876434878548).
    Server administrators or guild owners are strictly disallowed.
    """
    if not user:
        return False

    user_id = getattr(user, 'id', None)
    if not user_id:
        return False

    # 1. Check strict whitelist IDs
    if user_id in AUTHORIZED_ADMIN_IDS:
        return True

    # 2. Check bot instance owner IDs
    if hasattr(bot, "owner_id") and bot.owner_id == user_id:
        return True
    if hasattr(bot, "owner_ids") and bot.owner_ids and user_id in bot.owner_ids:
        return True

    # 3. Check Discord Developer Application Owner
    global _APP_OWNER_ID_CACHE, _APP_OWNER_CACHE_EXP
    now = time.time()
    if now > _APP_OWNER_CACHE_EXP:
        try:
            app = await bot.application_info()
            if app.owner:
                _APP_OWNER_ID_CACHE = app.owner.id
            _APP_OWNER_CACHE_EXP = now + 3600  # Cache for 1 hour
        except Exception:
            _APP_OWNER_CACHE_EXP = now + 60

    if user_id == _APP_OWNER_ID_CACHE:
        return True

    # 4. Optional ADMIN_IDS override from environment variable if provided
    admin_env = os.getenv("ADMIN_IDS", "")
    if admin_env:
        allowed_ids = {int(x.strip()) for x in admin_env.replace(",", " ").split() if x.strip().isdigit()}
        if user_id in allowed_ids:
            return True

    return False

