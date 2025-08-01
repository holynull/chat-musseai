# src/utils/api_decorators.py (修改后的版本)
"""
Enhanced API decorators with Redis caching support
"""
import time
import hashlib
import threading
from functools import wraps
import requests
from loggers import logger
from utils.redis_cache import _cache_backend

# Keep existing rate limiting variables for backward compatibility
_last_request_time = 0
_request_lock = threading.Lock()

# Default configuration
DEFAULT_CACHE_DURATION = 300  # 5 minutes
DEFAULT_MIN_REQUEST_INTERVAL = 1.2  # 1.2 seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # seconds

class APIRateLimitException(Exception):
    """Custom exception for rate limit (429) errors that should trigger API switching"""
    def __init__(self, message, api_name=None):
        super().__init__(message)
        self.api_name = api_name

def cache_result(duration: int = DEFAULT_CACHE_DURATION):
    """
    Enhanced cache decorator with Redis support and memory fallback
    
    Args:
        duration: Cache duration in seconds (default: 300 seconds)
        
    Returns:
        Decorated function with Redis caching capability
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key based on function name and arguments
            cache_key = f"{func.__name__}_{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            # Check cache
            cached_result = _cache_backend.get(cache_key)
            if cached_result:
                cached_data, timestamp = cached_result
                if time.time() - timestamp < duration:
                    logger.debug(f"Cache hit for {func.__name__} (age: {time.time() - timestamp:.1f}s)")
                    return cached_data
            
            # Execute the function
            logger.debug(f"Cache miss for {func.__name__}, executing function")
            result = func(*args, **kwargs)
            
            # Cache the result if not None
            if result is not None:
                _cache_backend.set(cache_key, result, time.time(), duration)
                logger.debug(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator

def rate_limit(interval: float = DEFAULT_MIN_REQUEST_INTERVAL):
    """
    Rate limiting decorator to prevent API abuse
    
    Args:
        interval: Minimum interval between requests in seconds
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global _last_request_time
            
            with _request_lock:
                current_time = time.time()
                time_since_last = current_time - _last_request_time
                
                if time_since_last < interval:
                    sleep_time = interval - time_since_last
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {func.__name__}")
                    time.sleep(sleep_time)
                
                _last_request_time = time.time()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def no_retry_on_429():
    """
    Decorator that converts 429 errors to APIRateLimitException
    instead of retrying, allowing higher-level fallback logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    # Convert 429 to custom exception for API switching
                    raise APIRateLimitException(
                        f"Rate limit exceeded for {func.__name__}", 
                        api_name=getattr(func, '_api_name', 'unknown')
                    )
                raise
        return wrapper
    return decorator

def retry_on_429(max_retries: int = DEFAULT_MAX_RETRIES, delay: float = DEFAULT_RETRY_DELAY):
    """
    Retry decorator for handling 429 (Too Many Requests) errors
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Base delay between retries (will use exponential backoff)
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        last_exception = e
                        if attempt < max_retries:
                            sleep_time = delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(
                                f"429 error for {func.__name__}, retrying in {sleep_time}s "
                                f"(attempt {attempt + 1}/{max_retries + 1})"
                            )
                            time.sleep(sleep_time)
                            continue
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        sleep_time = delay * (2 ** attempt)
                        logger.warning(
                            f"Request failed for {func.__name__}, retrying in {sleep_time}s "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        time.sleep(sleep_time)
                        continue
                    raise
            
            raise last_exception
        return wrapper
    return decorator

def clear_cache(pattern: str = "*"):
    """Clear cached data by pattern"""
    _cache_backend.clear(pattern)
    logger.info(f"Cache cleared with pattern: {pattern}")

def get_cache_stats():
    """Get comprehensive cache statistics"""
    return _cache_backend.get_stats()

def cache_health_check():
    """Perform cache health check"""
    return _cache_backend.health_check()

# Commonly used decorator combinations
def api_call_with_cache_and_rate_limit(
    cache_duration: int = DEFAULT_CACHE_DURATION,
    rate_limit_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY
):
    """
    Convenience decorator that combines Redis caching, rate limiting, and retry logic
    
    Args:
        cache_duration: Cache duration in seconds
        rate_limit_interval: Minimum interval between requests
        max_retries: Maximum retry attempts
        retry_delay: Base delay for retries
        
    Returns:
        Combined decorator with Redis caching
    """
    def decorator(func):
        # Apply decorators in reverse order (innermost first)
        func = retry_on_429(max_retries, retry_delay)(func)
        func = rate_limit(rate_limit_interval)(func)
        func = cache_result(cache_duration)(func)
        return func
    return decorator

def api_call_with_cache_and_rate_limit_no_429_retry(
    cache_duration: int = DEFAULT_CACHE_DURATION,
    rate_limit_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
    api_name: str = None
):
    """
    Enhanced decorator with Redis caching and rate limiting 
    but doesn't retry on 429 - throws APIRateLimitException instead
    
    Args:
        cache_duration: Cache duration in seconds
        rate_limit_interval: Minimum interval between requests
        api_name: Name of the API for exception handling
        
    Returns:
        Combined decorator without 429 retry
    """
    def decorator(func):
        # Store API name for exception handling
        if api_name:
            func._api_name = api_name
            
        # Apply decorators without 429 retry
        func = no_retry_on_429()(func)
        func = rate_limit(rate_limit_interval)(func)
        func = cache_result(cache_duration)(func)
        return func
    return decorator

# Cache management utilities
def warm_cache(func, *args, **kwargs):
    """Warm up cache by pre-executing function"""
    try:
        result = func(*args, **kwargs)
        logger.info(f"Cache warmed for {func.__name__}")
        return result
    except Exception as e:
        logger.warning(f"Failed to warm cache for {func.__name__}: {e}")
        return None

def invalidate_cache_by_pattern(pattern: str):
    """Invalidate cache entries matching pattern"""
    cleared_count = _cache_backend.clear(pattern)
    logger.info(f"Invalidated cache entries matching pattern '{pattern}': {cleared_count}")
