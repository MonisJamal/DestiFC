import asyncio
import json
import database
from renderz_api import query_players_by_program, search_fifarenderz
from maps import nation_map, club_map

async def main():
    p = await database.get_db()
    print("Ensuring official_cards table exists...")
    await p.execute("""
        CREATE TABLE IF NOT EXISTS official_cards (
            asset_id BIGINT PRIMARY KEY,
            player_name TEXT NOT NULL,
            card_name TEXT,
            rating INT NOT NULL,
            position TEXT NOT NULL,
            source TEXT,
            club_name TEXT,
            nation_name TEXT,
            player_data JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_official_cards_rating ON official_cards(rating DESC);
        CREATE INDEX IF NOT EXISTS idx_official_cards_name ON official_cards(player_name);
        CREATE INDEX IF NOT EXISTS idx_official_cards_pos ON official_cards(position);
    """)

    all_players = {}

    # 1. Fetch top ratings 122 down to 105
    for r in [122, 121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105]:
        for offset in range(0, 72, 24):
            batch = query_players_by_program("", size=24, from_offset=offset, min_rating=r, max_rating=r)
            if not batch:
                break
            for pl in batch:
                aid = pl.get("assetId")
                if aid:
                    all_players[aid] = pl

    # 2. Fetch popular superstar searches
    superstars = [
        "Messi", "Ronaldo", "Cristiano", "Zidane", "Cruyff", "Mbappe", "Mbappé",
        "Haaland", "Neymar", "Ronaldinho", "Gullit", "Maldini", "Pele", "Pelé",
        "Henry", "Bellingham", "Vinicius", "Salah", "Kaka", "Kaká", "Rivaldo",
        "Beckham", "Maradona", "Yashin", "Buffon", "Courtois", "Van Dijk",
        "Vieira", "Rodri", "De Bruyne", "Kane", "Saka", "Foden", "Yamal",
        "Musiala", "Wirtz", "Lewandowski", "Son", "Alvarez", "Lautaro", "Garrincha"
    ]
    for name in superstars:
        batch = search_fifarenderz(name, size=24)
        for pl in batch:
            aid = pl.get("assetId")
            if aid:
                all_players[aid] = pl

    print(f"Collected {len(all_players)} official players. Batch inserting...")

    rows = []
    for aid, pl in all_players.items():
        pname = pl.get("cardName") or pl.get("lastName") or pl.get("commonName") or "Player"
        cname = pl.get("cardName") or pname
        ovr = int(pl.get("rating") or 100)
        pos = pl.get("position") or "ST"
        src = pl.get("source") or ""
        
        c_raw = pl.get("club")
        if isinstance(c_raw, dict):
            cid = c_raw.get("id")
            c_str = club_map.get(cid, c_raw.get("name", "Club"))
        else:
            c_str = str(c_raw or "Club")

        n_raw = pl.get("nation")
        if isinstance(n_raw, dict):
            nid = n_raw.get("id")
            n_str = nation_map.get(nid, n_raw.get("name", "World"))
        else:
            n_str = str(n_raw or "World")

        rows.append((aid, pname, cname, ovr, pos, src, c_str, n_str, json.dumps(pl)))

    # Batch insert in chunks of 200 with executemany
    chunk_size = 200
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        await p.executemany("""
            INSERT INTO official_cards (asset_id, player_name, card_name, rating, position, source, club_name, nation_name, player_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (asset_id) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                card_name = EXCLUDED.card_name,
                rating = EXCLUDED.rating,
                position = EXCLUDED.position,
                source = EXCLUDED.source,
                club_name = EXCLUDED.club_name,
                nation_name = EXCLUDED.nation_name,
                player_data = EXCLUDED.player_data
        """, chunk)
        print(f"Inserted batch {i // chunk_size + 1}/{(len(rows) + chunk_size - 1) // chunk_size}...")

    c = await p.fetch("SELECT count(*) FROM official_cards")
    print(f"🎉 Complete! Total official cards in Supabase: {c[0]['count']}")

if __name__ == "__main__":
    asyncio.run(main())
