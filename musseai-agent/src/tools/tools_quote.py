from collections import defaultdict
import time
import traceback
from typing import Dict, List
from langchain.agents import tool
from tradingview_ta import TA_Handler
from loggers import logger

from utils.api.cryptocompare import getLatestQuote as _getLatestQuote 
from tradingview_screener import Query, Column
from langchain.agents import tool
from utils.api.cryptocompare import getKlineDataWithCache
from utils.api.cryptocompare import getRecentTrades



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
    return _getLatestQuote(symbols=symbols)


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
    return getKlineDataWithCache(
        symbol=symbol,
        period=period,
        limit=limit,
        to_timestamp=to_timestamp,
        from_timestamp=from_timestamp,
        exchange=exchange,
        logger=logger,
    )

@tool
def get_recent_trades(
    symbol: str, limit: int = 100, exchange: str = "CCCAGG", to_timestamp: int = None
) -> str:
    """
    Retrieves recent completed trade records for market activity analysis.

    This function fetches the most recent executed trades, providing insights into
    market activity, trading patterns, and price movements.

    Args:
        symbol (str): Cryptocurrency symbol (e.g., "BTC", "ETH")
        limit (int): Number of recent trades to retrieve (1-2000, default: 100)
        exchange (str): Exchange name (default: "CCCAGG" for aggregated data)
        to_timestamp (int): End timestamp (Unix). If None, uses current time

    Returns:
        str: JSON string containing recent trades with:
             - trade records: timestamp, price, quantity, side (buy/sell)
             - summary statistics: total volume, average price, high/low
             - market_activity_analysis: trade frequency, volume distribution
             - price_trend and market_pressure indicators

    Example usage:
        get_recent_trades("BTC") - Get last 100 Bitcoin trades
        get_recent_trades("ETH", 50) - Get last 50 Ethereum trades
        get_recent_trades("BTC", 200, "Binance") - Get 200 trades from Binance
    """
    return getRecentTrades(
        symbol=symbol,
        limit=limit,
        exchange=exchange,
        to_timestamp=to_timestamp,
        logger=logger,
    )

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
        kline_data = getKlineDataWithCache(
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


tools = [
    getLatestQuote,
    get_trade_pair_and_exchanges,
    get_indicators,
    get_historical_klines,
    # get_recent_trades,
    get_volume_profile,
]
