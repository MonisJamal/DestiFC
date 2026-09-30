"""Run the DestiFC admin portal alongside the Discord bot."""
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()
uvicorn.run(
    "admin_portal.app:app",
    host=os.getenv("ADMIN_PORTAL_HOST", "0.0.0.0"),
    port=int(os.getenv("ADMIN_PORTAL_PORT", "8000")),
    proxy_headers=True,
)
