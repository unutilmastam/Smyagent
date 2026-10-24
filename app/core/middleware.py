"""Pure-ASGI request-ID middleware (works under uvicorn and the a2wsgi bridge)."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import error_body
from app.core.logging import request_id_var

HEADER = "x-request-id"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
logger = logging.getLogger("app.request")
error_logger = logging.getLogger("app.errors")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(HEADER.encode(), b"").decode("latin-1")
        rid = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((HEADER.encode(), rid.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # Handled here (not only in Starlette's outer ServerErrorMiddleware) so the
            # log line, the response body and the header all carry the request ID.
            error_logger.exception("unhandled_error", extra={"error_type": type(exc).__name__})
            if response_started:
                raise
            body = json.dumps(error_body("internal_error", "Internal server error")).encode()
            await send_wrapper(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send_wrapper({"type": "http.response.body", "body": body})
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)
