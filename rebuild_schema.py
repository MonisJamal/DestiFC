import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def rebuild_schema():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set in .env")
        return
        
    print(f"Connecting to database...")
    conn = await asyncpg.connect(db_url)
    
    tables = [
        "player_stats", "user_signature_box", "signature_box_config",
        "sbc_completions", "active_sbcs", "global_exchange_pool",
        "store_player_shop", "global_drafts", "season_pass",
        "achievements", "user_stats", "formation_layouts",
        "portal_jobs", "matches", "market", "custom_draft_cards",
        "official_cards", "squads", "inventory", "system_settings",
        "admin_users", "users"
    ]
    
    print("Dropping ALL existing tables...")
    for table in tables:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        print(f"  Dropped {table}")
        
    print("\nCreating all tables from scratch...")
    
    # ============================================================
    # TABLE: users
    # Used by: database.py, cogs/economy.py, cogs/admin.py, cogs/draft.py, etc.
    # ============================================================
    await conn.execute("""
    CREATE TABLE users (
        user_id BIGINT PRIMARY KEY,
        coins BIGINT DEFAULT 0,
        vouchers BIGINT DEFAULT 0,
        gems BIGINT DEFAULT 0,
        fans BIGINT DEFAULT 0,
        drafts_opened BIGINT DEFAULT 0,
        drafts_since_walkout BIGINT DEFAULT 0,
        draft_pity JSONB DEFAULT '{"1":0,"2":0,"3":0}'::jsonb,
        is_private BIGINT DEFAULT 0,
        starter_claimed BIGINT DEFAULT 0,
        daily_vouchers_bought INTEGER DEFAULT 0,
        last_voucher_buy_date TEXT,
        last_quest_daily BIGINT DEFAULT 0,
        last_quest_skill BIGINT DEFAULT 0,
        last_quest_h2h BIGINT DEFAULT 0,
        last_quest_freekick BIGINT DEFAULT 0,
        last_quest_dribble BIGINT DEFAULT 0,
        last_quest_trivia BIGINT DEFAULT 0,
        last_quest_gk BIGINT DEFAULT 0,
        last_quest_volley BIGINT DEFAULT 0,
        last_daily BIGINT DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_spin BIGINT DEFAULT 0,
        last_work BIGINT DEFAULT 0,
        last_match_time BIGINT DEFAULT 0,
        draft_battle_wins INTEGER DEFAULT 0,
        draft_battle_losses INTEGER DEFAULT 0,
        draft_battle_draws INTEGER DEFAULT 0,
        draft_battle_elo INTEGER DEFAULT 1200,
        draft_battle_points INTEGER DEFAULT 0
    );
    """)
    print("  ✅ users")
    
    # ============================================================
    # TABLE: inventory
    # Used by: database.py (INSERT/SELECT/UPDATE/DELETE)
    # Columns from: INSERT INTO inventory (user_id, player_id, player_name, ovr, position, player_data)
    #               SELECT id, user_id, player_id, player_name, ovr, position, locked, player_data
    # ============================================================
    await conn.execute("""
    CREATE TABLE inventory (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        player_id TEXT,
        player_name TEXT,
        ovr INTEGER,
        position TEXT,
        player_data JSONB,
        locked INTEGER DEFAULT 0
    );
    CREATE INDEX idx_inventory_user ON inventory(user_id);
    """)
    print("  ✅ inventory")
    
    # ============================================================
    # TABLE: squads
    # Used by: database.py - SELECT active_squad / INSERT ... active_squad
    # ============================================================
    await conn.execute("""
    CREATE TABLE squads (
        user_id BIGINT PRIMARY KEY,
        active_squad JSONB
    );
    """)
    print("  ✅ squads")
    
    # ============================================================
    # TABLE: global_drafts
    # database.py: SELECT draft_number, pool_a, pool_b, pool_c, expires_at
    # INSERT INTO global_drafts (draft_number, draft_data, pool_a, pool_b, pool_c, expires_at)
    # expires_at is passed via _parse_timestamp() which returns datetime → TIMESTAMP
    # ============================================================
    await conn.execute("""
    CREATE TABLE global_drafts (
        draft_number INTEGER PRIMARY KEY,
        draft_data JSONB,
        pool_a JSONB,
        pool_b JSONB,
        pool_c JSONB,
        expires_at TIMESTAMP
    );
    """)
    print("  ✅ global_drafts")
    
    # ============================================================
    # TABLE: store_player_shop
    # database.py: SELECT slot, player_data, price, expires_at
    # INSERT INTO store_player_shop (slot, player_data, price, expires_at)
    # expires_at is passed via _parse_timestamp() → TIMESTAMP
    # ============================================================
    await conn.execute("""
    CREATE TABLE store_player_shop (
        slot INTEGER PRIMARY KEY,
        player_data JSONB,
        price BIGINT,
        expires_at TIMESTAMP
    );
    """)
    print("  ✅ store_player_shop")
    
    # ============================================================
    # TABLE: market
    # cogs/market.py: INSERT INTO market (seller_id, inventory_id, player_id, player_name, ovr, price, player_data)
    #                 SELECT * FROM market WHERE ...
    # ============================================================
    await conn.execute("""
    CREATE TABLE market (
        id BIGSERIAL PRIMARY KEY,
        seller_id BIGINT NOT NULL,
        inventory_id BIGINT,
        player_id TEXT,
        player_name TEXT,
        ovr INTEGER,
        price BIGINT NOT NULL,
        player_data JSONB,
        listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active'
    );
    """)
    print("  ✅ market")
    
    # ============================================================
    # TABLE: custom_draft_cards
    # database.py: INSERT INTO custom_draft_cards (player_data)
    #              SELECT id, player_data FROM custom_draft_cards
    #              WHERE (exchange_exclusive IS NULL OR exchange_exclusive = 0)
    # ============================================================
    await conn.execute("""
    CREATE TABLE custom_draft_cards (
        id BIGSERIAL PRIMARY KEY,
        player_data JSONB,
        exchange_exclusive INTEGER DEFAULT 0
    );
    """)
    print("  ✅ custom_draft_cards")
    
    # ============================================================
    # TABLE: official_cards
    # database.py: SELECT rating, player_data FROM official_cards WHERE rating >= $1
    #              WHERE (exchange_exclusive IS NULL OR exchange_exclusive = 0)
    #              SELECT MAX(rating) FROM official_cards
    # ============================================================
    await conn.execute("""
    CREATE TABLE official_cards (
        id SERIAL PRIMARY KEY,
        asset_id INTEGER,
        player_name TEXT,
        card_name TEXT,
        rating INTEGER NOT NULL,
        position TEXT,
        source TEXT,
        club_name TEXT,
        nation_name TEXT,
        player_data JSONB NOT NULL,
        exchange_exclusive INTEGER DEFAULT 0
    );
    CREATE INDEX idx_official_cards_rating ON official_cards(rating);
    """)
    print("  ✅ official_cards")
    
    # ============================================================
    # TABLE: matches
    # database.py/cogs/match.py: match results storage
    # ============================================================
    await conn.execute("""
    CREATE TABLE matches (
        id BIGSERIAL PRIMARY KEY,
        user1_id BIGINT,
        user2_id BIGINT,
        winner_id BIGINT,
        match_data JSONB,
        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ matches")
    
    # ============================================================
    # TABLE: system_settings
    # database.py: SELECT value FROM system_settings WHERE key = $1
    #              INSERT INTO system_settings (key, value) ... ON CONFLICT (key) DO UPDATE SET value = $2
    # Used for: bot_config, luck_settings, gameplay_settings, compensation_config, season_config
    # ============================================================
    await conn.execute("""
    CREATE TABLE system_settings (
        key TEXT PRIMARY KEY,
        value JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ system_settings")
    
    # ============================================================
    # TABLE: active_sbcs
    # cogs/sbc.py: INSERT INTO active_sbcs (sbc_json, expires_at) VALUES ($1, $2)
    #              SELECT id, sbc_json, expires_at FROM active_sbcs WHERE expires_at > $1
    #              expires_at compared with int(time.time()) → BIGINT
    #              sbc_json is passed as json.dumps() string → TEXT
    # ============================================================
    await conn.execute("""
    CREATE TABLE active_sbcs (
        id BIGSERIAL PRIMARY KEY,
        sbc_json TEXT,
        expires_at BIGINT
    );
    """)
    print("  ✅ active_sbcs")
    
    # ============================================================
    # TABLE: sbc_completions
    # cogs/sbc.py: INSERT INTO sbc_completions (user_id, sbc_id, completed_at)
    #              SELECT 1 FROM sbc_completions WHERE user_id = $1 AND sbc_id = $2
    #              sbc_id comes from active_sbcs.id (BIGINT serial)
    #              completed_at uses int(time.time()) → BIGINT
    # ============================================================
    await conn.execute("""
    CREATE TABLE sbc_completions (
        user_id BIGINT,
        sbc_id BIGINT,
        completed_at BIGINT,
        PRIMARY KEY (user_id, sbc_id)
    );
    """)
    print("  ✅ sbc_completions")
    
    # ============================================================
    # TABLE: season_pass
    # cogs/season.py: CREATE TABLE IF NOT EXISTS season_pass (
    #     user_id BIGINT PRIMARY KEY, season_id INTEGER DEFAULT 1,
    #     xp BIGINT DEFAULT 0, claimed_tiers TEXT DEFAULT '[]', started_at BIGINT DEFAULT 0)
    # ============================================================
    await conn.execute("""
    CREATE TABLE season_pass (
        user_id BIGINT PRIMARY KEY,
        season_id INTEGER DEFAULT 1,
        xp BIGINT DEFAULT 0,
        claimed_tiers TEXT DEFAULT '[]',
        started_at BIGINT DEFAULT 0
    );
    """)
    print("  ✅ season_pass")
    
    # ============================================================
    # TABLE: achievements
    # cogs/achievements.py: CREATE TABLE IF NOT EXISTS achievements (
    #     user_id BIGINT, badge_id TEXT, unlocked_at TIMESTAMP, PRIMARY KEY (user_id, badge_id))
    # ============================================================
    await conn.execute("""
    CREATE TABLE achievements (
        user_id BIGINT,
        badge_id TEXT,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, badge_id)
    );
    """)
    print("  ✅ achievements")
    
    # ============================================================
    # TABLE: user_stats
    # cogs/achievements.py: CREATE TABLE IF NOT EXISTS user_stats (
    #     user_id BIGINT PRIMARY KEY, walkouts_pulled INTEGER, etc.)
    # cogs/compensation.py: SELECT stats FROM user_stats / INSERT ... stats JSONB
    # ============================================================
    await conn.execute("""
    CREATE TABLE user_stats (
        user_id BIGINT PRIMARY KEY,
        walkouts_pulled INTEGER DEFAULT 0,
        matches_won INTEGER DEFAULT 0,
        exchanges_done INTEGER DEFAULT 0,
        sbcs_done INTEGER DEFAULT 0,
        market_buys INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        stats JSONB
    );
    """)
    print("  ✅ user_stats")
    
    # ============================================================
    # TABLE: formation_layouts
    # database.py: SELECT formation_name, positions_json FROM formation_layouts
    # vercel: INSERT INTO formation_layouts (formation_name, positions_json, updated_at)
    # ============================================================
    await conn.execute("""
    CREATE TABLE formation_layouts (
        formation_name TEXT PRIMARY KEY,
        positions_json JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ formation_layouts")
    
    # ============================================================
    # TABLE: portal_jobs
    # main.py: SELECT id, job_type, payload FROM portal_jobs WHERE status = 'pending' AND job_type IN (...)
    #          UPDATE portal_jobs SET status = 'completed', result = '...' WHERE id = $1
    # database.py: SELECT 1 FROM portal_jobs WHERE job_name = $1
    # vercel: INSERT INTO portal_jobs (job_name, job_type, payload, status, requested_at)
    #         UPDATE portal_jobs SET status = 'failed', error = '...'
    # ============================================================
    await conn.execute("""
    CREATE TABLE portal_jobs (
        id BIGSERIAL PRIMARY KEY,
        job_name TEXT,
        job_type TEXT,
        status TEXT DEFAULT 'pending',
        payload JSONB DEFAULT '{}'::jsonb,
        result TEXT,
        error TEXT,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ portal_jobs")
    
    # ============================================================
    # TABLE: signature_box_config
    # database.py: SELECT * FROM signature_box_config WHERE id = 1
    #              INSERT INTO signature_box_config (id, title, subtitle, is_active, banner_url,
    #                  expires_at, signature_card_data, rewards_json, draw_costs_json, updated_at)
    #              is_active is passed as bool() → BOOLEAN
    # cogs/admin.py: SELECT is_active, title, starts_at, expires_at
    # ============================================================
    await conn.execute("""
    CREATE TABLE signature_box_config (
        id INTEGER PRIMARY KEY,
        title TEXT,
        subtitle TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        banner_url TEXT,
        expires_at TIMESTAMP,
        starts_at TIMESTAMP,
        signature_card_data JSONB,
        rewards_json JSONB,
        draw_costs_json JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ signature_box_config")
    
    # ============================================================
    # TABLE: user_signature_box
    # database.py: INSERT INTO user_signature_box (user_id, box_id, claimed_reward_ids, draws_completed)
    #              SELECT * FROM user_signature_box WHERE user_id = $1
    # ============================================================
    await conn.execute("""
    CREATE TABLE user_signature_box (
        user_id BIGINT PRIMARY KEY,
        box_id INTEGER DEFAULT 1,
        claimed_reward_ids JSONB DEFAULT '[]'::jsonb,
        draws_completed INTEGER DEFAULT 0,
        last_drawn_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    print("  ✅ user_signature_box")
    
    # ============================================================
    # TABLE: global_exchange_pool
    # database.py: SELECT pool_data, expires_at FROM global_exchange_pool WHERE id = 1
    #              INSERT INTO global_exchange_pool (id, pool_data, expires_at) ...
    #              expires_at passed via _parse_timestamp() → TIMESTAMP
    # ============================================================
    await conn.execute("""
    CREATE TABLE global_exchange_pool (
        id INTEGER PRIMARY KEY DEFAULT 1,
        pool_data JSONB,
        expires_at TIMESTAMP
    );
    """)
    print("  ✅ global_exchange_pool")
    
    # ============================================================
    # TABLE: player_stats
    # database.py: INSERT INTO player_stats (user_id, player_name, player_id, position, ovr,
    #     matches_played, goals, assists, clean_sheets, yellow_cards, red_cards, total_rating, motm_count)
    #     ON CONFLICT (user_id, player_name) DO UPDATE SET ...
    # ============================================================
    await conn.execute("""
    CREATE TABLE player_stats (
        user_id BIGINT,
        player_name TEXT,
        player_id TEXT,
        position TEXT,
        ovr INTEGER,
        matches_played INTEGER DEFAULT 0,
        goals INTEGER DEFAULT 0,
        assists INTEGER DEFAULT 0,
        clean_sheets INTEGER DEFAULT 0,
        yellow_cards INTEGER DEFAULT 0,
        red_cards INTEGER DEFAULT 0,
        total_rating NUMERIC DEFAULT 0,
        motm_count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, player_name)
    );
    """)
    print("  ✅ player_stats")
    
    # ============================================================
    # TABLE: admin_users
    # vercel: /api/auth/me → SELECT * FROM admin_users WHERE username = $1
    # ============================================================
    await conn.execute("""
    CREATE TABLE admin_users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT,
        password_hash TEXT,
        display_name TEXT,
        role TEXT DEFAULT 'admin',
        permissions JSONB DEFAULT '[]'::jsonb,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    );
    """)
    print("  ✅ admin_users")
    
    # ============================================================
    # VERIFICATION
    # ============================================================
    print("\n" + "="*60)
    print("VERIFICATION — All tables and columns:")
    print("="*60)
    
    all_tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    
    for t in all_tables:
        tname = t['table_name']
        cols = await conn.fetch("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = $1 ORDER BY ordinal_position
        """, tname)
        print(f"\n📋 {tname} ({len(cols)} columns)")
        for c in cols:
            print(f"   {c['column_name']:30s} {c['data_type']:20s} {c['column_default'] or ''}")
    
    print(f"\n✅ Total tables created: {len(all_tables)}")
    await conn.close()
    print("\n🎉 Database schema rebuild COMPLETE!")

if __name__ == "__main__":
    asyncio.run(rebuild_schema())
