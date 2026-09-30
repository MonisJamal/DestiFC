# DestiFC Admin Portal

1. Unzip the bundle in the same folder as the DestiFC bot.
2. Create a `.env` file from `.env.example` and set the Discord token plus both admin-portal secrets.
3. Install requirements: `pip install -r requirements.txt`.
4. Start the Discord bot as usual: `python main.py`.
5. In a second process, start the portal: `python run_portal.py`.

The portal listens on port 8000 by default. Set `ADMIN_PORTAL_PORT` if your host needs a different port. Set `ADMIN_PORTAL_HTTPS=true` when it is served behind HTTPS. The generated deployment archive intentionally excludes `.env`, SQLite databases, logs, virtual environments, and private uploads.

The portal shares `destifc.db` with Discord. Back it up before a production upgrade.
