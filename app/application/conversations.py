"""Mustafo client conversations and order intake (CLAUDE.md §5, §8.2, §13.2, M8).

Inbound flow per message: store (idempotent) → suppression check → classify →
opt-out / handoff / bot question / price / Order Brief interview → one reply.
A reply is either sent at once (reply mode `auto_safe`, gate-clean, kill switch
open) or stored as a DRAFT the owner approves. Confirmed briefs move the lead to
ORDER_CONFIRMED and notify the owner exactly once.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.application.controls import Button, ControlGate
from app.application.workflow import NotFoundError, WorkflowService
from app.domain.actors import Actor
from app.domain.agent_settings import ConversationSettings, ReplyMode
from app.domain.agents import AgentModule, SendingBlockedError
from app.domain.conversation import (
    Brief,
    BriefField,
    BriefStatus,
    ConversationState,
    Intent,
    MessageDirection,
    MessageStatus,
    classify,
    detect_language,
    detect_services,
    question,
    reply_is_safe,
    summary,
    switch_language,
    text,
    with_disclosure,
)
from app.domain.errors import DomainError
from app.domain.leads import LeadStage, can_transition
from app.infrastructure.database.models import (
    Company,
    Conversation,
    ConversationMessage,
    Lead,
    OrderBrief,
    SuppressionRecord,
)
from app.infrastructure.database.types import utcnow
from app.infrastructure.repositories.agent_settings import AgentSettingsRepository
from app.infrastructure.repositories.companies import CompanyRepository, NewCompany
from app.infrastructure.repositories.jobs import JobRepository
from app.infrastructure.repositories.workflow import AuditLogRepository

CHANNEL = "telegram"
SEND_JOB = "outbound.telegram_reply"  # "outbound." → cancelled by the global STOP
ACTOR = Actor.agent(AgentModule.CONVERSATION.value)
MAX_INBOUND = 4000
MAX_OWNER_REPLY = 4000

# Owner-bot callback data (≤ 64 bytes).
CB_SEND, CB_DISCARD = "ms", "mx"
CB_ORDER_ACCEPT, CB_ORDER_QUESTION, CB_ORDER_REJECT = "oa", "oq", "or"


class ConversationError(DomainError):
    """The conversation/message/brief is not in a state that allows this action."""


@dataclass
class InboundOutcome:
    conversation_id: uuid.UUID
    # Text to deliver right now in the webhook response (auto_safe mode only).
    send_now: str | None = None
    send_now_message_id: uuid.UUID | None = None
    # Owner notifications to deliver after commit.
    notify: list[tuple[str, list[Button]]] = field(default_factory=list)


class ConversationService:
    def __init__(
        self,
        session: Session,
        *,
        outbound_sending_enabled: bool,
        base_url: str = "",
    ) -> None:
        self.session = session
        self.outbound_sending_enabled = outbound_sending_enabled
        self.base_url = base_url.rstrip("/") if base_url.startswith("https://") else ""
        self.workflow = WorkflowService(session)
        repo = AgentSettingsRepository(session)
        self.settings: ConversationSettings = repo.get(AgentModule.CONVERSATION)
        self.gate_words: tuple[str, ...] = tuple(repo.get(AgentModule.QUALITY_GATE).extra_blocked)

    # -- inbound ---------------------------------------------------------------

    def handle_inbound(
        self,
        *,
        chat_id: int,
        message_id: int,
        body: str,
        display_name: str | None = None,
    ) -> InboundOutcome | None:
        """Process one client message. None when it is a duplicate."""
        body = body.strip()[:MAX_INBOUND]
        conversation = self._conversation(chat_id, body, display_name)
        external_id = f"{chat_id}:{message_id}"
        duplicate = self.session.scalars(
            select(ConversationMessage.id).where(
                ConversationMessage.channel == CHANNEL,
                ConversationMessage.external_message_id == external_id,
            )
        ).first()
        if duplicate is not None:
            return None
        intent = classify(body)
        inbound = ConversationMessage(
            conversation_id=conversation.id,
            channel=CHANNEL,
            direction=MessageDirection.IN,
            status=MessageStatus.RECEIVED,
            text=body,
            intent=intent.value,
            external_message_id=external_id,
            created_by=f"client:{chat_id}",
        )
        self.session.add(inbound)
        conversation.last_message_at = utcnow()
        self.session.flush()
        outcome = InboundOutcome(conversation.id)

        if conversation.state is ConversationState.OPTED_OUT or self.is_suppressed(chat_id):
            return outcome  # never reply again; stored for the owner only
        if intent is Intent.OPT_OUT:
            self._opt_out(conversation, inbound, outcome)
            return outcome
        if conversation.state is ConversationState.HANDOFF:
            outcome.notify.append(self._owner_message_note(conversation, body))
            return outcome
        if intent is Intent.SPAM:
            return outcome

        lang = conversation.language
        if intent is Intent.HUMAN_REQUEST:
            conversation.state = ConversationState.HANDOFF
            outcome.notify.append(
                (
                    f"🙋 Mijoz siz bilan gaplashmoqchi: {self._client_label(conversation)}\n"
                    f"Xabar: {body[:300]}{self._link(conversation)}",
                    [],
                )
            )
            self._reply(
                conversation, text("handoff", lang, contact=self.settings.owner_contact), outcome
            )
            return outcome
        if intent is Intent.BOT_QUESTION:
            self._reply(conversation, text("bot_answer", lang), outcome)
            return outcome
        if conversation.state is ConversationState.ORDER_CONFIRMED:
            outcome.notify.append(self._owner_message_note(conversation, body))
            self._reply(conversation, text("after_order", lang), outcome)
            return outcome

        brief = self._active_brief(conversation)
        if conversation.state is ConversationState.AWAITING_CONFIRMATION and brief is not None:
            self._confirmation_step(conversation, brief, inbound, intent, body, outcome)
            return outcome
        if conversation.state is ConversationState.BRIEF and brief is not None:
            self._interview_step(conversation, brief, intent, body, outcome)
            return outcome

        # OPEN: start the interview on interest or a price question, else welcome.
        if intent in (Intent.INTEREST, Intent.PRICE_REQUEST):
            self._start_brief(conversation, intent, body, outcome)
        else:
            first = conversation.disclosed_at is None and not self._has_pending_disclosure(
                conversation
            )
            self._reply(conversation, text("welcome" if first else "fallback", lang), outcome)
        return outcome

    def _conversation(self, chat_id: int, body: str, display_name: str | None) -> Conversation:
        conversation = self.session.scalars(
            select(Conversation).where(
                Conversation.channel == CHANNEL, Conversation.external_chat_id == str(chat_id)
            )
        ).first()
        if conversation is None:
            conversation = Conversation(
                channel=CHANNEL,
                external_chat_id=str(chat_id),
                display_name=(display_name or "")[:120] or None,
                language=detect_language(body),
                state=ConversationState.OPEN,
            )
            self.session.add(conversation)
            self.session.flush()
        elif len(body) >= 12:
            # A clearly different language from the client switches the reply language.
            conversation.language = switch_language(conversation.language, body)
        return conversation

    # -- interview -------------------------------------------------------------

    def _start_brief(
        self, conversation: Conversation, intent: Intent, body: str, outcome: InboundOutcome
    ) -> None:
        lang = conversation.language
        brief = Brief()
        if intent is Intent.INTEREST and detect_services(body):
            brief.record(body)  # the first message already says what to build
        row = OrderBrief(
            conversation_id=conversation.id,
            status=BriefStatus.COLLECTING,
            answers=brief.answers,
            services=brief.services,
        )
        self.session.add(row)
        self._ensure_lead(conversation)
        row.lead_id = conversation.lead_id
        conversation.state = ConversationState.BRIEF
        parts = []
        if intent is Intent.PRICE_REQUEST:
            parts.append(text("price_answer", lang))
        parts.append(text("brief_start", lang))
        next_field = brief.next_field()
        assert next_field is not None
        parts.append(question(next_field, lang))
        self._reply(conversation, "\n\n".join(parts), outcome)

    def _interview_step(
        self,
        conversation: Conversation,
        row: OrderBrief,
        intent: Intent,
        body: str,
        outcome: InboundOutcome,
    ) -> None:
        lang = conversation.language
        brief = _load(row)
        current = brief.next_field()
        if intent is Intent.PRICE_REQUEST and current is not BriefField.CONTACT:
            reply = text("price_answer", lang)
            if current is not None:
                reply += "\n\n" + question(current, lang)
            self._reply(conversation, reply, outcome)
            return
        brief.record(body)
        _store(row, brief)
        following = brief.next_field()
        if following is not None:
            self._reply(conversation, question(following, lang), outcome)
            return
        row.status = BriefStatus.AWAITING_CONFIRMATION
        conversation.state = ConversationState.AWAITING_CONFIRMATION
        self._reply(conversation, summary(brief, lang), outcome)

    def _confirmation_step(
        self,
        conversation: Conversation,
        row: OrderBrief,
        inbound: ConversationMessage,
        intent: Intent,
        body: str,
        outcome: InboundOutcome,
    ) -> None:
        lang = conversation.language
        brief = _load(row)
        if intent is Intent.CONFIRM:
            self._confirm(conversation, row, inbound, outcome)
            return
        if intent is Intent.DENY and len(body) <= 12:
            self._reply(conversation, text("correct_what", lang), outcome)
            return
        # Anything else is a correction: keep it as a note and show the brief again.
        notes = brief.answers.get("notes", "")
        brief.answers["notes"] = (notes + "\n" + body).strip()[:1000]
        _store(row, brief)
        self._reply(conversation, summary(brief, lang), outcome)

    def _confirm(
        self,
        conversation: Conversation,
        row: OrderBrief,
        inbound: ConversationMessage,
        outcome: InboundOutcome,
    ) -> None:
        """Explicit client confirmation → ORDER_CONFIRMED, owner notified once (§8.2)."""
        now = utcnow()
        row.status = BriefStatus.CONFIRMED
        row.confirmed_at = now
        row.confirmation_message_id = inbound.id
        conversation.state = ConversationState.ORDER_CONFIRMED
        self._ensure_lead(conversation)
        row.lead_id = conversation.lead_id
        self._rename_company(conversation, row)
        self._lead_to(conversation, LeadStage.ORDER_CONFIRMED, "client confirmed the Order Brief")
        if row.notified_at is None:
            row.notified_at = now
            outcome.notify.append(self.order_notification(conversation, row))
        self._reply(conversation, text("confirmed", conversation.language), outcome)

    # -- opt-out ---------------------------------------------------------------

    def _opt_out(
        self, conversation: Conversation, inbound: ConversationMessage, outcome: InboundOutcome
    ) -> None:
        conversation.state = ConversationState.OPTED_OUT
        self.suppress(
            str(conversation.external_chat_id),
            company_id=conversation.company_id,
            reason="client opted out in chat",
            source_message_id=inbound.id,
        )
        # Nothing waiting for this client may go out any more.
        self.session.execute(
            update(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation.id,
                ConversationMessage.status.in_([MessageStatus.DRAFT, MessageStatus.APPROVED]),
            )
            .values(status=MessageStatus.BLOCKED, note="client opted out")
            .execution_options(synchronize_session=False)
        )
        brief = self._active_brief(conversation)
        if brief is not None:
            brief.status = BriefStatus.CANCELLED
        if conversation.lead_id is not None:
            self._lead_to(conversation, LeadStage.DO_NOT_CONTACT, "client opted out")
        outcome.notify.append(
            (f"🚫 Mijoz rad etdi (boshqa yozilmaydi): {self._client_label(conversation)}", [])
        )

    def suppress(
        self,
        value: str,
        *,
        company_id: uuid.UUID | None,
        reason: str,
        source_message_id: uuid.UUID | None = None,
    ) -> None:
        if self.is_suppressed(value):
            return
        self.session.add(
            SuppressionRecord(
                channel=CHANNEL,
                value=value,
                company_id=company_id,
                reason=reason[:200],
                source_message_id=source_message_id,
            )
        )
        self.session.flush()

    def is_suppressed(self, chat_id: int | str) -> bool:
        return (
            self.session.scalars(
                select(SuppressionRecord.id).where(
                    SuppressionRecord.channel == CHANNEL, SuppressionRecord.value == str(chat_id)
                )
            ).first()
            is not None
        )

    # -- replies ---------------------------------------------------------------

    def _has_pending_disclosure(self, conversation: Conversation) -> bool:
        return (
            self.session.scalars(
                select(ConversationMessage.id).where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.has_disclosure.is_(True),
                    ConversationMessage.status.in_(
                        [MessageStatus.DRAFT, MessageStatus.APPROVED, MessageStatus.SENT]
                    ),
                )
            ).first()
            is not None
        )

    def _reply(self, conversation: Conversation, body: str, outcome: InboundOutcome) -> None:
        lang = conversation.language
        disclose = conversation.disclosed_at is None and not self._has_pending_disclosure(
            conversation
        )
        if disclose:
            body = with_disclosure(body, lang)
        message = ConversationMessage(
            conversation_id=conversation.id,
            channel=CHANNEL,
            direction=MessageDirection.OUT,
            status=MessageStatus.DRAFT,
            text=body,
            has_disclosure=disclose,
            created_by=str(ACTOR),
        )
        self.session.add(message)
        self.session.flush()
        safe = reply_is_safe(body, lang, extra_blocked=self.gate_words)
        blocked_reason = self._send_block_reason()
        if self.settings.reply_mode is ReplyMode.AUTO_SAFE and safe and blocked_reason is None:
            message.status = MessageStatus.SENT
            message.sent_at = utcnow()
            if disclose:
                conversation.disclosed_at = message.sent_at
            outcome.send_now = body
            outcome.send_now_message_id = message.id
            return
        if not safe:
            message.note = "quality gate: price/commitment/blocked word"
        elif blocked_reason is not None and self.settings.reply_mode is ReplyMode.AUTO_SAFE:
            message.note = blocked_reason[:200]
        outcome.notify.append(self.draft_notification(conversation, message))

    def _send_block_reason(self) -> str | None:
        gate = ControlGate(self.session, outbound_sending_enabled=self.outbound_sending_enabled)
        try:
            gate.ensure_may_send(AgentModule.CONVERSATION)
        except SendingBlockedError as exc:
            return str(exc)
        return None

    # -- owner actions -----------------------------------------------------------

    def approve_message(self, message_id: uuid.UUID, actor: Actor) -> ConversationMessage:
        message = self._message(message_id)
        if message.direction is not MessageDirection.OUT or message.status not in (
            MessageStatus.DRAFT,
            MessageStatus.BLOCKED,
        ):
            raise ConversationError(f"message is {message.status.value}")
        conversation = message.conversation
        if conversation.state is ConversationState.OPTED_OUT or self.is_suppressed(
            conversation.external_chat_id
        ):
            raise ConversationError("the client opted out; nothing can be sent")
        message.status = MessageStatus.APPROVED
        message.note = None
        self._enqueue_send(message)
        AuditLogRepository(self.session).add(
            actor=actor,
            action="conversation.approve_reply",
            entity_type="conversation",
            entity_id=conversation.id,
            details={"message": str(message.id)},
        )
        return message

    def discard_message(self, message_id: uuid.UUID, actor: Actor) -> ConversationMessage:
        message = self._message(message_id)
        if message.direction is not MessageDirection.OUT or message.status not in (
            MessageStatus.DRAFT,
            MessageStatus.BLOCKED,
        ):
            raise ConversationError(f"message is {message.status.value}")
        message.status = MessageStatus.REJECTED
        AuditLogRepository(self.session).add(
            actor=actor,
            action="conversation.discard_reply",
            entity_type="conversation",
            entity_id=message.conversation_id,
            details={"message": str(message.id)},
        )
        return message

    def owner_reply(
        self, conversation_id: uuid.UUID, actor: Actor, body: str
    ) -> ConversationMessage:
        """The owner writes personally (may name a price); Mustafo steps back (HANDOFF)."""
        conversation = self._get(conversation_id)
        body = body.strip()
        if not body or len(body) > MAX_OWNER_REPLY:
            raise DomainError(f"text must be 1-{MAX_OWNER_REPLY} characters")
        if conversation.state is ConversationState.OPTED_OUT or self.is_suppressed(
            conversation.external_chat_id
        ):
            raise ConversationError("the client opted out; nothing can be sent")
        message = ConversationMessage(
            conversation_id=conversation.id,
            channel=CHANNEL,
            direction=MessageDirection.OUT,
            status=MessageStatus.APPROVED,
            text=body,
            created_by=str(actor),
        )
        self.session.add(message)
        self.session.flush()
        if conversation.state is not ConversationState.ORDER_CONFIRMED:
            conversation.state = ConversationState.HANDOFF
        self._enqueue_send(message)
        AuditLogRepository(self.session).add(
            actor=actor,
            action="conversation.owner_reply",
            entity_type="conversation",
            entity_id=conversation.id,
        )
        return message

    def resume_bot(self, conversation_id: uuid.UUID, actor: Actor) -> Conversation:
        conversation = self._get(conversation_id)
        if conversation.state is not ConversationState.HANDOFF:
            raise ConversationError(f"conversation is {conversation.state.value}")
        brief = self._active_brief(conversation)
        if brief is None:
            conversation.state = ConversationState.OPEN
        elif brief.status is BriefStatus.AWAITING_CONFIRMATION:
            conversation.state = ConversationState.AWAITING_CONFIRMATION
        else:
            conversation.state = ConversationState.BRIEF
        AuditLogRepository(self.session).add(
            actor=actor,
            action="conversation.resume_bot",
            entity_type="conversation",
            entity_id=conversation.id,
        )
        return conversation

    def decide_order(self, brief_id: uuid.UUID, actor: Actor, decision: str) -> OrderBrief:
        """Owner on a confirmed order: accepted (WON) / question (talk) / rejected (LOST)."""
        row = self.session.get(OrderBrief, brief_id, with_for_update=True)
        if row is None:
            raise NotFoundError("order not found")
        if row.status is not BriefStatus.CONFIRMED:
            raise ConversationError("the client has not confirmed this order")
        if row.owner_decision is not None:
            raise ConversationError(f"already decided: {row.owner_decision}")
        conversation = self._get(row.conversation_id)
        if decision == "accepted":
            self._lead_to(conversation, LeadStage.WON, "owner accepted the order")
        elif decision == "question":
            self._lead_to(conversation, LeadStage.RESPONDED, "owner has questions")
            conversation.state = ConversationState.HANDOFF
        elif decision == "rejected":
            self._lead_to(conversation, LeadStage.LOST, "owner declined the order")
        else:
            raise DomainError("unknown decision")
        row.owner_decision = decision
        AuditLogRepository(self.session).add(
            actor=actor,
            action=f"order.{decision}",
            entity_type="order_brief",
            entity_id=row.id,
        )
        return row

    # -- notifications -----------------------------------------------------------

    def order_notification(
        self, conversation: Conversation, row: OrderBrief
    ) -> tuple[str, list[Button]]:
        services = ", ".join(row.services) or row.answers.get("service", "—")
        lines = [
            f"✅ Yangi buyurtma — {self._client_label(conversation)} {services} yasatishga rozi",
            "",
        ]
        for f in BriefField:
            lines.append(f"• {f.value}: {row.answers.get(f.value, '—')}")
        if row.answers.get("notes"):
            lines.append(f"• notes: {row.answers['notes']}")
        if row.budget_note:
            lines.append(f"• budjet (mijoz so'zi, faqat siz uchun): {row.budget_note}")
        lines.append(self._link(conversation).strip())
        buttons = [
            Button("✅ Qabul qilaman", data=f"{CB_ORDER_ACCEPT}:{row.id}"),
            Button("❓ Savol beraman", data=f"{CB_ORDER_QUESTION}:{row.id}"),
            Button("❌ Rad etaman", data=f"{CB_ORDER_REJECT}:{row.id}"),
        ]
        return "\n".join(line for line in lines if line is not None), buttons

    def draft_notification(
        self, conversation: Conversation, message: ConversationMessage
    ) -> tuple[str, list[Button]]:
        last_in = (
            self.session.scalars(
                select(ConversationMessage.text)
                .where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.direction == MessageDirection.IN,
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(1)
            ).first()
            or ""
        )
        note = f"\n⚠️ {message.note}" if message.note else ""
        body = (
            f"💬 {self._client_label(conversation)}: {last_in[:300]}\n\n"
            f"Mustafo javobi (tasdiqlang):\n{message.text[:1500]}{note}"
            f"{self._link(conversation)}"
        )
        return body, [
            Button("✅ Yuborish", data=f"{CB_SEND}:{message.id}"),
            Button("❌ Bekor", data=f"{CB_DISCARD}:{message.id}"),
        ]

    def _owner_message_note(
        self, conversation: Conversation, body: str
    ) -> tuple[str, list[Button]]:
        return (
            f"💬 {self._client_label(conversation)}: {body[:500]}{self._link(conversation)}",
            [],
        )

    def _client_label(self, conversation: Conversation) -> str:
        if conversation.company_id:
            company = self.session.get(Company, conversation.company_id)
            if company is not None and not company.name.startswith("Telegram:"):
                return company.name
        return conversation.display_name or f"Telegram {conversation.external_chat_id}"

    def _link(self, conversation: Conversation) -> str:
        return f"\n{self.base_url}/conversations/{conversation.id}" if self.base_url else ""

    # -- helpers -----------------------------------------------------------------

    def _enqueue_send(self, message: ConversationMessage) -> None:
        JobRepository(self.session).enqueue(
            job_type=SEND_JOB,
            agent_module=AgentModule.CONVERSATION.value,
            payload={"message_id": str(message.id)},
            idempotency_key=f"send:{message.id}:{utcnow():%Y%m%d%H%M%S%f}",
        )

    def _ensure_lead(self, conversation: Conversation) -> None:
        """Inbound clients get a company + lead at RESPONDED (CLAUDE.md §9.2)."""
        if conversation.lead_id is not None:
            return
        if conversation.company_id is None:
            name = f"Telegram: {conversation.display_name or conversation.external_chat_id}"
            company = CompanyRepository(self.session).add(
                NewCompany(
                    name=name[:200],
                    country="UZ",
                    source_type="telegram",
                    notes="Client wrote to the Mustafo bot first.",
                    allow_name_city_duplicate=True,
                )
            )
            conversation.company_id = company.id
        lead = self.session.scalars(
            select(Lead).where(Lead.company_id == conversation.company_id)
        ).first()
        if lead is None:
            lead = self.workflow.create_lead(conversation.company_id, ACTOR, inbound=True)
        conversation.lead_id = lead.id

    def _rename_company(self, conversation: Conversation, row: OrderBrief) -> None:
        contact = str(row.answers.get(BriefField.CONTACT.value, "")).strip()
        if conversation.company_id is None:
            return
        company = self.session.get(Company, conversation.company_id)
        if company is None or not company.name.startswith("Telegram:") or not contact:
            return
        first = contact.split(",")[0].strip()
        if 2 <= len(first) <= 120:
            company.name = first

    def _lead_to(self, conversation: Conversation, target: LeadStage, reason: str) -> None:
        if conversation.lead_id is None:
            return
        lead = self.session.get(Lead, conversation.lead_id)
        if lead is None or lead.stage is target:
            return
        if target is LeadStage.ORDER_CONFIRMED and not can_transition(lead.stage, target):
            # Outbound leads reach the order via RESPONDED (client wrote back).
            for step in (LeadStage.CONTACTED, LeadStage.RESPONDED):
                if can_transition(lead.stage, step):
                    self.workflow.transition_lead(lead.id, step, ACTOR, "client replied")
        if can_transition(lead.stage, target, resume_stage=lead.resume_stage):
            self.workflow.transition_lead(lead.id, target, ACTOR, reason)

    def _active_brief(self, conversation: Conversation) -> OrderBrief | None:
        return self.session.scalars(
            select(OrderBrief)
            .where(
                OrderBrief.conversation_id == conversation.id,
                OrderBrief.status.in_([BriefStatus.COLLECTING, BriefStatus.AWAITING_CONFIRMATION]),
            )
            .order_by(OrderBrief.created_at.desc())
        ).first()

    def _get(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = self.session.get(Conversation, conversation_id)
        if conversation is None:
            raise NotFoundError("conversation not found")
        return conversation

    def _message(self, message_id: uuid.UUID) -> ConversationMessage:
        message = self.session.get(ConversationMessage, message_id, with_for_update=True)
        if message is None:
            raise NotFoundError("message not found")
        return message


def _load(row: OrderBrief) -> Brief:
    return Brief(
        answers=dict(row.answers or {}),
        services=list(row.services or []),
        budget_note=row.budget_note,
    )


def _store(row: OrderBrief, brief: Brief) -> None:
    row.answers = dict(brief.answers)
    row.services = list(brief.services)
    row.budget_note = brief.budget_note


def project_spec(
    row: OrderBrief, conversation: Conversation, company_name: str, confirmed: datetime | None
) -> str:
    """Owner-side Markdown spec to paste into Claude Code (CLAUDE.md §8.2 step 6)."""
    a = row.answers
    labels: Sequence[tuple[str, str]] = (
        ("service", "What to build"),
        ("goal", "Business goal"),
        ("features", "Required features"),
        ("examples", "Examples / references"),
        ("content", "Content the client provides"),
        ("deadline", "Client's preferred timing (not a commitment)"),
        ("contact", "Contact"),
        ("notes", "Client corrections / notes"),
    )
    lines = [
        f"# Project spec — {company_name}",
        "",
        f"- Source: Telegram conversation {conversation.id} ({conversation.language.value})",
        f"- Client confirmed the brief: {confirmed:%Y-%m-%d %H:%M} UTC"
        if confirmed
        else "- Not confirmed",
        f"- Services: {', '.join(row.services) or '—'}",
        "",
    ]
    for key, label in labels:
        if a.get(key):
            lines += [f"## {label}", "", str(a[key]), ""]
    if row.budget_note:
        lines += ["## Budget (client's own words — internal)", "", row.budget_note, ""]
    lines += [
        "## Not agreed yet",
        "",
        "- Price, payment terms and the delivery date are agreed by the owner personally.",
        "",
    ]
    return "\n".join(lines)
