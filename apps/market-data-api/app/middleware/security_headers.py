"""Security-headers middleware.

Strips framework-identifying headers and adds security-related headers
to every response.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


# Headers to remove from responses
_STRIP_HEADERS = {"server", "x-powered-by"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Strip framework-identifying headers
        for header in _STRIP_HEADERS:
            if header in response.headers:
                del response.headers[header]

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"

        return response
