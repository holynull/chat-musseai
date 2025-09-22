from collections import defaultdict
import datetime
from logging import Logger
import logging
import time
import traceback
from typing import Dict, List
from langchain.agents import tool
import requests
import json
from tradingview_ta import TA_Handler, Interval, Exchange
import os
from loggers import logger

from utils.api.cryptocompare import getLatestQuoteRealTime, getRealtimeOrderBookDepth
from tradingview_screener import Query, Column


@tool
def getLatestQuote(symbols: str) -> str:
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
        * Current price in multiple currencies (USD, EUR, BTC)
        * Market cap
        * 24h volume
        * 24h price changes
        * Supply information
        * High/Low prices
        * Other market metrics

    Example usage:
    getLatestQuote("BTC") - Get latest Bitcoin market data
    getLatestQuote("ETH") - Get latest Ethereum market data
    getLatestQuote("BTC,ETH,ADA") - Get multiple cryptocurrencies data
    """
    logger.info("Tool calling getLatestQuote")
    return getLatestQuoteRealTime(symbols=symbols)


@tool
def get_trade_pair_and_exchanges(
    symbol: str, market_type: str = "crypto"
) -> Dict[str, List[str]]:
    """
    Query all related trade pair and corresponding exchanges by base currency

    Args:
        symbol: Base currency code (e.g., 'BTC', 'ETH', 'ADA')
        market_type: Market type ('crypto', 'stock', 'forex', etc.)

    Returns:
        Dict[str, List[str]]: Dictionary of {symbol: [exchange1, exchange2, ...]}
    """
    try:
        logger.info(
            f"Querying all trading pairs and exchanges related to {symbol.upper()}..."
        )

        base_currency_upper = symbol.upper()

        # Execute query - returns (total_count, dataframe)
        total_count, df = (
            Query()
            .set_markets("crypto")
            .select("name", "exchange")  # Symbol  # Exchange
            .where(
                # Column('type').like(f"{market_type}*"),
                Column("name").like(
                    f"{base_currency_upper}*"
                )  # Starts with base currency
            )
            .get_scanner_data()
        )

        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return {}

        # Build mapping from symbol to exchanges
        symbol_exchange_map = defaultdict(list)

        # Iterate over DataFrame rows
        for _, row in df.iterrows():
            symbol = row.get("name", "")
            exchange = row.get("exchange", "")

            if symbol and exchange:
                # Ensure it starts with base currency
                if symbol.upper().startswith(base_currency_upper):
                    symbol_exchange_map[symbol].append(exchange)

        # Convert to regular dict, deduplicate and sort exchange lists
        result = {}
        for symbol, exchanges in symbol_exchange_map.items():
            result[symbol] = sorted(list(set(exchanges)))

        # Sort by symbol
        result = dict(sorted(result.items()))

        logger.info(
            f"Found {len(result)} related trading pairs (total records: {total_count}):"
        )
        total_exchanges = sum(len(exchanges) for exchanges in result.values())
        logger.info(f"Total {total_exchanges} exchange-symbol combinations")

        # Show first few examples
        for i, (symbol, exchanges) in enumerate(list(result.items())[:5]):
            logger.info(
                f"  {symbol}: {len(exchanges)} exchanges ({', '.join(exchanges[:3])}{'...' if len(exchanges) > 3 else ''})"
            )

        if len(result) > 5:
            logger.info(f"  ... and {len(result) - 5} more trading pairs")

        return result

    except Exception as e:
        logger.error(f"Failed to query {symbol}: {e}")
        return {}


@tool
def get_indicators(trade_pair: str, exchange: str, interval: str) -> str:
    """
    Retrieves technical analysis indicators for cryptocurrency trading pairs using TradingView data.

    This function fetches comprehensive technical analysis indicators including moving averages,
    oscillators, and other technical metrics that can be used for trading strategy development
    and market analysis. The data is sourced from TradingView's technical analysis engine.

    Args:
        trade_pair (str): The trade pair return from `get_symbols_and_exchanges`
        exchange (str): The exchange name where the trading pair is listed, return from `get_symbols_and_exchanges`.
        interval (str): The time interval for technical analysis.
                       Supported intervals include:
                       - "1m", "5m", "15m", "30m" (minutes)
                       - "1h", "2h", "4h" (hours)
                       - "1d" (daily)
                       - "1W" (weekly)
                       - "1M" (monthly)

    Returns:
        str: A dictionary containing technical indicators data including:
             - Moving averages (EMA, SMA for various periods)
             - Oscillators (RSI, MACD, Stochastic, etc.)
             - Trend indicators (ADX, Aroon, etc.)
             - Volume indicators
             - Support/resistance levels
             - Other technical analysis metrics

             If an error occurs, returns the exception object.

    Examples:
        get_indicators("BTC", "BINANCE", "1d") - Get daily Bitcoin indicators from Binance
        get_indicators("ETH", "COINBASE", "4h") - Get 4-hour Ethereum indicators from Coinbase
        get_indicators("ADA", "KRAKEN", "1h") - Get hourly Cardano indicators from Kraken

    Note:
        - The function automatically creates a USDT trading pair (e.g., BTC -> BTCUSDT)
        - Make sure the specified exchange supports the requested trading pair
        - Different exchanges may have varying data availability for different intervals
        - TradingView data quality and availability may vary between exchanges

    Raises:
        Exception: Various exceptions may occur including:
                  - Invalid symbol/exchange combination
                  - Network connectivity issues
                  - TradingView API limitations or rate limits
                  - Unsupported interval for the specified exchange
                  - Trading pair not found on the specified exchange
    """
    logger.info("get_indicators")
    try:
        btc_usdt = TA_Handler(
            symbol=trade_pair,
            screener="crypto",
            exchange=exchange,
            interval=interval,
        )
        indicators = btc_usdt.get_analysis().indicators
        return indicators
    except Exception as e:
        logger.error(traceback.format_exc())
        return e


from langchain.agents import tool
from utils.api.cryptocompare import getKlineData as _getKlineData
from utils.api.cryptocompare import getRecentTrades
from utils.api.cryptocompare import getRealtimeOrderBookDepth

from utils.api.cryptocompare import getRealtimeTrades as _getRealtimeTrades
from loggers import logger


@tool
def get_historical_klines(
    symbol: str,
    period: str = "daily",
    limit: int = 100,
    to_timestamp: int = None,
    from_timestamp: int = None,
    exchange: str = "CCCAGG",
) -> str:
    """
    Retrieves historical cryptocurrency kline (candlestick) data for technical analysis.

    This function fetches OHLCV (Open, High, Low, Close, Volume) historical data
    which is essential for technical analysis and trading strategy development.

    Args:
        symbol (str): Cryptocurrency symbol (e.g., "BTC", "ETH")
        period (str): Time period. Options:
            - "1m", "minute": 1-minute klines
            - "1h", "hourly": 1-hour klines
            - "1d", "daily": 1-day klines (default)
        limit (int): Number of data points (1-2000, default: 100)
        to_timestamp (int): End timestamp (Unix). If None, uses current time
        from_timestamp (int): Start timestamp (Unix). Takes precedence over limit
        exchange (str): Exchange name (default: "CCCAGG" for aggregated data)

    Returns:
        str: JSON string containing historical OHLCV data with:
             - timestamp, open, high, low, close, volume
             - datetime formatted strings
             - period and exchange information
             - data quality indicators

    Example usage:
        get_historical_klines("BTC", "daily", 30) - Get 30 daily Bitcoin candles
        get_historical_klines("ETH", "1h", 24) - Get 24 hourly Ethereum candles
        get_historical_klines("BTC", "1m", 60) - Get 60 minute Bitcoin candles
    """
    return _getKlineData(
        symbol=symbol,
        period=period,
        limit=limit,
        to_timestamp=to_timestamp,
        from_timestamp=from_timestamp,
        exchange=exchange,
        logger=logger,
    )


# @tool
# def get_order_book(
#     symbols: str,
#     exchange: str,
#     depth: int = 20,
# ) -> str:
#     """
#     Retrieves real-time order book depth data for market liquidity analysis.

#     This function fetches bid and ask prices with their volumes, providing
#     crucial information about market depth, liquidity, and potential support/resistance levels.

#     Args:
#         symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC"
#         depth (int): Number of price levels for both bids and asks (1-50, default: 20)
#         exchange (str): The exchange name where the trading pair is listed, return from `get_symbols_and_exchanges`.

#     Returns:
#         str: JSON string containing order book data with:
#              - bids: buy orders sorted by price (highest first)
#              - asks: sell orders sorted by price (lowest first)
#              - summary: best bid/ask, spread, total volumes
#              - market_depth_analysis: liquidity score, imbalance metrics
#              - price_impact analysis for different volume levels

#     Example usage:
#         get_order_book("BTC") - Get 20-level Bitcoin order book
#         get_order_book("ETH", 10) - Get 10-level Ethereum order book
#         get_order_book("BTC", 50, "Binance") - Get 50-level from Binance
#     """
#     logger.info("get_order_book starting.")
#     return get_realtime_order_book(
#         symbols=symbols, depth=depth, exchange=exchange, logger=logger
#     )


# @tool
# def get_recent_trades(
#     symbol: str, limit: int = 100, exchange: str = "CCCAGG", to_timestamp: int = None
# ) -> str:
#     """
#     Retrieves recent completed trade records for market activity analysis.

#     This function fetches the most recent executed trades, providing insights into
#     market activity, trading patterns, and price movements.

#     Args:
#         symbol (str): Cryptocurrency symbol (e.g., "BTC", "ETH")
#         limit (int): Number of recent trades to retrieve (1-2000, default: 100)
#         exchange (str): Exchange name (default: "CCCAGG" for aggregated data)
#         to_timestamp (int): End timestamp (Unix). If None, uses current time

#     Returns:
#         str: JSON string containing recent trades with:
#              - trade records: timestamp, price, quantity, side (buy/sell)
#              - summary statistics: total volume, average price, high/low
#              - market_activity_analysis: trade frequency, volume distribution
#              - price_trend and market_pressure indicators

#     Example usage:
#         get_recent_trades("BTC") - Get last 100 Bitcoin trades
#         get_recent_trades("ETH", 50) - Get last 50 Ethereum trades
#         get_recent_trades("BTC", 200, "Binance") - Get 200 trades from Binance
#     """
#     return getRecentTrades(
#         symbol=symbol,
#         limit=limit,
#         exchange=exchange,
#         to_timestamp=to_timestamp,
#         logger=logger,
#     )


# @tool
# def get_realtime_order_book(symbols: str, exchange: str, depth: int = 10) -> str:
#     """
#     Retrieves ultra real-time order book data with minimal caching for high-frequency trading.

#     Optimized version with shorter cache duration and faster rate limits for applications
#     requiring the freshest order book data.

#     Args:
#         symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC". , the same as `get_order_book`'s parameter
#         depth (int): Number of price levels (1-25, default: 10 for speed)
#         exchange (str): The exchange name, the same as `get_order_book`'s parameter.

#     Returns:
#         str: JSON string with real-time order book data

#     Example usage:
#         get_realtime_order_book("BTC") - Get real-time Bitcoin order book
#         get_realtime_order_book("ETH", 5) - Get 5-level Ethereum order book
#     """
#     logger.info("get_realtime_order_book starting")
#     return getRealtimeOrderBookDepth(
#         symbols=symbols, depth=depth, exchange=exchange, logger=logger
#     )


# @tool
# def get_realtime_trades(symbol: str, limit: int = 50, exchange: str = "CCCAGG") -> str:
#     """
#     Retrieves ultra real-time trade records with minimal caching for high-frequency applications.

#     Optimized version with shorter cache duration and faster rate limits for applications
#     requiring the freshest trade data.

#     Args:
#         symbol (str): Cryptocurrency symbol
#         limit (int): Number of recent trades (1-100, default: 50 for speed)
#         exchange (str): Exchange name

#     Returns:
#         str: JSON string with real-time trade data

#     Example usage:
#         get_realtime_trades("BTC") - Get real-time Bitcoin trades
#         get_realtime_trades("ETH", 25) - Get 25 recent Ethereum trades
#     """
#     return _getRealtimeTrades(
#         symbol=symbol, limit=limit, exchange=exchange, logger=logger
#     )


# @tool
# def get_volume_profile(
#     symbol: str, period: str = "daily", limit: int = 30, exchange: str = "CCCAGG"
# ) -> str:
#     """
#     Calculates volume profile data by analyzing trading volume at different price levels.

#     This function processes historical kline data to generate volume profile information,
#     which helps identify key support/resistance levels and high-volume trading zones.

#     Args:
#         symbol (str): Cryptocurrency symbol
#         period (str): Time period for analysis ("daily", "1h", "1m")
#         limit (int): Number of periods to analyze (default: 30)
#         exchange (str): Exchange name

#     Returns:
#         str: JSON string containing volume profile with:
#              - price_levels: volume distribution by price ranges
#              - poc: Point of Control (highest volume price level)
#              - value_area: high/low boundaries containing 70% of volume
#              - volume_nodes: significant volume clusters

#     Example usage:
#         get_volume_profile("BTC") - Get 30-day Bitcoin volume profile
#         get_volume_profile("ETH", "1h", 24) - Get 24-hour Ethereum profile
#     """
#     try:
#         # Get historical data first
#         kline_data = _getKlineData(
#             symbol=symbol, period=period, limit=limit, exchange=exchange, logger=logger
#         )

#         import json

#         data = json.loads(kline_data)

#         if data.get("error"):
#             return kline_data  # Return error as-is

#         klines = data.get("data", {}).get(symbol, {}).get("klines", [])
#         if not klines:
#             return json.dumps(
#                 {
#                     "error": True,
#                     "message": f"No kline data available for volume profile calculation",
#                     "symbol": symbol,
#                 }
#             )

#         # Calculate volume profile
#         price_volume_map = {}
#         total_volume = 0

#         for kline in klines:
#             high = kline["high"]
#             low = kline["low"]
#             volume = kline["volume"]
#             close = kline["close"]

#             # Distribute volume across price levels (simplified approach)
#             price_range = high - low if high > low else 0.01
#             num_levels = max(
#                 10, int(price_range / (close * 0.001))
#             )  # Dynamic levels based on price

#             for i in range(num_levels):
#                 price_level = low + (price_range * i / num_levels)
#                 price_key = round(price_level, 2)

#                 if price_key not in price_volume_map:
#                     price_volume_map[price_key] = 0

#                 price_volume_map[price_key] += volume / num_levels
#                 total_volume += volume / num_levels

#         # Sort by volume descending
#         sorted_levels = sorted(
#             price_volume_map.items(), key=lambda x: x[1], reverse=True
#         )

#         # Find Point of Control (POC)
#         poc_price = sorted_levels[0][0] if sorted_levels else 0
#         poc_volume = sorted_levels[0][1] if sorted_levels else 0

#         # Calculate Value Area (70% of total volume)
#         value_area_volume = total_volume * 0.7
#         cumulative_volume = 0
#         value_area_prices = []

#         for price, volume in sorted_levels:
#             if cumulative_volume < value_area_volume:
#                 value_area_prices.append(price)
#                 cumulative_volume += volume
#             else:
#                 break

#         value_area_high = max(value_area_prices) if value_area_prices else 0
#         value_area_low = min(value_area_prices) if value_area_prices else 0

#         # Identify significant volume nodes (top 20% by volume)
#         significant_nodes = sorted_levels[: max(1, len(sorted_levels) // 5)]

#         result = {
#             "source": "CryptoCompare_VolumeProfile",
#             "symbol": symbol.upper(),
#             "period": period,
#             "exchange": exchange,
#             "analysis_period": f"{limit} {period} periods",
#             "timestamp": int(time.time()),
#             "price_levels": [
#                 {
#                     "price": price,
#                     "volume": round(volume, 4),
#                     "volume_percentage": round((volume / total_volume) * 100, 2),
#                 }
#                 for price, volume in sorted_levels[:50]  # Top 50 levels
#             ],
#             "point_of_control": {
#                 "price": poc_price,
#                 "volume": round(poc_volume, 4),
#                 "volume_percentage": round((poc_volume / total_volume) * 100, 2),
#             },
#             "value_area": {
#                 "high": value_area_high,
#                 "low": value_area_low,
#                 "range": round(value_area_high - value_area_low, 2),
#                 "volume_percentage": 70.0,
#             },
#             "volume_nodes": [
#                 {
#                     "price": price,
#                     "volume": round(volume, 4),
#                     "significance": "high" if volume > poc_volume * 0.8 else "medium",
#                 }
#                 for price, volume in significant_nodes
#             ],
#             "summary": {
#                 "total_volume": round(total_volume, 4),
#                 "price_range": {
#                     "high": max(price_volume_map.keys()) if price_volume_map else 0,
#                     "low": min(price_volume_map.keys()) if price_volume_map else 0,
#                 },
#                 "num_price_levels": len(price_volume_map),
#                 "periods_analyzed": len(klines),
#             },
#         }

#         return json.dumps(result, ensure_ascii=False, indent=2)

#     except Exception as e:
#         logger.error(f"Error calculating volume profile for {symbol}: {str(e)}")
#         return json.dumps(
#             {
#                 "error": True,
#                 "message": f"Failed to calculate volume profile: {str(e)}",
#                 "symbol": symbol,
#                 "error_type": "calculation_error",
#             }
#         )


@tool
def backtest_trading_signal(
    direction: str,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    symbol: str,
    signal_time: str,  # 新增：信号时间，格式: YYYY-MM-DD HH:MM:SS
    signal_timezone: str,
    backtest_hours: int = 24,
) -> str:
    """
    Backtests trading signal using market data AFTER the signal time.

    This function validates trading signals by testing them against real market data
    that occurred AFTER the signal was generated, ensuring realistic backtest results.

    Args:
        direction (str): Trading direction ("LONG" or "SHORT")
        entry_price (float): Entry price level
        stop_loss (float): Stop loss price level
        target_price (float): Target price level
        symbol (str): Cryptocurrency symbol
        signal_time (str): Signal generation time (YYYY-MM-DD HH:MM:SS)
        signal_timezone (str): Timezone of `signal_time`
        backtest_hours (int): Hours to backtest after signal time (default: 24)

    Returns:
        str: Backtest results showing signal performance using post-signal data
    """
    try:
        logger.info(
            f"Starting backtest for {symbol} signal: {direction} at {entry_price}, "
            f"signal time: {signal_time} {signal_timezone}"
        )

        # Validate signal logic
        validation = _validate_signal_prices(
            direction, entry_price, stop_loss, target_price
        )
        if validation.get("error"):
            return json.dumps(validation, ensure_ascii=False, indent=2)

        # Parse signal time to timestamp
        signal_timestamp = _parse_signal_time_to_timestamp(
            f"{signal_time} {signal_timezone}"
        )
        if not signal_timestamp:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Invalid signal_time format: {signal_time}. Expected: YYYY-MM-DD HH:MM:SS",
                    "symbol": symbol,
                },
                ensure_ascii=False,
                indent=2,
            )

        # Calculate end timestamp for backtest period
        end_timestamp = signal_timestamp + (
            backtest_hours * 3600
        )  # Convert hours to seconds
        current_timestamp = int(time.time())

        # Ensure we don't try to get future data
        if signal_timestamp > current_timestamp:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Signal time is in the future. Cannot backtest future signals.",
                    "signal_time": signal_time,
                    "current_time": datetime.datetime.fromtimestamp(
                        current_timestamp
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                },
                ensure_ascii=False,
                indent=2,
            )

        # Limit end time to current time
        end_timestamp = min(end_timestamp, current_timestamp)
        actual_backtest_hours = (end_timestamp - signal_timestamp) / 3600
        actual_backtest_hours = (
            actual_backtest_hours if actual_backtest_hours >= 1 else 1
        )

        # Get historical data AFTER signal time
        kline_data = _getKlineData(
            symbol=symbol,
            period="minute",  # Use minute data for precise backtest
            limit=min(
                1000, int(actual_backtest_hours * 60)
            ),  # Convert hours to minutes
            from_timestamp=signal_timestamp,  # Start from signal time
            to_timestamp=end_timestamp,  # End at calculated time
            exchange="CCCAGG",
            logger=logger,
        )

        data = json.loads(kline_data)
        if data.get("error"):
            return json.dumps(
                {
                    "error": True,
                    "message": f"Failed to fetch post-signal data for {symbol}: {data.get('message', 'Unknown error')}",
                    "symbol": symbol,
                    "signal_time": signal_time,
                },
                ensure_ascii=False,
                indent=2,
            )

        klines = data.get("data", {}).get(symbol, {}).get("klines", [])
        if len(klines) < 2:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Insufficient post-signal data for {symbol}. Got {len(klines)} data points.",
                    "symbol": symbol,
                    "signal_time": signal_time,
                    "suggestion": "Try increasing backtest_hours or check if signal_time is too recent",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Filter klines to ensure they are all after signal time
        filtered_klines = [k for k in klines if k["timestamp"] >= signal_timestamp]

        if len(filtered_klines) < 2:
            return json.dumps(
                {
                    "error": True,
                    "message": f"No market data available after signal time {signal_time}",
                    "symbol": symbol,
                },
                ensure_ascii=False,
                indent=2,
            )

        # Execute backtest using post-signal data
        signal_info = {
            "direction": direction.upper(),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "signal_time": signal_time,
            "signal_timestamp": signal_timestamp,
        }

        result = _test_signal_prices_post_signal(signal_info, filtered_klines)

        return json.dumps(
            {
                "signal_backtest": {
                    "symbol": symbol,
                    "direction": direction.upper(),
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "signal_time": signal_time,
                    "backtest_period": {
                        "start_time": signal_time,
                        "end_time": datetime.datetime.fromtimestamp(
                            end_timestamp
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "actual_hours": round(actual_backtest_hours, 2),
                        "requested_hours": backtest_hours,
                    },
                    "data_quality": {
                        "total_data_points": len(filtered_klines),
                        "data_coverage_minutes": len(filtered_klines),
                        "all_post_signal": True,
                    },
                    "risk_reward_ratio": abs(target_price - entry_price)
                    / abs(entry_price - stop_loss),
                    "backtest_outcome": result["outcome"],
                    "execution_details": result["execution"],
                    "performance_metrics": result["performance"],
                    "signal_effectiveness": result["effectiveness"],
                    "validation": "✓ Backtest uses only post-signal market data",
                }
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"Signal backtest error: {str(e)}\n{traceback.format_exc()}")
        return json.dumps(
            {
                "error": True,
                "message": f"Backtest failed: {str(e)}",
                "symbol": symbol,
                "signal_time": signal_time if "signal_time" in locals() else "N/A",
            },
            ensure_ascii=False,
            indent=2,
        )


def _parse_signal_time_to_timestamp(signal_time: str) -> int:
    """
    Parse signal time string to Unix timestamp with better timezone handling.

    Args:
        signal_time (str): Time string in various formats:
                          - "YYYY-MM-DD HH:MM:SS UTC"
                          - "YYYY-MM-DD HH:MM:SS Asia/Shanghai"
                          - "YYYY-MM-DD HH:MM:SS" (assumes UTC)

    Returns:
        int: Unix timestamp or None if parsing fails
    """
    try:
        time_str = signal_time.strip()
        logger.info(f"Parsing signal time: '{time_str}'")

        # Try to extract timezone from the string
        parts = time_str.split()
        if len(parts) >= 3:
            # Format: "YYYY-MM-DD HH:MM:SS TIMEZONE"
            time_part = " ".join(parts[:2])  # "YYYY-MM-DD HH:MM:SS"
            tz_part = " ".join(parts[2:])  # "UTC" or "Asia/Shanghai"

            try:
                dt = datetime.datetime.strptime(time_part, "%Y-%m-%d %H:%M:%S")

                # Handle timezone
                if tz_part == "UTC":
                    dt = dt.replace(tzinfo=pytz.UTC)
                elif validate_timezone(tz_part):
                    tz = pytz.timezone(tz_part)
                    dt = tz.localize(dt)
                else:
                    logger.warning(f"Unknown timezone '{tz_part}', assuming UTC")
                    dt = dt.replace(tzinfo=pytz.UTC)

                timestamp = int(dt.timestamp())
                logger.info(
                    f"Parsed '{time_str}' to timestamp {timestamp} (UTC: {datetime.datetime.fromtimestamp(timestamp, pytz.UTC)})"
                )
                return timestamp

            except ValueError:
                pass

        # Fallback to original formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S UTC",
            "%Y-%m-%d %H:%M:%S %Z",
        ]

        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(time_str, fmt)
                # Only assume UTC if no timezone was specified in any format
                if dt.tzinfo is None:
                    logger.warning(
                        f"No timezone specified in '{time_str}', assuming UTC"
                    )
                    dt = dt.replace(tzinfo=pytz.UTC)
                return int(dt.timestamp())
            except ValueError:
                continue

        # Final attempt with ISO format
        dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return int(dt.timestamp())

    except Exception as e:
        logger.error(f"Failed to parse signal time '{signal_time}': {e}")
        return None


def _test_signal_prices_post_signal(signal_info: dict, klines: list) -> dict:
    """
    Test signal prices against post-signal market data only.

    Args:
        signal_info (dict): Signal information including prices and timestamps
        klines (list): Market data klines AFTER signal time

    Returns:
        dict: Backtest results with execution details
    """
    try:
        direction = signal_info["direction"]
        entry_price = signal_info["entry_price"]
        stop_loss = signal_info["stop_loss"]
        target_price = signal_info["target_price"]
        signal_timestamp = signal_info["signal_timestamp"]

        # Track execution
        entry_hit = False
        entry_time = None
        entry_kline_index = None
        outcome = "no_entry"
        exit_price = None
        exit_time = None
        max_favorable = entry_price
        max_adverse = entry_price

        logger.info(f"Testing signal against {len(klines)} post-signal data points")

        # Process each kline in chronological order (all are post-signal)
        for i, kline in enumerate(klines):
            high = kline["high"]
            low = kline["low"]
            close = kline["close"]
            timestamp = kline["timestamp"]

            # Ensure this kline is actually after signal time
            if timestamp < signal_timestamp:
                continue

            if not entry_hit:
                # Check if price touched entry level
                if low <= entry_price <= high:
                    entry_hit = True
                    entry_time = timestamp
                    entry_kline_index = i
                    logger.info(
                        f"Entry hit at {datetime.datetime.fromtimestamp(timestamp)} - price range: {low}-{high}"
                    )
                    continue
            else:
                # After entry, check for exit conditions
                if direction == "LONG":
                    max_favorable = max(max_favorable, high)
                    max_adverse = min(max_adverse, low)

                    # Check stop loss first (priority)
                    if low <= stop_loss:
                        outcome = "stop_loss"
                        exit_price = stop_loss
                        exit_time = timestamp
                        logger.info(
                            f"Stop loss hit at {datetime.datetime.fromtimestamp(timestamp)} - low: {low}"
                        )
                        break
                    # Check target
                    elif high >= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_time = timestamp
                        logger.info(
                            f"Target hit at {datetime.datetime.fromtimestamp(timestamp)} - high: {high}"
                        )
                        break

                else:  # SHORT
                    max_favorable = min(max_favorable, low)
                    max_adverse = max(max_adverse, high)

                    # Check stop loss first (priority)
                    if high >= stop_loss:
                        outcome = "stop_loss"
                        exit_price = stop_loss
                        exit_time = timestamp
                        logger.info(
                            f"Stop loss hit at {datetime.datetime.fromtimestamp(timestamp)} - high: {high}"
                        )
                        break
                    # Check target
                    elif low <= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_time = timestamp
                        logger.info(
                            f"Target hit at {datetime.datetime.fromtimestamp(timestamp)} - low: {low}"
                        )
                        break

        # If still in position after all data, use last available price
        if entry_hit and outcome not in ["stop_loss", "target_hit"]:
            outcome = "still_open"
            exit_price = klines[-1]["close"]
            exit_time = klines[-1]["timestamp"]
            logger.info(
                f"Position still open at end of backtest period - last price: {exit_price}"
            )

        # Calculate performance metrics
        if entry_hit:
            if direction == "LONG":
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                max_gain_pct = ((max_favorable - entry_price) / entry_price) * 100
                max_loss_pct = ((max_adverse - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                max_gain_pct = ((entry_price - max_favorable) / entry_price) * 100
                max_loss_pct = ((entry_price - max_adverse) / entry_price) * 100

            performance = {
                "pnl_percentage": round(pnl_pct, 2),
                "max_favorable_move": round(max_gain_pct, 2),
                "max_adverse_move": round(max_loss_pct, 2),
                "entry_executed": True,
                "exit_reason": outcome,
                "bars_to_entry": (
                    entry_kline_index if entry_kline_index is not None else 0
                ),
                "bars_in_position": (
                    len(klines) - entry_kline_index - 1
                    if entry_kline_index is not None
                    else 0
                ),
            }
        else:
            performance = {
                "pnl_percentage": 0,
                "max_favorable_move": 0,
                "max_adverse_move": 0,
                "entry_executed": False,
                "exit_reason": "entry_price_not_reached_post_signal",
                "bars_to_entry": len(klines),  # All bars processed, no entry
                "bars_in_position": 0,
            }

        # Execution details with post-signal validation
        execution = {
            "entry_hit": entry_hit,
            "entry_time": (
                datetime.datetime.fromtimestamp(entry_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if entry_time
                else None
            ),
            "exit_time": (
                datetime.datetime.fromtimestamp(exit_time).strftime("%Y-%m-%d %H:%M:%S")
                if exit_time
                else None
            ),
            "actual_exit_price": exit_price,
            "time_in_position_minutes": (
                int((exit_time - entry_time) / 60) if entry_time and exit_time else 0
            ),
            "post_signal_validation": {
                "signal_timestamp": signal_timestamp,
                "first_data_timestamp": klines[0]["timestamp"] if klines else None,
                "all_data_post_signal": all(
                    k["timestamp"] >= signal_timestamp for k in klines
                ),
                "data_gap_minutes": (
                    int((klines[0]["timestamp"] - signal_timestamp) / 60)
                    if klines
                    else 0
                ),
            },
        }

        # Signal effectiveness assessment with post-signal context
        if not entry_hit:
            effectiveness = "entry_too_aggressive_post_signal"
            conclusion = f"Entry price {entry_price} was not reached in {len(klines)} minutes after signal time - signal may be too optimistic"
        elif outcome == "target_hit":
            effectiveness = "highly_effective_post_signal"
            conclusion = f"Signal successful - reached target with {pnl_pct:.1f}% profit in {int((exit_time - entry_time) / 60)} minutes"
        elif outcome == "stop_loss":
            effectiveness = "stopped_out_post_signal"
            conclusion = f"Signal hit stop loss with {pnl_pct:.1f}% loss in {int((exit_time - entry_time) / 60)} minutes"
        else:  # still_open
            if pnl_pct > 0:
                effectiveness = "profitable_open_post_signal"
                conclusion = (
                    f"Signal currently profitable at {pnl_pct:.1f}% (unrealized)"
                )
            else:
                effectiveness = "losing_open_post_signal"
                conclusion = f"Signal currently losing at {pnl_pct:.1f}% (unrealized)"

        return {
            "outcome": outcome,
            "execution": execution,
            "performance": performance,
            "effectiveness": effectiveness,
            "conclusion": conclusion,
            "post_signal_validation": "✓ Backtest used only post-signal market data",
        }

    except Exception as e:
        logger.error(
            f"Error in post-signal backtest: {str(e)}\n{traceback.format_exc()}"
        )
        return {
            "outcome": "error",
            "execution": {},
            "performance": {"pnl_percentage": 0},
            "effectiveness": "test_failed",
            "conclusion": f"Post-signal backtest failed: {str(e)}",
            "post_signal_validation": "✗ Backtest failed",
        }


def _validate_signal_prices(
    direction: str, entry: float, stop: float, target: float
) -> dict:
    """Validate signal price logic"""
    try:
        direction = direction.upper()

        if direction == "LONG":
            if not (stop < entry < target):
                return {
                    "error": True,
                    "message": "Invalid LONG signal: Stop loss must be below entry, target above entry",
                }
        elif direction == "SHORT":
            if not (target < entry < stop):
                return {
                    "error": True,
                    "message": "Invalid SHORT signal: Target must be below entry, stop loss above entry",
                }
        else:
            return {"error": True, "message": "Direction must be 'LONG' or 'SHORT'"}

        return {"valid": True}

    except Exception as e:
        return {"error": True, "message": f"Price validation failed: {str(e)}"}


import datetime
import pytz
from loggers import logger

# 支持的时区白名单（可根据需要扩展）
SUPPORTED_TIMEZONES = set(pytz.all_timezones)


def validate_timezone(time_zone: str) -> bool:
    """验证时区参数是否有效"""
    if not time_zone or not isinstance(time_zone, str):
        return False
    return time_zone in SUPPORTED_TIMEZONES


@tool
def now(time_zone: str) -> str:
    """
    获取带时区感知的当前时间

    Args:
        time_zone (Optional[str]): 时区标识符，如 'Asia/Shanghai', 'America/New_York'
                                  如果为None，则返回UTC时间

    Returns:
        str: ISO格式的时间字符串 (YYYY-MM-DD HH:MM:SS.mmmmmm)

    Examples:
        >>> now_with_timezone('Asia/Shanghai')
        '2024-01-15 14:30:45.123456'
        >>> now_with_timezone()  # 默认UTC
        '2024-01-15 06:30:45.123456'
    """
    try:
        if time_zone and validate_timezone(time_zone):
            # 使用指定时区
            tz = pytz.timezone(time_zone)
            current_time = datetime.datetime.now(tz)
            logger.debug(f"Generated time for timezone {time_zone}: {current_time}")
        else:
            # 默认使用UTC时区
            current_time = datetime.datetime.now(pytz.UTC)
            if time_zone:  # 如果提供了无效时区，记录警告
                logger.warning(
                    f"Invalid timezone '{time_zone}' provided, falling back to UTC"
                )

        return current_time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        logger.error(f"Error generating timezone-aware time: {e}")
        # 发生错误时回退到UTC时间
        return datetime.datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")


@tool
def convert_to_utc_time(local_time: str, source_timezone: str = "UTC") -> str:
    """
    Convert local time to UTC time with explicit timezone handling.

    This function provides explicit timezone conversion, ensuring users can
    convert their local time to UTC before using it in trading signals or backtests.

    Args:
        local_time (str): Local time string in format "YYYY-MM-DD HH:MM:SS"
        source_timezone (str): Source timezone (e.g., "Asia/Shanghai", "America/New_York", "Europe/London")
                              Default: "UTC" (no conversion needed)

    Returns:
        str: UTC time string in format "YYYY-MM-DD HH:MM:SS UTC"

    Examples:
        convert_to_utc_time("2024-01-15 14:30:00", "Asia/Shanghai")
        # Returns: "2024-01-15 06:30:00 UTC" (Shanghai is UTC+8)

        convert_to_utc_time("2024-01-15 09:30:00", "America/New_York")
        # Returns: "2024-01-15 14:30:00 UTC" (EST is UTC-5, EDT is UTC-4)

        convert_to_utc_time("2024-01-15 14:30:00")  # Already UTC
        # Returns: "2024-01-15 14:30:00 UTC"

    Note:
        - This function handles daylight saving time automatically
        - Use this before calling backtest_trading_signal to ensure correct UTC timing
        - Supported timezones include all pytz timezone identifiers
    """
    try:
        logger.info(f"Converting time '{local_time}' from {source_timezone} to UTC")

        # Validate timezone
        if not validate_timezone(source_timezone):
            return json.dumps(
                {
                    "error": True,
                    "message": f"Invalid timezone: {source_timezone}",
                    "supported_timezones_sample": [
                        "UTC",
                        "Asia/Shanghai",
                        "America/New_York",
                        "Europe/London",
                        "Asia/Tokyo",
                        "America/Los_Angeles",
                        "Europe/Paris",
                    ],
                    "note": "Use pytz.all_timezones for complete list",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Parse the local time
        try:
            dt = datetime.datetime.strptime(local_time.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            return json.dumps(
                {
                    "error": True,
                    "message": f"Invalid time format: {local_time}. Expected: YYYY-MM-DD HH:MM:SS",
                    "example": "2024-01-15 14:30:00",
                },
                ensure_ascii=False,
                indent=2,
            )

        # Apply source timezone
        source_tz = pytz.timezone(source_timezone)
        localized_dt = source_tz.localize(dt)

        # Convert to UTC
        utc_dt = localized_dt.astimezone(pytz.UTC)
        utc_time_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        result = {
            "original_time": local_time,
            "source_timezone": source_timezone,
            "utc_time": utc_time_str,
            "utc_timestamp": int(utc_dt.timestamp()),
            "conversion_info": {
                "timezone_offset": str(localized_dt.utcoffset()),
                "dst_active": localized_dt.dst() != datetime.timedelta(0),
                "timezone_abbreviation": localized_dt.strftime("%Z"),
            },
            "usage_note": "Use the 'utc_time' value (without 'UTC' suffix) for backtest_trading_signal",
        }

        logger.info(
            f"Successfully converted {local_time} {source_timezone} to {utc_time_str}"
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except pytz.exceptions.AmbiguousTimeError as e:
        # Handle daylight saving time ambiguity
        return json.dumps(
            {
                "error": True,
                "message": f"Ambiguous time during daylight saving transition: {local_time}",
                "suggestion": "Specify whether the time is before or after DST transition",
                "timezone": source_timezone,
                "details": str(e),
            },
            ensure_ascii=False,
            indent=2,
        )

    except pytz.exceptions.NonExistentTimeError as e:
        # Handle non-existent time during DST transition
        return json.dumps(
            {
                "error": True,
                "message": f"Non-existent time during daylight saving transition: {local_time}",
                "suggestion": "This time was skipped during DST transition",
                "timezone": source_timezone,
                "details": str(e),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error converting time to UTC: {str(e)}")
        return json.dumps(
            {
                "error": True,
                "message": f"Time conversion failed: {str(e)}",
                "original_time": local_time,
                "source_timezone": source_timezone,
            },
            ensure_ascii=False,
            indent=2,
        )


@tool
def get_utc_time():
    """
    Useful when you need to get the current UTC time of the system.
    Returns the current UTC time in ISO format (YYYY-MM-DD HH:MM:SS.mmmmmm).
    """
    import pytz

    return datetime.datetime.now(tz=pytz.UTC).isoformat(" ")


# 更新工具列表
tools = [
    # getLatestQuote,
    # get_trade_pair_and_exchanges,
    # get_indicators,
    # get_historical_klines,
    # get_order_book,
    # get_recent_trades,
    # get_realtime_order_book,
    # get_realtime_trades,
    # get_volume_profile,
    backtest_trading_signal,
    # now,
    # convert_to_utc_time,
    # get_utc_time,
]
