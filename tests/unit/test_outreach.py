"""Outreach rules, unsubscribe tokens, email building and inbound mail parsing (M9)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app.application.outreach import strip_quoted
from app.domain.conversation import Intent, classify
from app.domain.outreach import (
    CapPolicy,
    email_cap_today,
    email_footer,
    follow_up,
    follow_up_due,
    should_pause,
    unsubscribe_token,
    verify_unsubscribe_token,
)
from app.domain.persona import Language
from app.domain.quality_gate import Verdict, review
from app.infrastructure.email.inbox import parse_mail
from app.infrastructure.email.smtp import OutgoingEmail, build_message

POLICY = CapPolicy(daily_cap=30, warmup_start=10, warmup_step=5)


def test_warm_up_grows_to_the_cap() -> None:
    day0 = date(2026, 11, 1)
    assert email_cap_today(POLICY, None, day0) == 10
    assert email_cap_today(POLICY, day0, day0) == 10
    assert email_cap_today(POLICY, day0, day0 + timedelta(days=2)) == 20
    assert email_cap_today(POLICY, day0, day0 + timedelta(days=30)) == 30
    assert email_cap_today(CapPolicy(5, 10, 5), None, day0) == 5  # cap below warm-up start


def test_auto_pause_rules() -> None:
    assert should_pause(sent=0, bounced=0, complaints=1) is not None  # any complaint
    assert should_pause(sent=10, bounced=5, complaints=0) is None  # too few to judge
    assert should_pause(sent=40, bounced=2, complaints=0) is None  # exactly 5%
    assert "bounce rate" in (should_pause(sent=40, bounced=3, complaints=0) or "")


def test_follow_up_timing() -> None:
    sent = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert not follow_up_due(sent, sent + timedelta(days=4, hours=23), 5)
    assert follow_up_due(sent, sent + timedelta(days=5), 5)


def test_unsubscribe_tokens() -> None:
    token = unsubscribe_token("secret", "Info@Lazzat.uz")
    assert verify_unsubscribe_token("secret", token) == "info@lazzat.uz"
    assert verify_unsubscribe_token("other-secret", token) is None
    _, mac = token.split(".")
    forged = unsubscribe_token("guess", "boss@x.uz").split(".")[0] + "." + mac
    assert verify_unsubscribe_token("secret", forged) is None
    assert verify_unsubscribe_token("secret", "garbage") is None
    assert verify_unsubscribe_token("secret", "%%%.x") is None


@pytest.mark.parametrize("lang", [Language.UZ, Language.RU, Language.EN, Language.UZ_CYRL])
def test_follow_up_is_gate_clean_and_has_no_numbers(lang: Language) -> None:
    subject, body = follow_up("Lazzat", lang)
    result = review(
        body, language=lang if lang is not Language.UZ_CYRL else Language.UZ, evidence_count=None
    )
    assert result.verdict is Verdict.APPROVED, result.issues
    assert not re.search(r"\d", body) and "Lazzat" in subject


def test_every_email_has_an_unsubscribe_link_and_identity() -> None:
    footer = email_footer(Language.RU, "https://agent.itcode.uz/u/abc")
    assert "https://agent.itcode.uz/u/abc" in footer and "STOP" in footer
    assert "ITcoDe.Uz" in footer


def test_message_headers() -> None:
    message = build_message(
        OutgoingEmail("info@lazzat.uz", "Taklif", "Salom", "https://agent.itcode.uz/u/t"),
        sender="Mustafo — ITcoDe.Uz <agent@itcode.uz>",
    )
    assert message["List-Unsubscribe"] == "<https://agent.itcode.uz/u/t>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["Message-ID"].endswith("@itcode.uz>")
    assert message["Reply-To"] == message["From"]
    assert message.get_content().strip() == "Salom"


def test_strip_quoted_keeps_only_the_clients_words() -> None:
    reply = (
        "Rahmat, qiziq. Qachon gaplashamiz?\n\n"
        "On Mon, 2 Nov 2026 Mustafo <agent@itcode.uz> wrote:\n"
        '> Agar bu sizga kerak bo\'lmasa, "kerak emas" deb javob yozing\n'
    )
    words = strip_quoted(reply)
    assert words == "Rahmat, qiziq. Qachon gaplashamiz?"
    assert classify(words) is not Intent.OPT_OUT  # the quoted opt-out hint is ignored
    assert classify(strip_quoted("STOP\n\n> quoted")) is Intent.OPT_OUT


def _raw(headers: str, body: str) -> bytes:
    return (headers.strip() + "\n\n" + body).replace("\n", "\r\n").encode()


def test_parse_plain_reply() -> None:
    mail = parse_mail(
        _raw(
            "From: Ali <INFO@lazzat.uz>\nTo: agent@itcode.uz\nSubject: Re: Taklif\n"
            "Content-Type: text/plain; charset=utf-8",
            "Qiziq, batafsil yozing.",
        )
    )
    assert mail.sender == "info@lazzat.uz" and "Qiziq" in mail.text
    assert not mail.is_bounce and not mail.is_complaint


def test_parse_bounce_and_complaint() -> None:
    bounce = parse_mail(
        _raw(
            "From: Mail Delivery System <MAILER-DAEMON@mail.itcode.uz>\n"
            "Subject: Undelivered\nMIME-Version: 1.0\n"
            'Content-Type: multipart/report; report-type=delivery-status; boundary="b"',
            "--b\nContent-Type: text/plain\n\nfailed\n--b\n"
            "Content-Type: message/delivery-status\n\nReporting-MTA: dns; mail.itcode.uz\n\n"
            "Final-Recipient: rfc822; nobody@lazzat.uz\n"
            "Action: failed\nStatus: 5.1.1\n--b--",
        )
    )
    assert bounce.is_bounce and bounce.failed_recipients == ["nobody@lazzat.uz"]
    exim = parse_mail(
        _raw(
            "From: Mail Delivery System <Mailer-Daemon@host>\nX-Failed-Recipients: a@b.uz\n"
            "Subject: Mail delivery failed",
            "This message was created automatically.",
        )
    )
    assert exim.is_bounce and exim.failed_recipients == ["a@b.uz"]
    complaint = parse_mail(
        _raw(
            "From: feedback@mail.ru\nSubject: complaint\nMIME-Version: 1.0\n"
            'Content-Type: multipart/report; report-type=feedback-report; boundary="b"',
            "--b\nContent-Type: text/plain\n\nabuse\n--b--",
        )
    )
    assert complaint.is_complaint
