"""Small synchronous Bot API client. The token is part of the URL and is never logged."""

from __future__ import annotations

from typing import Any

import httpx

API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
ALLOWED_UPDATES = ["message", "callback_query"]


class TelegramError(RuntimeError):
    """Bot API call failed. The message never contains the bot token."""


class TelegramClient:
    def __init__(self, token: str, *, http: httpx.Client | None = None) -> None:
        if not token:
            raise TelegramError("bot token is not configured")
        self._token = token
        self._http = http or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        url = f"{API_BASE}/bot{self._token}/{method}"
        try:
            response = self._http.post(url, json=payload)
        except httpx.HTTPError as exc:
            # str(exc) can include the request URL (with the token): report the type only.
            raise TelegramError(f"{method}: network error ({type(exc).__name__})") from None
        try:
            body = response.json()
        except ValueError:
            raise TelegramError(f"{method}: HTTP {response.status_code}, non-JSON body") from None
        if not body.get("ok"):
            description = str(body.get("description", "unknown error"))[:200]
            raise TelegramError(f"{method}: HTTP {response.status_code}: {description}")
        return body.get("result")

    def set_webhook(self, url: str, *, secret_token: str) -> None:
        self._call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": ALLOWED_UPDATES,
                "drop_pending_updates": True,
                "max_connections": 5,  # shared hosting: few Passenger processes
            },
        )

    def webhook_info(self) -> dict[str, Any]:
        result = self._call("getWebhookInfo", {})
        return result if isinstance(result, dict) else {}

    def send_message(self, chat_id: int, text: str) -> None:
        self._call("sendMessage", {"chat_id": chat_id, "text": text[:4096]})
