# src/utils/api_manager.py
import os
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loggers import logger
import traceback

# In api_manager.py, add cache dictionary
_price_cache = {}


def get_crypto_historical_data(
    coin_id: str, vs_currency: str = "usd", days: int = 365
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
    # Check cache
    cache_key = f"{coin_id}_{vs_currency}_{days}"
    current_time = time.time()

    # If cache exists and not expired (24 hour validity)
    if cache_key in _price_cache:
        cache_data, timestamp = _price_cache[cache_key]
        if current_time - timestamp < 86400:  # 24 hours = 86400 seconds
            return cache_data

    # First try using the global API manager
    global api_manager

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

    # Use fallback mechanism to get data
    result = api_manager.fetch_with_fallback(symbol, days)

    if result and "prices" in result and len(result["prices"]) > 0:
        # Convert to format needed by performance_analysis.py
        prices_data = []
        for i, price in enumerate(result["prices"]):
            if i < len(result["dates"]):
                date_str = result["dates"][i]
                try:
                    date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
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

        # Update cache
        _price_cache[cache_key] = (response_data, current_time)

        return response_data

    # If unable to get data, return failure
    failed_response = {
        "success": False,
        "error": "Could not fetch price data from any available API",
        "coin_id": coin_id,
    }

    # Cache failed results too, but only for a short time (5 minutes) to avoid frequent retries of failing APIs
    _price_cache[cache_key] = (failed_response, current_time)

    return failed_response


class MultiAPIManager:
    def __init__(self):
        self.apis = {
            "coingecko": {
                "base_url": "https://api.coingecko.com/api/v3",
                "rate_limit": 1.0,  # Slightly reduced from 1.2 for better reliability
                "daily_limit": 10000,
                "priority": 1,  # Highest priority
                "last_request": 0,
                "retry_count": 0,
                "max_retries": 3,
            },
            "coincap": {
                "base_url": "https://rest.coincap.io/v3",  # Updated from API 2.0 to API 3.0
                "rate_limit": 0.1,
                "daily_limit": None,
                "priority": 2,
                "last_request": 0,
                "api_key": os.getenv(
                    "COINCAP_API_KEY"
                ),  # Add API key support for authentication
            },
            "cryptocompare": {
                "base_url": "https://min-api.cryptocompare.com/data",
                "rate_limit": 0.05,
                "daily_limit": 100000,
                "priority": 3,  # Third priority
                "last_request": 0,
            },
            "binance": {
                "base_url": "https://api.binance.com/api/v3",
                "rate_limit": 0.1,
                "daily_limit": None,
                "priority": 4,  # Fourth priority
                "last_request": 0,
            },
            "yahoo": {
                "base_url": "https://query1.finance.yahoo.com/v8/finance/chart",
                "rate_limit": 0.5,
                "daily_limit": None,
                "priority": 5,  # Lowest priority
                "last_request": 0,
            },
        }

        # 添加基准映射常量
        self.benchmark_mapping = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SP500": "^GSPC",
            "NASDAQ": "^IXIC",
            "GOLD": "GC=F",
            "USD": "DX-Y.NYB",
        }

        # 风险无风险利率源
        self.risk_free_rate_symbol = "^TNX"

        self.symbol_mapping = self._init_symbol_mapping()

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

    def _wait_for_rate_limit(self, api_name: str):
        """等待满足API速率限制"""
        api_config = self.apis[api_name]
        elapsed = time.time() - api_config["last_request"]
        if elapsed < api_config["rate_limit"]:
            time.sleep(api_config["rate_limit"] - elapsed)
        api_config["last_request"] = time.time()

    def fetch_historical_prices_coingecko(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """
        Fetch historical prices from CoinGecko with enhanced error handling and retry logic
        """
        max_retries = self.apis["coingecko"].get("max_retries", 3)

        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit("coingecko")

                # Get coin ID mapping if not cached
                if not self.symbol_mapping["coingecko"]:
                    self.symbol_mapping["coingecko"] = self._get_coingecko_mapping()

                coin_id = self.symbol_mapping["coingecko"].get(symbol.upper())
                if not coin_id:
                    #  Try common mappings for major coins
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

                url = (
                    f"{self.apis['coingecko']['base_url']}/coins/{coin_id}/market_chart"
                )
                params = {"vs_currency": "usd", "days": days, "interval": "daily"}

                # Enhanced headers to avoid 401 errors
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
                    # Reset retry count on success
                    self.apis["coingecko"]["retry_count"] = 0
                    return result
                else:
                    logger.warning(
                        f"CoinGecko returned empty data for {symbol} on attempt {attempt + 1}"
                    )

            except requests.exceptions.HTTPError as e:
                logger.debug(traceback.format_exc())
                if e.response.status_code == 401:
                    logger.error(
                        f"CoinGecko API unauthorized error (401) for {symbol} on attempt {attempt + 1}"
                    )
                    # Increase rate limit on 401 errors
                    self.apis["coingecko"]["rate_limit"] = min(
                        5.0, self.apis["coingecko"]["rate_limit"] * 1.5
                    )
                elif e.response.status_code == 429:
                    logger.error(
                        f"CoinGecko API rate limit (429) for {symbol} on attempt {attempt + 1}"
                    )
                    # Exponential backoff for rate limits
                    backoff_time = 2**attempt
                    logger.info(f"Backing off for {backoff_time} seconds...")
                    time.sleep(backoff_time)
                    self.apis["coingecko"]["rate_limit"] = min(
                        10.0, self.apis["coingecko"]["rate_limit"] * 2
                    )
                elif e.response.status_code == 404:
                    logger.error(
                        f"CoinGecko API not found (404) for {symbol} - invalid coin ID"
                    )
                    break  # Don't retry on 404
                else:
                    logger.error(f"CoinGecko API HTTP error for {symbol}: {e}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"Retrying CoinGecko in {wait_time} seconds...")
                    time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                logger.debug(traceback.format_exc())
                logger.error(
                    f"CoinGecko API request failed for {symbol} on attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 1
                    time.sleep(wait_time)
            except Exception as e:
                logger.debug(traceback.format_exc())
                logger.error(
                    f"CoinGecko API unexpected error for {symbol} on attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(1)

            # All attempts failed
            self.apis["coingecko"]["retry_count"] += 1
            logger.error(
                f"CoinGecko API failed for {symbol} after {max_retries} attempts"
            )
            return None

    def fetch_historical_prices_coincap(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """Fetch historical prices from CoinCap API 3.0 with authentication"""
        try:
            self._wait_for_rate_limit("coincap")

            # CoinCap uses asset IDs
            asset_id = self.symbol_mapping["coincap"].get(symbol.upper())
            if not asset_id:
                asset_id = symbol.lower()  # fallback

            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)

            url = f"{self.apis['coincap']['base_url']}/assets/{asset_id}/history"
            params = {"interval": "d1", "start": start_time, "end": end_time}

            # Add authentication header if API key is available
            headers = {}
            if self.apis["coincap"].get("api_key"):
                headers["Authorization"] = f"Bearer {self.apis['coincap']['api_key']}"

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            return self._process_coincap_data(data)

        except Exception as e:
            logger.error(f"CoinCap API 3.0 failed for {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return None

    def fetch_historical_prices_binance(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """从Binance获取历史价格"""
        try:
            self._wait_for_rate_limit("binance")

            # Binance uses USDT pairs
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

        except Exception as e:
            logger.error(f"Binance API failed for {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return None

    def fetch_historical_prices_cryptocompare(
        self, symbol: str, days: int = 90
    ) -> Optional[Dict]:
        """从CryptoCompare获取历史价格"""
        try:
            self._wait_for_rate_limit("cryptocompare")

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

        except Exception as e:
            logger.error(f"CryptoCompare API failed for {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return None

    def fetch_with_fallback(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """
        Use multi-API failover mechanism with CoinGecko priority
        """
        logger.info(f"Starting API fallback for {symbol} with CoinGecko priority")

        # First priority: Try CoinGecko with enhanced error handling
        logger.info(f"Trying CoinGecko (priority 1) for {symbol}")
        try:
            # Add user agent to avoid rate limiting
            self.apis["coingecko"]["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )

            result = self.fetch_historical_prices_coingecko(symbol, days)

            if result and len(result.get("prices", [])) > 10:
                logger.info(f"Successfully fetched data from CoinGecko for {symbol}")
                return result
            else:
                logger.warning(f"CoinGecko returned insufficient data for {symbol}")

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.warning(f"CoinGecko API failed for {symbol}: {e}")
            # Don't immediately give up on CoinGecko - might be temporary issue

        # Second priority: Try reliable free APIs in order
        free_apis = ["coincap", "cryptocompare", "binance"]
        for api_name in free_apis:
            try:
                logger.info(f"Trying {api_name} (fallback) for {symbol}")

                if api_name == "coincap":
                    result = self.fetch_historical_prices_coincap(symbol, days)
                elif api_name == "cryptocompare":
                    result = self.fetch_historical_prices_cryptocompare(symbol, days)
                elif api_name == "binance":
                    result = self.fetch_historical_prices_binance(symbol, days)
                else:
                    continue

                if result and len(result.get("prices", [])) > 10:
                    logger.info(
                        f"Successfully fetched data from {api_name} for {symbol}"
                    )
                    return result

            except Exception as e:
                logger.debug(traceback.format_exc())
                logger.warning(f"API {api_name} failed for {symbol}: {e}")
                continue

        # Third priority: Retry CoinGecko with different parameters
        logger.info(f"Retrying CoinGecko with relaxed parameters for {symbol}")
        try:
            # Try with shorter period if original failed
            shorter_days = min(days, 30)
            result = self.fetch_historical_prices_coingecko(symbol, shorter_days)

            if result and len(result.get("prices", [])) > 5:
                logger.info(
                    f"Successfully fetched reduced data from CoinGecko for {symbol}"
                )
                return result

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.warning(f"CoinGecko retry failed for {symbol}: {e}")

        # Fourth priority: Try remaining APIs as last resort
        remaining_apis = ["yahoo"]
        for api_name in remaining_apis:
            try:
                logger.info(f"Trying {api_name} (last resort) for {symbol}")

                method_name = f"fetch_historical_prices_{api_name}"
                if hasattr(self, method_name):
                    method = getattr(self, method_name)
                    result = method(symbol, days)

                    if result and len(result.get("prices", [])) > 10:
                        logger.info(
                            f"Successfully fetched data from {api_name} for {symbol}"
                        )
                        return result

            except Exception as e:
                logger.debug(traceback.format_exc())
                logger.warning(f"API {api_name} failed for {symbol}: {e}")
                continue

        logger.error(f"All APIs failed for {symbol}")
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
                self._wait_for_rate_limit("coingecko")

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

    def fetch_market_data_coingecko(self, symbol: str) -> Optional[Dict]:
        """
        Fetch current market data from CoinGecko with caching, rate limiting and retry logic
        """
        try:
            self._wait_for_rate_limit("coingecko")

            url = f"{self.apis['coingecko']['base_url']}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": symbol.lower(),
                "per_page": 1,
                "page": 1,
                "sparkline": False,
                "price_change_percentage": "1h,24h,7d",
            }

            headers = {
                "User-Agent": self.apis["coingecko"].get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"CoinGecko market data API failed for {symbol}: {e}")
            return None

    def fetch_market_chart_coingecko(
        self, symbol: str, days: str = "30", interval: str = "daily"
    ) -> Optional[Dict]:
        """
        Fetch market chart data from CoinGecko with caching and rate limiting
        """
        try:
            self._wait_for_rate_limit("coingecko")

            url = f"{self.apis['coingecko']['base_url']}/coins/{symbol.lower()}/market_chart"
            params = {"vs_currency": "usd", "days": days, "interval": interval}

            headers = {
                "User-Agent": self.apis["coingecko"].get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"CoinGecko market chart API failed for {symbol}: {e}")
            return None

    def fetch_yahoo_finance_data(self, symbol: str, period: str = "1y") -> Dict:
        """
        Fetch stock/index data from Yahoo Finance

        Args:
            symbol: Yahoo Finance symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

        Returns:
            Dict containing price history
        """
        try:
            # Add yahoo to apis config if not exists
            if "yahoo" not in self.apis:
                self.apis["yahoo"] = {
                    "base_url": "https://query1.finance.yahoo.com/v8/finance/chart",
                    "rate_limit": 0.5,  # 2 requests per second
                    "daily_limit": None,
                    "priority": 5,
                    "last_request": 0,
                }

            self._wait_for_rate_limit("yahoo")

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

        except requests.exceptions.RequestException as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Yahoo Finance API request failed for {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol}
        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Unexpected error fetching Yahoo Finance data: {e}")
            return {"success": False, "error": str(e), "symbol": symbol}

    def _process_yahoo_data(self, data: Dict, symbol: str) -> Dict:
        """Process Yahoo Finance data format"""
        try:
            chart_data = data["chart"]["result"][0]
            timestamps = chart_data["timestamp"]
            indicators = chart_data["indicators"]["quote"][0]

            prices = []
            for i, timestamp in enumerate(timestamps):
                if indicators["close"][i] is not None:
                    prices.append(
                        {
                            "timestamp": timestamp * 1000,  # Convert to milliseconds
                            "date": datetime.fromtimestamp(timestamp),
                            "price": indicators["close"][i],
                            "open": indicators["open"][i],
                            "high": indicators["high"][i],
                            "low": indicators["low"][i],
                            "volume": (
                                indicators["volume"][i]
                                if indicators["volume"][i]
                                else 0
                            ),
                        }
                    )

            return {"success": True, "symbol": symbol, "prices": prices}

        except Exception as e:
            logger.debug(traceback.format_exc())
            logger.error(f"Error processing Yahoo Finance data for {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol}

    def get_risk_free_rate(self) -> float:
        """
        Get current risk-free rate from 10-year Treasury yield

        Returns:
            Risk-free rate as decimal (e.g., 0.045 for 4.5%)
        """
        try:
            data = self.fetch_yahoo_finance_data("^TNX", "5d")
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
                result = get_crypto_historical_data(coin_id, "usd", days)
                if result["success"]:
                    return result
                # If failed, try direct method
                return self.fetch_historical_prices_coingecko(benchmark, days)
        else:
            symbol = benchmark_mapping.get(benchmark, benchmark)
            return self.fetch_yahoo_finance_data(symbol)

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
                data = get_crypto_historical_data(coin_id, "usd", 30)

                # If failed, try direct method
                if not data["success"]:
                    data = self.fetch_historical_prices_coingecko(symbol, 30)
            else:
                data = self.fetch_yahoo_finance_data(symbol, period="1mo")

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
                    data = get_crypto_historical_data(symbol.lower(), "usd", days)
                else:
                    data = self.fetch_yahoo_finance_data(symbol, "1y")

                results[symbol] = data

                # Add small delay to respect rate limits
                time.sleep(0.1)

            except Exception as e:
                logger.debug(traceback.format_exc())
                logger.error(f"Failed to fetch data for {symbol}: {e}")
                results[symbol] = {"success": False, "error": str(e)}

        return results


def get_latest_crypto_price(symbol: str) -> Dict:
    """
    Get latest price for a cryptocurrency using CoinCap API 3.0 with authentication

    Args:
        symbol: Cryptocurrency symbol (e.g. 'BTC')

    Returns:
        Dict with price information
    """
    try:
        # Try CoinCap first (most reliable for latest prices)
        api_manager._wait_for_rate_limit("coincap")

        # CoinCap uses asset IDs
        asset_id = api_manager.symbol_mapping["coincap"].get(symbol.upper())
        if not asset_id:
            # Common mappings
            common_mappings = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "BNB": "binance-coin",
                "SOL": "solana",
            }
            asset_id = common_mappings.get(symbol.upper(), symbol.lower())

        url = f"{api_manager.apis['coincap']['base_url']}/assets/{asset_id}"

        # Add authentication header if API key is available
        headers = {}
        if api_manager.apis["coincap"].get("api_key"):
            headers["Authorization"] = (
                f"Bearer {api_manager.apis['coincap']['api_key']}"
            )

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json().get("data", {})
        if data and "priceUsd" in data:
            return {
                "success": True,
                "symbol": symbol.upper(),
                "price": float(data["priceUsd"]),
                "market_cap": float(data.get("marketCapUsd", 0)),
                "volume_24h": float(data.get("volumeUsd24Hr", 0)),
                "change_24h": float(data.get("changePercent24Hr", 0)),
                "timestamp": int(time.time() * 1000),
                "source": "coincap_v3",
            }
    except Exception as e:
        logger.debug(traceback.format_exc())
        logger.warning(f"CoinCap API 3.0 failed for latest price of {symbol}: {e}")

    # If CoinCap fails, try CryptoCompare
    try:
        api_manager._wait_for_rate_limit("cryptocompare")

        url = f"{api_manager.apis['cryptocompare']['base_url']}/price"
        params = {"fsym": symbol.upper(), "tsyms": "USD"}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data and "USD" in data:
            return {
                "success": True,
                "symbol": symbol.upper(),
                "price": float(data["USD"]),
                "timestamp": int(time.time() * 1000),
                "source": "cryptocompare",
            }
    except Exception as e:
        logger.debug(traceback.format_exc())
        logger.warning(f"CryptoCompare API failed for latest price of {symbol}: {e}")

    # All APIs failed
    return {
        "success": False,
        "symbol": symbol.upper(),
        "error": "Failed to get latest price from any API",
    }


# 全局实例
api_manager = MultiAPIManager()


# 在文件末尾添加全局函数，保持向后兼容性
def get_risk_free_rate_global() -> float:
    """Global function for backward compatibility"""
    return api_manager.get_risk_free_rate()


def get_benchmark_price_data_global(benchmark: str, days: int = 365) -> Dict:
    """Global function for backward compatibility"""
    return api_manager.get_benchmark_price_data(benchmark, days)


def get_asset_price_at_date_global(symbol: str, target_date: datetime) -> float:
    """Global function for backward compatibility"""
    return api_manager.get_asset_price_at_date(symbol, target_date)
