"""Best-effort owner notifications via the owner bot (never blocks or fails the caller)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.infrastructure.telegram.client import TelegramClient, TelegramError

if TYPE_CHECKING:
    from app.application.controls import Button, OwnerNotifier

logger = logging.getLogger("app.notifier")


class TelegramOwnerNotifier:
    def __init__(self, client: TelegramClient, admin_ids: list[int]) -> None:
        self.client = client
        self.admin_ids = admin_ids

    def notify(self, text: str, buttons: Sequence[Button] = ()) -> None:
        markup = inline_keyboard(buttons) if buttons else None
        for chat_id in self.admin_ids:
            try:
                self.client.send_message(chat_id, text, reply_markup=markup)
            except TelegramError as exc:
                logger.warning("owner_notification_failed", extra={"error": str(exc)})


def inline_keyboard(buttons: Sequence[Button]) -> dict[str, Any]:
    """One row of buttons; each is a callback (`data`, ≤64 bytes) or a link."""
    row: list[dict[str, str]] = []
    for button in buttons:
        if button.url:
            row.append({"text": button.text, "url": button.url})
        elif button.data:
            row.append({"text": button.text, "callback_data": button.data[:64]})
    return {"inline_keyboard": [row]}


def build_owner_notifier(settings: Settings) -> OwnerNotifier:
    """Owner bot notifier when the bot is configured, otherwise a no-op."""
    from app.application.controls import NullNotifier

    if not settings.owner_bot_enabled:
        return NullNotifier()
    client = TelegramClient(settings.telegram_admin_bot_token.get_secret_value())
    return TelegramOwnerNotifier(client, settings.telegram_admin_ids)
