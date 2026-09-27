import asyncio
from renderz_api import query_players_by_program

async def main():
    players = query_players_by_program("PROGRAM_ANN27", min_rating=120, max_rating=122, size=1)
    if players:
        print(players[0])

asyncio.run(main())
