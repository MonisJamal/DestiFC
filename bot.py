import sys, os, subprocess

log_file = "bot_startup.log"
def log(msg):
    with open(log_file, "a") as f:
        f.write(str(msg) + "\n")
    print(msg)

log("=== BOT STARTUP INITIATED ===")
try:
    import curl_cffi
    log("curl_cffi is ALREADY INSTALLED.")
except ImportError:
    log("curl_cffi NOT found. Attempting install...")
    res = subprocess.run([sys.executable, "-m", "pip", "install", "curl_cffi", "--break-system-packages"], capture_output=True, text=True)
    log(f"pip install stdout: {res.stdout}")
    log(f"pip install stderr: {res.stderr}")
    try:
        import curl_cffi
        log("curl_cffi successfully installed and imported!")
    except Exception as e:
        log(f"curl_cffi STILL failed to import: {e}")

try:
    from curl_cffi import requests
    test_url = "https://images-v2.renderz.app/player_25_156616_CHA26_WHITE_490645153ad9a5c3?verify=1786629503-SkmTITRaWYZcw2QFiI8WxpUAIo2PmezZ%2Fj6sPN7iKR4%3D"
    r = requests.get(test_url, impersonate="chrome124", timeout=10)
    log(f"Cloudflare test download status: {r.status_code}, length: {len(r.content)}, type: {r.headers.get('content-type')}")
except Exception as e:
    log(f"Cloudflare test download failed: {e}")

import main

if __name__ == '__main__':
    if not main.TOKEN or main.TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = main.DestiFC()
        bot.run(main.TOKEN)
