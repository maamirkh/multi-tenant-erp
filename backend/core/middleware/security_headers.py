"""SecurityHeadersMiddleware — add OWASP-recommended security response headers.

Applied globally to every response so that all API endpoints and error
responses include the required headers.  The headers enforce browser-level
protections against common attack vectors.

Headers set (per spec.md §13.7):
  - X-Content-Type-Options      : nosniff
  - X-Frame-Options             : DENY
  - X-XSS-Protection            : 1; mode=block
  - Referrer-Policy             : strict-origin-when-cross-origin
  - Content-Security-Policy     : default-src 'self'
  - Strict-Transport-Security   : max-age=31536000; includeSubDomains
  - Permissions-Policy          : camera=(), microphone=(), geolocation=()
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects security headers on every response."""

    # Swagger/ReDoc paths that require CDN resources and inline scripts.
    _DOCS_PATHS = frozenset(
        {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
    )

    # Relaxed CSP for documentation pages — allows Swagger UI CDN assets
    # and the inline <script> tag that FastAPI injects to bootstrap the UI.
    _DOCS_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' https://fastapi.tiangolo.com data:; "
        "font-src 'self' https://cdn.jsdelivr.net"
    )

    _API_CSP = "default-src 'self'"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            self._DOCS_CSP if request.url.path in self._DOCS_PATHS else self._API_CSP
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response
