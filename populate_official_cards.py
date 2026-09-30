import asyncio
import json
import database
from renderz_api import query_players_by_program, search_fifarenderz
from maps import nation_map, club_map

async def main():
    p = await database.get_db()
    print("Creating official_cards table in Supabase...")
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
    print("Table official_cards ready.")

    print("Fetching top players from RenderZ to populate Supabase...")
    all_players = {}

    # Fetch 122 down to 110
    for r in [122, 121, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110]:
        print(f"Fetching rating {r}...")
        for offset in range(0, 120, 24):
            batch = query_players_by_program("", size=24, from_offset=offset, min_rating=r, max_rating=r)
            if not batch:
                break
            for pl in batch:
                aid = pl.get("assetId")
                if aid:
                    all_players[aid] = pl
        print(f"Total collected so far: {len(all_players)}")

    # Fetch famous player searches (Messi, Ronaldo, Zidane, Cruyff, Mbappe, Haaland, Neymar, Ronaldinho, Gullit, Maldini, Pele, etc.)
    famous = ["Messi", "Ronaldo", "Zidane", "Cruyff", "Mbappe", "Haaland", "Neymar", "Ronaldinho", "Gullit", "Maldini", "Pele", "Henry", "Bellingham", "Vinicius", "Salah", "Kaka", "Rivaldo", "Beckham", "Maradona", "Yashin", "Buffon", "Courtois", "Van Dijk", "Vieira", "Rodri", "De Bruyne"]
    for query in famous:
        print(f"Searching famous '{query}'...")
        batch = search_fifarenderz(query, size=24)
        for pl in batch:
            aid = pl.get("assetId")
            if aid:
                all_players[aid] = pl

    print(f"Saving {len(all_players)} official cards into Supabase...")

    inserted = 0
    for aid, pl in all_players.items():
        pname = pl.get("cardName") or pl.get("lastName") or pl.get("commonName") or "Player"
        cname = pl.get("cardName") or pname
        ovr = int(pl.get("rating") or 100)
        pos = pl.get("position") or "ST"
        src = pl.get("source") or ""
        
        # Resolve club/nation text
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

        await p.execute("""
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
        """, aid, pname, cname, ovr, pos, src, c_str, n_str, json.dumps(pl))
        inserted += 1

    print(f"✅ Successfully inserted/updated {inserted} official cards in Supabase!")

if __name__ == "__main__":
    asyncio.run(main())
