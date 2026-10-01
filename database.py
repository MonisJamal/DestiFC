import asyncpg
import json
import asyncio
import os
import datetime

DB_FILE = "destifc.db"
SUPABASE_URL = os.getenv("DATABASE_URL", os.getenv("SUPABASE_URL", "postgresql://neondb_owner:npg_EZ7gQ4pOFNYU@ep-dry-thunder-b1l2ju9a.c-5.eu-central-1.aws.neon.tech/neondb?sslmode=require"))

import time

# Global connection pool & fast memory caches
_pool = None
_DRAFTS_CACHE = None
_DRAFTS_CACHE_EXP = 0
_LAYOUTS_CACHE = None
_LAYOUTS_CACHE_EXP = 0
_USER_INVENTORY_CACHE = {}  # {user_id: {"data": list, "exp": timestamp}}
_USER_SQUAD_CACHE = {}      # {user_id: {"data": dict, "exp": timestamp}}
_USER_CACHE = {}            # {user_id: {"data": dict, "exp": timestamp}}

def flush_all_caches():
    """Flush every in-memory cache. Call after SIGNAL_RELOAD_COGS or panel auto-fix."""
    global _DRAFTS_CACHE, _DRAFTS_CACHE_EXP, _LAYOUTS_CACHE, _LAYOUTS_CACHE_EXP
    global _BOT_CONFIG_CACHE, _BOT_CONFIG_CACHE_EXP, _GAMEPLAY_CACHE, _GAMEPLAY_CACHE_EXP
    global _CUSTOM_DRAFT_CARDS_CACHE
    _DRAFTS_CACHE = None
    _DRAFTS_CACHE_EXP = 0
    _LAYOUTS_CACHE = None
    _LAYOUTS_CACHE_EXP = 0
    _USER_INVENTORY_CACHE.clear()
    _USER_SQUAD_CACHE.clear()
    _USER_CACHE.clear()
    try:
        _BOT_CONFIG_CACHE = None  # noqa: F841 – reset handled via global
        _BOT_CONFIG_CACHE_EXP = 0
    except Exception:
        pass
    try:
        _GAMEPLAY_CACHE = None
        _GAMEPLAY_CACHE_EXP = 0
    except Exception:
        pass
    try:
        _CUSTOM_DRAFT_CARDS_CACHE = None
    except Exception:
        pass
    print("[Database] All in-memory caches flushed!")

import ssl

async def get_db():
    global _pool
    if _pool is None or getattr(_pool, '_closed', False):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _pool = await asyncpg.create_pool(
            SUPABASE_URL,
            ssl=ctx,
            min_size=2,
            max_size=25,
            command_timeout=20,
            timeout=20,
            max_inactive_connection_lifetime=180.0,
            statement_cache_size=0
        )
    return _pool

async def execute(query_str: str, *args):
    p = await get_db()
    return await p.execute(query_str, *args)

async def fetch_all(query_str: str, *args):
    p = await get_db()
    return await p.fetch(query_str, *args)

async def fetch_one(query_str: str, *args):
    p = await get_db()
    return await p.fetchrow(query_str, *args)

async def fetch_val(query_str: str, *args):
    p = await get_db()
    return await p.fetchval(query_str, *args)

async def setup():
    """Initializes the database pool and verifies schema."""
    p = await get_db()
    print("✅ Neon PostgreSQL Connected and Verified!")

def _sanitize_user_dict(d: dict, user_id: int) -> dict:
    return {
        "user_id": user_id,
        "coins": int(d.get("coins") or 0),
        "vouchers": int(d.get("vouchers") or 0),
        "gems": int(d.get("gems") or 0),
        "fans": int(d.get("fans") or 0),
        "drafts_opened": int(d.get("drafts_opened") or 0),
        "drafts_since_walkout": int(d.get("drafts_since_walkout") or 0),
        "is_private": int(d.get("is_private") or 0),
        "last_quest_daily": int(d.get("last_quest_daily") or 0),
        "last_quest_skill": int(d.get("last_quest_skill") or 0),
        "last_quest_h2h": int(d.get("last_quest_h2h") or 0),
        "last_quest_freekick": int(d.get("last_quest_freekick") or 0),
        "last_quest_dribble": int(d.get("last_quest_dribble") or 0),
        "last_quest_trivia": int(d.get("last_quest_trivia") or 0),
        "last_quest_gk": int(d.get("last_quest_gk") or 0),
        "last_quest_volley": int(d.get("last_quest_volley") or 0),
        "last_daily": int(d.get("last_daily") or 0),
        "last_work": int(d.get("last_work") or 0),
        "last_match_time": int(d.get("last_match_time") or 0),
        "draft_battle_wins": int(d.get("draft_battle_wins") or 0),
        "draft_battle_losses": int(d.get("draft_battle_losses") or 0),
        "draft_battle_draws": int(d.get("draft_battle_draws") or 0),
        "draft_battle_elo": int(d.get("draft_battle_elo") or 1000),
        "draft_battle_points": int(d.get("draft_battle_points") or 0),
        "daily_vouchers_bought": int(d.get("daily_vouchers_bought") or 0),
        "last_voucher_buy_date": str(d.get("last_voucher_buy_date") or ""),
        "draft_pity": d.get("draft_pity") or {}
    }

async def get_user(user_id: int) -> dict:
    p = await get_db()
    row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    if row:
        return _sanitize_user_dict(dict(row), user_id)
    else:
        await p.execute('INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id)
        row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        if row:
            return _sanitize_user_dict(dict(row), user_id)
        return _sanitize_user_dict({}, user_id)

async def add_coins(user_id: int, amount: int):
    p = await get_db()
    await p.execute(
        'UPDATE users SET coins = GREATEST(0, COALESCE(coins, 0) + $1) WHERE user_id = $2',
        int(amount), user_id
    )

async def update_coins(user_id: int, amount: int):
    await add_coins(user_id, amount)

async def add_vouchers(user_id: int, amount: int):
    p = await get_db()
    await p.execute(
        'UPDATE users SET vouchers = GREATEST(0, COALESCE(vouchers, 0) + $1) WHERE user_id = $2',
        int(amount), user_id
    )

async def update_vouchers(user_id: int, amount: int):
    await add_vouchers(user_id, amount)

async def get_daily_vouchers_bought(user_id: int) -> int:
    p = await get_db()
    row = await p.fetchrow('SELECT daily_vouchers_bought, last_voucher_buy_date FROM users WHERE user_id = $1', user_id)
    if not row:
        return 0
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if row['last_voucher_buy_date'] != today:
        return 0
    return int(row['daily_vouchers_bought'] or 0)

async def record_vouchers_bought(user_id: int, amount: int):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    p = await get_db()
    row = await p.fetchrow('SELECT daily_vouchers_bought, last_voucher_buy_date FROM users WHERE user_id = $1', user_id)
    current = 0
    if row and row['last_voucher_buy_date'] == today:
        current = int(row['daily_vouchers_bought'] or 0)
    new_total = current + int(amount)

    await p.execute('''
        UPDATE users 
        SET daily_vouchers_bought = $1, last_voucher_buy_date = $2
        WHERE user_id = $3
    ''', new_total, today, user_id)

async def update_gems(user_id: int, amount: int):
    p = await get_db()
    await p.execute(
        'UPDATE users SET gems = GREATEST(0, COALESCE(gems, 0) + $1) WHERE user_id = $2',
        int(amount), user_id
    )

async def add_fans(user_id: int, amount: int):
    p = await get_db()
    await p.execute(
        'UPDATE users SET fans = GREATEST(0, COALESCE(fans, 0) + $1) WHERE user_id = $2',
        int(amount), user_id
    )

async def increment_drafts(user_id: int, amount: int = 1):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['drafts_opened'] = int(_USER_CACHE[user_id]['data'].get('drafts_opened', 0) or 0) + int(amount)
    p = await get_db()
    await p.execute(
        'UPDATE users SET drafts_opened = COALESCE(drafts_opened, 0) + $1 WHERE user_id = $2',
        int(amount), user_id
    )

async def get_leaderboard(limit: int = 10):
    p = await get_db()
    rows = await p.fetch('SELECT user_id, fans FROM users ORDER BY fans DESC LIMIT $1', limit)
    return [dict(r) for r in rows]

async def get_coins_leaderboard(limit: int = 10):
    p = await get_db()
    rows = await p.fetch('SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT $1', limit)
    return [dict(r) for r in rows]

async def get_vouchers_leaderboard(limit: int = 10):
    p = await get_db()
    rows = await p.fetch('SELECT user_id, vouchers FROM users ORDER BY vouchers DESC LIMIT $1', limit)
    return [dict(r) for r in rows]

async def set_highest_div(user_id: int, div: str):
    pass

async def set_starter_claimed(user_id: int):
    pass

async def get_user_rank(user_id: int) -> dict:
    p = await get_db()
    try:
        user_fans = await p.fetchval('SELECT fans FROM users WHERE user_id = $1', user_id)
        if user_fans is None:
            user_fans = 0
        rank = await p.fetchval('SELECT COUNT(*) + 1 FROM users WHERE fans > $1', user_fans)
        total = await p.fetchval('SELECT COUNT(*) FROM users')
        return {"rank": int(rank or 1), "fans": int(user_fans), "total_users": int(total or 1)}
    except Exception as e:
        print(f"[Database] Error getting user rank: {e}")
        return {"rank": 1, "fans": 0, "total_users": 1}

async def add_player_to_inventory(user_id: int, player_data: dict):
    await add_players_to_inventory_batch(user_id, [player_data])

async def add_players_to_inventory_batch(user_id: int, player_list: list):
    if not player_list:
        return
    _USER_INVENTORY_CACHE.pop(user_id, None)
    p = await get_db()
    records = []
    for player_data in player_list:
        player_id = str(player_data.get('id', 'unknown'))
        player_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
        ovr = player_data.get('rating', 0)
        pos = str(player_data.get('position') or player_data.get('pos') or player_data.get('cardPosition') or 'ST').strip().upper()
        data_str = json.dumps(player_data)
        records.append((user_id, player_id, player_name, ovr, pos, data_str))
    
    await p.executemany(
        'INSERT INTO inventory (user_id, player_id, player_name, ovr, position, player_data) VALUES ($1, $2, $3, $4, $5, $6)',
        records
    )

async def get_inventory_light(user_id: int) -> list:
    """Ultra fast inventory query without transferring heavy player_data JSON."""
    now = time.time()
    if user_id in _USER_INVENTORY_CACHE:
        cached = _USER_INVENTORY_CACHE[user_id]
        if now - cached['exp'] < 300:
            return cached['data']
    p = await get_db()
    rows = await p.fetch(
        'SELECT id, user_id, player_id, player_name, ovr, position, locked FROM inventory WHERE user_id = $1 ORDER BY ovr DESC, id DESC',
        user_id
    )
    inv = [dict(r) for r in rows]
    _USER_INVENTORY_CACHE[user_id] = {"data": inv, "exp": now}
    return inv

async def get_inventory(user_id: int, full: bool = True) -> list:
    now = time.time()
    if user_id in _USER_INVENTORY_CACHE:
        cached = _USER_INVENTORY_CACHE[user_id]
        if now - cached['exp'] < 120:
            return cached['data']
    p = await get_db()
    rows = await p.fetch(
        'SELECT id, user_id, player_id, player_name, ovr, position, locked, player_data FROM inventory WHERE user_id = $1 ORDER BY ovr DESC, id DESC',
        user_id
    )
    inv = [dict(r) for r in rows]
    _USER_INVENTORY_CACHE[user_id] = {"data": inv, "exp": now}
    return inv

async def get_inventory_autocomplete(user_id: int, search: str = "") -> list:
    now = time.time()
    clean_search = (search or "").strip().lower()
    
    # Check in-memory inventory cache first for 0ms instantaneous autocomplete response
    if user_id in _USER_INVENTORY_CACHE:
        cached = _USER_INVENTORY_CACHE[user_id]
        if now - cached['exp'] < 20:
            inv = cached['data']
            if clean_search:
                results = [
                    p for p in inv 
                    if clean_search in str(p.get('player_name', '')).lower() 
                    or clean_search in str(p.get('id', ''))
                ]
            else:
                results = inv
            return results[:25]

    p = await get_db()
    try:
        if clean_search:
            rows = await asyncio.wait_for(p.fetch(
                '''SELECT id, player_name, ovr, player_data, locked 
                   FROM inventory 
                   WHERE user_id = $1 AND (player_name ILIKE $2 OR id::text LIKE $2) 
                   ORDER BY ovr DESC, id DESC 
                   LIMIT 25''',
                user_id, f"%{clean_search}%"
            ), timeout=1.8)
        else:
            rows = await asyncio.wait_for(p.fetch(
                '''SELECT id, player_name, ovr, player_data, locked 
                   FROM inventory 
                   WHERE user_id = $1 
                   ORDER BY ovr DESC, id DESC 
                   LIMIT 25''',
                user_id
            ), timeout=1.8)
        return [dict(r) for r in rows]
    except Exception:
        return []

async def get_inventory_size(user_id: int) -> int:
    p = await get_db()
    val = await p.fetchval('SELECT COUNT(*) FROM inventory WHERE user_id = $1', user_id)
    return int(val or 0)

async def remove_players_from_inventory(user_id: int, inventory_ids: list):
    if not inventory_ids:
        return
    _USER_INVENTORY_CACHE.pop(user_id, None)
    p = await get_db()
    int_ids = [int(x) for x in inventory_ids]
    await p.execute(
        'DELETE FROM inventory WHERE user_id = $1 AND id = ANY($2::bigint[])',
        user_id, int_ids
    )

async def get_squad(user_id: int) -> dict:
    now = time.time()
    if user_id in _USER_SQUAD_CACHE:
        cached = _USER_SQUAD_CACHE[user_id]
        if now - cached['exp'] < 30:
            return cached['data']

    await get_user(user_id)
    p = await get_db()
    row = await p.fetchrow('SELECT active_squad FROM squads WHERE user_id = $1', user_id)
    if row and row['active_squad']:
        try:
            data = json.loads(row['active_squad'])
        except Exception:
            data = {}
        if "formation" not in data:
            data = {"formation": "4-3-3 Flat", "players": data.get("players", data)}
        if "tactic" not in data:
            data["tactic"] = "Tiki-Taka"
        _USER_SQUAD_CACHE[user_id] = {"data": data, "exp": now}
        return data
    
    default_squad = {
        "formation": "4-3-3 Flat",
        "tactic": "Tiki-Taka",
        "players": {
            "LW": None, "ST": None, "RW": None,
            "CM1": None, "CM2": None, "CM3": None,
            "LB": None, "CB1": None, "CB2": None, "RB": None,
            "GK": None
        }
    }
    await p.execute(
        'INSERT INTO squads (user_id, active_squad) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET active_squad = $2',
        user_id, json.dumps(default_squad)
    )
    _USER_SQUAD_CACHE[user_id] = {"data": default_squad, "exp": now}
    return default_squad

async def update_squad(user_id: int, squad: dict):
    _USER_SQUAD_CACHE[user_id] = {"data": squad, "exp": time.time()}
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'INSERT INTO squads (user_id, active_squad) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET active_squad = $2',
        user_id, json.dumps(squad)
    )

async def save_squad(user_id: int, squad: dict):
    await update_squad(user_id, squad)

async def get_player_by_inv_id(user_id: int, inv_id: int):
    p = await get_db()
    row = await p.fetchrow('SELECT * FROM inventory WHERE id = $1 AND user_id = $2', int(inv_id), user_id)
    if row:
        return dict(row)
    return None

async def lock_player(user_id: int, inv_id: int):
    _USER_INVENTORY_CACHE.pop(user_id, None)
    p = await get_db()
    await p.execute('UPDATE inventory SET locked = 1 WHERE id = $1 AND user_id = $2', int(inv_id), user_id)

async def unlock_player(user_id: int, inv_id: int):
    _USER_INVENTORY_CACHE.pop(user_id, None)
    p = await get_db()
    await p.execute('UPDATE inventory SET locked = 0 WHERE id = $1 AND user_id = $2', int(inv_id), user_id)

async def get_squad_locked_ids(user_id: int) -> set:
    squad = await get_squad(user_id)
    locked = set()
    if not squad or "players" not in squad:
        return locked
    for slot, player in squad["players"].items():
        if not player or not isinstance(player, dict):
            continue
        inv_id = player.get("inv_id") or player.get("inventory_id") or player.get("id")
        if inv_id is not None:
            locked.add(int(inv_id))
    return locked

def _parse_timestamp(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(val, fmt)
            except Exception:
                pass
        try:
            return datetime.datetime.fromisoformat(val.replace("Z", ""))
        except Exception:
            return datetime.datetime.now()
    return datetime.datetime.now()

def _format_timestamp(val) -> str:
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val) if val is not None else ""

_CUSTOM_DRAFT_CARDS_CACHE = None

async def get_active_drafts():
    global _DRAFTS_CACHE
    if _DRAFTS_CACHE is not None:
        return _DRAFTS_CACHE
        
    p = await get_db()
    rows = await p.fetch("SELECT draft_number, pool_a, pool_b, pool_c, expires_at FROM global_drafts")
    if not rows:
        return None
    drafts = {}
    for r in rows:
        drafts[r['draft_number']] = {
            "pool_a": json.loads(r['pool_a']) if r.get('pool_a') else [],
            "pool_b": json.loads(r['pool_b']) if r.get('pool_b') else [],
            "pool_c": json.loads(r['pool_c']) if r.get('pool_c') else [],
            "expires_at": _format_timestamp(r['expires_at'])
        }
    _DRAFTS_CACHE = drafts
    return drafts

async def set_active_drafts(drafts_dict):
    global _DRAFTS_CACHE
    _DRAFTS_CACHE = drafts_dict
    p = await get_db()
    await p.execute("DELETE FROM global_drafts")
    for d_num, data in drafts_dict.items():
        exp = _parse_timestamp(data.get("expires_at"))
        pool_a_json = json.dumps(data.get("pool_a", []))
        pool_b_json = json.dumps(data.get("pool_b", []))
        pool_c_json = json.dumps(data.get("pool_c", []))
        await p.execute(
            "INSERT INTO global_drafts (draft_number, draft_data, pool_a, pool_b, pool_c, expires_at) VALUES ($1, $2, $3, $4, $5, $6)",
            int(d_num), json.dumps(data), pool_a_json, pool_b_json, pool_c_json, exp
        )

async def get_store_player_shop():
    p = await get_db()
    rows = await p.fetch("SELECT slot, player_data, price, expires_at FROM store_player_shop ORDER BY slot ASC")
    items = []
    for r in rows:
        items.append({
            "slot": r['slot'],
            "player": json.loads(r['player_data']),
            "price": r['price'],
            "expires_at": _format_timestamp(r['expires_at'])
        })
    return items

async def set_store_player_shop(items: list):
    p = await get_db()
    await p.execute("DELETE FROM store_player_shop")
    for idx, item in enumerate(items, start=1):
        slot = item.get('slot') or idx
        p_data = item.get('player_data') or item.get('player') or {}
        exp = _parse_timestamp(item.get("expires_at"))
        await p.execute(
            "INSERT INTO store_player_shop (slot, player_data, price, expires_at) VALUES ($1, $2, $3, $4)",
            int(slot), json.dumps(p_data), item['price'], exp
        )

_EXCHANGE_POOL_CACHE = None

async def get_active_exchange_pool():
    global _EXCHANGE_POOL_CACHE
    if _EXCHANGE_POOL_CACHE is not None:
        return _EXCHANGE_POOL_CACHE
    p = await get_db()
    try:
        row = await p.fetchrow("SELECT pool_data, expires_at FROM global_exchange_pool WHERE id = 1")
        if not row or not row['pool_data']:
            return None
        data = json.loads(row['pool_data'])
        data['expires_at'] = _format_timestamp(row['expires_at'])
        _EXCHANGE_POOL_CACHE = data
        return data
    except Exception:
        return None

async def set_active_exchange_pool(pool_dict: dict):
    global _EXCHANGE_POOL_CACHE
    _EXCHANGE_POOL_CACHE = pool_dict
    p = await get_db()
    try:
        exp = _parse_timestamp(pool_dict.get("expires_at"))
        pool_json = json.dumps(pool_dict)
        await p.execute('''
            INSERT INTO global_exchange_pool (id, pool_data, expires_at)
            VALUES (1, $1, $2)
            ON CONFLICT (id) DO UPDATE SET
                pool_data = $1,
                expires_at = $2
        ''', pool_json, exp)
    except Exception as e:
        print(f"[Database] Error setting active exchange pool: {e}")

async def add_custom_draft_card(player_data):
    global _CUSTOM_DRAFT_CARDS_CACHE
    _CUSTOM_DRAFT_CARDS_CACHE = None
    p = await get_db()
    await p.execute('INSERT INTO custom_draft_cards (player_data) VALUES ($1)', json.dumps(player_data))

async def update_single_draft(draft_number: int, draft_data: dict):
    global _DRAFTS_CACHE
    p = await get_db()
    exp = _parse_timestamp(draft_data.get("expires_at"))
    pool_a_json = json.dumps(draft_data.get("pool_a", []))
    pool_b_json = json.dumps(draft_data.get("pool_b", []))
    pool_c_json = json.dumps(draft_data.get("pool_c", []))
    
    await p.execute('''
        INSERT INTO global_drafts (draft_number, draft_data, pool_a, pool_b, pool_c, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (draft_number) DO UPDATE SET
            draft_data = $2,
            pool_a = $3,
            pool_b = $4,
            pool_c = $5,
            expires_at = $6
    ''', int(draft_number), json.dumps(draft_data), pool_a_json, pool_b_json, pool_c_json, exp)
    
    if _DRAFTS_CACHE is not None:
        _DRAFTS_CACHE[int(draft_number)] = draft_data
        _DRAFTS_CACHE[str(draft_number)] = draft_data

async def decrement_custom_card_supply(card_data: dict) -> dict:
    """
    Decrements the available supply of a custom card when pulled.
    If supply drops to 0 or less, deletes the card from custom_draft_cards and flags as exhausted.
    """
    if not isinstance(card_data, dict):
        return {"exhausted": False, "card": card_data}

    card_id = str(card_data.get('id') or card_data.get('custom_id') or card_data.get('assetId') or '')
    card_name = card_data.get('cardName') or card_data.get('player_name') or ''
    
    p = await get_db()
    try:
        rows = await p.fetch('SELECT id, player_data FROM custom_draft_cards')
        for r in rows:
            try:
                pd = json.loads(r['player_data']) if isinstance(r['player_data'], str) else r['player_data']
            except Exception:
                continue
                
            r_id = str(r['id'])
            p_id = str(pd.get('id') or '')
            p_name = pd.get('cardName') or pd.get('player_name') or ''
            
            # Match card
            is_match = False
            if card_id and (card_id == r_id or card_id == p_id):
                is_match = True
            elif card_name and card_name == p_name:
                is_match = True

            if is_match:
                supply = pd.get('supply')
                if supply is not None:
                    try:
                        cur_supply = int(supply)
                    except (ValueError, TypeError):
                        continue
                        
                    new_supply = cur_supply - 1
                    global _CUSTOM_DRAFT_CARDS_CACHE
                    _CUSTOM_DRAFT_CARDS_CACHE = None
                    
                    if new_supply <= 0:
                        # Supply finished! Remove completely so it can no longer be pulled or rolled
                        await p.execute('DELETE FROM custom_draft_cards WHERE id = $1', r['id'])
                        pd['supply'] = 0
                        print(f"[Database] Custom Card '{p_name}' supply EXHAUSTED (0 remaining). Deleted from active pool.")
                        return {"exhausted": True, "card": pd, "db_id": r['id']}
                    else:
                        pd['supply'] = new_supply
                        await p.execute('UPDATE custom_draft_cards SET player_data = $1 WHERE id = $2', json.dumps(pd), r['id'])
                        print(f"[Database] Custom Card '{p_name}' supply decremented -> {new_supply} remaining.")
                        return {"exhausted": False, "card": pd, "remaining_supply": new_supply, "db_id": r['id']}
    except Exception as e:
        print(f"[Database] Error in decrement_custom_card_supply: {e}")

    return {"exhausted": False, "card": card_data}

async def get_all_custom_draft_cards():
    global _CUSTOM_DRAFT_CARDS_CACHE, _CUSTOM_DRAFT_CARDS_EXP
    now = time.time()
    if _CUSTOM_DRAFT_CARDS_CACHE is not None and now < _CUSTOM_DRAFT_CARDS_EXP:
        return _CUSTOM_DRAFT_CARDS_CACHE
    p = await get_db()
    try:
        rows = await p.fetch('SELECT player_data FROM custom_draft_cards')
        _CUSTOM_DRAFT_CARDS_CACHE = [json.loads(r['player_data']) for r in rows]
        _CUSTOM_DRAFT_CARDS_EXP = now + 120.0
        return _CUSTOM_DRAFT_CARDS_CACHE
    except Exception:
        return []

async def get_draft_pity(user_id: int, pack_id: int | str = 1) -> int:
    user = await get_user(user_id)
    pity_data = user.get('draft_pity') or {}
    if isinstance(pity_data, str):
        try:
            pity_data = json.loads(pity_data)
        except Exception:
            pity_data = {}
    key = str(pack_id)
    if isinstance(pity_data, dict) and key in pity_data:
        return int(pity_data[key])
    return int(user.get('drafts_since_walkout', 0))

async def set_draft_pity(user_id: int, pack_id: int | str, count: int):
    global _USER_CACHE
    key = str(pack_id)
    count = max(0, int(count))
    
    # Mutate in-memory cache immediately for 0ms read latency
    if user_id in _USER_CACHE:
        cached_user = _USER_CACHE[user_id]['data']
        pity_data = cached_user.get('draft_pity') or {}
        if isinstance(pity_data, str):
            try: pity_data = json.loads(pity_data)
            except Exception: pity_data = {}
        elif not isinstance(pity_data, dict):
            pity_data = {}
        pity_data[key] = count
        cached_user['draft_pity'] = pity_data
        cached_user['drafts_since_walkout'] = count

    p = await get_db()
    await p.execute('''
        UPDATE users 
        SET draft_pity = jsonb_set(COALESCE(draft_pity, '{"1":0,"2":0,"3":0}'::jsonb), $1::text[], $2::jsonb, true),
            drafts_since_walkout = $3
        WHERE user_id = $4
    ''', [key], json.dumps(count), count, user_id)

async def increment_draft_pity(user_id: int, pack_id: int | str, amount: int = 1):
    current = await get_draft_pity(user_id, pack_id)
    await set_draft_pity(user_id, pack_id, current + amount)

async def reset_draft_pity(user_id: int, pack_id: int | str):
    await set_draft_pity(user_id, pack_id, 0)

async def set_drafts_since_walkout(user_id: int, count: int, pack_id: int | str = 1):
    await set_draft_pity(user_id, pack_id, count)

async def increment_drafts_since_walkout(user_id: int, amount: int = 1, pack_id: int | str = 1):
    await increment_draft_pity(user_id, pack_id, amount)

async def reset_drafts_since_walkout(user_id: int, pack_id: int | str = 1):
    await reset_draft_pity(user_id, pack_id)

async def is_profile_private(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user.get('is_private', 0))

async def toggle_privacy(user_id: int):
    user = await get_user(user_id)
    new_state = 1 if user.get('is_private', 0) == 0 else 0
    p = await get_db()
    await p.execute('UPDATE users SET is_private = $1 WHERE user_id = $2', new_state, user_id)
    return new_state

async def consume_portal_job(job_name: str) -> bool:
    p = await get_db()
    try:
        val = await p.fetchval('SELECT 1 FROM portal_jobs WHERE job_name = $1', job_name)
        if not val:
            return False
        await p.execute('DELETE FROM portal_jobs WHERE job_name = $1', job_name)
        return True
    except Exception:
        return False

async def get_draft_battle_stats(user_id: int) -> dict:
    p = await get_db()
    row = await p.fetchrow('SELECT draft_battle_wins, draft_battle_losses, draft_battle_draws, draft_battle_elo, draft_battle_points FROM users WHERE user_id = $1', user_id)
    if row:
        return dict(row)
    return {"draft_battle_wins": 0, "draft_battle_losses": 0, "draft_battle_draws": 0, "draft_battle_elo": 1000, "draft_battle_points": 0}

async def record_draft_battle_result(user_a_id: int, user_b_id: int, score_a: int, score_b: int, wager: int = 0):
    await get_user(user_a_id)
    await get_user(user_b_id)
    p = await get_db()

    if score_a > score_b: # User A won
        await p.execute('''
            UPDATE users SET 
                draft_battle_wins = COALESCE(draft_battle_wins, 0) + 1,
                draft_battle_elo = COALESCE(draft_battle_elo, 1000) + 25,
                draft_battle_points = COALESCE(draft_battle_points, 0) + 3,
                coins = COALESCE(coins, 0) + $1
            WHERE user_id = $2
        ''', wager * 2 if wager > 0 else 5_000_000, user_a_id)

        await p.execute('''
            UPDATE users SET 
                draft_battle_losses = COALESCE(draft_battle_losses, 0) + 1,
                draft_battle_elo = GREATEST(800, COALESCE(draft_battle_elo, 1000) - 15),
                draft_battle_points = COALESCE(draft_battle_points, 0) + 1
            WHERE user_id = $1
        ''', user_b_id)
    elif score_b > score_a: # User B won
        await p.execute('''
            UPDATE users SET 
                draft_battle_wins = COALESCE(draft_battle_wins, 0) + 1,
                draft_battle_elo = COALESCE(draft_battle_elo, 1000) + 25,
                draft_battle_points = COALESCE(draft_battle_points, 0) + 3,
                coins = COALESCE(coins, 0) + $1
            WHERE user_id = $2
        ''', wager * 2 if wager > 0 else 5_000_000, user_b_id)

        await p.execute('''
            UPDATE users SET 
                draft_battle_losses = COALESCE(draft_battle_losses, 0) + 1,
                draft_battle_elo = GREATEST(800, COALESCE(draft_battle_elo, 1000) - 15),
                draft_battle_points = COALESCE(draft_battle_points, 0) + 1
            WHERE user_id = $1
        ''', user_a_id)
    else: # Draw
        await p.execute('''
            UPDATE users SET 
                draft_battle_draws = COALESCE(draft_battle_draws, 0) + 1,
                draft_battle_elo = COALESCE(draft_battle_elo, 1000) + 5,
                draft_battle_points = COALESCE(draft_battle_points, 0) + 1,
                coins = COALESCE(coins, 0) + $1
            WHERE user_id = $2
        ''', wager if wager > 0 else 2_500_000, user_a_id)

        await p.execute('''
            UPDATE users SET 
                draft_battle_draws = COALESCE(draft_battle_draws, 0) + 1,
                draft_battle_elo = COALESCE(draft_battle_elo, 1000) + 5,
                draft_battle_points = COALESCE(draft_battle_points, 0) + 1,
                coins = COALESCE(coins, 0) + $1
            WHERE user_id = $2
        ''', wager if wager > 0 else 2_500_000, user_b_id)

async def get_draft_battle_leaderboard(limit: int = 10) -> list:
    p = await get_db()
    rows = await p.fetch('''
        SELECT user_id, draft_battle_elo, draft_battle_wins, draft_battle_losses, draft_battle_draws, draft_battle_points
        FROM users
        WHERE draft_battle_wins > 0 OR draft_battle_losses > 0 OR draft_battle_draws > 0
        ORDER BY draft_battle_elo DESC, draft_battle_points DESC
        LIMIT $1
    ''', limit)
    return [dict(r) for r in rows]

# Compatibility stubs
async def init_db_schema(): pass
async def ensure_locked_column(): pass
async def ensure_pity_column(): pass

async def get_formation_layouts() -> dict:
    global _LAYOUTS_CACHE, _LAYOUTS_CACHE_EXP
    now = time.time()
    if _LAYOUTS_CACHE is not None and now < _LAYOUTS_CACHE_EXP:
        return _LAYOUTS_CACHE
    try:
        p = await get_db()
        rows = await p.fetch('SELECT formation_name, positions_json FROM formation_layouts')
        layouts = {}
        for r in rows:
            try:
                pj = r['positions_json']
                layouts[r['formation_name']] = json.loads(pj) if isinstance(pj, str) else pj
            except Exception:
                pass
        _LAYOUTS_CACHE = layouts
        _LAYOUTS_CACHE_EXP = now + 60.0  # 60s cache
        return layouts
    except Exception:
        return {}

# Event exchanges (memory cache)
EVENT_EXCHANGES = []
def get_event_exchanges(): return EVENT_EXCHANGES
def set_event_exchanges(events):
    global EVENT_EXCHANGES
    EVENT_EXCHANGES = events

# Ultra-fast RAM cache for official cards by rating
_OFFICIAL_CARDS_CACHE = {}

async def get_official_cards_by_rating(min_rating: int, max_rating: int = None, limit: int = 100):
    global _OFFICIAL_CARDS_CACHE
    import random
    if max_rating is None:
        max_rating = min_rating
        
    cached_matching = []
    for r in range(min_rating, max_rating + 1):
        if r in _OFFICIAL_CARDS_CACHE:
            cached_matching.extend(_OFFICIAL_CARDS_CACHE[r])
            
    if cached_matching:
        return random.sample(cached_matching, min(limit, len(cached_matching)))
        
    try:
        p = await get_db()
        rows = await p.fetch('''
            SELECT player_data FROM official_cards 
            WHERE rating >= $1 AND rating <= $2 
            ORDER BY RANDOM() LIMIT $3
        ''', min_rating, max_rating, limit)
        
        res = []
        for r in rows:
            try:
                pd = json.loads(r['player_data']) if isinstance(r['player_data'], str) else r['player_data']
                res.append(pd)
            except Exception:
                pass
        return res
    except Exception as e:
        print(f"Error fetching official cards by rating: {e}")
        return []

async def preload_official_cards_cache():
    global _OFFICIAL_CARDS_CACHE
    try:
        p = await get_db()
        rows = await p.fetch('SELECT rating, player_data FROM official_cards WHERE rating >= 110')
        cache = {}
        for r in rows:
            rating = r['rating']
            if rating not in cache:
                cache[rating] = []
            try:
                pd = json.loads(r['player_data']) if isinstance(r['player_data'], str) else r['player_data']
                cache[rating].append(pd)
            except Exception:
                pass
        _OFFICIAL_CARDS_CACHE = cache
        print(f"[Database] Preloaded {sum(len(v) for v in cache.values())} official cards into RAM cache!")
    except Exception as e:
        print(f"[Database] Card cache preload note: {e}")

async def get_max_official_ovr() -> int:
    """
    Returns the maximum OVR rating available in the official cards database.
    Dynamically scales when higher-rated cards (e.g., 124+, 125+) are released.
    """
    global _OFFICIAL_CARDS_CACHE
    if _OFFICIAL_CARDS_CACHE:
        valid_ratings = [r for r, cards in _OFFICIAL_CARDS_CACHE.items() if len(cards) >= 1]
        if valid_ratings:
            return max(valid_ratings)
    try:
        p = await get_db()
        max_r = await p.fetchval('SELECT MAX(rating) FROM official_cards')
        return int(max_r) if max_r else 122
    except Exception:
        return 122

# ================= Player Performance Stats =================

async def record_player_match_stats(user_id: int, stats_list: list[dict]):
    """
    Records detailed post-match stats for an array of players for a user in a single batch operation.
    """
    if not stats_list:
        return
    p = await get_db()
    records = []
    for s in stats_list:
        p_name = s.get("player_name") or s.get("name") or "Player"
        p_id = str(s.get("player_id") or s.get("id") or "")
        pos = str(s.get("position") or s.get("pos") or "CM").upper()
        ovr = int(s.get("ovr") or s.get("rating") or 100)
        goals = int(s.get("goals") or 0)
        assists = int(s.get("assists") or 0)
        clean_sheets = int(s.get("clean_sheets") or 0)
        yellows = int(s.get("yellow_cards") or s.get("yellows") or 0)
        reds = int(s.get("red_cards") or s.get("reds") or 0)
        rating = float(s.get("rating") or 6.0)
        motm = int(s.get("is_motm") or 0)
        records.append((user_id, p_name, p_id, pos, ovr, goals, assists, clean_sheets, yellows, reds, rating, motm))

    try:
        await p.executemany('''
            INSERT INTO player_stats (
                user_id, player_name, player_id, position, ovr,
                matches_played, goals, assists, clean_sheets,
                yellow_cards, red_cards, total_rating, motm_count
            ) VALUES ($1, $2, $3, $4, $5, 1, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (user_id, player_name) DO UPDATE SET
                player_id = COALESCE(NULLIF(EXCLUDED.player_id, ''), player_stats.player_id),
                position = COALESCE(EXCLUDED.position, player_stats.position),
                ovr = GREATEST(COALESCE(player_stats.ovr, 0), EXCLUDED.ovr),
                matches_played = player_stats.matches_played + 1,
                goals = player_stats.goals + EXCLUDED.goals,
                assists = player_stats.assists + EXCLUDED.assists,
                clean_sheets = player_stats.clean_sheets + EXCLUDED.clean_sheets,
                yellow_cards = player_stats.yellow_cards + EXCLUDED.yellow_cards,
                red_cards = player_stats.red_cards + EXCLUDED.red_cards,
                total_rating = player_stats.total_rating + EXCLUDED.total_rating,
                motm_count = player_stats.motm_count + EXCLUDED.motm_count
        ''', records)
    except Exception as e:
        print(f"[Database] Error batch recording stats: {e}")

async def get_user_player_stats(user_id: int, player_name: str = None) -> list[dict]:
    """
    Fetches stats for a specific player or all players belonging to a user.
    """
    p = await get_db()
    try:
        if player_name:
            rows = await p.fetch('''
                SELECT user_id, player_name, player_id, position, ovr,
                       matches_played, goals, assists, clean_sheets,
                       yellow_cards, red_cards, total_rating, motm_count,
                       ROUND(CAST(total_rating / NULLIF(matches_played, 0) AS NUMERIC), 2) as avg_rating
                FROM player_stats
                WHERE user_id = $1 AND LOWER(player_name) = LOWER($2)
            ''', user_id, player_name.strip())
            if not rows:
                rows = await p.fetch('''
                    SELECT user_id, player_name, player_id, position, ovr,
                           matches_played, goals, assists, clean_sheets,
                           yellow_cards, red_cards, total_rating, motm_count,
                           ROUND(CAST(total_rating / NULLIF(matches_played, 0) AS NUMERIC), 2) as avg_rating
                    FROM player_stats
                    WHERE user_id = $1 AND player_name ILIKE $2
                    ORDER BY matches_played DESC LIMIT 5
                ''', user_id, f"%{player_name.strip()}%")
        else:
            rows = await p.fetch('''
                SELECT user_id, player_name, player_id, position, ovr,
                       matches_played, goals, assists, clean_sheets,
                       yellow_cards, red_cards, total_rating, motm_count,
                       ROUND(CAST(total_rating / NULLIF(matches_played, 0) AS NUMERIC), 2) as avg_rating
                FROM player_stats
                WHERE user_id = $1
                ORDER BY goals DESC, matches_played DESC
            ''', user_id)
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[Database] Error fetching player stats: {e}")
        return []

async def get_club_leader_stats(user_id: int) -> dict:
    """
    Calculates top club performers:
    - Top Scorer (Golden Boot)
    - Playmaker (Most Assists)
    - Highest Average Rating (Min 1 match)
    - Clean Sheet Leader (Defenders CB/LB/RB/LWB/RWB & GK only)
    - Disciplinary Records (Yellow & Red cards)
    """
    p = await get_db()
    try:
        all_players = await p.fetch('''
            SELECT user_id, player_name, player_id, position, ovr,
                   matches_played, goals, assists, clean_sheets,
                   yellow_cards, red_cards, total_rating, motm_count,
                   ROUND(CAST(total_rating / NULLIF(matches_played, 0) AS NUMERIC), 2) as avg_rating
            FROM player_stats
            WHERE user_id = $1 AND matches_played > 0
        ''', user_id)
        
        if not all_players:
            return {}

        players = [dict(r) for r in all_players]

        top_scorer = max(players, key=lambda x: (x['goals'], x['matches_played'])) if any(x['goals'] > 0 for x in players) else None
        top_assists = max(players, key=lambda x: (x['assists'], x['matches_played'])) if any(x['assists'] > 0 for x in players) else None
        best_rating = max(players, key=lambda x: (float(x['avg_rating'] or 0), x['matches_played'])) if players else None
        
        # Clean sheets only for defenders and GK
        defenders_gk = [p for p in players if any(k in str(p.get('position', '')).upper() for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])]
        top_clean_sheets = max(defenders_gk, key=lambda x: (x['clean_sheets'], x['matches_played'])) if (defenders_gk and any(x['clean_sheets'] > 0 for x in defenders_gk)) else None
        
        most_yellows = max(players, key=lambda x: (x['yellow_cards'], x['matches_played'])) if any(x['yellow_cards'] > 0 for x in players) else None
        most_reds = max(players, key=lambda x: (x['red_cards'], x['matches_played'])) if any(x['red_cards'] > 0 for x in players) else None

        total_club_goals = sum(p['goals'] for p in players)
        total_club_assists = sum(p['assists'] for p in players)
        total_matches = max(p['matches_played'] for p in players) if players else 0

        return {
            "top_scorer": top_scorer,
            "top_assists": top_assists,
            "best_rating": best_rating,
            "top_clean_sheets": top_clean_sheets,
            "most_yellows": most_yellows,
            "most_reds": most_reds,
            "total_goals": total_club_goals,
            "total_assists": total_club_assists,
            "total_matches": total_matches,
            "tracked_count": len(players)
        }
    except Exception as e:
        print(f"[Database] Error in get_club_leader_stats: {e}")
        return {}

# ================= Signature Box Functions =================

DEFAULT_SIGNATURE_BOX = {
    "id": 1,
    "title": "FC SIGNATURE BOX",
    "subtitle": "Exclusive 10-Reward Limited Box Draw",
    "is_active": True,
    "banner_url": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80",
    "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
    "signature_card_data": {
        "id": "sig_zidane_124",
        "cardName": "Zinedine Zidane",
        "firstName": "Zinedine",
        "lastName": "Zidane",
        "rating": 124,
        "position": "CAM",
        "club": {"id": 243, "name": "Real Madrid"},
        "nation": {"id": 18, "name": "France"},
        "source": "SIGNATURE_BOX",
        "is_signature_box": True,
        "is_custom": True,
        "performance_boost": 1.25,
        "custom_background_url": "https://images.unsplash.com/photo-1579546929518-9e396f3cc809?auto=format&fit=crop&w=800&q=80",
        "stats": {"PAC": 130, "SHO": 138, "PAS": 145, "DRI": 142, "DEF": 115, "PHY": 128}
    },
    "rewards_json": [
        {"id": 1, "tier": "bad", "name": "50,000,000 Coins", "type": "coins", "amount": 50000000, "icon": "🪙", "base_weight": 22.0},
        {"id": 2, "tier": "bad", "name": "5 Draft Vouchers", "type": "vouchers", "amount": 5, "icon": "🎟️", "base_weight": 22.0},
        {"id": 3, "tier": "mid", "name": "250,000,000 Coins", "type": "coins", "amount": 250000000, "icon": "💰", "base_weight": 11.0},
        {"id": 4, "tier": "mid", "name": "20 Draft Vouchers", "type": "vouchers", "amount": 20, "icon": "🎟️", "base_weight": 11.0},
        {"id": 5, "tier": "mid", "name": "500 Gems", "type": "gems", "amount": 500, "icon": "💎", "base_weight": 11.0},
        {"id": 6, "tier": "mid", "name": "100,000 Fans", "type": "fans", "amount": 100000, "icon": "👥", "base_weight": 11.0},
        {"id": 7, "tier": "mid", "name": "1x 115-118 Elite Pack", "type": "pack", "amount": 1, "pack_rating_min": 115, "pack_rating_max": 118, "icon": "📦", "base_weight": 8.0},
        {"id": 8, "tier": "good", "name": "2,500,000,000 Coins (2.5B)", "type": "coins", "amount": 2500000000, "icon": "👑", "base_weight": 2.0},
        {"id": 9, "tier": "good", "name": "75 Draft Vouchers", "type": "vouchers", "amount": 75, "icon": "🎫", "base_weight": 2.0},
        {"id": 10, "tier": "good", "name": "🌟 124 OVR Signature Zidane", "type": "signature_card", "amount": 1, "icon": "🌟", "base_weight": 1.0}
    ],
    "draw_costs_json": [
        {"draw": 1, "currency": "coins", "amount": 50000000},
        {"draw": 2, "currency": "coins", "amount": 100000000},
        {"draw": 3, "currency": "coins", "amount": 200000000},
        {"draw": 4, "currency": "coins", "amount": 350000000},
        {"draw": 5, "currency": "coins", "amount": 550000000},
        {"draw": 6, "currency": "coins", "amount": 800000000},
        {"draw": 7, "currency": "coins", "amount": 1100000000},
        {"draw": 8, "currency": "coins", "amount": 1500000000},
        {"draw": 9, "currency": "coins", "amount": 2000000000},
        {"draw": 10, "currency": "coins", "amount": 2500000000}
    ]
}

_SIG_BOX_CACHE = None
_SIG_BOX_CACHE_EXP = 0

async def get_signature_box_config() -> dict:
    global _SIG_BOX_CACHE, _SIG_BOX_CACHE_EXP
    now = time.time()
    if _SIG_BOX_CACHE and now - _SIG_BOX_CACHE_EXP < 30:
        return _SIG_BOX_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow('SELECT * FROM signature_box_config WHERE id = 1')
        if not row:
            # Seed default config
            sb = DEFAULT_SIGNATURE_BOX
            await p.execute('''
                INSERT INTO signature_box_config (id, title, subtitle, is_active, banner_url, expires_at, signature_card_data, rewards_json, draw_costs_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
            ''', sb['id'], sb['title'], sb['subtitle'], sb['is_active'], sb['banner_url'],
                 datetime.datetime.strptime(sb['expires_at'], "%Y-%m-%d %H:%M:%S"),
                 json.dumps(sb['signature_card_data']), json.dumps(sb['rewards_json']), json.dumps(sb['draw_costs_json']))
            _SIG_BOX_CACHE = sb
            _SIG_BOX_CACHE_EXP = now
            return sb
        
        data = dict(row)
        for k in ['signature_card_data', 'rewards_json', 'draw_costs_json']:
            if isinstance(data.get(k), str):
                try: data[k] = json.loads(data[k])
                except Exception: pass
        if data.get('expires_at'):
            data['expires_at'] = data['expires_at'].strftime("%Y-%m-%d %H:%M:%S")
        _SIG_BOX_CACHE = data
        _SIG_BOX_CACHE_EXP = now
        return data
    except Exception as e:
        print(f"[Database] Error in get_signature_box_config: {e}")
        return DEFAULT_SIGNATURE_BOX

async def save_signature_box_config(config: dict) -> bool:
    global _SIG_BOX_CACHE, _SIG_BOX_CACHE_EXP
    p = await get_db()
    try:
        exp_dt = None
        if config.get('expires_at'):
            try:
                exp_dt = datetime.datetime.strptime(str(config['expires_at']).strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    exp_dt = datetime.datetime.fromisoformat(str(config['expires_at']).replace('Z', '+00:00'))
                except Exception:
                    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)

        await p.execute('''
            INSERT INTO signature_box_config (id, title, subtitle, is_active, banner_url, expires_at, signature_card_data, rewards_json, draw_costs_json, updated_at)
            VALUES (1, $1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                subtitle = EXCLUDED.subtitle,
                is_active = EXCLUDED.is_active,
                banner_url = EXCLUDED.banner_url,
                expires_at = EXCLUDED.expires_at,
                signature_card_data = EXCLUDED.signature_card_data,
                rewards_json = EXCLUDED.rewards_json,
                draw_costs_json = EXCLUDED.draw_costs_json,
                updated_at = CURRENT_TIMESTAMP
        ''', config.get('title', 'FC SIGNATURE BOX'),
             config.get('subtitle', 'Exclusive 10-Reward Box Draw'),
             bool(config.get('is_active', True)),
             config.get('banner_url', ''),
             exp_dt,
             json.dumps(config.get('signature_card_data', {})),
             json.dumps(config.get('rewards_json', [])),
             json.dumps(config.get('draw_costs_json', [])))
        _SIG_BOX_CACHE = None
        _SIG_BOX_CACHE_EXP = 0
        return True
    except Exception as e:
        print(f"[Database] Error in save_signature_box_config: {e}")
        return False

async def get_user_signature_box(user_id: int) -> dict:
    p = await get_db()
    try:
        row = await p.fetchrow('SELECT * FROM user_signature_box WHERE user_id = $1', user_id)
        if not row:
            await p.execute('INSERT INTO user_signature_box (user_id, box_id, claimed_reward_ids, draws_completed) VALUES ($1, 1, $2, 0) ON CONFLICT (user_id) DO NOTHING', user_id, json.dumps([]))
            return {"user_id": user_id, "box_id": 1, "claimed_reward_ids": [], "draws_completed": 0}
        data = dict(row)
        if isinstance(data.get('claimed_reward_ids'), str):
            try: data['claimed_reward_ids'] = json.loads(data['claimed_reward_ids'])
            except Exception: data['claimed_reward_ids'] = []
        return data
    except Exception as e:
        print(f"[Database] Error in get_user_signature_box: {e}")
        return {"user_id": user_id, "box_id": 1, "claimed_reward_ids": [], "draws_completed": 0}

async def record_user_signature_box_draw(user_id: int, reward_id: int):
    p = await get_db()
    try:
        user_box = await get_user_signature_box(user_id)
        claimed = list(user_box.get('claimed_reward_ids', []))
        if reward_id not in claimed:
            claimed.append(reward_id)
        draws = int(user_box.get('draws_completed', 0)) + 1
        await p.execute('''
            INSERT INTO user_signature_box (user_id, box_id, claimed_reward_ids, draws_completed, last_drawn_at)
            VALUES ($1, 1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                claimed_reward_ids = EXCLUDED.claimed_reward_ids,
                draws_completed = EXCLUDED.draws_completed,
                last_drawn_at = CURRENT_TIMESTAMP
        ''', user_id, json.dumps(claimed), draws)
    except Exception as e:
        print(f"[Database] Error recording signature box draw: {e}")

async def reset_user_signature_box(user_id: int = None):
    p = await get_db()
    try:
        if user_id:
            await p.execute('UPDATE user_signature_box SET claimed_reward_ids = $1, draws_completed = 0 WHERE user_id = $2', json.dumps([]), user_id)
        else:
            await p.execute('UPDATE user_signature_box SET claimed_reward_ids = $1, draws_completed = 0', json.dumps([]))
        return True
    except Exception as e:
        print(f"[Database] Error resetting user signature box: {e}")
        return False

# ================= Luck Settings Functions =================

DEFAULT_LUCK_SETTINGS = {
    "draft_pool_a_rate": 2.5,
    "draft_pool_b_rate": 30.0,
    "draft_pool_c_rate": 67.5,
    "walkout_122_share": 6.0,
    "walkout_121_share": 35.0,
    "walkout_120_share": 59.0,
    "pity_pool_a_threshold": 70,
    "pity_pool_b_interval": 10,
    "global_luck_multiplier": 1.0,
    "exchange_top_rate": 5.0,
    "exchange_mid_rate": 35.0,
    "exchange_base_rate": 60.0
}

_LUCK_CACHE = None
_LUCK_CACHE_EXP = 0

async def get_luck_settings() -> dict:
    global _LUCK_CACHE, _LUCK_CACHE_EXP
    now = time.time()
    if _LUCK_CACHE and now - _LUCK_CACHE_EXP < 30:
        return _LUCK_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'luck_settings'")
        if not row:
            await p.execute("INSERT INTO system_settings (key, value) VALUES ('luck_settings', $1) ON CONFLICT (key) DO NOTHING", json.dumps(DEFAULT_LUCK_SETTINGS))
            _LUCK_CACHE = DEFAULT_LUCK_SETTINGS
            _LUCK_CACHE_EXP = now
            return DEFAULT_LUCK_SETTINGS
        val = row['value']
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = DEFAULT_LUCK_SETTINGS
        res = {**DEFAULT_LUCK_SETTINGS, **(val if isinstance(val, dict) else {})}
        _LUCK_CACHE = res
        _LUCK_CACHE_EXP = now
        return res
    except Exception as e:
        print(f"[Database] Error in get_luck_settings: {e}")
        return DEFAULT_LUCK_SETTINGS

async def save_luck_settings(settings: dict) -> bool:
    global _LUCK_CACHE, _LUCK_CACHE_EXP
    p = await get_db()
    try:
        merged = {**DEFAULT_LUCK_SETTINGS, **settings}
        await p.execute('''
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('luck_settings', $1, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        ''', json.dumps(merged))
        _LUCK_CACHE = merged
        _LUCK_CACHE_EXP = time.time()
        return True
    except Exception as e:
        print(f"[Database] Error in save_luck_settings: {e}")
        return False

# ================= OVR Price Limits & Economy Functions =================

DEFAULT_OVR_PRICES = {
    125: {"min_price": 16000000000, "max_price": 32000000000, "quicksell": 11200000000},
    124: {"min_price": 8000000000, "max_price": 16000000000, "quicksell": 5600000000},
    123: {"min_price": 4000000000, "max_price": 8000000000, "quicksell": 2800000000},
    122: {"min_price": 2000000000, "max_price": 4000000000, "quicksell": 1400000000},
    121: {"min_price": 900000000, "max_price": 1800000000, "quicksell": 630000000},
    120: {"min_price": 400000000, "max_price": 800000000, "quicksell": 280000000},
    119: {"min_price": 70000000, "max_price": 140000000, "quicksell": 49000000},
    118: {"min_price": 65000000, "max_price": 130000000, "quicksell": 45500000},
    117: {"min_price": 60000000, "max_price": 120000000, "quicksell": 42000000},
    116: {"min_price": 10000000, "max_price": 20000000, "quicksell": 7000000},
    115: {"min_price": 9000000, "max_price": 18000000, "quicksell": 6300000},
    114: {"min_price": 8000000, "max_price": 16000000, "quicksell": 5600000},
    113: {"min_price": 7000000, "max_price": 14000000, "quicksell": 4900000},
    112: {"min_price": 6000000, "max_price": 12000000, "quicksell": 4200000},
    111: {"min_price": 5000000, "max_price": 10000000, "quicksell": 3500000},
    110: {"min_price": 4000000, "max_price": 8000000, "quicksell": 2800000},
    109: {"min_price": 3000000, "max_price": 6000000, "quicksell": 2100000},
    108: {"min_price": 2000000, "max_price": 4000000, "quicksell": 1400000},
    107: {"min_price": 1000000, "max_price": 2000000, "quicksell": 700000},
    106: {"min_price": 500000, "max_price": 1000000, "quicksell": 350000},
    105: {"min_price": 250000, "max_price": 500000, "quicksell": 175000},
    104: {"min_price": 200000, "max_price": 400000, "quicksell": 140000},
    103: {"min_price": 150000, "max_price": 300000, "quicksell": 105000},
    102: {"min_price": 100000, "max_price": 200000, "quicksell": 70000},
    101: {"min_price": 75000, "max_price": 150000, "quicksell": 52500},
    100: {"min_price": 50000, "max_price": 100000, "quicksell": 35000},
}

_OVR_PRICES_CACHE = None
_OVR_PRICES_CACHE_EXP = 0

def _calculate_fallback_price_limits(ovr: int) -> tuple[int, int]:
    if ovr > 122:
        max_p = 4_000_000_000 * (2 ** (ovr - 122))
        return max_p // 2, max_p
    if ovr >= 107:
        base = (ovr - 106) * 1_000_000
        return base, base * 2
    return 100, 200

def get_price_limits_for_ovr(ovr: int) -> tuple[int, int]:
    global _OVR_PRICES_CACHE
    try:
        ovr_int = int(ovr)
    except Exception:
        return 100, 200
    ovr_str = str(ovr_int)
    cache = _OVR_PRICES_CACHE or DEFAULT_OVR_PRICES
    entry = cache.get(ovr_int) or cache.get(ovr_str)
    if entry and isinstance(entry, dict):
        min_p = int(entry.get('min_price', 0))
        max_p = int(entry.get('max_price', 0))
        if min_p > 0 and max_p > 0:
            return min_p, max_p
    if ovr_int in DEFAULT_OVR_PRICES:
        d = DEFAULT_OVR_PRICES[ovr_int]
        return d["min_price"], d["max_price"]
    return _calculate_fallback_price_limits(ovr_int)

def get_quicksell_value_for_ovr(ovr: int) -> int:
    global _OVR_PRICES_CACHE
    try:
        ovr_int = int(ovr)
    except Exception:
        return 50
    ovr_str = str(ovr_int)
    cache = _OVR_PRICES_CACHE or DEFAULT_OVR_PRICES
    entry = cache.get(ovr_int) or cache.get(ovr_str)
    if entry and isinstance(entry, dict) and entry.get('quicksell'):
        return int(entry['quicksell'])
    min_p, _ = get_price_limits_for_ovr(ovr_int)
    return max(1, int(min_p * 0.70))

async def get_ovr_price_settings() -> dict:
    global _OVR_PRICES_CACHE, _OVR_PRICES_CACHE_EXP
    now = time.time()
    if _OVR_PRICES_CACHE and now - _OVR_PRICES_CACHE_EXP < 30:
        return _OVR_PRICES_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'ovr_prices'")
        if not row:
            raw_defaults = {str(k): v for k, v in DEFAULT_OVR_PRICES.items()}
            await p.execute("INSERT INTO system_settings (key, value) VALUES ('ovr_prices', $1) ON CONFLICT (key) DO NOTHING", json.dumps(raw_defaults))
            _OVR_PRICES_CACHE = DEFAULT_OVR_PRICES
            _OVR_PRICES_CACHE_EXP = now
            return DEFAULT_OVR_PRICES
        val = row['value']
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = {}
        parsed = {}
        for k, v in (val or {}).items():
            try: parsed[int(k)] = v
            except Exception: parsed[k] = v
        merged = {**DEFAULT_OVR_PRICES, **parsed}
        _OVR_PRICES_CACHE = merged
        _OVR_PRICES_CACHE_EXP = now
        return merged
    except Exception as e:
        print(f"[Database] Error in get_ovr_price_settings: {e}")
        return DEFAULT_OVR_PRICES

async def save_ovr_price_settings(prices_dict: dict) -> bool:
    global _OVR_PRICES_CACHE, _OVR_PRICES_CACHE_EXP
    p = await get_db()
    try:
        ser = {str(k): v for k, v in prices_dict.items()}
        await p.execute('''
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('ovr_prices', $1, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        ''', json.dumps(ser))
        
        parsed = {}
        for k, v in prices_dict.items():
            try: parsed[int(k)] = v
            except Exception: parsed[k] = v
        _OVR_PRICES_CACHE = {**DEFAULT_OVR_PRICES, **parsed}
        _OVR_PRICES_CACHE_EXP = time.time()
        return True
    except Exception as e:
        print(f"[Database] Error in save_ovr_price_settings: {e}")
        return False

# ================= Global Economy Settings =================

DEFAULT_ECONOMY_CONFIG = {
    "daily_coins_min": 5_000_000,
    "daily_coins_max": 20_000_000,
    "daily_vouchers": 2,
    "daily_cooldown_hours": 24,
    "daily_streak_multiplier": 0.10,
    "daily_walkout_chance": 0.15,
    "work_coins_min": 2_000_000,
    "work_coins_max": 10_000_000,
    "work_cooldown_mins": 30,
    "voucher_coin_price": 10_000_000,
    "voucher_daily_limit": 70,
    "market_tax_percent": 10.0,
    "trade_tax_percent": 5.0,
    "max_market_listings": 10,
    "starter_coins": 50_000_000,
    "starter_vouchers": 10,
    "dribble_reward_vouchers": 2,
    "dribble_reward_coins": 5_000_000,
    "dribble_cooldown_mins": 120,
    "trivia_reward_vouchers": 1,
    "trivia_reward_coins": 5_000_000,
    "trivia_cooldown_mins": 60,
    "freekick_reward_vouchers": 1,
    "freekick_reward_coins": 4_000_000,
    "freekick_cooldown_mins": 90,
    "gk_reward_vouchers": 1,
    "gk_reward_coins": 4_000_000,
    "gk_cooldown_mins": 90,
    "volley_reward_vouchers": 1,
    "volley_reward_coins": 4_000_000,
    "volley_cooldown_mins": 90,
    "h2h_ai_reward_vouchers": 2,
    "h2h_ai_reward_coins": 10_000_000,
    "h2h_ai_cooldown_mins": 120,
    "penalty_reward_vouchers": 1,
    "penalty_reward_coins": 3_000_000,
    "penalty_cooldown_mins": 60
}

_ECONOMY_CACHE = None
_ECONOMY_CACHE_EXP = 0

async def get_economy_config() -> dict:
    global _ECONOMY_CACHE, _ECONOMY_CACHE_EXP
    now = time.time()
    if _ECONOMY_CACHE and now - _ECONOMY_CACHE_EXP < 30:
        return _ECONOMY_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'economy_config'")
        if not row:
            await p.execute("INSERT INTO system_settings (key, value) VALUES ('economy_config', $1) ON CONFLICT (key) DO NOTHING", json.dumps(DEFAULT_ECONOMY_CONFIG))
            _ECONOMY_CACHE = DEFAULT_ECONOMY_CONFIG
            _ECONOMY_CACHE_EXP = now
            return DEFAULT_ECONOMY_CONFIG
        val = row['value']
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = {}
        merged = {**DEFAULT_ECONOMY_CONFIG, **(val or {})}
        _ECONOMY_CACHE = merged
        _ECONOMY_CACHE_EXP = now
        return merged
    except Exception as e:
        print(f"[Database] Error in get_economy_config: {e}")
        return DEFAULT_ECONOMY_CONFIG

async def save_economy_config(config_dict: dict) -> bool:
    global _ECONOMY_CACHE, _ECONOMY_CACHE_EXP
    p = await get_db()
    try:
        merged = {**DEFAULT_ECONOMY_CONFIG, **config_dict}
        await p.execute('''
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('economy_config', $1, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        ''', json.dumps(merged))
        _ECONOMY_CACHE = merged
        _ECONOMY_CACHE_EXP = time.time()
        return True
    except Exception as e:
        print(f"[Database] Error in save_economy_config: {e}")
        return False

# ================= Global Gameplay & Match Settings =================

DEFAULT_GAMEPLAY_CONFIG = {
    "match_win_coins": 25_000_000,
    "match_draw_coins": 10_000_000,
    "match_loss_coins": 5_000_000,
    "match_win_fans": 25,
    "match_draw_fans": 0,
    "match_loss_fans": -15,
    "match_win_xp": 75,
    "match_challenge_timeout_secs": 60,
    "match_cooldown_mins": 0,
    "match_sim_step_delay_secs": 0,
    "draft_battle_entry_fee": 0,
    "draft_battle_winner_coins": 50_000_000,
    "draft_battle_winner_vouchers": 5,
    "custom_card_match_boost": 1.15,
    "penalty_shootout_enabled": True,
    "division_tiers": [
        { "id": 1, "name": "Amateur III", "min_fans": 0, "badge": "🥉", "win_reward_coins": 10000000, "win_reward_vouchers": 1 },
        { "id": 2, "name": "Amateur II", "min_fans": 10000, "badge": "🥉", "win_reward_coins": 12000000, "win_reward_vouchers": 1 },
        { "id": 3, "name": "Amateur I", "min_fans": 20000, "badge": "🥉", "win_reward_coins": 15000000, "win_reward_vouchers": 1 },
        { "id": 4, "name": "Pro III", "min_fans": 30000, "badge": "🥈", "win_reward_coins": 18000000, "win_reward_vouchers": 2 },
        { "id": 5, "name": "Pro II", "min_fans": 50000, "badge": "🥈", "win_reward_coins": 20000000, "win_reward_vouchers": 2 },
        { "id": 6, "name": "Pro I", "min_fans": 70000, "badge": "🥈", "win_reward_coins": 25000000, "win_reward_vouchers": 2 },
        { "id": 7, "name": "World Class III", "min_fans": 100000, "badge": "🥇", "win_reward_coins": 30000000, "win_reward_vouchers": 3 },
        { "id": 8, "name": "World Class II", "min_fans": 200000, "badge": "🥇", "win_reward_coins": 35000000, "win_reward_vouchers": 3 },
        { "id": 9, "name": "World Class I", "min_fans": 300000, "badge": "🥇", "win_reward_coins": 40000000, "win_reward_vouchers": 3 },
        { "id": 10, "name": "Legendary III", "min_fans": 400000, "badge": "💎", "win_reward_coins": 50000000, "win_reward_vouchers": 4 },
        { "id": 11, "name": "Legendary II", "min_fans": 600000, "badge": "💎", "win_reward_coins": 65000000, "win_reward_vouchers": 4 },
        { "id": 12, "name": "Legendary I", "min_fans": 800000, "badge": "💎", "win_reward_coins": 80000000, "win_reward_vouchers": 5 },
        { "id": 13, "name": "FC Champion", "min_fans": 1000000, "badge": "🏆", "win_reward_coins": 100000000, "win_reward_vouchers": 6 }
    ]
}

_GAMEPLAY_CACHE = None
_GAMEPLAY_CACHE_EXP = 0

async def get_gameplay_config() -> dict:
    global _GAMEPLAY_CACHE, _GAMEPLAY_CACHE_EXP
    now = time.time()
    if _GAMEPLAY_CACHE and now - _GAMEPLAY_CACHE_EXP < 30:
        return _GAMEPLAY_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'gameplay_config'")
        if not row:
            await p.execute("INSERT INTO system_settings (key, value) VALUES ('gameplay_config', $1) ON CONFLICT (key) DO NOTHING", json.dumps(DEFAULT_GAMEPLAY_CONFIG))
            _GAMEPLAY_CACHE = DEFAULT_GAMEPLAY_CONFIG
            _GAMEPLAY_CACHE_EXP = now
            return DEFAULT_GAMEPLAY_CONFIG
        val = row['value']
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = {}
        merged = {**DEFAULT_GAMEPLAY_CONFIG, **(val or {})}
        _GAMEPLAY_CACHE = merged
        _GAMEPLAY_CACHE_EXP = now
        return merged
    except Exception as e:
        print(f"[Database] Error in get_gameplay_config: {e}")
        return DEFAULT_GAMEPLAY_CONFIG

async def save_gameplay_config(config_dict: dict) -> bool:
    global _GAMEPLAY_CACHE, _GAMEPLAY_CACHE_EXP
    p = await get_db()
    try:
        merged = {**DEFAULT_GAMEPLAY_CONFIG, **config_dict}
        await p.execute('''
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('gameplay_config', $1, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        ''', json.dumps(merged))
        _GAMEPLAY_CACHE = merged
        _GAMEPLAY_CACHE_EXP = time.time()
        return True
    except Exception as e:
        print(f"[Database] Error in save_gameplay_config: {e}")
        return False

# ================= Bot System & Presence Config =================

DEFAULT_BOT_CONFIG = {
    "presence_activity_type": "Playing",
    "presence_status_text": "FC Mobile 27",
    "presence_status_state": "online",
    "maintenance_mode": False,
    "maintenance_message": "🛠️ DestiFC is currently undergoing scheduled maintenance. Commands are temporarily paused!",
    "draft_rotation_hours": 2.0,
    "store_rotation_hours": 4.0,
    "commands_enabled": {
        "draft": True,
        "market": True,
        "draft_battle": True,
        "exchange": True,
        "trade": True,
        "squad": True,
        "sbc": True,
        "signature_box": True,
        "daily": True,
        "work": True,
        "match": True
    }
}

_BOT_CONFIG_CACHE = None
_BOT_CONFIG_CACHE_EXP = 0

async def get_bot_config() -> dict:
    global _BOT_CONFIG_CACHE, _BOT_CONFIG_CACHE_EXP
    now = time.time()
    if _BOT_CONFIG_CACHE and now - _BOT_CONFIG_CACHE_EXP < 15:
        return _BOT_CONFIG_CACHE

    p = await get_db()
    try:
        row = await p.fetchrow("SELECT value FROM system_settings WHERE key = 'bot_config'")
        if not row:
            await p.execute("INSERT INTO system_settings (key, value) VALUES ('bot_config', $1) ON CONFLICT (key) DO NOTHING", json.dumps(DEFAULT_BOT_CONFIG))
            _BOT_CONFIG_CACHE = DEFAULT_BOT_CONFIG
            _BOT_CONFIG_CACHE_EXP = now
            return DEFAULT_BOT_CONFIG
        val = row['value']
        if isinstance(val, str):
            try: val = json.loads(val)
            except Exception: val = {}
        merged = {**DEFAULT_BOT_CONFIG, **(val or {})}
        _BOT_CONFIG_CACHE = merged
        _BOT_CONFIG_CACHE_EXP = now
        return merged
    except Exception as e:
        print(f"[Database] Error in get_bot_config: {e}")
        return DEFAULT_BOT_CONFIG

async def save_bot_config(config_dict: dict) -> bool:
    global _BOT_CONFIG_CACHE, _BOT_CONFIG_CACHE_EXP
    p = await get_db()
    try:
        merged = {**DEFAULT_BOT_CONFIG, **config_dict}
        await p.execute('''
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('bot_config', $1, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        ''', json.dumps(merged))
        _BOT_CONFIG_CACHE = merged
        _BOT_CONFIG_CACHE_EXP = time.time()
        return True
    except Exception as e:
        print(f"[Database] Error in save_bot_config: {e}")
        return False




