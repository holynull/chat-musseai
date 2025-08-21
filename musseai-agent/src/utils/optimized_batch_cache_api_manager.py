from datetime import datetime
import threading
import time
from typing import Dict, List,  Optional
from loggers import logger

from utils.api_decorators import api_call_with_cache_and_rate_limit
from utils.batch_cache_api_manager import BatchCacheAPIManager
from utils.redis_cache import _cache_backend

API_CONFIG = {
    "default_cache_duration": 300,  # 5 minutes
    "historical_data_cache": 86400,  # 24 hours for historical data
    "market_data_cache": 300,  # 5 minutes for current market data
    "risk_free_rate_cache": 3600,  # 1 hour for risk-free rate
    "coingecko_rate_limit": 1.2,
    "coincap_rate_limit": 0.1,
    "binance_rate_limit": 0.1,
    "cryptocompare_rate_limit": 0.05,
    "yahoo_rate_limit": 2.0,
    "max_retries": 3,
    "retry_delay": 2,
}


def market_data_api(func):
    """Decorator combination for real-time market data APIs"""
    return api_call_with_cache_and_rate_limit(
        cache_duration=API_CONFIG["market_data_cache"],
        rate_limit_interval=API_CONFIG["coingecko_rate_limit"],
        max_retries=API_CONFIG["max_retries"],
        retry_delay=API_CONFIG["retry_delay"],
    )(func)

class OptimizedBatchCacheAPIManager(BatchCacheAPIManager):
    """Optimized batch cache manager with better cache management"""

    def __init__(self):
        super().__init__()
        self.batch_cache_duration = 86400  # 24 hours
        self.preload_in_progress = False  # Prevent concurrent preloads
        self.last_preload_time = 0
        self.min_preload_interval = 1800  # Minimum 30 minutes between preloads

    def get_cached_data(self, asset_type: str, symbol: str) -> Optional[Dict]:
        """Enhanced cache retrieval supporting multiple data types including chart data"""
        try:
            cache_key = "preload_all_market_data_"
            cached_batch = _cache_backend.get(cache_key)

            current_time = time.time()

            # Check if we should trigger preload
            should_preload = False

            if not cached_batch:
                # Only preload if enough time has passed since last attempt
                if current_time - self.last_preload_time > self.min_preload_interval:
                    should_preload = True
                    logger.info("No batch cache found, scheduling preload...")
                else:
                    logger.debug(
                        f"Batch cache missing but preload attempted recently "
                        f"({current_time - self.last_preload_time:.1f}s ago), skipping"
                    )
                    return None
            else:
                batch_data, timestamp = cached_batch
                cache_age = current_time - timestamp

                # Check if cache is expired
                if cache_age > self.batch_cache_duration:
                    if (
                        current_time - self.last_preload_time
                        > self.min_preload_interval
                    ):
                        should_preload = True
                        logger.info(
                            f"Batch cache expired (age: {cache_age:.1f}s), scheduling refresh..."
                        )
                    else:
                        logger.debug(
                            "Cache expired but refresh attempted recently, using stale data"
                        )
                        # Use stale data rather than trigger frequent reloads
                else:
                    # Cache is valid, return data based on asset_type
                    if asset_type == "crypto" and symbol in batch_data.get(
                        "crypto_prices", {}
                    ):
                        return batch_data["crypto_prices"][symbol]

                    elif asset_type == "traditional":
                        for name, data in batch_data.get(
                            "traditional_assets", {}
                        ).items():
                            if data.get("symbol") == symbol or name == symbol:
                                return data
                        return None

                    elif asset_type == "chart_data":
                        if symbol in batch_data.get("crypto_prices", {}):
                            cached_result = batch_data["crypto_prices"][symbol]
                            if cached_result and cached_result.get("chart_data"):
                                cache_age = current_time - cached_result.get(
                                    "cached_at", 0
                                )

                                # Use cached chart data if less than 30 minutes old (same logic as original)
                                if cache_age < 1800:
                                    logger.info(
                                        f"Chart data cache hit for {symbol} (age: {cache_age:.1f}s)"
                                    )
                                    chart_data = cached_result["chart_data"]

                                    if isinstance(chart_data, dict):
                                        chart_data["cache_hit"] = True
                                        chart_data["cache_age"] = cache_age
                                        chart_data["source"] = (
                                            f"{chart_data.get('source', 'unknown')}_cached"
                                        )

                                    return chart_data
                                else:
                                    logger.debug(
                                        f"Chart data cache expired for {symbol} (age: {cache_age:.1f}s)"
                                    )
                        return None

                # Trigger preload if needed (non-blocking)
                if should_preload and not self.preload_in_progress:
                    self._trigger_background_preload()

                return None

        except Exception as e:
            logger.error(f"Error getting cached data for {asset_type}:{symbol}: {e}")
            return None

    def _trigger_background_preload(self):
        """Trigger preload in background thread to avoid blocking"""

        def background_preload():
            try:
                if self.preload_in_progress:
                    logger.debug("Preload already in progress, skipping")
                    return

                self.preload_in_progress = True
                self.last_preload_time = time.time()

                logger.info("Starting background batch preload...")
                self.preload_all_market_data()
                logger.info("Background batch preload completed")

            except Exception as e:
                logger.error(f"Background preload failed: {e}")
            finally:
                self.preload_in_progress = False

        # Start background thread
        threading.Thread(target=background_preload, daemon=True).start()

    @market_data_api
    def get_asset_current_price(self, symbol: str) -> Dict:
        """
        Get current price for a specific asset with fallback mechanism
        
        Strategy:
        1. Check batch cache first
        2. If cache miss, use multi-API fallback
        3. Return standardized price data format
        
        Args:
            symbol: Asset symbol (e.g., 'BTC', 'ETH')
            
        Returns:
            Dict: Standardized price data with metadata
        """
        logger.info(f"Fetching current price for {symbol}")
        
        # Step 1: Try batch cache
        cached_result = self.get_cached_data("crypto_prices", symbol)
        if cached_result and cached_result.get("market_data"):
            market_data = cached_result["market_data"]
            cache_age = time.time() - cached_result.get("cached_at", 0)
            # Use cached data if less than 5 minutes old
            if cache_age < 300 and "price" in market_data:
                logger.info(f"Cache hit for {symbol} price (age: {cache_age:.1f}s)")
                return {
                    "success": True,
                    "symbol": symbol,
                    "price": market_data["price"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": f"{market_data.get('source', 'unknown')}_cached",
                    "cache_hit": True,
                    "cache_age": cache_age,
                    "market_cap": market_data.get("market_cap"),
                    "volume_24h": market_data.get("volume_24h"),
                    "change_24h": market_data.get("change_24h"),
                }
        
        # Step 2: Cache miss - use multi-API fallback
        logger.info(f"Cache miss for {symbol}, fetching from APIs")
        market_data = self.fetch_market_data(symbol)
        
        if market_data and "price" in market_data:
            return {
                "success": True,
                "symbol": symbol,
                "price": market_data["price"],
                "timestamp": datetime.utcnow().isoformat(),
                "source": market_data.get("source", "multi_api"),
                "cache_hit": False,
                "market_cap": market_data.get("market_cap"),
                "volume_24h": market_data.get("volume_24h"),
                "change_24h": market_data.get("change_24h"),
            }
        
        # Step 3: All methods failed
        logger.error(f"Failed to get price data for {symbol} from all sources")
        return {
            "success": False,
            "symbol": symbol,
            "error": "Failed to fetch price from all available APIs",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    @market_data_api  
    def get_multiple_asset_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get current prices for multiple assets efficiently
        
        Args:
            symbols: List of asset symbols
            
        Returns:
            Dict: Mapping of symbol to price data
        """
        results = {}
        
        for symbol in symbols:
            try:
                price_data = self.get_asset_current_price(symbol)
                results[symbol] = price_data
                
                # Small delay to respect rate limits
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")
                results[symbol] = {
                    "success": False,
                    "symbol": symbol,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
        
        return results
