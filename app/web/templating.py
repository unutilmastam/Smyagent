"""Jinja2 environment (autoescape on for .html) and the page render helper."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.web.i18n import (
    LANG_COOKIE,
    LANGUAGE_NAMES,
    LANGUAGES,
    language_from_header,
    normalize_language,
    translator,
)

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
HTMX_FILE = "vendor/htmx-2.0.4.min.js"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

NO_STORE = {"Cache-Control": "no-store"}


def request_language(request: Request) -> str:
    cookie = request.cookies.get(LANG_COOKIE)
    if cookie:
        return normalize_language(cookie)
    return language_from_header(request.headers.get("accept-language"))


def is_htmx_partial(request: Request) -> bool:
    """HTMX request that wants a fragment (not a boosted full-page navigation)."""
    return bool(request.headers.get("hx-request")) and not request.headers.get("hx-boosted")


def render(
    request: Request, name: str, context: dict[str, object] | None = None, status: int = 200
) -> Response:
    lang = request_language(request)
    full: dict[str, object] = {
        "lang": lang,
        "t": translator(lang),
        "languages": LANGUAGES,
        "language_names": LANGUAGE_NAMES,
        "htmx_src": "/static/" + HTMX_FILE,
    }
    full.update(context or {})
    response = templates.TemplateResponse(request, name, full, status_code=status)
    response.headers.update(NO_STORE)
    return response
