import os
import random
import logging
from PIL import Image
from config import PFP_DIR
import database as db

logger = logging.getLogger(__name__)


async def download_random_pfp(account_phone: str) -> str | None:
    """
    Local PFP picker with DB-backed no-reuse.
    30% chance of having a PFP, 70% clean letter avatar (None).
    On exhaust of all PFPs → admin is notified and reuse starts.
    """
    if random.random() > 0.30:
        return None

    chosen = await db.get_next_pfp_path(account_phone)
    if not chosen or not os.path.exists(chosen):
        return None

    try:
        clean_phone = account_phone.replace("+", "").replace(" ", "")
        temp_dest = os.path.abspath(os.path.join(PFP_DIR, f"temp_{clean_phone}.jpg"))

        with Image.open(chosen) as img:
            img = img.convert("RGB")
            img = img.resize((512, 512), Image.Resampling.LANCZOS)
            img.save(temp_dest, "JPEG", quality=95)
        return temp_dest
    except Exception as e:
        logger.error(f"Local PFP Optimize Error: {e}")
        return chosen


def cleanup_pfp(file_path: str):
    """Temporary processed photo ko delete karta hai"""
    if file_path and os.path.exists(file_path) and "temp_" in os.path.basename(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
