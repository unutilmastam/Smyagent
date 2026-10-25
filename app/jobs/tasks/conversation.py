"""Send owner-approved client replies via the Mustafo bot (kill switch + suppression)."""

from __future__ import annotations

import uuid
from typing import Any

from app.application.controls import ControlGate
from app.application.conversations import SEND_JOB, ConversationService
from app.domain.agents import AgentModule, SendingBlockedError
from app.domain.conversation import ConversationState, MessageStatus
from app.infrastructure.database.models import ConversationMessage
from app.infrastructure.database.types import utcnow
from app.infrastructure.telegram.client import TelegramError
from app.jobs.context import RetryableTaskError, TaskContext

__all__ = ["SEND_JOB", "run_send_reply"]


def _block(ctx: TaskContext, message_id: uuid.UUID, reason: str) -> str:
    with ctx.database.transaction() as session:
        message = session.get(ConversationMessage, message_id)
        if message is not None and message.status is MessageStatus.APPROVED:
            message.status = MessageStatus.BLOCKED
            message.note = reason[:200]
    return f"blocked: {reason}"


def run_send_reply(ctx: TaskContext, payload: dict[str, Any]) -> str:
    message_id = uuid.UUID(str(payload["message_id"]))
    with ctx.database.transaction() as session:
        message = session.get(ConversationMessage, message_id)
        if message is None or message.status is not MessageStatus.APPROVED:
            return "skipped (not approved or already sent)"
        conversation = message.conversation
        chat_id = int(conversation.external_chat_id)
        text = message.text
        service = ConversationService(
            session, outbound_sending_enabled=ctx.settings.outbound_sending_enabled
        )
        opted_out = conversation.state is ConversationState.OPTED_OUT or service.is_suppressed(
            chat_id
        )
        try:
            # Immediately before the provider call (CLAUDE.md §13A.2).
            ControlGate(
                session, outbound_sending_enabled=ctx.settings.outbound_sending_enabled
            ).ensure_may_send(AgentModule.CONVERSATION)
            blocked = None
        except SendingBlockedError as exc:
            blocked = str(exc)
    if opted_out:
        return _block(ctx, message_id, "client opted out")
    if blocked is not None:
        return _block(ctx, message_id, blocked)
    bot = ctx.client_bot_factory(ctx.settings)
    if bot is None:
        return _block(ctx, message_id, "TELEGRAM_CLIENT_BOT_TOKEN is not configured")
    try:
        bot.send_message(chat_id, text)
    except TelegramError as exc:
        raise RetryableTaskError(str(exc)) from None
    with ctx.database.transaction() as session:
        message = session.get(ConversationMessage, message_id)
        assert message is not None
        message.status = MessageStatus.SENT
        message.sent_at = utcnow()
        if message.has_disclosure and message.conversation.disclosed_at is None:
            message.conversation.disclosed_at = message.sent_at
    return f"yuborildi: {text[:60]}"
