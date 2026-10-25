"""Deterministic website audit (CLAUDE.md §8.1 Research & Audit). Pure: no I/O.

Not a security audit. Every check records what was observed (evidence) so findings are
verifiable facts; anything that is an interpretation is marked as an inference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser

SLOW_RESPONSE_MS = 3000
HEAVY_PAGE_BYTES = 3 * 1024 * 1024
TEXT_EXCERPT_CHARS = 8000

_PHONE = re.compile(r"(?:\+?998|\+7|\+996|\+992)[\s\-()]*\d[\d\s\-()]{7,14}\d")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
_YEAR = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", re.I)  # noqa: RUF001 - en dash in year ranges
_GENERATORS = ("wordpress", "tilda", "wix", "joomla", "bitrix", "opencart", "shopify", "drupal")


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    BAD = "bad"
    INFO = "info"


class Kind(str, Enum):
    FACT = "fact"  # directly observed
    INFERENCE = "inference"  # interpretation of facts; must be labeled as such


@dataclass(frozen=True)
class Check:
    key: str
    severity: Severity
    evidence: str


@dataclass(frozen=True)
class Finding:
    key: str
    kind: Kind
    statement: str
    confidence: float


@dataclass(frozen=True)
class AuditInput:
    requested_url: str
    final_url: str
    status_code: int
    elapsed_ms: int
    size_bytes: int
    html: str
    redirects: tuple[str, ...] = ()
    current_year: int = 2026


@dataclass
class PageFacts:
    title: str = ""
    description: str = ""
    viewport: str = ""
    lang: str = ""
    generator: str = ""
    og_title: bool = False
    h1_count: int = 0
    images: int = 0
    images_without_alt: int = 0
    forms: int = 0
    tel_links: list[str] = field(default_factory=list)
    mailto_links: list[str] = field(default_factory=list)
    telegram_links: list[str] = field(default_factory=list)
    instagram_links: list[str] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = PageFacts()
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        f = self.facts
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "html":
            f.lang = a.get("lang", "")[:16]
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "")
            if name == "description":
                f.description = content[:300]
            elif name == "viewport":
                f.viewport = content[:200]
            elif name == "generator":
                f.generator = content[:100]
            elif name == "og:title":
                f.og_title = True
        elif tag == "h1":
            f.h1_count += 1
        elif tag == "img":
            f.images += 1
            if not a.get("alt", "").strip():
                f.images_without_alt += 1
        elif tag == "form":
            f.forms += 1
        elif tag == "a":
            href = a.get("href", "").strip()
            low = href.lower()
            if low.startswith("tel:"):
                f.tel_links.append(href[4:][:40])
            elif low.startswith("mailto:"):
                f.mailto_links.append(href[7:].split("?")[0][:100])
            elif "t.me/" in low or "telegram.me/" in low:
                f.telegram_links.append(href[:200])
            elif "instagram.com/" in low:
                f.instagram_links.append(href[:200])

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.facts.title = (self.facts.title + data).strip()[:300]
        elif data.strip():
            self.facts.text_parts.append(data.strip())


def parse_page(html: str) -> PageFacts:
    parser = _Parser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: S110 - malformed HTML: keep what was parsed (pure layer, no logging)
        pass
    return parser.facts


@dataclass(frozen=True)
class AuditResult:
    checks: list[Check]
    findings: list[Finding]
    score: int  # 0-100, higher = healthier website (lower = bigger opportunity)
    title: str
    text_excerpt: str
    facts: PageFacts


_SEVERITY_VALUE = {Severity.OK: 1.0, Severity.INFO: 1.0, Severity.WARN: 0.5, Severity.BAD: 0.0}
# What matters most to a visitor and to the business counts double; minor signals half.
CHECK_WEIGHTS = {
    "https": 2.0,
    "status": 2.0,
    "mobile_viewport": 2.0,
    "visible_contacts": 2.0,
    "title": 1.0,
    "meta_description": 1.0,
    "response_time": 1.0,
    "page_size": 0.5,
    "image_alt_text": 0.5,
    "lang_attribute": 0.5,
    "copyright_year": 0.5,
}


def audit(page: AuditInput) -> AuditResult:
    facts = parse_page(page.html)
    text = facts.text
    checks: list[Check] = []
    findings: list[Finding] = []

    def fact(key: str, statement: str) -> None:
        findings.append(Finding(key, Kind.FACT, statement, 1.0))

    def inference(key: str, statement: str, confidence: float) -> None:
        findings.append(Finding(key, Kind.INFERENCE, statement, confidence))

    https = page.final_url.lower().startswith("https://")
    checks.append(Check("https", Severity.OK if https else Severity.BAD, page.final_url[:200]))
    if not https:
        fact("no_https", "The website is served without HTTPS.")

    ok_status = 200 <= page.status_code < 400
    checks.append(
        Check("status", Severity.OK if ok_status else Severity.BAD, str(page.status_code))
    )
    if not ok_status:
        fact("http_error", f"The homepage returned HTTP {page.status_code}.")

    checks.append(Check("title", Severity.OK if facts.title else Severity.WARN, facts.title or "—"))
    checks.append(
        Check(
            "meta_description",
            Severity.OK if facts.description else Severity.WARN,
            facts.description or "—",
        )
    )
    if not facts.title or not facts.description:
        fact("weak_seo_metadata", "The homepage lacks a title or meta description.")

    mobile = "width=device-width" in facts.viewport.replace(" ", "").lower()
    checks.append(
        Check("mobile_viewport", Severity.OK if mobile else Severity.BAD, facts.viewport or "—")
    )
    if not mobile:
        fact("not_mobile_friendly", "The homepage has no responsive (mobile) viewport tag.")

    slow = page.elapsed_ms > SLOW_RESPONSE_MS
    checks.append(
        Check("response_time", Severity.WARN if slow else Severity.OK, f"{page.elapsed_ms} ms")
    )
    if slow:
        fact("slow_response", f"The homepage took {page.elapsed_ms} ms to load (one measurement).")
    heavy = page.size_bytes > HEAVY_PAGE_BYTES
    checks.append(
        Check("page_size", Severity.WARN if heavy else Severity.OK, f"{page.size_bytes} bytes")
    )

    phones_in_text = _PHONE.findall(text)
    emails_in_text = _EMAIL.findall(text)
    has_contact = bool(facts.tel_links or facts.mailto_links or phones_in_text or emails_in_text)
    checks.append(
        Check(
            "visible_contacts",
            Severity.OK if has_contact else Severity.WARN,
            ", ".join((facts.tel_links + facts.mailto_links + phones_in_text + emails_in_text)[:4])
            or "—",
        )
    )
    if not has_contact:
        fact("no_visible_contacts", "No phone number or email address is visible on the homepage.")

    checks.append(
        Check(
            "telegram_link",
            Severity.OK if facts.telegram_links else Severity.INFO,
            facts.telegram_links[0] if facts.telegram_links else "—",
        )
    )
    checks.append(Check("contact_form", Severity.INFO, str(facts.forms)))
    if facts.forms == 0 and not facts.telegram_links:
        inference(
            "no_online_inquiry",
            "Visitors cannot send a request online (no form or Telegram link found).",
            0.6,
        )

    alt_ratio = (facts.images - facts.images_without_alt) / facts.images if facts.images else 1.0
    checks.append(
        Check(
            "image_alt_text",
            Severity.OK if alt_ratio >= 0.8 else Severity.WARN,
            f"{facts.images_without_alt}/{facts.images} without alt",
        )
    )
    checks.append(
        Check("lang_attribute", Severity.OK if facts.lang else Severity.WARN, facts.lang or "—")
    )

    years = [int(y) for y in _YEAR.findall(page.html)]
    if years:
        latest = max(years)
        old = latest < page.current_year - 1
        checks.append(Check("copyright_year", Severity.WARN if old else Severity.OK, str(latest)))
        if old:
            inference(
                "possibly_outdated",
                f"The footer copyright says {latest}; the site may not be maintained.",
                0.5,
            )

    generator = facts.generator.lower()
    builder = next((g for g in _GENERATORS if g in generator), None)
    if builder:
        checks.append(Check("site_builder", Severity.INFO, facts.generator))

    scored = [c for c in checks if c.key in CHECK_WEIGHTS]
    total = sum(CHECK_WEIGHTS[c.key] for c in scored)
    earned = sum(CHECK_WEIGHTS[c.key] * _SEVERITY_VALUE[c.severity] for c in scored)
    score = round(100 * earned / total) if total else 0
    return AuditResult(
        checks=checks,
        findings=findings,
        score=score,
        title=facts.title,
        text_excerpt=text[:TEXT_EXCERPT_CHARS],
        facts=facts,
    )


NO_WEBSITE_FINDING = Finding(
    "no_website", Kind.FACT, "No website was found for this business in its public listing.", 1.0
)


def unreachable_finding(category: str) -> Finding:
    return Finding(
        "website_unreachable",
        Kind.FACT,
        f"The listed website could not be opened ({category}).",
        1.0,
    )
