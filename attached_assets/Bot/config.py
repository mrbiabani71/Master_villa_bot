import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

_admin_id = os.environ.get("ADMIN_ID")
if not _admin_id:
    raise ValueError("ADMIN_ID environment variable is not set")
ADMIN_ID = int(_admin_id)
