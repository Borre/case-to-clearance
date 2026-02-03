"""Rate limiting middleware for API endpoints."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter(BaseHTTPMiddleware):
    """Simple in-memory rate limiter using token bucket algorithm."""

    def __init__(self, app, requests_per_minute: int | None = None):
        """Initialize the rate limiter.

        Args:
            app: FastAPI/Starlette application
            requests_per_minute: Maximum requests per minute per client
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.max_requests_per_minute
        self.requests: defaultdict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response from downstream

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Skip rate limiting for health check and static files
        if request.url.path in ["/health", "/static", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        async with self._lock:
            now = time.time()
            window_start = now - 60.0  # 1 minute window

            # Clean old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id] if req_time > window_start
            ]

            # Check limit
            if len(self.requests[client_id]) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_id}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                )

            # Record this request
            self.requests[client_id].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.requests[client_id])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(window_start + 60))

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting.

        Args:
            request: Incoming request

        Returns:
            Client identifier string
        """
        # Try to get real IP from forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client host
        return request.client.host if request.client else "unknown"


class SlidingWindowRateLimiter(RateLimiter):
    """Enhanced rate limiter with sliding window algorithm."""

    def __init__(self, app, requests_per_minute: int | None = None, window_size: int = 60):
        """Initialize sliding window rate limiter.

        Args:
            app: FastAPI/Starlette application
            requests_per_minute: Maximum requests per window
            window_size: Window size in seconds
        """
        super().__init__(app, requests_per_minute)
        self.window_size = window_size
        # Track (timestamp, count) tuples for more precise tracking
        self.windows: defaultdict[str, list[tuple[float, int]]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with sliding window rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response from downstream

        Raises:
            HTTPException: If rate limit exceeded
        """
        if request.url.path in ["/health", "/static", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_id = self._get_client_id(request)

        async with self._lock:
            now = time.time()
            current_window = int(now / self.window_size)

            # Clean old windows
            self.windows[client_id] = [
                (window, count)
                for window, count in self.windows[client_id]
                if window >= current_window - 1
            ]

            # Calculate current rate using weighted sliding window
            weighted_count = 0.0
            for window, count in self.windows[client_id]:
                if window == current_window:
                    weighted_count += count
                elif window == current_window - 1:
                    # Partial weight for previous window
                    elapsed = now - (window * self.window_size)
                    weight = 1.0 - (elapsed / self.window_size)
                    weighted_count += count * weight

            if weighted_count >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_id}: {weighted_count:.1f}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per {self.window_size} seconds.",
                )

            # Add current request to current window
            # Find or create entry for current window
            window_entry = next(
                ((w, c) for w, c in self.windows[client_id] if w == current_window),
                None,
            )
            if window_entry:
                idx = self.windows[client_id].index(window_entry)
                self.windows[client_id][idx] = (current_window, window_entry[1] + 1)
            else:
                self.windows[client_id].append((current_window, 1))

        response = await call_next(request)

        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - weighted_count)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(remaining))
        response.headers["X-RateLimit-Window"] = str(self.window_size)

        return response
