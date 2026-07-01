import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

_admin_id = os.environ.get("ADMIN_ID")
if not _admin_id:
    raise ValueError("ADMIN_ID environment variable is not set")
ADMIN_ID = int(_admin_id)

# Optional: Telegram channel ID the bot should watch for villa posts.
# Set CHANNEL_ID env var to the channel's numeric ID (e.g. -1001234567890).
# If not set, the bot will process posts from ANY channel it is admin of.
_channel_id = os.environ.get("CHANNEL_ID")
CHANNEL_ID: int | None = int(_channel_id) if _channel_id else None
