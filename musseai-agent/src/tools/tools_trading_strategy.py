from collections import defaultdict
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

from utils.api.cryptocompare import getLatestQuoteRealTime,getRealtimeOrderBookDepth 
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


@tool
def get_order_book(
    symbols: str,
    exchange: str,
    depth: int = 20,
) -> str:
    """
    Retrieves real-time order book depth data for market liquidity analysis.

    This function fetches bid and ask prices with their volumes, providing
    crucial information about market depth, liquidity, and potential support/resistance levels.

    Args:
        symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC"
        depth (int): Number of price levels for both bids and asks (1-50, default: 20)
        exchange (str): The exchange name where the trading pair is listed, return from `get_symbols_and_exchanges`.

    Returns:
        str: JSON string containing order book data with:
             - bids: buy orders sorted by price (highest first)
             - asks: sell orders sorted by price (lowest first)
             - summary: best bid/ask, spread, total volumes
             - market_depth_analysis: liquidity score, imbalance metrics
             - price_impact analysis for different volume levels

    Example usage:
        get_order_book("BTC") - Get 20-level Bitcoin order book
        get_order_book("ETH", 10) - Get 10-level Ethereum order book
        get_order_book("BTC", 50, "Binance") - Get 50-level from Binance
    """
    logger.info("get_order_book starting.")
    return get_realtime_order_book(
        symbols=symbols, depth=depth, exchange=exchange, logger=logger
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
def get_realtime_order_book(
    symbols: str,  exchange: str ,depth: int = 10
) -> str:
    """
    Retrieves ultra real-time order book data with minimal caching for high-frequency trading.

    Optimized version with shorter cache duration and faster rate limits for applications
    requiring the freshest order book data.

    Args:
        symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH" or single "BTC". , the same as `get_order_book`'s parameter
        depth (int): Number of price levels (1-25, default: 10 for speed)
        exchange (str): The exchange name, the same as `get_order_book`'s parameter.

    Returns:
        str: JSON string with real-time order book data

    Example usage:
        get_realtime_order_book("BTC") - Get real-time Bitcoin order book
        get_realtime_order_book("ETH", 5) - Get 5-level Ethereum order book
    """
    logger.info("get_realtime_order_book starting")
    return getRealtimeOrderBookDepth(
        symbols=symbols, depth=depth, exchange=exchange, logger=logger
    )


@tool
def get_realtime_trades(symbol: str, limit: int = 50, exchange: str = "CCCAGG") -> str:
    """
    Retrieves ultra real-time trade records with minimal caching for high-frequency applications.

    Optimized version with shorter cache duration and faster rate limits for applications
    requiring the freshest trade data.

    Args:
        symbol (str): Cryptocurrency symbol
        limit (int): Number of recent trades (1-100, default: 50 for speed)
        exchange (str): Exchange name

    Returns:
        str: JSON string with real-time trade data

    Example usage:
        get_realtime_trades("BTC") - Get real-time Bitcoin trades
        get_realtime_trades("ETH", 25) - Get 25 recent Ethereum trades
    """
    return _getRealtimeTrades(
        symbol=symbol, limit=limit, exchange=exchange, logger=logger
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

@tool
def backtest_trading_signal(
    direction: str,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    symbol: str,
    backtest_hours: int = 24
) -> str:
    """
    Backtests trading signal prices (entry, stop loss, target) for effectiveness.
    
    Validates trading signal by testing entry, stop loss, and target prices
    against recent historical data to assess signal quality.
    
    Args:
        direction (str): Trading direction ("LONG" or "SHORT")
        entry_price (float): Entry price level
        stop_loss (float): Stop loss price level
        target_price (float): Target price level
        symbol (str): Cryptocurrency symbol
        backtest_hours (int): Hours of historical data to test (default: 24)
        
    Returns:
        str: Backtest results showing signal performance and outcome
    """
    try:
        logger.info(f"Starting backtest for {symbol} signal: {direction} at {entry_price}")
        
        # Validate signal logic
        validation = _validate_signal_prices(direction, entry_price, stop_loss, target_price)
        if validation.get("error"):
            return json.dumps(validation, ensure_ascii=False, indent=2)
        
        # Get historical data
        limit = min(100, backtest_hours * 4)  # 15-minute intervals
        
        kline_data = _getKlineData(
            symbol=symbol,
            period="minute",
            limit=limit,
            exchange="CCCAGG",
            logger=logger
        )
        
        data = json.loads(kline_data)
        if data.get("error"):
            return json.dumps({
                "error": True,
                "message": f"Failed to fetch historical data for {symbol}",
                "symbol": symbol
            }, ensure_ascii=False, indent=2)
        
        klines = data.get("data", {}).get(symbol, {}).get("klines", [])
        if len(klines) < 5:
            return json.dumps({
                "error": True,
                "message": f"Insufficient historical data for {symbol}",
                "symbol": symbol
            }, ensure_ascii=False, indent=2)
        
        # Execute backtest
        signal_info = {
            "direction": direction.upper(),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price
        }
        
        result = _test_signal_prices(signal_info, klines)
        
        return json.dumps({
            "signal_backtest": {
                "symbol": symbol,
                "direction": direction.upper(),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target_price": target_price,
                "risk_reward_ratio": abs(target_price - entry_price) / abs(entry_price - stop_loss),
                "backtest_period_hours": backtest_hours,
                "data_points": len(klines),
                "backtest_outcome": result["outcome"],
                "execution_details": result["execution"],
                "performance_metrics": result["performance"],
                "signal_effectiveness": result["effectiveness"]
            }
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Signal backtest error: {str(e)}")
        return json.dumps({
            "error": True,
            "message": f"Backtest failed: {str(e)}"
        }, ensure_ascii=False, indent=2)


def _validate_signal_prices(direction: str, entry: float, stop: float, target: float) -> dict:
    """Validate signal price logic"""
    try:
        direction = direction.upper()
        
        if direction == "LONG":
            if not (stop < entry < target):
                return {
                    "error": True,
                    "message": "Invalid LONG signal: Stop loss must be below entry, target above entry"
                }
        elif direction == "SHORT":
            if not (target < entry < stop):
                return {
                    "error": True,
                    "message": "Invalid SHORT signal: Target must be below entry, stop loss above entry"
                }
        else:
            return {
                "error": True,
                "message": "Direction must be 'LONG' or 'SHORT'"
            }
        
        return {"valid": True}
        
    except Exception as e:
        return {
            "error": True,
            "message": f"Price validation failed: {str(e)}"
        }


def _test_signal_prices(signal_info: dict, klines: list) -> dict:
    """Test signal prices against historical data"""
    try:
        direction = signal_info["direction"]
        entry_price = signal_info["entry_price"]
        stop_loss = signal_info["stop_loss"]
        target_price = signal_info["target_price"]
        
        # Track execution
        entry_hit = False
        entry_time = None
        outcome = "no_entry"
        exit_price = None
        exit_time = None
        max_favorable = entry_price
        max_adverse = entry_price
        
        # Find entry point
        for i, kline in enumerate(klines):
            high = kline["high"]
            low = kline["low"]
            
            if not entry_hit:
                # Check if price touched entry level
                if low <= entry_price <= high:
                    entry_hit = True
                    entry_time = kline["timestamp"]
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
                        exit_time = kline["timestamp"]
                        break
                    # Check target
                    elif high >= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_time = kline["timestamp"]
                        break
                        
                else:  # SHORT
                    max_favorable = min(max_favorable, low)
                    max_adverse = max(max_adverse, high)
                    
                    # Check stop loss first (priority)
                    if high >= stop_loss:
                        outcome = "stop_loss"
                        exit_price = stop_loss
                        exit_time = kline["timestamp"]
                        break
                    # Check target
                    elif low <= target_price:
                        outcome = "target_hit"
                        exit_price = target_price
                        exit_time = kline["timestamp"]
                        break
        
        # If still in position, use last price
        if entry_hit and outcome not in ["stop_loss", "target_hit"]:
            outcome = "still_open"
            exit_price = klines[-1]["close"]
            exit_time = klines[-1]["timestamp"]
        
        # Calculate performance
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
                "exit_reason": outcome
            }
        else:
            performance = {
                "pnl_percentage": 0,
                "max_favorable_move": 0,
                "max_adverse_move": 0,
                "entry_executed": False,
                "exit_reason": "entry_price_not_reached"
            }
        
        # Execution details
        execution = {
            "entry_hit": entry_hit,
            "entry_time": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S") if entry_time else None,
            "exit_time": datetime.fromtimestamp(exit_time).strftime("%Y-%m-%d %H:%M:%S") if exit_time else None,
            "actual_exit_price": exit_price,
            "time_in_position_minutes": int((exit_time - entry_time) / 60) if entry_time and exit_time else 0
        }
        
        # Signal effectiveness assessment
        if not entry_hit:
            effectiveness = "entry_too_aggressive"
            conclusion = "Entry price was not reached - signal may be too optimistic"
        elif outcome == "target_hit":
            effectiveness = "highly_effective"
            conclusion = f"Signal successful - reached target with {pnl_pct:.1f}% profit"
        elif outcome == "stop_loss":
            effectiveness = "stopped_out"
            conclusion = f"Signal hit stop loss with {pnl_pct:.1f}% loss"
        else:  # still_open
            if pnl_pct > 0:
                effectiveness = "profitable_open"
                conclusion = f"Signal currently profitable at {pnl_pct:.1f}%"
            else:
                effectiveness = "losing_open"
                conclusion = f"Signal currently losing at {pnl_pct:.1f}%"
        
        return {
            "outcome": outcome,
            "execution": execution,
            "performance": performance,
            "effectiveness": effectiveness,
            "conclusion": conclusion
        }
        
    except Exception as e:
        logger.error(f"Error testing signal prices: {str(e)}")
        return {
            "outcome": "error",
            "execution": {},
            "performance": {"pnl_percentage": 0},
            "effectiveness": "test_failed",
            "conclusion": f"Backtest failed: {str(e)}"
        }


# 更新工具列表
tools = [
    getLatestQuote,
    get_trade_pair_and_exchanges,
    get_indicators,
    get_historical_klines,
    get_order_book,
    get_recent_trades,
    get_realtime_order_book,
    get_realtime_trades,
    get_volume_profile,
    backtest_trading_signal,
]

# Import the additional strategy generation tools
from tools.tools_strategy_generator import additional_tools

# Update the tools list to include all strategy generation tools
tools.extend(additional_tools)
