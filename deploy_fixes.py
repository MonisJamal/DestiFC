import os
import paramiko
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

HOST = "geu2.xsystemshosting.com"
PORT = 2023
USER = "user_294051.58a88227"
PASS = "Biryani37@"

FILES_TO_UPLOAD = [
    "database.py",
    "main.py",
    "cogs/admin.py",
    "cogs/draft.py",
    "cogs/black_market.py",
    "cogs/drops.py"
]

def deploy():
    print(f"Connecting to SFTP {HOST}:{PORT}...")
    transport = paramiko.Transport((HOST, PORT))
    transport.banner_timeout = 30
    transport.connect(username=USER, password=PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    print("✅ SFTP Connected!")

    local_dir = "/Users/monisjamal/.gemini/antigravity/scratch/DestiFC"
    
    for f in FILES_TO_UPLOAD:
        local_path = os.path.join(local_dir, f)
        print(f"⚡ Uploading {f}...")
        sftp.put(local_path, f)

    sftp.close()
    transport.close()
    print("✅ All modified files uploaded successfully!")

async def trigger_restart():
    db_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(db_url, ssl='require')
    row = await conn.fetchrow(
        "INSERT INTO portal_jobs (job_type, payload, status) VALUES ('SIGNAL_RESTART', '{}', 'pending') RETURNING id;"
    )
    job_id = row['id']
    print(f"✅ Dispatched SIGNAL_RESTART job #{job_id}")

    print("Waiting for bot to reboot...")
    for _ in range(15):
        await asyncio.sleep(2)
        status_row = await conn.fetchrow("SELECT status, result FROM portal_jobs WHERE id = $1;", job_id)
        if status_row and status_row['status'] == 'completed':
            print(f"✅ Bot reboot confirmed! Result: {status_row['result']}")
            break
    await conn.close()

if __name__ == "__main__":
    deploy()
    asyncio.run(trigger_restart())
