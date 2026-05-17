"""
Retry utilities with exponential backoff for API calls.
"""
import time
import logging
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        exceptions: Tuple of exception types to catch and retry.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt >= max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
