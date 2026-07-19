"""CSRF middleware placeholder for future cookie-based authentication support.

This module provides an extensible hook that will enforce CSRF token validation
once cookie-based sessions are introduced.  The current authentication strategy
uses stateless JWT Bearer tokens (see ADR-0001 and ADR-0003), which are not
susceptible to CSRF attacks.  This placeholder ensures that adding CSRF
protection in a future Epic requires only enabling the middleware — no
structural changes to the request pipeline are needed.

Usage (future)::

    from core.middleware.csrf import CSRFMiddleware
    app.add_middleware(CSRFMiddleware)
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Extensible CSRF middleware hook.

    Current behaviour: pass-through (no-op).  All requests are forwarded
    unchanged.  When cookie-based authentication is introduced, this class
    must be updated to:

    1. Read the CSRF token from the ``X-CSRF-Token`` request header.
    2. Validate it against the value stored in the session cookie.
    3. Reject non-idempotent requests (POST/PUT/PATCH/DELETE) that lack a
       valid token with HTTP 403.

    The middleware is intentionally **not** registered in ``main.py`` until
    cookie-based auth is active, to avoid a 403-producing no-op on every
    request.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Pass-through: CSRF enforcement is deferred until cookie-based auth.
        response: Response = await call_next(request)  # type: ignore[operator]
        return response
