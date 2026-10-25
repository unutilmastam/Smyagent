"""Outreach against a real schema: planning, caps, no double send, inbox, tasks (M9)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import select

from app.application.controls import AgentControlService
from app.application.outreach import Deferred, OutreachError, OutreachService
from app.application.proposals import ProposalService
from app.core.config import Settings, load_settings
from app.domain.actors import Actor
from app.domain.agent_settings import ConversationSettings
from app.domain.agents import AgentModule, ControlState
from app.domain.contacts import ContactKind
from app.domain.leads import LeadStage
from app.domain.outreach import Channel, OutreachKind, OutreachStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    Contact,
    Job,
    Lead,
    OutreachEvent,
    Proposal,
    SuppressionRecord,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.email.inbox import InboundMail
from app.infrastructure.email.smtp import EmailSendError
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.jobs.context import DeferTaskError, RetryableTaskError, TaskContext
from app.jobs.runner import JobRunner
from app.jobs.tasks.outreach import EMAIL_JOB, run_inbox, run_send_email
from tests.integration.proposal_helpers import awaiting_proposal

OWNER = Actor.user("owner")
EMAIL = "info@lazzat.uz"


def _settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "app_secret_key": "s" * 40,
        "app_base_url": "https://agent.itcode.uz",
        "smtp_host": "mail.itcode.uz",
        "smtp_from": "Mustafo — ITcoDe.Uz <agent@itcode.uz>",
        "outbound_sending_enabled": True,
    }
    base.update(kw)
    return load_settings(**base)


class FakeSender:
    def __init__(self, error: EmailSendError | None = None) -> None:
        self.sent: list[EmailMessage] = []
        self.error = error

    def send(self, message: EmailMessage) -> None:
        if self.error:
            raise self.error
        self.sent.append(message)


class FakeInbox:
    def __init__(self, mails: list[InboundMail]) -> None:
        self.mails = mails

    def fetch_unseen(self) -> list[InboundMail]:
        mails, self.mails = self.mails, []
        return mails


class Notes:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def notify(self, text: str, buttons: object = ()) -> None:
        self.texts.append(text)


def _approved(
    db: Database, *, kinds: tuple[tuple[ContactKind, str, bool], ...] | None = None
) -> uuid.UUID:
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        proposal = s.get(Proposal, pid)
        assert proposal is not None
        for kind, value, role in (
            kinds if kinds is not None else ((ContactKind.EMAIL, EMAIL, True),)
        ):
            s.add(
                Contact(
                    company_id=proposal.company_id, kind=kind, value=value, is_role_address=role
                )
            )
        ProposalService(s).approve(pid, OWNER)
    return pid


def _cfg(db: Database, **kw: object) -> None:
    with db.transaction() as s:
        AgentSettingsRepository(s).save(
            AgentModule.CONVERSATION,
            ConversationSettings(**kw),
            OWNER,  # type: ignore[arg-type]
        )


def _ctx(
    db: Database,
    settings: Settings,
    sender: FakeSender | None = None,
    inbox: FakeInbox | None = None,
    notes: Notes | None = None,
) -> TaskContext:
    return TaskContext(
        database=db,
        settings=settings,
        module=AgentModule.CONVERSATION,
        job_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        search_provider_factory=lambda _s: None,
        email_sender_factory=lambda _s: sender,
        inbox_factory=lambda _s: inbox,
        notifier=notes or Notes(),
    )


def _plan(db: Database, settings: Settings) -> int:
    with db.transaction() as s:
        return OutreachService(s, settings).plan()


def _events(db: Database) -> list[OutreachEvent]:
    with db.transaction() as s:
        rows = list(s.scalars(select(OutreachEvent).order_by(OutreachEvent.created_at)))
        for row in rows:
            s.expunge(row)
        return rows


def _lead(db: Database) -> LeadStage:
    with db.transaction() as s:
        return s.scalars(select(Lead)).one().stage


def test_plan_queues_one_email_per_company(db: Database) -> None:
    settings = _settings()
    _approved(db)
    assert _plan(db, settings) == 2  # event + sender job
    assert _plan(db, settings) == 0  # idempotent (same hour slot, same company)
    [event] = _events(db)
    assert event.channel is Channel.EMAIL and event.status is OutreachStatus.QUEUED
    assert event.recipient == EMAIL and event.kind is OutreachKind.FIRST
    with db.transaction() as s:
        assert len(s.scalars(select(Job).where(Job.job_type == EMAIL_JOB)).all()) == 1


def test_drafting_works_with_sending_disabled(db: Database) -> None:
    _approved(db)
    assert _plan(db, _settings(outbound_sending_enabled=False)) == 1  # event only, no job
    with db.transaction() as s:
        assert s.scalars(select(Job).where(Job.job_type == EMAIL_JOB)).all() == []


def test_send_once_with_footer_and_lead_contacted(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    sender = FakeSender()
    assert "yuborildi" in run_send_email(_ctx(db, settings, sender), {"event_id": str(event.id)})
    [message] = sender.sent
    body = message.get_content()
    assert body.startswith("Assalomu alaykum! Men Mustafo") and "https://agent.itcode.uz/u/" in body
    assert "kerak emas" in body and message["List-Unsubscribe"].startswith("<https://agent")
    assert _lead(db) is LeadStage.CONTACTED
    # Re-running the same job never sends a second time.
    assert "skipped" in run_send_email(_ctx(db, settings, sender), {"event_id": str(event.id)})
    assert len(sender.sent) == 1


def test_interrupted_send_is_never_retried(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    with db.transaction() as s:
        s.get(OutreachEvent, event.id).status = OutreachStatus.SENDING  # type: ignore[union-attr]
    sender = FakeSender()
    assert "skipped" in run_send_email(_ctx(db, settings, sender), {"event_id": str(event.id)})
    assert sender.sent == [] and _events(db)[0].status is OutreachStatus.UNKNOWN


def test_daily_cap_and_spacing_defer(db: Database) -> None:
    settings = _settings()
    _cfg(db, email_warmup_start=1, email_daily_cap=1)
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(event.id)})
    # A second queued email the same day hits the cap (warm-up start = 1).
    with db.transaction() as s:
        other = OutreachEvent(
            company_id=event.company_id,
            channel=Channel.EMAIL,
            kind=OutreachKind.FOLLOW_UP,
            status=OutreachStatus.QUEUED,
            recipient="sales@lazzat.uz",
            idempotency_key="test:other",
            body="x",
            created_by="test",
        )
        s.add(other)
        s.flush()
        other_id = other.id
    with pytest.raises(DeferTaskError) as exc:
        run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(other_id)})
    assert "cap" in str(exc.value) and exc.value.run_after > utcnow() + timedelta(hours=1)
    _cfg(db, email_warmup_start=10, email_min_gap_minutes=10)
    with pytest.raises(DeferTaskError) as gap:
        run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(other_id)})
    assert "spacing" in str(gap.value)


def test_runner_defers_without_using_an_attempt(db: Database) -> None:
    settings = _settings()
    _cfg(db, email_warmup_start=1, email_daily_cap=1)
    _approved(db)
    sender = FakeSender()
    runner = JobRunner(
        db,
        settings,
        search_provider_factory=lambda _s: None,
        email_sender_factory=lambda _s: sender,
        worker_id="t",
    )
    runner.run(max_jobs=5, max_seconds=60)
    assert len(sender.sent) == 1
    with db.transaction() as s:
        s.add(
            OutreachEvent(
                company_id=_events(db)[0].company_id,
                channel=Channel.EMAIL,
                kind=OutreachKind.FOLLOW_UP,
                status=OutreachStatus.QUEUED,
                recipient="sales@lazzat.uz",
                idempotency_key="test:x",
                body="x",
                created_by="test",
            )
        )
    runner.run(max_jobs=5, max_seconds=60)
    assert len(sender.sent) == 1
    with db.transaction() as s:
        job = s.scalars(
            select(Job).where(Job.job_type == EMAIL_JOB).order_by(Job.created_at.desc())
        ).first()
        assert job is not None and job.status.value == "QUEUED" and job.attempts == 0
        assert job.run_after > utcnow()


def test_suppressed_or_stopped_never_sends(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    with db.transaction() as s:
        AgentControlService(s).set_state("global", ControlState.STOPPED, OWNER, "test")
    with pytest.raises(DeferTaskError):
        run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(event.id)})
    with db.transaction() as s:
        AgentControlService(s).set_state("global", ControlState.ACTIVE, OWNER, "test")
        OutreachService(s, settings).unsubscribe(EMAIL, reason="test")
    sender = FakeSender()
    run_send_email(_ctx(db, settings, sender), {"event_id": str(event.id)})
    assert sender.sent == [] and _events(db)[0].status is OutreachStatus.BLOCKED
    assert _lead(db) is LeadStage.DO_NOT_CONTACT


def test_bounce_and_temporary_failure(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    with pytest.raises(RetryableTaskError):
        run_send_email(
            _ctx(db, settings, FakeSender(EmailSendError("SMTP 451", permanent=False))),
            {"event_id": str(event.id)},
        )
    assert _events(db)[0].status is OutreachStatus.QUEUED  # nothing sent: safe to retry
    out = run_send_email(
        _ctx(db, settings, FakeSender(EmailSendError("SMTP 550", permanent=True))),
        {"event_id": str(event.id)},
    )
    assert out.startswith("bounced") and _events(db)[0].status is OutreachStatus.BOUNCED


def test_complaint_pauses_email(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    notes = Notes()
    run_inbox(
        _ctx(
            db,
            settings,
            inbox=FakeInbox([InboundMail("fbl@mail.ru", "x", "", is_complaint=True)]),
            notes=notes,
        ),
        {},
    )
    assert any("Spam" in t for t in notes.texts)
    [event] = _events(db)
    with pytest.raises(DeferTaskError) as exc:
        run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(event.id)})
    assert "paused" in str(exc.value)
    assert _plan(db, settings) == 0  # no new sender jobs while paused
    with db.transaction() as s:
        OutreachService(s, settings).resume_email(OWNER)
        assert not OutreachService(s, settings).channel_state().paused


def test_bounce_rate_auto_pause(db: Database) -> None:
    settings = _settings()
    pid = _approved(db)
    with db.transaction() as s:
        company_id = s.get(Proposal, pid).company_id  # type: ignore[union-attr]
        for i in range(20):
            s.add(
                OutreachEvent(
                    company_id=company_id,
                    channel=Channel.EMAIL,
                    kind=OutreachKind.FIRST,
                    status=OutreachStatus.SENT,
                    recipient=f"a{i}@x.uz",
                    idempotency_key=f"t{i}",
                    body="x",
                    created_by="t",
                    sent_at=utcnow(),
                )
            )
    mails = [
        InboundMail("mailer-daemon@x", "fail", "", is_bounce=True, failed_recipients=[f"a{i}@x.uz"])
        for i in range(2)
    ]
    notes = Notes()
    run_inbox(_ctx(db, settings, inbox=FakeInbox(mails), notes=notes), {})
    assert any("to'xtatildi" in t for t in notes.texts)


def test_reply_and_stop_by_email(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(event.id)})
    quoted = "Qiziq, qo'ng'iroq qiling.\n\nOn Mon Mustafo wrote:\n> \"kerak emas\" deb javob yozing"
    notes = Notes()
    run_inbox(
        _ctx(
            db, settings, inbox=FakeInbox([InboundMail(EMAIL, "Re: Taklif", quoted)]), notes=notes
        ),
        {},
    )
    assert _lead(db) is LeadStage.RESPONDED  # the quoted opt-out hint is not an opt-out
    assert any("javob yozdi" in t and "qo'ng'iroq" in t for t in notes.texts)
    run_inbox(
        _ctx(
            db, settings, inbox=FakeInbox([InboundMail(EMAIL, "Re: Taklif", "STOP")]), notes=notes
        ),
        {},
    )
    assert _lead(db) is LeadStage.DO_NOT_CONTACT
    with db.transaction() as s:
        assert (
            s.scalars(
                select(SuppressionRecord.value).where(SuppressionRecord.channel == "email")
            ).one()
            == EMAIL
        )
    # Unknown senders are left to the owner's mailbox.
    run_inbox(_ctx(db, settings, inbox=FakeInbox([InboundMail("x@y.uz", "hi", "hello")])), {})


def test_follow_up_once_after_five_days(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    run_send_email(_ctx(db, settings, FakeSender()), {"event_id": str(event.id)})
    assert _plan(db, settings) == 0  # too early
    with db.transaction() as s:
        s.get(OutreachEvent, event.id).sent_at = utcnow() - timedelta(days=5, minutes=1)  # type: ignore[union-attr]
    assert _plan(db, settings) == 2  # follow-up event + job
    follow = _events(db)[1]
    assert follow.kind is OutreachKind.FOLLOW_UP and "Bir necha kun oldin" in follow.body
    assert _plan(db, settings) == 0  # never a second follow-up


def test_telegram_and_phone_tasks(db: Database) -> None:
    settings = _settings(smtp_host="", smtp_from="")  # no email: owner tasks
    _cfg(db, telegram_daily_cap=1)
    _approved(
        db,
        kinds=(
            (ContactKind.TELEGRAM, "@lazzat_uz", False),
            (ContactKind.PHONE, "+998901234567", False),
        ),
    )
    assert _plan(db, settings) == 1
    [task] = _events(db)
    assert task.channel is Channel.TELEGRAM and task.status is OutreachStatus.TASK
    with db.transaction() as s:
        OutreachService(s, settings).mark_task_done(task.id, OWNER)
    assert _lead(db) is LeadStage.CONTACTED
    with db.transaction() as s, pytest.raises(OutreachError):
        OutreachService(s, settings).mark_task_done(task.id, OWNER)  # already done


def test_phone_only_company_gets_a_call_task(db: Database) -> None:
    settings = _settings(smtp_host="", smtp_from="")
    _approved(db, kinds=((ContactKind.PHONE, "+998901234567", False),))
    _plan(db, settings)
    [task] = _events(db)
    assert task.channel is Channel.PHONE and task.recipient == "+998901234567"


def test_personal_email_is_never_used(db: Database) -> None:
    _approved(db, kinds=((ContactKind.EMAIL, "ali.karimov@gmail.com", False),))
    assert _plan(db, _settings()) == 0


def test_auto_approve_clean_offers(db: Database) -> None:
    settings = _settings()
    _cfg(db, email_auto_approve=True)
    pid = awaiting_proposal(db)
    with db.transaction() as s:
        company_id = s.get(Proposal, pid).company_id  # type: ignore[union-attr]
        s.add(
            Contact(
                company_id=company_id, kind=ContactKind.EMAIL, value=EMAIL, is_role_address=True
            )
        )
    assert _plan(db, settings) >= 2
    with db.transaction() as s:
        assert s.get(Proposal, pid).status.value == "APPROVED"  # type: ignore[union-attr]
    assert _events(db)[0].status is OutreachStatus.QUEUED


def test_deferred_is_raised_by_service(db: Database) -> None:
    settings = _settings()
    _approved(db)
    _plan(db, settings)
    [event] = _events(db)
    with db.transaction() as s:
        OutreachService(s, settings).channel_state().paused = True
    with db.transaction() as s, pytest.raises(Deferred):
        OutreachService(s, settings).prepare_email(event.id)
