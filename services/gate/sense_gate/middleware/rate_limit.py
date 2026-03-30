"""
Sense Gate — Redis Rate Limiting Middleware
Sliding window rate limiter keyed by API key or IP address.
"""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from sense_gate.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis.
    Falls back to pass-through if Redis is unavailable.
    """

    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self._redis = redis_client

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._redis is None:
            return await call_next(request)

        # Key by API key header or remote IP
        key_raw = (
            request.headers.get("X-API-Key")
            or request.headers.get("Authorization", "")
            or request.client.host
        )
        # Truncate long keys
        rate_key = f"rate:{key_raw[:64]}"
        window = settings.rate_limit_window_seconds
        limit = settings.rate_limit_requests

        try:
            now = time.time()
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(rate_key, 0, now - window)
            pipe.zadd(rate_key, {str(now): now})
            pipe.zcard(rate_key)
            pipe.expire(rate_key, window)
            results = await pipe.execute()
            count = results[2]

            if count > limit:
                logger.warning("Rate limit exceeded — key=%s count=%d", rate_key[:20], count)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": f"Too many requests. Limit: {limit} per {window}s.",
                        "retry_after": window,
                    },
                    headers={"Retry-After": str(window)},
                )
        except Exception as e:
            logger.debug("Rate limit Redis error (passing through): %s", e)

        return await call_next(request)
