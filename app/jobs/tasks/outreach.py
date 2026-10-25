"""Outreach jobs: send one email (never twice) and read the mailbox (M9)."""

from __future__ import annotations

import uuid
from typing import Any

from app.application.outreach import EMAIL_JOB, INBOX_JOB, Deferred, OutreachService
from app.infrastructure.email.smtp import EmailSendError
from app.jobs.context import DeferTaskError, RetryableTaskError, TaskContext

__all__ = ["EMAIL_JOB", "INBOX_JOB", "run_inbox", "run_send_email"]


def run_send_email(ctx: TaskContext, payload: dict[str, Any]) -> str:
    event_id = uuid.UUID(str(payload["event_id"]))
    try:
        with ctx.database.transaction() as session:
            prepared = OutreachService(session, ctx.settings).prepare_email(event_id)
    except Deferred as exc:
        raise DeferTaskError(str(exc), exc.until) from None
    if prepared is None:
        return "skipped (not queued, suppressed or interrupted earlier)"
    # SENDING is committed: from here a crash leaves UNKNOWN, never a second send.
    sender = ctx.email_sender_factory(ctx.settings)
    if sender is None:
        with ctx.database.transaction() as session:
            OutreachService(session, ctx.settings).mark_failed(
                event_id, "SMTP is not configured", permanent=False
            )
        return "SMTP is not configured"
    try:
        sender.send(prepared.message)
    except EmailSendError as exc:
        with ctx.database.transaction() as session:
            service = OutreachService(session, ctx.settings)
            service.mark_failed(event_id, str(exc), permanent=exc.permanent)
            paused = service.channel_state().paused
        if paused:
            ctx.notifier.notify(
                "⛔ Email avtomatik to'xtatildi (bounce). /outreach sahifasini ko'ring."
            )
        if exc.permanent:
            return f"bounced: {exc}"
        raise RetryableTaskError(str(exc)) from None
    with ctx.database.transaction() as session:
        OutreachService(session, ctx.settings).mark_sent(event_id)
    return f"email yuborildi: {prepared.message['To']}"


def run_inbox(ctx: TaskContext, payload: dict[str, Any]) -> str:
    inbox = ctx.inbox_factory(ctx.settings)
    if inbox is None:
        return "IMAP is not configured"
    try:
        mails = inbox.fetch_unseen()
    except OSError as exc:
        raise RetryableTaskError(f"IMAP error ({type(exc).__name__})") from None
    notes: list[str] = []
    with ctx.database.transaction() as session:
        service = OutreachService(session, ctx.settings)
        for mail in mails:
            notes += service.process_mail(mail)
    for note in notes:
        ctx.notifier.notify(note)
    return f"{len(mails)} ta xat o'qildi, {len(notes)} ta muhim"
