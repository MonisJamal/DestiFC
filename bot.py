import sys, os

print("=== DestiFC Starting ===")
try:
    from curl_cffi import requests
    print("curl_cffi loaded successfully!")
except ImportError as e:
    print(f"curl_cffi import warning: {e}")

import main

if __name__ == '__main__':
    if not main.TOKEN or main.TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = main.DestiFC()
        bot.run(main.TOKEN)
