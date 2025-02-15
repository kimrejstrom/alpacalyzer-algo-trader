from collections.abc import Callable
from functools import lru_cache, wraps
from time import time
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def timed_lru_cache(seconds: int, maxsize: int = 128) -> Callable[[F], F]:
    """
    A decorator that combines lru_cache with a time-based expiry.

    Args:
        seconds (int): Cache expiry time in seconds.
        maxsize (int): Maximum size of the cache.

    Returns:
        function: Decorated function with time-based expiry.
    """

    def decorator(func):
        cached_func = lru_cache(maxsize=maxsize)(func)
        cache_expiry: dict[tuple[Any, ...], float] = {}

        @wraps(func)
        def wrapped(*args, **kwargs):
            now = time()
            key = args + tuple(kwargs.items())
            if key in cache_expiry:
                if now - cache_expiry[key] > seconds:
                    cached_func.cache_clear()
                    cache_expiry.pop(key, None)

            result = cached_func(*args, **kwargs)
            cache_expiry[key] = now
            return result

        wrapped.cache_clear = cached_func.cache_clear  # type: ignore
        return wrapped

    return decorator
