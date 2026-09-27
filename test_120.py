from renderz_api import query_players_by_program
players = query_players_by_program("", min_rating=120, max_rating=122, size=50)
for p in players:
    name = p.get('cardName') or p.get('lastName', 'Unknown')
    print(f"{name} ({p.get('rating')}) - Nation: {p.get('nation', {}).get('id')} / Club: {p.get('club', {}).get('id')}")
