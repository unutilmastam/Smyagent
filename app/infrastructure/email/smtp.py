"""SMTP sender (cPanel mailbox). TLS is always verified; the password is never logged."""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Protocol

from app.core.config import Settings

TIMEOUT_SECONDS = 20


class EmailSendError(RuntimeError):
    def __init__(self, message: str, *, permanent: bool) -> None:
        super().__init__(message)
        self.permanent = permanent  # 5xx: the address is refused, do not retry


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    body: str
    unsubscribe_url: str


def build_message(mail: OutgoingEmail, *, sender: str) -> EmailMessage:
    """Plain-text email with honest headers and one-click unsubscribe (RFC 8058)."""
    _, address = parseaddr(sender)
    domain = address.rsplit("@", 1)[-1] if "@" in address else "localhost"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = mail.to
    message["Reply-To"] = sender
    message["Subject"] = mail.subject
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Message-ID"] = make_msgid(domain=domain)
    message["List-Unsubscribe"] = f"<{mail.unsubscribe_url}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message["Auto-Submitted"] = "no"  # a person-approved business message, not an autoreply
    message.set_content(mail.body, charset="utf-8")
    return message


class SmtpSender:
    def __init__(
        self, host: str, port: int, username: str, password: str, *, use_ssl: bool
    ) -> None:
        self.host, self.port = host, port
        self.username, self._password = username, password
        self.use_ssl = use_ssl

    def send(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        try:
            if self.use_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    self.host, self.port, timeout=TIMEOUT_SECONDS, context=context
                )
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=TIMEOUT_SECONDS)
                client.starttls(context=context)
            with client:
                if self.username:
                    client.login(self.username, self._password)
                refused = client.send_message(message)
        except smtplib.SMTPRecipientsRefused:
            raise EmailSendError("recipient refused", permanent=True) from None
        except smtplib.SMTPResponseException as exc:
            raise EmailSendError(
                f"SMTP {exc.smtp_code}", permanent=500 <= exc.smtp_code < 600
            ) from None
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailSendError(f"SMTP error ({type(exc).__name__})", permanent=False) from None
        if refused:
            raise EmailSendError("recipient refused", permanent=True)


def build_email_sender(settings: Settings) -> EmailSender | None:
    if not settings.email_enabled:
        return None
    return SmtpSender(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_username,
        settings.smtp_password.get_secret_value(),
        use_ssl=settings.smtp_use_ssl,
    )
