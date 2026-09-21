import os

# ================= BASE DIRECTORY =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= TELEGRAM API CREDENTIALS =================
API_ID = int(os.getenv("API_ID", "36621792"))# Apna numeric API ID dalein
API_HASH = os.getenv("API_HASH", "bbb33bfb0ed319f6b9b099745878bff1")  # Apna API Hash dalein
BOT_TOKEN = os.getenv("BOT_TOKEN", "8785852001:AAHcvLI2MPVVDtuffArn1M_k2QO4g23H3S0")  # Bot Token

# ================= ADMIN CONFIGURATION =================
ADMIN_ID = 6905413717

# ================= SUPABASE CLOUD REST API CONFIG =================
SUPABASE_URL = "https://jjrgatqtiwkehwqovrtf.supabase.co"
SUPABASE_KEY = "sb_publishable_Ls4S97bf1S7phjUI9PPiUQ_lDq3UwVn"

# ================= LOCAL STORAGE PATHS =================
DB_PATH = os.path.join(BASE_DIR, "reviews_bot.db")
NAMES_FILE = os.path.join(BASE_DIR, "names.txt")
MEDIA_DIR = os.path.join(BASE_DIR, "saved_media")
PFP_DIR = os.path.join(BASE_DIR, "pfp")  # Local PFP Folder

# Folders auto-create karein agar na hon
for directory in (MEDIA_DIR, PFP_DIR):
    if not os.path.exists(directory):
        os.makedirs(directory)
