"""Installable PWA: manifest and a service worker that caches the app shell only.

Pages with data are never cached (CLAUDE.md §7.3): the worker only serves
versioned static assets from its cache and lets every navigation go to the network.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

from app.web.templating import HTMX_FILE, STATIC_DIR

router = APIRouter(include_in_schema=False)

MANIFEST = {
    "name": "SMY Agent",
    "short_name": "SMY Agent",
    "description": "ITcoDe.Uz — AI sales agent",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#f6f7f9",
    "theme_color": "#0f766e",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/static/icons/icon.svg", "sizes": "any", "type": "image/svg+xml"},
    ],
}

# Static files the service worker caches; must match SHELL in static/sw.js (tested).
SHELL_ASSETS = [
    "/static/app.css",
    "/static/app.js",
    "/static/" + HTMX_FILE,
    "/static/icons/icon-192.png",
]


@router.get("/manifest.webmanifest")
def manifest() -> Response:
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@router.get("/sw.js")
def service_worker() -> Response:
    # Served from "/" so its scope covers the whole app.
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )
