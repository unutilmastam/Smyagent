"""Minimal, tolerant models of Telegram updates (unknown fields ignored)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TgUser(_Model):
    id: int
    is_bot: bool = False
    username: str | None = None
    language_code: str | None = None


class TgChat(_Model):
    id: int
    type: str


class TgMessage(_Model):
    message_id: int
    chat: TgChat
    from_: TgUser | None = Field(default=None, alias="from")
    text: str | None = Field(default=None, max_length=4096)
    date: int | None = None


class TgCallbackQuery(_Model):
    """Inline button press (`callback_data` ≤ 64 bytes per Bot API)."""

    id: str
    from_: TgUser = Field(alias="from")
    message: TgMessage | None = None
    data: str | None = Field(default=None, max_length=64)


class TgUpdate(_Model):
    update_id: int
    message: TgMessage | None = None
    edited_message: TgMessage | None = None
    callback_query: TgCallbackQuery | None = None
