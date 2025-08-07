import os
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loggers import logger
import traceback
from utils.api_decorators import (
    api_call_with_cache_and_rate_limit,
    api_call_with_cache_and_rate_limit_no_429_retry,
    APIRateLimitException,
)


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
