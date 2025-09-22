import datetime
import time
import traceback
from langchain.agents import tool
import json
from loggers import logger
from utils.api.cryptocompare import getKlineData 

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
        kline_data = getKlineData(
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

# 更新工具列表
tools = [
    backtest_trading_signal,
]
