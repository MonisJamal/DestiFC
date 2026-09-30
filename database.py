import asyncpg
import json
import asyncio
import os
import datetime

DB_FILE = "destifc.db"
SUPABASE_URL = "postgresql://postgres.xreebpmibnbttuhevall:MonislovesBiryani37@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

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

async def get_db():
    global _pool
    if _pool is None or getattr(_pool, '_closed', False):
        _pool = await asyncpg.create_pool(
            SUPABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=20,
            max_inactive_connection_lifetime=60.0,
            statement_cache_size=0
        )
    return _pool

async def setup():
    """Initializes the database pool and verifies schema."""
    p = await get_db()
    # Ensure default tables exist
    await p.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            coins BIGINT DEFAULT 0,
            vouchers INTEGER DEFAULT 0,
            gems INTEGER DEFAULT 0,
            fans INTEGER DEFAULT 0,
            drafts_opened INTEGER DEFAULT 0,
            drafts_since_walkout INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            last_quest_daily INTEGER DEFAULT 0,
            last_quest_skill INTEGER DEFAULT 0,
            last_quest_h2h INTEGER DEFAULT 0,
            last_quest_freekick INTEGER DEFAULT 0,
            last_quest_dribble INTEGER DEFAULT 0,
            last_quest_trivia INTEGER DEFAULT 0,
            last_quest_gk INTEGER DEFAULT 0,
            last_quest_volley INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            player_id TEXT,
            player_name TEXT,
            ovr INTEGER,
            player_data TEXT,
            locked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS squads (
            user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
            active_squad TEXT
        );

        CREATE TABLE IF NOT EXISTS global_drafts (
            draft_number INTEGER PRIMARY KEY,
            draft_data TEXT,
            pool_a TEXT,
            pool_b TEXT,
            pool_c TEXT,
            expires_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS store_player_shop (
            id BIGSERIAL PRIMARY KEY,
            slot INTEGER UNIQUE,
            player_data TEXT,
            price BIGINT,
            expires_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS market (
            id BIGSERIAL PRIMARY KEY,
            seller_id BIGINT REFERENCES users(user_id),
            inventory_id BIGINT,
            player_id TEXT,
            player_name TEXT,
            ovr INTEGER,
            price BIGINT,
            player_data TEXT,
            listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS custom_draft_cards (
            id BIGSERIAL PRIMARY KEY,
            player_data TEXT
        );

        CREATE TABLE IF NOT EXISTS portal_jobs (
            job_name TEXT PRIMARY KEY,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS formation_layouts (
            formation_name TEXT PRIMARY KEY,
            positions_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS active_sbcs (
            id BIGSERIAL PRIMARY KEY,
            sbc_json TEXT,
            expires_at BIGINT
        );

        CREATE TABLE IF NOT EXISTS sbc_completions (
            user_id BIGINT,
            sbc_id BIGINT,
            completed_at BIGINT,
            PRIMARY KEY (user_id, sbc_id)
        );

        CREATE TABLE IF NOT EXISTS season_pass (
            user_id BIGINT PRIMARY KEY,
            season_id INTEGER DEFAULT 1,
            xp BIGINT DEFAULT 0,
            claimed_tiers TEXT DEFAULT '[]',
            started_at BIGINT DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS achievements (
            user_id BIGINT,
            badge_id TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, badge_id)
        );

        CREATE TABLE IF NOT EXISTS user_stats (
            user_id BIGINT PRIMARY KEY,
            walkouts_pulled INTEGER DEFAULT 0,
            matches_won INTEGER DEFAULT 0,
            exchanges_done INTEGER DEFAULT 0,
            sbcs_done INTEGER DEFAULT 0,
            market_buys INTEGER DEFAULT 0,
            daily_streak INTEGER DEFAULT 0
        );
    ''')
    print("✅ Supabase PostgreSQL Connected and Verified!")

async def get_user(user_id: int) -> dict:
    global _USER_CACHE
    now = time.time()
    if user_id in _USER_CACHE:
        cached = _USER_CACHE[user_id]
        if now - cached.get('exp', 0) < 60:
            return cached['data']

    p = await get_db()
    row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    if row:
        data = dict(row)
    else:
        await p.execute('INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id)
        row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        if row:
            data = dict(row)
        else:
            data = {
                "user_id": user_id, "coins": 0, "vouchers": 0, "gems": 0, "fans": 0,
                "drafts_opened": 0, "drafts_since_walkout": 0, "is_private": 0
            }
    _USER_CACHE[user_id] = {"data": data, "exp": now}
    return data

async def add_coins(user_id: int, amount: int):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['coins'] = max(0, int(_USER_CACHE[user_id]['data'].get('coins', 0)) + int(amount))
    p = await get_db()
    await p.execute(
        'UPDATE users SET coins = GREATEST(0, coins + $1) WHERE user_id = $2',
        amount, user_id
    )

async def update_coins(user_id: int, amount: int):
    await add_coins(user_id, amount)

async def add_vouchers(user_id: int, amount: int):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['vouchers'] = max(0, int(_USER_CACHE[user_id]['data'].get('vouchers', 0)) + int(amount))
    p = await get_db()
    await p.execute(
        'UPDATE users SET vouchers = GREATEST(0, vouchers + $1) WHERE user_id = $2',
        amount, user_id
    )

async def update_vouchers(user_id: int, amount: int):
    await add_vouchers(user_id, amount)

async def get_daily_vouchers_bought(user_id: int) -> int:
    user = await get_user(user_id)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if user.get("last_voucher_buy_date") != today:
        return 0
    return int(user.get("daily_vouchers_bought", 0) or 0)

async def record_vouchers_bought(user_id: int, amount: int):
    global _USER_CACHE
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    user = await get_user(user_id)
    
    current = 0 if user.get("last_voucher_buy_date") != today else int(user.get("daily_vouchers_bought", 0) or 0)
    new_total = current + amount

    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['daily_vouchers_bought'] = new_total
        _USER_CACHE[user_id]['data']['last_voucher_buy_date'] = today

    p = await get_db()
    await p.execute('''
        UPDATE users 
        SET daily_vouchers_bought = $1, last_voucher_buy_date = $2
        WHERE user_id = $3
    ''', new_total, today, user_id)

async def update_gems(user_id: int, amount: int):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['gems'] = max(0, int(_USER_CACHE[user_id]['data'].get('gems', 0)) + int(amount))
    p = await get_db()
    await p.execute(
        'UPDATE users SET gems = GREATEST(0, gems + $1) WHERE user_id = $2',
        amount, user_id
    )

async def add_fans(user_id: int, amount: int):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['fans'] = max(0, int(_USER_CACHE[user_id]['data'].get('fans', 0)) + int(amount))
    p = await get_db()
    await p.execute(
        'UPDATE users SET fans = GREATEST(0, fans + $1) WHERE user_id = $2',
        amount, user_id
    )

async def increment_drafts(user_id: int, amount: int = 1):
    global _USER_CACHE
    if user_id in _USER_CACHE:
        _USER_CACHE[user_id]['data']['drafts_opened'] = int(_USER_CACHE[user_id]['data'].get('drafts_opened', 0)) + int(amount)
    p = await get_db()
    await p.execute(
        'UPDATE users SET drafts_opened = drafts_opened + $1 WHERE user_id = $2',
        amount, user_id
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
        data_str = json.dumps(player_data)
        records.append((user_id, player_id, player_name, ovr, data_str))
    
    await p.executemany(
        'INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data) VALUES ($1, $2, $3, $4, $5)',
        records
    )

async def get_inventory(user_id: int) -> list:
    now = time.time()
    if user_id in _USER_INVENTORY_CACHE:
        cached = _USER_INVENTORY_CACHE[user_id]
        if now - cached['exp'] < 20:
            return cached['data']
    p = await get_db()
    rows = await p.fetch('SELECT * FROM inventory WHERE user_id = $1 ORDER BY ovr DESC', user_id)
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
    if user_id in _USER_INVENTORY_CACHE:
        return len(_USER_INVENTORY_CACHE[user_id]['data'])
    p = await get_db()
    val = await p.fetchval('SELECT COUNT(*) FROM inventory WHERE user_id = $1', user_id)
    return val or 0

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
    p = await get_db()
    await p.execute('UPDATE inventory SET locked = 1 WHERE id = $1 AND user_id = $2', int(inv_id), user_id)

async def unlock_player(user_id: int, inv_id: int):
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
            int(d_num), pool_a_json, pool_a_json, pool_b_json, pool_c_json, exp
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
    for item in items:
        exp = _parse_timestamp(item.get("expires_at"))
        await p.execute(
            "INSERT INTO store_player_shop (player_data, price, expires_at) VALUES ($1, $2, $3)",
            json.dumps(item['player_data']), item['price'], exp
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
            CREATE TABLE IF NOT EXISTS global_exchange_pool (
                id INTEGER PRIMARY KEY DEFAULT 1,
                pool_data TEXT,
                expires_at TIMESTAMP
            );
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
    ''', int(draft_number), pool_a_json, pool_a_json, pool_b_json, pool_c_json, exp)
    
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



