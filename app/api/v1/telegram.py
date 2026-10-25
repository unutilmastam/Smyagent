"""Telegram webhook for the owner control bot (CLAUDE.md §13.1, §13.3).

The reply is returned in the webhook response body (a Bot API method call), so
handling an update needs no outbound HTTP request from inside Passenger.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.deps import get_database
from app.application.conversations import ConversationService
from app.application.owner_bot import OwnerBotService
from app.core.config import Settings, get_settings
from app.core.exceptions import error_body
from app.core.security import tokens_equal
from app.infrastructure.database import Database
from app.infrastructure.repositories.inbound import InboundEventRepository
from app.infrastructure.telegram.schemas import TgUpdate

logger = logging.getLogger("app.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"], include_in_schema=False)

SECRET_HEADER = "x-telegram-bot-api-secret-token"  # noqa: S105 - header name, not a secret
MAX_BODY_BYTES = 256 * 1024


@router.post("/webhook")
async def owner_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    if not settings.owner_bot_enabled:
        return JSONResponse(error_body("not_found", "Not found"), status_code=404)
    expected = settings.telegram_webhook_secret.get_secret_value()
    if not tokens_equal(request.headers.get(SECRET_HEADER), expected):
        logger.warning("telegram.webhook_bad_secret")
        return JSONResponse(error_body("forbidden", "Forbidden"), status_code=403)

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse(error_body("too_large", "Payload too large"), status_code=413)
    try:
        update = TgUpdate.model_validate_json(body)
    except ValidationError:
        # Acknowledge so Telegram does not retry a payload we will never understand.
        logger.warning("telegram.webhook_unparseable")
        return Response(status_code=200)

    with database.transaction() as session:
        reply = OwnerBotService(
            session,
            admin_ids=settings.telegram_admin_ids,
            outbound_sending_enabled=settings.outbound_sending_enabled,
        ).handle(update)
    if reply is None:
        return Response(status_code=200)
    payload: dict[str, Any]
    if reply.callback_query_id is not None:
        payload = {
            "method": "answerCallbackQuery",
            "callback_query_id": reply.callback_query_id,
            "text": reply.text[:200],
            "show_alert": True,
        }
    else:
        payload = {"method": "sendMessage", "chat_id": reply.chat_id, "text": reply.text}
    return JSONResponse(payload)


CLIENT_CHANNEL = "telegram:client_bot"


@router.post("/client-webhook")
async def client_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    """Mustafo client bot: client-initiated conversations only (CLAUDE.md §13.2)."""
    if not settings.client_bot_enabled:
        return JSONResponse(error_body("not_found", "Not found"), status_code=404)
    expected = settings.telegram_webhook_secret.get_secret_value()
    if not tokens_equal(request.headers.get(SECRET_HEADER), expected):
        logger.warning("telegram.client_webhook_bad_secret")
        return JSONResponse(error_body("forbidden", "Forbidden"), status_code=403)
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse(error_body("too_large", "Payload too large"), status_code=413)
    try:
        update = TgUpdate.model_validate_json(body)
    except ValidationError:
        logger.warning("telegram.client_webhook_unparseable")
        return Response(status_code=200)
    message = update.message
    sender = message.from_ if message else None
    if (
        message is None
        or sender is None
        or sender.is_bot
        or message.chat.type != "private"
        or not message.text
    ):
        return Response(status_code=200)  # only private text messages from people

    with database.transaction() as session:
        if not InboundEventRepository(session).register(CLIENT_CHANNEL, str(update.update_id)):
            return Response(status_code=200)
        outcome = ConversationService(
            session,
            outbound_sending_enabled=settings.outbound_sending_enabled,
            base_url=settings.app_base_url,
        ).handle_inbound(
            chat_id=message.chat.id,
            message_id=message.message_id,
            body=message.text,
            display_name=sender.first_name,
        )
    if outcome is None:
        return Response(status_code=200)
    for text, buttons in outcome.notify:  # after commit; best effort, never blocks the client
        request.app.state.notifier.notify(text, buttons)
    if outcome.send_now is None:
        return Response(status_code=200)
    return JSONResponse(
        {"method": "sendMessage", "chat_id": message.chat.id, "text": outcome.send_now[:4096]}
    )
