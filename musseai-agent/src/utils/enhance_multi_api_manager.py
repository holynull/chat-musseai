import threading
import time
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from loggers import logger
import traceback
from utils.api_decorators import (
    api_call_with_cache_and_rate_limit,
    APIRateLimitException,
    cache_result,
    clear_cache,
    get_cache_stats,
)
from utils.api_manager import MultiAPIManager
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


class BatchCacheAPIManager(MultiAPIManager):
    """Enhanced batch cache manager with 429 protection"""

    def __init__(self):
        super().__init__()
        self.batch_cache_duration = 86400  # 24 hours for batch data
        self.batch_delay_base = 0.5
        self.batch_delay_max = 10.0
        self.consecutive_429_count = 0
        self.preload_symbols = [
            "BTC",
            "ETH",
            "BNB",
            "ADA",
            "SOL",
            "DOT",
            "LINK",
            "UNI",
            "AAVE",
            "^GSPC",
            "^IXIC",
            "^DJI",
            "^TNX",
            "GC=F",
            "DX-Y.NYB",
        ]

    def warm_cache_on_startup(self):
        """Warm cache on application startup with enhanced 429 protection"""
        try:
            logger.info("Warming cache on startup...")

            # Mark batch operation start
            if hasattr(self, "start_batch_operation"):
                self.start_batch_operation()

            # Preload all market data
            self.preload_all_market_data()

            logger.info("Cache warming completed successfully")

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            logger.debug(traceback.format_exc())
        finally:
            # Mark batch operation end
            if hasattr(self, "end_batch_operation"):
                self.api_manager.end_batch_operation()

    @cache_result(duration=86400)  # 24-hour cache
    def preload_all_market_data(self) -> Dict:
        """Enhanced preload with comprehensive 429 protection"""
        logger.info("Starting batch preload of market data...")

        batch_data = {
            "crypto_prices": {},
            "traditional_assets": {},
            "market_metrics": {},
            "fear_greed_index": None,
            "risk_free_rate": None,
            "timestamp": time.time(),
        }

        # Batch load crypto data with enhanced 429 protection
        crypto_symbols = [
            # Top 10 by market cap
            "BTC",
            "ETH",
            "BNB",
            "XRP",
            "SOL",
            "ADA",
            "DOGE",
            "AVAX",
            "TRX",
            "DOT",
            # DeFi tokens
            "LINK",
            "UNI",
            "AAVE",
            "SUSHI",
            "COMP",
            "MKR",
            "CRV",
            "1INCH",
            # Layer 2 & Scaling
            "MATIC",
            "OP",
            "ARB",
            "LRC",
            "IMX",
            # Meme coins (popular)
            "SHIB",
            "PEPE",
            "FLOKI",
            "BONK",
            # Infrastructure & Utilities
            "ATOM",
            "NEAR",
            "ALGO",
            "VET",
            "FTM",
            "HBAR",
            # Gaming & NFT
            "SAND",
            "MANA",
            "AXS",
            "ENJ",
            "GALA",
            # Stablecoins (for reference)
            "USDT",
            "USDC",
            "BUSD",
            "DAI",
            # Newer projects
            "APT",
            "SUI",
            "OP",
            "ARB",
            "LDO",
            "RPL",
            # Pattener
            "SWFTC",
        ]

        for i, symbol in enumerate(crypto_symbols):
            try:
                # Check if too many APIs are rate limited
                if self._should_pause_batch_operation():
                    logger.warning(
                        "Too many APIs rate limited, pausing batch operation"
                    )
                    time.sleep(60)  # Pause for 1 minute

                # Get both current price and historical data with safe methods
                # Add delay between market data and historical data calls to prevent 429
                market_data = self._safe_fetch_market_data(symbol)

                # CRITICAL: Add delay between the two API calls to prevent 429
                if market_data:
                    # If market data was successful, add a small delay before historical data
                    api_delay = self._calculate_inter_call_delay()
                    logger.debug(f"Inter-call delay for {symbol}: {api_delay}s")
                    time.sleep(api_delay)
                else:
                    # If market data failed, add a longer delay before trying historical data
                    time.sleep(1.0)

                historical_data = self._safe_fetch_historical_data(symbol)

                if market_data or historical_data:
                    batch_data["crypto_prices"][symbol] = {
                        "market_data": market_data,
                        "historical_data": historical_data,
                        "cached_at": time.time(),
                    }

                    # Reset consecutive 429 count on success
                    self.consecutive_429_count = 0
                    logger.info(f"Successfully cached data for {symbol}")
                else:
                    logger.warning(f"Failed to get any data for {symbol}")

                # Dynamic delay based on API response and position in batch
                delay = self._calculate_batch_delay(i, len(crypto_symbols))
                time.sleep(delay)

            except APIRateLimitException as e:
                logger.warning(f"429 error for {symbol}: {e}")
                self.consecutive_429_count += 1

                # Exponential backoff for 429 errors
                backoff_delay = min(2**self.consecutive_429_count, 60)
                logger.info(f"429 backoff: waiting {backoff_delay}s before continuing")
                time.sleep(backoff_delay)
                continue

            except Exception as e:
                logger.warning(f"Failed to preload data for {symbol}: {e}")
                time.sleep(1.0)
                continue

        for i, symbol in enumerate(crypto_symbols):
            try:
                if self._should_pause_batch_operation():
                    logger.warning(
                        "Too many APIs rate limited, pausing batch operation"
                    )
                    time.sleep(60)

                # 1. Get current market data
                market_data = self._safe_fetch_market_data(symbol)

                # Add delay between calls
                if market_data:
                    api_delay = self._calculate_inter_call_delay()
                    time.sleep(api_delay)
                else:
                    time.sleep(1.0)

                # 2. Get historical data
                historical_data = self._safe_fetch_historical_data(symbol)

                # Add delay before chart data
                time.sleep(self._calculate_inter_call_delay())

                # 3. NEW: Get market chart data
                chart_data = self._safe_fetch_market_chart_data(symbol)

                # Store all data together
                if market_data or historical_data or chart_data:
                    batch_data["crypto_prices"][symbol] = {
                        "market_data": market_data,
                        "historical_data": historical_data,
                        "chart_data": chart_data,  # 新增图表数据
                        "cached_at": time.time(),
                    }

                    # Reset consecutive 429 count on success
                    self.consecutive_429_count = 0
                    logger.info(f"Successfully cached all data for {symbol}")
                else:
                    logger.warning(f"Failed to get any data for {symbol}")

                    # Dynamic delay based on API response and position in batch
                    delay = self._calculate_batch_delay(i, len(crypto_symbols))
                    time.sleep(delay)

            except APIRateLimitException as e:
                logger.warning(f"429 error for {symbol}: {e}")
                self.consecutive_429_count += 1

                # Exponential backoff for 429 errors
                backoff_delay = min(2**self.consecutive_429_count, 60)
                logger.info(f"429 backoff: waiting {backoff_delay}s before continuing")
                time.sleep(backoff_delay)
                continue

            except Exception as e:
                logger.warning(f"Failed to preload data for {symbol}: {e}")
                time.sleep(1.0)
                continue

        # Load traditional assets with 429 protection
        self._preload_traditional_assets_safe(batch_data)

        # Load market metrics with 429 protection
        self._preload_market_metrics_safe(batch_data)

        # Load market metrics with 429 protection
        self._preload_market_metrics_safe(batch_data)

        # 新增：加载全局市场指标
        self._preload_global_metrics_safe(batch_data)

        logger.info(
            f"Batch preload completed. Cached {len(batch_data['crypto_prices'])} "
            f"crypto assets and {len(batch_data['traditional_assets'])} traditional assets"
        )
        return batch_data

    def _preload_global_metrics_safe(self, batch_data: Dict):
        """Safely preload global market metrics with enhanced 429 protection"""
        try:
            # Add delay before global metrics call
            time.sleep(1.0)

            batch_data["global_metrics"] = self._safe_get_global_metrics()

        except Exception as e:
            logger.warning(f"Failed to load global metrics: {e}")
            # Set fallback values
            batch_data["global_metrics"] = {}

    @market_data_api
    def _safe_get_global_metrics(self) -> Dict:
        """Safely get global market metrics with enhanced timeout and 429 handling"""
        try:
            return self.get_market_metrics()
        except APIRateLimitException as e:
            logger.debug(f"Global metrics rate limited: {e}")
            self.consecutive_429_count += 1
            return {}
        except Exception as e:
            logger.debug(f"Global metrics fetch failed: {e}")
            return {}

    def _safe_fetch_market_chart_data(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """Safely fetch market chart data with enhanced 429 handling"""
        try:
            return self.fetch_market_chart_multi_api(symbol, days, interval)
        except APIRateLimitException as e:
            logger.debug(f"Market chart data fetch rate limited for {symbol}: {e}")
            # Mark this as a 429 occurrence for delay calculation
            self.consecutive_429_count += 1
            return None
        except Exception as e:
            logger.debug(f"Market chart data fetch failed for {symbol}: {e}")
            return None

    def _calculate_inter_call_delay(self) -> float:
        """Calculate delay between market_data and historical_data calls for same symbol"""
        base_delay = 0.5  # 500ms base delay

        # Increase delay based on recent 429 errors
        if self.consecutive_429_count > 0:
            # Exponential increase: 0.5s -> 1s -> 2s -> 4s (max)
            multiplier = min(2**self.consecutive_429_count, 8)
            calculated_delay = base_delay * multiplier
        else:
            calculated_delay = base_delay

        # Check current API rate limit status
        rate_limited_apis = sum(
            1 for api in self.apis.keys() if self._is_api_rate_limited(api)
        )
        total_apis = len(self.apis)

        if total_apis > 0:
            rate_limited_ratio = rate_limited_apis / total_apis
            if rate_limited_ratio > 0.3:  # More than 30% APIs are rate limited
                calculated_delay *= 2  # Double the delay

        # Cap the maximum delay
        return min(calculated_delay, 5.0)  # Maximum 5 seconds between calls

    @market_data_api
    def _safe_fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """Safely fetch market data with enhanced 429 handling"""
        try:
            return super().fetch_market_data(symbol)
        except APIRateLimitException as e:
            logger.debug(f"Market data fetch rate limited for {symbol}: {e}")
            # Mark this as a 429 occurrence for delay calculation
            self.consecutive_429_count += 1
            return None
        except Exception as e:
            logger.debug(f"Market data fetch failed for {symbol}: {e}")
            return None

    def _safe_fetch_historical_data(self, symbol: str) -> Optional[Dict]:
        """Safely fetch historical data with enhanced 429 handling"""
        try:
            return super().fetch_with_fallback(symbol, days=365)
        except APIRateLimitException as e:
            logger.debug(f"Historical data fetch rate limited for {symbol}: {e}")
            # Mark this as a 429 occurrence for delay calculation
            self.consecutive_429_count += 1
            return None
        except Exception as e:
            logger.debug(f"Historical data fetch failed for {symbol}: {e}")
            return None

    def _should_pause_batch_operation(self) -> bool:
        """Enhanced check if batch operation should be paused due to too many 429s"""
        rate_limited_count = len(getattr(self, "rate_limited_apis", {}))
        disabled_count = len(getattr(self, "disabled_apis", {}))
        total_apis = len(getattr(self, "apis", {}))

        if total_apis == 0:
            return False

        # Pause if more than 60% of APIs are rate limited or disabled
        unavailable_ratio = (rate_limited_count + disabled_count) / total_apis
        should_pause = unavailable_ratio > 0.6

        if should_pause:
            logger.warning(
                f"Pausing batch operation: {rate_limited_count} rate limited, "
                f"{disabled_count} disabled out of {total_apis} total APIs "
                f"(unavailable ratio: {unavailable_ratio:.1%})"
            )

        return should_pause

    def _calculate_batch_delay(self, current_index: int, total_symbols: int) -> float:
        """Enhanced dynamic delay calculation for batch operations"""
        base_delay = self.batch_delay_base

        # Increase delay if we've had recent 429s
        if self.consecutive_429_count > 0:
            base_delay *= 1.5 ** min(self.consecutive_429_count, 5)

        # Increase delay as we progress through batch to be more conservative
        progress_factor = 1 + (current_index / total_symbols) * 0.5
        calculated_delay = base_delay * progress_factor

        # Additional delay based on API availability
        available_apis = sum(
            1 for api in self.apis.keys() if self._is_api_available(api)
        )
        total_apis = len(self.apis)

        if total_apis > 0:
            availability_ratio = available_apis / total_apis
            if availability_ratio < 0.5:  # Less than 50% APIs available
                calculated_delay *= 2  # Double the delay when APIs are struggling

        return min(calculated_delay, self.batch_delay_max)

    def _preload_traditional_assets_safe(self, batch_data: Dict):
        """Safely preload traditional assets with enhanced 429 protection"""
        traditional_symbols = {
            "^GSPC": "SP500",
            "^IXIC": "NASDAQ",
            "^DJI": "DOW",
            "^TNX": "10Y_TREASURY",
            "GC=F": "GOLD",
            "DX-Y.NYB": "USD_INDEX",
        }

        for i, (symbol, name) in enumerate(traditional_symbols.items()):
            try:
                if self._should_pause_batch_operation():
                    logger.warning(
                        "Pausing traditional assets loading due to rate limits"
                    )
                    time.sleep(30)

                # Yahoo Finance data with enhanced error handling
                data = self._safe_fetch_yahoo_data(symbol)
                if data and data.get("success"):
                    batch_data["traditional_assets"][name] = {
                        "data": data,
                        "symbol": symbol,
                        "cached_at": time.time(),
                    }
                    logger.info(f"Successfully cached {name} ({symbol})")

                # Yahoo Finance needs longer delays due to stricter rate limiting
                yahoo_delay = max(
                    2.0,  # Minimum 2 seconds for Yahoo Finance
                    self._calculate_batch_delay(i, len(traditional_symbols)),
                )
                time.sleep(yahoo_delay)

            except Exception as e:
                logger.warning(f"Failed to preload {name} ({symbol}): {e}")
                time.sleep(2.0)
                continue

    def _safe_fetch_yahoo_data(self, symbol: str) -> Optional[Dict]:
        """Safely fetch Yahoo Finance data with 429 protection"""
        try:
            return self.fetch_yahoo_finance_data(symbol, "1y")
        except APIRateLimitException as e:
            logger.debug(f"Yahoo Finance rate limited for {symbol}: {e}")
            self.consecutive_429_count += 1
            return None
        except Exception as e:
            logger.debug(f"Yahoo Finance fetch failed for {symbol}: {e}")
            return None

    def _preload_market_metrics_safe(self, batch_data: Dict):
        """Safely preload market metrics with enhanced 429 protection"""
        try:
            # Add delays between different metric calls
            batch_data["market_metrics"] = self._safe_get_market_metrics()
            time.sleep(1.0)  # Delay between metric calls

            batch_data["fear_greed_index"] = self._safe_get_fear_greed_index()
            time.sleep(1.0)  # Delay between metric calls

            batch_data["risk_free_rate"] = self._safe_get_risk_free_rate()

        except Exception as e:
            logger.warning(f"Failed to load market metrics: {e}")
            # Set fallback values
            batch_data["market_metrics"] = {}
            batch_data["fear_greed_index"] = (50, "Neutral", "sideways", "neutral")
            batch_data["risk_free_rate"] = 0.045

    @market_data_api
    def _safe_get_market_metrics(self) -> Dict:
        """Safely get market metrics with enhanced timeout and 429 handling"""
        try:
            return self.get_market_metrics()
        except APIRateLimitException as e:
            logger.debug(f"Market metrics rate limited: {e}")
            self.consecutive_429_count += 1
            return {}
        except Exception as e:
            logger.debug(f"Market metrics fetch failed: {e}")
            return {}

    def _safe_get_fear_greed_index(self):
        """Safely get fear & greed index with enhanced timeout and 429 handling"""
        try:
            return self.get_fear_greed_index()
        except APIRateLimitException as e:
            logger.debug(f"Fear & greed index rate limited: {e}")
            self.consecutive_429_count += 1
            return (50, "Neutral", "sideways", "neutral")
        except Exception as e:
            logger.debug(f"Fear & greed index fetch failed: {e}")
            return (50, "Neutral", "sideways", "neutral")

    def _safe_get_risk_free_rate(self) -> float:
        """Safely get risk-free rate with enhanced timeout and 429 handling"""
        try:
            return self.get_risk_free_rate()
        except APIRateLimitException as e:
            logger.debug(f"Risk-free rate rate limited: {e}")
            self.consecutive_429_count += 1
            return 0.045
        except Exception as e:
            logger.debug(f"Risk-free rate fetch failed: {e}")
            return 0.045

    @market_data_api
    def _safe_fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """Safely fetch market data with 429 handling"""
        try:
            return super().fetch_market_data(symbol)
        except APIRateLimitException:
            logger.debug(
                f"Market data fetch rate limited for {symbol}\n{traceback.format_exc()}"
            )
            return None
        except Exception as e:
            logger.debug(
                f"Market data fetch failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            return None

    def _safe_fetch_historical_data(self, symbol: str) -> Optional[Dict]:
        """Safely fetch historical data with 429 handling"""
        try:
            return super().fetch_with_fallback(symbol, days=365)
        except APIRateLimitException:
            logger.debug(
                f"Historical data fetch rate limited for {symbol}\n{traceback.format_exc()}"
            )
            return None
        except Exception as e:
            logger.debug(
                f"Historical data fetch failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            return None

    def _should_pause_batch_operation(self) -> bool:
        """Check if batch operation should be paused due to too many 429s"""
        rate_limited_count = len(getattr(self, "rate_limited_apis", {}))
        total_apis = len(getattr(self, "apis", {}))

        if total_apis == 0:
            return False

        # Pause if more than 50% of APIs are rate limited
        return rate_limited_count > (total_apis * 0.5)

    def _calculate_batch_delay(self, current_index: int, total_symbols: int) -> float:
        """Calculate dynamic delay based on batch progress and recent 429s"""
        base_delay = self.batch_delay_base

        # Increase delay if we've had recent 429s
        if self.consecutive_429_count > 0:
            base_delay *= 1.5 ** min(self.consecutive_429_count, 5)

        # Increase delay as we progress through batch
        progress_factor = 1 + (current_index / total_symbols) * 0.5
        calculated_delay = base_delay * progress_factor

        return min(calculated_delay, self.batch_delay_max)

    def _preload_traditional_assets_safe(self, batch_data: Dict):
        """Safely preload traditional assets with enhanced 429 protection"""
        traditional_symbols = {
            "^GSPC": "SP500",
            "^IXIC": "NASDAQ",
            "^DJI": "DOW",
            "^TNX": "10Y_TREASURY",
            "GC=F": "GOLD",
            "DX-Y.NYB": "USD_INDEX",
        }

        for i, (symbol, name) in enumerate(traditional_symbols.items()):
            try:
                if self._should_pause_batch_operation():
                    logger.warning(
                        "Pausing traditional assets loading due to rate limits"
                    )
                    time.sleep(30)

                data = self.fetch_yahoo_finance_data(symbol, "1y")
                if data and data.get("success"):
                    batch_data["traditional_assets"][name] = {
                        "data": data,
                        "symbol": symbol,
                        "cached_at": time.time(),
                    }
                    logger.info(f"Successfully cached {name} ({symbol})")

                # Yahoo Finance needs longer delays
                yahoo_delay = max(
                    1.0, self._calculate_batch_delay(i, len(traditional_symbols))
                )
                time.sleep(yahoo_delay)

            except Exception as e:
                logger.warning(
                    f"Failed to preload {name} ({symbol}): {e}\n{traceback.format_exc()}"
                )
                time.sleep(2.0)
                continue

    def _preload_market_metrics_safe(self, batch_data: Dict):
        """Safely preload market metrics with 429 protection"""
        try:
            batch_data["market_metrics"] = self._safe_get_market_metrics()
            batch_data["fear_greed_index"] = self._safe_get_fear_greed_index()
            batch_data["risk_free_rate"] = self._safe_get_risk_free_rate()
        except Exception as e:
            logger.warning(
                f"Failed to load market metrics: {e}\n{traceback.format_exc()}"
            )
            # Set fallback values
            batch_data["market_metrics"] = {}
            batch_data["fear_greed_index"] = (50, "Neutral", "sideways", "neutral")
            batch_data["risk_free_rate"] = 0.045

    @market_data_api
    def get_fear_greed_index(self):
        """Get Fear & Greed Index with multi-API fallback"""
        api_methods = [
            ("alternative_me", self._fetch_fear_greed_alternative),
            # ("coinmarketcap", self._fetch_fear_greed_cmc),  # If available
        ]

        for api_name, api_method in api_methods:
            try:
                result = api_method()
                if result:
                    return result
            except Exception as e:
                logger.warning(
                    f"Fear & Greed API {api_name} failed: {e}\n{traceback.format_exc()}"
                )
                continue

        # Fallback to estimated values based on market conditions
        return self._estimate_fear_greed_from_market()

    @market_data_api
    def get_real_defi_yields(self) -> Dict:
        """Fetch real DeFi yields from multiple protocols with fallback"""
        yields = {}

        # Define yield sources in priority order
        yield_sources = [
            ("aave", self._fetch_aave_yields),
            ("compound", self._fetch_compound_yields),
            ("defi_pulse", self._fetch_defi_pulse_yields),
            ("fallback", self._get_fallback_yields),
        ]

        for source_name, fetch_method in yield_sources:
            try:
                source_yields = fetch_method()
                if source_yields:
                    yields.update(source_yields)
                    logger.info(f"Successfully fetched yields from {source_name}")
                    break  # Use first successful source
            except Exception as e:
                logger.warning(
                    f"DeFi yields source {source_name} failed: {e}\n{traceback.format_exc()}"
                )
                continue

        return yields if yields else self._get_fallback_yields()

    @market_data_api
    def _safe_get_market_metrics(self) -> Dict:
        """Safely get market metrics with timeout"""
        try:
            return self.get_market_metrics()
        except Exception as e:
            logger.debug(f"Market metrics fetch failed: {e}\n{traceback.format_exc()}")
            return {}

    def _safe_get_fear_greed_index(self):
        """Safely get fear & greed index with timeout"""
        try:
            return self.get_fear_greed_index()
        except Exception as e:
            logger.debug(
                f"Fear & greed index fetch failed: {e}\n{traceback.format_exc()}"
            )
            return (50, "Neutral", "sideways", "neutral")

    def _safe_get_risk_free_rate(self) -> float:
        """Safely get risk-free rate with timeout"""
        try:
            return self.get_risk_free_rate()
        except Exception as e:
            logger.debug(f"Risk-free rate fetch failed: {e}\n{traceback.format_exc()}")
            return 0.045

    def get_cached_data(self, asset_type: str, symbol: str) -> Optional[Dict]:
        """Get data from batch cache with enhanced error handling"""
        raise NotImplemented("No Implemented")


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


class CacheRefreshScheduler:
    """Background scheduler for cache refresh"""

    def __init__(self, batch_cache_manager):
        self.batch_cache_manager = batch_cache_manager
        self.scheduler_thread = None
        self.running = False

    def start_scheduler(self):
        """Start background cache refresh scheduler"""
        if self.running:
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Cache refresh scheduler started")

    def stop_scheduler(self):
        """Stop background scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Cache refresh scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Refresh every 4 hours
                time.sleep(4 * 3600)

                if self.running:
                    logger.info("Starting scheduled cache refresh...")
                    self.batch_cache_manager.preload_all_market_data()
                    logger.info("Scheduled cache refresh completed")

            except Exception as e:
                logger.error(
                    f"Scheduled cache refresh failed: {e}\n{traceback.format_exc()}"
                )
                # Continue running even if refresh fails
                time.sleep(300)  # Wait 5 minutes before retrying


class SmartCacheInvalidator:
    """Smart cache invalidation based on market conditions"""

    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.last_btc_price = None
        self.volatility_threshold = 0.05  # 5% price change triggers refresh

    def should_invalidate_cache(self) -> bool:
        """Check if cache should be invalidated due to high volatility"""
        try:
            # Get current BTC price as market indicator
            current_btc_data = self.api_manager.fetch_market_data("BTC")
            if not current_btc_data:
                return False

            current_price = current_btc_data.get("current_price", 0)

            if self.last_btc_price is None:
                self.last_btc_price = current_price
                return False

            # Calculate price change
            price_change = (
                abs(current_price - self.last_btc_price) / self.last_btc_price
            )

            if price_change > self.volatility_threshold:
                logger.info(
                    f"High volatility detected: {price_change:.2%} BTC price change, invalidating cache"
                )
                self.last_btc_price = current_price
                return True

            return False

        except Exception as e:
            logger.warning(
                f"Failed to check market volatility: {e}\n{traceback.format_exc()}"
            )
            return False

    def conditional_cache_refresh(self):
        """Refresh cache only if market conditions warrant it"""
        if self.should_invalidate_cache():
            logger.info("Triggering conditional cache refresh due to market volatility")
            # Clear existing cache
            clear_cache("*market*")
            # Trigger fresh data load
            self.api_manager.batch_cache_manager.preload_all_market_data()


class EnhancedMultiAPIManager(OptimizedBatchCacheAPIManager):
    """Enhanced API Manager with comprehensive caching strategy"""

    def __init__(self):
        super().__init__()
        # Initialize batch caching components
        self.cache_scheduler = CacheRefreshScheduler(self)
        self.cache_invalidator = SmartCacheInvalidator(self)

        # Start background processes
        # self._initialize_caching_system()

    def _initialize_caching_system(self):
        """Initialize the comprehensive caching system"""
        logger.info("Initializing enhanced caching system...")

        try:
            # Warm cache on startup
            threading.Thread(target=self.warm_cache_on_startup, daemon=True).start()

            # Start refresh scheduler
            self.cache_scheduler.start_scheduler()

            # Set up periodic volatility checks
            threading.Thread(target=self._volatility_monitor_loop, daemon=True).start()

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
    def fetch_with_fallback(
        self, symbol: str, days: int = 90, max_global_retries: int = None
    ) -> Optional[Dict]:
        """Enhanced fallback with batch cache priority"""
        # First try batch cache
        result = self.get_cached_data("crypto_prices", symbol)
        if result and result.get("historical_data"):
            cache_age = time.time() - result.get("cached_at", 0)
            if cache_age < 1800:  # 30 minutes freshness
                logger.info(f"Batch cache hit for {symbol} (age: {cache_age:.1f}s)")
            else:
                logger.warning(
                    f"Batch cache not hit for {symbol} (age: {cache_age:.1f}s)"
                )
            return result["historical_data"]
        else:
            logger.warning(f"No key {symbol} historical_data in the cache.")

        # Fallback to original method
        # logger.info(f"Using individual API fallback for {symbol}")
        # return super().fetch_with_fallback(symbol, days, max_global_retries)

    # @market_data_api
    def fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Enhanced fetch_market_data with batch cache priority

        Strategy:
        1. First check batch cache for recent market data
        2. If cache miss or expired, fallback to parent's multi-API method
        3. Cache successful results for future use

        Args:
            symbol: Cryptocurrency symbol or coin ID

        Returns:
            Dict: Market data in standardized format
        """
        logger.info(f"Enhanced market data fetch for {symbol}")

        # Step 1: Check batch cache first
        cached_result = self.get_cached_data("crypto_prices", symbol)
        if cached_result and cached_result.get("market_data"):
            market_data = cached_result["market_data"]
            cache_age = time.time() - cached_result.get("cached_at", 0)

            # Use cached data if less than 5 minutes old (300 seconds)
            if cache_age < 300:
                logger.info(
                    f"Batch cache hit for {symbol} market data (age: {cache_age:.1f}s)"
                )
                # market_data = cached_result["market_data"]
                # Add cache metadata
                if isinstance(market_data, dict):
                    market_data["cache_hit"] = True
                    market_data["cache_age"] = cache_age
                    market_data["source"] = (
                        f"{market_data.get('source', 'unknown')}_cached"
                    )
            else:
                logger.warning(
                    f"Batch cache expired for {symbol} (age: {cache_age:.1f}s), fetching fresh data"
                )
            return market_data
        else:
            logger.warning(
                f"Fetching fresh market data for {symbol} using multi-API fallback"
            )

        # Step 2: Cache miss or expired - use parent's multi-API method
        # logger.info(f"Fetching fresh market data for {symbol} using multi-API fallback")

        # return super().fetch_market_data(symbol)

    # @api_call_with_cache_and_rate_limit(
    #     cache_duration=300,
    #     rate_limit_interval=1.2,
    #     max_retries=0,
    #     retry_delay=2,
    # )
    def get_market_metrics(self, max_global_retries: int = None) -> Optional[Dict]:
        """
        Enhanced get market metrics with multi-API fallback mechanism similar to fetch_with_fallback

        Strategy:
        1. First check batch cache for recent market metrics
        2. If cache miss or expired, use multi-API fallback approach
        3. Try each API in priority order with proper error handling
        4. Handle rate limiting and API failures gracefully

        Args:
            max_global_retries: Maximum global retry attempts (default: 2)

        Returns:
            Dict: Market metrics data in standardized format
        """
        if max_global_retries is None:
            max_global_retries = self.default_max_global_retries

        logger.info("Starting enhanced market metrics fetch with multi-API fallback")

        # Step 1: Check batch cache first
        cache_key = "preload_all_market_data_"
        cached_batch = _cache_backend.get(cache_key)

        if cached_batch:
            batch_data, timestamp = cached_batch
            cache_age = time.time() - timestamp

            # Use cached market metrics if less than 5 minutes old
            if cache_age < 300 and batch_data.get("global_metrics"):
                logger.info(
                    f"Batch cache hit for market metrics (age: {cache_age:.1f}s)"
                )
                metrics = batch_data["global_metrics"]

                # Add cache metadata
                if isinstance(metrics, dict):
                    metrics["cache_hit"] = True
                    metrics["cache_age"] = cache_age
                    metrics["source"] = f"{metrics.get('source', 'unknown')}_cached"
            else:
                logger.warning(
                    f"Batch cache expired for market metrics (age: {cache_age:.1f}s)"
                )
            return metrics

    def fetch_yahoo_finance_data(self, symbol: str, period: str = "1y") -> Dict:
        """Enhanced Yahoo Finance with batch cache support"""
        # Check batch cache first
        result = self.get_cached_data("traditional", symbol)
        if result and result.get("data"):
            cache_age = time.time() - result.get("cached_at", 0)
            if cache_age < 1800:  # 30 minutes freshness
                logger.info(
                    f"Batch cache hit for Yahoo Finance {symbol} (age: {cache_age:.1f}s)"
                )
            return result["data"]

        # If not in batch cache or expired, use original method with improved caching
        logger.info(f"Using individual Yahoo Finance call for {symbol}")
        return self.fetch_yahoo_finance_data_optimized(symbol, period)

    # Override the fetch_market_chart_multi_api method to use cache first
    # @api_call_with_cache_and_rate_limit(
    #     cache_duration=1800,
    #     rate_limit_interval=1.2,
    #     max_retries=0,
    #     retry_delay=2,
    # )
    def fetch_market_chart_multi_api(
        self,
        symbol: str,
        days: str = "30",
        interval: str = "daily",
        max_global_retries: int = None,
    ) -> Optional[Dict]:
        """
        Enhanced fetch market chart data with batch cache priority

        Strategy:
        1. First check batch cache for recent chart data
        2. If cache miss or expired, fallback to original multi-API method
        3. Cache successful results for future use

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days of data (default: "30")
            interval: Data interval - "daily", "hourly", or "weekly" (default: "daily")
            max_global_retries: Maximum global retry attempts

        Returns:
            Dict: Market chart data in standardized format with prices, market_caps, and total_volumes
        """
        logger.info(f"Enhanced market chart fetch for {symbol}")
        crypto_prices = self.get_cached_data("crypto_prices", symbol)
        if crypto_prices and crypto_prices.get("chart_data"):
            return crypto_prices["chart_data"]
        else:
            logger.warning(f"No chart data for symbole {symbol}")
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
        Enhanced get asset price at specific date with batch cache priority

        Strategy:
        1. First check batch cache for historical data
        2. If cache hit, use cached data for price lookup
        3. If cache miss, fallback to individual API calls
        4. Support both crypto and traditional assets

        Args:
            symbol: Asset symbol
            target_date: Target date

        Returns:
            Price at the date
        """
        try:
            logger.info(f"Getting price for {symbol} at {target_date}")

            # Step 1: Check if it's crypto or traditional asset
            crypto_symbols = [
                "BTC",
                "ETH",
                "ADA",
                "DOT",
                "LINK",
                "UNI",
                "AAVE",
                "SOL",
                "BNB",
                "XRP",
                "DOGE",
                "AVAX",
                "MATIC",
                "ATOM",
                "NEAR",
            ]

            is_crypto = symbol.upper() in crypto_symbols

            # Step 2: Try batch cache first
            if is_crypto:
                cached_result = self.get_cached_data("crypto_prices", symbol)
                if cached_result and cached_result.get("historical_data"):
                    cache_age = time.time() - cached_result.get("cached_at", 0)

                    # Use cached data if less than 1 hour old
                    if cache_age < 3600:
                        logger.info(
                            f"Using batch cached historical data for {symbol} (age: {cache_age:.1f}s)"
                        )
                        historical_data = cached_result["historical_data"]

                        # Extract price at target date from cached data
                        price = self._extract_price_from_cached_data(
                            historical_data, target_date
                        )
                        if price > 0:
                            return price
                        else:
                            logger.warning(
                                f"Could not find price for {symbol} at {target_date} in cached data"
                            )
                    else:
                        logger.debug(
                            f"Cached data too old for {symbol} (age: {cache_age:.1f}s)"
                        )
            else:
                # Traditional asset - check batch cache
                cached_result = self.get_cached_data("traditional", symbol)
                if cached_result and cached_result.get("data"):
                    cache_age = time.time() - cached_result.get("cached_at", 0)

                    # Use cached data if less than 1 hour old
                    if cache_age < 3600:
                        logger.info(
                            f"Using batch cached traditional data for {symbol} (age: {cache_age:.1f}s)"
                        )
                        traditional_data = cached_result["data"]

                        # Extract price from traditional asset data
                        price = self._extract_price_from_yahoo_data(
                            traditional_data, target_date
                        )
                        if price > 0:
                            return price
                        else:
                            logger.warning(
                                f"Could not find price for {symbol} at {target_date} in cached traditional data"
                            )
                    else:
                        logger.debug(
                            f"Cached traditional data too old for {symbol} (age: {cache_age:.1f}s)"
                        )

            # Step 3: Cache miss or expired - fallback to individual API calls
            logger.info(f"Cache miss for {symbol}, using individual API calls")

            if is_crypto:
                # Map symbol to coin_id for crypto assets
                coin_mapping = {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "ADA": "cardano",
                    "DOT": "polkadot",
                    "LINK": "chainlink",
                    "UNI": "uniswap",
                    "AAVE": "aave",
                    "SOL": "solana",
                    "BNB": "binancecoin",
                    "XRP": "ripple",
                    "DOGE": "dogecoin",
                    "AVAX": "avalanche-2",
                    "MATIC": "polygon",
                    "ATOM": "cosmos",
                    "NEAR": "near",
                }
                coin_id = coin_mapping.get(symbol.upper(), symbol.lower())

                # Try multi-API approach for crypto
                data = self.get_crypto_historical_data(coin_id, "usd", 90)

                # If multi-API failed, try direct fallback method
                if not data.get("success"):
                    logger.warning(
                        f"Multi-API crypto fetch failed for {symbol}, trying direct fallback"
                    )
                    data = self.fetch_with_fallback(symbol, 90)
                    if data and "prices" in data:
                        # Convert format to match expected structure
                        prices_data = []
                        for i, price in enumerate(data["prices"]):
                            if i < len(data.get("dates", [])):
                                date_str = data["dates"][i]
                                try:
                                    # Handle different date formats
                                    if isinstance(date_str, str):
                                        if "T" in date_str:
                                            date_obj = datetime.fromisoformat(
                                                date_str.replace("Z", "+00:00")
                                            )
                                        else:
                                            date_obj = datetime.strptime(
                                                date_str, "%Y-%m-%d"
                                            )
                                    else:
                                        continue

                                    timestamp = int(date_obj.timestamp() * 1000)
                                    prices_data.append(
                                        {
                                            "timestamp": timestamp,
                                            "date": date_obj,
                                            "price": price,
                                        }
                                    )
                                except (ValueError, AttributeError) as e:
                                    logger.debug(
                                        f"Date parsing error for {date_str}: {e}"
                                    )
                                    continue

                        data = {"success": True, "prices": prices_data}
            else:
                # Traditional asset - use Yahoo Finance
                data = self.fetch_yahoo_finance_data_optimized(symbol, period="3m")

            # Step 4: Extract price from fresh data
            if not data or not data.get("success"):
                logger.error(f"Failed to get any data for {symbol}")
                return 0.0

            # Find price closest to target date
            target_timestamp = target_date.timestamp()
            closest_price = 0.0
            min_diff = float("inf")

            prices_data = data.get("prices", [])
            if not prices_data:
                logger.error(f"No price data available for {symbol}")
                return 0.0

            for price_item in prices_data:
                try:
                    # Handle different data formats
                    if isinstance(price_item, dict):
                        if "timestamp" in price_item:
                            # Format from crypto APIs
                            price_timestamp = (
                                price_item["timestamp"] / 1000
                            )  # Convert to seconds
                            price_value = price_item["price"]
                        elif "date" in price_item:
                            # Format from Yahoo Finance
                            if isinstance(price_item["date"], datetime):
                                price_timestamp = price_item["date"].timestamp()
                            else:
                                continue
                            price_value = price_item["price"]
                        else:
                            continue
                    else:
                        # Handle list format [timestamp, price]
                        if len(price_item) >= 2:
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

                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"Error processing price data item: {e}")
                    continue

            if closest_price > 0:
                # Log how close we got to the target date
                closest_date = datetime.fromtimestamp(target_timestamp + min_diff)
                logger.info(
                    f"Found price {closest_price} for {symbol} on {closest_date} (diff: {min_diff/86400:.1f} days)"
                )
                return closest_price
            else:
                logger.error(f"No valid price found for {symbol} near {target_date}")
                return 0.0

        except Exception as e:
            logger.error(
                f"Error getting asset price for {symbol} at {target_date}: {e}"
            )
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
    def fetch_yahoo_finance_data_optimized(
        self, symbol: str, period: str = "1y"
    ) -> Dict:
        """Optimized Yahoo Finance with batch cache support"""
        # Check batch cache first
        cached_data = self.get_cached_data("traditional", symbol)
        if cached_data and cached_data.get("data"):
            cache_age = time.time() - cached_data.get("cached_at", 0)
            if cache_age < 1800:  # Use cached data if less than 30 minutes old
                logger.info(
                    f"Using batch cached Yahoo data for {symbol} (age: {cache_age:.1f}s)"
                )
            return cached_data["data"]

        # If not in batch cache or expired, make individual call
        # return self._fetch_yahoo_finance_individual(symbol, period)

    def get_risk_free_rate(self) -> float:
        """
        Get current risk-free rate from 10-year Treasury yield

        Returns:
            Risk-free rate as decimal (e.g., 0.045 for 4.5%)
        """
        try:
            data = self.fetch_yahoo_finance_data_optimized("^TNX", "5d")
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
            return self.fetch_yahoo_finance_data_optimized(symbol)

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
