"""
Enhanced Portfolio Performance Analysis with Real Data Integration
Uses third-party APIs to fetch real market data and provides comprehensive analysis
"""

from decimal import Decimal
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import requests
import json
from langchain.agents import tool
from mysql.db import get_db
from mysql.model import (
    PortfolioSourceModel,
    PositionModel,
    TransactionModel,
    TransactionType,
)
from loggers import logger
from utils.api_decorators import api_call_with_cache_and_rate_limit, cache_result
import traceback

# ========================================
# Configuration and Constants
# ========================================

# API Endpoints and Keys
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
YAHOO_FINANCE_API_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
TWELVE_DATA_API_BASE = "https://api.twelvedata.com"

# Benchmark mapping for different asset types
BENCHMARK_MAPPING = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "GOLD": "GC=F",
    "USD": "DX-Y.NYB",
}

# Risk-free rate sources (using 10-year Treasury as proxy)
RISK_FREE_RATE_SYMBOL = "^TNX"

# ========================================
# Data Fetching Functions
# ========================================


@api_call_with_cache_and_rate_limit(cache_duration=600, rate_limit_interval=1.5)
def fetch_coingecko_price_data(
    coin_id: str, vs_currency: str = "usd", days: int = 365
) -> Dict:
    """
    Fetch historical price data from CoinGecko API

    Args:
        coin_id: CoinGecko coin identifier
        vs_currency: Base currency for prices
        days: Number of days of historical data

    Returns:
        Dict containing price history data
    """
    try:
        url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": vs_currency,
            "days": days,
            "interval": "daily" if days > 90 else "hourly",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Convert to more usable format
        prices = []
        for timestamp, price in data.get("prices", []):
            prices.append(
                {
                    "timestamp": timestamp,
                    "date": datetime.fromtimestamp(timestamp / 1000),
                    "price": price,
                }
            )

        return {
            "success": True,
            "coin_id": coin_id,
            "prices": prices,
            "market_caps": data.get("market_caps", []),
            "total_volumes": data.get("total_volumes", []),
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"CoinGecko API request failed for {coin_id}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error fetching CoinGecko data: {e}")
        return {"success": False, "error": str(e)}


@api_call_with_cache_and_rate_limit(cache_duration=900, rate_limit_interval=2.0)
def fetch_yahoo_finance_data(symbol: str, period: str = "1y") -> Dict:
    """
    Fetch stock/index data from Yahoo Finance

    Args:
        symbol: Yahoo Finance symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dict containing price history
    """
    try:
        url = f"{YAHOO_FINANCE_API_BASE}/{symbol}"
        params = {
            "period1": int((datetime.now() - timedelta(days=365)).timestamp()),
            "period2": int(datetime.now().timestamp()),
            "interval": "1d",
            "includePrePost": "false",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
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
                            indicators["volume"][i] if indicators["volume"][i] else 0
                        ),
                    }
                )

        return {"success": True, "symbol": symbol, "prices": prices}

    except requests.exceptions.RequestException as e:
        logger.error(f"Yahoo Finance API request failed for {symbol}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error fetching Yahoo Finance data: {e}")
        return {"success": False, "error": str(e)}


@cache_result(duration=3600)
def get_risk_free_rate() -> float:
    """
    Get current risk-free rate from 10-year Treasury yield

    Returns:
        Risk-free rate as decimal (e.g., 0.045 for 4.5%)
    """
    try:
        data = fetch_yahoo_finance_data(RISK_FREE_RATE_SYMBOL, "5d")
        if data["success"] and data["prices"]:
            latest_yield = data["prices"][-1]["price"]
            return latest_yield / 100  # Convert percentage to decimal
        return 0.045  # Default fallback
    except Exception as e:
        logger.error(f"Failed to fetch risk-free rate: {e}")
        return 0.045


def get_benchmark_price_data(benchmark: str, days: int = 365) -> Dict:
    """
    Get price data for benchmark asset

    Args:
        benchmark: Benchmark symbol
        days: Number of days of data

    Returns:
        Price data dictionary
    """
    if benchmark in ["BTC", "ETH"]:
        coin_id = BENCHMARK_MAPPING.get(benchmark)
        if coin_id:
            return fetch_coingecko_price_data(coin_id, days=days)
    else:
        symbol = BENCHMARK_MAPPING.get(benchmark, benchmark)
        return fetch_yahoo_finance_data(symbol)

    return {"success": False, "error": f"Unknown benchmark: {benchmark}"}


# ========================================
# Portfolio Value Calculation Functions
# ========================================


def calculate_portfolio_value_at_date(user_id: str, target_date: datetime) -> float:
    """
    Calculate portfolio value at a specific date using historical prices

    Args:
        user_id: User identifier
        target_date: Date to calculate value for

    Returns:
        Portfolio value in USD
    """
    try:
        with get_db() as db:
            # Get positions at the target date
            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.user_id == user_id,
                    PositionModel.created_at <= target_date,
                    PositionModel.quantity > 0,
                )
                .all()
            )

            if not positions:
                return 0.0

            total_value = 0.0

            for position in positions:
                # Get historical price for this asset at target date
                asset_price = get_asset_price_at_date(
                    position.asset_symbol, target_date
                )
                if asset_price > 0:
                    total_value += float(position.quantity) * asset_price

            return total_value

    except Exception as e:
        logger.error(f"Error calculating portfolio value at date: {e}")
        return 0.0


def get_asset_price_at_date(symbol: str, target_date: datetime) -> float:
    """
    Get asset price at specific date

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
            coin_id = BENCHMARK_MAPPING.get(symbol.upper(), symbol.lower())
            data = fetch_coingecko_price_data(coin_id, days=30)
        else:
            data = fetch_yahoo_finance_data(symbol, period="1mo")

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
        logger.error(f"Error getting asset price for {symbol} at {target_date}: {e}")
        return 0.0


def get_net_deposits_in_period(
    user_id: str, start_date: datetime, end_date: datetime
) -> float:
    """
    Calculate net deposits (deposits - withdrawals) in a period

    Args:
        user_id: User identifier
        start_date: Period start date
        end_date: Period end date

    Returns:
        Net deposits amount
    """
    try:
        with get_db() as db:
            transactions = (
                db.query(TransactionModel)
                .filter(
                    TransactionModel.user_id == user_id,
                    TransactionModel.created_at >= start_date,
                    TransactionModel.created_at <= end_date,
                    TransactionModel.transaction_type.in_(
                        [TransactionType.DEPOSIT, TransactionType.WITHDRAW]
                    ),
                )
                .all()
            )

            net_deposits = 0.0
            for tx in transactions:
                if tx.transaction_type == TransactionType.DEPOSIT:
                    net_deposits += float(tx.amount)
                elif tx.transaction_type == TransactionType.WITHDRAW:
                    net_deposits -= float(tx.amount)

            return net_deposits

    except Exception as e:
        logger.error(f"Error calculating net deposits: {e}")
        return 0.0


# ========================================
# Risk Metrics Calculation
# ========================================


def calculate_risk_metrics(
    returns: List[float], benchmark_returns: List[float]
) -> Dict:
    """
    Calculate comprehensive risk-adjusted metrics

    Args:
        returns: Portfolio returns (as percentages)
        benchmark_returns: Benchmark returns (as percentages)

    Returns:
        Dictionary with risk metrics
    """
    try:
        if not returns or len(returns) < 2:
            return {
                "volatility": 0,
                "beta": 0,
                "alpha": 0,
                "sharpe_ratio": 0,
                "information_ratio": 0,
                "max_drawdown": 0,
                "var_95": 0,
                "sortino_ratio": 0,
            }

        returns_array = np.array(returns) / 100  # Convert to decimal
        benchmark_array = np.array(benchmark_returns[: len(returns)]) / 100

        # Volatility (annualized standard deviation)
        volatility = np.std(returns_array) * np.sqrt(252)

        # Beta calculation (covariance / benchmark variance)
        if len(benchmark_array) > 0 and np.var(benchmark_array) > 0:
            covariance = np.cov(returns_array, benchmark_array)[0][1]
            benchmark_variance = np.var(benchmark_array)
            beta = covariance / benchmark_variance
        else:
            beta = 1.0

        # Alpha calculation (excess return over expected return)
        risk_free_rate = get_risk_free_rate()
        portfolio_return = np.mean(returns_array)
        benchmark_return = np.mean(benchmark_array) if len(benchmark_array) > 0 else 0
        expected_return = risk_free_rate + beta * (benchmark_return - risk_free_rate)
        alpha = portfolio_return - expected_return

        # Sharpe Ratio
        excess_return = portfolio_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0

        # Information Ratio (excess return vs benchmark / tracking error)
        if len(benchmark_array) > 0:
            excess_returns = returns_array - benchmark_array
            tracking_error = np.std(excess_returns) * np.sqrt(252)
            information_ratio = (
                np.mean(excess_returns) * 252 / tracking_error
                if tracking_error > 0
                else 0
            )
        else:
            information_ratio = 0

        # Maximum Drawdown
        cumulative_returns = (1 + returns_array).cumprod()
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - peak) / peak
        max_drawdown = np.min(drawdown)

        # Value at Risk (95% confidence)
        var_95 = np.percentile(returns_array, 5)

        # Sortino Ratio (downside deviation)
        negative_returns = returns_array[returns_array < 0]
        downside_deviation = (
            np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0
        )
        sortino_ratio = (
            excess_return / downside_deviation if downside_deviation > 0 else 0
        )

        return {
            "volatility": float(volatility),
            "beta": float(beta),
            "alpha": float(alpha),
            "sharpe_ratio": float(sharpe_ratio),
            "information_ratio": float(information_ratio),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95),
            "sortino_ratio": float(sortino_ratio),
        }

    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        return {
            "volatility": 0,
            "beta": 0,
            "alpha": 0,
            "sharpe_ratio": 0,
            "information_ratio": 0,
            "max_drawdown": 0,
            "var_95": 0,
            "sortino_ratio": 0,
        }


def calculate_performance_attribution(
    user_id: str, start_date: str, end_date: str
) -> Dict:
    """
    Calculate performance attribution by asset/sector

    Args:
        user_id: User identifier
        start_date: Analysis start date
        end_date: Analysis end date

    Returns:
        Performance attribution breakdown
    """
    try:
        with get_db() as db:
            # Get positions during the period
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = (
                datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_date
                else datetime.utcnow()
            )

            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.user_id == user_id,
                    PositionModel.created_at <= end_dt,
                    PositionModel.quantity > 0,
                )
                .all()
            )

            attribution = {}
            total_contribution = 0.0

            for position in positions:
                asset_symbol = position.asset_symbol

                # Calculate asset contribution to portfolio return
                start_price = get_asset_price_at_date(asset_symbol, start_dt)
                end_price = get_asset_price_at_date(asset_symbol, end_dt)

                if start_price > 0:
                    asset_return = (end_price - start_price) / start_price
                    position_value = float(position.quantity) * start_price
                    contribution = asset_return * position_value

                    attribution[asset_symbol] = {
                        "return": asset_return * 100,
                        "weight": position_value,
                        "contribution": contribution,
                    }

                    total_contribution += contribution

            # Normalize weights
            total_value = sum(attr["weight"] for attr in attribution.values())
            if total_value > 0:
                for asset in attribution:
                    attribution[asset]["weight"] = (
                        attribution[asset]["weight"] / total_value * 100
                    )

            return {
                "asset_attribution": attribution,
                "total_contribution": total_contribution,
            }

    except Exception as e:
        logger.error(f"Error calculating performance attribution: {e}")
        return {"asset_attribution": {}, "total_contribution": 0.0}


# ========================================
# Main Portfolio Performance Analysis Tools
# ========================================


@tool
def analyze_portfolio_performance(
    user_id: str, start_date: str, end_date: str = None, benchmark: str = "BTC"
) -> Dict:
    """
    Analyze portfolio performance over a specified period with detailed metrics.

    Args:
        user_id (str): User identifier
        start_date (str): Start date (ISO format)
        end_date (str, optional): End date (ISO format, default: now)
        benchmark (str): Benchmark asset for comparison (default: BTC)

    Returns:
        Dict: Comprehensive performance analysis including:
            - Absolute and relative returns
            - Risk-adjusted metrics
            - Benchmark comparison
            - Performance attribution
    """
    try:
        # Input validation
        if not user_id:
            return {"error": "User ID is required", "error_code": "INVALID_INPUT"}

        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = (
                datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_date
                else datetime.utcnow()
            )
        except ValueError:
            return {
                "error": "Invalid date format. Use ISO format (YYYY-MM-DD)",
                "error_code": "INVALID_DATE",
            }

        # Get basic performance data from existing function
        from tools.tools_crypto_portfolios import calculate_portfolio_performance

        performance = calculate_portfolio_performance.invoke(
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )

        if isinstance(performance, dict) and "error" in performance:
            return performance

        # Calculate period details
        period_days = (end_dt - start_dt).days
        total_return = performance.get("total_return", 0)
        starting_value = performance.get("starting_value", 0)
        ending_value = performance.get("ending_value", 0)

        # Enhanced return calculations
        annualized_return = 0
        if period_days > 0 and starting_value > 0:
            annualized_return = (
                (ending_value / starting_value) ** (365 / period_days) - 1
            ) * 100

        # Get benchmark data for comparison
        benchmark_data = get_benchmark_price_data(benchmark, days=period_days + 30)
        benchmark_return = 0

        if benchmark_data["success"] and benchmark_data["prices"]:
            prices = benchmark_data["prices"]
            # Find prices closest to our date range
            start_price = None
            end_price = None

            for price_data in prices:
                price_date = price_data["date"]
                if not start_price and price_date >= start_dt:
                    start_price = price_data["price"]
                if price_date <= end_dt:
                    end_price = price_data["price"]

            if start_price and end_price and start_price > 0:
                benchmark_return = ((end_price / start_price) - 1) * 100

        # Calculate daily returns for risk metrics
        portfolio_returns = get_daily_portfolio_returns(user_id, start_dt, end_dt)
        benchmark_returns = get_daily_benchmark_returns(benchmark, start_dt, end_dt)

        # Calculate risk metrics
        risk_metrics = calculate_risk_metrics(portfolio_returns, benchmark_returns)

        # Performance attribution
        attribution = calculate_performance_attribution(
            user_id, start_date, end_date or datetime.utcnow().isoformat()
        )

        return {
            "analysis_metadata": {
                "user_id": user_id,
                "analysis_date": datetime.utcnow().isoformat(),
                "benchmark": benchmark,
            },
            "period": {
                "start_date": start_date,
                "end_date": end_date or datetime.utcnow().isoformat(),
                "days": period_days,
            },
            "returns": {
                "total_return": total_return,
                "annualized_return": annualized_return,
                "absolute_gain": ending_value
                - starting_value
                - performance.get("net_deposits", 0),
            },
            "value_changes": {
                "starting_value": starting_value,
                "ending_value": ending_value,
                "net_deposits": performance.get("net_deposits", 0),
            },
            "pnl_breakdown": {
                "realized_pnl": performance.get("realized_pnl", 0),
                "unrealized_pnl": performance.get("unrealized_pnl", 0),
                "total_pnl": performance.get("total_pnl", 0),
            },
            "risk_adjusted_metrics": risk_metrics,
            "benchmark_comparison": {
                "benchmark": benchmark,
                "benchmark_return": benchmark_return,
                "excess_return": total_return - benchmark_return,
                "outperformed": total_return > benchmark_return,
            },
            "performance_attribution": attribution,
        }

    except ValueError as e:
        logger.error(f"Data validation error: {e}")
        return {
            "error": f"Data validation failed: {str(e)}",
            "error_code": "VALIDATION_ERROR",
        }
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        return {"error": "Database connection failed", "error_code": "DB_ERROR"}
    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {
            "error": f"Failed to analyze portfolio performance: {str(e)}",
            "error_code": "UNKNOWN_ERROR",
        }


def get_daily_portfolio_returns(
    user_id: str, start_date: datetime, end_date: datetime
) -> List[float]:
    """
    Calculate daily portfolio returns for risk analysis

    Args:
        user_id: User identifier
        start_date: Start date
        end_date: End date

    Returns:
        List of daily returns as percentages
    """
    try:
        returns = []
        current_date = start_date
        previous_value = None

        while current_date <= end_date:
            portfolio_value = calculate_portfolio_value_at_date(user_id, current_date)

            if previous_value is not None and previous_value > 0:
                daily_return = ((portfolio_value / previous_value) - 1) * 100
                returns.append(daily_return)

            previous_value = portfolio_value
            current_date += timedelta(days=1)

        return returns

    except Exception as e:
        logger.error(f"Error calculating daily portfolio returns: {e}")
        return []


def get_daily_benchmark_returns(
    benchmark: str, start_date: datetime, end_date: datetime
) -> List[float]:
    """
    Get daily benchmark returns for comparison

    Args:
        benchmark: Benchmark symbol
        start_date: Start date
        end_date: End date

    Returns:
        List of daily returns as percentages
    """
    try:
        days_diff = (end_date - start_date).days + 7  # Add buffer
        benchmark_data = get_benchmark_price_data(benchmark, days=days_diff)

        if not benchmark_data["success"]:
            return []

        prices = benchmark_data["prices"]
        returns = []

        for i in range(1, len(prices)):
            if prices[i - 1]["price"] > 0:
                daily_return = ((prices[i]["price"] / prices[i - 1]["price"]) - 1) * 100
                returns.append(daily_return)

        return returns

    except Exception as e:
        logger.error(f"Error calculating benchmark returns: {e}")
        return []


@tool
def compare_to_benchmarks(
    user_id: str, benchmarks: List[str] = ["BTC", "ETH", "SP500"]
) -> Dict:
    """
    Compare portfolio performance against multiple benchmarks.

    Args:
        user_id (str): User identifier
        benchmarks (List[str]): List of benchmark symbols to compare against

    Returns:
        Dict: Comparison results including:
            - Performance vs each benchmark
            - Correlation analysis
            - Risk-adjusted comparisons
    """
    try:
        if not user_id:
            return {"error": "User ID is required", "error_code": "INVALID_INPUT"}

        # Get portfolio metrics for the last year
        from tools.portfolio_analysis.portfolio_overview import get_portfolio_metrics

        portfolio_metrics = get_portfolio_metrics.invoke(
            {"user_id": user_id, "period_days": 365}
        )

        if "error" in portfolio_metrics:
            return portfolio_metrics

        portfolio_return = portfolio_metrics["returns"]["return_percentage"]
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)

        # Get portfolio daily returns for correlation analysis
        portfolio_daily_returns = get_daily_portfolio_returns(
            user_id, start_date, end_date
        )

        comparisons = []

        for benchmark in benchmarks:
            try:
                # Get benchmark data
                benchmark_data = get_benchmark_price_data(benchmark, days=365)

                if not benchmark_data["success"]:
                    logger.warning(f"Failed to get data for benchmark {benchmark}")
                    continue

                # Calculate benchmark return
                prices = benchmark_data["prices"]
                if len(prices) < 2:
                    continue

                start_price = prices[0]["price"]
                end_price = prices[-1]["price"]
                benchmark_return = (
                    ((end_price / start_price) - 1) * 100 if start_price > 0 else 0
                )

                # Get daily returns for correlation
                benchmark_daily_returns = get_daily_benchmark_returns(
                    benchmark, start_date, end_date
                )

                # Calculate correlation
                correlation = 0
                if (
                    len(portfolio_daily_returns) > 0
                    and len(benchmark_daily_returns) > 0
                ):
                    min_length = min(
                        len(portfolio_daily_returns), len(benchmark_daily_returns)
                    )
                    if min_length > 1:
                        port_returns = np.array(portfolio_daily_returns[:min_length])
                        bench_returns = np.array(benchmark_daily_returns[:min_length])
                        correlation_matrix = np.corrcoef(port_returns, bench_returns)
                        correlation = (
                            correlation_matrix[0, 1]
                            if not np.isnan(correlation_matrix[0, 1])
                            else 0
                        )

                # Calculate beta
                beta = 0
                if (
                    len(portfolio_daily_returns) > 0
                    and len(benchmark_daily_returns) > 0
                ):
                    min_length = min(
                        len(portfolio_daily_returns), len(benchmark_daily_returns)
                    )
                    if min_length > 1:
                        port_returns = (
                            np.array(portfolio_daily_returns[:min_length]) / 100
                        )
                        bench_returns = (
                            np.array(benchmark_daily_returns[:min_length]) / 100
                        )
                        if np.var(bench_returns) > 0:
                            covariance = np.cov(port_returns, bench_returns)[0][1]
                            beta = covariance / np.var(bench_returns)

                # Calculate tracking error
                tracking_error = 0
                if (
                    len(portfolio_daily_returns) > 0
                    and len(benchmark_daily_returns) > 0
                ):
                    min_length = min(
                        len(portfolio_daily_returns), len(benchmark_daily_returns)
                    )
                    if min_length > 1:
                        excess_returns = np.array(
                            portfolio_daily_returns[:min_length]
                        ) - np.array(benchmark_daily_returns[:min_length])
                        tracking_error = np.std(excess_returns) * np.sqrt(
                            252
                        )  # Annualized

                comparison = {
                    "benchmark": benchmark,
                    "portfolio_return": portfolio_return,
                    "benchmark_return": benchmark_return,
                    "excess_return": portfolio_return - benchmark_return,
                    "outperformed": portfolio_return > benchmark_return,
                    "correlation": float(correlation),
                    "beta": float(beta),
                    "tracking_error": float(tracking_error),
                    "data_points": len(benchmark_daily_returns),
                }

                comparisons.append(comparison)

            except Exception as e:
                logger.error(f"Error processing benchmark {benchmark}: {e}")
                continue

        if not comparisons:
            return {
                "error": "No benchmark data could be retrieved",
                "error_code": "NO_DATA",
            }

        # Summary statistics
        avg_excess_return = sum(c["excess_return"] for c in comparisons) / len(
            comparisons
        )
        outperformance_rate = (
            sum(1 for c in comparisons if c["outperformed"]) / len(comparisons) * 100
        )

        best_performer = (
            max(comparisons, key=lambda x: x["excess_return"]) if comparisons else None
        )
        worst_performer = (
            min(comparisons, key=lambda x: x["excess_return"]) if comparisons else None
        )

        return {
            "analysis_metadata": {
                "user_id": user_id,
                "analysis_date": datetime.utcnow().isoformat(),
                "period": "365 days",
            },
            "comparisons": comparisons,
            "summary": {
                "average_excess_return": avg_excess_return,
                "outperformance_rate": outperformance_rate,
                "best_relative_performance": (
                    best_performer["benchmark"] if best_performer else None
                ),
                "worst_relative_performance": (
                    worst_performer["benchmark"] if worst_performer else None
                ),
                "highest_correlation": (
                    max(comparisons, key=lambda x: x["correlation"])["benchmark"]
                    if comparisons
                    else None
                ),
                "lowest_correlation": (
                    min(comparisons, key=lambda x: x["correlation"])["benchmark"]
                    if comparisons
                    else None
                ),
            },
        }

    except ValueError as e:
        logger.error(f"Data validation error: {e}")
        return {
            "error": f"Data validation failed: {str(e)}",
            "error_code": "VALIDATION_ERROR",
        }
    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {
            "error": f"Failed to compare to benchmarks: {str(e)}",
            "error_code": "UNKNOWN_ERROR",
        }


@tool
def get_historical_performance(user_id: str, interval: str = "monthly") -> List[Dict]:
    """
    Get historical performance data at specified intervals with real calculations.

    Args:
        user_id (str): User identifier
        interval (str): Time interval ('daily', 'weekly', 'monthly', 'quarterly')

    Returns:
        List[Dict]: Historical performance data points with real portfolio values
    """
    try:
        if not user_id:
            return [{"error": "User ID is required", "error_code": "INVALID_INPUT"}]

        with get_db() as db:
            # Get user's sources to verify user exists
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            if not sources:
                return [
                    {
                        "error": "No active portfolio sources found",
                        "error_code": "NO_DATA",
                    }
                ]

            # Determine interval days
            interval_days = {
                "daily": 1,
                "weekly": 7,
                "monthly": 30,
                "quarterly": 90,
            }.get(interval, 30)

            # Generate historical data points with real calculations
            performance_history = []
            current_date = datetime.utcnow()
            periods_to_analyze = min(
                24, int(730 / interval_days)
            )  # Up to 24 periods or 2 years max

            for i in range(periods_to_analyze):
                period_end = current_date - timedelta(days=i * interval_days)
                period_start = period_end - timedelta(days=interval_days)

                try:
                    # Calculate real portfolio values
                    start_value = calculate_portfolio_value_at_date(
                        user_id, period_start
                    )
                    end_value = calculate_portfolio_value_at_date(user_id, period_end)
                    net_deposits = get_net_deposits_in_period(
                        user_id, period_start, period_end
                    )

                    # Calculate time-weighted return
                    period_return = 0
                    if start_value > 0:
                        adjusted_end_value = end_value - net_deposits
                        period_return = ((adjusted_end_value / start_value) - 1) * 100

                    # Get benchmark performance for comparison
                    benchmark_return = 0
                    try:
                        benchmark_data = get_benchmark_price_data(
                            "BTC", days=interval_days + 7
                        )
                        if (
                            benchmark_data["success"]
                            and len(benchmark_data["prices"]) >= 2
                        ):
                            prices = benchmark_data["prices"]
                            bench_start = None
                            bench_end = None

                            # Find prices closest to our period dates
                            for price_data in prices:
                                price_date = price_data["date"]
                                if abs((price_date - period_start).days) < 3:
                                    bench_start = price_data["price"]
                                if abs((price_date - period_end).days) < 3:
                                    bench_end = price_data["price"]

                            if bench_start and bench_end and bench_start > 0:
                                benchmark_return = ((bench_end / bench_start) - 1) * 100
                    except Exception as be:
                        logger.warning(f"Failed to get benchmark data for period: {be}")

                    performance_history.append(
                        {
                            "period_start": period_start.isoformat(),
                            "period_end": period_end.isoformat(),
                            "interval": interval,
                            "portfolio_performance": {
                                "return_percentage": round(period_return, 2),
                                "absolute_return": round(
                                    end_value - start_value - net_deposits, 2
                                ),
                                "starting_value": round(start_value, 2),
                                "ending_value": round(end_value, 2),
                            },
                            "cash_flows": {
                                "net_deposits": round(net_deposits, 2),
                                "has_deposits": net_deposits > 0,
                                "has_withdrawals": net_deposits < 0,
                            },
                            "benchmark_comparison": {
                                "benchmark": "BTC",
                                "benchmark_return": round(benchmark_return, 2),
                                "excess_return": round(
                                    period_return - benchmark_return, 2
                                ),
                                "outperformed": period_return > benchmark_return,
                            },
                            "period_metrics": {
                                "days": interval_days,
                                "annualized_return": (
                                    round(
                                        (
                                            (1 + period_return / 100)
                                            ** (365 / interval_days)
                                            - 1
                                        )
                                        * 100,
                                        2,
                                    )
                                    if period_return != 0
                                    else 0
                                ),
                            },
                        }
                    )

                except Exception as pe:
                    logger.warning(
                        f"Failed to calculate performance for period {period_start} to {period_end}: {pe}"
                    )
                    continue

            # Sort by period_start (most recent first)
            performance_history.sort(key=lambda x: x["period_start"], reverse=True)

            # Add summary statistics
            if performance_history:
                returns = [
                    p["portfolio_performance"]["return_percentage"]
                    for p in performance_history
                    if p["portfolio_performance"]["return_percentage"] != 0
                ]

                if returns:
                    summary_stats = {
                        "total_periods": len(performance_history),
                        "periods_with_data": len(returns),
                        "average_return": round(np.mean(returns), 2),
                        "volatility": round(np.std(returns), 2),
                        "best_period": round(max(returns), 2),
                        "worst_period": round(min(returns), 2),
                        "positive_periods": sum(1 for r in returns if r > 0),
                        "negative_periods": sum(1 for r in returns if r < 0),
                        "win_rate": (
                            round(
                                sum(1 for r in returns if r > 0) / len(returns) * 100, 1
                            )
                            if returns
                            else 0
                        ),
                    }

                    # Insert summary at the beginning
                    performance_history.insert(
                        0,
                        {
                            "summary": summary_stats,
                            "analysis_date": datetime.utcnow().isoformat(),
                        },
                    )

            return performance_history

    except ValueError as e:
        logger.error(f"Data validation error: {e}")
        return [
            {
                "error": f"Data validation failed: {str(e)}",
                "error_code": "VALIDATION_ERROR",
            }
        ]
    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return [
            {
                "error": f"Failed to get historical performance: {str(e)}",
                "error_code": "UNKNOWN_ERROR",
            }
        ]


tools = [
    analyze_portfolio_performance,
    compare_to_benchmarks,
    get_historical_performance,
]
