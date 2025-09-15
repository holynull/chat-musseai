import json
from logging import Logger
import logging
import traceback
import numpy as np
import requests
import os
from datetime import datetime, timedelta
from typing import Optional, Union, List
import time

from utils.api_decorators import api_call_with_cache_and_rate_limit


def getLatestQuoteRealTime(
    symbols: str,
    logger: Logger = None,
) -> str:
    """
    Retrieves the latest cryptocurrency quotation data from CryptoCompare API.

    This function fetches real-time price and market data for specified cryptocurrencies
    using the CryptoCompare API. The data includes latest price, market cap,
    volume, and other market metrics.

    Input:
    - symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH".
                    CryptoCompare supports up to 100 symbols per request.

    Output:
    - Returns a JSON string containing latest market data including:
        * Current price in multiple currencies (USD, EUR, etc.)
        * Market cap
        * 24h volume
        * 24h price changes
        * Supply information
        * Other market metrics

    Example usage:
    _getLatestQuote("BTC") - Get latest Bitcoin market data
    _getLatestQuote("ETH") - Get latest Ethereum market data
    _getLatestQuote("BTC,ETH,ADA") - Get multiple cryptocurrencies data
    """
    if logger is None:
        logger = logging.getLogger("getLatestQuoteRealTime")

    try:
        logger.info(f"Get latest quote from CryptoCompare API. {symbols}")

        # CryptoCompare API endpoint for multiple symbol price data
        base_url = "https://min-api.cryptocompare.com/data/pricemultifull"

        # Parameters for the API request
        params = {
            "fsyms": symbols,  # From symbols (the cryptocurrencies we want data for)
            "tsyms": "USD,EUR,BTC",  # To symbols (currencies to convert to)
            "tryConversion": "true",  # Try conversion even if direct trading pair doesn't exist
        }

        # Add API key if available (CryptoCompare has free tier but API key improves limits)
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        if api_key:
            params["api_key"] = api_key

        # Make the API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()  # Raise exception for bad status codes

        data = response.json()

        # Check if the response contains error
        if "Response" in data and data["Response"] == "Error":
            error_msg = data.get("Message", "Unknown error from CryptoCompare API")
            logger.error(f"CryptoCompare API [getLatestQuote] error: {error_msg}")
            return json.dumps(
                {"error": True, "message": error_msg, "requested_symbols": symbols}
            )

        # Process and enhance the response data
        processed_data = {
            "source": "CryptoCompare",
            "timestamp": data.get("MetaData", {}).get("LastUpdateTS", ""),
            "symbols_requested": symbols.split(","),
            "data": {},
        }

        # Extract DISPLAY data (formatted for humans) and RAW data (for calculations)
        display_data = data.get("DISPLAY", {})
        raw_data = data.get("RAW", {})

        # Process each requested symbol
        for symbol in symbols.split(","):
            symbol = symbol.strip().upper()

            if symbol in display_data and symbol in raw_data:
                # Combine display and raw data for comprehensive information
                symbol_data = {
                    "symbol": symbol,
                    "prices": {},
                    "market_data": {},
                    "changes": {},
                    "volume": {},
                    "supply": {},
                }

                # Extract price data for different currencies
                for currency in ["USD", "EUR", "BTC"]:
                    if currency in display_data[symbol]:
                        display_curr = display_data[symbol][currency]
                        raw_curr = raw_data[symbol][currency]

                        symbol_data["prices"][currency] = {
                            "price": display_curr.get("PRICE", ""),
                            "price_raw": raw_curr.get("PRICE", 0),
                            "market_cap": display_curr.get("MKTCAP", ""),
                            "market_cap_raw": raw_curr.get("MKTCAP", 0),
                        }

                        symbol_data["changes"][currency] = {
                            "change_24h": display_curr.get("CHANGE24HOUR", ""),
                            "change_24h_pct": display_curr.get("CHANGEPCT24HOUR", ""),
                            "change_24h_raw": raw_curr.get("CHANGE24HOUR", 0),
                            "change_24h_pct_raw": raw_curr.get("CHANGEPCT24HOUR", 0),
                        }

                        symbol_data["volume"][currency] = {
                            "volume_24h": display_curr.get("VOLUME24HOUR", ""),
                            "volume_24h_to": display_curr.get("VOLUME24HOURTO", ""),
                            "volume_24h_raw": raw_curr.get("VOLUME24HOUR", 0),
                            "volume_24h_to_raw": raw_curr.get("VOLUME24HOURTO", 0),
                        }

                # Add additional market data from USD data (most comprehensive)
                if "USD" in raw_data[symbol]:
                    usd_raw = raw_data[symbol]["USD"]
                    symbol_data["market_data"] = {
                        "circulating_supply": usd_raw.get("CIRCULATINGSUPPLY", 0),
                        "total_supply": usd_raw.get("SUPPLY", 0),
                        "last_update": usd_raw.get("LASTUPDATE", 0),
                        "high_24h": usd_raw.get("HIGH24HOUR", 0),
                        "low_24h": usd_raw.get("LOW24HOUR", 0),
                        "open_24h": usd_raw.get("OPEN24HOUR", 0),
                    }

                processed_data["data"][symbol] = symbol_data
            else:
                # Symbol not found in response
                processed_data["data"][symbol] = {
                    "error": f"Symbol {symbol} not found or not supported",
                    "symbol": symbol,
                }
                logger.warning(f"Symbol {symbol} not found in CryptoCompare response")

        return json.dumps(processed_data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "network_error",
            }
        )
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response from CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "json_decode_error",
            }
        )
    except Exception as e:
        error_msg = f"Unexpected error when calling CryptoCompare API: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "unexpected_error",
            }
        )


@api_call_with_cache_and_rate_limit(
    cache_duration=3600,
    rate_limit_interval=1.2,  # 1.2 seconds interval
    max_retries=2,
    retry_delay=1,
)
def getLatestQuote(
    symbols: str,
    logger: Logger = None,
) -> str:
    """
    Retrieves the latest cryptocurrency quotation data from CryptoCompare API.

    This function fetches real-time price and market data for specified cryptocurrencies
    using the CryptoCompare API. The data includes latest price, market cap,
    volume, and other market metrics.

    Input:
    - symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH".
                    CryptoCompare supports up to 100 symbols per request.

    Output:
    - Returns a JSON string containing latest market data including:
        * Current price in multiple currencies (USD, EUR, etc.)
        * Market cap
        * 24h volume
        * 24h price changes
        * Supply information
        * Other market metrics

    Example usage:
    _getLatestQuote("BTC") - Get latest Bitcoin market data
    _getLatestQuote("ETH") - Get latest Ethereum market data
    _getLatestQuote("BTC,ETH,ADA") - Get multiple cryptocurrencies data
    """
    if logger is None:
        logger = logging.getLogger("getLatestQuote")

    try:
        logger.info(f"Get latest quote from CryptoCompare API. {symbols}")

        # CryptoCompare API endpoint for multiple symbol price data
        base_url = "https://min-api.cryptocompare.com/data/pricemultifull"

        # Parameters for the API request
        params = {
            "fsyms": symbols,  # From symbols (the cryptocurrencies we want data for)
            "tsyms": "USD,EUR,BTC",  # To symbols (currencies to convert to)
            "tryConversion": "true",  # Try conversion even if direct trading pair doesn't exist
        }

        # Add API key if available (CryptoCompare has free tier but API key improves limits)
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        if api_key:
            params["api_key"] = api_key

        # Make the API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()  # Raise exception for bad status codes

        data = response.json()

        # Check if the response contains error
        if "Response" in data and data["Response"] == "Error":
            error_msg = data.get("Message", "Unknown error from CryptoCompare API")
            logger.error(f"CryptoCompare API [getLatestQuote] error: {error_msg}")
            return json.dumps(
                {"error": True, "message": error_msg, "requested_symbols": symbols}
            )

        # Process and enhance the response data
        processed_data = {
            "source": "CryptoCompare",
            "timestamp": data.get("MetaData", {}).get("LastUpdateTS", ""),
            "symbols_requested": symbols.split(","),
            "data": {},
        }

        # Extract DISPLAY data (formatted for humans) and RAW data (for calculations)
        display_data = data.get("DISPLAY", {})
        raw_data = data.get("RAW", {})

        # Process each requested symbol
        for symbol in symbols.split(","):
            symbol = symbol.strip().upper()

            if symbol in display_data and symbol in raw_data:
                # Combine display and raw data for comprehensive information
                symbol_data = {
                    "symbol": symbol,
                    "prices": {},
                    "market_data": {},
                    "changes": {},
                    "volume": {},
                    "supply": {},
                }

                # Extract price data for different currencies
                for currency in ["USD", "EUR", "BTC"]:
                    if currency in display_data[symbol]:
                        display_curr = display_data[symbol][currency]
                        raw_curr = raw_data[symbol][currency]

                        symbol_data["prices"][currency] = {
                            "price": display_curr.get("PRICE", ""),
                            "price_raw": raw_curr.get("PRICE", 0),
                            "market_cap": display_curr.get("MKTCAP", ""),
                            "market_cap_raw": raw_curr.get("MKTCAP", 0),
                        }

                        symbol_data["changes"][currency] = {
                            "change_24h": display_curr.get("CHANGE24HOUR", ""),
                            "change_24h_pct": display_curr.get("CHANGEPCT24HOUR", ""),
                            "change_24h_raw": raw_curr.get("CHANGE24HOUR", 0),
                            "change_24h_pct_raw": raw_curr.get("CHANGEPCT24HOUR", 0),
                        }

                        symbol_data["volume"][currency] = {
                            "volume_24h": display_curr.get("VOLUME24HOUR", ""),
                            "volume_24h_to": display_curr.get("VOLUME24HOURTO", ""),
                            "volume_24h_raw": raw_curr.get("VOLUME24HOUR", 0),
                            "volume_24h_to_raw": raw_curr.get("VOLUME24HOURTO", 0),
                        }

                # Add additional market data from USD data (most comprehensive)
                if "USD" in raw_data[symbol]:
                    usd_raw = raw_data[symbol]["USD"]
                    symbol_data["market_data"] = {
                        "circulating_supply": usd_raw.get("CIRCULATINGSUPPLY", 0),
                        "total_supply": usd_raw.get("SUPPLY", 0),
                        "last_update": usd_raw.get("LASTUPDATE", 0),
                        "high_24h": usd_raw.get("HIGH24HOUR", 0),
                        "low_24h": usd_raw.get("LOW24HOUR", 0),
                        "open_24h": usd_raw.get("OPEN24HOUR", 0),
                    }

                processed_data["data"][symbol] = symbol_data
            else:
                # Symbol not found in response
                processed_data["data"][symbol] = {
                    "error": f"Symbol {symbol} not found or not supported",
                    "symbol": symbol,
                }
                logger.warning(f"Symbol {symbol} not found in CryptoCompare response")

        return json.dumps(processed_data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "network_error",
            }
        )
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response from CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "json_decode_error",
            }
        )
    except Exception as e:
        error_msg = f"Unexpected error when calling CryptoCompare API: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols,
                "error_type": "unexpected_error",
            }
        )

@api_call_with_cache_and_rate_limit(
    cache_duration=1800,  # 30 minutes cache for historical data
    rate_limit_interval=1.5,  # 1.5 seconds interval for kline data
    max_retries=3,
    retry_delay=2,
)
def getKlineData(
    symbol: str,
    period: str = "daily",
    limit: int = 100,
    to_timestamp: Optional[int] = None,
    from_timestamp: Optional[int] = None,
    exchange: str = "CCCAGG",
    logger: Logger = None,
) -> str:
    """
    Retrieves historical cryptocurrency kline (candlestick) data from CryptoCompare API.

    This function fetches OHLCV (Open, High, Low, Close, Volume) historical data
    for specified cryptocurrencies with support for multiple timeframes.

    Args:
        symbol (str): cryptocurrency symbol. Example: "BTC"
        period (str): Time period for kline data. Options:
            - "minute" or "1m": 1-minute klines (7 days limit)
            - "15minute" or "15m": 15-minute klines (30 days limit)
            - "hourly" or "1h": 1-hour klines (365 days limit)
            - "daily" or "1d": 1-day klines (2000 days limit)

        limit (int): Number of data points to return (1-2000, default: 100)
        to_timestamp (Optional[int]): End timestamp (Unix timestamp). If None, uses current time
        from_timestamp (Optional[int]): Start timestamp (Unix timestamp). Takes precedence over limit
        exchange (str): Exchange to get data from (default: "CCCAGG" for aggregated data)
        logger (Logger): Logger instance for logging operations

    Returns:
        str: JSON string containing historical kline data
    """
    if logger is None:
        logger = logging.getLogger("cryptocompare_kline")

    try:
        logger.info(
            f"Get kline data from CryptoCompare API. Symbol: {symbol}, Period: {period}, Limit: {limit}"
        )

        # Validate and normalize period parameter
        period_mapping = {
            "minute": {
                "endpoint": "histominute",
                "period_name": "minute",
                "aggregate": 1,
                "max_days": 7,  # CryptoCompare limit for minute data
            },
            "1m": {
                "endpoint": "histominute",
                "period_name": "minute",
                "aggregate": 1,
                "max_days": 7,
            },
            "15m": {
                "endpoint": "histominute",
                "period_name": "15minute",
                "aggregate": 15,
                "max_days": 30,  # 15-minute data limit
            },
            "15minute": {
                "endpoint": "histominute",
                "period_name": "15minute",
                "aggregate": 15,
                "max_days": 30,
            },
            "hourly": {
                "endpoint": "histohour",
                "period_name": "hourly",
                "aggregate": 1,
                "max_days": 365,  # Hourly data limit
            },
            "1h": {
                "endpoint": "histohour",
                "period_name": "hourly",
                "aggregate": 1,
                "max_days": 365,
            },
            "daily": {
                "endpoint": "histoday",
                "period_name": "daily",
                "aggregate": 1,
                "max_days": 2000,
            },
            "1d": {
                "endpoint": "histoday",
                "period_name": "daily",
                "aggregate": 1,
                "max_days": 2000,
            },
        }

        if period.lower() not in period_mapping:
            error_msg = f"Unsupported period '{period}'. Supported: {list(period_mapping.keys())}"
            logger.error(error_msg)
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "requested_symbol": symbol,
                    "error_type": "invalid_parameter",
                }
            )

        endpoint_info = period_mapping[period.lower()]
        endpoint = endpoint_info["endpoint"]
        period_name = endpoint_info["period_name"]
        max_days = endpoint_info["max_days"]

        # Validate limit parameter
        if not isinstance(limit, int) or limit < 1 or limit > 2000:
            error_msg = f"Invalid limit '{limit}'. Must be integer between 1 and 2000"
            logger.error(error_msg)
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "requested_symbol": symbol.split(","),
                    "error_type": "invalid_parameter",
                }
            )

        # Process timestamp parameters
        current_timestamp = int(time.time())

        if to_timestamp is None:
            to_timestamp = current_timestamp

        # **KEY FIX: Add data availability validation**
        max_seconds_back = max_days * 86400  # Convert days to seconds
        earliest_allowed_timestamp = current_timestamp - max_seconds_back

        if from_timestamp is not None:
            # If from_timestamp is provided, validate it's within limits
            if from_timestamp < earliest_allowed_timestamp:
                error_msg = f"Requested start time is too far back. {period_name} data is only available for the last {max_days} days. Earliest available: {datetime.fromtimestamp(earliest_allowed_timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
                logger.error(error_msg)
                return json.dumps(
                    {
                        "error": True,
                        "message": error_msg,
                        "requested_symbol": symbol,
                        "error_type": "data_limit_exceeded",
                        "max_days_available": max_days,
                        "earliest_timestamp": earliest_allowed_timestamp,
                    }
                )

            # Calculate limit based on time range
            time_diff = to_timestamp - from_timestamp
            if period_name == "minute":
                calculated_limit = min(int(time_diff / 60), 2000)
            elif period_name == "15minute":
                calculated_limit = min(int(time_diff / 900), 2000)
            elif period_name == "hourly":
                calculated_limit = min(int(time_diff / 3600), 2000)
            else:  # daily
                calculated_limit = min(int(time_diff / 86400), 2000)

            limit = max(1, calculated_limit)
        else:
            # **KEY FIX: Validate limit doesn't exceed available data range**
            period_seconds = _get_period_seconds(period_name)
            if endpoint_info.get("aggregate", 1) > 1:
                period_seconds *= endpoint_info["aggregate"]

            requested_timespan = limit * period_seconds
            if requested_timespan > max_seconds_back:
                # Adjust limit to fit within available data range
                max_limit = max_seconds_back // period_seconds
                old_limit = limit
                limit = max(1, int(max_limit))
                logger.warning(
                    f"Requested limit {old_limit} exceeds available data range for {period_name}. Adjusted to {limit} (max {max_days} days of data)"
                )

        # Split symbols and process each one
        processed_data = {
            "source": "CryptoCompare",
            "period": period_name,
            "symbol_requested": symbol,
            "timestamp_range": {
                # **KEY FIX: Ensure from timestamp is within limits**
                "from": max(
                    to_timestamp - (limit * _get_period_seconds(period_name)),
                    earliest_allowed_timestamp,
                ),
                "to": to_timestamp,
            },
            "data": {},
        }

        # Get API key if available
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")

        # Process each symbol
        try:
            # Build API URL and parameters
            base_url = f"https://min-api.cryptocompare.com/data/v2/{endpoint}"

            params = {
                "fsym": symbol,  # From symbol
                "tsym": "USDT",  # To symbol (USD for standard pricing)
                "limit": limit,
                "toTs": to_timestamp,
                "e": exchange,
            }

            # Add aggregate parameter for sub-hourly periods
            if endpoint_info.get("aggregate", 1) > 1:
                params["aggregate"] = endpoint_info["aggregate"]

            if api_key:
                params["api_key"] = api_key

            # Make API request for this symbol
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # **KEY FIX: Improved error handling - return immediately on API error**
            if data.get("Response") == "Error":
                error_msg = data.get("Message", f"Unknown error for symbol {symbol}")
                logger.error(
                    f"CryptoCompare API [getKlineData] error for {symbol}: {error_msg}"
                )

                # Check if it's a data limit error and provide helpful guidance
                if (
                    "only available for the last" in error_msg.lower()
                    or "data limit" in error_msg.lower()
                ):
                    enhanced_error_msg = f"{error_msg}. Try using a shorter time period or reduce the limit parameter. For {period_name} data, maximum history is {max_days} days."
                    return json.dumps(
                        {
                            "error": True,
                            "message": enhanced_error_msg,
                            "requested_symbol": symbol,
                            "error_type": "data_limit_exceeded",
                            "max_days_available": max_days,
                            "suggestion": f"For {period_name} data, use limit <= {max_seconds_back // _get_period_seconds(period_name)} or choose a longer time period like 'hourly' or 'daily'.",
                        }
                    )

                return json.dumps(
                    {
                        "error": True,
                        "message": error_msg,
                        "requested_symbol": symbol,
                        "error_type": "api_error",
                    }
                )

            # Extract historical data
            hist_data = data.get("Data", {}).get("Data", [])

            if not hist_data:
                logger.warning(f"No historical data found for symbol {symbol}")
                processed_data["data"][symbol] = {
                    "error": True,
                    "message": f"No historical data available for {symbol}",
                    "symbol": symbol,
                }
                return json.dumps(processed_data, ensure_ascii=False, indent=2)

            # Process kline data
            klines = []
            for candle in hist_data:
                # Skip incomplete candles (where all OHLC values are 0)
                if (
                    candle.get("open", 0) == 0
                    and candle.get("high", 0) == 0
                    and candle.get("low", 0) == 0
                    and candle.get("close", 0) == 0
                ):
                    continue

                kline_data = {
                    "timestamp": candle.get("time", 0),
                    "datetime": datetime.fromtimestamp(candle.get("time", 0)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "open": float(candle.get("open", 0)),
                    "high": float(candle.get("high", 0)),
                    "low": float(candle.get("low", 0)),
                    "close": float(candle.get("close", 0)),
                    "volume": float(
                        candle.get("volumefrom", 0)
                    ),  # Volume in base currency
                    "volume_to": float(
                        candle.get("volumeto", 0)
                    ),  # Volume in quote currency (USD)
                    "conversionType": candle.get("conversionType", ""),
                    "conversionSymbol": candle.get("conversionSymbol", ""),
                }
                klines.append(kline_data)

            # Sort klines by timestamp (ascending)
            klines.sort(key=lambda x: x["timestamp"])

            # Add processed symbol data
            processed_data["data"][symbol] = {
                "symbol": symbol,
                "klines": klines,
                "count": len(klines),
                "period": period_name,
                "exchange": exchange,
                "aggregated": data.get("Data", {}).get("Aggregated", False),
                "time_from": data.get("Data", {}).get("TimeFrom", 0),
                "time_to": data.get("Data", {}).get("TimeTo", 0),
            }

            logger.info(
                f"Successfully retrieved {len(klines)} {period_name} klines for {symbol}"
            )

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error for symbol {symbol}: {str(e)}"
            logger.error(error_msg)
            processed_data["data"][symbol] = {
                "error": True,
                "message": error_msg,
                "symbol": symbol,
                "error_type": "network_error",
            }

        except Exception as e:
            error_msg = f"Unexpected error for symbol {symbol}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            processed_data["data"][symbol] = {
                "error": True,
                "message": error_msg,
                "symbol": symbol,
                "error_type": "processing_error",
            }

        return json.dumps(processed_data, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"Unexpected error when calling CryptoCompare Kline API: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbol": symbol,
                "error_type": "unexpected_error",
            }
        )


def _get_period_seconds(period_name: str) -> int:
    """
    Helper function to get the number of seconds for each period type.

    Args:
        period_name (str): The period name ("minute", "15minute", "hourly", "daily")

    Returns:
        int: Number of seconds in the period
    """
    period_seconds = {
        "minute": 60,
        "15minute": 900,  # 15 minutes = 15 * 60 seconds
        "hourly": 3600,
        "daily": 86400,
    }
    return period_seconds.get(period_name, 86400)


@api_call_with_cache_and_rate_limit(
    cache_duration=60,  # 1 minute cache for order book data (real-time sensitive)
    rate_limit_interval=0.5,  # 0.5 seconds interval for order book requests
    max_retries=3,
    retry_delay=1,
)
def getOrderBookDepth(
    symbols: str,
    exchange: str,
    depth: int = 20,
    logger: Logger = None,
) -> str:
    return _getOrderBookDepth(symbols, exchange, depth, logger)


def _getOrderBookDepth(
    symbols: str,
    exchange: str,
    depth: int = 20,
    logger: Logger = None,
) -> str:
    """
    Retrieves order book depth data for one or more cryptocurrency symbols from CryptoCompare API.

    This function fetches real-time order book data showing bid and ask prices with their
    corresponding volumes, providing insights into market liquidity and trading activity.

    Args:
        symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC"
        depth (int): Number of price levels to retrieve for both bids and asks (1-50, default: 20)
        exchange (str): Exchange to get order book from (default: "CCCAGG" for aggregated data)
        logger (Logger): Logger instance for logging operations

    Returns:
        str: JSON string containing order book depth data with structure:
            {
                "source": "CryptoCompare",
                "symbols_requested": ["BTC", "ETH"],
                "exchange": "CCCAGG",
                "timestamp": 1234567890,
                "datetime": "2024-01-01 12:00:00",
                "depth": 20,
                "data": {
                    "BTC": {
                        "symbol": "BTC",
                        "bids": [...],
                        "asks": [...],
                        "summary": {...},
                        "market_depth_analysis": {...}
                    },
                    "ETH": {
                        "symbol": "ETH",
                        "bids": [...],
                        "asks": [...],
                        "summary": {...},
                        "market_depth_analysis": {...}
                    }
                }
            }

    Example usage:
        getOrderBookDepth("BTC") - Get 20-level order book for Bitcoin
        getOrderBookDepth("BTC,ETH") - Get order books for both Bitcoin and Ethereum
        getOrderBookDepth("ETH", depth=10) - Get 10-level order book for Ethereum
        getOrderBookDepth("BTC,ETH,ADA", depth=50, exchange="Binance") - Get 50-level order books from Binance
    """
    if logger is None:
        logger = logging.getLogger("cryptocompare_orderbook")

    try:
        logger.info(
            f"Get order book depth from CryptoCompare API. Symbols: {symbols}, Depth: {depth}, Exchange: {exchange}"
        )

        # Validate parameters
        is_valid, error_message = _validateOrderBookParameters(symbols, depth, exchange)
        if not is_valid:
            logger.error(f"Invalid parameters: {error_message}")
            return json.dumps(
                {
                    "error": True,
                    "message": error_message,
                    "symbols_requested": symbols.split(",") if symbols else [],
                    "error_type": "invalid_parameter",
                }
            )

        # Parse and clean symbols
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            error_msg = "No valid symbols provided"
            logger.error(error_msg)
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "symbols_requested": [],
                    "error_type": "invalid_parameter",
                }
            )

        # CryptoCompare API endpoint for order book data
        base_url = "https://min-api.cryptocompare.com/data/ob/l1/top"

        # Parameters for the API request - use fsyms for multiple symbols
        params = {
            "fsyms": symbols,  # Use original symbols string as shown in API documentation
            "tsyms": "USDT,USDC",  # To symbol (quote currency)
            "limit": depth,  # Number of levels for both bids and asks
            "e": exchange,  # Exchange
        }

        # Add API key if available
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        if api_key:
            params["api_key"] = api_key

        # Make the API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check if the response contains error
        if "Response" in data and data["Response"] == "Error":
            error_msg = data.get("Message", "Unknown error from CryptoCompare API")
            logger.error(f"CryptoCompare API [getOrderBookDepth] error: {error_msg}")
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "symbols_requested": symbol_list,
                    "error_type": "api_error",
                }
            )

        # Initialize response structure
        processed_data = {
            "source": "CryptoCompare",
            "symbols_requested": symbol_list,
            "exchange": exchange,
            "timestamp": int(time.time()),
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "depth": depth,
            "data": {},
        }

        # Extract order book data - API may return data for multiple symbols
        order_book_data = data.get("Data", {})
        if not order_book_data:
            error_msg = f"No order book data available for symbols: {symbols}"
            logger.warning(error_msg)
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "symbols_requested": symbol_list,
                    "error_type": "no_data",
                }
            )

        # Process each symbol in the response
        for symbol in symbol_list:
            symbol = symbol.upper()

            # Check if this symbol has data in the response
            symbol_data = order_book_data.get(symbol, {})
            if not symbol_data:
                logger.warning(f"No order book data found for symbol {symbol}")
                processed_data["data"][symbol] = {
                    "error": True,
                    "message": f"No order book data available for {symbol}",
                    "symbol": symbol,
                    "error_type": "no_data",
                }
                continue

            # Process bids and asks for this symbol
            raw_bids = symbol_data.get("bids", [])
            raw_asks = symbol_data.get("asks", [])

            processed_bids = []
            processed_asks = []
            total_bid_volume = 0
            total_ask_volume = 0

            # Process bids (buy orders) - sort by price descending
            for i, bid in enumerate(raw_bids[:depth]):
                price = float(bid.get("price", 0))
                volume = float(bid.get("quantity", 0))
                total_bid_volume += volume

                processed_bids.append(
                    {
                        "price": price,
                        "price_formatted": f"${price:,.2f}",
                        "volume": volume,
                        "total_volume": total_bid_volume,
                        "level": i + 1,
                    }
                )

            # Process asks (sell orders) - sort by price ascending
            for i, ask in enumerate(raw_asks[:depth]):
                price = float(ask.get("price", 0))
                volume = float(ask.get("quantity", 0))
                total_ask_volume += volume

                processed_asks.append(
                    {
                        "price": price,
                        "price_formatted": f"${price:,.2f}",
                        "volume": volume,
                        "total_volume": total_ask_volume,
                        "level": i + 1,
                    }
                )

            # Calculate summary metrics for this symbol
            best_bid = processed_bids[0]["price"] if processed_bids else 0
            best_ask = processed_asks[0]["price"] if processed_asks else 0
            spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0
            spread_percent = (spread / best_bid * 100) if best_bid > 0 else 0
            mid_price = (
                (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
            )

            # Build symbol data
            processed_data["data"][symbol] = {
                "symbol": symbol,
                "bids": processed_bids,
                "asks": processed_asks,
                "summary": {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": round(spread, 8),
                    "spread_percent": round(spread_percent, 4),
                    "total_bid_volume": round(total_bid_volume, 8),
                    "total_ask_volume": round(total_ask_volume, 8),
                    "mid_price": round(mid_price, 8),
                    "bid_levels": len(processed_bids),
                    "ask_levels": len(processed_asks),
                },
                "market_depth_analysis": {
                    "liquidity_score": _calculateLiquidityScore(
                        processed_bids, processed_asks
                    ),
                    "order_book_imbalance": _calculateOrderBookImbalance(
                        total_bid_volume, total_ask_volume
                    ),
                    "price_impact_1pct": _calculatePriceImpact(
                        processed_bids, processed_asks, 0.01
                    ),
                },
            }

        logger.info(
            f"Successfully retrieved order book depth for symbols: {', '.join(symbol_list)}"
        )

        return json.dumps(processed_data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling CryptoCompare order book API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "symbols_requested": symbols.split(",") if symbols else [],
                "error_type": "network_error",
            }
        )
    except json.JSONDecodeError as e:
        error_msg = (
            f"Failed to parse JSON response from CryptoCompare order book API: {str(e)}"
        )
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "symbols_requested": symbols.split(",") if symbols else [],
                "error_type": "json_decode_error",
            }
        )
    except Exception as e:
        error_msg = (
            f"Unexpected error when calling CryptoCompare order book API: {str(e)}"
        )
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "symbols_requested": symbols.split(",") if symbols else [],
                "error_type": "unexpected_error",
            }
        )


def _validateOrderBookParameters(
    symbols: str, depth: int, exchange: str
) -> tuple[bool, str]:
    """
    Validates parameters for order book depth requests.

    Args:
        symbols (str): Comma-separated cryptocurrency symbols
        depth (int): Number of price levels to retrieve
        exchange (str): Exchange name

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Validate symbols
    if not symbols or not symbols.strip():
        return False, "Symbols parameter cannot be empty"

    # Parse and validate individual symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return False, "No valid symbols found in symbols parameter"

    if len(symbol_list) > 10:  # Reasonable limit for multiple symbols
        return False, "Too many symbols requested (maximum 10 allowed)"

    for symbol in symbol_list:
        if len(symbol) < 2 or len(symbol) > 10:
            return False, f"Invalid symbol format: {symbol}"

    # Validate depth
    if not isinstance(depth, int) or depth < 1 or depth > 50:
        return False, "Depth must be an integer between 1 and 50"

    # Validate exchange
    if not exchange or not exchange.strip():
        return False, "Exchange parameter cannot be empty"

    return True, "Valid parameters"


def _validateOrderBookParameters(
    symbol: str, depth: int, exchange: str
) -> tuple[bool, str]:
    """
    Validates parameters for order book depth requests.

    Args:
        symbol (str): Cryptocurrency symbol
        depth (int): Number of price levels to retrieve
        exchange (str): Exchange name

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Validate symbol
    if not symbol or not symbol.strip():
        return False, "Symbol parameter cannot be empty"

    symbol = symbol.strip().upper()
    if len(symbol) < 2 or len(symbol) > 10:
        return False, f"Invalid symbol format: {symbol}"

    # Validate depth
    if not isinstance(depth, int) or depth < 1 or depth > 50:
        return False, "Depth must be an integer between 1 and 50"

    # Validate exchange
    if not exchange or not exchange.strip():
        return False, "Exchange parameter cannot be empty"

    return True, "Valid parameters"


def _calculateLiquidityScore(bids: List[dict], asks: List[dict]) -> float:
    """
    Calculates a liquidity score based on order book depth and volume.

    Args:
        bids (List[dict]): List of bid orders
        asks (List[dict]): List of ask orders

    Returns:
        float: Liquidity score (0-100)
    """
    if not bids or not asks:
        return 0.0

    try:
        # Calculate volume-weighted depth
        total_bid_volume = sum(bid["volume"] for bid in bids)
        total_ask_volume = sum(ask["volume"] for ask in asks)
        total_volume = total_bid_volume + total_ask_volume

        # Calculate spread impact
        best_bid = bids[0]["price"] if bids else 0
        best_ask = asks[0]["price"] if asks else 0
        spread_pct = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 100

        # Liquidity score formula (higher volume and lower spread = better liquidity)
        volume_score = min(total_volume / 100, 50)  # Cap at 50 points
        spread_score = max(50 - spread_pct * 10, 0)  # Lower spread = higher score
        depth_score = min(len(bids) + len(asks), 20)  # More levels = better

        liquidity_score = (volume_score + spread_score + depth_score) / 1.2
        return round(min(liquidity_score, 100), 2)

    except Exception:
        return 0.0


def _calculateOrderBookImbalance(bid_volume: float, ask_volume: float) -> dict:
    """
    Calculates order book imbalance metrics.

    Args:
        bid_volume (float): Total bid volume
        ask_volume (float): Total ask volume

    Returns:
        dict: Imbalance metrics
    """
    total_volume = bid_volume + ask_volume
    if total_volume == 0:
        return {
            "ratio": 0.5,
            "imbalance": 0.0,
            "dominance": "neutral",
            "strength": "none",
        }

    bid_ratio = bid_volume / total_volume
    ask_ratio = ask_volume / total_volume
    imbalance = (
        bid_ratio - ask_ratio
    )  # Positive = buy pressure, Negative = sell pressure

    # Determine dominance and strength
    if abs(imbalance) < 0.1:
        dominance = "neutral"
        strength = "weak"
    elif imbalance > 0:
        dominance = "buy_pressure"
        strength = "strong" if imbalance > 0.3 else "moderate"
    else:
        dominance = "sell_pressure"
        strength = "strong" if imbalance < -0.3 else "moderate"

    return {
        "ratio": round(bid_ratio, 4),
        "imbalance": round(imbalance, 4),
        "dominance": dominance,
        "strength": strength,
    }


def _calculatePriceImpact(
    bids: List[dict], asks: List[dict], volume_pct: float
) -> dict:
    """
    Calculates estimated price impact for a given volume percentage.

    Args:
        bids (List[dict]): List of bid orders
        asks (List[dict]): List of ask orders
        volume_pct (float): Volume percentage to simulate (e.g., 0.01 for 1%)

    Returns:
        dict: Price impact analysis
    """
    if not bids or not asks:
        return {"buy_impact": 0.0, "sell_impact": 0.0}

    try:
        # Calculate total available volume
        total_bid_volume = sum(bid["volume"] for bid in bids)
        total_ask_volume = sum(ask["volume"] for ask in asks)

        # Volume to simulate
        target_volume = max(total_bid_volume, total_ask_volume) * volume_pct

        # Calculate buy impact (market buy order)
        buy_impact = 0.0
        remaining_volume = target_volume
        best_ask = asks[0]["price"] if asks else 0
        for ask in asks:
            if remaining_volume <= 0:
                break
            volume_taken = min(remaining_volume, ask["volume"])
            if best_ask > 0:
                buy_impact = ((ask["price"] - best_ask) / best_ask) * 100
            remaining_volume -= volume_taken

        # Calculate sell impact (market sell order)
        sell_impact = 0.0
        remaining_volume = target_volume
        best_bid = bids[0]["price"] if bids else 0

        for bid in bids:
            if remaining_volume <= 0:
                break
            volume_taken = min(remaining_volume, bid["volume"])
            if best_bid > 0:
                sell_impact = ((best_bid - bid["price"]) / best_bid) * 100
            remaining_volume -= volume_taken

        return {
            "buy_impact": round(buy_impact, 4),
            "sell_impact": round(sell_impact, 4),
            "volume_simulated": target_volume,
        }

    except Exception:
        return {"buy_impact": 0.0, "sell_impact": 0.0, "volume_simulated": 0.0}


@api_call_with_cache_and_rate_limit(
    cache_duration=30,  # 30 seconds cache for real-time order book
    rate_limit_interval=0.3,  # 0.3 seconds interval for frequent updates
    max_retries=2,
    retry_delay=0.5,
)
def getRealtimeOrderBookDepth(
    symbols: str,  # 修改参数名
    exchange: str,
    depth: int = 10,
    logger: Logger = None,
) -> str:
    """
    Retrieves real-time order book depth with minimal caching for high-frequency trading applications.

    This is an optimized version of getOrderBookDepth with shorter cache duration
    and faster rate limits for applications requiring the freshest order book data.

    Args:
        symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC"
        depth (int): Number of price levels (1-25, default: 10 for faster response)
        exchange (str): Exchange to get order book from
        logger (Logger): Logger instance

    Returns:
        str: JSON string with real-time order book data
    """
    if logger is None:
        logger = logging.getLogger("cryptocompare_realtime_orderbook")

    # Limit depth for real-time requests
    if depth > 25:
        depth = 25
        logger.warning(f"Depth limited to 25 for real-time requests")

    logger.info(f"Get real-time order book for {symbols}")

    return _getOrderBookDepth(
        symbols=symbols, depth=depth, exchange=exchange, logger=logger  # 使用新的参数名
    )


@api_call_with_cache_and_rate_limit(
    cache_duration=30,  # 30 seconds cache for trade data (real-time sensitive)
    rate_limit_interval=0.8,  # 0.8 seconds interval for trade requests
    max_retries=3,
    retry_delay=1,
)
def getRecentTrades(
    symbol: str,
    limit: int = 100,
    exchange: str = "CCCAGG",
    to_timestamp: Optional[int] = None,
    logger: Logger = None,
) -> str:
    """
    Retrieves recent trade records for a single cryptocurrency symbol from CryptoCompare API.

    This function fetches the most recent completed trades for a specified cryptocurrency,
    providing detailed information about market activity including prices, volumes,
    timestamps, and trade directions (buy/sell).

    Args:
        symbol (str): Single cryptocurrency symbol. Example: "BTC"
        limit (int): Number of recent trades to retrieve (1-2000, default: 100)
        exchange (str): Exchange to get trade data from (default: "CCCAGG" for aggregated data)
        to_timestamp (Optional[int]): End timestamp (Unix timestamp). If None, uses current time
        logger (Logger): Logger instance for logging operations

    Returns:
        str: JSON string containing recent trade data with structure:
            {
                "source": "CryptoCompare",
                "symbol": "BTC",
                "exchange": "CCCAGG",
                "timestamp": 1234567890,
                "datetime": "2024-01-01 12:00:00",
                "limit": 100,
                "trades": [
                    {
                        "trade_id": "12345",
                        "timestamp": 1234567890,
                        "datetime": "2024-01-01 12:00:00",
                        "price": 45000.0,
                        "price_formatted": "$45,000.00",
                        "quantity": 0.5,
                        "total_value": 22500.0,
                        "total_value_formatted": "$22,500.00",
                        "side": "buy",  # "buy" or "sell"
                        "exchange": "Binance"
                    }
                ],
                "count": 100,
                "summary": {
                    "total_volume": 150.5,
                    "total_value": 6750000.0,
                    "average_price": 44850.25,
                    "highest_price": 45500.0,
                    "lowest_price": 44200.0,
                    "buy_trades": 65,
                    "sell_trades": 35,
                    "buy_volume": 95.2,
                    "sell_volume": 55.3,
                    "time_range": {
                        "from": 1234567000,
                        "to": 1234567890,
                        "duration_minutes": 14.83
                    }
                },
                "market_activity_analysis": {
                    "trade_frequency": 6.75,  # trades per minute
                    "volume_distribution": {
                        "small_trades": 45,  # < 0.1 BTC
                        "medium_trades": 35,  # 0.1 - 1 BTC
                        "large_trades": 20   # > 1 BTC
                    },
                    "price_trend": "bullish",  # "bullish", "bearish", "sideways"
                    "market_pressure": "buy_dominant"  # "buy_dominant", "sell_dominant", "balanced"
                }
            }

    Example usage:
        getRecentTrades("BTC") - Get last 100 trades for Bitcoin
        getRecentTrades("ETH", limit=50) - Get last 50 trades for Ethereum
        getRecentTrades("BTC", exchange="Binance", limit=200) - Get 200 trades from Binance
        getRecentTrades("ETH", to_timestamp=1672531200) - Get trades up to specific time
    """
    if logger is None:
        logger = logging.getLogger("cryptocompare_trades")

    try:
        logger.info(
            f"Get recent trades from CryptoCompare API. Symbol: {symbol}, Limit: {limit}, Exchange: {exchange}"
        )

        # Validate parameters
        is_valid, error_message = _validateTradeParameters(symbol, limit, exchange)
        if not is_valid:
            logger.error(f"Invalid parameters: {error_message}")
            return json.dumps(
                {
                    "error": True,
                    "message": error_message,
                    "requested_symbol": symbol,
                    "error_type": "invalid_parameter",
                }
            )

        # Process timestamp parameter
        current_timestamp = int(time.time())
        if to_timestamp is None:
            to_timestamp = current_timestamp

        # CryptoCompare API endpoint for trade data
        # base_url = "https://min-api.cryptocompare.com/data/v2/histotrade"
        base_url = "https://min-api.cryptocompare.com/data/histotrade"

        # Parameters for the API request
        params = {
            "fsym": symbol.upper(),  # From symbol (the cryptocurrency)
            "tsym": "USD",  # To symbol (quote currency)
            "limit": limit,  # Number of trades to retrieve
            "toTs": to_timestamp,  # End timestamp
            "e": exchange,  # Exchange
        }

        # Add API key if available
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        if api_key:
            params["api_key"] = api_key

        # Make the API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check if the response contains error
        if "Response" in data and data["Response"] == "Error":
            error_msg = data.get("Message", "Unknown error from CryptoCompare API")
            logger.error(f"CryptoCompare API [getRecentTrades] error: {error_msg}")
            return json.dumps(
                {
                    "error": True,
                    "message": error_msg,
                    "requested_symbol": symbol,
                    "error_type": "api_error",
                }
            )

        # Extract trade data
        trade_data = data.get("Data", {}).get("Data", [])
        if not trade_data:
            logger.warning(f"No trade data found for symbol {symbol}")
            return json.dumps(
                {
                    "error": True,
                    "message": f"No recent trade data available for {symbol}",
                    "requested_symbol": symbol,
                    "error_type": "no_data",
                }
            )

        # Process trades
        processed_trades = []
        total_volume = 0
        total_value = 0
        buy_trades = 0
        sell_trades = 0
        buy_volume = 0
        sell_volume = 0
        prices = []
        timestamps = []

        for trade in trade_data:
            # Skip invalid trades
            if (
                not trade.get("time")
                or not trade.get("price")
                or not trade.get("quantity")
            ):
                continue

            timestamp = trade.get("time", 0)
            price = float(trade.get("price", 0))
            quantity = float(trade.get("quantity", 0))
            total_trade_value = price * quantity

            # Determine trade side (CryptoCompare may not always provide this)
            # We'll use a heuristic based on price movement or mark as 'unknown'
            side = trade.get("side", "unknown")
            if side == "unknown":
                # Simple heuristic: compare with previous trade price
                if processed_trades:
                    prev_price = processed_trades[-1]["price"]
                    side = "buy" if price >= prev_price else "sell"
                else:
                    side = "buy"  # Default for first trade

            trade_record = {
                "trade_id": trade.get("id", f"{timestamp}_{len(processed_trades)}"),
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "price": price,
                "price_formatted": f"${price:,.2f}",
                "quantity": quantity,
                "total_value": total_trade_value,
                "total_value_formatted": f"${total_trade_value:,.2f}",
                "side": side,
                "exchange": trade.get("exchange", exchange),
            }

            processed_trades.append(trade_record)

            # Update statistics
            total_volume += quantity
            total_value += total_trade_value
            prices.append(price)
            timestamps.append(timestamp)

            if side == "buy":
                buy_trades += 1
                buy_volume += quantity
            else:
                sell_trades += 1
                sell_volume += quantity

        # Sort trades by timestamp (most recent first)
        processed_trades.sort(key=lambda x: x["timestamp"], reverse=True)

        # Calculate summary statistics
        if prices:
            average_price = total_value / total_volume if total_volume > 0 else 0
            highest_price = max(prices)
            lowest_price = min(prices)
            time_range_seconds = (
                max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0
            )
            duration_minutes = time_range_seconds / 60
        else:
            average_price = highest_price = lowest_price = 0
            duration_minutes = 0

        # Calculate market activity analysis
        trade_frequency = len(processed_trades) / max(
            duration_minutes, 1
        )  # trades per minute

        # Volume distribution analysis
        small_trades = sum(1 for t in processed_trades if t["quantity"] < 0.1)
        medium_trades = sum(1 for t in processed_trades if 0.1 <= t["quantity"] <= 1.0)
        large_trades = sum(1 for t in processed_trades if t["quantity"] > 1.0)

        # Price trend analysis
        if len(prices) >= 2:
            first_half_avg = sum(prices[: len(prices) // 2]) / (len(prices) // 2)
            second_half_avg = sum(prices[len(prices) // 2 :]) / (
                len(prices) - len(prices) // 2
            )

            if second_half_avg > first_half_avg * 1.002:  # 0.2% threshold
                price_trend = "bullish"
            elif second_half_avg < first_half_avg * 0.998:
                price_trend = "bearish"
            else:
                price_trend = "sideways"
        else:
            price_trend = "sideways"

        # Market pressure analysis
        if buy_volume > sell_volume * 1.2:
            market_pressure = "buy_dominant"
        elif sell_volume > buy_volume * 1.2:
            market_pressure = "sell_dominant"
        else:
            market_pressure = "balanced"

        # Build response
        processed_data = {
            "source": "CryptoCompare",
            "symbol": symbol.upper(),
            "exchange": exchange,
            "timestamp": current_timestamp,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "limit": limit,
            "trades": processed_trades,
            "count": len(processed_trades),
            "summary": {
                "total_volume": round(total_volume, 8),
                "total_value": round(total_value, 2),
                "average_price": round(average_price, 2),
                "highest_price": round(highest_price, 2),
                "lowest_price": round(lowest_price, 2),
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "buy_volume": round(buy_volume, 8),
                "sell_volume": round(sell_volume, 8),
                "time_range": {
                    "from": min(timestamps) if timestamps else 0,
                    "to": max(timestamps) if timestamps else 0,
                    "duration_minutes": round(duration_minutes, 2),
                },
            },
            "market_activity_analysis": {
                "trade_frequency": round(trade_frequency, 2),
                "volume_distribution": {
                    "small_trades": small_trades,
                    "medium_trades": medium_trades,
                    "large_trades": large_trades,
                },
                "price_trend": price_trend,
                "market_pressure": market_pressure,
            },
        }

        logger.info(
            f"Successfully retrieved {len(processed_trades)} recent trades for {symbol}"
        )

        return json.dumps(processed_data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling CryptoCompare trades API: {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbol": symbol,
                "error_type": "network_error",
            }
        )
    except json.JSONDecodeError as e:
        error_msg = (
            f"Failed to parse JSON response from CryptoCompare trades API: {str(e)}"
        )
        logger.error(error_msg)
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbol": symbol,
                "error_type": "json_decode_error",
            }
        )
    except Exception as e:
        error_msg = f"Unexpected error when calling CryptoCompare trades API: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": error_msg,
                "requested_symbol": symbol,
                "error_type": "unexpected_error",
            }
        )


def _validateTradeParameters(
    symbol: str, limit: int, exchange: str
) -> tuple[bool, str]:
    """
    Validates parameters for trade data requests.

    Args:
        symbol (str): Cryptocurrency symbol
        limit (int): Number of trades to retrieve
        exchange (str): Exchange name

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Validate symbol
    if not symbol or not symbol.strip():
        return False, "Symbol parameter cannot be empty"

    symbol = symbol.strip().upper()
    if len(symbol) < 2 or len(symbol) > 10:
        return False, f"Invalid symbol format: {symbol}"

    # Validate limit
    if not isinstance(limit, int) or limit < 1 or limit > 2000:
        return False, "Limit must be an integer between 1 and 2000"

    # Validate exchange
    if not exchange or not exchange.strip():
        return False, "Exchange parameter cannot be empty"

    return True, "Valid parameters"


@api_call_with_cache_and_rate_limit(
    cache_duration=10,  # 10 seconds cache for ultra real-time trades
    rate_limit_interval=0.5,  # 0.5 seconds interval for high frequency requests
    max_retries=2,
    retry_delay=0.5,
)
def getRealtimeTrades(
    symbol: str,
    limit: int = 50,
    exchange: str = "CCCAGG",
    logger: Logger = None,
) -> str:
    """
    Retrieves ultra real-time recent trades with minimal caching for high-frequency applications.

    This is an optimized version of getRecentTrades with shorter cache duration
    and faster rate limits for applications requiring the freshest trade data.

    Args:
        symbol (str): Single cryptocurrency symbol
        limit (int): Number of recent trades (1-100, default: 50 for faster response)
        exchange (str): Exchange to get trade data from
        logger (Logger): Logger instance

    Returns:
        str: JSON string with real-time trade data
    """
    if logger is None:
        logger = logging.getLogger("cryptocompare_realtime_trades")

    # Limit trades for real-time requests
    if limit > 100:
        limit = 100
        logger.warning(f"Limit reduced to 100 for real-time trade requests")

    logger.info(f"Get real-time trades for {symbol}")

    return getRecentTrades(symbol=symbol, limit=limit, exchange=exchange, logger=logger)
