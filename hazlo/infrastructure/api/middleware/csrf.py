"""CSRF protection middleware for admin forms."""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method in ("POST", "PATCH", "DELETE") and request.url.path.startswith("/admin"):
            token = request.headers.get("X-CSRF-Token")
            if token is None:
                form = await request.form()
                token = form.get("csrf_token")

            expected = request.scope.get("session", {}).get("csrf_token")
            if not token or not expected or not hmac.compare_digest(str(token), str(expected)):
                return Response(content="CSRF token invalid", status_code=403, headers={"WWW-Authenticate": "Basic"})

        return await call_next(request)


def generate_csrf_token() -> str:
    return secrets.token_hex(32)
