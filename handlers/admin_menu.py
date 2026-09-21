from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from config import ADMIN_ID, PFP_DIR, NAMES_FILE
import database as db
import os

user_states = {}


def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ADD ACC (OTP)", callback_data="btn_add_acc"),
            InlineKeyboardButton("📂 SESSIONS (.txt)", callback_data="btn_import_sessions")
        ],
        [
            InlineKeyboardButton("⚡ BULK OTP LOGIN", callback_data="btn_bulk_login"),
            InlineKeyboardButton("🎯 TARGET USER ID", callback_data="btn_user_id")
        ],
        [
            InlineKeyboardButton("📝 SET REVIEWS", callback_data="btn_set_reviews"),
            InlineKeyboardButton("🖼 PFP & NAMES", callback_data="btn_pfp_names")
        ],
        [
            InlineKeyboardButton("📋 TEMPLATES", callback_data="btn_templates"),
            InlineKeyboardButton("⚙️ AUTO TRIGGER", callback_data="btn_auto_settings")
        ],
        [
            InlineKeyboardButton("📊 STATS", callback_data="btn_stats"),
            InlineKeyboardButton("🚀 SEND REVIEWS", callback_data="btn_send_reviews")
        ]
    ])


def register_admin_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            await message.reply_text("⛔ Unauthorized.")
            return
        user_states.pop(message.from_user.id, None)
        await message.reply_text(
            "👋 **Review Automation Bot Ready!**\n\n"
            "Channel me bot ko **admin** banao → Auto Trigger settings me watch channel + end sticker set karo.\n"
            "Jab end sticker aayega → 2 min baad reviews auto jayenge.",
            reply_markup=get_main_keyboard()
        )

    # ================= STATS =================
    @app.on_callback_query(filters.regex("^btn_stats$"))
    async def stats_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        acc_count = await db.get_accounts_count()
        target_id = await db.get_target_id()
        text_cnt, photo_cnt = await db.get_reviews_count()
        pfp_cnt = await db.get_pfp_count()
        names_cnt = await db.get_names_count()
        templates = await db.get_all_templates()
        watch = await db.get_setting("watch_channel", "")
        delay = await db.get_review_delay()
        batch = await db.get_batch_size()
        end_uid = await db.get_setting("end_sticker_unique_id", "")

        text = (
            "📊 **SYSTEM STATS**\n\n"
            f"👥 Active Accounts: `{acc_count}`\n"
            f"🎯 Target: `{target_id or 'Not set'}`\n"
            f"💬 Text Reviews: `{text_cnt}`\n"
            f"📸 Photo Proofs: `{photo_cnt}`\n"
            f"🖼 Local PFPs: `{pfp_cnt}`\n"
            f"📛 Names: `{names_cnt}`\n"
            f"📋 Templates: `{len(templates)}`\n\n"
            f"📡 Watch Channel: `{watch or 'Not set'}`\n"
            f"⏱ Review Delay: `{delay}s`\n"
            f"📦 Rounds (Batch): `{batch}`\n"
            f"🏷 End Sticker: `{'Registered' if end_uid else 'Not registered'}`"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_main_keyboard())
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= TARGET ID =================
    @app.on_callback_query(filters.regex("^btn_user_id$"))
    async def user_id_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_TARGET_ID"
        await callback.message.edit_text(
            "🎯 **Set Target Username / ID**\n\n"
            "Jis chat me reviews bhejne hain uska @username ya ID bhejo:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_main_menu")]])
        )
        await callback.answer()

    # ================= PFP & NAMES =================
    @app.on_callback_query(filters.regex("^btn_pfp_names$"))
    async def pfp_names_menu(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        pfp_cnt = await db.get_pfp_count()
        used_pfp = await db.get_used_pfp_count()
        names_cnt = await db.get_names_count()
        used_names = await db.get_used_names_count()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📁 Upload New PFPs (zip/photos)", callback_data="btn_upload_pfps")],
            [InlineKeyboardButton("♻️ Clear Used PFP Tracking", callback_data="btn_clear_used_pfps")],
            [InlineKeyboardButton("🗑️ DELETE All PFPs from folder", callback_data="btn_delete_all_pfps")],
            [InlineKeyboardButton("📛 Upload New names.txt", callback_data="btn_upload_names")],
            [InlineKeyboardButton("♻️ Clear Used Names Tracking", callback_data="btn_clear_used_names")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")]
        ])
        await callback.message.edit_text(
            f"🖼 **PFP & Names Management**\n\n"
            f"📁 PFPs in folder: `{pfp_cnt}`\n"
            f"🔴 Used PFPs (tracked): `{used_pfp}`\n"
            f"🟢 Available PFPs: `{max(0, pfp_cnt - used_pfp)}`\n\n"
            f"📛 Names in names.txt: `{names_cnt}`\n"
            f"🔴 Used names (tracked): `{used_names}`\n"
            f"🟢 Available names: `{max(0, names_cnt - used_names)}`\n\n"
            "**Clear Used Tracking** = sirf used list reset (files delete nahi hoti)\n"
            "**DELETE All PFPs** = folder se saari images permanently delete",
            reply_markup=kb
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_clear_used_pfps$"))
    async def clear_used_pfps_cb(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        await db.clear_used_pfps()
        await callback.answer("✅ Used PFP tracking cleared! Ab saari PFPs available hain.", show_alert=True)
        # Refresh menu so used count shows 0
        await pfp_names_menu(client, callback)

    @app.on_callback_query(filters.regex("^btn_clear_used_names$"))
    async def clear_used_names_cb(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        await db.clear_used_names()
        await callback.answer("✅ Used names tracking cleared! Ab saare names available hain.", show_alert=True)
        await pfp_names_menu(client, callback)

    @app.on_callback_query(filters.regex("^btn_delete_all_pfps$"))
    async def delete_all_pfps_cb(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        deleted = await db.delete_all_pfps_from_folder()
        await callback.answer(f"🗑️ {deleted} PFP files deleted from folder!", show_alert=True)
        await pfp_names_menu(client, callback)

    @app.on_callback_query(filters.regex("^btn_upload_names$"))
    async def upload_names(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_NAMES_FILE"
        await callback.message.edit_text(
            "📛 **Upload names.txt**\n\nHar line me ek name. File document ke roop me bhejo.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_pfp_names")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_upload_pfps$"))
    async def upload_pfps(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_PFP_FILES"
        await callback.message.edit_text(
            "🖼 **Upload PFPs**\n\n"
            "• Single photo bhejo **ya**\n"
            "• Multiple photos **ya**\n"
            "• .zip file of images\n\n"
            "Bot unhe `pfp/` folder me save kar lega.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_pfp_names")]])
        )
        await callback.answer()

    # ================= TEMPLATES =================
    @app.on_callback_query(filters.regex("^btn_templates$"))
    async def templates_menu(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        templates = await db.get_all_templates()
        lines = [f"• `{t['name']}` (ID: {t['id']})" for t in templates] or ["_No templates yet_"]
        kb_rows = [
            [InlineKeyboardButton("➕ Upload New Template (.txt)", callback_data="btn_add_template")],
        ]
        for t in templates:
            kb_rows.append([InlineKeyboardButton(f"🗑️ Remove: {t['name']}", callback_data=f"btn_del_tmpl_{t['id']}")])
        kb_rows.append([InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")])
        await callback.message.edit_text(
            "📋 **Review Templates**\n\n"
            "Har template alag .txt file hai. Bot randomly template pick karke usme se review lega.\n\n"
            + "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb_rows)
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_add_template$"))
    async def add_template_start(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_TEMPLATE_FILE"
        await callback.message.edit_text(
            "📋 **New Template**\n\n"
            "Pehle template ka **name** text me bhejo (e.g. `session_a`),\n"
            "phir .txt file bhejna.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_templates")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex(r"^btn_del_tmpl_(\d+)$"))
    async def del_template(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        tmpl_id = int(callback.matches[0].group(1))
        await db.delete_template(tmpl_id)
        await callback.answer("✅ Template deleted.", show_alert=True)
        # refresh
        await templates_menu(client, callback)

    # ================= AUTO TRIGGER SETTINGS =================
    @app.on_callback_query(filters.regex("^btn_auto_settings$"))
    async def auto_settings(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        watch = await db.get_setting("watch_channel", "")
        delay = await db.get_review_delay()
        batch = await db.get_batch_size()
        inter = await db.get_inter_round_delay()
        enabled = await db.get_setting("auto_trigger_enabled", "1")
        end_uid = await db.get_setting("end_sticker_unique_id", "")

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📡 Set Watch Channel", callback_data="btn_set_watch")],
            [InlineKeyboardButton("🏷 Register End Sticker", callback_data="btn_reg_end_sticker")],
            [InlineKeyboardButton("⏱ Delay after sticker (sec)", callback_data="btn_set_delay")],
            [InlineKeyboardButton("📦 Set Rounds (Batch)", callback_data="btn_set_batch")],
            [InlineKeyboardButton("⏳ Inter-round wait (sec)", callback_data="btn_set_inter_delay")],
            [InlineKeyboardButton(
                f"{'🟢 Auto ON' if enabled == '1' else '🔴 Auto OFF'}",
                callback_data="btn_toggle_auto"
            )],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")]
        ])
        await callback.message.edit_text(
            "⚙️ **Auto Trigger Settings**\n\n"
            f"📡 Watch Channel: `{watch or 'Not set'}`\n"
            f"🏷 End Sticker: `{'✅ Registered' if end_uid else '❌ Not set'}`\n"
            f"⏱ Delay after sticker: `{delay}s`\n"
            f"📦 Rounds (Batch): `{batch}`  ← kitni baar full cycle\n"
            f"⏳ Wait between rounds: `{inter}s` (default 5 min)\n"
            f"Auto Trigger: `{'ON' if enabled == '1' else 'OFF'}`\n\n"
            "**Batch example:** 30 accounts + Rounds=2\n"
            "→ Round 1: sab 30 se reviews\n"
            "→ 5 min wait → auto delete\n"
            "→ Round 2: phir sab 30 se reviews (naya PFP/name)\n\n"
            "**Kaise use karein:**\n"
            "1. Bot ko signal channel me **Admin** banao\n"
            "2. Watch channel set karo\n"
            "3. End sticker private me forward karke Register karo\n"
            "4. End sticker aate hi delay ke baad multi-round reviews auto jayenge",
            reply_markup=kb
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_set_watch$"))
    async def set_watch(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_WATCH_CHANNEL"
        await callback.message.edit_text(
            "📡 **Watch Channel**\n\n"
            "Channel username (@channel) ya numeric ID bhejo jahan stickers aate hain:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_auto_settings")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_reg_end_sticker$"))
    async def reg_end_sticker(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_END_STICKER"
        await callback.message.edit_text(
            "🏷 **Register End Sticker**\n\n"
            "Trading signals bot ka **Session End Sticker** yahan private chat me forward / bhejo.\n"
            "Bot uska file_unique_id save kar lega.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_auto_settings")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_set_delay$"))
    async def set_delay(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_DELAY"
        await callback.message.edit_text(
            "⏱ **Review Delay (seconds)**\n\n"
            "End sticker ke baad kitne seconds baad reviews bhejne hain?\n"
            "Example: `120` (2 minutes)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_auto_settings")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_set_batch$"))
    async def set_batch(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_BATCH"
        await callback.message.edit_text(
            "📦 **Rounds (Batch)**\n\n"
            "Kitni baar **full cycle** chalani hai?\n\n"
            "Example: `2` + 30 accounts\n"
            "→ Round 1: sab 30 se reviews\n"
            "→ wait (inter-round delay) → auto delete\n"
            "→ Round 2: phir sab 30 se reviews (naya PFP/name)\n\n"
            "Minimum `1`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_auto_settings")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_set_inter_delay$"))
    async def set_inter_delay(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states[callback.from_user.id] = "AWAITING_INTER_DELAY"
        await callback.message.edit_text(
            "⏳ **Inter-round wait (seconds)**\n\n"
            "Ek round complete hone ke baad kitne seconds baad delete + next round?\n"
            "Default: `300` (5 minutes)\n"
            "Example: `300`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="btn_auto_settings")]])
        )
        await callback.answer()

    @app.on_callback_query(filters.regex("^btn_toggle_auto$"))
    async def toggle_auto(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        cur = await db.get_setting("auto_trigger_enabled", "1")
        new = "0" if cur == "1" else "1"
        await db.set_setting("auto_trigger_enabled", new)
        await callback.answer(f"Auto Trigger {'ON' if new == '1' else 'OFF'}", show_alert=True)
        await auto_settings(client, callback)

    # ================= TEXT INPUT HANDLER =================
    @app.on_message(filters.private & filters.text, group=1)
    async def handle_text_inputs(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return
        state = user_states.get(message.from_user.id)
        text = message.text.strip()

        if state == "AWAITING_TARGET_ID":
            if not text.startswith("@") and not text.isdigit():
                text = f"@{text}"
            await db.set_target_id(text)
            user_states.pop(message.from_user.id, None)
            await message.reply_text(f"✅ Target set: `{text}`", reply_markup=get_main_keyboard())

        elif state == "AWAITING_WATCH_CHANNEL":
            if not text.startswith("@") and not text.lstrip("-").isdigit():
                text = f"@{text}"
            await db.set_setting("watch_channel", text)
            user_states.pop(message.from_user.id, None)
            await message.reply_text(f"✅ Watch channel set: `{text}`", reply_markup=get_main_keyboard())

        elif state == "AWAITING_DELAY":
            try:
                sec = int(text)
                if sec < 30:
                    sec = 30
                await db.set_setting("review_delay_seconds", str(sec))
                user_states.pop(message.from_user.id, None)
                await message.reply_text(f"✅ Delay set to {sec} seconds.", reply_markup=get_main_keyboard())
            except ValueError:
                await message.reply_text("Number bhejo (e.g. 120)")

        elif state == "AWAITING_BATCH":
            try:
                n = max(1, int(text))
                await db.set_setting("batch_size", str(n))
                user_states.pop(message.from_user.id, None)
                await message.reply_text(
                    f"✅ Rounds (Batch) = `{n}`\n\n"
                    f"Matlab {n} baar full cycle (sab accounts → wait → delete → phir se).",
                    reply_markup=get_main_keyboard()
                )
            except ValueError:
                await message.reply_text("Number bhejo (min 1)")

        elif state == "AWAITING_INTER_DELAY":
            try:
                sec = max(60, int(text))
                await db.set_setting("inter_round_delay", str(sec))
                user_states.pop(message.from_user.id, None)
                await message.reply_text(
                    f"✅ Inter-round wait = `{sec}` seconds ({sec//60} min approx).",
                    reply_markup=get_main_keyboard()
                )
            except ValueError:
                await message.reply_text("Number bhejo (e.g. 300)")

        elif state == "AWAITING_TEMPLATE_NAME":
            user_states[message.from_user.id] = f"AWAITING_TEMPLATE_FILE|{text}"
            await message.reply_text(f"Template name `{text}` save. Ab uski .txt file bhejo.")

        elif state and state.startswith("AWAITING_TEMPLATE_FILE|"):
            # name already set, waiting for file – handled in document handler
            pass

        elif state == "AWAITING_TEMPLATE_FILE":
            # first they sent name as text
            user_states[message.from_user.id] = f"AWAITING_TEMPLATE_FILE|{text}"
            await message.reply_text(f"✅ Name: `{text}`\nAb .txt file document ke roop me bhejo.")

        else:
            message.continue_propagation()

    # ================= DOCUMENT / PHOTO HANDLERS FOR UPLOADS =================
    @app.on_message(filters.private & (filters.document | filters.photo), group=2)
    async def handle_uploads(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return
        state = user_states.get(message.from_user.id)

        # Names file
        if state == "AWAITING_NAMES_FILE" and message.document:
            path = await message.download()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(NAMES_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                await db.clear_used_names()
                cnt = len([l for l in content.splitlines() if l.strip()])
                await message.reply_text(f"✅ names.txt updated ({cnt} names). Used tracking reset.", reply_markup=get_main_keyboard())
            except Exception as e:
                await message.reply_text(f"Error: {e}")
            finally:
                user_states.pop(message.from_user.id, None)
                try:
                    os.remove(path)
                except Exception:
                    pass
            return

        # Template .txt
        if state and (state == "AWAITING_TEMPLATE_FILE" or state.startswith("AWAITING_TEMPLATE_FILE|")):
            if not message.document:
                await message.reply_text("Please send a .txt document.")
                return
            name = "template"
            if "|" in state:
                name = state.split("|", 1)[1]
            path = await message.download()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                tmpl_id = await db.add_template(name)
                for line in lines:
                    await db.add_review("text", line, template_id=tmpl_id)
                await message.reply_text(
                    f"✅ Template `{name}` added with {len(lines)} reviews.",
                    reply_markup=get_main_keyboard()
                )
            except Exception as e:
                await message.reply_text(f"Error: {e}")
            finally:
                user_states.pop(message.from_user.id, None)
                try:
                    os.remove(path)
                except Exception:
                    pass
            return

        # PFP uploads
        if state == "AWAITING_PFP_FILES":
            import zipfile
            import uuid
            os.makedirs(PFP_DIR, exist_ok=True)
            added = 0
            if message.photo:
                dest = os.path.join(PFP_DIR, f"{uuid.uuid4().hex}.jpg")
                await message.download(dest)
                added = 1
            elif message.document:
                path = await message.download()
                if path.lower().endswith(".zip"):
                    try:
                        with zipfile.ZipFile(path, "r") as z:
                            for info in z.infolist():
                                if info.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                    data = z.read(info)
                                    out = os.path.join(PFP_DIR, f"{uuid.uuid4().hex}{os.path.splitext(info.filename)[1]}")
                                    with open(out, "wb") as f:
                                        f.write(data)
                                    added += 1
                    except Exception as e:
                        await message.reply_text(f"Zip error: {e}")
                else:
                    dest = os.path.join(PFP_DIR, f"{uuid.uuid4().hex}{os.path.splitext(path)[1]}")
                    os.rename(path, dest)
                    added = 1
                try:
                    os.remove(path)
                except Exception:
                    pass
            if added:
                await db.clear_used_pfps()
                await message.reply_text(f"✅ {added} PFP(s) added. Used tracking reset.", reply_markup=get_main_keyboard())
            user_states.pop(message.from_user.id, None)
            return

    # ================= MAIN MENU =================
    @app.on_callback_query(filters.regex("^btn_main_menu$"))
    async def back_to_menu(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        user_states.pop(callback.from_user.id, None)
        try:
            await callback.message.edit_text("👋 **Main Dashboard**", reply_markup=get_main_keyboard())
        except MessageNotModified:
            pass
        await callback.answer()
