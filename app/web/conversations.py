"""Client conversations: list, detail with drafts, owner replies, orders and spec export (M8)."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_database
from app.application.conversations import (
    MAX_OWNER_REPLY,
    ConversationService,
    project_spec,
)
from app.core.config import Settings, get_settings
from app.domain.actors import Actor
from app.domain.conversation import BriefStatus, ConversationState, MessageStatus
from app.domain.errors import DomainError
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Company,
    Conversation,
    ConversationMessage,
    OrderBrief,
)
from app.web.auth import CurrentUser, ForbiddenError, require_csrf, require_user
from app.web.layout import layout_context
from app.web.templating import render

router = APIRouter(include_in_schema=False)
PAGE_SIZE = 50
DECISIONS = ("accepted", "question", "rejected")


def _uuid(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


@router.get("/conversations", response_class=HTMLResponse)
def conversation_list(
    request: Request,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    raw = request.query_params.get("state") or ""
    try:
        state = ConversationState(raw) if raw else None
    except ValueError:
        state = None
    with database.transaction() as session:
        stmt = select(Conversation)
        if state is not None:
            stmt = stmt.where(Conversation.state == state)
        conversations = list(
            session.scalars(stmt.order_by(Conversation.last_message_at.desc()).limit(PAGE_SIZE))
        )
        ids = [c.id for c in conversations]
        drafts = dict(
            session.execute(
                select(ConversationMessage.conversation_id, func.count())
                .where(
                    ConversationMessage.conversation_id.in_(ids),
                    ConversationMessage.status.in_([MessageStatus.DRAFT, MessageStatus.BLOCKED]),
                )
                .group_by(ConversationMessage.conversation_id)
            )
            .tuples()
            .all()
        )
        names = {
            c.id: c.name
            for c in session.scalars(
                select(Company).where(
                    Company.id.in_([c.company_id for c in conversations if c.company_id])
                )
            )
        }
        context = layout_context(session, user)
    context.update(
        {
            "rows": [
                (c, names.get(c.company_id) if c.company_id else None, drafts.get(c.id, 0))
                for c in conversations
            ],
            "state": state,
            "states": list(ConversationState),
        }
    )
    return render(request, "conversations/list.html", context)


def _detail_context(session: Session, conversation_id: uuid.UUID) -> dict[str, object] | None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    messages = list(
        session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    briefs = list(
        session.scalars(
            select(OrderBrief)
            .where(OrderBrief.conversation_id == conversation.id)
            .order_by(OrderBrief.created_at.desc())
        )
    )
    company = session.get(Company, conversation.company_id) if conversation.company_id else None
    return {
        "conversation": conversation,
        "messages": messages,
        "briefs": briefs,
        "company": company,
        "max_reply": MAX_OWNER_REPLY,
    }


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
def conversation_detail(
    request: Request,
    conversation_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    parsed = _uuid(conversation_id)
    with database.transaction() as session:
        data = _detail_context(session, parsed) if parsed else None
        context = layout_context(session, user)
        if data is None:
            context["title_key"] = "error.not_found"
            return render(request, "error.html", context, status=404)
        context.update(data)
        context["done"] = request.query_params.get("done")
        context["error"] = request.query_params.get("error")
        return render(request, "conversations/detail.html", context)


@router.get("/conversations/{conversation_id}/brief.md")
def brief_spec(
    conversation_id: str,
    user: CurrentUser = Depends(require_user),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
) -> Response:
    parsed = _uuid(conversation_id)
    with database.transaction() as session:
        conversation = session.get(Conversation, parsed) if parsed else None
        row = (
            session.scalars(
                select(OrderBrief)
                .where(OrderBrief.conversation_id == conversation.id)
                .order_by(OrderBrief.created_at.desc())
            ).first()
            if conversation
            else None
        )
        if conversation is None or row is None:
            return PlainTextResponse("Not found", status_code=404)
        company = session.get(Company, conversation.company_id) if conversation.company_id else None
        name = company.name if company else (conversation.display_name or "Telegram client")
        text = project_spec(row, conversation, name, row.confirmed_at)
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="order-{parsed}.md"'},
    )


def _service(session: Session, settings: Settings) -> ConversationService:
    return ConversationService(
        session,
        outbound_sending_enabled=settings.outbound_sending_enabled,
        base_url=settings.app_base_url,
    )


def _owner(user: CurrentUser) -> Actor:
    if not user.is_owner:
        raise ForbiddenError("owner role required")
    return Actor.user(str(user.id))


def _back(
    conversation_id: uuid.UUID, done: str | None = None, error: str | None = None
) -> Response:
    query = f"?done={done}" if done else ""
    if error:
        query = f"?error={quote(error[:150])}"
    return RedirectResponse(f"/conversations/{conversation_id}{query}", status_code=303)


@router.post("/conversations/messages/{message_id}/{action}")
def message_action(
    message_id: str,
    action: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    actor = _owner(user)
    parsed = _uuid(message_id)
    if parsed is None or action not in ("send", "discard"):
        return PlainTextResponse("Not found", status_code=404)
    with database.transaction() as session:
        message = session.get(ConversationMessage, parsed)
        if message is None:
            return PlainTextResponse("Not found", status_code=404)
        conversation_id = message.conversation_id
    try:
        with database.transaction() as session:
            service = _service(session, settings)
            if action == "send":
                service.approve_message(parsed, actor)
            else:
                service.discard_message(parsed, actor)
    except DomainError as exc:
        return _back(conversation_id, error=str(exc))
    return _back(conversation_id, done=action)


@router.post("/conversations/{conversation_id}/reply")
def owner_reply(
    conversation_id: str,
    body: Annotated[str, Form(max_length=MAX_OWNER_REPLY)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    actor = _owner(user)
    parsed = _uuid(conversation_id)
    if parsed is None:
        return PlainTextResponse("Not found", status_code=404)
    try:
        with database.transaction() as session:
            _service(session, settings).owner_reply(parsed, actor, body)
    except DomainError as exc:
        return _back(parsed, error=str(exc))
    return _back(parsed, done="reply")


@router.post("/conversations/{conversation_id}/resume")
def resume_bot(
    conversation_id: str,
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    actor = _owner(user)
    parsed = _uuid(conversation_id)
    if parsed is None:
        return PlainTextResponse("Not found", status_code=404)
    try:
        with database.transaction() as session:
            _service(session, settings).resume_bot(parsed, actor)
    except DomainError as exc:
        return _back(parsed, error=str(exc))
    return _back(parsed, done="resume")


@router.post("/orders/{brief_id}/decide")
def decide_order(
    brief_id: str,
    decision: Annotated[str, Form(max_length=16)],
    user: CurrentUser = Depends(require_csrf),  # noqa: B008
    database: Database = Depends(get_database),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    actor = _owner(user)
    parsed = _uuid(brief_id)
    if parsed is None or decision not in DECISIONS:
        return PlainTextResponse("Not found", status_code=404)
    with database.transaction() as session:
        row = session.get(OrderBrief, parsed)
        if row is None:
            return PlainTextResponse("Not found", status_code=404)
        conversation_id = row.conversation_id
    try:
        with database.transaction() as session:
            _service(session, settings).decide_order(parsed, actor, decision)
    except DomainError as exc:
        return _back(conversation_id, error=str(exc))
    return _back(conversation_id, done=decision)


def open_order_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(OrderBrief)
            .where(OrderBrief.status == BriefStatus.CONFIRMED, OrderBrief.owner_decision.is_(None))
        )
        or 0
    )
