"""SSRF-safe fetcher: no network — a fake resolver and httpx.MockTransport."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.infrastructure.http_fetcher.fetcher import (
    MAX_BYTES,
    FetchError,
    RobotsDisallowedError,
    SafeFetcher,
)
from app.infrastructure.http_fetcher.policy import BlockedURLError

PUBLIC = "93.184.216.34"
DNS = {
    "example.uz": [PUBLIC],
    "shop.example.uz": [PUBLIC],
    "evil.example": ["10.0.0.5"],
    "rebind.example": [PUBLIC, "127.0.0.1"],
    "v6.example": ["::ffff:192.168.0.1"],
}
HTML = {"content-type": "text/html; charset=utf-8"}


def resolver(host: str, port: int) -> list[str]:
    if host not in DNS:
        raise OSError("NXDOMAIN")
    return DNS[host]


def make(handler: Callable[[httpx.Request], httpx.Response], **kw: object) -> SafeFetcher:
    return SafeFetcher(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
        min_interval=0,
        respect_robots=kw.pop("respect_robots", False),
        **kw,  # type: ignore[arg-type]
    )


def test_connects_to_validated_ip_with_host_and_sni() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers=HTML, text="<title>Salom</title>")

    result = make(handler).fetch("https://example.uz/about")
    req = seen[0]
    assert req.url.host == PUBLIC and req.url.path == "/about"
    assert req.headers["host"] == "example.uz"
    assert req.extensions["sni_hostname"] == "example.uz"
    assert "SMY-Agent" in req.headers["user-agent"]
    assert (
        result.status_code == 200 and "Salom" in result.text and result.final_url.endswith("/about")
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example/",
        "http://rebind.example/",
        "http://v6.example/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/latest/",
    ],
)
def test_private_targets_never_contacted(url: str) -> None:
    contacted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(str(request.url))
        return httpx.Response(200, headers=HTML, text="x")

    with pytest.raises(BlockedURLError):
        make(handler).fetch(url)
    assert contacted == []


@pytest.mark.parametrize(
    "location",
    [
        "http://127.0.0.1/admin",
        "http://evil.example/",
        "file:///etc/passwd",
        "http://example.uz:22/",
    ],
)
def test_redirect_to_forbidden_target_is_blocked(location: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": location})

    with pytest.raises(BlockedURLError):
        make(handler).fetch("https://example.uz/")


def test_relative_redirect_followed_and_revalidated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "https://shop.example.uz/uz/"})
        return httpx.Response(200, headers=HTML, text="<title>Shop</title>")

    result = make(handler).fetch("http://example.uz/")
    assert result.final_url == "https://shop.example.uz/uz/" and result.redirects == [
        "https://shop.example.uz/uz/"
    ]


def test_redirect_loop_is_cut() -> None:
    handler = lambda request: httpx.Response(302, headers={"location": "/again"})  # noqa: E731
    with pytest.raises(FetchError) as exc:
        make(handler).fetch("https://example.uz/")
    assert exc.value.category == "redirects"


def test_body_size_limit() -> None:
    big = b"x" * (MAX_BYTES + 10)
    with pytest.raises(FetchError) as exc:
        make(lambda r: httpx.Response(200, headers=HTML, content=big)).fetch("https://example.uz/")
    assert exc.value.category == "too_large"
    declared = {**HTML, "content-length": str(MAX_BYTES * 2)}
    with pytest.raises(FetchError):
        make(lambda r: httpx.Response(200, headers=declared, content=b"x")).fetch(
            "https://example.uz/"
        )


def test_content_type_allowlist() -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/zip"}, content=b"PK")

    with pytest.raises(FetchError) as exc:
        make(handler).fetch("https://example.uz/")
    assert exc.value.category == "content_type"


def test_dns_failure_and_timeout_categories() -> None:
    with pytest.raises(FetchError) as dns:
        make(lambda r: httpx.Response(200)).fetch("https://missing.example/")
    assert dns.value.category == "dns"

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(FetchError) as timeout:
        make(slow).fetch("https://example.uz/")
    assert timeout.value.category == "timeout"


def test_robots_txt_is_respected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, headers=HTML, text="x")

    with pytest.raises(RobotsDisallowedError):
        make(handler, respect_robots=True).fetch("https://example.uz/")


def test_missing_robots_txt_allows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers=HTML, text="ok")

    assert make(handler, respect_robots=True).fetch("https://example.uz/").status_code == 200


def test_per_host_throttle() -> None:
    sleeps: list[float] = []
    t = [100.0]
    fetcher = SafeFetcher(
        resolver=resolver,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, headers=HTML, text="x")),
        min_interval=2.0,
        respect_robots=False,
        clock=lambda: t[0],
        sleep=sleeps.append,
    )
    fetcher.fetch("https://example.uz/")
    fetcher.fetch("https://example.uz/other")
    assert sleeps and sleeps[0] == pytest.approx(2.0)


def test_error_pages_are_returned_for_auditing() -> None:
    result = make(lambda r: httpx.Response(503, text="down")).fetch("https://example.uz/")
    assert result.status_code == 503
