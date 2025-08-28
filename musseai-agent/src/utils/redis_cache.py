# src/utils/redis_cache.py
import os
import json
import time
import hashlib
import threading
from typing import Any, Optional, Dict, Tuple, List
from urllib.parse import urlparse
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from loggers import logger


class RedisCacheBackend:
    """Redis cache backend with fallback to memory cache"""

    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}  # Fallback cache
        self.cache_lock = threading.Lock()
        self.connection_pool = None
        self.last_connection_attempt = 0
        self.connection_retry_interval = 30  # seconds
        self._setup_redis()

    def _setup_redis(self):
        """Setup Redis connection with connection pooling"""
        current_time = time.time()

        # Avoid frequent reconnection attempts
        if (
            current_time - self.last_connection_attempt
        ) < self.connection_retry_interval:
            return

        self.last_connection_attempt = current_time

        try:
            redis_config = self._get_redis_config()

            # Create connection pool for better performance
            self.connection_pool = redis.ConnectionPool(
                **redis_config,
                max_connections=20,
                retry_on_timeout=True,
                decode_responses=True,
            )

            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                decode_responses=True,
                encoding="utf-8",  # 明确指定编码
                encoding_errors="strict",  # 编码错误处理
            )

            # Test connection
            self.redis_client.ping()
            logger.info(
                f"Redis cache connected to {redis_config['host']}:{redis_config['port']}"
            )

        except Exception as e:
            logger.warning(f"Redis connection failed, using memory cache: {e}")
            self.redis_client = None
            self.connection_pool = None

    def _get_redis_config(self) -> dict:
        """Get Redis configuration from environment variables

        Supports both REDIS_URI and individual Redis configuration variables.
        REDIS_URI takes precedence if provided.

        Supported URI formats:
        - redis://[[username]:[password]]@host:port[/database]
        - rediss://[[username]:[password]]@host:port[/database] (SSL)
        - redis+sentinel://[[username]:[password]]@host:port[/database]
        """
        redis_uri = os.getenv("REDIS_URI")

        if redis_uri:
            return self._parse_redis_uri(redis_uri)
        else:
            # Fallback to individual environment variables
            return self._get_individual_redis_config()

    def _parse_redis_uri(self, redis_uri: str) -> dict:
        """Parse Redis URI and return configuration dictionary"""
        try:
            parsed = urlparse(redis_uri)

            config = {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 6379,
                "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", 5)),
                "socket_connect_timeout": int(os.getenv("REDIS_CONNECT_TIMEOUT", 5)),
                "socket_keepalive": True,
                "socket_keepalive_options": {},
                "health_check_interval": 30,
            }

            # Handle authentication
            if parsed.username:
                config["username"] = parsed.username
            if parsed.password:
                config["password"] = parsed.password

            # Handle database selection
            if parsed.path and len(parsed.path) > 1:
                try:
                    config["db"] = int(parsed.path[1:])  # Remove leading '/'
                except ValueError:
                    logger.warning(
                        f"Invalid database number in Redis URI: {parsed.path}"
                    )
                    config["db"] = 0
            else:
                config["db"] = 0

            # Handle SSL for rediss:// scheme
            if parsed.scheme == "rediss":
                config["ssl"] = True
                config["ssl_check_hostname"] = False
                config["ssl_cert_reqs"] = None

            # Handle Redis Sentinel
            elif parsed.scheme == "redis+sentinel":
                # For Sentinel, we need different handling
                # This is a basic implementation - you might need to extend it
                config["sentinel"] = True
                config["service_name"] = os.getenv(
                    "REDIS_SENTINEL_SERVICE_NAME", "mymaster"
                )

            logger.debug(
                f"Parsed Redis URI successfully: {parsed.scheme}://{config['host']}:{config['port']}/{config['db']}"
            )
            return config

        except Exception as e:
            logger.error(f"Failed to parse Redis URI '{redis_uri}': {e}")
            logger.info("Falling back to individual Redis environment variables")
            return self._get_individual_redis_config()

    def _get_individual_redis_config(self) -> dict:
        """Get Redis configuration from individual environment variables"""
        config = {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", 6379)),
            "db": int(os.getenv("REDIS_DB", 0)),
            "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", 5)),
            "socket_connect_timeout": int(os.getenv("REDIS_CONNECT_TIMEOUT", 5)),
            "socket_keepalive": True,
            "socket_keepalive_options": {},
            "health_check_interval": 30,
        }

        # Add password if provided
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_password:
            config["password"] = redis_password

        # Add username if provided (Redis 6.0+)
        redis_username = os.getenv("REDIS_USERNAME")
        if redis_username:
            config["username"] = redis_username

        # SSL configuration
        if os.getenv("REDIS_SSL", "").lower() in ("true", "1", "yes"):
            config["ssl"] = True
            config["ssl_check_hostname"] = os.getenv(
                "REDIS_SSL_CHECK_HOSTNAME", "false"
            ).lower() in ("true", "1", "yes")

            # SSL certificate files
            ssl_cert_file = os.getenv("REDIS_SSL_CERT_FILE")
            if ssl_cert_file:
                config["ssl_certfile"] = ssl_cert_file
            ssl_key_file = os.getenv("REDIS_SSL_KEY_FILE")
            if ssl_key_file:
                config["ssl_keyfile"] = ssl_key_file

            ssl_ca_file = os.getenv("REDIS_SSL_CA_FILE")
            if ssl_ca_file:
                config["ssl_ca_certs"] = ssl_ca_file

        return config

    def _serialize_value(self, value: Any) -> str:
        """Serialize value for Redis storage with compression support"""
        try:
            # Handle special types that json can't serialize
            if hasattr(value, "__dict__"):
                # Convert objects to dict
                serializable_value = self._make_serializable(value)
            else:
                serializable_value = value

            return json.dumps(
                serializable_value,
                default=str,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except Exception as e:
            logger.warning(f"Failed to serialize cache value: {e}")
            return str(value)

    def _make_serializable(self, obj: Any) -> Any:
        """Convert complex objects to serializable format"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, "__dict__"):
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        else:
            return obj

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from Redis storage"""
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to deserialize cache value: {e}")
            return value
        except Exception as e:
            logger.error(f"Unexpected error deserializing cache value: {e}")
            return None

    def _generate_cache_key(self, key: str) -> str:
        """Generate prefixed cache key for Redis"""
        return f"musseai:cache:{key}"

    def get(self, key: str) -> Optional[Tuple[Any, float]]:
        """Get cached value with timestamp"""
        redis_key = self._generate_cache_key(key)

        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.hgetall(redis_key)
                logger.debug(f"Real key: {redis_key} ")
                if (
                    cached_data
                    and "value" in cached_data
                    and "timestamp" in cached_data
                ):
                    value = self._deserialize_value(cached_data["value"])
                    timestamp = float(cached_data["timestamp"])
                    logger.debug(f"Hits cached Redis: {key} ")
                    return (value, timestamp)
                else:
                    logger.debug(f"Miss cached data: {cached_data}")
            except (ConnectionError, TimeoutError, RedisError) as e:
                logger.warning(f"Redis get failed, falling back to memory: {e}")
                self._setup_redis()  # Try to reconnect
            except Exception as e:
                logger.error(f"Unexpected Redis error: {e}")

        # Fallback to memory cache
        with self.cache_lock:
            return self.memory_cache.get(key)

    def set(self, key: str, value: Any, timestamp: float, duration: int = 3600):
        """Set cached value with timestamp and expiration"""
        redis_key = self._generate_cache_key(key)

        # Try Redis first
        if self.redis_client:
            try:
                serialized_value = self._serialize_value(value)

                # Use pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                pipe.hset(
                    redis_key,
                    mapping={
                        "value": serialized_value,
                        "timestamp": str(timestamp),
                        "duration": str(duration),
                    },
                )
                # Set expiration with buffer time
                pipe.expire(redis_key, duration + 60)  # Extra 60 seconds buffer
                pipe.execute()

                logger.debug(f"Cached to Redis: {key} (expires in {duration}s)")
                logger.debug(f"Real key: {redis_key} (expires in {duration}s)")
                return True

            except (ConnectionError, TimeoutError, RedisError) as e:
                logger.warning(f"Redis set failed, falling back to memory: {e}")
                self._setup_redis()
            except Exception as e:
                logger.error(f"Unexpected Redis error during set: {e}")

        # Fallback to memory cache
        with self.cache_lock:
            self.memory_cache[key] = (value, timestamp)
            logger.debug(f"Cached to memory: {key}")

        return False

    def delete(self, key: str) -> bool:
        """Delete cached value"""
        redis_key = self._generate_cache_key(key)
        deleted = False

        # Delete from Redis
        if self.redis_client:
            try:
                result = self.redis_client.delete(redis_key)
                deleted = bool(result)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        # Delete from memory cache
        with self.cache_lock:
            if key in self.memory_cache:
                del self.memory_cache[key]
                deleted = True

        return deleted

    def clear(self, pattern: str = "*"):
        """Clear cached data by pattern"""
        redis_pattern = f"musseai:cache:{pattern}"

        if self.redis_client:
            try:
                # Use scan for better performance with large datasets
                cursor = 0
                deleted_count = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor=cursor, match=redis_pattern, count=100
                    )
                    if keys:
                        deleted_count += self.redis_client.delete(*keys)
                    if cursor == 0:
                        break

                logger.info(f"Cleared {deleted_count} Redis cache entries")

            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        # Clear memory cache
        with self.cache_lock:
            if pattern == "*":
                cleared_count = len(self.memory_cache)
                self.memory_cache.clear()
                logger.info(f"Cleared {cleared_count} memory cache entries")
            else:
                # Pattern matching for memory cache
                keys_to_delete = [
                    k
                    for k in self.memory_cache.keys()
                    if self._match_pattern(k, pattern)
                ]
                for key in keys_to_delete:
                    del self.memory_cache[key]
                logger.info(
                    f"Cleared {len(keys_to_delete)} memory cache entries matching pattern"
                )

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for memory cache cleanup"""
        if pattern == "*":
            return True
        if "*" not in pattern:
            return key == pattern
        # Simple wildcard matching
        import fnmatch

        return fnmatch.fnmatch(key, pattern)

    def cleanup_expired(self, max_age: float):
        """Clean up expired entries from memory cache"""
        current_time = time.time()
        with self.cache_lock:
            expired_keys = [
                k
                for k, (_, ts) in self.memory_cache.items()
                if current_time - ts >= max_age
            ]
            for key in expired_keys:
                del self.memory_cache[key]

            if expired_keys:
                logger.debug(
                    f"Cleaned up {len(expired_keys)} expired memory cache entries"
                )

    def get_stats(self) -> Dict:
        """Get comprehensive cache statistics"""
        stats = {
            "redis_connected": self.redis_client is not None,
            "memory_cache_size": 0,
            "redis_cache_size": 0,
            "total_memory_usage": 0,
        }

        # Memory cache stats
        with self.cache_lock:
            stats["memory_cache_size"] = len(self.memory_cache)
            # Estimate memory usage
            import sys

            stats["total_memory_usage"] = sum(
                sys.getsizeof(k) + sys.getsizeof(v)
                for k, v in self.memory_cache.items()
            )

        # Redis stats
        if self.redis_client:
            try:
                redis_keys = self.redis_client.keys("musseai:cache:*")
                stats["redis_cache_size"] = len(redis_keys)

                # Redis memory info
                memory_info = self.redis_client.info("memory")
                stats["redis_memory_usage"] = memory_info.get("used_memory", 0)
                stats["redis_memory_human"] = memory_info.get("used_memory_human", "0B")

                # Connection info
                stats["redis_connected_clients"] = self.redis_client.info(
                    "clients"
                ).get("connected_clients", 0)

            except Exception as e:
                stats["redis_error"] = str(e)

        return stats

    def health_check(self) -> Dict:
        """Perform health check on cache backends"""
        health = {
            "redis": {"status": "disconnected", "latency_ms": None},
            "memory": {"status": "ok", "size": 0},
        }

        # Redis health check
        if self.redis_client:
            try:
                start_time = time.time()
                self.redis_client.ping()
                latency = (time.time() - start_time) * 1000  # Convert to milliseconds

                health["redis"] = {
                    "status": "connected",
                    "latency_ms": round(latency, 2),
                }
            except Exception as e:
                health["redis"] = {
                    "status": "error",
                    "error": str(e),
                    "latency_ms": None,
                }

        # Memory cache health
        with self.cache_lock:
            health["memory"]["size"] = len(self.memory_cache)

        return health


# Global cache backend instance
_cache_backend = RedisCacheBackend()
