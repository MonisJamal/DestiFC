import asyncio
import json
import time
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

import database
from renderz_api import query_players_by_program, search_fifarenderz
from maps import nation_map, club_map

def get_club_string(c_raw):
    if isinstance(c_raw, dict):
        cid = c_raw.get("id")
        return club_map.get(cid, c_raw.get("name", "Club"))
    return str(c_raw or "Club")

def get_nation_string(n_raw):
    if isinstance(n_raw, dict):
        nid = n_raw.get("id")
        return nation_map.get(nid, n_raw.get("name", "World"))
    return str(n_raw or "World")

def clean_player_name(pl):
    return pl.get("cardName") or pl.get("lastName") or pl.get("commonName") or pl.get("firstName") or "Player"

async def sync_renderz_cards(min_ovr: int = 105, max_ovr: int = 125, fetch_leaks: bool = True):
    """
    Syncs the latest cards and unreleased leaks from RenderZ into PostgreSQL official_cards table
    and triggers a refresh of the in-memory RAM cache for bot drafts and packs.
    """
    print(f"[RenderZ Sync] Starting sync for OVR range {min_ovr}-{max_ovr} (fetch_leaks={fetch_leaks})...")
    start_time = time.time()
    all_players = {}

    # 1. Rating Tiers (High OVR priority for bot drafts & pools)
    ratings = list(range(max_ovr, min_ovr - 1, -1))
    for r in ratings:
        for offset in range(0, 96, 48):
            batch = query_players_by_program("", size=48, from_offset=offset, min_rating=r, max_rating=r)
            if not batch:
                break
            for pl in batch:
                aid = pl.get("assetId") or pl.get("id")
                if aid:
                    all_players[aid] = pl
            if len(batch) < 48:
                break
        await asyncio.sleep(0.05)

    # 2. Fetch Newly Added / Unreleased Leaks & Data-Mines
    if fetch_leaks:
        try:
            # Query recently data-mined cards
            for offset in range(0, 100, 50):
                batch = search_fifarenderz("", size=50, from_offset=offset)
                if not batch:
                    break
                for pl in batch:
                    aid = pl.get("assetId") or pl.get("id")
                    if aid:
                        all_players[aid] = pl
                if len(batch) < 50:
                    break
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[RenderZ Sync] Warning: failed to fetch leaks batch: {e}")

    # 3. Famous superstars to guarantee their cards are present
    superstars = [
        "Messi", "Ronaldo", "Cristiano", "Zidane", "Cruyff", "Mbappe", "Mbappé",
        "Haaland", "Neymar", "Ronaldinho", "Gullit", "Maldini", "Pele", "Pelé",
        "Henry", "Bellingham", "Vinicius", "Salah", "Kaka", "Kaká", "Rivaldo",
        "Beckham", "Maradona", "Yashin", "Buffon", "Courtois", "Van Dijk",
        "Vieira", "Rodri", "De Bruyne", "Kane", "Saka", "Foden", "Yamal",
        "Musiala", "Wirtz", "Lewandowski", "Son", "Van Nistelrooy", "Zanetti"
    ]
    for name in superstars:
        try:
            batch = search_fifarenderz(name, size=24)
            for pl in batch:
                aid = pl.get("assetId") or pl.get("id")
                if aid:
                    all_players[aid] = pl
            await asyncio.sleep(0.02)
        except Exception:
            pass

    print(f"[RenderZ Sync] Collected {len(all_players)} cards from RenderZ. Preparing database insert...")

    p = await database.get_db()
    existing_asset_ids = set([r[0] for r in await p.fetch("SELECT asset_id FROM official_cards")])
    new_cards_count = 0

    rows = []
    for aid, pl in all_players.items():
        if aid not in existing_asset_ids:
            new_cards_count += 1

        pname = clean_player_name(pl)
        cname = pl.get("cardName") or pname
        ovr = int(pl.get("rating") or 100)
        pos = pl.get("position") or "ST"
        src = pl.get("source") or "PROGRAM_RENDERZ"
        c_str = get_club_string(pl.get("club"))
        n_str = get_nation_string(pl.get("nation"))

        rows.append((
            int(aid),
            pname,
            cname,
            ovr,
            pos,
            src,
            c_str,
            n_str,
            json.dumps(pl)
        ))

    # Batch upsert in chunks of 200
    chunk_size = 200
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        await p.executemany("""
            INSERT INTO official_cards (asset_id, player_name, card_name, rating, position, source, club_name, nation_name, player_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            ON CONFLICT (asset_id) DO UPDATE SET
                player_name = EXCLUDED.player_name,
                card_name = EXCLUDED.card_name,
                rating = EXCLUDED.rating,
                position = EXCLUDED.position,
                source = EXCLUDED.source,
                club_name = EXCLUDED.club_name,
                nation_name = EXCLUDED.nation_name,
                player_data = EXCLUDED.player_data;
        """, chunk)

    # Preload and refresh official cards in bot RAM cache
    await database.preload_official_cards_cache()

    total_in_db = await p.fetchval("SELECT count(*) FROM official_cards")
    duration = round(time.time() - start_time, 2)

    result_summary = {
        "status": "success",
        "scraped": len(all_players),
        "new_cards_added": new_cards_count,
        "total_official_cards": total_in_db,
        "duration_seconds": duration,
        "synced_at": datetime.datetime.now().isoformat()
    }
    print(f"[RenderZ Sync] Complete in {duration}s! New cards added: {new_cards_count}. Total in DB: {total_in_db}")
    return result_summary

if __name__ == "__main__":
    asyncio.run(sync_renderz_cards(min_ovr=110, max_ovr=125, fetch_leaks=True))
