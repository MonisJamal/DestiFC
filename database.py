import aiosqlite
import json

DB_FILE = "destifc.db"

async def setup():
    async with aiosqlite.connect(DB_FILE) as db:
        # Enable Write-Ahead Logging for absolute data safety and concurrent writes
        await db.execute('PRAGMA journal_mode=WAL;')
        await db.execute('PRAGMA synchronous=NORMAL;')
        
        # Users table (economy and basic stats)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                vouchers INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0
            )
        ''')
        # Inventory table (users' collected players)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                player_id TEXT,
                player_name TEXT,
                ovr INTEGER,
                player_data TEXT, -- JSON string of full player stats
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        # Squads table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS squads (
                user_id INTEGER PRIMARY KEY,
                active_squad TEXT, -- JSON array of inventory IDs
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
                await db.commit()
                return {"user_id": user_id, "coins": 0, "vouchers": 0, "gems": 0, "fans": 0, "drafts_opened": 0}
            return dict(row)

async def increment_drafts(user_id: int, amount: int = 1):
    await get_user(user_id)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET drafts_opened = drafts_opened + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def add_fans(user_id: int, amount: int):
    await get_user(user_id)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET fans = max(0, fans + ?) WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def get_leaderboard(limit: int = 10):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT user_id, fans FROM users ORDER BY fans DESC LIMIT ?', (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def remove_players_from_inventory(user_id: int, inventory_ids: list):
    if not inventory_ids: return
    async with aiosqlite.connect(DB_FILE) as db:
        placeholders = ','.join('?' for _ in inventory_ids)
        query = f'DELETE FROM inventory WHERE user_id = ? AND id IN ({placeholders})'
        await db.execute(query, [user_id] + inventory_ids)
        await db.commit()

async def add_vouchers(user_id: int, amount: int):
    await get_user(user_id) # ensure user exists
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET vouchers = vouchers + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()

async def add_player_to_inventory(user_id: int, player_data: dict):
    await get_user(user_id)
    player_id = str(player_data.get('id', 'unknown'))
    player_name = player_data.get('cardName') or player_data.get('lastName', 'Unknown')
    ovr = player_data.get('rating', 0)
    data_str = json.dumps(player_data)
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            'INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data) VALUES (?, ?, ?, ?, ?)',
            (user_id, player_id, player_name, ovr, data_str)
        )
        await db.commit()

async def get_inventory(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM inventory WHERE user_id = ? ORDER BY ovr DESC', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_squad(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT active_squad FROM squads WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row['active_squad']:
                data = json.loads(row['active_squad'])
                # Migration for old data structure
                if "formation" not in data:
                    data = {
                        "formation": "4-3-3",
                        "players": data
                    }
                return data
            
            # Default empty squad (4-3-3)
            default_squad = {
                "formation": "4-3-3",
                "players": {
                    "LW": None, "ST": None, "RW": None,
                    "CM1": None, "CM2": None, "CM3": None,
                    "LB": None, "CB1": None, "CB2": None, "RB": None,
                    "GK": None
                }
            }
            await db.execute('INSERT OR REPLACE INTO squads (user_id, active_squad) VALUES (?, ?)', 
                             (user_id, json.dumps(default_squad)))
            await db.commit()
            return default_squad

async def update_squad(user_id: int, squad: dict):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO squads (user_id, active_squad) VALUES (?, ?)', 
                         (user_id, json.dumps(squad)))
        await db.commit()

async def get_player_by_inv_id(user_id: int, inv_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM inventory WHERE id = ? AND user_id = ?', (inv_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_active_drafts():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT draft_number, pool_a, pool_b, pool_c, expires_at FROM global_drafts") as cursor:
            rows = await cursor.fetchall()
            if not rows: return None
            import json
            drafts = {}
            for row in rows:
                drafts[row[0]] = {
                    "pool_a": json.loads(row[1]),
                    "pool_b": json.loads(row[2]),
                    "pool_c": json.loads(row[3]),
                    "expires_at": row[4]
                }
            return drafts

async def set_active_drafts(drafts_dict):
    async with aiosqlite.connect(DB_FILE) as db:
        import json
        await db.execute("DELETE FROM global_drafts")
        for d_num, data in drafts_dict.items():
            await db.execute(
                "INSERT INTO global_drafts (draft_number, pool_a, pool_b, pool_c, expires_at) VALUES (?, ?, ?, ?, ?)",
                (d_num, json.dumps(data["pool_a"]), json.dumps(data["pool_b"]), json.dumps(data["pool_c"]), data["expires_at"])
            )
        await db.commit()
