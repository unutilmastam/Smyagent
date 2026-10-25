"""Owner control bot: authorization, idempotency and commands (CLAUDE.md §13.1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.actors import Actor
from app.domain.agents import GLOBAL_CONTROL, AgentModule, ControlState
from app.domain.jobs import JobStatus
from app.domain.telegram import is_owner_message, parse_command
from app.infrastructure.database.models import Company, Job, Lead
from app.infrastructure.repositories.controls import AgentControlRepository
from app.infrastructure.repositories.inbound import InboundEventRepository
from app.infrastructure.repositories.workflow import AuditLogRepository
from app.infrastructure.telegram.schemas import TgUpdate

logger = logging.getLogger("app.owner_bot")

CHANNEL = "telegram:owner_bot"

HELP_TEXT = (
    "SMY Agent — boshqaruv boti\n\n"
    "/status — tizim holati\n"
    "/help — buyruqlar ro'yxati\n\n"
    "Tez orada: lid ogohlantirishlari, takliflarni tasdiqlash, /stop_all."
)

STATE_ICONS = {ControlState.ACTIVE: "🟢", ControlState.PAUSED: "🟡", ControlState.STOPPED: "🔴"}


@dataclass(frozen=True)
class BotReply:
    chat_id: int
    text: str


class OwnerBotService:
    def __init__(self, session: Session, *, admin_ids: list[int]) -> None:
        self.session = session
        self.admin_ids = admin_ids

    def handle(self, update: TgUpdate) -> BotReply | None:
        """Process one update. Returns the reply for the owner, or None (ignored)."""
        if not InboundEventRepository(self.session).register(CHANNEL, str(update.update_id)):
            logger.info("owner_bot.duplicate_update", extra={"update_id": update.update_id})
            return None
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
        return BotReply(chat_id, f"Noma'lum buyruq: /{command.name}\n\n{HELP_TEXT}")

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
        lines = [
            "📊 SMY Agent holati",
            f"Umumiy: {STATE_ICONS[global_state]} {global_state.value}",
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
