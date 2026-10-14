import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("Error: DISCORD_TOKEN is missing!")
    sys.exit(1)

GUILD_ID = "1222195412295745536"  # BeastlyFC
ROLE_ID = "1557010712013045860"   # DestiFC Players

HEADERS = {
    'Authorization': f'Bot {TOKEN}',
    'Content-Type': 'application/json',
    'User-Agent': 'DiscordBot (DestiFC, 1.0)'
}

LOG_FILE = "mass_assign_roles.log"

def log(msg):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def fetch_all_members():
    log(f"Fetching all members from guild {GUILD_ID}...")
    all_members = []
    last_id = None
    
    while True:
        url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members?limit=1000"
        if last_id:
            url += f"&after={last_id}"
            
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 429:
            retry = float(r.json().get('retry_after', 2.0))
            log(f"Rate limited on fetch. Retrying in {retry}s...")
            time.sleep(retry + 0.5)
            continue
            
        if r.status_code != 200:
            log(f"Failed to fetch members: HTTP {r.status_code} - {r.text}")
            break
            
        data = r.json()
        if not data:
            break
            
        all_members.extend(data)
        last_id = data[-1]['user']['id']
        log(f"Fetched {len(all_members)} members so far...")
        
        if len(data) < 1000:
            break
            
        time.sleep(0.5)
        
    log(f"Total members fetched: {len(all_members)}")
    return all_members

def assign_role(member_id):
    url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{member_id}/roles/{ROLE_ID}"
    while True:
        r = requests.put(url, headers=HEADERS)
        if r.status_code == 204:
            return True, "SUCCESS"
        elif r.status_code == 429:
            retry = float(r.json().get('retry_after', 1.0))
            time.sleep(retry + 0.2)
            continue
        elif r.status_code == 404:
            return False, "Member not found"
        elif r.status_code == 403:
            return False, "Missing Permissions"
        else:
            return False, f"HTTP {r.status_code}: {r.text}"

def main():
    log(f"=== Starting Mass Role Assignment for Guild {GUILD_ID} -> Role {ROLE_ID} ===")
    members = fetch_all_members()
    
    # Filter candidates: non-bots who don't already have the role
    candidates = []
    already_have = 0
    bots_count = 0
    
    for m in members:
        u = m.get('user', {})
        if u.get('bot'):
            bots_count += 1
            continue
        if ROLE_ID in m.get('roles', []):
            already_have += 1
            continue
        candidates.append(m)
        
    log(f"Total fetched: {len(members)} | Bots: {bots_count} | Already have role: {already_have} | Needs role: {len(candidates)}")
    
    success = 0
    failed = 0
    
    for i, m in enumerate(candidates, 1):
        uid = m['user']['id']
        uname = m['user'].get('username', 'Unknown')
        
        ok, res = assign_role(uid)
        if ok:
            success += 1
        else:
            failed += 1
            log(f"[{i}/{len(candidates)}] Failed for {uname} ({uid}): {res}")
            
        if i % 25 == 0 or i == len(candidates):
            log(f"Progress: [{i}/{len(candidates)}] ({round(i/len(candidates)*100, 1)}%) | Success: {success} | Failed: {failed}")
            
        time.sleep(0.2)  # Polite pacing to stay under Discord burst limits
        
    log(f"=== Mass Role Assignment Complete! Total Granted: {success} | Failed: {failed} ===")

if __name__ == '__main__':
    main()
