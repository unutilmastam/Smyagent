"""Which URLs and IP addresses the fetcher may contact. Pure functions, fully tested."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})

# Ranges that are_global misses or that we want to name explicitly.
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(net)
    for net in (
        "100.64.0.0/10",  # CGNAT
        "169.254.0.0/16",  # link-local incl. cloud metadata 169.254.169.254
        "192.0.0.0/24",
        "198.18.0.0/15",  # benchmarking
        "fd00:ec2::254/128",  # AWS IPv6 metadata
        "64:ff9b::/96",  # NAT64 (checked separately for the embedded IPv4)
    )
)


class BlockedURLError(ValueError):
    """The URL or the address it resolves to may not be fetched."""


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str
    port: int
    path: str  # path + query, never empty


def parse_target(url: str) -> Target:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise BlockedURLError("only http and https URLs are allowed")
    if parts.username or parts.password:
        raise BlockedURLError("credentials in URLs are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise BlockedURLError("URL has no host")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise BlockedURLError("invalid port") from exc
    if port not in ALLOWED_PORTS:
        raise BlockedURLError(f"port {port} is not allowed")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return Target(scheme=scheme, host=host, port=port, path=path)


def is_blocked_ip(value: str) -> bool:
    """True for anything that is not a public unicast address (IPv4 and IPv6)."""
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address):
        # Addresses that embed an IPv4 address are judged by that address.
        embedded = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)
        if embedded is None and ip in ipaddress.ip_network("64:ff9b::/96"):
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None and is_blocked_ip(str(embedded)):
            return True
    if any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version):
        return True
    return not ip.is_global or ip.is_multicast
