"""Retry utilities with exponential backoff."""

import asyncio
import functools
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def async_retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff + jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + asyncio.get_event_loop().time() % 0.5)

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): "
                        f"{e}. Retrying in {delay:.1f}s..."
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but mypy needs it
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for sync functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import time

            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    delay = delay * (0.5 + (time.time() % 1.0) * 0.5)

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): "
                        f"{e}. Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator
