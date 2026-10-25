"""Mustafo client bot end to end: webhook → conversation → Order Brief → owner (M8)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.application.controls import AgentControlService, Button
from app.application.conversations import ConversationError, ConversationService
from app.core.config import Settings, load_settings
from app.domain.actors import Actor
from app.domain.agent_settings import ConversationSettings, ReplyMode
from app.domain.agents import AgentModule, ControlState
from app.domain.conversation import BriefStatus, ConversationState, MessageStatus
from app.domain.leads import LeadStage
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Conversation,
    ConversationMessage,
    Job,
    Lead,
    OrderBrief,
    SuppressionRecord,
)
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.jobs.context import TaskContext
from app.jobs.tasks.conversation import run_send_reply
from app.main import create_app

URL = "/api/v1/telegram/client-webhook"
SECRET = "c" * 40
CHAT = 7_700_001
OWNER = Actor.user("owner")
ANSWERS = [
    "Telegram bot",
    "Buyurtmalarni tez qabul qilish",
    "katalog, savat",
    "yo'q",
    "ha, rasmlar bor",
    "2 hafta ichida",
    "Lazzat Oshxonasi, Ali, +998901234567",
]


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, list[Button]]] = []

    def notify(self, text: str, buttons: Sequence[Button] = ()) -> None:
        self.sent.append((text, list(buttons)))

    def texts(self) -> list[str]:
        return [t for t, _ in self.sent]


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


def _settings(outbound: bool = True) -> Settings:
    return load_settings(
        _env_file=None,
        app_env="test",
        telegram_client_bot_token="1234567890:AAC" + "y" * 32,
        telegram_webhook_secret=SECRET,
        outbound_sending_enabled=outbound,
    )


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def bot(db: Database, notifier: FakeNotifier) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(), database=db, notifier=notifier)) as client:
        yield client


def _auto(db: Database) -> None:
    with db.transaction() as s:
        AgentSettingsRepository(s).save(
            AgentModule.CONVERSATION, ConversationSettings(reply_mode=ReplyMode.AUTO_SAFE), OWNER
        )


_counter = iter(range(1, 10_000))
_OUT = ConversationMessage.direction == "out"


def _say(client: TestClient, text: str, *, chat: int = CHAT, chat_type: str = "private") -> Any:
    n = next(_counter)
    payload = {
        "update_id": 900_000 + n,
        "message": {
            "message_id": n,
            "chat": {"id": chat, "type": chat_type},
            "from": {"id": chat, "is_bot": False, "first_name": "Ali"},
            "text": text,
        },
    }
    r = client.post(URL, json=payload, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})
    assert r.status_code == 200
    return r.json()["text"] if r.content else None


def _conversation(db: Database, chat: int = CHAT) -> Conversation:
    with db.transaction() as s:
        conv = s.scalars(
            select(Conversation).where(Conversation.external_chat_id == str(chat))
        ).one()
        s.expunge(conv)
        return conv


def _lead_stage(db: Database) -> LeadStage:
    with db.transaction() as s:
        return s.scalars(select(Lead)).one().stage


def test_disabled_and_secret(web: TestClient, bot: TestClient) -> None:
    assert web.post(URL, json={"update_id": 1}).status_code == 404  # client bot not configured
    assert bot.post(URL, json={"update_id": 1}).status_code == 403  # no secret header


def test_default_mode_drafts_every_reply_for_the_owner(
    bot: TestClient, db: Database, notifier: FakeNotifier
) -> None:
    assert _say(bot, "Salom") is None  # nothing sent without approval
    with db.transaction() as s:
        draft = s.scalars(
            select(ConversationMessage).where(ConversationMessage.status == MessageStatus.DRAFT)
        ).one()
        assert draft.text.startswith("Assalomu alaykum! Men Mustafo") and draft.has_disclosure
    text, buttons = notifier.sent[-1]
    assert "Mustafo javobi" in text and [b.data for b in buttons] == [
        f"ms:{draft.id}",
        f"mx:{draft.id}",
    ]
    # The second reply does not repeat the disclosure (the first is still pending).
    _say(bot, "nima qilasiz?")
    with db.transaction() as s:
        drafts = list(
            s.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.status == MessageStatus.DRAFT)
                .order_by(ConversationMessage.created_at)
            )
        )
        assert [d.has_disclosure for d in drafts] == [True, False]


def test_full_order_intake_in_auto_mode(
    bot: TestClient, db: Database, notifier: FakeNotifier
) -> None:
    _auto(db)
    first = _say(bot, "Assalomu alaykum, narxi qancha?")
    assert first.startswith("Assalomu alaykum! Men Mustafo")  # disclosure first
    assert "shaxsan yuboradi" in first and "1/7" in first
    for answer in ANSWERS[:-1]:
        reply = _say(bot, answer)
        assert "Men Mustafo" not in reply  # disclosed once only
    shown = _say(bot, ANSWERS[-1])
    assert "Buyurtmangizni shunday tushundim" in shown and "2 hafta" not in shown
    assert _lead_stage(db) is LeadStage.RESPONDED
    with db.transaction() as s:
        assert s.scalars(select(OrderBrief)).one().status is BriefStatus.AWAITING_CONFIRMATION
    # Something that is not an explicit "yes" never confirms the brief.
    again = _say(bot, "dizayn ko'k rangda bo'lsin")
    assert "shunday tushundim" in again and "ko'k rangda" in again
    assert not any("Yangi buyurtma" in t for t in notifier.texts())

    done = _say(bot, "ha")
    assert "Buyurtmangiz qabul qilindi" in done
    assert _lead_stage(db) is LeadStage.ORDER_CONFIRMED
    with db.transaction() as s:
        brief = s.scalars(select(OrderBrief)).one()
        assert brief.status is BriefStatus.CONFIRMED and brief.confirmed_at is not None
        confirmation = s.get(ConversationMessage, brief.confirmation_message_id)
        assert confirmation is not None and confirmation.text == "ha"
        assert brief.services == ["telegram_bot"]
    orders = [t for t in notifier.texts() if t.startswith("✅ Yangi buyurtma")]
    assert len(orders) == 1 and "Lazzat Oshxonasi" in orders[0] and "yasatishga rozi" in orders[0]
    # Writing again after the order: polite reply, no second order notification.
    _say(bot, "ha")
    assert len([t for t in notifier.texts() if t.startswith("✅ Yangi buyurtma")]) == 1
    with db.transaction() as s:
        sent = s.scalars(
            select(ConversationMessage.text).where(ConversationMessage.direction == "out")
        ).all()
        assert all(not re.search(r"so'm|\$|usd", t, re.I) for t in sent)


def test_opt_out_is_immediate_and_permanent(
    bot: TestClient, db: Database, notifier: FakeNotifier
) -> None:
    _auto(db)
    _say(bot, "Salom, menga sayt kerak")
    assert _say(bot, "Rahmat, kerak emas") is None
    conv = _conversation(db)
    assert conv.state is ConversationState.OPTED_OUT
    with db.transaction() as s:
        assert s.scalars(select(SuppressionRecord)).one().value == str(CHAT)
        assert s.scalars(select(OrderBrief)).one().status is BriefStatus.CANCELLED
    assert _lead_stage(db) is LeadStage.DO_NOT_CONTACT
    assert any("rad etdi" in t for t in notifier.texts())
    assert _say(bot, "salom yana") is None  # never answered again
    with db.transaction() as s, pytest.raises(ConversationError):
        ConversationService(s, outbound_sending_enabled=True).owner_reply(conv.id, OWNER, "x")


def test_bot_question_and_human_handoff(
    bot: TestClient, db: Database, notifier: FakeNotifier
) -> None:
    _auto(db)
    answer = _say(bot, "Siz botmisiz?")
    assert "AI yordamchiman, inson emasman" in answer
    handoff = _say(bot, "odam bilan gaplashmoqchiman")
    assert "@ITcoDe_Uz" in handoff
    assert _conversation(db).state is ConversationState.HANDOFF
    assert any("gaplashmoqchi" in t for t in notifier.texts())
    assert _say(bot, "qachon yozasiz?") is None  # Mustafo stays silent during handoff


def test_russian_client_gets_russian_replies(bot: TestClient, db: Database) -> None:
    _auto(db)
    reply = _say(bot, "Здравствуйте, сколько стоит интернет-магазин?")
    assert reply.startswith("Здравствуйте! Я Мустафо") and "лично пришлёт цену" in reply


def test_auto_mode_respects_kill_switch_and_outbound_flag(
    db: Database, notifier: FakeNotifier
) -> None:
    _auto(db)
    with TestClient(create_app(_settings(outbound=False), database=db, notifier=notifier)) as c:
        assert _say(c, "Salom") is None
    with db.transaction() as s:
        draft = s.scalars(
            select(ConversationMessage).where(ConversationMessage.direction == "out")
        ).one()
        assert draft.status is MessageStatus.DRAFT and "OUTBOUND" in (draft.note or "")
    with db.transaction() as s:
        AgentControlService(s).set_state("global", ControlState.STOPPED, OWNER, "test")
    with TestClient(create_app(_settings(), database=db, notifier=notifier)) as c:
        assert _say(c, "menga sayt kerak") is None


def test_ignored_updates(bot: TestClient, db: Database) -> None:
    assert _say(bot, "salom", chat=-100123, chat_type="group") is None
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(Conversation)) == 0


def test_duplicate_update_is_processed_once(bot: TestClient, db: Database) -> None:
    payload = {
        "update_id": 555,
        "message": {
            "message_id": 1,
            "chat": {"id": CHAT, "type": "private"},
            "from": {"id": CHAT, "is_bot": False},
            "text": "Salom",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
    bot.post(URL, json=payload, headers=headers)
    bot.post(URL, json=payload, headers=headers)
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(ConversationMessage)) == 2  # in + draft


def _ctx(db: Database, settings: Settings, fake: FakeBot | None) -> TaskContext:
    return TaskContext(
        database=db,
        settings=settings,
        module=AgentModule.CONVERSATION,
        job_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        search_provider_factory=lambda _s: None,
        client_bot_factory=lambda _s: fake,
    )


def test_owner_approval_then_send_job(bot: TestClient, db: Database) -> None:
    _say(bot, "Salom")
    with db.transaction() as s:
        draft = s.scalars(
            select(ConversationMessage).where(ConversationMessage.direction == "out")
        ).one()
        mid = draft.id
        ConversationService(s, outbound_sending_enabled=True).approve_message(mid, OWNER)
        job = s.scalars(select(Job).where(Job.job_type == "outbound.telegram_reply")).one()
        assert job.payload == {"message_id": str(mid)}
    fake = FakeBot()
    assert "yuborildi" in run_send_reply(_ctx(db, _settings(), fake), {"message_id": str(mid)})
    assert fake.sent and fake.sent[0][0] == CHAT and "Men Mustafo" in fake.sent[0][1]
    assert _conversation(db).disclosed_at is not None
    # Re-running the job never sends twice.
    assert "skipped" in run_send_reply(_ctx(db, _settings(), fake), {"message_id": str(mid)})
    assert len(fake.sent) == 1


def test_send_job_blocks_after_opt_out_and_when_disabled(bot: TestClient, db: Database) -> None:
    _say(bot, "Salom")
    with db.transaction() as s:
        mid = s.scalars(
            select(ConversationMessage.id).where(ConversationMessage.direction == "out")
        ).one()
        ConversationService(s, outbound_sending_enabled=True).approve_message(mid, OWNER)
    fake = FakeBot()
    out = run_send_reply(_ctx(db, _settings(outbound=False), fake), {"message_id": str(mid)})
    assert out.startswith("blocked") and fake.sent == []
    with db.transaction() as s:
        assert s.get(ConversationMessage, mid).status is MessageStatus.BLOCKED  # type: ignore[union-attr]
        ConversationService(s, outbound_sending_enabled=True).approve_message(mid, OWNER)
    _say(bot, "yozmang")  # opt-out blocks the queued message
    assert run_send_reply(_ctx(db, _settings(), fake), {"message_id": str(mid)}).startswith(
        "skipped"
    )
    assert fake.sent == []


def test_order_decisions(bot: TestClient, db: Database) -> None:
    _auto(db)
    _say(bot, "menga bot kerak")
    for answer in ANSWERS[1:]:
        _say(bot, answer)
    _say(bot, "ha")
    with db.transaction() as s:
        brief_id = s.scalars(select(OrderBrief.id)).one()
        service = ConversationService(s, outbound_sending_enabled=True)
        service.decide_order(brief_id, OWNER, "accepted")
        with pytest.raises(ConversationError):
            service.decide_order(brief_id, OWNER, "rejected")
    assert _lead_stage(db) is LeadStage.WON


def test_order_confirmed_requires_confirmed_brief(bot: TestClient, db: Database) -> None:
    _auto(db)
    _say(bot, "menga bot kerak")
    with db.transaction() as s:
        brief_id = s.scalars(select(OrderBrief.id)).one()
        with pytest.raises(ConversationError):
            ConversationService(s, outbound_sending_enabled=True).decide_order(
                brief_id, OWNER, "accepted"
            )
    assert _lead_stage(db) is LeadStage.RESPONDED
