"""
Caching utilities for workflow system.
Provides simple in-memory caching with TTL support.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowCache:
    """
    Simple in-memory cache with TTL support.
    Thread-safe for read operations, basic write safety.
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache.

        Args:
            ttl: Time to live in seconds (default 5 minutes)
            max_size: Maximum number of cache entries
        """
        self.cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                logger.debug(f"Cache hit for key: {key}")
                return value
            # Expired, remove it
            del self.cache[key]

        self.misses += 1
        logger.debug(f"Cache miss for key: {key}")
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        # Simple size limit enforcement
        if len(self.cache) >= self.max_size:
            # Remove oldest entry (not LRU, but simple)
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

        self.cache[key] = (value, time.time())
        logger.debug(f"Cached value for key: {key}")

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
        }


# Global cache instances for different purposes
session_cache = WorkflowCache(ttl=1800, max_size=500)  # 30 min for sessions
template_cache = WorkflowCache(ttl=3600, max_size=100)  # 1 hour for templates
api_cache = WorkflowCache(ttl=300, max_size=200)  # 5 min for API responses


def cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash of arguments as cache key
    """
    # Create a string representation of arguments
    key_data = {"args": args, "kwargs": sorted(kwargs.items())}
    key_str = json.dumps(key_data, sort_keys=True, default=str)

    # Return MD5 hash for consistent key length
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 300, cache_instance: WorkflowCache | None = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        cache_instance: Cache instance to use (default: api_cache)

    Returns:
        Decorated function with caching
    """
    cache = cache_instance or api_cache

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        # Add cache control methods
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_stats = lambda: cache.get_stats()

        return wrapper

    return decorator


# Specialized cache decorators
cache_session = lambda func: cached(ttl=1800, cache_instance=session_cache)(func)
cache_template = lambda func: cached(ttl=3600, cache_instance=template_cache)(func)
cache_api = lambda func: cached(ttl=300, cache_instance=api_cache)(func)
