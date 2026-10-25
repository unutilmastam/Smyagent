"""Fetch public web pages safely (CLAUDE.md §15.2).

- http/https only, allowed ports only, no credentials in URLs
- DNS is resolved here; every resolved address must be public, and the
  connection goes to that validated IP (Host header + TLS SNI keep the name),
  so a DNS rebinding answer cannot redirect us inside the network
- redirects are followed manually (max 5) and each hop is re-validated
- connect/read timeouts and an overall time budget; max body size;
  allowed content types only; TLS verification always on
- robots.txt is respected; an honest User-Agent identifies SMY Agent
- at most one request per host every `min_interval` seconds
"""

from __future__ import annotations

import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin

import httpx

from app.infrastructure.http_fetcher.policy import (
    BlockedURLError,
    Target,
    is_blocked_ip,
    parse_target,
)

USER_AGENT = "SMY-Agent/0.1 (+https://itcode.uz; website audit for ITcoDe.Uz)"
ROBOTS_AGENT = "SMY-Agent"
MAX_REDIRECTS = 5
MAX_BYTES = 2 * 1024 * 1024
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
TOTAL_BUDGET_SECONDS = 25.0

Resolver = Callable[[str, int], list[str]]


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


class FetchError(RuntimeError):
    """Category is safe to store and show: dns, connect, timeout, tls, http, too_large, ..."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class RobotsDisallowedError(FetchError):
    def __init__(self, url: str) -> None:
        super().__init__("robots", f"robots.txt disallows {url}")


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    elapsed_ms: int
    redirects: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        charset = "utf-8"
        if "charset=" in self.content_type:
            charset = self.content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class SafeFetcher:
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        transport: httpx.BaseTransport | None = None,
        min_interval: float = 2.0,
        respect_robots: bool = True,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        verify: ssl.SSLContext | bool = True,
    ) -> None:
        self.resolver = resolver
        self.client = httpx.Client(
            transport=transport,
            timeout=TIMEOUT,
            follow_redirects=False,
            verify=verify,
            # Never via an env proxy: it would re-resolve the name and defeat IP pinning.
            trust_env=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self.min_interval = min_interval
        self.respect_robots = respect_robots
        self.clock = clock
        self.sleep = sleep
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}

    # -- public ------------------------------------------------------------

    def fetch(self, url: str) -> FetchResult:
        started = self.clock()
        current = url
        redirects: list[str] = []
        if self.respect_robots and not self._allowed_by_robots(current):
            raise RobotsDisallowedError(current)
        for _ in range(MAX_REDIRECTS + 1):
            response, body = self._request(current, started, read_body=True)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise FetchError("http", "redirect without Location header")
                current = urljoin(current, location)
                redirects.append(current)
                if self.respect_robots and not self._allowed_by_robots(current):
                    raise RobotsDisallowedError(current)
                continue
            content_type = response.headers.get("content-type", "").lower()
            if response.status_code < 400 and not content_type.startswith(ALLOWED_TYPES):
                raise FetchError(
                    "content_type", f"content type {content_type or 'missing'} not allowed"
                )
            return FetchResult(
                requested_url=url,
                final_url=current,
                status_code=response.status_code,
                content_type=content_type,
                body=body,
                elapsed_ms=int((self.clock() - started) * 1000),
                redirects=redirects,
            )
        raise FetchError("redirects", f"more than {MAX_REDIRECTS} redirects")

    # -- internals ---------------------------------------------------------

    def _resolve_public(self, target: Target) -> str:
        if not any(c.isalpha() for c in target.host) or ":" in target.host:
            addresses = [target.host.strip("[]")]  # literal IP in the URL
        else:
            try:
                addresses = self.resolver(target.host, target.port)
            except (OSError, UnicodeError) as exc:
                raise FetchError("dns", f"cannot resolve {target.host}") from exc
        if not addresses:
            raise FetchError("dns", f"no address for {target.host}")
        # Every answer must be public: an attacker could mix a private one in.
        blocked = [a for a in addresses if is_blocked_ip(a)]
        if blocked:
            raise BlockedURLError(f"{target.host} resolves to a non-public address")
        return addresses[0]

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = self.min_interval - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        self._last_request[host] = self.clock()

    def _request(
        self, url: str, started: float, *, read_body: bool
    ) -> tuple[httpx.Response, bytes]:
        target = parse_target(url)
        ip = self._resolve_public(target)
        if self.clock() - started > TOTAL_BUDGET_SECONDS:
            raise FetchError("timeout", "overall time budget exceeded")
        self._throttle(target.host)
        ip_host = f"[{ip}]" if ":" in ip else ip
        default_port = (target.scheme == "https" and target.port == 443) or (
            target.scheme == "http" and target.port == 80
        )
        host_header = target.host if default_port else f"{target.host}:{target.port}"
        pinned = f"{target.scheme}://{ip_host}:{target.port}{target.path}"
        request = self.client.build_request(
            "GET",
            pinned,
            headers={"Host": host_header},
            extensions={"sni_hostname": target.host},
        )
        try:
            response = self.client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise FetchError("timeout", f"timeout contacting {target.host}") from exc
        except httpx.ConnectError as exc:
            message = str(exc).lower()
            category = "tls" if "ssl" in message or "certificate" in message else "connect"
            raise FetchError(category, f"cannot connect to {target.host}") from exc
        except httpx.HTTPError as exc:
            raise FetchError("http", f"{type(exc).__name__} from {target.host}") from exc
        try:
            body = b""
            if read_body:
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > MAX_BYTES:
                    raise FetchError("too_large", "response larger than the limit")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise FetchError("too_large", "response larger than the limit")
                    chunks.append(chunk)
                body = b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise FetchError("timeout", f"timeout reading {target.host}") from exc
        finally:
            response.close()
        return response, body

    def _allowed_by_robots(self, url: str) -> bool:
        target = parse_target(url)
        key = f"{target.scheme}://{target.host}:{target.port}"
        if key not in self._robots:
            self._robots[key] = self._load_robots(key, target)
        parser = self._robots[key]
        return parser is None or parser.can_fetch(ROBOTS_AGENT, url)

    def _load_robots(self, base: str, target: Target) -> robotparser.RobotFileParser | None:
        robots_url = (
            f"{target.scheme}://{target.host}"
            + ("" if target.port in (80, 443) else f":{target.port}")
            + "/robots.txt"
        )
        try:
            response, body = self._request(robots_url, self.clock(), read_body=True)
        except FetchError:
            return None  # unreachable robots.txt: treated as "no rules"
        if response.status_code >= 400:
            return None
        parser = robotparser.RobotFileParser()
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        return parser

    def close(self) -> None:
        self.client.close()
