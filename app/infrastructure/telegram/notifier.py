"""Best-effort owner notifications via the owner bot (never blocks or fails the caller)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.infrastructure.telegram.client import TelegramClient, TelegramError

if TYPE_CHECKING:
    from app.application.controls import OwnerNotifier

logger = logging.getLogger("app.notifier")


class TelegramOwnerNotifier:
    def __init__(self, client: TelegramClient, admin_ids: list[int]) -> None:
        self.client = client
        self.admin_ids = admin_ids

    def notify(self, text: str) -> None:
        for chat_id in self.admin_ids:
            try:
                self.client.send_message(chat_id, text)
            except TelegramError as exc:
                logger.warning("owner_notification_failed", extra={"error": str(exc)})


def build_owner_notifier(settings: Settings) -> OwnerNotifier:
    """Owner bot notifier when the bot is configured, otherwise a no-op."""
    from app.application.controls import NullNotifier

    if not settings.owner_bot_enabled:
        return NullNotifier()
    client = TelegramClient(settings.telegram_admin_bot_token.get_secret_value())
    return TelegramOwnerNotifier(client, settings.telegram_admin_ids)
