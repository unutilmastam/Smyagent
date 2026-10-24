"""Auth/CSRF error responses: redirects/HTML for the dashboard, JSON envelope for the API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.core.exceptions import error_body
from app.web.auth import CsrfError, ForbiddenError, LoginRequiredError, login_url


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def register_web_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LoginRequiredError)
    async def _login_required(request: Request, exc: LoginRequiredError) -> Response:
        if _is_api(request):
            return JSONResponse(error_body("unauthorized", "Authentication required"), 401)
        target = login_url(exc.next_path)
        if request.headers.get("hx-request"):
            # HTMX swaps responses in place; ask it to navigate instead.
            return Response(status_code=401, headers={"HX-Redirect": target})
        return RedirectResponse(target, status_code=303)

    @app.exception_handler(ForbiddenError)
    async def _forbidden(request: Request, _: ForbiddenError) -> Response:
        return JSONResponse(error_body("forbidden", "Not allowed"), status_code=403)

    @app.exception_handler(CsrfError)
    async def _csrf(request: Request, _: CsrfError) -> Response:
        return JSONResponse(
            error_body("csrf_failed", "Session expired or invalid form. Reload the page."),
            status_code=403,
        )
