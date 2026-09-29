from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env file from the bot folder
load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

_admin_id = os.getenv("ADMIN_ID")
if not _admin_id:
    raise ValueError("ADMIN_ID environment variable is not set")
ADMIN_ID = int(_admin_id)

_channel_id = os.getenv("CHANNEL_ID")
CHANNEL_ID = int(_channel_id) if _channel_id else None

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")