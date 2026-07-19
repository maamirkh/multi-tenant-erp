"""Authentication Hook Middleware.

Attempts to extract and validate the JWT from every incoming request.
A valid token populates ``request.state.user`` with a ``CurrentUser``
instance so that downstream handlers (middleware, dependencies, services)
can access the authenticated identity without re-parsing the token.

Failure to authenticate does NOT cause the middleware to reject the request.
Enforcement happens at the endpoint level via ``require_authenticated``
(or ``get_current_user``) FastAPI dependencies — this allows public routes
to function correctly even when no valid token is present.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.auth.interfaces import CurrentUser

logger = logging.getLogger(__name__)


class AuthHookMiddleware(BaseHTTPMiddleware):
    """Opportunistically authenticate every incoming request.

    Sets ``request.state.user`` to a ``CurrentUser`` instance.
    When authentication fails (missing/invalid token), the user is set to
    an unauthenticated sentinel so that public routes continue to work.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            from core.auth.dependencies import get_current_user
            from core.config.settings import get_settings
            from core.database.session import get_db

            db_gen = get_db()
            db = next(db_gen)
            try:
                user = get_current_user(
                    request=request,
                    db=db,
                    settings=get_settings(),
                )
                request.state.user = user
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
        except Exception:  # noqa: BLE001
            # Any auth failure in middleware must not break public routes.
            request.state.user = CurrentUser(is_authenticated=False)

        return await call_next(request)
