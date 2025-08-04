# src/utils/api_manager.py
import os
import threading
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loggers import logger
import traceback
from utils.api_decorators import (
    api_call_with_cache_and_rate_limit,
    api_call_with_cache_and_rate_limit_no_429_retry,
    APIRateLimitException,
    cache_result,
    clear_cache,
    get_cache_stats,
    rate_limit,
    retry_on_429,
)
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


class MultiAPIManager:
    def __init__(self):
        self.apis = {
            "coingecko": {
                "base_url": "https://api.coingecko.com/api/v3",
                "priority": 1,
            },
            "coincap": {
                "base_url": "https://rest.coincap.io/v3",
                "priority": 2,
                "api_key": os.getenv("COINCAP_API_KEY"),
            },
            "cryptocompare": {
                "base_url": "https://min-api.cryptocompare.com/data",
                "priority": 3,
            },
            "binance": {
                "base_url": "https://api.binance.com/api/v3",
                "priority": 4,
            },
            "yahoo": {
                "base_url": "https://query1.finance.yahoo.com/v8/finance/chart",
                "priority": 5,
            },
        }

        self.symbol_mapping = self._init_symbol_mapping()
        self.benchmark_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SP500": "^GSPC",
            "NASDAQ": "^IXIC",
            "GOLD": "GC=F",
            "USD": "DX-Y.NYB",
        }
        self.risk_free_rate_symbol = "^TNX"

        self.symbol_mapping = self._init_symbol_mapping()

        # Track which APIs are currently rate limited
        self.rate_limited_apis = {}
        self.rate_limit_reset_time = {}

        self.disabled_apis = {}  # API名称 -> 禁用原因
        self.api_disable_time = {}  # API名称 -> 禁用时间

        # Configuration for global retries
        self.default_max_global_retries = 2
        self.global_retry_wait_base = 60  # Base wait time in seconds

    def _mark_api_disabled(self, api_name: str, reason: str = "403_credits_exhausted"):
        """Mark an API as permanently disabled due to 403 error (credits exhausted)"""
        self.disabled_apis[api_name] = reason
        self.api_disable_time[api_name] = time.time()
        logger.error(f"API {api_name} disabled permanently due to: {reason}")

    def _is_api_disabled(self, api_name: str) -> bool:
        """Check if an API is permanently disabled"""
        return api_name in self.disabled_apis

    def _is_api_available(self, api_name: str) -> bool:
        """Check if an API is available (not rate limited or disabled)"""
        return not self._is_api_rate_limited(api_name) and not self._is_api_disabled(
            api_name
        )

    def get_api_status(self) -> Dict:
        """Get status of all APIs"""
        status = {}
        for api_name in self.apis.keys():
            status[api_name] = {
                "available": self._is_api_available(api_name),
                "rate_limited": self._is_api_rate_limited(api_name),
                "disabled": self._is_api_disabled(api_name),
                "disabled_reason": self.disabled_apis.get(api_name),
                "disabled_since": self.api_disable_time.get(api_name),
            }
        return status

    def fetch_with_batch_cache_fallback(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch data with batch cache fallback"""
        # First try batch cache
        cached_data = self.get_cached_data("crypto", symbol)
        if cached_data and cached_data.get("historical_data"):
            cache_age = time.time() - cached_data.get("cached_at", 0)
            if cache_age < 3600:  # Use cached data if less than 1 hour old
                logger.info(
                    f"Using batch cached data for {symbol} (age: {cache_age:.1f}s)"
                )
                return cached_data["historical_data"]

        # Fallback to individual API calls - use internal method
        logger.info(f"Batch cache miss for {symbol}, using individual API call")
        return self.fetch_with_fallback(symbol, days)

    @cache_result(duration=3600)  # 1-hour cache for individual calls
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
        return self._fetch_yahoo_finance_individual(symbol, period)

    def _fetch_yahoo_finance_individual(self, symbol: str, period: str = "1y") -> Dict:
        """Individual Yahoo Finance API call with improved error handling"""
        url = f"{self.apis['yahoo']['base_url']}/{symbol}"

        # Calculate time range
        period_days = {"1y": 365, "6m": 180, "3m": 90, "1m": 30}
        days = period_days.get(period, 365)

        params = {
            "period1": int((datetime.now() - timedelta(days=days)).timestamp()),
            "period2": int(datetime.now().timestamp()),
            "interval": "1d",
            "includePrePost": "false",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self._process_yahoo_data(data, symbol)

    def _is_api_rate_limited(self, api_name: str) -> bool:
        """Check if an API is currently rate limited"""
        if api_name in self.rate_limited_apis:
            reset_time = self.rate_limit_reset_time.get(api_name, 0)
            if time.time() < reset_time:
                return True
            else:
                # Reset time has passed, remove from rate limited list
                self.rate_limited_apis.pop(api_name, None)
                self.rate_limit_reset_time.pop(api_name, None)
        return False

    def _mark_api_rate_limited(self, api_name: str, reset_after_seconds: int = 300):
        """Mark an API as rate limited for a certain duration"""
        self.rate_limited_apis[api_name] = True
        self.rate_limit_reset_time[api_name] = time.time() + reset_after_seconds
        logger.warning(
            f"API {api_name} marked as rate limited for {reset_after_seconds} seconds"
        )

    def _init_symbol_mapping(self):
        """初始化不同API的符号映射"""
        return {
            "coingecko": {},  # Will be populated dynamically
            "coincap": {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "BNB": "binance-coin",
                "ADA": "cardano",
                "SOL": "solana",
                "DOT": "polkadot",
                "MATIC": "polygon",
                "AVAX": "avalanche",
                "DOGE": "dogecoin",
                "SHIB": "shiba-inu",
            },
            "binance": {
                # Binance uses direct symbols like BTCUSDT
            },
            "cryptocompare": {
                # CryptoCompare uses direct symbols
            },
        }

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=86400, rate_limit_interval=1.2, api_name="coingecko"
    )
    def fetch_historical_prices_coingecko(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch historical prices from CoinGecko with enhanced error handling"""
        # Simplified implementation without manual retry/rate limiting
        if not self.symbol_mapping["coingecko"]:
            self.symbol_mapping["coingecko"] = self._get_coingecko_mapping()

        coin_id = self.symbol_mapping["coingecko"].get(symbol.upper())
        if not coin_id:
            common_mappings = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "ADA": "cardano",
                "DOT": "polkadot",
                "AVAX": "avalanche-2",
                "LINK": "chainlink",
            }
            coin_id = common_mappings.get(symbol.upper(), symbol.lower())

        url = f"{self.apis['coingecko']['base_url']}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}

        headers = {
            "User-Agent": self.apis["coingecko"].get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        result = self._process_coingecko_data(data)

        if result and len(result.get("prices", [])) > 0:
            return result
        else:
            raise ValueError(f"CoinGecko returned empty data for {symbol}")

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=300, rate_limit_interval=0.1, api_name="coincap"
    )
    def fetch_historical_prices_coincap(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch historical prices from CoinCap API 3.0 with authentication"""

        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info("CoinCap API is disabled due to 403 error, skipping...")
            raise ValueError(
                "CoinCap API disabled due to 403 error (credits exhausted)"
            )

        asset_id = self.symbol_mapping["coincap"].get(symbol.upper(), symbol.lower())

        end_time = int(time.time() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)

        url = f"{self.apis['coincap']['base_url']}/assets/{asset_id}/history"
        params = {"interval": "d1", "start": start_time, "end": end_time}

        headers = {}
        if self.apis["coincap"].get("api_key"):
            headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            return self._process_coincap_data(data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(
                    f"CoinCap API returned 403 - credits likely exhausted for {symbol}"
                )
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                raise ValueError("CoinCap API credits exhausted (403)")
            else:
                raise

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=300, rate_limit_interval=0.1, api_name="binance"
    )
    def fetch_historical_prices_binance(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch historical prices from Binance"""
        binance_symbol = f"{symbol.upper()}USDT"

        url = f"{self.apis['binance']['base_url']}/klines"
        params = {
            "symbol": binance_symbol,
            "interval": "1d",
            "limit": min(days, 1000),  # Binance limit
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        return self._process_binance_data(data)

    @api_call_with_cache_and_rate_limit(cache_duration=300, rate_limit_interval=0.05)
    def fetch_historical_prices_cryptocompare(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch historical prices from CryptoCompare"""
        url = f"{self.apis['cryptocompare']['base_url']}/v2/histoday"
        params = {
            "fsym": symbol.upper(),
            "tsym": "USD",
            "limit": days,
            "aggregate": 1,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        return self._process_cryptocompare_data(data)

    @api_call_with_cache_and_rate_limit(
        cache_duration=3600,
        rate_limit_interval=2.0,  # 增加间隔
        max_retries=5,  # 更多重试次数
        retry_delay=5,  # 更长延迟
    )
    def fetch_yahoo_finance_data(self, symbol: str, period: str = "1y") -> Dict:
        """Fetch stock/index data from Yahoo Finance"""
        url = f"{self.apis['yahoo']['base_url']}/{symbol}"
        params = {
            "period1": int((datetime.now() - timedelta(days=365)).timestamp()),
            "period2": int(datetime.now().timestamp()),
            "interval": "1d",
            "includePrePost": "false",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self._process_yahoo_data(data, symbol)

    @api_call_with_cache_and_rate_limit(
        cache_duration=300,
        rate_limit_interval=1.2,
        max_retries=0,
        retry_delay=2,  # 不重试
    )
    def fetch_with_fallback(
        self, symbol: str, days: int = 90, max_global_retries: int = None
    ) -> Optional[Dict]:
        """
        Use multi-API failover mechanism with enhanced decorator support
        """
        if max_global_retries is None:
            max_global_retries = self.default_max_global_retries
        logger.info(f"Starting enhanced API fallback for {symbol}")

        # Define API methods in priority order
        api_methods = [
            ("coingecko", self.fetch_historical_prices_coingecko),
            ("coincap", self.fetch_historical_prices_coincap),
            ("cryptocompare", self.fetch_historical_prices_cryptocompare),
            ("binance", self.fetch_historical_prices_binance),
        ]

        for global_retry in range(max_global_retries + 1):
            available_apis = []
            rate_limited_count = 0
            disabled_count = 0

            # Filter out currently rate limited and disabled APIs
            for api_name, api_method in api_methods:
                if self._is_api_disabled(api_name):
                    disabled_count += 1
                    logger.debug(f"Skipping disabled API: {api_name}")
                elif not self._is_api_rate_limited(api_name):
                    available_apis.append((api_name, api_method))
                else:
                    rate_limited_count += 1
                    logger.debug(f"Skipping rate limited API: {api_name}")

            if not available_apis:
                if global_retry < max_global_retries:
                    wait_time = 60 * (global_retry + 1)  # Wait 60s, 120s, etc.
                    logger.warning(
                        f"All APIs unavailable (disabled: {disabled_count}, rate limited: {rate_limited_count}), "
                        f"waiting {wait_time}s before retry {global_retry + 1}"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"All APIs exhausted after maximum retries. "
                        f"Disabled: {disabled_count}, Rate limited: {rate_limited_count}"
                    )
                    return None

            # Try each available API
            for api_name, api_method in available_apis:
                try:
                    logger.info(f"Trying API: {api_name} for {symbol}")
                    result = api_method(symbol, days)

                    if result and len(result.get("prices", [])) > 10:
                        logger.info(
                            f"Successfully fetched data from {api_name} for {symbol}"
                        )
                        return result
                    else:
                        logger.warning(
                            f"API {api_name} returned insufficient data for {symbol}"
                        )

                except APIRateLimitException as e:
                    logger.warning(
                        f"API {api_name} rate limited: {e}\n{traceback.format_exc()}"
                    )
                    self._mark_api_rate_limited(api_name, reset_after_seconds=300)
                    continue  # Try next API immediately

                except ValueError as e:
                    # Check if it's a 403 disabled API error
                    if "403" in str(e) or "disabled" in str(e):
                        logger.warning(
                            f"API {api_name} is disabled due to 403 error: {e}"
                        )
                        continue  # Try next API immediately
                    else:
                        logger.warning(
                            f"API {api_name} failed for {symbol}: {e}\n{traceback.format_exc()}"
                        )
                        continue  # Try next API

                except Exception as e:
                    logger.warning(
                        f"API {api_name} failed for {symbol}: {e}\n{traceback.format_exc()}"
                    )
                    continue  # Try next API

            # If we get here, all available APIs failed (not due to rate limits)
            logger.warning(
                f"All available APIs failed for {symbol} on attempt {global_retry + 1}"
            )
            if global_retry < max_global_retries:
                time.sleep(5)  # Short wait before retrying
                continue
            else:
                break

        logger.error(
            f"All APIs failed for {symbol} after {max_global_retries + 1} attempts"
        )
        return None

    def _process_coingecko_data(self, data: Dict) -> Dict:
        """处理CoinGecko数据格式"""
        prices = data.get("prices", [])
        if not prices:
            return {}

        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["returns"] = df["price"].pct_change().dropna()

        return {
            "prices": df["price"].tolist(),
            "returns": df["returns"].tolist(),
            "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "volatility": df["returns"].std() * np.sqrt(365),
            "mean_return": df["returns"].mean() * 365,
        }

    def _process_coincap_data(self, data: Dict) -> Dict:
        """处理CoinCap数据格式"""
        history = data.get("data", [])
        if not history:
            return {}

        prices = [float(item["priceUsd"]) for item in history if item["priceUsd"]]
        dates = [item["date"] for item in history]

        if len(prices) < 2:
            return {}

        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]

        return {
            "prices": prices,
            "returns": returns,
            "dates": dates,
            "volatility": np.std(returns) * np.sqrt(365) if returns else 0,
            "mean_return": np.mean(returns) * 365 if returns else 0,
        }

    def _process_binance_data(self, data: List) -> Dict:
        """处理Binance数据格式"""
        if not data:
            return {}

        prices = [float(kline[4]) for kline in data]  # Close price
        dates = [
            pd.to_datetime(int(kline[0]), unit="ms").strftime("%Y-%m-%d")
            for kline in data
        ]

        if len(prices) < 2:
            return {}

        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]

        return {
            "prices": prices,
            "returns": returns,
            "dates": dates,
            "volatility": np.std(returns) * np.sqrt(365) if returns else 0,
            "mean_return": np.mean(returns) * 365 if returns else 0,
        }

    def _process_cryptocompare_data(self, data: Dict) -> Dict:
        """处理CryptoCompare数据格式"""
        history = data.get("Data", {}).get("Data", [])
        if not history:
            return {}

        prices = [float(item["close"]) for item in history if item["close"]]
        dates = [
            pd.to_datetime(int(item["time"]), unit="s").strftime("%Y-%m-%d")
            for item in history
        ]

        if len(prices) < 2:
            return {}

        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]

        return {
            "prices": prices,
            "returns": returns,
            "dates": dates,
            "volatility": np.std(returns) * np.sqrt(365) if returns else 0,
            "mean_return": np.mean(returns) * 365 if returns else 0,
        }

    def _get_coingecko_mapping(self) -> Dict[str, str]:
        """
        Get CoinGecko symbol mapping with retry mechanism
        """
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Add user agent header to help prevent 401 errors
                headers = {
                    "User-Agent": self.apis["coingecko"].get(
                        "user_agent",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    )
                }

                url = f"{self.apis['coingecko']['base_url']}/coins/list"
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                coins = response.json()
                mapping = {}
                for coin in coins:
                    symbol = coin["symbol"].upper()
                    if symbol not in mapping:  # Prioritize coins listed first
                        mapping[symbol] = coin["id"]

                # Add important mappings manually to ensure they're correct
                # These override any automatic mappings
                important_mappings = {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "BNB": "binancecoin",
                    "SOL": "solana",
                    "ADA": "cardano",
                    "XRP": "ripple",
                    "DOGE": "dogecoin",
                    "DOT": "polkadot",
                    "AVAX": "avalanche-2",
                    "SHIB": "shiba-inu",
                    "MATIC": "matic-network",
                    "LINK": "chainlink",
                }

                for symbol, coin_id in important_mappings.items():
                    mapping[symbol] = coin_id

                return mapping

            except requests.exceptions.HTTPError as e:
                logger.debug(traceback.format_exc())
                if e.response.status_code == 401:
                    logger.error(
                        f"CoinGecko API unauthorized error (401) on attempt {attempt+1}/{max_retries}"
                    )
                    # Increase wait time on 401 errors
                    self.apis["coingecko"]["rate_limit"] = 5.0
                elif e.response.status_code == 429:
                    logger.error(
                        f"CoinGecko API rate limit (429) on attempt {attempt+1}/{max_retries}"
                    )
                    # Exponential backoff for rate limits
                    self.apis["coingecko"]["rate_limit"] *= 2
                else:
                    logger.error(
                        f"CoinGecko API HTTP error: {e} on attempt {attempt+1}/{max_retries}"
                    )

                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2**attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error("Failed to get CoinGecko mapping after all retries")
                    return (
                        important_mappings  # Return just the manually defined mappings
                    )

            except Exception as e:
                logger.error(f"Failed to get CoinGecko mapping: {e}")
                logger.debug(traceback.format_exc())

                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2**attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    # Return a minimal mapping for most common coins
                    return {
                        "BTC": "bitcoin",
                        "ETH": "ethereum",
                        "BNB": "binancecoin",
                        "SOL": "solana",
                        "ADA": "cardano",
                        "XRP": "ripple",
                        "DOGE": "dogecoin",
                        "DOT": "polkadot",
                        "AVAX": "avalanche-2",
                        "SHIB": "shiba-inu",
                        "MATIC": "matic-network",
                        "LINK": "chainlink",
                    }

    @market_data_api
    def fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch current market data from multiple APIs with fallback mechanism

        This function has been enhanced to use multiple third-party APIs:
        1. CoinGecko (primary)
        2. CoinCap (secondary)
        3. Binance (tertiary)
        4. CryptoCompare (fallback)

        Args:
            symbol: Cryptocurrency symbol or coin ID

        Returns:
            Dict: Market data in standardized format
        """
        # Define API methods in priority order
        api_methods = [
            ("coingecko", self._fetch_coingecko_market_data),
            ("coincap", self._fetch_coincap_market_data),
            ("binance", self._fetch_binance_market_data),
            ("cryptocompare", self._fetch_cryptocompare_market_data),
        ]

        last_error = None

        for api_name, api_method in api_methods:
            # Skip disabled APIs
            if self._is_api_disabled(api_name):
                logger.debug(f"Skipping disabled API: {api_name}")
                continue

            # Skip rate-limited APIs
            if self._is_api_rate_limited(api_name):
                logger.debug(f"Skipping rate-limited API: {api_name}")
                continue

            try:
                logger.info(
                    f"Attempting to fetch market data from {api_name} for {symbol}"
                )
                result = api_method(symbol)

                if result and self._validate_market_data(result):
                    logger.info(
                        f"Successfully fetched market data from {api_name} for {symbol}"
                    )
                    return result
                else:
                    logger.warning(f"API {api_name} returned invalid data for {symbol}")

            except APIRateLimitException as e:
                logger.warning(
                    f"API {api_name} rate limited: {e}\n{traceback.format_exc()}"
                )
                self._mark_api_rate_limited(api_name, reset_after_seconds=300)
                last_error = e
                continue

            except ValueError as e:
                # Check if it's a 403 disabled API error
                if "403" in str(e) or "disabled" in str(e):
                    logger.warning(f"API {api_name} is disabled due to 403 error: {e}")
                    last_error = e
                    continue
                else:
                    logger.warning(
                        f"API {api_name} failed for {symbol}: {e}\n{traceback.format_exc()}"
                    )
                    last_error = e
                    continue

            except Exception as e:
                logger.warning(
                    f"API {api_name} failed for {symbol}: {e}\n{traceback.format_exc()}"
                )
                last_error = e
                continue

        # All APIs failed
        logger.error(f"All APIs failed to fetch market data for {symbol}")
        if last_error:
            raise last_error
        return None

    def _validate_market_data(self, data: Dict) -> bool:
        """
        Validate market data format and content

        Args:
            data: Market data dictionary

        Returns:
            bool: True if data is valid
        """
        if not isinstance(data, dict):
            return False

        required_fields = ["current_price", "market_cap", "total_volume"]

        for field in required_fields:
            if field not in data:
                return False
            if data[field] is None:
                return False
            if not isinstance(data[field], (int, float)):
                return False
            if data[field] < 0:
                return False

        return True

    def _fetch_coingecko_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data from CoinGecko API

        Args:
            symbol: Cryptocurrency symbol or coin ID

        Returns:
            Dict: Standardized market data
        """
        try:
            # Determine if symbol is coin_id or symbol
            if not self.symbol_mapping["coingecko"]:
                self.symbol_mapping["coingecko"] = self._get_coingecko_mapping()

            coin_id = self.symbol_mapping["coingecko"].get(symbol.upper())
            if not coin_id:
                # Try common mappings
                common_mappings = {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "SOL": "solana",
                    "ADA": "cardano",
                    "DOT": "polkadot",
                    "AVAX": "avalanche-2",
                    "LINK": "chainlink",
                }
                coin_id = common_mappings.get(symbol.upper(), symbol.lower())

            url = f"{self.apis['coingecko']['base_url']}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": coin_id,
                "per_page": 1,
                "page": 1,
                "sparkline": False,
                "price_change_percentage": "1h,24h,7d",
            }

            headers = {
                "User-Agent": self.apis["coingecko"].get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ),
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data or len(data) == 0:
                raise ValueError(f"No data returned for {symbol}")

            item = data[0]
            return {
                "id": item["id"],
                "symbol": item["symbol"],
                "name": item["name"],
                "current_price": item["current_price"],
                "market_cap": item["market_cap"],
                "market_cap_rank": item["market_cap_rank"],
                "fully_diluted_valuation": item.get("fully_diluted_valuation"),
                "total_volume": item["total_volume"],
                "high_24h": item["high_24h"],
                "low_24h": item["low_24h"],
                "price_change_24h": item["price_change_24h"],
                "price_change_percentage_24h": item["price_change_percentage_24h"],
                "price_change_percentage_7d": item.get(
                    "price_change_percentage_7d_in_currency"
                ),
                "price_change_percentage_1h": item.get(
                    "price_change_percentage_1h_in_currency"
                ),
                "market_cap_change_24h": item["market_cap_change_24h"],
                "market_cap_change_percentage_24h": item[
                    "market_cap_change_percentage_24h"
                ],
                "circulating_supply": item["circulating_supply"],
                "total_supply": item["total_supply"],
                "max_supply": item["max_supply"],
                "ath": item["ath"],
                "ath_change_percentage": item["ath_change_percentage"],
                "ath_date": item["ath_date"],
                "atl": item["atl"],
                "atl_change_percentage": item["atl_change_percentage"],
                "atl_date": item["atl_date"],
                "last_updated": item["last_updated"],
                "source": "coingecko",
            }

        except Exception as e:
            logger.error(
                f"CoinGecko market data API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    def _fetch_coincap_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data from CoinCap API

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            Dict: Standardized market data
        """
        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info("CoinCap API is disabled due to 403 error, skipping...")
            raise ValueError(
                "CoinCap API disabled due to 403 error (credits exhausted)"
            )

        try:
            # Map symbol to CoinCap asset ID
            asset_id = self.symbol_mapping["coincap"].get(
                symbol.upper(), symbol.lower()
            )

            url = f"{self.apis['coincap']['base_url']}/assets/{asset_id}"

            headers = {}
            if self.apis["coincap"].get("api_key"):
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data.get("data"):
                raise ValueError(f"No data returned for {symbol}")

            item = data["data"]

            # Convert CoinCap format to standardized format
            return {
                "id": item["id"],
                "symbol": item["symbol"].lower(),
                "name": item["name"],
                "current_price": float(item["priceUsd"]) if item["priceUsd"] else 0,
                "market_cap": (
                    float(item["marketCapUsd"]) if item["marketCapUsd"] else 0
                ),
                "market_cap_rank": int(item["rank"]) if item["rank"] else 0,
                "fully_diluted_valuation": None,  # Not available in CoinCap
                "total_volume": (
                    float(item["volumeUsd24Hr"]) if item["volumeUsd24Hr"] else 0
                ),
                "high_24h": None,  # Not available in basic endpoint
                "low_24h": None,  # Not available in basic endpoint
                "price_change_24h": None,
                "price_change_percentage_24h": (
                    float(item["changePercent24Hr"]) if item["changePercent24Hr"] else 0
                ),
                "price_change_percentage_7d": None,  # Not available
                "price_change_percentage_1h": None,  # Not available
                "market_cap_change_24h": None,
                "market_cap_change_percentage_24h": None,
                "circulating_supply": float(item["supply"]) if item["supply"] else 0,
                "total_supply": float(item["supply"]) if item["supply"] else 0,
                "max_supply": float(item["maxSupply"]) if item["maxSupply"] else None,
                "ath": None,  # Not available
                "ath_change_percentage": None,
                "ath_date": None,
                "atl": None,
                "atl_change_percentage": None,
                "atl_date": None,
                "last_updated": None,
                "source": "coincap",
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(
                    f"CoinCap API returned 403 - credits likely exhausted for {symbol}"
                )
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                raise ValueError("CoinCap API credits exhausted (403)")
            else:
                logger.error(
                    f"CoinCap market data API failed for {symbol}: {e}\n{traceback.format_exc()}"
                )
                raise
        except Exception as e:
            logger.error(
                f"CoinCap market data API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    def _fetch_binance_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data from Binance API

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            Dict: Standardized market data
        """
        try:
            # Convert symbol to Binance format (e.g., BTC -> BTCUSDT)
            binance_symbol = f"{symbol.upper()}USDT"

            # Get 24hr ticker statistics
            url = f"{self.apis['binance']['base_url']}/ticker/24hr"
            params = {"symbol": binance_symbol}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data:
                raise ValueError(f"No data returned for {symbol}")

            # Get additional price info
            price_url = f"{self.apis['binance']['base_url']}/ticker/price"
            price_response = requests.get(price_url, params=params, timeout=10)
            price_data = price_response.json() if price_response.ok else {}

            # Convert Binance format to standardized format
            return {
                "id": symbol.lower(),
                "symbol": symbol.lower(),
                "name": symbol.upper(),
                "current_price": float(data["lastPrice"]),
                "market_cap": None,  # Not available from Binance
                "market_cap_rank": None,
                "fully_diluted_valuation": None,
                "total_volume": float(data["volume"])
                * float(data["lastPrice"]),  # Volume in USD
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "price_change_24h": float(data["priceChange"]),
                "price_change_percentage_24h": float(data["priceChangePercent"]),
                "price_change_percentage_7d": None,  # Not available
                "price_change_percentage_1h": None,  # Not available
                "market_cap_change_24h": None,
                "market_cap_change_percentage_24h": None,
                "circulating_supply": None,
                "total_supply": None,
                "max_supply": None,
                "ath": None,
                "ath_change_percentage": None,
                "ath_date": None,
                "atl": None,
                "atl_change_percentage": None,
                "atl_date": None,
                "last_updated": None,
                "source": "binance",
            }

        except Exception as e:
            logger.error(
                f"Binance market data API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    def _fetch_cryptocompare_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Fetch market data from CryptoCompare API

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            Dict: Standardized market data
        """
        try:
            # Get current price data
            price_url = f"{self.apis['cryptocompare']['base_url']}/price"
            price_params = {"fsym": symbol.upper(), "tsyms": "USD"}

            price_response = requests.get(price_url, params=price_params, timeout=10)
            price_response.raise_for_status()
            price_data = price_response.json()

            if "USD" not in price_data:
                raise ValueError(f"No USD price data for {symbol}")

            current_price = price_data["USD"]

            # Get additional market data
            pricemulti_url = f"{self.apis['cryptocompare']['base_url']}/pricemultifull"
            multi_params = {"fsyms": symbol.upper(), "tsyms": "USD"}

            multi_response = requests.get(
                pricemulti_url, params=multi_params, timeout=10
            )
            multi_data = multi_response.json() if multi_response.ok else {}

            # Extract detailed data if available
            detailed_data = {}
            if "RAW" in multi_data and symbol.upper() in multi_data["RAW"]:
                detailed_data = multi_data["RAW"][symbol.upper()].get("USD", {})

            return {
                "id": symbol.lower(),
                "symbol": symbol.lower(),
                "name": symbol.upper(),
                "current_price": current_price,
                "market_cap": detailed_data.get("MKTCAP"),
                "market_cap_rank": None,
                "fully_diluted_valuation": None,
                "total_volume": detailed_data.get("TOTALVOLUME24HTO"),
                "high_24h": detailed_data.get("HIGH24HOUR"),
                "low_24h": detailed_data.get("LOW24HOUR"),
                "price_change_24h": detailed_data.get("CHANGE24HOUR"),
                "price_change_percentage_24h": detailed_data.get("CHANGEPCT24HOUR"),
                "price_change_percentage_7d": None,  # Not available
                "price_change_percentage_1h": detailed_data.get("CHANGEPCTHOUR"),
                "market_cap_change_24h": None,
                "market_cap_change_percentage_24h": None,
                "circulating_supply": detailed_data.get("SUPPLY"),
                "total_supply": None,
                "max_supply": None,
                "ath": None,
                "ath_change_percentage": None,
                "ath_date": None,
                "atl": None,
                "atl_change_percentage": None,
                "atl_date": None,
                "last_updated": None,
                "source": "cryptocompare",
            }

        except Exception as e:
            logger.error(
                f"CryptoCompare market data API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    # Enhanced batch fetch function
    @market_data_api
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

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=1800, rate_limit_interval=1.2, api_name="coingecko"
    )
    def fetch_market_chart_coingecko(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """
        Fetch market chart data from CoinGecko with caching and rate limiting
        """
        try:
            # Determine coin_id from symbol
            if not self.symbol_mapping["coingecko"]:
                self.symbol_mapping["coingecko"] = self._get_coingecko_mapping()

            coin_id = self.symbol_mapping["coingecko"].get(symbol.upper())
            if not coin_id:
                common_mappings = {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "SOL": "solana",
                    "ADA": "cardano",
                    "DOT": "polkadot",
                    "AVAX": "avalanche-2",
                    "LINK": "chainlink",
                }
                coin_id = common_mappings.get(symbol.upper(), symbol.lower())

            url = f"{self.apis['coingecko']['base_url']}/coins/{coin_id}/market_chart"
            params = {"vs_currency": "usd", "days": days, "interval": interval}

            headers = {
                "User-Agent": self.apis["coingecko"].get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ),
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
            }

            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            return self._process_coingecko_chart_data(data)

        except Exception as e:
            logger.error(
                f"CoinGecko market chart API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=1800, rate_limit_interval=0.1, api_name="coincap"
    )
    def fetch_market_chart_coincap(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """
        Fetch market chart data from CoinCap API
        """
        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info("CoinCap API is disabled due to 403 error, skipping...")
            raise ValueError(
                "CoinCap API disabled due to 403 error (credits exhausted)"
            )

        try:
            asset_id = self.symbol_mapping["coincap"].get(
                symbol.upper(), symbol.lower()
            )

            # Convert days to milliseconds for CoinCap API
            days_int = int(days)
            end_time = int(time.time() * 1000)
            start_time = end_time - (days_int * 24 * 60 * 60 * 1000)

            # Map interval to CoinCap format
            coincap_interval = self._map_interval_to_coincap(interval, days_int)

            url = f"{self.apis['coincap']['base_url']}/assets/{asset_id}/history"
            params = {
                "interval": coincap_interval,
                "start": start_time,
                "end": end_time,
            }

            headers = {}
            if self.apis["coincap"].get("api_key"):
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            return self._process_coincap_chart_data(data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(
                    f"CoinCap API returned 403 - credits likely exhausted for {symbol}"
                )
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                raise ValueError("CoinCap API credits exhausted (403)")
            else:
                logger.error(
                    f"CoinCap market chart API failed for {symbol}: {e}\n{traceback.format_exc()}"
                )
                raise
        except Exception as e:
            logger.error(
                f"CoinCap market chart API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=1800, rate_limit_interval=0.1, api_name="binance"
    )
    def fetch_market_chart_binance(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """
        Fetch market chart data from Binance API
        """
        try:
            binance_symbol = f"{symbol.upper()}USDT"

            # Map interval to Binance format
            binance_interval = self._map_interval_to_binance(interval)

            # Calculate limit based on days and interval
            days_int = int(days)
            limit = min(days_int, 1000)  # Binance limit

            url = f"{self.apis['binance']['base_url']}/klines"
            params = {
                "symbol": binance_symbol,
                "interval": binance_interval,
                "limit": limit,
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            return self._process_binance_chart_data(data)

        except Exception as e:
            logger.error(
                f"Binance market chart API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    @api_call_with_cache_and_rate_limit_no_429_retry(
        cache_duration=1800, rate_limit_interval=0.05, api_name="cryptocompare"
    )
    def fetch_market_chart_cryptocompare(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """
        Fetch market chart data from CryptoCompare API
        """
        try:
            # Map interval to CryptoCompare endpoint
            endpoint = self._map_interval_to_cryptocompare_endpoint(interval)

            url = f"{self.apis['cryptocompare']['base_url']}/v2/{endpoint}"
            params = {
                "fsym": symbol.upper(),
                "tsym": "USD",
                "limit": int(days),
                "aggregate": 1,
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            return self._process_cryptocompare_chart_data(data)

        except Exception as e:
            logger.error(
                f"CryptoCompare market chart API failed for {symbol}: {e}\n{traceback.format_exc()}"
            )
            raise

    @api_call_with_cache_and_rate_limit(
        cache_duration=1800,
        rate_limit_interval=1.2,
        max_retries=0,
        retry_delay=2,
    )
    def fetch_market_chart_multi_api(
        self,
        symbol: str,
        days: str = "30",
        interval: str = "daily",
        max_global_retries: int = None,
    ) -> Optional[Dict]:
        """
        Fetch market chart data using multi-API fallback mechanism with enhanced error handling

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days of data (default: "30")
            interval: Data interval - "daily", "hourly", or "weekly" (default: "daily")
            max_global_retries: Maximum global retry attempts

        Returns:
            Dict: Market chart data in standardized format with prices, market_caps, and total_volumes
        """
        if max_global_retries is None:
            max_global_retries = self.default_max_global_retries

        logger.info(f"Starting multi-API market chart fetch for {symbol}")

        # Define API methods in priority order
        api_methods = [
            ("coingecko", self.fetch_market_chart_coingecko),
            ("coincap", self.fetch_market_chart_coincap),
            ("binance", self.fetch_market_chart_binance),
            ("cryptocompare", self.fetch_market_chart_cryptocompare),
        ]

        for global_retry in range(max_global_retries + 1):
            available_apis = []
            rate_limited_count = 0
            disabled_count = 0

            # Filter out currently rate limited and disabled APIs
            for api_name, api_method in api_methods:
                if self._is_api_disabled(api_name):
                    disabled_count += 1
                    logger.debug(f"Skipping disabled API: {api_name}")
                elif not self._is_api_rate_limited(api_name):
                    available_apis.append((api_name, api_method))
                else:
                    rate_limited_count += 1
                    logger.debug(f"Skipping rate limited API: {api_name}")

            if not available_apis:
                if global_retry < max_global_retries:
                    wait_time = 60 * (global_retry + 1)  # Wait 60s, 120s, etc.
                    logger.warning(
                        f"All APIs unavailable (disabled: {disabled_count}, rate limited: {rate_limited_count}), "
                        f"waiting {wait_time}s before retry {global_retry + 1}"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("All APIs exhausted after maximum retries")
                    return None

            # Try each available API
            for api_name, api_method in available_apis:
                try:
                    logger.info(f"Trying API: {api_name} for {symbol} market chart")
                    result = api_method(symbol, days, interval)

                    if result and self._validate_chart_data(result):
                        logger.info(
                            f"Successfully fetched market chart data from {api_name} for {symbol}"
                        )
                        result["source"] = api_name
                        result["symbol"] = symbol
                        result["days"] = days
                        result["interval"] = interval
                        return result
                    else:
                        logger.warning(
                            f"API {api_name} returned insufficient chart data for {symbol}"
                        )

                except APIRateLimitException as e:
                    logger.warning(
                        f"API {api_name} rate limited: {e}\n{traceback.format_exc()}"
                    )
                    self._mark_api_rate_limited(api_name, reset_after_seconds=300)
                    continue  # Try next API immediately

                except ValueError as e:
                    # Check if it's a 403 disabled API error
                    if "403" in str(e) or "disabled" in str(e):
                        logger.warning(
                            f"API {api_name} is disabled due to 403 error: {e}"
                        )
                        continue  # Try next API immediately
                    else:
                        logger.warning(
                            f"API {api_name} failed for {symbol} chart: {e}\n{traceback.format_exc()}"
                        )
                        continue  # Try next API

                except Exception as e:
                    logger.warning(
                        f"API {api_name} failed for {symbol} chart: {e}\n{traceback.format_exc()}"
                    )
                    continue  # Try next API

            # If we get here, all available APIs failed (not due to rate limits)
            logger.warning(
                f"All available APIs failed for {symbol} chart on attempt {global_retry + 1}"
            )
            if global_retry < max_global_retries:
                time.sleep(5)  # Short wait before retrying
                continue
            else:
                break

        logger.error(
            f"All APIs failed for {symbol} chart after {max_global_retries + 1} attempts"
        )
        return None

    def _process_yahoo_data(self, data: Dict, symbol: str) -> Dict:
        """Process Yahoo Finance data format with enhanced error handling"""
        try:
            # Validate basic data structure
            if not data or "chart" not in data:
                raise ValueError("Invalid Yahoo Finance response: missing chart data")

            chart = data.get("chart", {})
            if not chart.get("result") or len(chart["result"]) == 0:
                raise ValueError("Invalid Yahoo Finance response: empty result")

            chart_data = chart["result"][0]

            # Check for required fields with defensive programming
            if "timestamp" not in chart_data:
                logger.warning(
                    f"Yahoo Finance response missing timestamp field for {symbol}"
                )
                # Try alternative field names or provide fallback
                timestamps = (
                    chart_data.get("timestamps") or chart_data.get("times") or []
                )
                if not timestamps:
                    raise ValueError(
                        "No timestamp data available in Yahoo Finance response"
                    )
            else:
                timestamps = chart_data["timestamp"]

            # Validate indicators data
            indicators = chart_data.get("indicators", {})
            if (
                not indicators
                or "quote" not in indicators
                or len(indicators["quote"]) == 0
            ):
                raise ValueError(
                    "Invalid Yahoo Finance response: missing quote indicators"
                )

            quote_data = indicators["quote"][0]

            # Validate that we have the required price data
            required_fields = ["close", "open", "high", "low"]
            for field in required_fields:
                if field not in quote_data:
                    logger.warning(
                        f"Missing {field} data in Yahoo Finance response for {symbol}"
                    )

            prices = []
            for i, timestamp in enumerate(timestamps):
                if (
                    i < len(quote_data.get("close", []))
                    and quote_data["close"][i] is not None
                ):
                    prices.append(
                        {
                            "timestamp": timestamp * 1000,  # Convert to milliseconds
                            "date": datetime.fromtimestamp(timestamp),
                            "price": quote_data["close"][i],
                            "open": quote_data.get("open", [None] * len(timestamps))[i],
                            "high": quote_data.get("high", [None] * len(timestamps))[i],
                            "low": quote_data.get("low", [None] * len(timestamps))[i],
                            "volume": quote_data.get("volume", [0] * len(timestamps))[i]
                            or 0,
                        }
                    )

            if not prices:
                raise ValueError(f"No valid price data extracted for {symbol}")

            return {"success": True, "symbol": symbol, "prices": prices}

        except KeyError as e:
            logger.error(
                f"Missing required field in Yahoo Finance data for {symbol}: {e}\n{traceback.format_exc()}"
            )
            logger.debug(
                f"Yahoo Finance raw response structure: {list(data.keys()) if data else 'None'}"
            )
            return {
                "success": False,
                "error": f"Missing required field: {e}",
                "symbol": symbol,
            }

        except Exception as e:
            logger.error(
                f"Error processing Yahoo Finance data for {symbol}: {e}\n{traceback.format_exc()}"
            )
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e), "symbol": symbol}

    def get_risk_free_rate(self) -> float:
        """
        Get current risk-free rate from 10-year Treasury yield

        Returns:
            Risk-free rate as decimal (e.g., 0.045 for 4.5%)
        """
        try:
            data = self.fetch_yahoo_finance_data_optimized("^TNX", "5d")
            if data["success"] and data["prices"]:
                latest_yield = data["prices"][-1]["price"]
                return latest_yield / 100  # Convert percentage to decimal
            return 0.045  # Default fallback
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Failed to fetch risk-free rate: {e}")
            return 0.045

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
                return self.fetch_historical_prices_coingecko(benchmark, days)
        else:
            symbol = benchmark_mapping.get(benchmark, benchmark)
            return self.fetch_yahoo_finance_data_optimized(symbol)

        return {"success": False, "error": f"Unknown benchmark: {benchmark}"}

    def get_asset_price_at_date(self, symbol: str, target_date: datetime) -> float:
        """
        Get asset price at specific date with unified API handling

        Args:
            symbol: Asset symbol
            target_date: Target date

        Returns:
            Price at the date
        """
        try:
            # Determine if it's crypto or traditional asset
            crypto_symbols = ["BTC", "ETH", "ADA", "DOT", "LINK", "UNI", "AAVE", "SOL"]

            if symbol.upper() in crypto_symbols:
                # Map symbol to coin_id
                coin_mapping = {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "ADA": "cardano",
                    "DOT": "polkadot",
                    "LINK": "chainlink",
                    "UNI": "uniswap",
                    "AAVE": "aave",
                    "SOL": "solana",
                }
                coin_id = coin_mapping.get(symbol.upper(), symbol.lower())

                # Try multi-API approach first
                data = self.get_crypto_historical_data(coin_id, "usd", 30)

                # If failed, try direct method
                if not data["success"]:
                    data = self.fetch_historical_prices_coingecko(symbol, 30)
            else:
                data = self.fetch_yahoo_finance_data_optimized(symbol, period="1mo")

            if not data["success"]:
                return 0.0

            # Find price closest to target date
            target_timestamp = target_date.timestamp()
            closest_price = 0.0
            min_diff = float("inf")

            for price_data in data["prices"]:
                price_timestamp = price_data["timestamp"] / 1000  # Convert to seconds
                diff = abs(price_timestamp - target_timestamp)

                if diff < min_diff:
                    min_diff = diff
                    closest_price = price_data["price"]
            return closest_price

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(
                f"Error getting asset price for {symbol} at {target_date}: {e}"
            )
            return 0.0

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

    @api_call_with_cache_and_rate_limit(
        cache_duration=86400,  # 24 hours cache
        rate_limit_interval=1.2,
        max_retries=3,
        retry_delay=2,
    )
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

    def fetch_multiple_assets_data(self, symbols: List[str], days: int = 365) -> Dict:
        """
        Batch fetch data for multiple assets with optimized API usage

        Args:
            symbols: List of asset symbols
            days: Number of days of data

        Returns:
            Dict mapping symbols to their price data
        """
        results = {}

        for symbol in symbols:
            try:
                # Determine asset type and use appropriate API
                crypto_symbols = [
                    "BTC",
                    "ETH",
                    "ADA",
                    "DOT",
                    "LINK",
                    "UNI",
                    "AAVE",
                    "SOL",
                ]

                if symbol.upper() in crypto_symbols:
                    data = self.get_crypto_historical_data(symbol.lower(), "usd", days)
                else:
                    data = self.fetch_yahoo_finance_data_optimized(symbol, "1y")

                results[symbol] = data

                # Add small delay to respect rate limits
                time.sleep(0.1)

            except Exception as e:
                logger.debug(traceback.format_exc())
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                results[symbol] = {"success": False, "error": str(e)}

        return results

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

    def _fetch_fear_greed_alternative(self):
        """Fetch from Alternative.me (existing implementation)"""
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        current_index = int(data["data"][0]["value"])
        classification = data["data"][0]["value_classification"]

        # Enhanced market condition mapping (existing logic)
        if current_index >= 80:
            market_condition = "extreme_bull"
            market_sentiment = "extreme_greed"
        elif current_index >= 70:
            market_condition = "strong_bull"
            market_sentiment = "greed"
        elif current_index >= 60:
            market_condition = "bull_market"
            market_sentiment = "optimistic"
        elif current_index >= 50:
            market_condition = "bull_leaning"
            market_sentiment = "neutral_positive"
        elif current_index >= 40:
            market_condition = "sideways"
            market_sentiment = "neutral"
        elif current_index >= 30:
            market_condition = "bear_leaning"
            market_sentiment = "neutral_negative"
        elif current_index >= 20:
            market_condition = "bear_market"
            market_sentiment = "fear"
        elif current_index >= 10:
            market_condition = "strong_bear"
            market_sentiment = "strong_fear"
        else:
            market_condition = "extreme_bear"
            market_sentiment = "extreme_fear"

        return current_index, classification, market_condition, market_sentiment

    def _estimate_fear_greed_from_market(self):
        """Estimate fear & greed based on market data when APIs fail"""
        try:
            # Get BTC trend
            btc_trend = self.analyze_btc_trend(7)
            weekly_change = btc_trend["weekly_change"]

            # Estimate index based on price movement
            if weekly_change > 15:
                index = 75  # Greed
            elif weekly_change > 5:
                index = 60  # Optimistic
            elif weekly_change > -5:
                index = 45  # Neutral
            elif weekly_change > -15:
                index = 30  # Fear
            else:
                index = 20  # Strong fear

            if index >= 70:
                classification = "Greed"
                market_condition = "bull_market"
                market_sentiment = "greed"
            elif index >= 50:
                classification = "Neutral"
                market_condition = "sideways"
                market_sentiment = "neutral"
            else:
                classification = "Fear"
                market_condition = "bear_market"
                market_sentiment = "fear"

            return index, classification, market_condition, market_sentiment

        except Exception:
            logger.error(traceback.format_exc())
            # Ultimate fallback
            return 50, "Neutral", "sideways", "neutral"

    @market_data_api
    def get_market_metrics(self):
        """Get market metrics from multiple APIs with fallback"""
        # Define API methods in priority order
        api_methods = [
            ("coingecko", self._fetch_coingecko_global_metrics),
            ("coincap", self._fetch_coincap_global_metrics),
            # ("binance", self._fetch_binance_global_metrics),
        ]

        for api_name, api_method in api_methods:
            if self._is_api_rate_limited(api_name):
                continue

            try:
                result = api_method()
                if result:
                    return result
            except Exception as e:
                logger.warning(
                    f"API {api_name} failed for global metrics: {e}\n{traceback.format_exc()}"
                )
                continue

        raise ValueError("All APIs failed for global metrics")

    def _fetch_coingecko_global_metrics(self):
        """Fetch from CoinGecko (existing implementation)"""
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "total_market_cap": data["data"]["total_market_cap"]["usd"],
            "btc_dominance": data["data"]["market_cap_percentage"]["btc"],
            "eth_dominance": data["data"]["market_cap_percentage"].get("eth", 0),
            "market_cap_change_24h": data["data"][
                "market_cap_change_percentage_24h_usd"
            ],
            "active_cryptocurrencies": data["data"]["active_cryptocurrencies"],
            "markets": data["data"]["markets"],
            "source": "coingecko",
        }

    def _fetch_coincap_global_metrics(self):
        """Fetch from CoinCap"""
        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info("CoinCap API is disabled due to 403 error, skipping...")
            return None

        try:
            headers = {}
            if self.apis["coincap"].get("api_key"):
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            url = f"{self.apis['coincap']['base_url']}/assets"
            params = {"limit": 10}  # Get top 10 for dominance calculation

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return None

            total_market_cap = sum(
                float(asset.get("marketCapUsd", 0)) for asset in data["data"]
            )
            btc_data = next(
                (asset for asset in data["data"] if asset["id"] == "bitcoin"), None
            )
            eth_data = next(
                (asset for asset in data["data"] if asset["id"] == "ethereum"), None
            )

            btc_dominance = (
                (float(btc_data["marketCapUsd"]) / total_market_cap * 100)
                if btc_data
                else 0
            )
            eth_dominance = (
                (float(eth_data["marketCapUsd"]) / total_market_cap * 100)
                if eth_data
                else 0
            )

            return {
                "total_market_cap": total_market_cap,
                "btc_dominance": btc_dominance,
                "eth_dominance": eth_dominance,
                "market_cap_change_24h": None,  # Not available in CoinCap
                "active_cryptocurrencies": len(data["data"]),
                "markets": None,
                "source": "coincap",
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("CoinCap API returned 403 - credits likely exhausted")
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                return None
            else:
                logger.error(f"CoinCap global metrics API failed: {e}")
                return None
        except Exception as e:
            logger.error(f"CoinCap global metrics API failed: {e}")
            return None

    @historical_data_api
    def analyze_btc_trend(self, days=30):
        """Analyze Bitcoin price trend using multi-API fallback"""
        # Use existing multi-API historical data method
        btc_data = self.fetch_with_batch_cache_fallback("BTC", days)

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

    @market_data_api
    def fetch_binance_market_data(self, symbols: List[str]) -> Dict:
        """
        从Binance获取市场数
        """
        results = {}

        try:
            # Binance 24hr ticker API
            url = f"{self.apis['binance']['base_url']}/ticker/24hr"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            # 创建符号映射
            for item in data:
                symbol = item["symbol"]
                if symbol.endswith("USDT"):
                    base_symbol = symbol[:-4]  # 移除USDT
                    if base_symbol in symbols:
                        results[base_symbol] = {
                            "id": base_symbol.lower(),
                            "symbol": base_symbol.lower(),
                            "current_price": float(item["lastPrice"]),
                            "market_cap": None,  # Binance不提供市值
                            "total_volume": float(item["volume"])
                            * float(item["lastPrice"]),
                            "price_change_percentage_24h": float(
                                item["priceChangePercent"]
                            ),
                        }

        except Exception as e:
            logger.error(
                f"Binance market data fetch failed: {e}\n{traceback.format_exc()}"
            )
        return results

    @market_data_api
    def fetch_current_market_data_coincap(self, coin_ids: List[str]) -> Dict:
        """
        Fetch current market data from CoinCap API v3

        Args:
            coin_ids (List[str]): List of CoinCap asset IDs or symbols

        Returns:
            Dict: Current market data
        """
        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info("CoinCap API is disabled due to 403 error, skipping...")
            return {}

        try:
            headers = {}
            if self.apis["coincap"]["api_key"]:
                # CoinCap uses Bearer token, not X-CG-API-KEY
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            # Use the correct CoinCap endpoint for assets
            url = f"{self.apis['coincap']['base_url']}/assets"

            # Convert symbols to CoinCap asset IDs if needed
            asset_ids = []
            for coin_id in coin_ids:
                # Map symbols to CoinCap asset IDs
                if coin_id.upper() in [
                    "ETH",
                    "BTC",
                    "SOL",
                    "BNB",
                    "USDT",
                    "TRX",
                    "SWFTC",
                    "ETHW",
                ]:
                    symbol_to_id = {
                        "ETH": "ethereum",
                        "BTC": "bitcoin",
                        "SOL": "solana",
                        "BNB": "binance-coin",
                        "USDT": "tether",
                        "TRX": "tron",
                        "SWFTC": "swftcoin",  # 需要验证准确的ID
                        "ETHW": "ethereum-pow",  # 需要验证准确的ID
                    }
                    asset_ids.append(symbol_to_id.get(coin_id.upper(), coin_id.lower()))
                else:
                    asset_ids.append(coin_id.lower())

            # Use CoinCap parameters, not CoinGecko parameters
            params = {"ids": ",".join(asset_ids), "limit": len(asset_ids)}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Process CoinCap response format
            all_data = {}
            if "data" in data:
                for item in data["data"]:
                    # Convert CoinCap format to expected format
                    processed_item = {
                        "id": item["id"],
                        "symbol": item["symbol"].lower(),
                        "current_price": (
                            float(item["priceUsd"]) if item["priceUsd"] else 0
                        ),
                        "market_cap": (
                            float(item["marketCapUsd"]) if item["marketCapUsd"] else 0
                        ),
                        "total_volume": (
                            float(item["volumeUsd24Hr"]) if item["volumeUsd24Hr"] else 0
                        ),
                        "price_change_percentage_24h": (
                            float(item["changePercent24Hr"])
                            if item["changePercent24Hr"]
                            else 0
                        ),
                        "rank": int(item["rank"]) if item["rank"] else 0,
                    }
                    all_data[item["id"]] = processed_item

            return all_data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("CoinCap API returned 403 - credits likely exhausted")
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                return {}
            else:
                logger.error(f"Failed to fetch market data from CoinCap: {e}")
                logger.debug(traceback.format_exc())
                return {}
        except Exception as e:
            logger.error(f"Failed to fetch market data from CoinCap: {e}")
            logger.debug(traceback.format_exc())
            return {}

    @market_data_api
    def get_coin_id_mapping_coincap(self) -> Dict[str, str]:
        """
        Get mapping from symbol to CoinCap asset ID using CoinCap API v3.

        Returns:
            Dict: Mapping of symbol to asset ID
        """
        # Check if CoinCap API is disabled
        if self._is_api_disabled("coincap"):
            logger.info(
                "CoinCap API is disabled due to 403 error, using fallback mapping..."
            )
            return self._get_fallback_coin_mapping()

        try:
            headers = {}
            if self.apis["coincap"]["api_key"]:
                # CoinCap uses Bearer token authentication
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            # Use correct CoinCap v3 endpoint
            url = f"{self.apis['coincap']['base_url']}/assets"

            # CoinCap API supports pagination and filtering
            params = {
                "limit": 2000,  # Get top 2000 assets to build comprehensive mapping
                "offset": 0,
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            mapping = {}

            # Process CoinCap response format
            if "data" in data:
                for asset in data["data"]:
                    symbol = asset["symbol"].upper()
                    asset_id = asset["id"]

                    # Prefer assets with higher rank (lower number = higher rank)
                    if symbol not in mapping:
                        mapping[symbol] = asset_id
                    else:
                        # If symbol already exists, prefer the one with better rank
                        existing_rank = float("inf")  # Default to infinity if no rank
                        current_rank = int(asset.get("rank", float("inf")))

                        # Keep the asset with better (lower) rank
                        if current_rank < existing_rank:
                            mapping[symbol] = asset_id

            # Add manual mappings for important coins to ensure accuracy
            important_mappings = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "BNB": "binance-coin",
                "SOL": "solana",
                "ADA": "cardano",
                "XRP": "ripple",
                "DOGE": "dogecoin",
                "DOT": "polkadot",
                "AVAX": "avalanche",
                "SHIB": "shiba-inu",
                "MATIC": "polygon",
                "LINK": "chainlink",
                "UNI": "uniswap",
                "ATOM": "cosmos",
                "LTC": "litecoin",
                "NEAR": "near-protocol",
                "APT": "aptos",
                "OP": "optimism",
                "ARB": "arbitrum",
            }

            # Override with manual mappings for critical assets
            for symbol, asset_id in important_mappings.items():
                mapping[symbol] = asset_id

            logger.info(
                f"Successfully built CoinCap mapping with {len(mapping)} assets"
            )
            return mapping

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("CoinCap API returned 403 - credits likely exhausted")
                self._mark_api_disabled("coincap", "403_credits_exhausted")
                return self._get_fallback_coin_mapping()
            else:
                logger.error(
                    f"HTTP error fetching CoinCap mapping: {e}\n{traceback.format_exc()}"
                )
                if e.response.status_code == 401:
                    logger.warning("CoinCap API authentication failed - check API key")
                elif e.response.status_code == 429:
                    logger.warning("CoinCap API rate limit exceeded")
                return self._get_fallback_coin_mapping()

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Network error fetching CoinCap mapping: {e}\n{traceback.format_exc()}"
            )
            return self._get_fallback_coin_mapping()

        except Exception as e:
            logger.error(
                f"Unexpected error fetching CoinCap mapping: {e}\n{traceback.format_exc()}"
            )
            logger.debug(traceback.format_exc())
            return self._get_fallback_coin_mapping()

    def _get_fallback_coin_mapping(self) -> Dict[str, str]:
        """
        Provide fallback coin mapping when API calls fail

        Returns:
            Dict: Basic mapping of popular cryptocurrencies
        """
        return {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "BNB": "binance-coin",
            "SOL": "solana",
            "ADA": "cardano",
            "XRP": "ripple",
            "DOGE": "dogecoin",
            "DOT": "polkadot",
            "AVAX": "avalanche",
            "SHIB": "shiba-inu",
            "MATIC": "polygon",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "ATOM": "cosmos",
            "LTC": "litecoin",
            "NEAR": "near-protocol",
            "APT": "aptos",
            "OP": "optimism",
            "ARB": "arbitrum",
            "TRX": "tron",
            "USDT": "tether",
            "USDC": "usd-coin",
            "BUSD": "binance-usd",
            "DAI": "dai",
            "WETH": "weth",
            "STETH": "staked-ether",
            "CRO": "cronos",
            "ALGO": "algorand",
            "VET": "vechain",
            "SAND": "the-sandbox",
            "MANA": "decentraland",
            "AXS": "axie-infinity",
            "FTM": "fantom",
            "THETA": "theta-token",
            "ICP": "internet-computer",
            "HBAR": "hedera-hashgraph",
            "XLM": "stellar",
            "ETC": "ethereum-classic",
            "FIL": "filecoin",
            "AAVE": "aave",
            "GRT": "the-graph",
            "ENJ": "enjincoin",
            "CHZ": "chiliz",
            "FLOW": "flow",
            "XTZ": "tezos",
        }

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

    def _fetch_aave_yields(self):
        """Fetch Aave yields (existing implementation)"""
        aave_response = requests.get(
            "https://aave-api-v2.aave.com/data/liquidity/v2", timeout=10
        )
        aave_data = aave_response.json()

        yields = {}
        for reserve in aave_data:
            if reserve["symbol"] == "USDC":
                yields["aave_usdc_supply"] = float(reserve["liquidityRate"]) * 100
            if reserve["symbol"] == "USDT":
                yields["aave_usdt_supply"] = float(reserve["liquidityRate"]) * 100
            if reserve["symbol"] == "WETH":
                yields["aave_eth_supply"] = float(reserve["liquidityRate"]) * 100

        return yields

    def _fetch_compound_yields(self):
        """Fetch Compound yields"""
        # Compound API endpoint
        url = "https://api.compound.finance/api/v2/ctoken"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        yields = {}
        for token in data.get("cToken", []):
            if token["underlying_symbol"] == "USDC":
                yields["compound_usdc"] = float(token["supply_rate"]["value"]) * 100
            elif token["underlying_symbol"] == "USDT":
                yields["compound_usdt"] = float(token["supply_rate"]["value"]) * 100
            elif token["underlying_symbol"] == "ETH":
                yields["compound_eth"] = float(token["supply_rate"]["value"]) * 100

        return yields

    def _fetch_defi_pulse_yields(self):
        """Fetch yields from DeFiPulse or similar aggregator"""
        # This would be implemented if DeFiPulse API is available
        # For now, return empty dict to fall through to next source
        return {}

    def _get_fallback_yields(self):
        """Conservative fallback yields based on current market conditions"""
        return {
            "aave_usdc_supply": 4.0,
            "aave_usdt_supply": 3.8,
            "aave_eth_supply": 2.5,
            "compound_usdc": 3.5,
            "compound_usdt": 3.2,
            "compound_eth": 2.2,
            "curve_3pool": 2.2,
            "yearn_usdc": 4.8,
            "uniswap_v3_eth_usdc": 8.5,
            "eth_staking": 4.0,
            "source": "fallback_estimates",
        }

    def _fetch_fed_rate(self):
        """Fetch from Federal Reserve API if available"""
        # This would be implemented if FRED API access is available
        # For now, return None to fall through
        return None

    # Add these helper methods to MultiAPIManager class

    def _validate_chart_data(self, data: Dict) -> bool:
        """Validate chart data format and content"""
        if not isinstance(data, dict):
            return False

        required_fields = ["prices"]
        for field in required_fields:
            if field not in data:
                return False
            if not isinstance(data[field], list):
                return False
            if len(data[field]) < 5:  # Minimum data points
                return False

        return True

    def _map_interval_to_coincap(self, interval: str, days: int) -> str:
        """Map interval to CoinCap format"""
        if days <= 1:
            return "h1"  # Hourly
        elif days <= 7:
            return "h6"  # 6-hourly
        else:
            return "d1"  # Daily

    def _map_interval_to_binance(self, interval: str) -> str:
        """Map interval to Binance format"""
        mapping = {"hourly": "1h", "daily": "1d", "weekly": "1w"}
        return mapping.get(interval, "1d")

    def _map_interval_to_cryptocompare_endpoint(self, interval: str) -> str:
        """Map interval to CryptoCompare endpoint"""
        mapping = {"hourly": "histohour", "daily": "histoday", "weekly": "histoday"}
        return mapping.get(interval, "histoday")

    def _process_coingecko_chart_data(self, data: Dict) -> Dict:
        """Process CoinGecko chart data format"""
        prices = data.get("prices", [])
        market_caps = data.get("market_caps", [])
        volumes = data.get("total_volumes", [])

        return {
            "prices": [[item[0], item[1]] for item in prices],
            "market_caps": [[item[0], item[1]] for item in market_caps],
            "total_volumes": [[item[0], item[1]] for item in volumes],
        }

    def _process_coincap_chart_data(self, data: Dict) -> Dict:
        """Process CoinCap chart data format"""
        history = data.get("data", [])

        prices = []
        market_caps = []
        volumes = []

        for item in history:
            timestamp = int(item.get("time", 0))
            price = float(item.get("priceUsd", 0))
            volume = float(item.get("volumeUsd24Hr", 0))

            prices.append([timestamp, price])
            market_caps.append([timestamp, None])  # Not available in history
            volumes.append([timestamp, volume])

        return {
            "prices": prices,
            "market_caps": market_caps,
            "total_volumes": volumes,
        }

    def _process_binance_chart_data(self, data: List) -> Dict:
        """Process Binance chart data format"""
        prices = []
        volumes = []

        for kline in data:
            timestamp = int(kline[0])
            close_price = float(kline[4])
            volume = float(kline[5])

            prices.append([timestamp, close_price])
            volumes.append([timestamp, volume])

        return {
            "prices": prices,
            "market_caps": [[item[0], None] for item in prices],  # Not available
            "total_volumes": volumes,
        }

    def _process_cryptocompare_chart_data(self, data: Dict) -> Dict:
        """Process CryptoCompare chart data format"""
        history = data.get("Data", {}).get("Data", [])

        prices = []
        volumes = []

        for item in history:
            timestamp = int(item["time"]) * 1000  # Convert to milliseconds
            close_price = float(item["close"])
            volume = float(item.get("volumeto", 0))

            prices.append([timestamp, close_price])
            volumes.append([timestamp, volume])

        return {
            "prices": prices,
            "market_caps": [[item[0], None] for item in prices],  # Not available
            "total_volumes": volumes,
        }


@api_call_with_cache_and_rate_limit(
    cache_duration=300, rate_limit_interval=1.0, max_retries=3, retry_delay=2
)
def get_latest_crypto_price(symbol: str) -> Dict:
    """Get latest price using multi-API fallback mechanism"""
    global api_manager

    # Use the existing multi-API market data method
    market_data = api_manager.fetch_market_data(symbol)
    if market_data:
        return {
            "success": True,
            "symbol": symbol.upper(),
            "price": market_data["current_price"],
            "market_cap": market_data["market_cap"],
            "volume_24h": market_data["total_volume"],
            "change_24h": market_data["price_change_percentage_24h"],
            "timestamp": int(time.time() * 1000),
            "source": market_data["source"],
        }

    raise ValueError(f"No price data available for {symbol}")


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
            if hasattr(self.api_manager, "end_batch_operation"):
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
            "BTC", "ETH", "BNB", "ADA", "SOL", "DOT", "LINK", "UNI", "AAVE",
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
            
        # Load traditional assets with 429 protection
        self._preload_traditional_assets_safe(batch_data)
    
        # Load market metrics with 429 protection
        self._preload_market_metrics_safe(batch_data)
    
        logger.info(
            f"Batch preload completed. Cached {len(batch_data['crypto_prices'])} "
            f"crypto assets and {len(batch_data['traditional_assets'])} traditional assets"
        )
        return batch_data
    
    def _calculate_inter_call_delay(self) -> float:
        """Calculate delay between market_data and historical_data calls for same symbol"""
        base_delay = 0.5  # 500ms base delay

        # Increase delay based on recent 429 errors
        if self.consecutive_429_count > 0:
            # Exponential increase: 0.5s -> 1s -> 2s -> 4s (max)
            multiplier = min(2 ** self.consecutive_429_count, 8)
            calculated_delay = base_delay * multiplier
        else:
            calculated_delay = base_delay

        # Check current API rate limit status
        rate_limited_apis = sum(1 for api in self.apis.keys() if self._is_api_rate_limited(api))
        total_apis = len(self.apis)

        if total_apis > 0:
            rate_limited_ratio = rate_limited_apis / total_apis
            if rate_limited_ratio > 0.3:  # More than 30% APIs are rate limited
                calculated_delay *= 2  # Double the delay

        # Cap the maximum delay
        return min(calculated_delay, 5.0)  # Maximum 5 seconds between calls

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
        available_apis = sum(1 for api in self.apis.keys() if self._is_api_available(api))
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
                    self._calculate_batch_delay(i, len(traditional_symbols))
                )
                time.sleep(yahoo_delay)

            except Exception as e:
                logger.warning(
                    f"Failed to preload {name} ({symbol}): {e}"
                )
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
            logger.warning(
                f"Failed to load market metrics: {e}"
            )
            # Set fallback values
            batch_data["market_metrics"] = {}
            batch_data["fear_greed_index"] = (50, "Neutral", "sideways", "neutral")
            batch_data["risk_free_rate"] = 0.045

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
        try:
            cache_key = "preload_all_market_data_"
            cached_batch = _cache_backend.get(cache_key)

            if not cached_batch:
                logger.info("No batch cache found, triggering preload...")
                batch_data = self.preload_all_market_data()
            else:
                batch_data, timestamp = cached_batch
                # Check if cache is still valid (within 24 hours)
                if time.time() - timestamp > self.batch_cache_duration:
                    logger.info("Batch cache expired, reloading...")
                    batch_data = self.preload_all_market_data()

            if asset_type == "crypto" and symbol in batch_data.get("crypto_prices", {}):
                return batch_data["crypto_prices"][symbol]
            elif asset_type == "traditional":
                for name, data in batch_data.get("traditional_assets", {}).items():
                    if data.get("symbol") == symbol or name == symbol:
                        return data

            return None
        except Exception as e:
            logger.error(
                f"Error getting cached data for {asset_type}:{symbol}: {e}\n{traceback.format_exc()}"
            )
            return None


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


# 在 api_manager.py 中添加的完整集成代码


class EnhancedMultiAPIManager(BatchCacheAPIManager):
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
        result = self.get_cached_data("crypto", symbol)
        if result and result.get("historical_data"):
            cache_age = time.time() - result.get("cached_at", 0)
            if cache_age < 1800:  # 30 minutes freshness
                logger.info(f"Batch cache hit for {symbol} (age: {cache_age:.1f}s)")
                return result["historical_data"]

        # Fallback to original method
        logger.info(f"Using individual API fallback for {symbol}")
        return super().fetch_with_fallback(symbol, days, max_global_retries)

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
