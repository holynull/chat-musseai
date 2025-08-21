import threading
import time
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from loggers import logger
import traceback
from utils.api_decorators import (
    api_call_with_cache_and_rate_limit,
    cache_result,
    clear_cache,
    get_cache_stats,
)
from utils.cache_refresh_scheduler import CacheRefreshScheduler
from utils.optimized_batch_cache_api_manager import OptimizedBatchCacheAPIManager
from utils.redis_cache import _cache_backend
from utils.smart_cache_invalidator import SmartCacheInvalidator

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


def historical_data_api(func):
    """Decorator combination for historical data APIs"""
    return api_call_with_cache_and_rate_limit(
        cache_duration=API_CONFIG["historical_data_cache"],
        rate_limit_interval=API_CONFIG["coingecko_rate_limit"],
        max_retries=API_CONFIG["max_retries"],
        retry_delay=API_CONFIG["retry_delay"],
    )(func)


def market_data_api(func):
    """Decorator combination for real-time market data APIs"""
    return api_call_with_cache_and_rate_limit(
        cache_duration=API_CONFIG["market_data_cache"],
        rate_limit_interval=API_CONFIG["coingecko_rate_limit"],
        max_retries=API_CONFIG["max_retries"],
        retry_delay=API_CONFIG["retry_delay"],
    )(func)


def fast_api(rate_limit_interval=0.1):
    """Decorator for high-frequency APIs like Binance"""

    def decorator(func):
        return api_call_with_cache_and_rate_limit(
            cache_duration=API_CONFIG["market_data_cache"],
            rate_limit_interval=rate_limit_interval,
            max_retries=API_CONFIG["max_retries"],
            retry_delay=API_CONFIG["retry_delay"],
        )(func)

    return decorator


class EnhancedMultiAPIManager(OptimizedBatchCacheAPIManager):
    """Enhanced API Manager with comprehensive caching strategy"""

    def __init__(self):
        super().__init__()
        # Initialize batch caching components
        self.cache_scheduler = CacheRefreshScheduler(self)
        self.cache_invalidator = SmartCacheInvalidator(self)

        # Start background processes
        self._initialize_caching_system()

    def _initialize_caching_system(self):
        """Initialize the comprehensive caching system"""
        logger.info("Initializing enhanced caching system...")

        try:
            # Warm cache on startup
            threading.Thread(target=self.warm_cache_on_startup, daemon=True).start()

            # Start refresh scheduler
            self.cache_scheduler.start_scheduler()

            # Set up periodic volatility checks
            # threading.Thread(target=self._volatility_monitor_loop, daemon=True).start()

            logger.info("Enhanced caching system initialized successfully")

        except Exception as e:
            logger.error(
                f"Failed to initialize caching system: {e}\n{traceback.format_exc()}"
            )

    def _volatility_monitor_loop(self):
        """Background loop to monitor market volatility"""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                self.cache_invalidator.conditional_cache_refresh()
            except Exception as e:
                logger.error(f"Volatility monitor error: {e}\n{traceback.format_exc()}")
                time.sleep(60)  # Wait 1 minute on error

    # Override key methods to use batch cache
    # def fetch_with_fallback(
    #     self, symbol: str, days: int = 90, max_global_retries: int = None
    # ) -> Optional[Dict]:
    #     """Enhanced fallback with batch cache priority"""
    #     # First try batch cache
    #     result = self.get_cached_data("crypto_prices", symbol)
    #     if result and result.get("historical_data"):
    #         cache_age = time.time() - result.get("cached_at", 0)
    #         if cache_age < 1800:  # 30 minutes freshness
    #             logger.info(f"Batch cache hit for {symbol} (age: {cache_age:.1f}s)")
    #         else:
    #             logger.warning(
    #                 f"Batch cache not hit for {symbol} (age: {cache_age:.1f}s)"
    #             )
    #         return result["historical_data"]
    #     else:
    #         logger.warning(f"No key {symbol} historical_data in the cache.")

    # Fallback to original method
    # logger.info(f"Using individual API fallback for {symbol}")
    # return super().fetch_with_fallback(symbol, days, max_global_retries)

    # @market_data_api
    # def fetch_market_data(self, symbol: str) -> Optional[Dict]:
    #     """
    #     Enhanced fetch_market_data with batch cache priority

    #     Strategy:
    #     1. First check batch cache for recent market data
    #     2. If cache miss or expired, fallback to parent's multi-API method
    #     3. Cache successful results for future use

    #     Args:
    #         symbol: Cryptocurrency symbol or coin ID

    #     Returns:
    #         Dict: Market data in standardized format
    #     """
    #     logger.info(f"Enhanced market data fetch for {symbol}")

    #     # Step 1: Check batch cache first
    #     cached_result = self.get_cached_data("crypto_prices", symbol)
    #     if cached_result and cached_result.get("market_data"):
    #         market_data = cached_result["market_data"]
    #         cache_age = time.time() - cached_result.get("cached_at", 0)

    #         # Use cached data if less than 5 minutes old (300 seconds)
    #         if cache_age < 300:
    #             logger.info(
    #                 f"Batch cache hit for {symbol} market data (age: {cache_age:.1f}s)"
    #             )
    #             # market_data = cached_result["market_data"]
    #             # Add cache metadata
    #             if isinstance(market_data, dict):
    #                 market_data["cache_hit"] = True
    #                 market_data["cache_age"] = cache_age
    #                 market_data["source"] = (
    #                     f"{market_data.get('source', 'unknown')}_cached"
    #                 )
    #         else:
    #             logger.warning(
    #                 f"Batch cache expired for {symbol} (age: {cache_age:.1f}s), fetching fresh data"
    #             )
    #         return market_data
    #     else:
    #         logger.warning(
    #             f"Fetching fresh market data for {symbol} using multi-API fallback"
    #         )

    # Step 2: Cache miss or expired - use parent's multi-API method
    # logger.info(f"Fetching fresh market data for {symbol} using multi-API fallback")

    # return super().fetch_market_data(symbol)

    # @api_call_with_cache_and_rate_limit(
    #     cache_duration=300,
    #     rate_limit_interval=1.2,
    #     max_retries=0,
    #     retry_delay=2,
    # )
    # def get_market_metrics(self, max_global_retries: int = None) -> Optional[Dict]:
    #     """
    #     Enhanced get market metrics with multi-API fallback mechanism similar to fetch_with_fallback

    #     Strategy:
    #     1. First check batch cache for recent market metrics
    #     2. If cache miss or expired, use multi-API fallback approach
    #     3. Try each API in priority order with proper error handling
    #     4. Handle rate limiting and API failures gracefully

    #     Args:
    #         max_global_retries: Maximum global retry attempts (default: 2)

    #     Returns:
    #         Dict: Market metrics data in standardized format
    #     """
    #     if max_global_retries is None:
    #         max_global_retries = self.default_max_global_retries

    #     logger.info("Starting enhanced market metrics fetch with multi-API fallback")

    #     # Step 1: Check batch cache first
    #     cache_key = "preload_all_market_data_"
    #     cached_batch = _cache_backend.get(cache_key)

    #     if cached_batch:
    #         batch_data, timestamp = cached_batch
    #         cache_age = time.time() - timestamp

    #         # Use cached market metrics if less than 5 minutes old
    #         if cache_age < 300 and batch_data.get("global_metrics"):
    #             logger.info(
    #                 f"Batch cache hit for market metrics (age: {cache_age:.1f}s)"
    #             )
    #             metrics = batch_data["global_metrics"]

    #             # Add cache metadata
    #             if isinstance(metrics, dict):
    #                 metrics["cache_hit"] = True
    #                 metrics["cache_age"] = cache_age
    #                 metrics["source"] = f"{metrics.get('source', 'unknown')}_cached"
    #         else:
    #             logger.warning(
    #                 f"Batch cache expired for market metrics (age: {cache_age:.1f}s)"
    #             )
    #         return metrics

    # def fetch_yahoo_finance_data(self, symbol: str, period: str = "1y") -> Dict:
    #     """Enhanced Yahoo Finance with batch cache support"""
    #     # Check batch cache first
    #     result = self.get_cached_data("traditional", symbol)
    #     if result and result.get("data"):
    #         cache_age = time.time() - result.get("cached_at", 0)
    #         if cache_age < 1800:  # 30 minutes freshness
    #             logger.info(
    #                 f"Batch cache hit for Yahoo Finance {symbol} (age: {cache_age:.1f}s)"
    #             )
    #         return result["data"]

    #     # If not in batch cache or expired, use original method with improved caching
    #     logger.info(f"Using individual Yahoo Finance call for {symbol}")
    #     return self.fetch_yahoo_finance_data_optimized(symbol, period)

    # Override the fetch_market_chart_multi_api method to use cache first
    # @api_call_with_cache_and_rate_limit(
    #     cache_duration=1800,
    #     rate_limit_interval=1.2,
    #     max_retries=0,
    #     retry_delay=2,
    # )
    # def fetch_market_chart_multi_api(
    #     self,
    #     symbol: str,
    #     days: str = "30",
    #     interval: str = "daily",
    #     max_global_retries: int = None,
    # ) -> Optional[Dict]:
    #     """
    #     Enhanced fetch market chart data with batch cache priority

    #     Strategy:
    #     1. First check batch cache for recent chart data
    #     2. If cache miss or expired, fallback to original multi-API method
    #     3. Cache successful results for future use

    #     Args:
    #         symbol: Cryptocurrency symbol
    #         days: Number of days of data (default: "30")
    #         interval: Data interval - "daily", "hourly", or "weekly" (default: "daily")
    #         max_global_retries: Maximum global retry attempts

    #     Returns:
    #         Dict: Market chart data in standardized format with prices, market_caps, and total_volumes
    #     """
    #     logger.info(f"Enhanced market chart fetch for {symbol}")
    #     crypto_prices = self.get_cached_data("crypto_prices", symbol)
    #     if crypto_prices and crypto_prices.get("chart_data"):
    #         return crypto_prices["chart_data"]
    #     else:
    #         logger.warning(f"No chart data for symbole {symbol}")
    # Step 2: Cache miss or expired - use original multi-API method
    # logger.info(f"Fetching fresh chart data for {symbol} using multi-API fallback")
    # return super().fetch_market_chart_multi_api(
    #     symbol, days, interval, max_global_retries
    # )

    def get_cache_status(self) -> Dict:
        """Get comprehensive cache status"""
        cache_stats = get_cache_stats()

        # Add batch cache specific stats
        batch_cache_key = "preload_all_market_data_"
        batch_cached = _cache_backend.get(batch_cache_key)

        batch_status = {
            "batch_cache_exists": bool(batch_cached),
            "batch_cache_age": 0,
            "cached_crypto_symbols": 0,
            "cached_traditional_symbols": 0,
        }

        if batch_cached:
            batch_data, timestamp = batch_cached
            batch_status["batch_cache_age"] = time.time() - timestamp
            batch_status["cached_crypto_symbols"] = len(
                batch_data.get("crypto_prices", {})
            )
            batch_status["cached_traditional_symbols"] = len(
                batch_data.get("traditional_assets", {})
            )

        return {
            "redis_cache": cache_stats,
            "batch_cache": batch_status,
            "scheduler_running": self.cache_scheduler.running,
            "last_volatility_check": getattr(
                self.cache_invalidator, "last_check_time", None
            ),
        }

    # @historical_data_api
    def analyze_btc_trend(self, days=30):
        """Analyze Bitcoin price trend using multi-API fallback"""
        # Use existing multi-API historical data method
        btc_data = self.fetch_with_fallback("BTC", days)

        if not btc_data or not btc_data.get("prices"):
            raise ValueError("Failed to fetch Bitcoin data from all APIs")

        prices = btc_data["prices"]

        if len(prices) < 7:
            raise ValueError("Insufficient price data for trend analysis")

        # Calculate key metrics (existing logic)
        current_price = prices[-1]
        week_ago_price = prices[-7] if len(prices) >= 7 else prices[0]
        month_ago_price = prices[0]

        # Calculate percentage changes
        weekly_change = (current_price - week_ago_price) / week_ago_price * 100
        monthly_change = (current_price - month_ago_price) / month_ago_price * 100

        # Calculate moving averages
        ma_7 = sum(prices[-7:]) / min(7, len(prices))
        ma_14 = sum(prices[-14:]) / min(14, len(prices))
        ma_30 = sum(prices) / len(prices)

        # Calculate volatility
        daily_returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1] * 100
            for i in range(1, len(prices))
        ]
        volatility = np.std(daily_returns) if len(daily_returns) > 1 else 0

        # Determine trend
        if current_price > ma_7 > ma_14 > ma_30 and weekly_change > 10:
            trend = "strong_bullish"
        elif current_price > ma_7 > ma_30 and weekly_change > 5:
            trend = "bullish"
        elif current_price < ma_7 < ma_14 < ma_30 and weekly_change < -10:
            trend = "strong_bearish"
        elif current_price < ma_7 < ma_30 and weekly_change < -5:
            trend = "bearish"
        else:
            trend = "sideways"

        return {
            "current_price": current_price,
            "weekly_change": weekly_change,
            "monthly_change": monthly_change,
            "ma_7": ma_7,
            "ma_14": ma_14,
            "ma_30": ma_30,
            "volatility": volatility,
            "trend": trend,
            "source": btc_data.get("source", "multi_api"),
        }

    def get_asset_price_at_date(self, symbol: str, target_date: datetime) -> float:
        """
        Enhanced get asset price at specific date using batch cache data exclusively

        This function now relies entirely on preloaded batch data, eliminating
        redundant API calls and improving performance consistency.

        Args:
            symbol: Asset symbol
            target_date: Target date

        Returns:
            Price at the date, or 0.0 if not available in batch cache
        """
        try:
            logger.info(f"Getting price for {symbol} at {target_date} from batch cache")

            # Step 1: Get preloaded batch data (should already be cached)
            batch_data = self.preload_all_market_data()

            if not batch_data:
                logger.warning("No batch preload data available")
                return 0.0

            # Step 2: Check crypto assets first (most common case)
            crypto_data = batch_data.get("crypto_prices", {}).get(symbol.upper())
            if crypto_data:
                return self._extract_price_from_crypto_cache(
                    crypto_data, target_date, symbol
                )

            # Step 3: Check traditional assets
            traditional_data = self._find_traditional_asset_data(batch_data, symbol)
            if traditional_data:
                return self._extract_price_from_traditional_cache(
                    traditional_data, target_date, symbol
                )

            # Step 4: No data found in batch cache
            logger.warning(f"Symbol {symbol} not found in batch cache")
            return 0.0

        except Exception as e:
            logger.error(
                f"Error getting asset price for {symbol} at {target_date}: {e}"
            )
            logger.debug(traceback.format_exc())
            return 0.0

    def _extract_price_from_crypto_cache(
        self, crypto_data: Dict, target_date: datetime, symbol: str
    ) -> float:
        """Extract price from crypto cache data with validation"""
        try:
            # Check cache freshness
            cache_age = time.time() - crypto_data.get("cached_at", 0)
            if cache_age > 86400:  # 24 hours
                logger.warning(
                    f"Cached crypto data for {symbol} is stale ({cache_age/3600:.1f} hours)"
                )
                return 0.0

            logger.info(
                f"Using fresh cached crypto data for {symbol} (age: {cache_age/60:.1f} minutes)"
            )

            # Try historical data first (most comprehensive)
            historical_data = crypto_data.get("historical_data")
            if historical_data:
                price = self._extract_price_from_cached_data(
                    historical_data, target_date
                )
                if price > 0:
                    logger.info(
                        f"Found price {price} from historical data for {symbol}"
                    )
                    return price

            # Try chart data as fallback
            chart_data = crypto_data.get("chart_data")
            if chart_data:
                price = self._extract_price_from_chart_data(chart_data, target_date)
                if price > 0:
                    logger.info(f"Found price {price} from chart data for {symbol}")
                    return price

            logger.warning(f"No suitable price data found in crypto cache for {symbol}")
            return 0.0

        except Exception as e:
            logger.error(f"Error extracting crypto price for {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return 0.0

    def _find_traditional_asset_data(
        self, batch_data: Dict, symbol: str
    ) -> Optional[Dict]:
        """Find traditional asset data from batch cache with symbol mapping"""
        try:
            traditional_assets = batch_data.get("traditional_assets", {})

            # Direct symbol lookup
            if symbol in traditional_assets:
                return traditional_assets[symbol]

            # Common symbol mappings for traditional assets
            symbol_mappings = {
                "^GSPC": "SP500",
                "^IXIC": "NASDAQ",
                "^DJI": "DOW",
                "^TNX": "10Y_TREASURY",
                "GC=F": "GOLD",
                "DX-Y.NYB": "USD_INDEX",
                "SPY": "SP500",  # ETF equivalents
                "QQQ": "NASDAQ",
                "DIA": "DOW",
            }

            # Try mapped names
            mapped_name = symbol_mappings.get(symbol)
            if mapped_name and mapped_name in traditional_assets:
                return traditional_assets[mapped_name]

            # Reverse mapping (name to symbol)
            reverse_mappings = {v: k for k, v in symbol_mappings.items()}
            if symbol in reverse_mappings:
                mapped_symbol = reverse_mappings[symbol]
                mapped_name = symbol_mappings.get(mapped_symbol)
                if mapped_name and mapped_name in traditional_assets:
                    return traditional_assets[mapped_name]

            return None

        except Exception as e:
            logger.error(f"Error finding traditional asset data for {symbol}: {e}")
            return None

    def _extract_price_from_traditional_cache(
        self, traditional_data: Dict, target_date: datetime, symbol: str
    ) -> float:
        """Extract price from traditional asset cache data"""
        try:
            # Check cache freshness
            cache_age = time.time() - traditional_data.get("cached_at", 0)
            if cache_age > 86400:  # 24 hours
                logger.warning(
                    f"Cached traditional data for {symbol} is stale ({cache_age/3600:.1f} hours)"
                )
                return 0.0

            logger.info(
                f"Using fresh cached traditional data for {symbol} (age: {cache_age/60:.1f} minutes)"
            )

            # Extract Yahoo Finance data
            yahoo_data = traditional_data.get("data")
            if yahoo_data:
                price = self._extract_price_from_yahoo_data(yahoo_data, target_date)
                if price > 0:
                    logger.info(
                        f"Found price {price} from traditional data for {symbol}"
                    )
                    return price

            logger.warning(
                f"No suitable price data found in traditional cache for {symbol}"
            )
            return 0.0

        except Exception as e:
            logger.error(f"Error extracting traditional price for {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return 0.0

    def _extract_price_from_chart_data(
        self, chart_data: Dict, target_date: datetime
    ) -> float:
        """Extract price from chart data format"""
        try:
            if not chart_data or not chart_data.get("success"):
                return 0.0

            target_timestamp = target_date.timestamp()
            closest_price = 0.0
            min_diff = float("inf")

            # Handle different chart data formats
            prices_data = []

            if "prices" in chart_data:
                prices_data = chart_data["prices"]
            elif isinstance(chart_data, dict) and "data" in chart_data:
                prices_data = chart_data["data"]
            else:
                return 0.0

            for price_item in prices_data:
                try:
                    # Handle different chart data formats
                    if isinstance(price_item, dict):
                        if "timestamp" in price_item and "price" in price_item:
                            # Format: {"timestamp": 1234567890000, "price": 45000}
                            price_timestamp = (
                                price_item["timestamp"] / 1000
                            )  # Convert to seconds
                            price_value = price_item["price"]
                        elif "date" in price_item and "price" in price_item:
                            # Format: {"date": "2023-01-01", "price": 45000}
                            if isinstance(price_item["date"], datetime):
                                price_timestamp = price_item["date"].timestamp()
                            elif isinstance(price_item["date"], str):
                                date_obj = datetime.fromisoformat(
                                    price_item["date"].replace("Z", "+00:00")
                                )
                                price_timestamp = date_obj.timestamp()
                            else:
                                continue
                            price_value = price_item["price"]
                        else:
                            continue
                    elif isinstance(price_item, (list, tuple)) and len(price_item) >= 2:
                        # Format: [timestamp, price]
                        price_timestamp = (
                            price_item[0] / 1000
                            if price_item[0] > 1e10
                            else price_item[0]
                        )
                        price_value = price_item[1]
                    else:
                        continue

                    # Find closest timestamp
                    diff = abs(price_timestamp - target_timestamp)
                    if diff < min_diff:
                        min_diff = diff
                        closest_price = float(price_value)

                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"Error processing chart price item: {e}")
                    continue

            return closest_price

        except Exception as e:
            logger.error(f"Error extracting price from chart data: {e}")
            logger.debug(traceback.format_exc())
            return 0.0

    def _extract_price_from_cached_data(
        self, historical_data: Dict, target_date: datetime
    ) -> float:
        """
        Extract price from cached historical data

        Args:
            historical_data: Cached historical data in various formats
            target_date: Target date to find price for

        Returns:
            Price at target date, or 0.0 if not found
        """
        try:
            target_timestamp = target_date.timestamp()
            closest_price = 0.0
            min_diff = float("inf")

            # Handle different cached data formats
            prices_data = []

            if "prices" in historical_data:
                prices_data = historical_data["prices"]
            elif isinstance(historical_data, list):
                prices_data = historical_data
            else:
                logger.warning("Unexpected cached data format")
                return 0.0

            for price_item in prices_data:
                try:
                    # Handle different price item formats
                    if isinstance(price_item, dict):
                        if "timestamp" in price_item:
                            price_timestamp = price_item["timestamp"] / 1000
                            price_value = price_item["price"]
                        elif "date" in price_item:
                            if isinstance(price_item["date"], datetime):
                                price_timestamp = price_item["date"].timestamp()
                            elif isinstance(price_item["date"], str):
                                # Parse date string
                                date_obj = datetime.fromisoformat(
                                    price_item["date"].replace("Z", "+00:00")
                                )
                                price_timestamp = date_obj.timestamp()
                            else:
                                continue
                            price_value = price_item["price"]
                        else:
                            continue
                    elif isinstance(price_item, (list, tuple)) and len(price_item) >= 2:
                        # [timestamp, price] format
                        price_timestamp = (
                            price_item[0] / 1000
                            if price_item[0] > 1e10
                            else price_item[0]
                        )
                        price_value = price_item[1]
                    else:
                        continue

                    diff = abs(price_timestamp - target_timestamp)

                    if diff < min_diff:
                        min_diff = diff
                        closest_price = float(price_value)

                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"Error processing cached price item: {e}")
                    continue

            return closest_price

        except Exception as e:
            logger.error(f"Error extracting price from cached data: {e}")
            logger.debug(traceback.format_exc())
            return 0.0

    def _extract_price_from_yahoo_data(
        self, yahoo_data: Dict, target_date: datetime
    ) -> float:
        """
        Extract price from cached Yahoo Finance data

        Args:
            yahoo_data: Cached Yahoo Finance data
            target_date: Target date to find price for

        Returns:
            Price at target date, or 0.0 if not found
        """
        try:
            if not yahoo_data.get("success") or not yahoo_data.get("prices"):
                return 0.0

            target_timestamp = target_date.timestamp()
            closest_price = 0.0
            min_diff = float("inf")
            for price_item in yahoo_data["prices"]:
                try:
                    if isinstance(price_item, dict):
                        if "timestamp" in price_item:
                            price_timestamp = price_item["timestamp"] / 1000
                            price_value = price_item["price"]
                        elif "date" in price_item:
                            if isinstance(price_item["date"], datetime):
                                price_timestamp = price_item["date"].timestamp()
                            else:
                                continue
                            price_value = price_item["price"]
                        else:
                            continue
                    else:
                        continue

                    diff = abs(price_timestamp - target_timestamp)

                    if diff < min_diff:
                        min_diff = diff
                        closest_price = float(price_value)

                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"Error processing Yahoo price item: {e}")
                    continue

            return closest_price

        except Exception as e:
            logger.error(f"Error extracting price from Yahoo data: {e}")
            logger.debug(traceback.format_exc())
            return 0.0

    # @cache_result(duration=3600)  # 1-hour cache for individual calls
    # def fetch_yahoo_finance_data_optimized(
    #     self, symbol: str, period: str = "1y"
    # ) -> Dict:
    #     """Optimized Yahoo Finance with batch cache support"""
    #     # Check batch cache first
    #     cached_data = self.get_cached_data("traditional", symbol)
    #     if cached_data and cached_data.get("data"):
    #         cache_age = time.time() - cached_data.get("cached_at", 0)
    #         if cache_age < 1800:  # Use cached data if less than 30 minutes old
    #             logger.info(
    #                 f"Using batch cached Yahoo data for {symbol} (age: {cache_age:.1f}s)"
    #             )
    #         return cached_data["data"]

        # If not in batch cache or expired, make individual call
        # return self._fetch_yahoo_finance_individual(symbol, period)

    def get_risk_free_rate(self) -> float:
        """
        Get current risk-free rate from 10-year Treasury yield

        Returns:
            Risk-free rate as decimal (e.g., 0.045 for 4.5%)
        """
        try:
            data = self.fetch_yahoo_finance_data("^TNX", "5d")
            if data and data.get("success") and data.get("prices"):
                latest_yield = data["prices"][-1]["price"]
                return latest_yield / 100  # Convert percentage to decimal
            return 0.045  # Default fallback
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Failed to fetch risk-free rate: {e}")
            return 0.045

    # @api_call_with_cache_and_rate_limit(
    #     cache_duration=86400,  # 24 hours cache
    #     rate_limit_interval=1.2,
    #     max_retries=3,
    #     retry_delay=2,
    # )
    def get_crypto_historical_data(
        self, coin_id: str, vs_currency: str = "usd", days: int = 365
    ) -> Dict:
        """
        Get cryptocurrency historical price data using multi-API fallback mechanism with caching

        Args:
            coin_id: Cryptocurrency ID or symbol
            vs_currency: Base currency for prices
            days: Number of days of historical data

        Returns:
            Dict: Dictionary containing price history data
        """
        symbol = coin_id
        # Extract corresponding symbol for special names like bitcoin, ethereum
        common_names = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "binancecoin": "BNB",
            "ripple": "XRP",
            "cardano": "ADA",
            "solana": "SOL",
            "polkadot": "DOT",
        }

        if coin_id in common_names:
            symbol = common_names[coin_id]

        # Use internal fallback mechanism - no external calls
        result = self.fetch_with_fallback(symbol, days)

        if result and "prices" in result and len(result["prices"]) > 0:
            # Convert to format needed by performance_analysis.py
            prices_data = []
            for i, price in enumerate(result["prices"]):
                if i < len(result["dates"]):
                    date_str = result["dates"][i]
                    try:
                        date_obj = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        logger.debug(traceback.format_exc())
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                    timestamp = int(
                        date_obj.timestamp() * 1000
                    )  # Convert to millisecond timestamp

                    prices_data.append(
                        {"timestamp": timestamp, "date": date_obj, "price": price}
                    )

            response_data = {
                "success": True,
                "coin_id": coin_id,
                "symbol": symbol,
                "prices": prices_data,
                "source": "multi_api_manager",
            }

            return response_data

        # If unable to get data, return failure
        failed_response = {
            "success": False,
            "error": "Could not fetch price data from any available API",
            "coin_id": coin_id,
        }

        return failed_response

    def get_benchmark_price_data(self, benchmark: str, days: int = 365) -> Dict:
        """
        Get price data for benchmark asset with unified fallback mechanism

        Args:
            benchmark: Benchmark symbol
            days: Number of days of data

        Returns:
            Price data dictionary
        """
        # Benchmark mapping
        benchmark_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SP500": "^GSPC",
            "NASDAQ": "^IXIC",
            "GOLD": "GC=F",
            "USD": "DX-Y.NYB",
        }

        if benchmark in ["BTC", "ETH"]:
            coin_id = benchmark_mapping.get(benchmark)
            if coin_id:
                # Try crypto API first
                result = self.get_crypto_historical_data(coin_id, "usd", days)
                if result["success"]:
                    return result
                # If failed, try direct method
                # return self.fetchpri(benchmark, days)
        else:
            symbol = benchmark_mapping.get(benchmark, benchmark)
            return self.fetch_yahoo_finance_data(symbol)

        return {"success": False, "error": f"Unknown benchmark: {benchmark}"}

    def get_daily_benchmark_returns(
        self, benchmark: str, start_date: datetime, end_date: datetime
    ) -> List[float]:
        """
        Get daily benchmark returns for comparison with unified API handling

        Args:
            benchmark: Benchmark symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of daily returns as percentages
        """
        try:
            days_diff = (end_date - start_date).days + 7  # Add buffer
            benchmark_data = self.get_benchmark_price_data(benchmark, days=days_diff)

            if not benchmark_data["success"]:
                return []

            prices = benchmark_data["prices"]
            returns = []

            for i in range(1, len(prices)):
                if prices[i - 1]["price"] > 0:
                    daily_return = (
                        (prices[i]["price"] / prices[i - 1]["price"]) - 1
                    ) * 100
                    returns.append(daily_return)

            return returns

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Error calculating benchmark returns: {e}")
            return []

    # Enhanced batch fetch function
    # @market_data_api
    def fetch_multiple_market_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch market data for multiple symbols using multi-API fallback

        Args:
            symbols: List of cryptocurrency symbols

        Returns:
            Dict: Mapping of symbol to market data
        """
        results = {}

        for symbol in symbols:
            try:
                market_data = self.fetch_market_data(symbol)
                if market_data:
                    results[symbol] = market_data
                else:
                    results[symbol] = {"success": False, "error": "No data available"}

                # Add small delay to respect rate limits
                time.sleep(0.1)

            except Exception as e:
                logger.error(
                    f"Failed to fetch market data for {symbol}: {e}\n{traceback.format_exc()}"
                )
                results[symbol] = {"success": False, "error": str(e)}

        return results

    def force_cache_refresh(self):
        """Manually trigger full cache refresh"""
        logger.info("Manual cache refresh triggered")
        clear_cache("*")
        self.preload_all_market_data()
        logger.info("Manual cache refresh completed")

    def shutdown(self):
        """Graceful shutdown of caching system"""
        logger.info("Shutting down enhanced caching system...")
        self.cache_scheduler.stop_scheduler()
        logger.info("Caching system shutdown completed")


# 替换全局实例
api_manager = EnhancedMultiAPIManager()
