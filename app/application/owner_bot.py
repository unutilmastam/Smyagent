"""Owner control bot: authorization, idempotency and commands (CLAUDE.md §13.1)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.automation import CB_JOB_RETRY, JobAdminService, cron_view
from app.application.controls import AgentControlService, describe_change
from app.application.conversations import (
    CB_DISCARD,
    CB_ORDER_ACCEPT,
    CB_ORDER_QUESTION,
    CB_ORDER_REJECT,
    CB_SEND,
    ConversationService,
)
from app.application.proposals import (
    CALLBACK_APPROVE,
    CALLBACK_REJECT,
    ProposalService,
)
from app.domain.actors import Actor
from app.domain.agents import GLOBAL_CONTROL, AgentModule, ControlState
from app.domain.automation import CronHealth, error_category
from app.domain.errors import DomainError
from app.domain.jobs import JobStatus
from app.domain.telegram import is_owner_message, parse_command
from app.infrastructure.database.models import Company, Job, Lead
from app.infrastructure.repositories.controls import AgentControlRepository
from app.infrastructure.repositories.inbound import InboundEventRepository
from app.infrastructure.repositories.workflow import AuditLogRepository
from app.infrastructure.telegram.schemas import TgCallbackQuery, TgUpdate

logger = logging.getLogger("app.owner_bot")

CHANNEL = "telegram:owner_bot"
_ORDER_DECISIONS = {
    CB_ORDER_ACCEPT: "accepted",
    CB_ORDER_QUESTION: "question",
    CB_ORDER_REJECT: "rejected",
}
_CALLBACK_ACTIONS = {
    CALLBACK_APPROVE,
    CALLBACK_REJECT,
    CB_SEND,
    CB_DISCARD,
    CB_JOB_RETRY,
    *_ORDER_DECISIONS,
}

HELP_TEXT = (
    "SMY Agent — boshqaruv boti\n\n"
    "/status — tizim holati\n"
    "/stop_all — ⛔ hammasini to'xtatish\n"
    "/resume_all — hammasini faollashtirish\n"
    "/agent <nom> on|pause|off — bitta agent\n"
    "/proposals — tasdiqlashni kutayotgan takliflar\n"
    "/approve <id> — taklifni tasdiqlash\n"
    "/reject <id> [sabab] — taklifni rad etish\n"
    "/jobs — fon ishlari: cron, navbat, oxirgi xatolar\n"
    "/retry <id> — xato bergan vazifani qayta urinish\n"
    "/help — buyruqlar ro'yxati\n\n"
    "Agent nomlari: " + ", ".join(m.value for m in AgentModule)
)

AGENT_ACTIONS = {
    "on": ControlState.ACTIVE,
    "pause": ControlState.PAUSED,
    "off": ControlState.STOPPED,
}

_CRON_ICONS = {
    CronHealth.OK: "✅ ishlayapti",
    CronHealth.LATE: "🛑 to'xtab qolgan",
    CronHealth.NEVER: "⏰ sozlanmagan",
}

STATE_ICONS = {ControlState.ACTIVE: "🟢", ControlState.PAUSED: "🟡", ControlState.STOPPED: "🔴"}


@dataclass(frozen=True)
class BotReply:
    chat_id: int
    text: str
    # Set for inline-button presses: the reply is shown as a callback answer.
    callback_query_id: str | None = None


class OwnerBotService:
    def __init__(
        self,
        session: Session,
        *,
        admin_ids: list[int],
        outbound_sending_enabled: bool = False,
        email_enabled: bool = False,
    ) -> None:
        self.session = session
        self.admin_ids = admin_ids
        self.outbound_sending_enabled = outbound_sending_enabled
        self.email_enabled = email_enabled

    def handle(self, update: TgUpdate) -> BotReply | None:
        """Process one update. Returns the reply for the owner, or None (ignored)."""
        if not InboundEventRepository(self.session).register(CHANNEL, str(update.update_id)):
            logger.info("owner_bot.duplicate_update", extra={"update_id": update.update_id})
            return None
        if update.callback_query is not None:
            return self._callback(update.callback_query)
        message = update.message
        if message is None:
            return None
        sender = message.from_
        if not is_owner_message(
            sender_id=sender.id if sender else None,
            sender_is_bot=sender.is_bot if sender else False,
            chat_type=message.chat.type,
            admin_ids=self.admin_ids,
        ):
            # Silently ignored: no reply reveals that the bot is a control bot.
            logger.warning(
                "owner_bot.unauthorized",
                extra={"sender_id": sender.id if sender else None, "chat_type": message.chat.type},
            )
            AuditLogRepository(self.session).add(
                actor=Actor.system("owner_bot"),
                action="telegram.unauthorized",
                details={"sender_id": sender.id if sender else None},
            )
            return None

        command = parse_command(message.text)
        chat_id = message.chat.id
        if command is None or command.name in ("start", "help"):
            return BotReply(chat_id, HELP_TEXT)
        if command.name == "status":
            return BotReply(chat_id, self._status_text())
        actor = Actor.user(f"tg-{sender.id}") if sender else Actor.system("owner_bot")
        if command.name == "stop_all":
            return BotReply(chat_id, self._set(GLOBAL_CONTROL, ControlState.STOPPED, actor))
        if command.name == "resume_all":
            return BotReply(chat_id, self._set(GLOBAL_CONTROL, ControlState.ACTIVE, actor))
        if command.name == "agent":
            parts = command.args.split()
            modules = {m.value for m in AgentModule}
            if len(parts) != 2 or parts[0] not in modules or parts[1] not in AGENT_ACTIONS:
                return BotReply(chat_id, "Foydalanish: /agent <nom> on|pause|off\n\n" + HELP_TEXT)
            return BotReply(chat_id, self._set(parts[0], AGENT_ACTIONS[parts[1]], actor))
        if command.name == "proposals":
            return BotReply(chat_id, self._pending_text())
        if command.name in ("approve", "reject"):
            prefix, _, reason = command.args.partition(" ")
            proposal = ProposalService(self.session).find_by_prefix(prefix)
            if proposal is None:
                return BotReply(chat_id, "Taklif topilmadi. /proposals ro'yxatidagi ID ni yozing.")
            approve = command.name == "approve"
            return BotReply(chat_id, self._decide(proposal.id, approve, actor, reason))
        if command.name == "jobs":
            return BotReply(chat_id, self._jobs_text())
        if command.name == "retry":
            try:
                job = JobAdminService(self.session).find_by_prefix(command.args)
            except DomainError:
                return BotReply(chat_id, "Vazifa topilmadi. /jobs ro'yxatidagi ID ni yozing.")
            return BotReply(chat_id, self._retry(job.id, actor))
        return BotReply(chat_id, f"Noma'lum buyruq: /{command.name}\n\n{HELP_TEXT}")

    def _callback(self, query: TgCallbackQuery) -> BotReply | None:
        chat = query.message.chat if query.message else None
        if not is_owner_message(
            sender_id=query.from_.id,
            sender_is_bot=query.from_.is_bot,
            chat_type=chat.type if chat else None,
            admin_ids=self.admin_ids,
        ):
            logger.warning("owner_bot.unauthorized_callback", extra={"sender_id": query.from_.id})
            AuditLogRepository(self.session).add(
                actor=Actor.system("owner_bot"),
                action="telegram.unauthorized",
                details={"sender_id": query.from_.id, "callback": True},
            )
            return None
        assert chat is not None
        action, _, raw_id = (query.data or "").partition(":")
        try:
            target_id = uuid.UUID(raw_id)
        except ValueError:
            target_id = None
        actor = Actor.user(f"tg-{query.from_.id}")
        if target_id is None or action not in _CALLBACK_ACTIONS:
            return BotReply(chat.id, "Noma'lum tugma.", callback_query_id=query.id)
        if action in (CALLBACK_APPROVE, CALLBACK_REJECT):
            text = self._decide(target_id, action == CALLBACK_APPROVE, actor, "Telegram")
        elif action == CB_JOB_RETRY:
            text = self._retry(target_id, actor)
        else:
            text = self._conversation_action(action, target_id, actor)
        return BotReply(chat.id, text, callback_query_id=query.id)

    def _conversation_action(self, action: str, target_id: uuid.UUID, actor: Actor) -> str:
        service = ConversationService(
            self.session, outbound_sending_enabled=self.outbound_sending_enabled
        )
        try:
            with self.session.begin_nested():
                if action == CB_SEND:
                    service.approve_message(target_id, actor)
                    return "✅ Javob yuborish navbatiga qo'yildi."
                if action == CB_DISCARD:
                    service.discard_message(target_id, actor)
                    return "❌ Javob bekor qilindi."
                decision = _ORDER_DECISIONS[action]
                service.decide_order(target_id, actor, decision)
        except DomainError as exc:
            return f"⚠️ Bajarilmadi: {exc}"
        return {
            "accepted": "✅ Buyurtma qabul qilindi (lid: WON). Narx va muddatni mijozga yozing.",
            "question": "❓ Suhbat sizga o'tdi — mijozga o'zingiz yozing.",
            "rejected": "❌ Buyurtma rad etildi (lid: LOST).",
        }[decision]

    def _decide(self, proposal_id: uuid.UUID, approve: bool, actor: Actor, reason: str) -> str:
        service = ProposalService(self.session)
        try:
            # A savepoint keeps the update registration even if the decision fails.
            with self.session.begin_nested():
                if approve:
                    service.approve(proposal_id, actor)
                else:
                    service.reject(proposal_id, actor, reason or "Telegram")
        except DomainError as exc:  # state, not-found or invalid lead transition
            return f"⚠️ Bajarilmadi: {exc}"
        short = str(proposal_id)[:8]
        if approve:
            return f"✅ Taklif {short} tasdiqlandi.\n{self._delivery_note()}"
        return f"❌ Taklif {short} rad etildi; kompaniyaga murojaat qilinmaydi."

    def _retry(self, job_id: uuid.UUID, actor: Actor) -> str:
        try:
            with self.session.begin_nested():
                job = JobAdminService(self.session).retry(job_id, actor)
        except DomainError as exc:
            return f"⚠️ Bajarilmadi: {exc}"
        return f"🔁 Vazifa {str(job.id)[:8]} ({job.job_type}) navbatga qaytdi — keyingi cron'da."

    def _jobs_text(self) -> str:
        service = JobAdminService(self.session)
        cron = cron_view(self.session)
        if cron.health is CronHealth.NEVER:
            cron_line = "⏰ Cron hali ishga tushmagan — cPanel → Cron Jobs ni sozlang."
        elif cron.health is CronHealth.LATE:
            cron_line = f"🛑 Cron {cron.minutes_ago} daqiqadan beri ishlamayapti!"
        else:
            cron_line = f"✅ Cron ishlayapti (oxirgi: {cron.minutes_ago} daqiqa oldin)"
        counts = service.counts()
        lines = [
            "🧾 Fon ishlari",
            cron_line,
            "",
            f"Navbatda: {counts.get(JobStatus.QUEUED, 0)}"
            f" · Ishlayapti: {counts.get(JobStatus.RUNNING, 0)}"
            f" · Xato: {counts.get(JobStatus.FAILED, 0)}",
        ]
        failures = service.recent_failures()
        if failures:
            lines += ["", "Oxirgi xatolar:"]
            for job in failures:
                lines.append(
                    f"{str(job.id)[:8]} · {job.job_type} · {error_category(job.last_error)}"
                )
            lines.append("\n/retry <id> — qayta urinish")
        return "\n".join(lines)

    def _delivery_note(self) -> str:
        """How the approved offer reaches the company (honest about what is switched on)."""
        if self.email_enabled and self.outbound_sending_enabled:
            return "📧 Kompaniyada ochiq email bo'lsa — navbatga qo'yildi (kunlik limit ichida)."
        if self.email_enabled:
            return (
                "📧 Email sozlangan, lekin yuborish o'chiq (OUTBOUND_SENDING_ENABLED=false). "
                "Telegram/telefon bo'lsa — 📤 Yuborish sahifasida vazifa."
            )
        return (
            "📧 Email hali ulanmagan (docs/email-uz.md). Hozircha Telegram/telefon bo'lsa — "
            "📤 Yuborish sahifasida siz uchun vazifa bo'ladi."
        )

    def _pending_text(self) -> str:
        rows = ProposalService(self.session).pending()
        if not rows:
            return "Tasdiqlashni kutayotgan taklif yo'q."
        lines = ["📝 Takliflar:"]
        for proposal, company in rows:
            mark = "⛔ tahrir kerak" if proposal.status.value == "NEEDS_EDIT" else "⏳"
            lines.append(f"{str(proposal.id)[:8]} · {company.name} · {mark}")
        lines.append("\n/approve <id> yoki /reject <id> [sabab]")
        return "\n".join(lines)

    def _set(self, key: str, state: ControlState, actor: Actor) -> str:
        change = AgentControlService(self.session).set_state(key, state, actor, "owner bot")
        return describe_change(change)

    def _status_text(self) -> str:
        count = self.session.scalar
        companies = count(select(func.count()).select_from(Company)) or 0
        leads = count(select(func.count()).select_from(Lead)) or 0
        jobs = dict(
            self.session.execute(select(Job.status, func.count()).group_by(Job.status))
            .tuples()
            .all()
        )
        states = AgentControlRepository(self.session).states()
        global_state = states.get(GLOBAL_CONTROL, ControlState.STOPPED)
        cron = cron_view(self.session)
        lines = [
            "📊 SMY Agent holati",
            f"Umumiy: {STATE_ICONS[global_state]} {global_state.value}",
            f"Cron: {_CRON_ICONS[cron.health]}"
            + (f" ({cron.minutes_ago} daq. oldin)" if cron.minutes_ago is not None else ""),
            "",
            f"Kompaniyalar: {companies}",
            f"Lidlar: {leads}",
            f"Navbatda: {jobs.get(JobStatus.QUEUED, 0)}"
            f" · Ishlayapti: {jobs.get(JobStatus.RUNNING, 0)}"
            f" · Xato: {jobs.get(JobStatus.FAILED, 0)}",
            "",
            "Agentlar:",
        ]
        for module in AgentModule:
            state = states.get(module.value, ControlState.STOPPED)
            lines.append(f"{STATE_ICONS[state]} {module.value}: {state.value}")
        return "\n".join(lines)
