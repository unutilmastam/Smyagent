"""Best-effort owner notifications via the owner bot (never blocks or fails the caller)."""

from __future__ import annotations

import logging

from app.infrastructure.telegram.client import TelegramClient, TelegramError

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
