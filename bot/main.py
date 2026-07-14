import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
for _name in ("admin.smart_import_flow", "channel_importer", "smart_import.importer"):
    logging.getLogger(_name).setLevel(logging.DEBUG)

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not token:
    print("ERROR: TELEGRAM_BOT_TOKEN is not set", flush=True)
    sys.exit(1)

if ":" not in token:
    print(f"ERROR: TELEGRAM_BOT_TOKEN looks invalid — expected format '123456789:ABCdef...' but got: {token[:20]}...", flush=True)
    print("Please update the TELEGRAM_BOT_TOKEN secret with the correct token from @BotFather.", flush=True)
    sys.exit(1)

print(f"Starting Master Villa Bot (token prefix: {token.split(':')[0]})...", flush=True)

import Bot
