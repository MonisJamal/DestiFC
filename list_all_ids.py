from renderz_api import query_players_by_program
import json

all_players = []
for offset in range(0, 300, 24):
    players = query_players_by_program("", min_rating=120, max_rating=122, size=24, from_offset=offset)
    if not players: break
    all_players.extend(players)

nations = set()
clubs = set()

for p in all_players:
    n_id = p.get('nation', {}).get('id')
    n_name = p.get('nation', {}).get('name')
    c_id = p.get('club', {}).get('id')
    c_name = p.get('club', {}).get('name')
    card = p.get('cardName') or p.get('lastName', 'Unknown')
    
    if n_id: nations.add((n_id, n_name, card))
    if c_id: clubs.add((c_id, c_name, card))

print("--- NATIONS ---")
for n in sorted(list(nations), key=lambda x: x[0]):
    print(f"{n[0]}: {n[1]} ({n[2]})")

print("\n--- CLUBS ---")
for c in sorted(list(clubs), key=lambda x: x[0]):
    print(f"{c[0]}: {c[1]} ({c[2]})")
