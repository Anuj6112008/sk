import os
import uuid
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PasswordHashInvalid,
    PhoneNumberInvalid,
    MessageNotModified
)
from config import API_ID, API_HASH, ADMIN_ID, MEDIA_DIR
import database as db

login_sessions = {}

def get_cancel_keyboard(is_bulk=False):
    buttons = []
    if is_bulk:
        buttons.append([InlineKeyboardButton("✅ Finish Bulk Login", callback_data="btn_finish_bulk_login")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_login")])
    return InlineKeyboardMarkup(buttons)

def register_account_handlers(app: Client):

    # ================= 1. IMPORT SESSIONS (.TXT / DIRECT TEXT) =================
    @app.on_callback_query(filters.regex("^btn_import_sessions$"))
    async def import_sessions_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        login_sessions[callback.from_user.id] = {
            "state": "AWAITING_SESSIONS_INPUT"
        }
        prompt_text = (
            "📂 **Import StringSessions (.txt / Text Message)**\n\n"
            "Aap do tarike se sessions add kar sakte hain:\n\n"
            "1️⃣ **`.txt` File Bhejein:** Jisme har line me ek Pyrogram StringSession ho.\n"
            "2️⃣ **Direct Text Message:** Yahan chat me ek ke neeche ek saare sessions paste karke bhej dein.\n\n"
            "⚡ *Bot saare sessions ko auto-check karke valid accounts ko Supabase Cloud me save kar lega!*"
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_login")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= 2. SINGLE ADD ACCOUNT (OTP) =================
    @app.on_callback_query(filters.regex("^btn_add_acc$"))
    async def add_acc_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        login_sessions[callback.from_user.id] = {
            "state": "AWAITING_PHONE",
            "is_bulk": False,
            "added_count": 0
        }
        prompt_text = (
            "📱 **Add Single Telegram Account**\n\n"
            "Kripya account ka **Phone Number** country code ke sath bhejein:\n\n"
            "_(Example: `+919876543210` ya `+1234567890`)_"
        )
        try:
            await callback.message.edit_text(prompt_text, reply_markup=get_cancel_keyboard(is_bulk=False))
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= 3. BULK OTP LOGIN =================
    @app.on_callback_query(filters.regex("^btn_bulk_login$"))
    async def bulk_login_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        login_sessions[callback.from_user.id] = {
            "state": "AWAITING_PHONE",
            "is_bulk": True,
            "added_count": 0
        }
        prompt_text = (
            "⚡ **Bulk Account Login Mode (Supabase Cloud)**\n\n"
            "Aap ek ke baad ek continuous accounts add kar sakte hain.\n\n"
            "👉 **Pehle Account ka Phone Number bhejein:**\n"
            "_(Example: `+919876543210`)_"
        )
        try:
            await callback.message.edit_text(prompt_text, reply_markup=get_cancel_keyboard(is_bulk=True))
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= 4. FINISH BULK LOGIN =================
    @app.on_callback_query(filters.regex("^btn_finish_bulk_login$"))
    async def finish_bulk_login_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        session_data = login_sessions.pop(callback.from_user.id, None)
        if session_data and "client" in session_data:
            try:
                await session_data["client"].disconnect()
            except Exception:
                pass

        added_cnt = session_data.get("added_count", 0) if session_data else 0
        total_accounts = await db.get_accounts_count()

        from handlers.admin_menu import get_main_keyboard
        finish_text = (
            "🎉 **Bulk Login Completed!**\n\n"
            f"✅ **Iss session me add huye:** `{added_cnt}` accounts\n"
            f"☁️ **Total Cloud Accounts in Supabase:** `{total_accounts}`\n\n"
            "Saare sessions cloud me safely save ho chuke hain."
        )
        try:
            await callback.message.edit_text(finish_text, reply_markup=get_main_keyboard())
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= 5. CANCEL LOGIN =================
    @app.on_callback_query(filters.regex("^btn_cancel_login$"))
    async def cancel_login_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        session_data = login_sessions.pop(callback.from_user.id, None)
        if session_data and "client" in session_data:
            try:
                await session_data["client"].disconnect()
            except Exception:
                pass

        from handlers.admin_menu import get_main_keyboard
        try:
            await callback.message.edit_text("❌ **Login Process Cancelled.**", reply_markup=get_main_keyboard())
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= 6. MESSAGE RECEIVER (SESSIONS, PHONE, OTP, 2FA) =================
    @app.on_message(filters.private & (filters.text | filters.document), group=2)
    async def handle_login_inputs(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return

        session_data = login_sessions.get(message.from_user.id)
        if not session_data:
            message.continue_propagation()
            return

        state = session_data.get("state")
        is_bulk = session_data.get("is_bulk", False)
        from handlers.admin_menu import get_main_keyboard

        # ================= A. BULK SESSIONS PARSER (.TXT / TEXT) =================
        if state == "AWAITING_SESSIONS_INPUT":
            session_strings = []

            # 1. Agar document (.txt file) bheja gaya hai
            if message.document:
                file_name = message.document.file_name or ""
                if not file_name.lower().endswith(".txt"):
                    await message.reply_text("❌ **Invalid File!** Kripya `.txt` file bhejein jisme sessions hon.")
                    return

                temp_path = os.path.join(MEDIA_DIR, f"sessions_{uuid.uuid4().hex[:6]}.txt")
                status_msg = await message.reply_text("⏳ *Reading .txt file & validating sessions...*", parse_mode=None)
                await message.download(file_name=temp_path)

                with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                    session_strings = [line.strip() for line in f if line.strip() and not line.startswith("#")]

                if os.path.exists(temp_path):
                    os.remove(temp_path)

            # 2. Agar direct text message paste kiya gaya hai
            elif message.text:
                status_msg = await message.reply_text("⏳ *Validating sessions & saving to Supabase Cloud...*", parse_mode=None)
                session_strings = [line.strip() for line in message.text.split("\n") if line.strip() and not line.startswith("#")]

            if not session_strings:
                await status_msg.edit_text("⚠️ Koi valid session strings nahi mile. Dobara try karein:")
                return

            valid_count = 0
            invalid_count = 0

            for s_str in session_strings:
                temp_cl = Client(
                    name=f"val_{uuid.uuid4().hex[:6]}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=s_str,
                    in_memory=True
                )
                try:
                    await temp_cl.start()
                    me = await temp_cl.get_me()
                    phone = me.phone_number or f"+{me.id}"
                    if not phone.startswith("+"):
                        phone = f"+{phone}"
                    first_name = me.first_name or "Trader"

                    # Direct Supabase Cloud me save karein
                    await db.save_account(phone, s_str, first_name, me.id)
                    await temp_cl.stop()
                    valid_count += 1
                except Exception:
                    invalid_count += 1

                await asyncio.sleep(0.5)

            login_sessions.pop(message.from_user.id, None)
            total_cloud_accounts = await db.get_accounts_count()

            result_text = (
                "🎉 **Sessions Import Completed!**\n\n"
                f"✅ **Valid & Saved to Supabase:** `{valid_count}`\n"
                f"⚠️ **Invalid / Expired:** `{invalid_count}`\n"
                f"☁️ **Total Cloud Accounts Now:** `{total_cloud_accounts}`\n\n"
                "Saare verified accounts live reviews bhejne ke liye ready hain!"
            )
            await status_msg.edit_text(result_text, reply_markup=get_main_keyboard())

        # ================= B. PHONE NUMBER INPUT (OTP FLOW) =================
        elif state == "AWAITING_PHONE" and message.text:
            phone_number = message.text.strip().replace(" ", "")
            status_msg = await message.reply_text("⏳ *Connecting to Telegram...*", parse_mode=None)

            try:
                temp_client = Client(
                    name=f"temp_{message.from_user.id}_{session_data.get('added_count', 0)}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    in_memory=True
                )
                await temp_client.connect()
                code_info = await temp_client.send_code(phone_number)

                session_data["state"] = "AWAITING_OTP"
                session_data["client"] = temp_client
                session_data["phone"] = phone_number
                session_data["phone_code_hash"] = code_info.phone_code_hash

                await status_msg.edit_text(
                    f"📩 **OTP Sent to:** `{phone_number}`\n\n"
                    "Telegram app par aaya hua **5-digit OTP Code** yahan bhejein:\n"
                    "_(Example: `12345` ya `1 2 3 4 5`)_",
                    reply_markup=get_cancel_keyboard(is_bulk=is_bulk)
                )

            except PhoneNumberInvalid:
                await status_msg.edit_text("❌ **Invalid Phone Number!** Kripya sahi country code ke sath dobara try karein.", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))
            except Exception as e:
                await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))

        # ================= C. OTP CODE INPUT (OTP FLOW) =================
        elif state == "AWAITING_OTP" and message.text:
            otp_code = message.text.strip().replace(" ", "").replace("-", "")
            temp_client = session_data["client"]
            phone = session_data["phone"]
            phone_code_hash = session_data["phone_code_hash"]

            status_msg = await message.reply_text("⏳ *Verifying OTP...*", parse_mode=None)

            try:
                await temp_client.sign_in(phone, phone_code_hash, otp_code)

                session_str = await temp_client.export_session_string()
                me = await temp_client.get_me()
                first_name = me.first_name or "Trader"
                
                await db.save_account(phone, session_str, first_name, me.id)
                await temp_client.disconnect()

                session_data["added_count"] = session_data.get("added_count", 0) + 1

                if is_bulk:
                    session_data["state"] = "AWAITING_PHONE"
                    session_data.pop("client", None)
                    session_data.pop("phone", None)
                    session_data.pop("phone_code_hash", None)

                    await status_msg.edit_text(
                        f"✅ **Account #{session_data['added_count']} Saved to Supabase!**\n\n"
                        f"👤 **Name:** `{first_name}`\n"
                        f"📱 **Phone:** `{phone}`\n"
                        f"🆔 **User ID:** `{me.id}`\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "👉 **Agla Phone Number bhejein** (ya neeche `Finish` dabayein):",
                        reply_markup=get_cancel_keyboard(is_bulk=True)
                    )
                else:
                    login_sessions.pop(message.from_user.id, None)
                    await status_msg.edit_text(
                        f"✅ **Account Added Successfully (Supabase Saved)!**\n\n"
                        f"👤 **Name:** `{first_name}`\n"
                        f"📱 **Phone:** `{phone}`\n"
                        f"🆔 **User ID:** `{me.id}`\n\n"
                        "Permanent session Supabase Cloud me save ho chuka hai.",
                        reply_markup=get_main_keyboard()
                    )

            except SessionPasswordNeeded:
                session_data["state"] = "AWAITING_2FA"
                await status_msg.edit_text(
                    "🔐 **Two-Step Verification (2FA) Detected!**\n\n"
                    "Is account par 2FA password laga hua hai. Kripya apna **2FA Password** yahan bhejein:",
                    reply_markup=get_cancel_keyboard(is_bulk=is_bulk)
                )

            except (PhoneCodeInvalid, PhoneCodeExpired):
                await status_msg.edit_text("❌ **Invalid ya Expired OTP!** Kripya sahi code daalein:", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))
            except Exception as e:
                await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))

        # ================= D. 2FA PASSWORD INPUT (OTP FLOW) =================
        elif state == "AWAITING_2FA" and message.text:
            password = message.text.strip()
            temp_client = session_data["client"]
            phone = session_data["phone"]

            status_msg = await message.reply_text("⏳ *Checking 2FA Password...*", parse_mode=None)

            try:
                await temp_client.check_password(password)

                session_str = await temp_client.export_session_string()
                me = await temp_client.get_me()
                first_name = me.first_name or "Trader"

                await db.save_account(phone, session_str, first_name, me.id)
                await temp_client.disconnect()

                session_data["added_count"] = session_data.get("added_count", 0) + 1

                if is_bulk:
                    session_data["state"] = "AWAITING_PHONE"
                    session_data.pop("client", None)
                    session_data.pop("phone", None)
                    session_data.pop("phone_code_hash", None)

                    await status_msg.edit_text(
                        f"✅ **Account #{session_data['added_count']} (2FA Verified) Saved to Supabase!**\n\n"
                        f"👤 **Name:** `{first_name}`\n"
                        f"📱 **Phone:** `{phone}`\n"
                        f"🆔 **User ID:** `{me.id}`\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "👉 **Agla Phone Number bhejein** (ya neeche `Finish` dabayein):",
                        reply_markup=get_cancel_keyboard(is_bulk=True)
                    )
                else:
                    login_sessions.pop(message.from_user.id, None)
                    await status_msg.edit_text(
                        f"✅ **Account Added Successfully (2FA Verified)!**\n\n"
                        f"👤 **Name:** `{first_name}`\n"
                        f"📱 **Phone:** `{phone}`\n"
                        f"🆔 **User ID:** `{me.id}`\n\n"
                        "Permanent session Supabase Cloud me save ho chuka hai.",
                        reply_markup=get_main_keyboard()
                    )

            except PasswordHashInvalid:
                await status_msg.edit_text("❌ **Galat Password!** Kripya sahi 2FA Password enter karein:", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))
            except Exception as e:
                await status_msg.edit_text(f"❌ **Error:** `{str(e)}`", reply_markup=get_cancel_keyboard(is_bulk=is_bulk))
        else:
            message.continue_propagation()