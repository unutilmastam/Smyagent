"""Conversation and order pages, owner actions and spec export (M8)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.domain.auth import Role
from app.domain.conversation import ConversationState, MessageStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Conversation,
    ConversationMessage,
    Job,
    Lead,
    OrderBrief,
    User,
)
from tests.integration.conversation_helpers import confirmed_order, conversation_id, say
from tests.integration.web.conftest import login


def _csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def authed(web: TestClient, owner: str) -> TestClient:
    assert login(web).status_code == 303
    return web


def test_pages_require_login(web: TestClient) -> None:
    assert web.get("/conversations").status_code in (302, 303)


def test_list_detail_and_home_order_alert(authed: TestClient, db: Database) -> None:
    confirmed_order(db)
    cid = conversation_id(db)
    listing = authed.get("/conversations").text
    assert "Lazzat Oshxonasi" in listing and "Buyurtma tasdiqlandi" in listing
    html = authed.get(f"/conversations/{cid}").text
    assert "Men Mustafo" in html and "katalog, savat" in html
    assert "mijoz tasdiqladi" in html and "Qabul qilaman" in html
    assert "Yangi buyurtma: 1" in authed.get("/").text
    assert authed.get("/conversations/nope").status_code == 404


def test_spec_export(authed: TestClient, db: Database) -> None:
    confirmed_order(db)
    r = authed.get(f"/conversations/{conversation_id(db)}/brief.md")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("# Project spec — Lazzat Oshxonasi")
    assert "## Required features" in r.text and "Price, payment terms" in r.text


def test_order_decision_from_dashboard(authed: TestClient, db: Database) -> None:
    confirmed_order(db)
    cid = conversation_id(db)
    csrf = _csrf(authed.get(f"/conversations/{cid}").text)
    with db.transaction() as s:
        brief_id = s.scalars(select(OrderBrief.id)).one()
    r = authed.post(f"/orders/{brief_id}/decide", data={"csrf_token": csrf, "decision": "question"})
    assert r.status_code == 303
    with db.transaction() as s:
        assert s.scalars(select(Lead)).one().stage.value == "RESPONDED"
        assert s.get(Conversation, cid).state is ConversationState.HANDOFF  # type: ignore[union-attr]
    again = authed.post(
        f"/orders/{brief_id}/decide", data={"csrf_token": csrf, "decision": "accepted"}
    )
    assert "error=" in again.headers["location"]


def test_draft_send_owner_reply_and_resume(authed: TestClient, db: Database) -> None:
    say(db, "Salom")  # default mode: draft
    cid = conversation_id(db)
    page = authed.get(f"/conversations/{cid}").text
    csrf = _csrf(page)
    with db.transaction() as s:
        draft = s.scalars(
            select(ConversationMessage).where(ConversationMessage.status == MessageStatus.DRAFT)
        ).one()
    assert f"/conversations/messages/{draft.id}/send" in page
    r = authed.post(f"/conversations/messages/{draft.id}/send", data={"csrf_token": csrf})
    assert r.status_code == 303
    with db.transaction() as s:
        assert s.get(ConversationMessage, draft.id).status is MessageStatus.APPROVED  # type: ignore[union-attr]
        assert s.scalars(select(Job).where(Job.job_type == "outbound.telegram_reply")).all()
    authed.post(
        f"/conversations/{cid}/reply",
        data={
            "csrf_token": csrf,
            "body": "Assalomu alaykum, Bahrullo yozyapman. Narxi 3 mln so'm.",
        },
    )
    with db.transaction() as s:
        conv = s.get(Conversation, cid)
        assert conv is not None and conv.state is ConversationState.HANDOFF
        owner_msg = s.scalars(
            select(ConversationMessage).where(ConversationMessage.created_by.like("user:%"))
        ).one()
        assert owner_msg.status is MessageStatus.APPROVED  # the owner may state a price
    authed.post(f"/conversations/{cid}/resume", data={"csrf_token": csrf})
    with db.transaction() as s:
        assert s.get(Conversation, cid).state is ConversationState.OPEN  # type: ignore[union-attr]


def test_viewer_reads_but_cannot_act(web: TestClient, db: Database) -> None:
    say(db, "Salom")
    cid = conversation_id(db)
    with db.transaction() as s:
        password = hash_password("Viewer-Pass-2026!")
        s.add(User(username="viewer1", password_hash=password, role=Role.VIEWER))
    assert login(web, username="viewer1", password="Viewer-Pass-2026!").status_code == 303
    html = web.get(f"/conversations/{cid}").text
    assert "Men Mustafo" in html and "/reply" not in html
    csrf = _csrf(web.get("/").text)
    assert (
        web.post(f"/conversations/{cid}/reply", data={"csrf_token": csrf, "body": "x"}).status_code
        == 403
    )


def test_conversation_settings_page(authed: TestClient, db: Database) -> None:
    url = "/settings/agents/conversation"
    csrf = _csrf(authed.get(url).text)
    r = authed.post(
        url,
        data={"csrf_token": csrf, "reply_mode": "auto_safe", "owner_contact": "+998 90 000 00 00"},
    )
    assert r.status_code == 303
    page = authed.get(url).text
    assert 'value="auto_safe" checked' in page and "+998 90 000 00 00" in page
