"""Owner-bot rules: who may command the bot and how commands are parsed (CLAUDE.md §13.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_COMMAND = re.compile(r"^/([a-z0-9_]{1,32})(?:@[A-Za-z0-9_]{3,64})?(?:\s+(.*))?$", re.S | re.I)


@dataclass(frozen=True)
class Command:
    name: str
    args: str


def parse_command(text: str | None) -> Command | None:
    """`/status`, `/status@SmyAgentBot`, `/agent research pause` -> Command; else None."""
    if not text:
        return None
    match = _COMMAND.match(text.strip())
    if match is None:
        return None
    return Command(name=match.group(1).lower(), args=(match.group(2) or "").strip())


def is_owner_message(
    *, sender_id: int | None, sender_is_bot: bool, chat_type: str | None, admin_ids: list[int]
) -> bool:
    """Authorize by numeric Telegram user ID only — never by username — and private chats only."""
    return (
        sender_id is not None
        and not sender_is_bot
        and chat_type == "private"
        and sender_id in admin_ids
    )
