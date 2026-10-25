from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings, load_settings
from app.infrastructure.database import Database
from app.infrastructure.database.models import AuditLog, InboundEvent
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.main import create_app
from tests.integration.proposal_helpers import awaiting_proposal

URL = "/api/v1/telegram/webhook"
SECRET = "w" * 40
ADMIN_ID = 5_000_001
TOKEN = "1234567890:AAH" + "x" * 32


@pytest.fixture
def bot_settings() -> Settings:
    return load_settings(
        _env_file=None,
        app_env="test",
        telegram_admin_bot_token=TOKEN,
        telegram_webhook_secret=SECRET,
        telegram_admin_ids=str(ADMIN_ID),
    )


@pytest.fixture
def bot(db: Database, bot_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(bot_settings, database=db)) as client:
        yield client


def _update(
    update_id: int,
    text: str,
    *,
    sender: int = ADMIN_ID,
    chat_type: str = "private",
    username: str = "owner",
) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 1_760_000_000,
            "chat": {"id": sender, "type": chat_type},
            "from": {"id": sender, "is_bot": False, "username": username},
            "text": text,
        },
    }


def _post(client: TestClient, payload: object, secret: str | None = SECRET) -> Any:
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
    return client.post(URL, json=payload, headers=headers)


def test_disabled_without_configuration(web: TestClient) -> None:
    assert _post(web, _update(1, "/status")).status_code == 404


@pytest.mark.parametrize("secret", [None, "", "wrong-secret", SECRET + "x"])
def test_bad_secret_is_rejected_and_nothing_recorded(
    bot: TestClient, db: Database, secret: str | None
) -> None:
    assert _post(bot, _update(1, "/status"), secret=secret).status_code == 403
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(InboundEvent)) == 0


def test_status_for_admin(bot: TestClient, db: Database) -> None:
    with db.transaction() as s:
        CompanyRepository(s).add(NewCompany(name="Denov Savdo", country="UZ"))
    r = _post(bot, _update(10, "/status@SmyAgentBot"))
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "sendMessage" and body["chat_id"] == ADMIN_ID
    assert "SMY Agent holati" in body["text"]
    assert "Kompaniyalar: 1" in body["text"]
    assert "research_audit: ACTIVE" in body["text"]


def test_help_and_unknown_command(bot: TestClient) -> None:
    assert "/status" in _post(bot, _update(11, "/start")).json()["text"]
    assert "Noma'lum buyruq: /deploy" in _post(bot, _update(12, "/deploy now")).json()["text"]
    assert "/status" in _post(bot, _update(13, "salom")).json()["text"]


def test_non_admin_is_ignored_and_audited(bot: TestClient, db: Database) -> None:
    # Same username as the owner, different numeric ID: still ignored (ID-based auth).
    r = _post(bot, _update(20, "/status", sender=999, username="owner"))
    assert r.status_code == 200 and r.content == b""
    with db.transaction() as s:
        actions = s.scalars(select(AuditLog.action)).all()
    assert actions == ["telegram.unauthorized"]


def test_admin_in_group_is_ignored(bot: TestClient) -> None:
    r = _post(bot, _update(21, "/status", chat_type="supergroup"))
    assert r.status_code == 200 and r.content == b""


def test_duplicate_update_processed_once(bot: TestClient, db: Database) -> None:
    first = _post(bot, _update(30, "/status"))
    again = _post(bot, _update(30, "/status"))
    assert first.json()["method"] == "sendMessage"
    assert again.status_code == 200 and again.content == b""
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(InboundEvent)) == 1


def test_garbage_payload_is_acknowledged(bot: TestClient) -> None:
    r = bot.post(URL, content=b"{not json", headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})
    assert r.status_code == 200 and r.content == b""
    assert _post(bot, {"update_id": 40}).status_code == 200  # no message: ignored


def test_oversized_payload_rejected(bot: TestClient) -> None:
    r = bot.post(
        URL, content=b"x" * (300 * 1024), headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}
    )
    assert r.status_code == 413


def test_stop_all_resume_and_single_agent(bot: TestClient, db: Database) -> None:
    from app.infrastructure.database.models import AgentControl

    def state(key: str) -> str:
        with db.transaction() as s:
            return (
                s.scalars(select(AgentControl.state).where(AgentControl.module == key)).one().value
            )

    reply = _post(bot, _update(50, "/stop_all")).json()["text"]
    assert "Barcha agentlar" in reply and state("global") == "STOPPED"
    assert state("global") == "STOPPED"
    _post(bot, _update(51, "/resume_all"))
    assert state("global") == "ACTIVE"
    reply = _post(bot, _update(52, "/agent research_audit pause")).json()["text"]
    assert "research_audit" in reply and state("research_audit") == "PAUSED"
    usage = _post(bot, _update(53, "/agent nobody off")).json()["text"]
    assert "Foydalanish" in usage
    with db.transaction() as s:
        actors = s.scalars(
            select(AuditLog.actor).where(AuditLog.action == "agent_control.set")
        ).all()
    assert actors and all(a == f"user:tg-{ADMIN_ID}" for a in actors)


def test_non_admin_cannot_stop(bot: TestClient, db: Database) -> None:
    from app.infrastructure.database.models import AgentControl

    _post(bot, _update(60, "/stop_all", sender=999))
    with db.transaction() as s:
        assert (
            s.scalars(select(AgentControl.state).where(AgentControl.module == "global")).one().value
            == "ACTIVE"
        )


# -- proposals (M7) -------------------------------------------------------------


def _callback(update_id: int, data: str, *, sender: int = ADMIN_ID) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb{update_id}",
            "from": {"id": sender, "is_bot": False},
            "message": {"message_id": 1, "chat": {"id": sender, "type": "private"}},
            "data": data,
        },
    }


def _stage(db: Database, pid: Any) -> str:
    from app.infrastructure.database.models import Lead, Proposal

    with db.transaction() as s:
        proposal = s.get(Proposal, pid)
        return s.get(Lead, proposal.lead_id).stage.value  # type: ignore[union-attr]


def test_approve_button_answers_callback(bot: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    r = _post(bot, _callback(200, f"pa:{pid}"))
    body = r.json()
    assert body["method"] == "answerCallbackQuery" and body["callback_query_id"] == "cb200"
    assert "tasdiqlandi" in body["text"]
    assert _stage(db, pid) == "APPROVED"
    # Pressing again (new update) is refused politely, nothing changes.
    again = _post(bot, _callback(201, f"pa:{pid}")).json()
    assert "Bajarilmadi" in again["text"] and _stage(db, pid) == "APPROVED"


def test_reject_button(bot: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    assert "rad etildi" in _post(bot, _callback(210, f"pr:{pid}")).json()["text"]
    assert _stage(db, pid) == "DISQUALIFIED"


def test_callback_from_stranger_is_ignored(bot: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    r = _post(bot, _callback(220, f"pa:{pid}", sender=999))
    assert r.status_code == 200 and r.content == b""
    assert _stage(db, pid) == "AWAITING_APPROVAL"


@pytest.mark.parametrize("data", ["pa:not-a-uuid", "xx:00000000-0000-0000-0000-000000000000", ""])
def test_bad_callback_data(bot: TestClient, db: Database, data: str) -> None:
    body = _post(bot, _callback(230, data)).json()
    assert body["text"] == "Noma'lum tugma."


def test_unknown_proposal_callback(bot: TestClient) -> None:
    body = _post(bot, _callback(240, "pa:00000000-0000-0000-0000-000000000000")).json()
    assert "Bajarilmadi" in body["text"]


def test_proposal_commands(bot: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    listing = _post(bot, _update(250, "/proposals")).json()["text"]
    assert str(pid)[:8] in listing and "Lazzat Oshxonasi" in listing
    assert "topilmadi" in _post(bot, _update(251, "/approve abc")).json()["text"]
    done = _post(bot, _update(252, f"/approve {str(pid)[:8]}")).json()["text"]
    assert "tasdiqlandi" in done and _stage(db, pid) == "APPROVED"
    assert "yo'q" in _post(bot, _update(253, "/proposals")).json()["text"]


def test_reject_command_with_reason(bot: TestClient, db: Database) -> None:
    pid = awaiting_proposal(db)
    _post(bot, _update(260, f"/reject {str(pid)[:8]} juda kichik biznes"))
    from app.infrastructure.database.models import ApprovalRequest

    with db.transaction() as s:
        assert s.scalars(select(ApprovalRequest)).one().reason == "juda kichik biznes"
