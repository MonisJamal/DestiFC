import os
import paramiko

HOST = "geu2.xsystemshosting.com"
PORT = 2023
USER = "user_294051.58a88227"
PASS = "Biryani37@"

def main():
    print(f"Connecting to SFTP {HOST}:{PORT} as {USER}...")
    transport = paramiko.Transport((HOST, PORT))
    transport.banner_timeout = 30
    transport.connect(username=USER, password=PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    print("✅ SFTP Connected!")

    local_dir = "/Users/monisjamal/.gemini/antigravity/scratch/DestiFC"

    # 1. Core Python files
    core_files = [
        'main.py', 'bot.py', 'database.py', 'auth.py', 'card_generator.py',
        'lineup_generator.py', 'maps.py', 'renderz_api.py', 'ai_engine.py',
        'requirements.txt', '.env'
    ]
    print("\n⚡ [1/3] Syncing core engine files...")
    for f in core_files:
        l_path = os.path.join(local_dir, f)
        if os.path.exists(l_path):
            print(f"  -> {f}")
            sftp.put(l_path, f)

    # 2. Cogs
    print("\n⚡ [2/3] Syncing all 16 modular cogs...")
    try:
        sftp.mkdir("cogs")
    except Exception:
        pass
    cogs_dir = os.path.join(local_dir, "cogs")
    for f in os.listdir(cogs_dir):
        if f.endswith('.py') and not f.startswith('__'):
            l_path = os.path.join(cogs_dir, f)
            print(f"  -> cogs/{f}")
            sftp.put(l_path, f"cogs/{f}")

    # 3. Essential Assets (Fonts + Backgrounds)
    print("\n⚡ [3/3] Syncing pitch backgrounds and fonts...")
    try:
        sftp.mkdir("assets")
    except Exception:
        pass
    try:
        sftp.mkdir("assets/fonts")
    except Exception:
        pass
    try:
        sftp.mkdir("assets/cache")
    except Exception:
        pass
    try:
        sftp.mkdir("assets/cache/images")
    except Exception:
        pass

    # Pitch backgrounds
    assets_dir = os.path.join(local_dir, "assets")
    for f in os.listdir(assets_dir):
        if f.endswith('.jpg') or f.endswith('.png'):
            l_path = os.path.join(assets_dir, f)
            print(f"  -> assets/{f}")
            sftp.put(l_path, f"assets/{f}")

    # Fonts
    fonts_dir = os.path.join(assets_dir, "fonts")
    if os.path.exists(fonts_dir):
        for f in os.listdir(fonts_dir):
            if f.endswith('.ttf') or f.endswith('.otf'):
                l_path = os.path.join(fonts_dir, f)
                print(f"  -> assets/fonts/{f}")
                sftp.put(l_path, f"assets/fonts/{f}")

    sftp.close()
    transport.close()
    print("\n🎉 COMPLETE! All essential bot code, cogs, fonts, and pitch assets are 100% deployed!")

if __name__ == "__main__":
    main()
