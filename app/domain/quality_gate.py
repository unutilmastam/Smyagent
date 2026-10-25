"""Quality Gate for client-facing text (CLAUDE.md §8.1, §5 rule 5, ADR-0008). Pure.

Rules, not an LLM: a client text must carry the AI disclosure and an opt-out, rest
on recorded evidence, be in the expected script, and contain **no price, amount,
discount, deadline, guarantee or contract term**. Marketing superlatives and
claims about other clients go to the owner for review.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from app.domain.persona import Language, is_cyrillic

MAX_LENGTH = 4000


class Verdict(str, Enum):
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class Severity(str, Enum):
    BLOCK = "block"  # -> rejected
    REVIEW = "review"  # -> needs_review


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    detail: str = ""


@dataclass(frozen=True)
class GateResult:
    verdict: Verdict
    issues: list[Issue] = field(default_factory=list)

    @property
    def codes(self) -> list[str]:
        return [i.code for i in self.issues]


_CURRENCY = (
    r"(?:so['ʻ‘’`]?m|sum|сум|сўм|usd|\$|€|eur|доллар\w*|dollar\w*|rubl\w*|руб\w*"
    r"|тенге|tenge|₸|kzt|kgs|tjs|uzs|сомони|somoni|сом)"
)
# Uzbek/Russian case endings after a currency word: "so'mdan", "долларов".
_SUFFIX = r"(?:dan|ga|gacha|lik|дан|га|гача|лик|ов|а|ы)?"
_MULTIPLIER = r"(?:k|ming|mln|million\w*|тыс\.?|тысяч\w*|млн|thousand)"
_PRICE_PATTERNS = [
    re.compile(rf"\d[\d\s.,']*\s*{_MULTIPLIER}?\s*{_CURRENCY}{_SUFFIX}(?![a-zа-яё])", re.I),
    re.compile(rf"(?<![a-zа-яё]){_CURRENCY}\s*\d", re.I),
    re.compile(r"(?:narx\w*|baho\w*|price\w*|cost\w*|цен\w*|стоимост\w*|стоит)\D{0,25}\d", re.I),
    re.compile(r"\d+\s*%"),
    re.compile(r"chegirma\w*|скидк\w*|discount\w*|aksiya|акци[яи]", re.I),
    re.compile(
        r"\bbepul\b|бесплатн\w*|\bfree of charge\b|\bfor free\b|\bfree (?:consult|trial|audit)",
        re.I,
    ),
]
_COMMITMENT_PATTERNS = [
    re.compile(r"kafolat\w*|гарант\w*|guarantee\w*", re.I),
    re.compile(r"shartnoma\w*|договор\w*|contract\w*", re.I),
    re.compile(r"oldindan to['ʻ‘’`]?lov|предоплат\w*|prepay\w*|to['ʻ‘’`]?lov shart", re.I),
    re.compile(r"\d+\s*(?:kun|hafta|oy)\s*(?:ichida|da)\b", re.I),
    re.compile(r"(?:в течение|за)\s*\d+\s*(?:дн|день|недел|месяц)", re.I),
    re.compile(r"within\s*\d+\s*(?:day|week|month)", re.I),
]
_CLAIM_PATTERNS = [
    re.compile(r"100\s*%|№\s*1|#\s*1\b", re.I),
    re.compile(r"eng yaxshi|самы[йе] лучш\w*|лучши[йе]\b|the best\b|best in\b", re.I),
    re.compile(r"mijozlarimiz|наши клиенты|our (?:clients|customers)", re.I),
    re.compile(r"marta oshadi|раз[а]? (?:больше|увелич\w*)|times more", re.I),
]
_DISCLOSURE = re.compile(r"(?:Mustafo|Мустафо).{0,120}\bAI\b|\bAI\b.{0,120}(?:Mustafo|Мустафо)")
_OPT_OUT = re.compile(
    r"kerak emas|yozmang|керак эмас|ёзманг|не пишите|отписаться|\bstop\b|unsubscribe", re.I
)
_LETTER = re.compile(r"[^\W\d_]")
_CYRILLIC = re.compile(r"[а-яёўқғҳ]", re.I)


def _matches(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        found += [m.group(0).strip() for m in pattern.finditer(text)]
    return found


def cyrillic_ratio(text: str) -> float:
    letters = _LETTER.findall(text)
    if not letters:
        return 0.0
    return sum(1 for ch in letters if _CYRILLIC.match(ch)) / len(letters)


def _word_patterns(words: Sequence[str]) -> list[re.Pattern[str]]:
    # Whole-word, case-insensitive; an owner word never becomes a regex.
    return [re.compile(rf"(?<!\w){re.escape(w)}(?!\w)", re.I) for w in words if w.strip()]


def review(
    text: str,
    *,
    language: Language,
    evidence_count: int,
    extra_blocked: Sequence[str] = (),
    extra_review: Sequence[str] = (),
) -> GateResult:
    """Check one client-facing text. Deterministic and reproducible.

    `extra_blocked` / `extra_review` are the owner's own words (agent settings); they
    add to the built-in rules and can never relax them.
    """
    issues: list[Issue] = []
    body = text.strip()
    if not body:
        return GateResult(Verdict.REJECTED, [Issue("empty", Severity.BLOCK)])

    for code, patterns, severity in (
        ("price", _PRICE_PATTERNS, Severity.BLOCK),
        ("commitment", _COMMITMENT_PATTERNS, Severity.BLOCK),
        ("unsupported_claim", _CLAIM_PATTERNS, Severity.REVIEW),
        ("owner_blocked_word", _word_patterns(extra_blocked), Severity.BLOCK),
        ("owner_review_word", _word_patterns(extra_review), Severity.REVIEW),
    ):
        hits = _matches(patterns, body)
        if hits:
            issues.append(Issue(code, severity, ", ".join(dict.fromkeys(hits))[:200]))

    if not _DISCLOSURE.search(body):
        issues.append(Issue("missing_disclosure", Severity.BLOCK))
    if not _OPT_OUT.search(body):
        issues.append(Issue("missing_opt_out", Severity.BLOCK))
    if evidence_count < 1:
        issues.append(Issue("no_evidence", Severity.BLOCK))

    ratio = cyrillic_ratio(body)
    if (is_cyrillic(language) and ratio < 0.5) or (not is_cyrillic(language) and ratio > 0.2):
        issues.append(Issue("language_mismatch", Severity.REVIEW, f"cyrillic {ratio:.0%}"))
    if len(body) > MAX_LENGTH:
        issues.append(Issue("too_long", Severity.REVIEW, str(len(body))))

    if any(i.severity is Severity.BLOCK for i in issues):
        verdict = Verdict.REJECTED
    elif issues:
        verdict = Verdict.NEEDS_REVIEW
    else:
        verdict = Verdict.APPROVED
    return GateResult(verdict, issues)
