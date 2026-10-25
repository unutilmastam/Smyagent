"""Outbound outreach for approved offers (CLAUDE.md §13.2a, §15.3, M9).

One first contact per company on its best public channel — email (sent by the agent
within caps), else Telegram (one-tap task for the owner), else phone (call task) —
plus at most one follow-up. Every email carries an opt-out link; suppression, the
email pause and the kill switch are checked right before each send. A send that may
have reached SMTP is never retried (status UNKNOWN) so nothing is sent twice.
"""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.application.control_snapshot import start_of_local_day
from app.application.controls import ControlGate
from app.application.proposals import ProposalService
from app.application.workflow import NotFoundError, WorkflowService
from app.core.config import Settings
from app.domain.actors import Actor
from app.domain.agent_settings import ConversationSettings
from app.domain.agents import AgentModule, SendingBlockedError
from app.domain.contacts import ContactKind
from app.domain.conversation import Intent, classify
from app.domain.errors import DomainError
from app.domain.leads import LeadStage, can_transition
from app.domain.outreach import (
    CapPolicy,
    Channel,
    OutreachKind,
    OutreachStatus,
    email_cap_today,
    email_footer,
    follow_up,
    follow_up_due,
    should_pause,
    unsubscribe_token,
)
from app.domain.persona import Language
from app.domain.proposals import ProposalStatus
from app.domain.quality_gate import Verdict
from app.infrastructure.database.models import (
    ChannelState,
    Company,
    Contact,
    Lead,
    OutreachEvent,
    Proposal,
    SuppressionRecord,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.email.inbox import InboundMail
from app.infrastructure.email.smtp import OutgoingEmail, build_message
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.infrastructure.repositories.jobs import JobRepository
from app.infrastructure.repositories.workflow import AuditLogRepository

ACTOR = Actor.agent(AgentModule.CONVERSATION.value)
AUTO_APPROVER = Actor.system("outreach_auto_send")
EMAIL_JOB = "outbound.email"  # "outbound." → cancelled by the global STOP
INBOX_JOB = "email.inbox"
BOUNCE_WINDOW = timedelta(days=30)
_QUOTE_START = re.compile(
    r"^(?:>|On .+wrote:|.+(?:пишет|написал|yozdi):\s*$|-{2,}\s*Original Message|From:\s|—\s*$)",
    re.I,
)


class OutreachError(DomainError):
    """The outreach event is not in a state that allows this action."""


class Deferred(Exception):
    def __init__(self, reason: str, until: datetime) -> None:
        super().__init__(reason)
        self.until = until


@dataclass(frozen=True)
class PreparedEmail:
    event_id: uuid.UUID
    message: EmailMessage


@dataclass(frozen=True)
class TodayStats:
    email_sent: int
    email_cap: int
    telegram_done: int
    telegram_cap: int
    bounced_30d: int
    sent_30d: int
    paused: bool
    pause_reason: str | None


def strip_quoted(text: str) -> str:
    """The client's own words: drop the quoted original and our footer."""
    lines: list[str] = []
    for line in text.splitlines():
        if _QUOTE_START.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()[:2000]


class OutreachService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.app = settings
        self.cfg: ConversationSettings = AgentSettingsRepository(session).get(
            AgentModule.CONVERSATION
        )
        self.workflow = WorkflowService(session)

    # -- suppression -------------------------------------------------------------

    def is_suppressed(self, channel: Channel, value: str) -> bool:
        return (
            self.session.scalars(
                select(SuppressionRecord.id).where(
                    SuppressionRecord.channel == channel.value,
                    SuppressionRecord.value == value.lower(),
                )
            ).first()
            is not None
        )

    def unsubscribe(self, address: str, *, reason: str) -> int:
        """Permanent opt-out of one email address. Returns blocked pending events."""
        address = address.strip().lower()
        contact_companies = list(
            self.session.scalars(
                select(Contact.company_id).where(
                    Contact.kind == ContactKind.EMAIL, Contact.value == address
                )
            )
        )
        if not self.is_suppressed(Channel.EMAIL, address):
            self.session.add(
                SuppressionRecord(
                    channel=Channel.EMAIL.value,
                    value=address,
                    company_id=contact_companies[0] if contact_companies else None,
                    reason=reason[:200],
                )
            )
        result = self.session.execute(
            update(OutreachEvent)
            .where(
                OutreachEvent.channel == Channel.EMAIL,
                OutreachEvent.recipient == address,
                OutreachEvent.status.in_([OutreachStatus.QUEUED, OutreachStatus.TASK]),
            )
            .values(status=OutreachStatus.BLOCKED, error="unsubscribed")
            .execution_options(synchronize_session=False)
        )
        blocked = result.rowcount if isinstance(result, CursorResult) else 0
        for company_id in set(contact_companies):
            self._lead_to(company_id, LeadStage.DO_NOT_CONTACT, "unsubscribed from email")
        self.session.flush()
        return blocked

    # -- planning (cron) -----------------------------------------------------------

    def plan(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        created = 0
        if self.cfg.email_auto_approve and self.app.email_enabled:
            created += self.auto_approve_clean()
        created += self.plan_first_contacts()
        created += self.plan_follow_ups(now)
        created += self.enqueue_email_jobs(now)
        return created

    def auto_approve_clean(self) -> int:
        """Owner turned auto-send on: gate-clean offers need no tap (CLAUDE.md §8.2)."""
        service = ProposalService(self.session)
        approved = 0
        for proposal in self.session.scalars(
            select(Proposal).where(Proposal.status == ProposalStatus.AWAITING_APPROVAL).limit(50)
        ):
            version = next(
                (v for v in proposal.versions if v.number == proposal.current_version), None
            )
            if version is None or version.gate_verdict is not Verdict.APPROVED:
                continue  # needs_review stays with the owner
            if self._best_email(proposal.company_id) is None:
                continue  # only email is automatic; Telegram/phone stay owner tasks
            service.approve(proposal.id, AUTO_APPROVER)
            approved += 1
        return approved

    def plan_first_contacts(self, limit: int = 50) -> int:
        created = 0
        rows = self.session.execute(
            select(Proposal, Lead)
            .join(Lead, Lead.id == Proposal.lead_id)
            .where(Proposal.status == ProposalStatus.APPROVED, Lead.stage == LeadStage.APPROVED)
            .order_by(Proposal.updated_at)
            .limit(limit)
        ).all()
        for proposal, lead in rows:
            key = f"first:{proposal.company_id}"
            if self._event_exists(key):
                continue
            version = next(v for v in proposal.versions if v.number == proposal.current_version)
            channel, recipient = self._pick_channel(proposal.company_id)
            if channel is None or recipient is None:
                continue
            self.session.add(
                OutreachEvent(
                    company_id=proposal.company_id,
                    lead_id=lead.id,
                    proposal_id=proposal.id,
                    channel=channel,
                    kind=OutreachKind.FIRST,
                    status=OutreachStatus.QUEUED
                    if channel is Channel.EMAIL
                    else OutreachStatus.TASK,
                    recipient=recipient,
                    idempotency_key=key,
                    subject=version.title,
                    body=version.body,
                    created_by=str(ACTOR),
                )
            )
            created += 1
        self.session.flush()
        return created

    def plan_follow_ups(self, now: datetime) -> int:
        created = 0
        firsts = self.session.scalars(
            select(OutreachEvent).where(
                OutreachEvent.kind == OutreachKind.FIRST,
                OutreachEvent.status.in_([OutreachStatus.SENT, OutreachStatus.DONE]),
                OutreachEvent.channel.in_([Channel.EMAIL, Channel.TELEGRAM]),
                OutreachEvent.replied_at.is_(None),
                OutreachEvent.sent_at <= now - timedelta(days=self.cfg.follow_up_days),
            )
        ).all()
        for first in firsts:
            key = f"follow_up:{first.company_id}"
            if first.sent_at is None or not follow_up_due(
                first.sent_at, now, self.cfg.follow_up_days
            ):
                continue
            if self._event_exists(key):
                continue
            lead = self.session.get(Lead, first.lead_id) if first.lead_id else None
            if lead is None or lead.stage is not LeadStage.CONTACTED:
                continue  # replied, opted out or progressed: no follow-up
            if first.channel is Channel.EMAIL and self.is_suppressed(
                Channel.EMAIL, first.recipient
            ):
                continue
            company = self.session.get(Company, first.company_id)
            proposal = self.session.get(Proposal, first.proposal_id) if first.proposal_id else None
            if company is None or proposal is None:
                continue
            subject, body = follow_up(company.name, proposal.language)
            self.session.add(
                OutreachEvent(
                    company_id=first.company_id,
                    lead_id=first.lead_id,
                    proposal_id=first.proposal_id,
                    channel=first.channel,
                    kind=OutreachKind.FOLLOW_UP,
                    status=OutreachStatus.QUEUED
                    if first.channel is Channel.EMAIL
                    else OutreachStatus.TASK,
                    recipient=first.recipient,
                    idempotency_key=key,
                    subject=subject,
                    body=body,
                    created_by=str(ACTOR),
                )
            )
            created += 1
        self.session.flush()
        return created

    def enqueue_email_jobs(self, now: datetime) -> int:
        """Queue sender jobs only when sending is possible (drafting works without it)."""
        if not (self.app.outbound_sending_enabled and self.app.email_enabled):
            return 0
        if self.channel_state().paused:
            return 0
        jobs = JobRepository(self.session)
        created = 0
        for event_id in self.session.scalars(
            select(OutreachEvent.id)
            .where(
                OutreachEvent.channel == Channel.EMAIL,
                OutreachEvent.status == OutreachStatus.QUEUED,
            )
            .order_by(OutreachEvent.created_at)
            .limit(50)
        ):
            _, new = jobs.enqueue(
                job_type=EMAIL_JOB,
                agent_module=AgentModule.CONVERSATION.value,
                payload={"event_id": str(event_id)},
                # Hourly slot: a job cancelled by STOP is re-queued later.
                idempotency_key=f"email:{event_id}:{now:%Y%m%d%H}",
            )
            created += int(new)
        return created

    def _pick_channel(self, company_id: uuid.UUID) -> tuple[Channel | None, str | None]:
        email = self._best_email(company_id) if self.app.email_enabled else None
        if email is not None:
            return Channel.EMAIL, email
        contacts = list(
            self.session.scalars(select(Contact).where(Contact.company_id == company_id))
        )
        telegram = next((c.value for c in contacts if c.kind is ContactKind.TELEGRAM), None)
        if telegram is not None:
            return Channel.TELEGRAM, telegram
        phone = next((c.value for c in contacts if c.kind is ContactKind.PHONE), None)
        if phone is not None:
            return Channel.PHONE, phone
        return None, None

    def _best_email(self, company_id: uuid.UUID) -> str | None:
        for contact in self.session.scalars(
            select(Contact).where(
                Contact.company_id == company_id,
                Contact.kind == ContactKind.EMAIL,
                Contact.is_role_address.is_(True),  # public business addresses only
            )
        ):
            if not self.is_suppressed(Channel.EMAIL, contact.value):
                return contact.value
        return None

    def _event_exists(self, key: str) -> bool:
        return (
            self.session.scalars(
                select(OutreachEvent.id).where(OutreachEvent.idempotency_key == key)
            ).first()
            is not None
        )

    # -- email sending ---------------------------------------------------------------

    def prepare_email(
        self, event_id: uuid.UUID, now: datetime | None = None
    ) -> PreparedEmail | None:
        """All checks, then SENDING (committed by the caller before SMTP is called)."""
        now = now or utcnow()
        event = self.session.get(OutreachEvent, event_id, with_for_update=True)
        if event is None or event.channel is not Channel.EMAIL:
            return None
        if event.status is OutreachStatus.SENDING:
            # A previous run died after handing it to SMTP: never risk a second send.
            event.status = OutreachStatus.UNKNOWN
            event.error = "run interrupted during send; check the mailbox"
            return None
        if event.status is not OutreachStatus.QUEUED:
            return None
        lead = self.session.get(Lead, event.lead_id) if event.lead_id else None
        if self.is_suppressed(Channel.EMAIL, event.recipient) or (
            lead is not None and lead.stage is LeadStage.DO_NOT_CONTACT
        ):
            event.status, event.error = OutreachStatus.BLOCKED, "suppressed"
            return None
        if not self.app.email_enabled:
            event.status, event.error = OutreachStatus.BLOCKED, "SMTP is not configured"
            return None
        state = self.channel_state()
        if state.paused:
            raise Deferred(f"email paused: {state.reason}", now + timedelta(hours=1))
        try:
            ControlGate(
                self.session, outbound_sending_enabled=self.app.outbound_sending_enabled
            ).ensure_may_send(AgentModule.CONVERSATION)
        except SendingBlockedError as exc:
            raise Deferred(str(exc), now + timedelta(minutes=15)) from None
        cap = self.email_cap(now)
        if self.emails_sent_today(now) >= cap:
            tomorrow = start_of_local_day(now, self.app.default_timezone) + timedelta(days=1)
            jitter = timedelta(minutes=random.randint(5, 90))  # noqa: S311 - spacing only
            raise Deferred(f"daily cap {cap} reached", tomorrow + jitter)
        last = self.session.scalar(
            select(func.max(OutreachEvent.sent_at)).where(OutreachEvent.channel == Channel.EMAIL)
        )
        gap = timedelta(minutes=self.cfg.email_min_gap_minutes)
        if last is not None and now - last < gap:
            jitter = timedelta(seconds=random.randint(0, 120))  # noqa: S311 - spacing, not security
            raise Deferred("spacing", last + gap + jitter)
        event.status = OutreachStatus.SENDING
        token = unsubscribe_token(
            self.app.app_secret_key.get_secret_value() or "dev", event.recipient
        )
        url = f"{self.app.app_base_url.rstrip('/')}/u/{token}"
        proposal = self.session.get(Proposal, event.proposal_id) if event.proposal_id else None
        language = proposal.language if proposal else Language.UZ
        body = event.body + email_footer(language, url)
        message = build_message(
            OutgoingEmail(
                to=event.recipient,
                subject=event.subject or "ITcoDe.Uz",
                body=body,
                unsubscribe_url=url,
            ),
            sender=self.app.smtp_from,
        )
        event.message_id = str(message["Message-ID"])[:255]
        self.session.flush()
        return PreparedEmail(event.id, message)

    def mark_sent(self, event_id: uuid.UUID, now: datetime | None = None) -> None:
        event = self.session.get(OutreachEvent, event_id)
        if event is None:
            return
        event.status, event.sent_at, event.error = OutreachStatus.SENT, now or utcnow(), None
        if event.kind is OutreachKind.FIRST:
            self._lead_to(event.company_id, LeadStage.CONTACTED, "offer emailed")

    def mark_failed(self, event_id: uuid.UUID, error: str, *, permanent: bool) -> None:
        event = self.session.get(OutreachEvent, event_id)
        if event is None:
            return
        event.error = error[:200]
        # Permanent refusal = bounce; temporary errors go back to the queue (nothing sent).
        event.status = OutreachStatus.BOUNCED if permanent else OutreachStatus.QUEUED
        if permanent:
            self.check_auto_pause()

    def email_cap(self, now: datetime) -> int:
        first = self.session.scalar(
            select(func.min(OutreachEvent.sent_at)).where(OutreachEvent.channel == Channel.EMAIL)
        )
        policy = CapPolicy(
            self.cfg.email_daily_cap, self.cfg.email_warmup_start, self.cfg.email_warmup_step
        )
        local_today = start_of_local_day(now, self.app.default_timezone)
        first_day = start_of_local_day(first, self.app.default_timezone).date() if first else None
        return email_cap_today(policy, first_day, local_today.date())

    def emails_sent_today(self, now: datetime) -> int:
        start = start_of_local_day(now, self.app.default_timezone)
        return (
            self.session.scalar(
                select(func.count())
                .select_from(OutreachEvent)
                .where(
                    OutreachEvent.channel == Channel.EMAIL,
                    OutreachEvent.sent_at >= start,
                    OutreachEvent.status.in_(
                        [OutreachStatus.SENT, OutreachStatus.BOUNCED, OutreachStatus.UNKNOWN]
                    ),
                )
            )
            or 0
        )

    # -- pause -------------------------------------------------------------------------

    def channel_state(self) -> ChannelState:
        state = self.session.get(ChannelState, Channel.EMAIL.value)
        if state is None:
            state = ChannelState(
                channel=Channel.EMAIL.value, paused=False, complaints=0, changed_by=str(ACTOR)
            )
            self.session.add(state)
            self.session.flush()
        return state

    def check_auto_pause(self, now: datetime | None = None) -> str | None:
        now = now or utcnow()
        state = self.channel_state()
        since = now - BOUNCE_WINDOW
        counts = dict(
            self.session.execute(
                select(OutreachEvent.status, func.count())
                .where(OutreachEvent.channel == Channel.EMAIL, OutreachEvent.updated_at >= since)
                .group_by(OutreachEvent.status)
            )
            .tuples()
            .all()
        )
        bounced = counts.get(OutreachStatus.BOUNCED, 0)
        sent = counts.get(OutreachStatus.SENT, 0) + bounced
        reason = should_pause(sent=sent, bounced=bounced, complaints=state.complaints)
        if reason and not state.paused:
            state.paused, state.reason = True, reason
            state.changed_at, state.changed_by = now, str(ACTOR)
            return reason
        return None

    def resume_email(self, actor: Actor) -> None:
        state = self.channel_state()
        state.paused, state.reason, state.complaints = False, None, 0
        state.changed_at, state.changed_by = utcnow(), str(actor)
        AuditLogRepository(self.session).add(
            actor=actor, action="outreach.email_resume", entity_type="channel"
        )

    # -- inbox ---------------------------------------------------------------------------

    def process_mail(self, mail: InboundMail) -> list[str]:
        """Replies, STOP, bounces, complaints → state changes + owner notes."""
        notes: list[str] = []
        state = self.channel_state()
        if mail.is_complaint:
            state.complaints += 1
            reason = self.check_auto_pause()
            notes.append(f"⛔ Spam shikoyati keldi — email to'xtatildi: {reason or 'paused'}")
            return notes
        if mail.is_bounce:
            for address in mail.failed_recipients:
                event = self._latest_event(address)
                if event is not None and event.status is OutreachStatus.SENT:
                    event.status, event.error = OutreachStatus.BOUNCED, "bounce"
            if reason := self.check_auto_pause():
                notes.append(f"⛔ Email avtomatik to'xtatildi: {reason}")
            return notes
        event = self._latest_event(mail.sender)
        if event is None:
            return notes  # not one of our recipients: the owner reads it in the mailbox
        words = strip_quoted(mail.text)
        company = self.session.get(Company, event.company_id)
        name = company.name if company else mail.sender
        if classify(words) is Intent.OPT_OUT or classify(mail.subject) is Intent.OPT_OUT:
            self.unsubscribe(mail.sender, reason="replied STOP / opt-out by email")
            notes.append(f"🚫 {name} email orqali rad etdi — boshqa yozilmaydi.")
            return notes
        event.replied_at = utcnow()
        self._lead_to(event.company_id, LeadStage.RESPONDED, "client replied by email")
        notes.append(f"📩 {name} javob yozdi ({mail.sender}):\n{words[:500]}")
        return notes

    def _latest_event(self, address: str) -> OutreachEvent | None:
        return self.session.scalars(
            select(OutreachEvent)
            .where(
                OutreachEvent.channel == Channel.EMAIL,
                OutreachEvent.recipient == address.lower(),
                OutreachEvent.sent_at.is_not(None),
            )
            .order_by(OutreachEvent.sent_at.desc())
        ).first()

    # -- owner tasks (Telegram / phone) ----------------------------------------------------

    def mark_task_done(
        self, event_id: uuid.UUID, actor: Actor, now: datetime | None = None
    ) -> None:
        now = now or utcnow()
        event = self._task(event_id)
        if event.channel is Channel.TELEGRAM:
            start = start_of_local_day(now, self.app.default_timezone)
            done_today = (
                self.session.scalar(
                    select(func.count())
                    .select_from(OutreachEvent)
                    .where(
                        OutreachEvent.channel == Channel.TELEGRAM,
                        OutreachEvent.status == OutreachStatus.DONE,
                        OutreachEvent.sent_at >= start,
                    )
                )
                or 0
            )
            if done_today >= self.cfg.telegram_daily_cap:
                raise OutreachError(f"Telegram daily cap {self.cfg.telegram_daily_cap} reached")
        event.status, event.sent_at = OutreachStatus.DONE, now
        if event.kind is OutreachKind.FIRST:
            self._lead_to(
                event.company_id, LeadStage.CONTACTED, f"owner contacted via {event.channel.value}"
            )
        AuditLogRepository(self.session).add(
            actor=actor,
            action="outreach.task_done",
            entity_type="outreach_event",
            entity_id=event.id,
            details={"channel": event.channel.value, "kind": event.kind.value},
        )

    def skip_task(self, event_id: uuid.UUID, actor: Actor) -> None:
        event = self._task(event_id)
        event.status = OutreachStatus.SKIPPED
        AuditLogRepository(self.session).add(
            actor=actor,
            action="outreach.task_skipped",
            entity_type="outreach_event",
            entity_id=event.id,
        )

    def mark_replied(self, event_id: uuid.UUID, actor: Actor) -> None:
        """Owner: the company answered (Telegram/phone/email read by hand)."""
        event = self.session.get(OutreachEvent, event_id)
        if event is None:
            raise NotFoundError("outreach event not found")
        event.replied_at = utcnow()
        self._lead_to(event.company_id, LeadStage.RESPONDED, "owner: client replied")
        AuditLogRepository(self.session).add(
            actor=actor, action="outreach.replied", entity_type="outreach_event", entity_id=event.id
        )

    def _task(self, event_id: uuid.UUID) -> OutreachEvent:
        event = self.session.get(OutreachEvent, event_id, with_for_update=True)
        if event is None:
            raise NotFoundError("outreach event not found")
        if event.status is not OutreachStatus.TASK:
            raise OutreachError(f"task is {event.status.value}")
        lead = self.session.get(Lead, event.lead_id) if event.lead_id else None
        if lead is not None and lead.stage is LeadStage.DO_NOT_CONTACT:
            event.status = OutreachStatus.BLOCKED
            raise OutreachError("the company opted out")
        return event

    # -- stats ---------------------------------------------------------------------------

    def today(self, now: datetime | None = None) -> TodayStats:
        now = now or utcnow()
        start = start_of_local_day(now, self.app.default_timezone)
        telegram_done = (
            self.session.scalar(
                select(func.count())
                .select_from(OutreachEvent)
                .where(
                    OutreachEvent.channel == Channel.TELEGRAM,
                    OutreachEvent.status == OutreachStatus.DONE,
                    OutreachEvent.sent_at >= start,
                )
            )
            or 0
        )
        since = now - BOUNCE_WINDOW
        counts = dict(
            self.session.execute(
                select(OutreachEvent.status, func.count())
                .where(OutreachEvent.channel == Channel.EMAIL, OutreachEvent.updated_at >= since)
                .group_by(OutreachEvent.status)
            )
            .tuples()
            .all()
        )
        state = self.channel_state()
        bounced = counts.get(OutreachStatus.BOUNCED, 0)
        return TodayStats(
            email_sent=self.emails_sent_today(now),
            email_cap=self.email_cap(now),
            telegram_done=telegram_done,
            telegram_cap=self.cfg.telegram_daily_cap,
            bounced_30d=bounced,
            sent_30d=counts.get(OutreachStatus.SENT, 0) + bounced,
            paused=state.paused,
            pause_reason=state.reason,
        )

    # -- helpers -------------------------------------------------------------------------

    def _lead_to(self, company_id: uuid.UUID, target: LeadStage, reason: str) -> None:
        lead = self.session.scalars(select(Lead).where(Lead.company_id == company_id)).first()
        if lead is None or lead.stage is target:
            return
        if can_transition(lead.stage, target, resume_stage=lead.resume_stage):
            self.workflow.transition_lead(lead.id, target, ACTOR, reason)
