import aiosqlite
import aiohttp
import random
import os
import logging
import time
from config import DB_PATH, NAMES_FILE, SUPABASE_URL, SUPABASE_KEY, PFP_DIR, MEDIA_DIR, ADMIN_ID

logger = logging.getLogger(__name__)

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

_last_notify = {}


async def init_db():
    """Local SQLite Database tables initialize karein"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                media_path TEXT,
                template_id INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_reviews (
                review_id INTEGER PRIMARY KEY
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_names (
                name TEXT PRIMARY KEY
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_pfps (
                pfp_path TEXT PRIMARY KEY
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_templates (
                template_id INTEGER PRIMARY KEY
            )
        """)

        defaults = {
            "watch_channel": "",
            "end_sticker_unique_id": "",
            "review_delay_seconds": "120",
            "batch_size": "1",
            "inter_round_delay": "300",
            "auto_trigger_enabled": "1",
            "target_id": ""
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v)
            )
        await db.commit()


# ================= SETTINGS =================

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


async def get_review_delay() -> int:
    try:
        return max(30, int(await get_setting("review_delay_seconds", "120")))
    except Exception:
        return 120


async def get_batch_size() -> int:
    """Number of full rounds (all accounts send → wait → delete → send again). Min 1."""
    try:
        return max(1, int(await get_setting("batch_size", "1")))
    except Exception:
        return 1


async def get_inter_round_delay() -> int:
    """Seconds between rounds (default 300 = 5 minutes)."""
    try:
        return max(60, int(await get_setting("inter_round_delay", "300")))
    except Exception:
        return 300


# ================= SUPABASE ACCOUNTS =================

async def save_account(phone: str, session_string: str, first_name: str, user_id: int):
    url = f"{SUPABASE_URL}/rest/v1/accounts"
    headers = {**SUPABASE_HEADERS, "Prefer": "resolution=merge-duplicates"}
    payload = {
        "phone": phone,
        "session_string": session_string,
        "first_name": first_name or "Trader",
        "user_id": user_id,
        "is_active": 1
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 201)
    except Exception as e:
        logger.error(f"Supabase Save Error: {e}")
        return False


async def get_all_accounts():
    url = f"{SUPABASE_URL}/rest/v1/accounts?is_active=eq.1&select=*"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=SUPABASE_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"Supabase Get Accounts Error: {e}")
    return []


async def get_accounts_count() -> int:
    accounts = await get_all_accounts()
    return len(accounts)


async def delete_account(phone: str):
    url = f"{SUPABASE_URL}/rest/v1/accounts?phone=eq.{phone}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=SUPABASE_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status in (200, 204)
    except Exception as e:
        logger.error(f"Supabase Delete Error: {e}")
        return False


# ================= TARGET =================

async def set_target_id(target_id: str):
    await set_setting("target_id", str(target_id))


async def get_target_id():
    val = await get_setting("target_id", "")
    return val if val else None


# ================= TEMPLATES =================

async def add_template(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO templates (name) VALUES (?)",
            (name.strip(),)
        )
        await db.commit()
        if cursor.lastrowid:
            return cursor.lastrowid
        async with db.execute("SELECT id FROM templates WHERE name = ?", (name.strip(),)) as c:
            row = await c.fetchone()
            return row[0] if row else 0


async def get_all_templates():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM templates ORDER BY id") as cursor:
            return await cursor.fetchall()


async def delete_template(template_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reviews WHERE template_id = ?", (template_id,))
        await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await db.execute("DELETE FROM used_templates WHERE template_id = ?", (template_id,))
        await db.commit()


async def get_random_template_id() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM templates") as cursor:
            templates = await cursor.fetchall()

        if not templates:
            return 0

        async with db.execute("SELECT template_id FROM used_templates") as cursor:
            used = set(row[0] for row in await cursor.fetchall())

        available = [t["id"] for t in templates if t["id"] not in used]

        if not available:
            await _flag_exhaust("Templates")
            await db.execute("DELETE FROM used_templates")
            await db.commit()
            available = [t["id"] for t in templates]

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_templates (template_id) VALUES (?)", (chosen,))
        await db.commit()
        return chosen


# ================= REVIEWS =================

async def add_review(review_type: str, content: str, media_path: str = None, template_id: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reviews (type, content, media_path, template_id) VALUES (?, ?, ?, ?)",
            (review_type, content, media_path, template_id)
        )
        await db.commit()


async def add_bulk_photos(photo_paths: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for p in photo_paths:
            await db.execute(
                "INSERT INTO reviews (type, content, media_path, template_id) VALUES ('photo', '', ?, 0)",
                (p,)
            )
        await db.commit()


async def get_text_reviews(template_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if template_id is not None and template_id > 0:
            async with db.execute(
                "SELECT * FROM reviews WHERE type = 'text' AND template_id = ?", (template_id,)
            ) as cursor:
                return await cursor.fetchall()
        async with db.execute("SELECT * FROM reviews WHERE type = 'text'") as cursor:
            return await cursor.fetchall()


async def get_photo_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reviews WHERE type = 'photo'") as cursor:
            return await cursor.fetchall()


async def get_unique_text_review(template_id: int = 0) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if template_id > 0:
            async with db.execute(
                "SELECT * FROM reviews WHERE type = 'text' AND template_id = ?", (template_id,)
            ) as cursor:
                all_texts = await cursor.fetchall()
        else:
            async with db.execute("SELECT * FROM reviews WHERE type = 'text'") as cursor:
                all_texts = await cursor.fetchall()

        if not all_texts:
            return "Bhai trading session bohot accha tha, profit booked! 🔥"

        async with db.execute("SELECT review_id FROM used_reviews") as cursor:
            used_ids = set(row[0] for row in await cursor.fetchall())

        available = [r for r in all_texts if r["id"] not in used_ids]

        if not available:
            await _flag_exhaust("Text Reviews")
            await db.execute("DELETE FROM used_reviews")
            await db.commit()
            available = all_texts

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_reviews (review_id) VALUES (?)", (chosen["id"],))
        await db.commit()
        return chosen["content"]


async def get_unique_photo_path() -> str | None:
    photos = await get_photo_reviews()
    if not photos:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT review_id FROM used_reviews") as cursor:
            used_ids = set(row[0] for row in await cursor.fetchall())

        available = [p for p in photos if p["id"] not in used_ids]

        if not available:
            await _flag_exhaust("Photo Proofs")
            # only clear used for photos
            photo_ids = [p["id"] for p in photos]
            for pid in photo_ids:
                await db.execute("DELETE FROM used_reviews WHERE review_id = ?", (pid,))
            await db.commit()
            available = photos

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_reviews (review_id) VALUES (?)", (chosen["id"],))
        await db.commit()

        path = chosen["media_path"]
        if path and os.path.exists(os.path.abspath(path)):
            return os.path.abspath(path)
        return None


async def get_reviews_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM reviews WHERE type = 'text'") as c1:
            text_cnt = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM reviews WHERE type = 'photo'") as c2:
            photo_cnt = (await c2.fetchone())[0]
        return text_cnt, photo_cnt


async def clear_text_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM used_reviews WHERE review_id IN (SELECT id FROM reviews WHERE type = 'text')")
        await db.execute("DELETE FROM reviews WHERE type = 'text'")
        await db.commit()


async def clear_photo_reviews():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT media_path FROM reviews WHERE type = 'photo'") as cursor:
            paths = [row[0] for row in await cursor.fetchall() if row[0]]
        await db.execute("DELETE FROM used_reviews WHERE review_id IN (SELECT id FROM reviews WHERE type = 'photo')")
        await db.execute("DELETE FROM reviews WHERE type = 'photo'")
        await db.commit()
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


async def clear_all_reviews():
    await clear_text_reviews()
    await clear_photo_reviews()


# ================= NAMES =================

async def get_next_name() -> str:
    if not os.path.exists(NAMES_FILE):
        return f"Trader_{random.randint(100, 999)}"

    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        all_names = [line.strip() for line in f if line.strip()]

    if not all_names:
        return f"Member_{random.randint(100, 999)}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM used_names") as cursor:
            used = set(row[0] for row in await cursor.fetchall())

        available = [n for n in all_names if n not in used]

        if not available:
            await _flag_exhaust("Names")
            await db.execute("DELETE FROM used_names")
            await db.commit()
            available = all_names

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_names (name) VALUES (?)", (chosen,))
        await db.commit()
        return chosen


async def clear_used_names():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM used_names")
        await db.commit()


async def get_used_names_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM used_names") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_names_count() -> int:
    if not os.path.exists(NAMES_FILE):
        return 0
    with open(NAMES_FILE, "r", encoding="utf-8") as f:
        return len([line.strip() for line in f if line.strip()])


# ================= PFP =================

async def get_next_pfp_path(account_phone: str) -> str | None:
    if not os.path.exists(PFP_DIR):
        return None

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    all_photos = [
        os.path.abspath(os.path.join(PFP_DIR, f))
        for f in os.listdir(PFP_DIR)
        if f.lower().endswith(valid_exts) and not f.startswith(".") and not f.startswith("temp_")
    ]

    if not all_photos:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pfp_path FROM used_pfps") as cursor:
            used = set(row[0] for row in await cursor.fetchall())

        available = [p for p in all_photos if p not in used]

        if not available:
            await _flag_exhaust("PFPs")
            await db.execute("DELETE FROM used_pfps")
            await db.commit()
            available = all_photos

        chosen = random.choice(available)
        await db.execute("INSERT OR IGNORE INTO used_pfps (pfp_path) VALUES (?)", (chosen,))
        await db.commit()
        return chosen


async def clear_used_pfps():
    """Only clears tracking DB so all PFPs become available again. Does NOT delete files."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM used_pfps")
        await db.commit()


async def get_used_pfp_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM used_pfps") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_pfp_count() -> int:
    """Count of actual image files in pfp/ folder."""
    if not os.path.exists(PFP_DIR):
        return 0
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    return len([
        f for f in os.listdir(PFP_DIR)
        if f.lower().endswith(valid_exts) and not f.startswith(".") and not f.startswith("temp_")
    ])


async def delete_all_pfps_from_folder() -> int:
    """Actually delete all PFP image files from pfp/ folder + clear tracking. Returns deleted count."""
    deleted = 0
    if not os.path.exists(PFP_DIR):
        await clear_used_pfps()
        return 0
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    for f in list(os.listdir(PFP_DIR)):
        if f.lower().endswith(valid_exts) and not f.startswith("."):
            path = os.path.join(PFP_DIR, f)
            try:
                os.remove(path)
                deleted += 1
            except Exception:
                pass
    await clear_used_pfps()
    return deleted


# ================= EXHAUST FLAG (rotation_engine will send actual message) =================

async def _flag_exhaust(resource_name: str):
    now = time.time()
    if resource_name in _last_notify and (now - _last_notify[resource_name]) < 300:
        return
    _last_notify[resource_name] = now
    await set_setting(f"exhaust_notify_{resource_name.replace(' ', '_')}", str(int(now)))
    logger.warning(f"RESOURCE EXHAUSTED: {resource_name} — reuse started.")


async def pop_exhaust_notifications() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key FROM settings WHERE key LIKE 'exhaust_notify_%'") as cursor:
            rows = await cursor.fetchall()
        messages = []
        for (key,) in rows:
            resource = key.replace("exhaust_notify_", "").replace("_", " ")
            messages.append(resource)
            await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        await db.commit()
        return messages
