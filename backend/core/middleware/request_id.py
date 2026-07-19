"""Request ID Middleware.

Reads or generates a unique request ID for every incoming HTTP request,
propagates it via the REQUEST_ID_CONTEXT context variable so structured
logging can attach it automatically, and echoes it back in the response
via the X-Request-ID header.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging.setup import REQUEST_ID_CONTEXT
from core.utils.uuid import generate_uuid

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique Request ID to every request.

    Order requirement: must be the outermost middleware so that all
    downstream middleware and handlers see the populated context variable.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id: str = request.headers.get(_REQUEST_ID_HEADER) or str(
            generate_uuid()
        )

        token = REQUEST_ID_CONTEXT.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            REQUEST_ID_CONTEXT.reset(token)

        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
