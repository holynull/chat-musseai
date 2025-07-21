"""
Common API decorators for caching, rate limiting, and retry logic
"""
import time
import hashlib
import threading
from functools import wraps
import requests
from loggers import logger


# Global cache and rate limiting variables
_cache = {}
_cache_lock = threading.Lock()
_last_request_time = 0
_request_lock = threading.Lock()

# Default configuration - can be overridden
DEFAULT_CACHE_DURATION = 300  # 5 minutes
DEFAULT_MIN_REQUEST_INTERVAL = 1.2  # 1.2 seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # seconds


def cache_result(duration: int = DEFAULT_CACHE_DURATION):
    """
    Cache decorator for API results with thread-safe implementation
    
    Args:
        duration: Cache duration in seconds (default: 300 seconds)
        
    Returns:
        Decorated function with caching capability
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key based on function name and arguments
            cache_key = f"{func.__name__}_{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            with _cache_lock:
                # Check if result exists in cache and is still valid
                if cache_key in _cache:
                    cached_data, timestamp = _cache[cache_key]
                    if time.time() - timestamp < duration:
                        logger.debug(f"Cache hit for {func.__name__}")
                        return cached_data
                
                # Clean up expired cache entries
                current_time = time.time()
                expired_keys = [
                    k for k, (_, ts) in _cache.items() 
                    if current_time - ts >= duration
                ]
                for key in expired_keys:
                    del _cache[key]
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Cache the result if not None
            if result is not None:
                with _cache_lock:
                    _cache[cache_key] = (result, time.time())
            
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
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                
                _last_request_time = time.time()
            
            return func(*args, **kwargs)
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
                                f"429 error, retrying in {sleep_time}s "
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
                            f"Request failed, retrying in {sleep_time}s "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        time.sleep(sleep_time)
                        continue
                    raise
            
            raise last_exception
        return wrapper
    return decorator


def clear_cache():
    """Clear all cached data"""
    with _cache_lock:
        _cache.clear()
        logger.info("Cache cleared")


def get_cache_stats():
    """Get cache statistics"""
    with _cache_lock:
        return {
            "cache_size": len(_cache),
            "cache_keys": list(_cache.keys())
        }


# Commonly used decorator combinations
def api_call_with_cache_and_rate_limit(
    cache_duration: int = DEFAULT_CACHE_DURATION,
    rate_limit_interval: float = DEFAULT_MIN_REQUEST_INTERVAL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY
):
    """
    Convenience decorator that combines caching, rate limiting, and retry logic
    
    Args:
        cache_duration: Cache duration in seconds
        rate_limit_interval: Minimum interval between requests
        max_retries: Maximum retry attempts
        retry_delay: Base delay for retries
        
    Returns:
        Combined decorator
    """
    def decorator(func):
        # Apply decorators in reverse order (innermost first)
        func = retry_on_429(max_retries, retry_delay)(func)
        func = rate_limit(rate_limit_interval)(func)
        func = cache_result(cache_duration)(func)
        return func
    return decorator
