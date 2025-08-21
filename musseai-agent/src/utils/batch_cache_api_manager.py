import time
from typing import Dict, Optional
from loggers import logger
import traceback
from utils.api_decorators import (
    APIRateLimitException,
    api_call_with_cache_and_rate_limit,
    cache_result,
)
from utils.api_manager import MultiAPIManager

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
