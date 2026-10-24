"""Passenger (cPanel "Setup Python App") startup file.

Startup file: deployment/cpanel/passenger_wsgi.py
Entry point:  application

Passenger speaks WSGI; FastAPI is ASGI. a2wsgi bridges them (ADR-0001).
Limitations under this bridge: no WebSockets, no streaming responses,
no reliance on FastAPI BackgroundTasks.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# Settings read `.env` relative to the working directory; Passenger does not
# guarantee it is the project root.
os.chdir(PROJECT_ROOT)

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.core.config import ConfigurationError, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _config_error_app(message: str) -> Callable[..., Iterable[bytes]]:
    """Serve 503 instead of crash-looping when configuration is invalid."""
    sys.stderr.write(message + "\n")

    def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        body = b'{"error":{"code":"configuration_error","message":"Service misconfigured"}}'
        start_response(
            "503 Service Unavailable",
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
        )
        return [body]

    return app


def build_application() -> Callable[..., Iterable[bytes]]:
    try:
        settings = get_settings()
    except ConfigurationError as exc:
        return _config_error_app(str(exc))
    return ASGIMiddleware(create_app(settings))  # type: ignore[return-value]


application = build_application()
