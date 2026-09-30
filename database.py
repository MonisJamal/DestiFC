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

async def get_db():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            SUPABASE_URL,
            min_size=5,
            max_size=30,
            command_timeout=15,
            max_inactive_connection_lifetime=300.0,
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
    p = await get_db()
    row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    if row:
        return dict(row)
    await p.execute('INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', user_id)
    row = await p.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    if row:
        return dict(row)
    return {
        "user_id": user_id, "coins": 0, "vouchers": 0, "gems": 0, "fans": 0,
        "drafts_opened": 0, "drafts_since_walkout": 0, "is_private": 0
    }

async def add_coins(user_id: int, amount: int):
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'UPDATE users SET coins = GREATEST(0, coins + $1) WHERE user_id = $2',
        amount, user_id
    )

async def update_coins(user_id: int, amount: int):
    await add_coins(user_id, amount)

async def add_vouchers(user_id: int, amount: int):
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'UPDATE users SET vouchers = GREATEST(0, vouchers + $1) WHERE user_id = $2',
        amount, user_id
    )

async def update_vouchers(user_id: int, amount: int):
    await add_vouchers(user_id, amount)

async def update_gems(user_id: int, amount: int):
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'UPDATE users SET gems = GREATEST(0, gems + $1) WHERE user_id = $2',
        amount, user_id
    )

async def add_fans(user_id: int, amount: int):
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'UPDATE users SET fans = GREATEST(0, fans + $1) WHERE user_id = $2',
        amount, user_id
    )

async def increment_drafts(user_id: int, amount: int = 1):
    await get_user(user_id)
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

async def add_player_to_inventory(user_id: int, player_data: dict):
    await add_players_to_inventory_batch(user_id, [player_data])

async def add_players_to_inventory_batch(user_id: int, player_list: list):
    if not player_list:
        return
    await get_user(user_id)
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
    await get_user(user_id)
    p = await get_db()
    rows = await p.fetch('SELECT * FROM inventory WHERE user_id = $1 ORDER BY ovr DESC', user_id)
    return [dict(r) for r in rows]

async def get_inventory_size(user_id: int) -> int:
    await get_user(user_id)
    p = await get_db()
    val = await p.fetchval('SELECT COUNT(*) FROM inventory WHERE user_id = $1', user_id)
    return val or 0

async def remove_players_from_inventory(user_id: int, inventory_ids: list):
    if not inventory_ids:
        return
    await get_user(user_id)
    p = await get_db()
    int_ids = [int(x) for x in inventory_ids]
    await p.execute(
        'DELETE FROM inventory WHERE user_id = $1 AND id = ANY($2::bigint[])',
        user_id, int_ids
    )

async def get_squad(user_id: int) -> dict:
    await get_user(user_id)
    p = await get_db()
    row = await p.fetchrow('SELECT active_squad FROM squads WHERE user_id = $1', user_id)
    if row and row['active_squad']:
        data = json.loads(row['active_squad'])
        if "formation" not in data:
            data = {"formation": "4-3-3", "players": data}
        return data
    
    default_squad = {
        "formation": "4-3-3",
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
    return default_squad

async def update_squad(user_id: int, squad: dict):
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
            "INSERT INTO store_player_shop (slot, player_data, price, expires_at) VALUES ($1, $2, $3, $4)",
            int(item["slot"]), json.dumps(item["player"]), int(item["price"]), exp
        )

async def add_custom_draft_card(player_data):
    global _CUSTOM_DRAFT_CARDS_CACHE
    _CUSTOM_DRAFT_CARDS_CACHE = None
    p = await get_db()
    await p.execute('INSERT INTO custom_draft_cards (player_data) VALUES ($1)', json.dumps(player_data))

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

async def increment_drafts_since_walkout(user_id: int, amount: int = 1):
    await get_user(user_id)
    p = await get_db()
    await p.execute(
        'UPDATE users SET drafts_since_walkout = COALESCE(drafts_since_walkout, 0) + $1 WHERE user_id = $2',
        amount, user_id
    )

async def reset_drafts_since_walkout(user_id: int):
    p = await get_db()
    await p.execute('UPDATE users SET drafts_since_walkout = 0 WHERE user_id = $1', user_id)

async def set_drafts_since_walkout(user_id: int, count: int):
    await get_user(user_id)
    p = await get_db()
    await p.execute('UPDATE users SET drafts_since_walkout = $1 WHERE user_id = $2', count, user_id)

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

