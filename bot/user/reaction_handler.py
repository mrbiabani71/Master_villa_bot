"""Handle Telegram message-reaction updates.

Reaction updates are optional analytics events. They must never interrupt the
main bot update loop if Telegram sends a reaction shape we do not recognize.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database_main import log_activity, register_user

logger = logging.getLogger(__name__)


async def handle_reaction(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Record a reaction update without affecting normal message handling."""
    reaction = update.message_reaction or update.message_reaction_count
    if reaction is None:
        return

    actor = reaction.user or reaction.actor_chat
    actor_id = getattr(actor, "id", None)
    if actor_id is not None:
        try:
            register_user(int(actor_id))
            log_activity("reaction")
        except Exception:
            logger.exception("Could not record a Telegram reaction")