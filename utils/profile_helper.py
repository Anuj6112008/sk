import os
import sys
import random
import asyncio
import requests
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAMES_PATH

from pyrogram.raw.functions.photos import GetUserPhotos, DeletePhotos
from pyrogram.raw.types import InputUserSelf, InputPhoto

# Live Search Tags for API
API_TAGS = [
    "car", "supercar", "sportsbike", "motorcycle", 
    "nature", "landscape", "sunset", "mountains", "aesthetic"
]

def get_random_name_from_file():
    """data/names.txt se name uthata hai"""
    if os.path.exists(NAMES_PATH):
        try:
            with open(NAMES_PATH, "r", encoding="utf-8") as f:
                names = [line.strip() for line in f if line.strip()]
            if names:
                return random.choice(names)
        except Exception as e:
            print(f"Error reading names.txt: {e}")
    return random.choice(["Karthik Subramanian", "Priya Krishnan", "Vignesh Ramesh", "Abhishek P", "Arjun Madhav"])

def fetch_live_api_photo():
    """
    Zero prebuilt/hardcoded URLs.
    100% Live Random API Call (LoremFlickr & Picsum Stream).
    """
    tag = random.choice(API_TAGS)
    random_id = random.randint(1, 999999)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    # 1. Live Keyword-Based Photo API (Cars, Bikes, Nature, Aesthetic)
    try:
        api_url = f"https://loremflickr.com/500/500/{tag}/all?lock={random_id}"
        res = requests.get(api_url, headers=headers, timeout=10, allow_redirects=True)
        if res.status_code == 200 and len(res.content) > 5000:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            temp_file.write(res.content)
            temp_file.close()
            print(f"🌐 [LIVE API] Downloaded random photo for tag: '{tag}'")
            return temp_file.name
    except Exception as e:
        print(f"⚠️ Live API error: {e}")

    # 2. Live Random Aesthetic Scenery API Fallback
    try:
        fallback_url = f"https://picsum.photos/500/500?random={random_id}"
        res = requests.get(fallback_url, headers=headers, timeout=10)
        if res.status_code == 200 and len(res.content) > 3000:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            temp_file.write(res.content)
            temp_file.close()
            print("🌐 [LIVE API] Downloaded random aesthetic photo")
            return temp_file.name
    except Exception as e:
        print(f"⚠️ Fallback API error: {e}")

    return None

async def remove_all_profile_photos(client):
    """Raw MTProto se saari purani DPs delete karta hai"""
    try:
        raw_photos = await client.invoke(
            GetUserPhotos(user_id=InputUserSelf(), offset=0, max_id=0, limit=100)
        )
        if hasattr(raw_photos, "photos") and raw_photos.photos:
            input_photos = [
                InputPhoto(id=p.id, access_hash=p.access_hash, file_reference=p.file_reference)
                for p in raw_photos.photos
            ]
            if input_photos:
                await client.invoke(DeletePhotos(id=input_photos))
                print(f"🗑️ [BLANK SET] Deleted {len(input_photos)} old photos. Account is now No-DP.")
    except Exception as e:
        print(f"⚠️ Photo delete error: {e}")

async def update_account_identity(client, *args, **kwargs):
    """
    1. names.txt se Name update karta hai.
    2. 50% Accounts: Live API se Cars/Bikes/Nature/Aesthetic DP lagata hai.
    3. 50% Accounts: Blank Initial Circle (No DP) rakhta hai.
    """
    full_name = get_random_name_from_file()
    parts = full_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    # 1. Update Name
    try:
        await client.update_profile(first_name=first_name, last_name=last_name)
        print(f"👤 [NAME SET] -> {full_name}")
    except Exception as e:
        print(f"⚠️ Name error: {e}")

    # 2. Strict 50% vs 50% Ratio
    should_have_pfp = (random.random() < 0.50)

    # Clean old photos first
    await remove_all_profile_photos(client)

    if should_have_pfp:
        photo_path = fetch_live_api_photo()
        if photo_path and os.path.exists(photo_path):
            try:
                await client.set_profile_photo(photo=photo_path)
                print(f"🖼️ [50% RULE] Applied Live Random API DP for {first_name}!")
                await asyncio.sleep(2)  # Wait for Telegram sync
            except Exception as e:
                print(f"⚠️ Set photo error: {e}")
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
    else:
        print(f"👤 [50% RULE] Setting No-DP (Clean Initial Circle for {first_name})")
        await asyncio.sleep(1)

    return f"{full_name} ({'DP: Set' if should_have_pfp else 'DP: Blank'})"