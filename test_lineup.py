from lineup_generator import generate_lineup_image
import json
squad = {"formation": "4-3-3", "players": {}}
img = generate_lineup_image(squad, {})
img.save("test_lineup.png")
