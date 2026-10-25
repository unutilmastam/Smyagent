"""Client-facing bot ("Mustafo") sender, built only when its token is configured."""

from __future__ import annotations

from typing import Protocol

from app.core.config import Settings
from app.infrastructure.telegram.client import TelegramClient


class ClientMessenger(Protocol):
    def send_message(self, chat_id: int, text: str) -> None: ...


def build_client_bot(settings: Settings) -> ClientMessenger | None:
    token = settings.telegram_client_bot_token.get_secret_value()
    return TelegramClient(token) if token else None
