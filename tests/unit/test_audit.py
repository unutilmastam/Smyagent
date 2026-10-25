from __future__ import annotations

from app.domain.audit import AuditInput, Kind, Severity, audit, parse_page

GOOD = """<!doctype html><html lang="uz"><head>
<title>Denov Mebel — mebel do'koni</title>
<meta name="description" content="Denovdagi mebel do'koni">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="WordPress 6.4">
<script>var tracking = "+998 90 000 00 00";</script>
</head><body><h1>Denov Mebel</h1>
<img src="a.jpg" alt="Divan"><a href="tel:+998901112233">Qo'ng'iroq</a>
<a href="https://t.me/denov_mebel">Telegram</a><form></form>
<footer>© 2026 Denov Mebel</footer></body></html>"""

BAD = """<html><body><p>Xush kelibsiz</p><img src="x.png"><img src="y.png">
<p>&copy; 2017</p></body></html>"""


def _input(
    html: str, url: str = "https://denovmebel.uz/", ms: int = 400, status: int = 200
) -> AuditInput:
    return AuditInput(
        requested_url=url,
        final_url=url,
        status_code=status,
        elapsed_ms=ms,
        size_bytes=len(html),
        html=html,
        current_year=2026,
    )


def test_good_site_scores_high_with_evidence() -> None:
    result = audit(_input(GOOD))
    checks = {c.key: c for c in result.checks}
    assert result.score >= 90
    assert checks["mobile_viewport"].severity is Severity.OK
    assert checks["visible_contacts"].evidence.startswith("+998901112233")
    assert checks["site_builder"].evidence == "WordPress 6.4"
    assert result.findings == []
    assert "tracking" not in result.text_excerpt  # scripts are not page text


def test_weak_site_yields_verified_facts_and_labeled_inferences() -> None:
    result = audit(_input(BAD, url="http://old.uz/", ms=4200))
    keys = {f.key: f for f in result.findings}
    assert {
        "no_https",
        "not_mobile_friendly",
        "weak_seo_metadata",
        "slow_response",
        "no_visible_contacts",
    } <= set(keys)
    assert all(keys[k].kind is Kind.FACT for k in ("no_https", "not_mobile_friendly"))
    assert (
        keys["possibly_outdated"].kind is Kind.INFERENCE
        and keys["possibly_outdated"].confidence < 1
    )
    assert keys["no_online_inquiry"].kind is Kind.INFERENCE
    assert result.score < 50


def test_http_error_page_is_a_fact() -> None:
    result = audit(_input("<html></html>", status=500))
    assert any(f.key == "http_error" and "500" in f.statement for f in result.findings)


def test_malformed_html_does_not_crash() -> None:
    facts = parse_page("<html><title>Half <b>open <<<>>> </ti")
    assert facts.title.startswith("Half")
    assert audit(_input("\x00\x01<<<")).score >= 0
