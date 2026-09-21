import sys
import os


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import asyncio
import logging
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
import database as db
from handlers import register_all_handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def start_bot():
    print(">> Initializing Database...")
    await db.init_db()
    print(">> Database Ready!")

   
    app = Client(
        name="trading_review_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

  
    register_all_handlers(app)

    print("=" * 55)
    print(">> TRADING REVIEW BOT IS RUNNING LIVE!")
    print(f">> Admin ID: {ADMIN_ID}")
    print(">> Press Ctrl + C to stop the bot")
    print("=" * 55)

    await app.start()
    
    
    try:
        from handlers.admin_menu import get_main_keyboard
        await app.send_message(
            ADMIN_ID,
            "🟢 **Bot Online & Ready!**\n\nReview system active ho chuka hai. Niche menu se shuru karein:",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.warning(f"Could not send startup alert: {e}")

    
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        print("\n>> Bot Stopped Successfully.")