from renderz_api import query_players_by_program
players = query_players_by_program("", min_rating=120, max_rating=122, size=100)
clubs = set()
for p in players:
    c_id = p.get('club', {}).get('id')
    name = p.get('cardName') or p.get('lastName', 'Unknown')
    if c_id: clubs.add((c_id, name))
for c in sorted(list(clubs), key=lambda x: x[0]):
    print(f"Club {c[0]}: {c[1]}")
