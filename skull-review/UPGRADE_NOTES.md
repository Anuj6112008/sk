# Review Bot Upgrade (Client Requirements)

## What was implemented

### 1. PFP & Names management (Admin panel)
- **🖼 PFP & NAMES** button
- Upload new PFPs (single / multiple / zip) → saved to `pfp/`
- Upload new `names.txt`
- Clear used-PFP tracking / Clear used-names tracking
- On exhaust → admin gets personal message + **reuse starts automatically** until new files are uploaded

### 2. Separate remove buttons
- **Clear TEXT only**
- **Clear PHOTOS only**
- **Clear ALL Reviews**

### 3. Review send timing
- Auto Trigger settings → **Set Delay (seconds)**
- Default = 120 (2 minutes after end sticker)

### 4. No reuse + exhaust notify
- PFPs, names, text reviews, photo proofs, templates all tracked as “used”
- When a pool is empty → message to admin + automatic reuse until admin uploads new content

### 5. Random proof images
- Every send picks a **random unused** photo proof (rotation)

### 6. Connect signal bot → review bot (channel sticker track)
- Give this bot **Admin** rights in the signal channel
- Auto Trigger menu:
  1. Set **Watch Channel** (@channel or ID)
  2. **Register End Sticker** (forward the session-end sticker to the bot in private)
  3. Set delay (default 120s)
- When the registered end sticker appears in the watch channel → wait delay → auto send reviews
- Debounce 10 min so multiple stickers don’t re-trigger

### 7. Multiple review templates
- **📋 TEMPLATES** menu
- Upload different `.txt` files as named templates
- Bot randomly picks a template, then a review from that template
- Add / Remove template buttons

### 8. Batch size
- Auto Trigger → **Set Batch Size**
- `0` = all active accounts
- Any number = only that many accounts per batch

## How to use Auto Trigger (most important)

1. Add the review bot as **Admin** in the trading-signals target channel(s)
2. Open bot → **⚙️ AUTO TRIGGER**
3. Set Watch Channel (same channel where end sticker is posted)
4. Register End Sticker (forward the exact end sticker from `@skullxstick` or the one signals bot uses)
5. Keep Auto ON
6. When session ends and end sticker is posted → after 2 min reviews go out automatically
7. After send you still get Delete Chat / Re-send buttons as before

## Files changed
- `database.py` – templates, used_pfps, settings, exhaust flags, separate clear
- `handlers/admin_menu.py` – full new menus
- `handlers/set_reviews.py` – separate clear buttons
- `handlers/rotation_engine.py` – sticker watcher + delayed auto send + batch + random proofs
- `utils/pfp_generator.py` – DB-backed no-reuse PFP

## Notes
- Existing account add / session import / OTP flow unchanged
- Supabase accounts still used
- After reviews are sent, use the same Delete & Re-send / Delete Only buttons
