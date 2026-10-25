"""Seed Mustafo conversations without the webhook (M8 tests)."""

from __future__ import annotations

import uuid

from app.application.conversations import ConversationService
from app.domain.actors import Actor
from app.domain.agent_settings import ConversationSettings, ReplyMode
from app.domain.agents import AgentModule
from app.infrastructure.database import Database
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository

ANSWERS = [
    "menga Telegram bot kerak",
    "Buyurtmalarni tez qabul qilish",
    "katalog, savat",
    "yo'q",
    "ha, rasmlar bor",
    "2 hafta ichida",
    "Lazzat Oshxonasi, Ali, +998901234567",
]


def say(db: Database, body: str, *, chat: int = 7_700_002, n: list[int] | None = None) -> None:
    counter = n if n is not None else _COUNTER
    counter[0] += 1
    with db.transaction() as s:
        ConversationService(s, outbound_sending_enabled=True).handle_inbound(
            chat_id=chat, message_id=counter[0], body=body, display_name="Ali"
        )


_COUNTER = [0]


def confirmed_order(db: Database, chat: int = 7_700_002) -> None:
    with db.transaction() as s:
        AgentSettingsRepository(s).save(
            AgentModule.CONVERSATION,
            ConversationSettings(reply_mode=ReplyMode.AUTO_SAFE),
            Actor.user("owner"),
        )
    for answer in ANSWERS:
        say(db, answer, chat=chat)
    say(db, "ha", chat=chat)


def conversation_id(db: Database, chat: int = 7_700_002) -> uuid.UUID:
    from sqlalchemy import select

    from app.infrastructure.database.models import Conversation

    with db.transaction() as s:
        return s.scalars(
            select(Conversation.id).where(Conversation.external_chat_id == str(chat))
        ).one()
