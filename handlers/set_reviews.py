import os
import uuid
import zipfile
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified
from config import ADMIN_ID, MEDIA_DIR
import database as db

review_states = {}

def get_reviews_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Text Reviews", callback_data="btn_add_text_rev"),
            InlineKeyboardButton("📂 Load Reviews (.txt)", callback_data="btn_load_txt_file")
        ],
        [
            InlineKeyboardButton("📸 Add Photo Proof", callback_data="btn_add_photo_rev"),
            InlineKeyboardButton("📦 Load Photos (.zip)", callback_data="btn_load_zip_file")
        ],
        [
            InlineKeyboardButton("⚡ Load Trading Preset", callback_data="btn_load_preset"),
        ],
        [
            InlineKeyboardButton("🗑️ Clear TEXT only", callback_data="btn_clear_text_rev"),
            InlineKeyboardButton("🗑️ Clear PHOTOS only", callback_data="btn_clear_photo_rev")
        ],
        [
            InlineKeyboardButton("🗑️ Clear ALL Reviews", callback_data="btn_clear_rev")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")
        ]
    ])

def register_review_handlers(app: Client):

    # ================= SET REVIEWS MENU =================
    @app.on_callback_query(filters.regex("^btn_set_reviews$"))
    async def set_reviews_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        text_cnt, photo_cnt = await db.get_reviews_count()
        menu_text = (
            "📝 **Review Management Hub**\n\n"
            f"💬 Current Text Reviews: `{text_cnt}`\n"
            f"📸 Current Photo Proofs: `{photo_cnt}`\n\n"
            "Neeche diye gaye options me se chunein:"
        )
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_reviews_keyboard())
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= ADD TEXT REVIEWS BUTTON =================
    @app.on_callback_query(filters.regex("^btn_add_text_rev$"))
    async def add_text_rev_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        review_states[callback.from_user.id] = "AWAITING_TEXT_REVIEWS"
        prompt_text = (
            "💬 **Add Bulk Text Reviews**\n\n"
            "Apne saare reviews yahan direct message me paste karein.\n"
            "⚠️ **Dhyan dein:** Har line me sirf **1 review** hona chahiye."
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_set_reviews")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= LOAD REVIEWS FROM .TXT FILE =================
    @app.on_callback_query(filters.regex("^btn_load_txt_file$"))
    async def load_txt_file_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        review_states[callback.from_user.id] = "AWAITING_TXT_FILE"
        prompt_text = (
            "📂 **Upload Reviews (.txt File)**\n\n"
            "Apni **`.txt` File** yahan Document ke roop me bhejein.\n"
            "⚠️ File ke andar har line me ek review hona chahiye."
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_set_reviews")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= ADD SINGLE PHOTO PROOF =================
    @app.on_callback_query(filters.regex("^btn_add_photo_rev$"))
    async def add_photo_rev_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        review_states[callback.from_user.id] = "AWAITING_PHOTO_REVIEW"
        prompt_text = (
            "📸 **Add Single Trading Screenshot Review**\n\n"
            "Trading profit / P&L ka **Screenshot (Photo)** bhejein."
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_set_reviews")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= LOAD PHOTOS FROM .ZIP FILE =================
    @app.on_callback_query(filters.regex("^btn_load_zip_file$"))
    async def load_zip_file_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        review_states[callback.from_user.id] = "AWAITING_ZIP_FILE"
        prompt_text = (
            "📦 **Upload Photo Proofs (.zip File)**\n\n"
            "Apni saari screenshot photos ko ek **`.zip` file** me daal kar yahan bhejein.\n\n"
            "⚡ *Bot saare screenshots ko automatically extract karke permanent proof queue me load kar lega!*"
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_set_reviews")]
        ])
        try:
            await callback.message.edit_text(prompt_text, reply_markup=cancel_kb)
        except MessageNotModified:
            pass
        await callback.answer()

    # ================= LOAD TRADING PRESET =================
    @app.on_callback_query(filters.regex("^btn_load_preset$"))
    async def load_preset_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return

        preset_reviews = [
            "Bhai aaj ka session ekdum next level tha! 3/3 ITM 🔥",
            "Bhai signal dot timing pe tha, 8500 profit booked ❤️",
            "Sir loss cover karwa diya aapne aaj ke session me, thank you so much!",
            "Solid analysis bhai, 2nd call to bohot perfect thi 👍",
            "Bhai VIP group ka access extend kar do please, result mast hai.",
            "Profit done for today sir, disciplined trading follow kiya 💯",
            "Bhai kal bhi session hoga na? Timing bata dena.",
            "Awesome signals bro! Daily aisa hi profit chahiye ❤️🔥",
            "Entry ekdum accurate thi sir, withdrawal laga diya maine.",
            "Bhai aapka strategy sachme work karta hai, genuine trading session!"
        ]

        for rev in preset_reviews:
            await db.add_review("text", rev)

        await callback.answer("✅ 10 Realistic Trading Reviews Added!", show_alert=True)
        text_cnt, photo_cnt = await db.get_reviews_count()
        menu_text = (
            "📝 **Review Management Hub**\n\n"
            f"💬 Current Text Reviews: `{text_cnt}`\n"
            f"📸 Current Photo Proofs: `{photo_cnt}`\n\n"
            "✅ *Default trading pack successfully loaded!*"
        )
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_reviews_keyboard())
        except MessageNotModified:
            pass

    # ================= CLEAR ALL =================
    @app.on_callback_query(filters.regex("^btn_clear_rev$"))
    async def clear_rev_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        await db.clear_all_reviews()
        await callback.answer("🗑️ Saare reviews delete ho gaye!", show_alert=True)
        menu_text = (
            "📝 **Review Management Hub**\n\n"
            "💬 Current Text Reviews: `0`\n"
            "📸 Current Photo Proofs: `0`\n\n"
            "⚠️ *Saare reviews clear kar diye gaye hain.*"
        )
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_reviews_keyboard())
        except MessageNotModified:
            pass

    # ================= CLEAR TEXT ONLY =================
    @app.on_callback_query(filters.regex("^btn_clear_text_rev$"))
    async def clear_text_only(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        await db.clear_text_reviews()
        text_cnt, photo_cnt = await db.get_reviews_count()
        await callback.answer("🗑️ Text reviews cleared!", show_alert=True)
        menu_text = (
            "📝 **Review Management Hub**\n\n"
            f"💬 Current Text Reviews: `{text_cnt}`\n"
            f"📸 Current Photo Proofs: `{photo_cnt}`\n\n"
            "Text reviews clear ho gaye."
        )
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_reviews_keyboard())
        except MessageNotModified:
            pass

    # ================= CLEAR PHOTOS ONLY =================
    @app.on_callback_query(filters.regex("^btn_clear_photo_rev$"))
    async def clear_photo_only(client: Client, callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            return
        await db.clear_photo_reviews()
        text_cnt, photo_cnt = await db.get_reviews_count()
        await callback.answer("🗑️ Photo proofs cleared!", show_alert=True)
        menu_text = (
            "📝 **Review Management Hub**\n\n"
            f"💬 Current Text Reviews: `{text_cnt}`\n"
            f"📸 Current Photo Proofs: `{photo_cnt}`\n\n"
            "Photo proofs clear ho gaye."
        )
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_reviews_keyboard())
        except MessageNotModified:
            pass

    # ================= MESSAGE RECEIVER =================
    @app.on_message(filters.private & (filters.text | filters.photo | filters.document), group=3)
    async def handle_review_inputs(client: Client, message: Message):
        if message.from_user.id != ADMIN_ID:
            return

        state = review_states.get(message.from_user.id)
        if not state:
            message.continue_propagation()
            return

        # 1. DIRECT TEXT REVIEWS
        if state == "AWAITING_TEXT_REVIEWS" and message.text:
            lines = [line.strip() for line in message.text.split("\n") if line.strip()]
            for line in lines:
                await db.add_review("text", line)

            review_states.pop(message.from_user.id, None)
            text_cnt, photo_cnt = await db.get_reviews_count()
            await message.reply_text(
                f"✅ **{len(lines)} Text Reviews Successfully Saved!**\n\n"
                f"📊 Total Text Reviews Now: `{text_cnt}`",
                reply_markup=get_reviews_keyboard()
            )

        # 2. .TXT FILE UPLOADER
        elif state == "AWAITING_TXT_FILE" and message.document:
            file_name = message.document.file_name or ""
            if not file_name.lower().endswith(".txt"):
                await message.reply_text("❌ **Invalid File!** Kripya `.txt` extension wali file bhejein.")
                return

            temp_txt_path = os.path.abspath(os.path.join(MEDIA_DIR, f"upload_{uuid.uuid4().hex[:6]}.txt"))
            status_msg = await message.reply_text("⏳ *Reading & Loading .txt file...*", parse_mode=None)

            try:
                await message.download(file_name=temp_txt_path)
                with open(temp_txt_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_lines = [line.strip() for line in f if line.strip()]

                for line in file_lines:
                    await db.add_review("text", line)

                if os.path.exists(temp_txt_path):
                    os.remove(temp_txt_path)

                review_states.pop(message.from_user.id, None)
                text_cnt, photo_cnt = await db.get_reviews_count()

                await status_msg.edit_text(
                    f"✅ **{len(file_lines)} Reviews Loaded from `{file_name}`!**\n\n"
                    f"📊 Total Text Reviews: `{text_cnt}`",
                    reply_markup=get_reviews_keyboard()
                )

            except Exception as e:
                await status_msg.edit_text(f"❌ **File Error:** `{str(e)}`")

        # 3. .ZIP PHOTOS EXTRACTOR (DEEP NESTED FOLDER FIX + ABSOLUTE PATH)
        elif state == "AWAITING_ZIP_FILE" and message.document:
            file_name = message.document.file_name or ""
            if not file_name.lower().endswith(".zip"):
                await message.reply_text("❌ **Invalid File!** Kripya `.zip` file upload karein.")
                return

            temp_zip_path = os.path.abspath(os.path.join(MEDIA_DIR, f"upload_{uuid.uuid4().hex[:6]}.zip"))
            status_msg = await message.reply_text("⏳ *Downloading & Extracting .zip images...*", parse_mode=None)

            try:
                await message.download(file_name=temp_zip_path)
                valid_extensions = (".jpg", ".jpeg", ".png", ".webp")
                extracted_photos = []

                with zipfile.ZipFile(temp_zip_path, "r") as zf:
                    for member in zf.namelist():
                        filename = os.path.basename(member)
                        # Skip folders or hidden/mac files
                        if not filename or filename.startswith(".") or member.startswith("__MACOSX"):
                            continue
                        if filename.lower().endswith(valid_extensions):
                            ext = os.path.splitext(filename)[1]
                            dest_name = f"proof_{uuid.uuid4().hex[:8]}{ext}"
                            dest_path = os.path.abspath(os.path.join(MEDIA_DIR, dest_name))
                            with open(dest_path, "wb") as f_out:
                                f_out.write(zf.read(member))
                            extracted_photos.append(dest_path)

                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)

                if extracted_photos:
                    await db.add_bulk_photos(extracted_photos)
                    review_states.pop(message.from_user.id, None)
                    text_cnt, photo_cnt = await db.get_reviews_count()

                    await status_msg.edit_text(
                        f"✅ **{len(extracted_photos)} Photo Proofs Successfully Extracted & Saved!**\n\n"
                        f"📸 Total Photo Proofs Now: `{photo_cnt}`\n"
                        "⚡ *Ab ye photos reviews me automatically send hongi!*",
                        reply_markup=get_reviews_keyboard()
                    )
                else:
                    await status_msg.edit_text("⚠️ Zip file ke andar koi valid images (.jpg, .png) nahi mili.")

            except Exception as e:
                await status_msg.edit_text(f"❌ **Zip Extraction Error:** `{str(e)}`")

        # 4. SINGLE PHOTO PROOF
        elif state == "AWAITING_PHOTO_REVIEW" and message.photo:
            caption = message.caption or ""
            file_name = f"proof_{uuid.uuid4().hex[:8]}.jpg"
            file_path = os.path.abspath(os.path.join(MEDIA_DIR, file_name))

            status_msg = await message.reply_text("⏳ *Saving Screenshot...*", parse_mode=None)
            await message.download(file_name=file_path)

            await db.add_review("photo", caption, file_path)
            review_states.pop(message.from_user.id, None)

            text_cnt, photo_cnt = await db.get_reviews_count()
            await status_msg.edit_text(
                f"✅ **Screenshot Proof Saved!**\n\n"
                f"📊 Total Photos Now: `{photo_cnt}`",
                reply_markup=get_reviews_keyboard()
            )
        else:
            message.continue_propagation()