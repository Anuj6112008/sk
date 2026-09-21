import os
import random
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.functions.messages import DeleteHistory
from config import API_ID, API_HASH, ADMIN_ID
from utils.pfp_generator import download_random_pfp, cleanup_pfp
import database as db

logger = logging.getLogger(__name__)

bulk_engine_state = {
    "target_id": None,
    "accounts_data": {},
    "is_running": False,
    "last_trigger_ts": 0,
}

_auto_trigger_lock = asyncio.Lock()


async def _send_exhaust_notifies(client: Client):
    resources = await db.pop_exhaust_notifications()
    for res in resources:
        try:
            await client.send_message(
                ADMIN_ID,
                f"⚠️ **Resource Exhausted & Reuse Started**\n\n"
                f"📁 `{res}` khatam ho gaya tha.\n"
                f"Bot ne reuse start kar diya hai.\n\n"
                f"Naya content upload karne ke liye admin panel use karein."
            )
        except Exception as e:
            logger.error(f"Could not notify admin about {res}: {e}")


async def _delete_all_sent_chats():
    """Delete chat history for all active accounts with the target (same as Delete Only)."""
    accounts = await db.get_all_accounts()
    target_id = bulk_engine_state.get("target_id") or await db.get_target_id()
    if not target_id:
        return

    for acc in accounts:
        phone = acc.get("phone", "")
        clean_phone = phone.replace("+", "").replace(" ", "")
        session_str = acc.get("session_string", "")
        if not session_str:
            continue
        user_client = Client(
            name=f"delround_{clean_phone}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True
        )
        try:
            await user_client.start()
            peer = int(target_id) if str(target_id).isdigit() else str(target_id)
            chat = await user_client.get_chat(peer)
            try:
                raw_peer = await user_client.resolve_peer(chat.id)
                await user_client.invoke(DeleteHistory(peer=raw_peer, max_id=0, revoke=True))
            except Exception:
                pass
            await user_client.stop()
        except Exception as e:
            logger.error(f"Round delete error {phone}: {e}")
            try:
                await user_client.stop()
            except Exception:
                pass
        await asyncio.sleep(0.3)


async def _send_one_round(bot_client: Client, status_msg: Message | None, round_num: int, total_rounds: int) -> int:
    """
    One full round = ALL active accounts send reviews (with PFP/name rotation).
    Returns number of successful accounts.
    """
    target_id = bulk_engine_state.get("target_id") or await db.get_target_id()
    if not target_id:
        if status_msg:
            await status_msg.edit_text("❌ Target ID set nahi hai.")
        return 0

    accounts = await db.get_all_accounts()
    if not accounts:
        if status_msg:
            await status_msg.edit_text("❌ Koi active account nahi hai.")
        return 0

    text_reviews = await db.get_text_reviews()
    photo_reviews = await db.get_photo_reviews()
    if not text_reviews and not photo_reviews:
        if status_msg:
            await status_msg.edit_text("❌ Koi reviews / proofs loaded nahi hain.")
        return 0

    formatted_target = target_id.strip()
    if not formatted_target.startswith("@") and not formatted_target.isdigit():
        formatted_target = f"@{formatted_target}"
    bulk_engine_state["target_id"] = formatted_target
    bulk_engine_state["accounts_data"] = {}

    if status_msg:
        try:
            await status_msg.edit_text(
                f"🚀 **Round {round_num}/{total_rounds} Started!**\n\n"
                f"🎯 Target: `{formatted_target}`\n"
                f"👥 Accounts (sab active): `{len(accounts)}`\n"
                f"📸 Photo Proofs: `{len(photo_reviews)}`\n"
                f"💬 Text Reviews: `{len(text_reviews)}`\n\n"
                "⏳ Dispatching..."
            )
        except Exception:
            pass

    success_count = 0

    for acc in accounts:
        phone = acc.get("phone") or acc.get("Phone") or ""
        clean_phone = phone.replace("+", "").replace(" ", "")
        session_str = acc.get("session_string") or acc.get("session") or ""
        if not session_str:
            continue

        user_client = Client(
            name=f"blk_{clean_phone}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True
        )

        try:
            await user_client.start()

            # Name + PFP rotation
            try:
                new_name = await db.get_next_name()
                parts = new_name.split(" ", 1)
                first = parts[0]
                last = parts[1] if len(parts) > 1 else ""
                await user_client.update_profile(first_name=first, last_name=last)

                pfp_path = await download_random_pfp(phone)
                if pfp_path:
                    try:
                        await user_client.set_profile_photo(photo=pfp_path)
                    except Exception:
                        pass
                    finally:
                        cleanup_pfp(pfp_path)
            except Exception as e:
                logger.warning(f"Profile update error {phone}: {e}")

            target_peer = int(formatted_target) if str(formatted_target).isdigit() else str(formatted_target)
            chat_obj = await user_client.get_chat(target_peer)
            chat_id = chat_obj.id
            sent_msg_ids = []

            msg_count = random.choices([1, 2, 3, 4], weights=[45, 30, 15, 10], k=1)[0]
            tmpl_id = await db.get_random_template_id()

            async def send_text():
                t = await db.get_unique_text_review(tmpl_id)
                m = await user_client.send_message(chat_id, t)
                if m:
                    sent_msg_ids.append(m.id)
                return m

            async def send_photo_with_caption():
                path = await db.get_unique_photo_path()
                caption = await db.get_unique_text_review(tmpl_id)
                if path:
                    m = await user_client.send_photo(chat_id, path, caption=caption)
                else:
                    m = await user_client.send_message(chat_id, caption)
                if m:
                    sent_msg_ids.append(m.id)
                return m

            if msg_count == 1:
                await send_photo_with_caption()
            elif msg_count == 2:
                await send_text()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await send_photo_with_caption()
            elif msg_count == 3:
                await send_text()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await send_photo_with_caption()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await send_text()
            else:
                await send_text()
                await asyncio.sleep(random.uniform(0.8, 1.5))
                await send_text()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await send_photo_with_caption()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await send_text()

            if sent_msg_ids:
                bulk_engine_state["accounts_data"][clean_phone] = {
                    "sent_msg_ids": sent_msg_ids,
                    "chat_id": chat_id,
                    "session_string": session_str,
                    "phone": phone
                }
                success_count += 1

            await user_client.stop()

        except Exception as e:
            logger.error(f"Bulk Send Error for {phone}: {e}")
            try:
                await user_client.stop()
            except Exception:
                pass

        await asyncio.sleep(random.uniform(1.5, 3.0))

    await _send_exhaust_notifies(bot_client)
    return success_count


async def process_bulk_send(bot_client: Client, status_msg: Message = None):
    """
    Multi-round runner.
    Batch size = number of full rounds.
    Example: 30 accounts + batch=2
      → Round 1: all 30 send
      → wait inter_round_delay (default 5 min)
      → auto delete all chats + PFP/name already rotated on next send
      → Round 2: all 30 send again
    """
    if bulk_engine_state["is_running"]:
        logger.warning("Bulk send already running, skipping.")
        return

    bulk_engine_state["is_running"] = True
    try:
        total_rounds = await db.get_batch_size()
        if total_rounds <= 0:
            total_rounds = 1  # minimum 1 round

        inter_delay = await db.get_inter_round_delay()  # default 300s = 5 min

        last_success = 0
        for r in range(1, total_rounds + 1):
            last_success = await _send_one_round(bot_client, status_msg, r, total_rounds)

            if r < total_rounds:
                # Wait then auto-delete before next round
                msg = (
                    f"✅ **Round {r}/{total_rounds} complete** (`{last_success}` accounts)\n\n"
                    f"⏳ {inter_delay} seconds baad messages delete + naya round start hoga..."
                )
                if status_msg:
                    try:
                        await status_msg.edit_text(msg)
                    except Exception:
                        await bot_client.send_message(ADMIN_ID, msg)
                else:
                    await bot_client.send_message(ADMIN_ID, msg)

                await asyncio.sleep(inter_delay)
                await _delete_all_sent_chats()

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            f"🗑️ Round {r} messages deleted.\n🚀 Round {r+1}/{total_rounds} start ho raha hai..."
                        )
                    except Exception:
                        pass

        # Final summary
        action_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Delete Chat & Send Review Again 🔄", callback_data="btn_bulk_delete_and_resend")],
            [InlineKeyboardButton("🗑️ Delete Chats Only 🛑", callback_data="btn_bulk_delete_only")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")]
        ])
        summary = (
            f"✅ **All {total_rounds} Round(s) Completed!**\n\n"
            f"📩 Last round sent: `{last_success}` accounts\n"
            f"🎯 Target: `{bulk_engine_state.get('target_id')}`\n\n"
            "Screenshot le lo. Phir manually delete / re-send bhi kar sakte ho."
        )
        if status_msg:
            try:
                await status_msg.edit_text(summary, reply_markup=action_kb)
            except Exception:
                await bot_client.send_message(ADMIN_ID, summary, reply_markup=action_kb)
        else:
            await bot_client.send_message(ADMIN_ID, summary, reply_markup=action_kb)

    finally:
        bulk_engine_state["is_running"] = False


def register_rotation_handlers(app: Client):

    @app.on_callback_query(filters.regex("^btn_send_reviews$"))
    async def send_reviews_start(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        target_id = await db.get_target_id()
        if not target_id:
            await callback.answer("❌ Pehle Target / USER ID set karein!", show_alert=True)
            return

        accounts = await db.get_all_accounts()
        if not accounts:
            await callback.answer("❌ Pehle accounts add karein!", show_alert=True)
            return

        text_cnt, photo_cnt = await db.get_reviews_count()
        if text_cnt == 0 and photo_cnt == 0:
            await callback.answer("❌ Pehle reviews / proofs load karein!", show_alert=True)
            return

        bulk_engine_state["target_id"] = target_id
        status_msg = await callback.message.edit_text("🚀 Starting multi-round send...")
        await callback.answer()
        await process_bulk_send(client, status_msg)

    # ================= AUTO TRIGGER FROM CHANNEL STICKER =================
    @app.on_message(filters.sticker & ~filters.private)
    async def on_channel_sticker(client: Client, message: Message):
        enabled = await db.get_setting("auto_trigger_enabled", "1")
        if enabled != "1":
            return

        watch = (await db.get_setting("watch_channel", "")).strip()
        if not watch:
            return

        chat = message.chat
        chat_username = f"@{chat.username}" if chat.username else ""
        chat_id_str = str(chat.id)

        if watch not in (chat_username, chat_id_str) and watch.lstrip("@") != (chat.username or ""):
            return

        end_uid = await db.get_setting("end_sticker_unique_id", "")
        sticker = message.sticker
        if not sticker:
            return
        if end_uid and sticker.file_unique_id != end_uid:
            return

        now = time.time()
        if now - bulk_engine_state["last_trigger_ts"] < 600:
            logger.info("Sticker detected but debounce active, ignoring.")
            return

        bulk_engine_state["last_trigger_ts"] = now
        delay = await db.get_review_delay()

        await client.send_message(
            ADMIN_ID,
            f"🏁 **End Sticker Detected!**\n\n"
            f"Channel: `{watch}`\n"
            f"⏳ Reviews {delay} seconds baad auto-send honge (multi-round as per batch size)..."
        )

        async def delayed_send():
            async with _auto_trigger_lock:
                await asyncio.sleep(delay)
                if bulk_engine_state["is_running"]:
                    return
                await client.send_message(ADMIN_ID, "🚀 Auto-trigger: Multi-round reviews start ho rahe hain...")
                await process_bulk_send(client, None)

        asyncio.create_task(delayed_send())

    @app.on_message(filters.private & filters.sticker)
    async def register_end_sticker(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return
        from handlers.admin_menu import user_states
        state = user_states.get(message.from_user.id)
        if state != "AWAITING_END_STICKER":
            return

        uid = message.sticker.file_unique_id
        await db.set_setting("end_sticker_unique_id", uid)
        user_states.pop(message.from_user.id, None)
        await message.reply_text(
            f"✅ **End Sticker Registered!**\n\n`file_unique_id = {uid}`\n\n"
            "Ab jab ye sticker watch channel me aayega, delay ke baad reviews auto-send ho jayenge.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")]])
        )

    @app.on_callback_query(filters.regex("^btn_bulk_delete_and_resend$"))
    async def bulk_delete_and_resend(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        status_msg = await callback.message.edit_text("⏳ Deleting chats then starting new multi-round send...")
        await callback.answer()
        await _delete_all_sent_chats()
        await process_bulk_send(client, status_msg)

    @app.on_callback_query(filters.regex("^btn_bulk_delete_only$"))
    async def bulk_delete_only(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        status_msg = await callback.message.edit_text("⏳ Deleting chats across all accounts...")
        await callback.answer()
        await _delete_all_sent_chats()
        from handlers.admin_menu import get_main_keyboard
        await status_msg.edit_text("✅ **All Chats Deleted!**", reply_markup=get_main_keyboard())
