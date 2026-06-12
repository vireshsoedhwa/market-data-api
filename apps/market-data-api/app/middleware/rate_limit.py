"""Rate-limit middleware using a Redis sliding-window counter.

Adds X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset
headers to every response. Returns 429 with the v2 error envelope when
the limit is exceeded.
"""

import logging
import time

import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.settings import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _client_key(request: Request) -> str:
    """Derive a rate-limit bucket key from the bearer token or client IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
        # Use first 16 chars of token hash to avoid storing full tokens
        return f"rl:{hash(token) & 0xFFFFFFFF:08x}"
    # Fallback to IP (X-Forwarded-For aware)
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"rl:ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health endpoint
        if request.url.path == "/health":
            return await call_next(request)

        limit = settings.rate_limit_requests_per_minute
        window = 60  # seconds
        now = int(time.time())
        window_start = now - window
        reset_at = now + window

        key = _client_key(request)

        try:
            r = _get_redis()
            pipe = r.pipeline()
            # Remove entries older than the window
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request
            pipe.zadd(key, {str(now) + ":" + str(id(request)): now})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry on the key
            pipe.expire(key, window + 1)
            results = await pipe.execute()
            request_count = results[2]
        except Exception:
            # If Redis is unavailable, allow the request but log
            logger.warning("Rate-limit Redis unavailable, allowing request", exc_info=True)
            return await call_next(request)

        remaining = max(0, limit - request_count)

        if request_count > limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit of {limit} requests per minute exceeded",
                        "symbol": None,
                        "retry_after_seconds": window,
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(window),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
