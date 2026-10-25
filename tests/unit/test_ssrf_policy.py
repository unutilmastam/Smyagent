from __future__ import annotations

import pytest

from app.infrastructure.http_fetcher.policy import BlockedURLError, is_blocked_ip, parse_target


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.5.4",
        "192.168.1.1",
        "0.0.0.0",
        "100.64.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "255.255.255.255",
        "198.18.0.1",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fd12:3456::1",
        "ff02::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",  # IPv4-mapped
        "2002:7f00:0001::1",  # 6to4 wrapping 127.0.0.1
        "64:ff9b::a00:1",  # NAT64 wrapping 10.0.0.1
        "not-an-ip",
        "fe80::1%eth0",
    ],
)
def test_blocked_addresses(ip: str) -> None:
    assert is_blocked_ip(ip)


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "185.8.212.10", "2606:4700:4700::1111"])
def test_public_addresses_allowed(ip: str) -> None:
    assert not is_blocked_ip(ip)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.uz/",
        "file:///etc/passwd",
        "gopher://x/",
        "javascript:alert(1)",
        "http://user:pw@example.uz/",
        "http:///nohost",
        "http://example.uz:22/",
        "http://example.uz:99999/",
    ],
)
def test_blocked_urls(url: str) -> None:
    with pytest.raises(BlockedURLError):
        parse_target(url)


def test_parse_target() -> None:
    t = parse_target("https://Example.UZ./about?x=1")
    assert (t.scheme, t.host, t.port, t.path) == ("https", "example.uz", 443, "/about?x=1")
    assert parse_target("http://example.uz").path == "/"
    assert parse_target("http://example.uz:8080/").port == 8080
