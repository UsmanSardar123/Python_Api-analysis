"""Sliding-window in-memory rate limiter for abuse protection."""

from collections import deque
import time

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings


class RateLimiter:
    """Thread/coroutine-safe sliding-window rate limiter keyed by client IP."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check_rate_limit(
        self,
        client_id: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        """Raise HTTP 429 if client_id exceeds max_requests within window_seconds."""
        now = time.monotonic()
        cutoff = now - float(window_seconds)

        bucket = self._hits.get(client_id)
        if bucket is None:
            bucket = deque()
            self._hits[client_id] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": (
                        f"Rate limit exceeded: maximum {max_requests} requests per "
                        f"{window_seconds} seconds allowed."
                    ),
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)

    def reset(self) -> None:
        """Clear all recorded request timestamps (useful in tests)."""
        self._hits.clear()


rate_limiter = RateLimiter()


async def enforce_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency enforcing per-IP sliding window rate limits."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown"

    rate_limiter.check_rate_limit(
        client_id=client_ip,
        max_requests=settings.rate_limit_requests_per_minute,
        window_seconds=settings.rate_limit_window_seconds,
    )

