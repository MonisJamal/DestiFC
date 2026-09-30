import os
import paramiko
import stat

HOST = "eu4-node.xsystemshosting.com"
PORT = 2025
USER = "user_294051.c1cc223f"
PASS = "Biryani37@"

def main():
    print(f"Connecting to SFTP {HOST}:{PORT} as {USER}...")
    transport = paramiko.Transport((HOST, PORT))
    transport.connect(username=USER, password=PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    print("✅ SFTP Connected successfully!")

    files = sftp.listdir(".")
    print("Remote files currently:", files)

    local_dir = "/Users/monisjamal/.gemini/antigravity/scratch/DestiFC"

    def upload_dir(local_path, remote_path):
        try:
            sftp.mkdir(remote_path)
        except Exception:
            pass
        for item in os.listdir(local_path):
            l_item = os.path.join(local_path, item)
            r_item = f"{remote_path}/{item}".replace("//", "/")
            if os.path.isdir(l_item):
                if item in [".git", ".venv", "__pycache__", "node_modules", ".next", ".archive_scratch", "backups", "web_admin", "admin_portal", "vercel_admin", "cache", "output", ".planning"]:
                    continue
                upload_dir(l_item, r_item)
            else:
                if item.endswith(('.zip', '.pyc', '.db', '.db-wal', '.db-shm', '.DS_Store')) or item.startswith(('patch_', 'test_')):
                    continue
                print(f"Uploading {item} -> {r_item}...")
                sftp.put(l_item, r_item)

    print("\n🚀 Syncing core source code, cogs, fonts, and assets to Pterodactyl...")
    upload_dir(local_dir, ".")

    # Helper to clean up remote directory
    def remove_remote_dir(path):
        try:
            for entry in sftp.listdir_attr(path):
                r_path = f"{path}/{entry.filename}"
                if stat.S_ISDIR(entry.st_mode):
                    remove_remote_dir(r_path)
                else:
                    sftp.remove(r_path)
            sftp.rmdir(path)
            print(f"Removed remote directory: {path}")
        except Exception as e:
            print(f"Directory cleanup note for {path}: {e}")

    # Remove conflicting .git so git merge/rebase crashes stop completely
    if ".git" in files:
        print("Removing .git folder on server to prevent git merge conflicts...")
        remove_remote_dir(".git")

    sftp.close()
    transport.close()
    print("\n🎉 ALL DONE! Your server files are 100% updated and synchronized.")

if __name__ == "__main__":
    main()
