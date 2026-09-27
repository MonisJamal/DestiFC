from renderz_api import query_players_by_program
players = query_players_by_program("", min_rating=120, max_rating=122, size=100)
nations = set()
for p in players:
    n_id = p.get('nation', {}).get('id')
    name = p.get('cardName') or p.get('lastName', 'Unknown')
    if n_id: nations.add((n_id, name))
for n in sorted(list(nations), key=lambda x: x[0]):
    print(f"Nation {n[0]}: {n[1]}")
