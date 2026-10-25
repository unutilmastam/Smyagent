"""The app must keep working behind Passenger's WSGI interface (ADR-0001)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from wsgiref.util import setup_testing_defaults

import pytest

PASSENGER_FILE = Path(__file__).resolve().parents[2] / "deployment" / "cpanel" / "passenger_wsgi.py"


def _load_passenger(monkeypatch: pytest.MonkeyPatch, **env: str) -> Any:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from app.core.config import get_settings

    get_settings.cache_clear()
    spec = importlib.util.spec_from_file_location("passenger_wsgi_under_test", PASSENGER_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("passenger_wsgi_under_test", None)
    spec.loader.exec_module(module)
    return module


def _call(app: Callable[..., Iterable[bytes]], path: str) -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, Any] = {}
    setup_testing_defaults(environ)
    environ.update({"PATH_INFO": path, "REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO(b"")})
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> None:
        captured["status"] = status
        captured["headers"] = {k.lower(): v for k, v in headers}

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


def test_health_through_wsgi_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_passenger(monkeypatch, APP_ENV="test")
    status, headers, body = _call(module.application, "/api/v1/health")
    assert status.startswith("200")
    assert json.loads(body)["status"] == "ok"
    assert "x-request-id" in headers


def test_misconfiguration_serves_503_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_passenger(
        monkeypatch, APP_ENV="production", APP_SECRET_KEY="tooshort-secret-abc"
    )
    status, _, body = _call(module.application, "/api/v1/health")
    assert status.startswith("503")
    assert b"configuration_error" in body
    assert b"tooshort-secret-abc" not in body


def test_root_startup_file_serves_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """cPanel startup file `passenger_wsgi.py` at the app root (nested path fallback)."""
    root_file = PASSENGER_FILE.parents[2] / "passenger_wsgi.py"
    monkeypatch.setenv("APP_ENV", "test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    spec = importlib.util.spec_from_file_location("root_passenger_under_test", root_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    status, _, body = _call(module.application, "/api/v1/health")
    assert status.startswith("200") and json.loads(body)["status"] == "ok"
