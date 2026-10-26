"""Read replies, bounces and spam complaints from the sender mailbox over IMAP."""

from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Protocol

from app.core.config import Settings

MAX_MESSAGES = 50
MAX_TEXT = 4000
_BOUNCE_SENDER = re.compile(r"mailer-daemon|postmaster", re.I)
_FINAL_RECIPIENT = re.compile(
    r"^(?:Final|Original)-Recipient:\s*(?:rfc822;)?\s*(\S+@\S+)", re.I | re.M
)
_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass(frozen=True)
class InboundMail:
    sender: str  # lowercased address
    subject: str
    text: str
    is_bounce: bool = False
    is_complaint: bool = False
    failed_recipients: list[str] = field(default_factory=list)


def _plain_text(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain",))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, ValueError):
        return ""
    return str(content)[:MAX_TEXT]


def parse_mail(raw: bytes) -> InboundMail:
    message = message_from_bytes(raw, policy=policy.default)
    assert isinstance(message, EmailMessage)
    sender = parseaddr(str(message.get("From", "")))[1].lower()
    subject = str(message.get("Subject", ""))[:300]
    report_type = ""
    if message.get_content_type() == "multipart/report":
        report_type = str(message.get_param("report-type") or "").lower()
    if report_type == "feedback-report":  # ARF spam complaint (RFC 5965)
        return InboundMail(sender, subject, "", is_complaint=True)
    if report_type == "delivery-status" or _BOUNCE_SENDER.search(sender):
        whole = raw.decode("utf-8", errors="replace")
        failed = [m.lower() for m in _FINAL_RECIPIENT.findall(whole)]
        header = message.get("X-Failed-Recipients")
        if header:
            failed += [a.lower() for a in _ADDRESS.findall(str(header))]
        return InboundMail(
            sender, subject, "", is_bounce=True, failed_recipients=list(dict.fromkeys(failed))
        )
    return InboundMail(sender, subject, _plain_text(message))


class Inbox(Protocol):
    def fetch_unseen(self) -> list[InboundMail]: ...


class ImapInbox:
    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.host, self.port, self.username, self._password = host, port, username, password

    def fetch_unseen(self) -> list[InboundMail]:
        """Read up to MAX_MESSAGES unseen messages and mark them seen."""
        mails: list[InboundMail] = []
        with imaplib.IMAP4_SSL(
            self.host, self.port, ssl_context=ssl.create_default_context(), timeout=20
        ) as client:
            client.login(self.username, self._password)
            client.select("INBOX")
            _, data = client.search(None, "UNSEEN")
            ids = (data[0] or b"").split()[:MAX_MESSAGES]
            for msg_id in ids:
                _, parts = client.fetch(msg_id.decode(), "(RFC822)")
                for part in parts:
                    if isinstance(part, tuple) and isinstance(part[1], bytes):
                        mails.append(parse_mail(part[1]))
                client.store(msg_id.decode(), "+FLAGS", "\\Seen")
        return mails


def build_inbox(settings: Settings) -> Inbox | None:
    if not settings.imap_host or not settings.imap_username:
        return None
    return ImapInbox(
        settings.imap_host,
        settings.imap_port,
        settings.imap_username,
        settings.imap_password.get_secret_value(),
    )


def check_login(settings: Settings) -> int:
    """IMAP login test for the setup guide: number of unseen messages, nothing marked seen."""
    with imaplib.IMAP4_SSL(
        settings.imap_host, settings.imap_port, ssl_context=ssl.create_default_context(), timeout=20
    ) as client:
        client.login(settings.imap_username, settings.imap_password.get_secret_value())
        client.select("INBOX", readonly=True)
        _, data = client.search(None, "UNSEEN")
        return len((data[0] or b"").split())
