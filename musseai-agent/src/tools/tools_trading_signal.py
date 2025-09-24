from collections import defaultdict
import datetime
import time
import traceback
from typing import Dict, List
from langchain.agents import tool
import json
from tradingview_ta import TA_Handler
from loggers import logger
from utils.api.cryptocompare import getLatestQuoteRealTime
from tradingview_screener import Query, Column
from utils.api.cryptocompare import getKlineData as _getKlineData
import datetime
import pytz
from loggers import logger


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


@tool
def get_volume_profile(
    symbol: str, period: str = "daily", limit: int = 30, exchange: str = "CCCAGG"
) -> str:
    """
    Calculates volume profile data by analyzing trading volume at different price levels.

    This function processes historical kline data to generate volume profile information,
    which helps identify key support/resistance levels and high-volume trading zones.

    Args:
        symbol (str): Cryptocurrency symbol
        period (str): Time period for analysis ("daily", "1h", "1m")
        limit (int): Number of periods to analyze (default: 30)
        exchange (str): Exchange name

    Returns:
        str: JSON string containing volume profile with:
             - price_levels: volume distribution by price ranges
             - poc: Point of Control (highest volume price level)
             - value_area: high/low boundaries containing 70% of volume
             - volume_nodes: significant volume clusters

    Example usage:
        get_volume_profile("BTC") - Get 30-day Bitcoin volume profile
        get_volume_profile("ETH", "1h", 24) - Get 24-hour Ethereum profile
    """
    try:
        # Get historical data first
        kline_data = _getKlineData(
            symbol=symbol, period=period, limit=limit, exchange=exchange, logger=logger
        )

        import json

        data = json.loads(kline_data)

        if data.get("error"):
            return kline_data  # Return error as-is

        klines = data.get("data", {}).get(symbol, {}).get("klines", [])
        if not klines:
            return json.dumps(
                {
                    "error": True,
                    "message": f"No kline data available for volume profile calculation",
                    "symbol": symbol,
                }
            )

        # Calculate volume profile
        price_volume_map = {}
        total_volume = 0

        for kline in klines:
            high = kline["high"]
            low = kline["low"]
            volume = kline["volume"]
            close = kline["close"]

            # Distribute volume across price levels (simplified approach)
            price_range = high - low if high > low else 0.01
            num_levels = max(
                10, int(price_range / (close * 0.001))
            )  # Dynamic levels based on price

            for i in range(num_levels):
                price_level = low + (price_range * i / num_levels)
                price_key = round(price_level, 2)

                if price_key not in price_volume_map:
                    price_volume_map[price_key] = 0

                price_volume_map[price_key] += volume / num_levels
                total_volume += volume / num_levels

        # Sort by volume descending
        sorted_levels = sorted(
            price_volume_map.items(), key=lambda x: x[1], reverse=True
        )

        # Find Point of Control (POC)
        poc_price = sorted_levels[0][0] if sorted_levels else 0
        poc_volume = sorted_levels[0][1] if sorted_levels else 0

        # Calculate Value Area (70% of total volume)
        value_area_volume = total_volume * 0.7
        cumulative_volume = 0
        value_area_prices = []

        for price, volume in sorted_levels:
            if cumulative_volume < value_area_volume:
                value_area_prices.append(price)
                cumulative_volume += volume
            else:
                break

        value_area_high = max(value_area_prices) if value_area_prices else 0
        value_area_low = min(value_area_prices) if value_area_prices else 0

        # Identify significant volume nodes (top 20% by volume)
        significant_nodes = sorted_levels[: max(1, len(sorted_levels) // 5)]

        result = {
            "source": "CryptoCompare_VolumeProfile",
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "analysis_period": f"{limit} {period} periods",
            "timestamp": int(time.time()),
            "price_levels": [
                {
                    "price": price,
                    "volume": round(volume, 4),
                    "volume_percentage": round((volume / total_volume) * 100, 2),
                }
                for price, volume in sorted_levels[:50]  # Top 50 levels
            ],
            "point_of_control": {
                "price": poc_price,
                "volume": round(poc_volume, 4),
                "volume_percentage": round((poc_volume / total_volume) * 100, 2),
            },
            "value_area": {
                "high": value_area_high,
                "low": value_area_low,
                "range": round(value_area_high - value_area_low, 2),
                "volume_percentage": 70.0,
            },
            "volume_nodes": [
                {
                    "price": price,
                    "volume": round(volume, 4),
                    "significance": "high" if volume > poc_volume * 0.8 else "medium",
                }
                for price, volume in significant_nodes
            ],
            "summary": {
                "total_volume": round(total_volume, 4),
                "price_range": {
                    "high": max(price_volume_map.keys()) if price_volume_map else 0,
                    "low": min(price_volume_map.keys()) if price_volume_map else 0,
                },
                "num_price_levels": len(price_volume_map),
                "periods_analyzed": len(klines),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Error calculating volume profile for {symbol}: {str(e)}")
        return json.dumps(
            {
                "error": True,
                "message": f"Failed to calculate volume profile: {str(e)}",
                "symbol": symbol,
                "error_type": "calculation_error",
            }
        )


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
    getLatestQuote,
    get_trade_pair_and_exchanges,
    get_indicators,
    get_volume_profile,
    now,
    convert_to_utc_time,
    get_utc_time,
]
