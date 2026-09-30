"""DestiFC Admin Portal — a secure web companion for the Discord admin commands."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "destifc.db"
UPLOADS = ROOT / "admin_portal" / "uploads"
THEME_UPLOADS = ROOT / "assets" / "admin_themes"
TEMPLATES = Jinja2Templates(directory=str(ROOT / "admin_portal" / "templates"))

app = FastAPI(title="DestiFC Admin Portal", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("ADMIN_PORTAL_SESSION_SECRET", "change-this-session-secret"),
    same_site="lax",
    https_only=os.getenv("ADMIN_PORTAL_HTTPS", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory=str(ROOT / "admin_portal" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")

THEMES = {
    "default": "Neon Stadium", "snow": "Frostbite Winter", "lava": "Volcanic Inferno",
    "cyberpunk": "Cyberpunk City", "desert": "Arabian Nights", "galaxy": "Galaxy Edition",
    "gold": "Champions Final",
}
POSITIONS = ["GK", "LB", "LWB", "CB", "RB", "RWB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "CF", "ST"]


def db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(503, "The DestiFC database has not been initialized yet. Start the bot once, then return here.")
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_portal_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS formation_layouts (
          formation_name TEXT PRIMARY KEY, positions_json TEXT NOT NULL,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS theme_overrides (
          theme_id TEXT PRIMARY KEY, background_path TEXT NOT NULL,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS portal_jobs (
          job_name TEXT PRIMARY KEY, requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS portal_audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, detail TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS custom_draft_cards (
          id INTEGER PRIMARY KEY AUTOINCREMENT, player_data TEXT
        );
    """)
    conn.commit()


def audit(conn: sqlite3.Connection, action: str, detail: str) -> None:
    conn.execute("INSERT INTO portal_audit_log (action, detail) VALUES (?, ?)", (action, detail[:800]))


def csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def protected(request: Request) -> RedirectResponse | None:
    if not request.session.get("admin"):
        return RedirectResponse("/login", status_code=303)
    return None


def verify_csrf(request: Request, token: str) -> None:
    if not secrets.compare_digest(token or "", request.session.get("csrf", "")):
        raise HTTPException(403, "Your session has expired. Reload the page and try again.")


def flash(request: Request, message: str, style: str = "success") -> None:
    request.session["flash"] = {"message": message, "style": style}


def render(request: Request, name: str, **context: Any):
    context.update({"csrf": csrf(request), "flash": request.session.pop("flash", None)})
    return TEMPLATES.TemplateResponse(request, name, context)


def parse_player(row: sqlite3.Row) -> dict[str, Any]:
    try:
        data = json.loads(row["player_data"] or "{}")
    except (TypeError, json.JSONDecodeError):
        data = {}
    return {
        "id": row["id"], "source": "Inventory", "user_id": row["user_id"],
        "name": row["player_name"], "ovr": row["ovr"],
        "position": data.get("position", "—"), "image": data.get("images", {}).get("playerCardImage", ""),
    }


def safe_upload(upload: UploadFile | None, destination: Path, prefix: str) -> str | None:
    if not upload or not upload.filename:
        return None
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Please upload a PNG, JPG, JPEG, or WEBP image.")
    destination.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}-{int(time.time() * 1000)}{suffix}"
    target = destination / filename
    with target.open("wb") as out:
        shutil.copyfileobj(upload.file, out, length=1024 * 1024)
    if target.stat().st_size > 12 * 1024 * 1024:
        target.unlink(missing_ok=True)
        raise HTTPException(400, "Images must be no larger than 12 MB.")
    return str(target.relative_to(ROOT))


@app.get("/login")
def login_page(request: Request):
    return render(request, "login.html", configured=bool(os.getenv("ADMIN_PORTAL_PASSWORD")))


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    configured = os.getenv("ADMIN_PORTAL_PASSWORD", "")
    if not configured:
        flash(request, "Set ADMIN_PORTAL_PASSWORD in .env before using the portal.", "error")
        return RedirectResponse("/login", status_code=303)
    if not secrets.compare_digest(password, configured):
        flash(request, "That password wasn't accepted.", "error")
        return RedirectResponse("/login", status_code=303)
    request.session["admin"] = True
    csrf(request)
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def dashboard(request: Request):
    if response := protected(request): return response
    with db() as conn:
        ensure_portal_tables(conn)
        counts = {
            "cards": conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0],
            "players": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "drafts": conn.execute("SELECT COUNT(*) FROM custom_draft_cards").fetchone()[0],
            "formations": conn.execute("SELECT COUNT(*) FROM formation_layouts").fetchone()[0],
        }
        activity = conn.execute("SELECT action, detail, created_at FROM portal_audit_log ORDER BY id DESC LIMIT 7").fetchall()
    return render(request, "dashboard.html", counts=counts, activity=activity)


@app.get("/cards")
def cards(request: Request, q: str = "", position: str = "", source: str = "all", min_ovr: int | None = None):
    if response := protected(request): return response
    cards: list[dict[str, Any]] = []
    with db() as conn:
        ensure_portal_tables(conn)
        if source in ("all", "inventory"):
            rows = conn.execute("SELECT id, user_id, player_name, ovr, player_data FROM inventory ORDER BY id DESC").fetchall()
            cards.extend(parse_player(row) for row in rows)
        if source in ("all", "draft"):
            rows = conn.execute("SELECT id, player_data FROM custom_draft_cards ORDER BY id DESC").fetchall()
            for row in rows:
                try: data = json.loads(row["player_data"] or "{}")
                except json.JSONDecodeError: data = {}
                cards.append({"id": row["id"], "source": "Draft pool", "user_id": "—", "name": data.get("cardName", "Unknown"), "ovr": data.get("rating", 0), "position": data.get("position", "—"), "image": data.get("images", {}).get("playerCardImage", "")})
    q = q.strip().lower()
    cards = [c for c in cards if (not q or q in str(c["name"]).lower() or q in str(c["user_id"])) and (not position or c["position"] == position) and (min_ovr is None or int(c["ovr"] or 0) >= min_ovr)]
    return render(request, "cards.html", cards=cards[:500], q=q, position=position, source=source, min_ovr=min_ovr, positions=POSITIONS)


@app.post("/cards/{source}/{card_id}/delete")
async def delete_card(request: Request, source: str, card_id: int, csrf_token: str = Form(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if source not in {"inventory", "draft"}: raise HTTPException(404)
    table = "inventory" if source == "inventory" else "custom_draft_cards"
    with db() as conn:
        ensure_portal_tables(conn)
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (card_id,))
        audit(conn, "Deleted card", f"{source} card #{card_id}")
        conn.commit()
    flash(request, "Card removed from the live database.")
    return RedirectResponse("/cards", status_code=303)


@app.get("/create-card")
def create_card_page(request: Request):
    if response := protected(request): return response
    return render(request, "create_card.html", positions=POSITIONS)


@app.post("/create-card")
async def create_card(
    request: Request, csrf_token: str = Form(...), name: str = Form(...), ovr: int = Form(...), position: str = Form(...),
    target_user_id: int | None = Form(None), quantity: int = Form(1), add_to_drafts: bool = Form(False),
    player_image: UploadFile = File(...), background_image: UploadFile | None = File(None), nation_id: int = Form(38), club_id: int = Form(112139),
):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if not 1 <= ovr <= 200 or quantity < 1 or quantity > 1000 or position.upper() not in POSITIONS:
        raise HTTPException(400, "Check the rating, position, and quantity fields.")
    player_path = safe_upload(player_image, UPLOADS, "player")
    bg_path = safe_upload(background_image, UPLOADS, "background")
    player_url = "/" + player_path.replace("admin_portal/", "")
    bg_url = "/" + bg_path.replace("admin_portal/", "") if bg_path else "https://images-v2.renderz.app/bg_23_backgrounds_27_ANNIVERSARY27_LIVE_STATIC?verify=1"
    custom_id = -int(time.time() * 1000)
    data = {"id": custom_id, "assetId": custom_id, "cardName": name.strip(), "lastName": name.strip(), "rating": ovr, "position": position.upper(), "nation": {"id": nation_id}, "club": {"id": club_id}, "images": {"playerCardImage": player_url, "playerCardBackground": bg_url}, "stats": {key: ovr for key in ["acc", "spd", "str", "fin", "sta", "sho", "dri", "def", "pas", "phy"]}, "is_custom": True}
    with db() as conn:
        ensure_portal_tables(conn)
        if target_user_id:
            conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (target_user_id,))
            for _ in range(quantity):
                conn.execute("INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data) VALUES (?, ?, ?, ?, ?)", (target_user_id, str(custom_id), data["cardName"], ovr, json.dumps(data)))
        if add_to_drafts:
            for _ in range(quantity): conn.execute("INSERT INTO custom_draft_cards (player_data) VALUES (?)", (json.dumps(data),))
        audit(conn, "Created custom card", f"{quantity}× {name} ({ovr}) | user={target_user_id or 'none'} | drafts={add_to_drafts}")
        conn.commit()
    flash(request, f"{name} is live. {'Draft pool updated.' if add_to_drafts else 'No draft entry created.'}")
    return RedirectResponse("/cards", status_code=303)


@app.get("/commands")
def commands_page(request: Request):
    if response := protected(request): return response
    return render(request, "commands.html")


@app.post("/commands/currency")
async def currency(request: Request, csrf_token: str = Form(...), user_id: int = Form(...), currency: str = Form(...), amount: int = Form(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if currency not in {"coins", "vouchers"} or amount == 0: raise HTTPException(400, "Choose coins or vouchers and a non-zero amount.")
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.execute(f"UPDATE users SET {currency} = max(0, {currency} + ?) WHERE user_id = ?", (amount, user_id))
        audit(conn, "Currency grant", f"{amount:+,} {currency} to {user_id}")
        conn.commit()
    flash(request, "Balance updated.")
    return RedirectResponse("/commands", status_code=303)


@app.post("/commands/restore")
async def restore(request: Request, csrf_token: str = Form(...), user_id: int = Form(...), cards_json: str = Form(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    try: entries = json.loads(cards_json)
    except json.JSONDecodeError: raise HTTPException(400, "Use a valid JSON array.")
    if not isinstance(entries, list) or len(entries) > 50: raise HTTPException(400, "Provide up to 50 card objects.")
    from renderz_api import search_fifarenderz
    restored = 0
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        for entry in entries:
            name, ovr, qty = str(entry.get("name", "")), int(entry.get("ovr", 0)), max(1, min(1000, int(entry.get("qty", 1))))
            matches = search_fifarenderz(name, size=25)
            found = next((p for p in matches if p.get("rating") == ovr), None)
            if not found: continue
            for _ in range(qty):
                conn.execute("INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data) VALUES (?, ?, ?, ?, ?)", (user_id, str(found.get("id", "unknown")), found.get("cardName") or found.get("lastName", "Unknown"), found.get("rating", 0), json.dumps(found)))
                restored += 1
        audit(conn, "Restored official cards", f"{restored} card(s) to {user_id}")
        conn.commit()
    flash(request, f"Restored {restored} exact-match card(s).")
    return RedirectResponse("/commands", status_code=303)


@app.post("/commands/give-official")
async def give_official(request: Request, csrf_token: str = Form(...), user_id: int = Form(...), player_name: str = Form(...), ovr: int = Form(...), quantity: int = Form(1)):
    """Web equivalent of /admin give and /admin give_official's chosen result."""
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if not 1 <= quantity <= 1000: raise HTTPException(400, "Quantity must be between 1 and 1,000.")
    from renderz_api import search_fifarenderz
    matches = search_fifarenderz(player_name, size=25)
    found = next((p for p in matches if p.get("rating") == ovr), None)
    if not found:
        flash(request, f"No exact {ovr} OVR RenderZ card found for {player_name}.", "error")
        return RedirectResponse("/commands", status_code=303)
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        for _ in range(quantity):
            conn.execute("INSERT INTO inventory (user_id, player_id, player_name, ovr, player_data) VALUES (?, ?, ?, ?, ?)", (user_id, str(found.get("id", "unknown")), found.get("cardName") or found.get("lastName", "Unknown"), found.get("rating", 0), json.dumps(found)))
        audit(conn, "Granted official card", f"{quantity}× {player_name} ({ovr}) to {user_id}")
        conn.commit()
    flash(request, f"Granted {quantity}× {player_name} ({ovr} OVR).")
    return RedirectResponse("/commands", status_code=303)


@app.post("/commands/clear")
async def clear_inventory(request: Request, csrf_token: str = Form(...), user_id: int = Form(...), max_ovr: int | None = Form(None)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    with db() as conn:
        sql, params = ("DELETE FROM inventory WHERE user_id = ?", [user_id]) if max_ovr is None else ("DELETE FROM inventory WHERE user_id = ? AND ovr <= ?", [user_id, max_ovr])
        deleted = conn.execute(sql, params).rowcount
        audit(conn, "Cleared inventory", f"{deleted} cards from {user_id}, max_ovr={max_ovr}")
        conn.commit()
    flash(request, f"Removed {deleted} card(s).")
    return RedirectResponse("/commands", status_code=303)


@app.post("/commands/remove-by-name")
async def remove_by_name(request: Request, csrf_token: str = Form(...), user_id: int = Form(...), player_name: str = Form(...), ovr: int | None = Form(None), quantity: int = Form(1)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if not 1 <= quantity <= 1000: raise HTTPException(400, "Quantity must be between 1 and 1,000.")
    with db() as conn:
        query = "SELECT id FROM inventory WHERE user_id = ? AND lower(player_name) LIKE ?"
        params: list[Any] = [user_id, f"%{player_name.lower()}%"]
        if ovr is not None:
            query += " AND ovr = ?"; params.append(ovr)
        ids = [row[0] for row in conn.execute(query + " ORDER BY id LIMIT ?", [*params, quantity]).fetchall()]
        if ids:
            conn.execute(f"DELETE FROM inventory WHERE id IN ({','.join('?' for _ in ids)})", ids)
        audit(conn, "Removed cards by name", f"{len(ids)}× {player_name} from {user_id}, ovr={ovr}")
        conn.commit()
    flash(request, f"Removed {len(ids)} matching card(s).")
    return RedirectResponse("/commands", status_code=303)


@app.post("/commands/refresh-store")
async def refresh_store(request: Request, csrf_token: str = Form(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    with db() as conn:
        ensure_portal_tables(conn)
        conn.execute("INSERT OR REPLACE INTO portal_jobs (job_name, requested_at) VALUES ('refresh_store', CURRENT_TIMESTAMP)")
        audit(conn, "Store refresh requested", "The Discord store worker will refresh on its next 5-minute check.")
        conn.commit()
    flash(request, "Store refresh queued for the bot worker.")
    return RedirectResponse("/commands", status_code=303)


@app.get("/formations")
def formations(request: Request, formation: str = "4-3-3 Attack"):
    if response := protected(request): return response
    from cogs.squad import FORMATION_MAP
    from lineup_generator import get_formation_coordinates
    if formation not in FORMATION_MAP: formation = next(iter(FORMATION_MAP))
    with db() as conn:
        ensure_portal_tables(conn)
        saved = conn.execute("SELECT positions_json FROM formation_layouts WHERE formation_name = ?", (formation,)).fetchone()
        themes = {row["theme_id"]: row["background_path"] for row in conn.execute("SELECT theme_id, background_path FROM theme_overrides")}
    defaults = get_formation_coordinates(formation, list(FORMATION_MAP[formation].keys()))
    points = json.loads(saved["positions_json"]) if saved else {slot: {"x": round(x / 1600 * 100, 1), "y": round(y / 900 * 100, 1)} for slot, (x, y) in defaults.items()}
    return render(request, "formations.html", formations=list(FORMATION_MAP.keys()), formation=formation, points=points, themes=THEMES, overrides=themes)


@app.post("/formations/save")
async def save_formation(request: Request, csrf_token: str = Form(...), formation: str = Form(...), positions_json: str = Form(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    from cogs.squad import FORMATION_MAP
    if formation not in FORMATION_MAP: raise HTTPException(400, "Unknown formation.")
    try: points = json.loads(positions_json)
    except json.JSONDecodeError: raise HTTPException(400, "Invalid player positions.")
    expected = set(FORMATION_MAP[formation])
    if set(points) != expected: raise HTTPException(400, "Every formation slot must be present.")
    for p in points.values():
        if not isinstance(p, dict) or not all(isinstance(p.get(k), (int, float)) and 0 <= p[k] <= 100 for k in ("x", "y")):
            raise HTTPException(400, "All player coordinates must be between 0 and 100.")
    with db() as conn:
        ensure_portal_tables(conn)
        conn.execute("INSERT OR REPLACE INTO formation_layouts (formation_name, positions_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (formation, json.dumps(points)))
        audit(conn, "Saved formation", formation)
        conn.commit()
    flash(request, f"{formation} is saved and will update in Discord within a few seconds.")
    return RedirectResponse(f"/formations?formation={formation}", status_code=303)


@app.post("/formations/theme")
async def save_theme(request: Request, csrf_token: str = Form(...), theme_id: str = Form(...), background: UploadFile = File(...)):
    if response := protected(request): return response
    verify_csrf(request, csrf_token)
    if theme_id not in THEMES: raise HTTPException(400, "Unknown theme.")
    path = safe_upload(background, THEME_UPLOADS, theme_id)
    with db() as conn:
        ensure_portal_tables(conn)
        conn.execute("INSERT OR REPLACE INTO theme_overrides (theme_id, background_path, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (theme_id, path))
        audit(conn, "Updated theme background", theme_id)
        conn.commit()
    flash(request, f"{THEMES[theme_id]} background updated.")
    return RedirectResponse("/formations", status_code=303)
