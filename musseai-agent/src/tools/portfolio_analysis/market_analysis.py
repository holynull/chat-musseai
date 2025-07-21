from decimal import Decimal
import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta
from langchain.agents import tool
from mysql.db import get_db
from mysql.model import (
    PortfolioSourceModel,
    PositionModel,
    TransactionModel,
    TransactionType,
)
from loggers import logger
import traceback

import requests
from .portfolio_overview import get_comprehensive_market_condition

from utils.api_decorators import (
    cache_result,
    rate_limit,
    retry_on_429,
    api_call_with_cache_and_rate_limit,
)


# ========================================
# Market Analysis Tools
# ========================================


@api_call_with_cache_and_rate_limit(
    cache_duration=300,  # Cache for 5 minutes
    rate_limit_interval=1.2,  # CoinGecko rate limit
    max_retries=3,
    retry_delay=2,
)
def fetch_coingecko_market_data(symbol):
    """Fetch market data from CoinGecko with caching, rate limiting and retry logic"""
    url = f"https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": symbol.lower(),  # CoinGecko uses lowercase IDs
        "per_page": 1,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d",
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


@tool
def analyze_market_conditions(asset_symbols: List[str] = None) -> Dict:
    """
    Analyze current market conditions relevant to the portfolio.

    Args:
        asset_symbols (List[str], optional): Specific assets to analyze

    Returns:
        Dict: Market analysis and conditions
    """

    @cache_result(duration=300)  # Cache results for 5 minutes
    def _analyze_market_conditions(assets):
        try:
            # Get base market condition data
            market_data = get_comprehensive_market_condition()

            # Initialize result dictionary with general market data
            result = {
                "market_condition": market_data.get(
                    "overall_market_condition", "sideways"
                ),
                "fear_greed_index": market_data.get("fear_greed_index"),
                "fear_greed_classification": market_data.get(
                    "fear_greed_classification"
                ),
                "btc_trend": market_data.get("btc_trend", {}).get("trend"),
                "btc_volatility": market_data.get("btc_trend", {}).get("volatility"),
                "market_metrics": market_data.get("market_metrics", {}),
                "analysis_time": datetime.now().isoformat(),
            }

            # If specific assets are provided, analyze them
            if (
                asset_symbols
                and isinstance(asset_symbols, list)
                and len(asset_symbols) > 0
            ):
                asset_specific_analysis = {}

                for symbol in asset_symbols:
                    try:
                        # Get asset-specific data from CoinGecko or other API
                        symbol_upper = symbol.upper()

                        asset_data = fetch_coingecko_market_data(symbol)

                        if asset_data and len(asset_data) > 0:
                            data = asset_data[0]

                            # Determine asset-specific trend
                            price_change_24h = data.get(
                                "price_change_percentage_24h", 0
                            )
                            price_change_7d = data.get("price_change_percentage_7d", 0)

                            if price_change_24h > 10 and price_change_7d > 15:
                                asset_trend = "strong_bullish"
                            elif price_change_24h > 5 and price_change_7d > 0:
                                asset_trend = "bullish"
                            elif price_change_24h < -10 and price_change_7d < -15:
                                asset_trend = "strong_bearish"
                            elif price_change_24h < -5 and price_change_7d < 0:
                                asset_trend = "bearish"
                            else:
                                asset_trend = "sideways"

                            # Determine asset sentiment relative to market
                            if (
                                asset_trend == "strong_bullish"
                                and result["market_condition"] != "bull_market"
                            ):
                                asset_sentiment = "outperforming_market"
                            elif (
                                asset_trend == "strong_bearish"
                                and result["market_condition"] != "bear_market"
                            ):
                                asset_sentiment = "underperforming_market"
                            elif asset_trend == result["market_condition"]:
                                asset_sentiment = "aligned_with_market"
                            else:
                                asset_sentiment = "mixed_signals"

                            # Store asset analysis
                            asset_specific_analysis[symbol_upper] = {
                                "current_price": data.get("current_price", 0),
                                "market_cap": data.get("market_cap", 0),
                                "market_cap_rank": data.get("market_cap_rank"),
                                "price_change_24h": price_change_24h,
                                "price_change_7d": price_change_7d,
                                "volume_24h": data.get("total_volume", 0),
                                "high_24h": data.get("high_24h", 0),
                                "low_24h": data.get("low_24h", 0),
                                "ath": data.get("ath", 0),
                                "ath_change_percentage": data.get(
                                    "ath_change_percentage", 0
                                ),
                                "trend": asset_trend,
                                "sentiment": asset_sentiment,
                                "recommendation": get_asset_recommendation(
                                    asset_trend, result["market_condition"]
                                ),
                            }
                        else:
                            asset_specific_analysis[symbol_upper] = {
                                "error": "No data found for this asset"
                            }
                    except Exception as e:
                        logger.warning(f"Failed to analyze asset {symbol}: {e}")
                        asset_specific_analysis[symbol_upper] = {
                            "error": f"Analysis failed: {str(e)}"
                        }

                # Add asset-specific analysis to result
                result["asset_analysis"] = asset_specific_analysis

                # Add correlations between assets if multiple assets
                if len(asset_specific_analysis) > 1:
                    try:
                        correlations = calculate_asset_correlations(asset_symbols)
                        result["asset_correlations"] = correlations
                    except Exception as e:
                        logger.warning(f"Failed to calculate asset correlations: {e}")

            # Add market insights based on conditions
            result["market_insights"] = generate_market_insights(result)

            return result

        except Exception as e:
            logger.error(
                f"Failed to analyze market conditions: {e}\n{traceback.format_exc()}"
            )
            return {
                "error": f"Failed to analyze market conditions: {str(e)}",
                "market_condition": "unknown",
            }

    return _analyze_market_conditions(tuple(asset_symbols) if asset_symbols else None)


def get_asset_recommendation(asset_trend, market_condition):
    """Generate asset-specific recommendation based on trend and market condition"""
    if asset_trend == "strong_bullish" and market_condition == "bull_market":
        return "Consider taking partial profits at resistance levels"
    elif asset_trend == "strong_bullish" and market_condition != "bull_market":
        return "Asset showing strength against market trend, monitor closely"
    elif asset_trend == "bullish" and market_condition == "bull_market":
        return "Hold and consider increasing position on dips"
    elif asset_trend == "strong_bearish" and market_condition == "bear_market":
        return "Consider reducing exposure or implementing hedging strategies"
    elif asset_trend == "bearish" and market_condition != "bear_market":
        return "Asset underperforming market, evaluate position fundamentals"
    elif asset_trend == "sideways":
        return "Monitor key support/resistance levels for breakout signals"
    else:
        return "Maintain current position and monitor market conditions"


@api_call_with_cache_and_rate_limit(
    cache_duration=1800,  # Cache for 30 minutes (historical data changes less frequently)
    rate_limit_interval=1.2,
    max_retries=3,
    retry_delay=2,
)
def fetch_coingecko_market_chart(symbol, days="30", interval="daily"):
    """Fetch market chart data from CoinGecko with caching and rate limiting"""
    url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": interval}

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


@cache_result(duration=1800)  # Cache for 30 minutes
def calculate_asset_correlations(asset_symbols):
    """Calculate correlations between assets based on price movements"""
    try:
        # Get historical price data for correlation calculation
        historical_prices = {}

        for symbol in asset_symbols:
            try:
                # Get 30-day price history
                data = fetch_coingecko_market_chart(symbol)

                if "prices" in data and len(data["prices"]) > 0:
                    # Extract just the prices from the data
                    prices = [price[1] for price in data["prices"]]
                    historical_prices[symbol.upper()] = prices
            except Exception as e:
                logger.warning(f"Failed to get historical prices for {symbol}: {e}")

        # Calculate correlations if we have data for at least two assets
        if len(historical_prices) > 1:
            correlation_matrix = {}

            # Ensure all price arrays have the same length
            min_length = min(len(prices) for prices in historical_prices.values())
            for symbol in historical_prices:
                historical_prices[symbol] = historical_prices[symbol][:min_length]

            # Calculate correlation between each pair of assets
            for symbol1 in historical_prices:
                correlation_matrix[symbol1] = {}
                for symbol2 in historical_prices:
                    if symbol1 != symbol2:
                        correlation = np.corrcoef(
                            historical_prices[symbol1], historical_prices[symbol2]
                        )[0, 1]
                        correlation_matrix[symbol1][symbol2] = round(
                            float(correlation), 3
                        )
                    else:
                        correlation_matrix[symbol1][symbol2] = 1.0

            return correlation_matrix
        else:
            return {"message": "Insufficient data to calculate correlations"}

    except Exception as e:
        logger.error(f"Error calculating asset correlations: {e}")
        return {"error": str(e)}


def generate_market_insights(market_data):
    """Generate market insights based on current conditions"""
    insights = []

    # Market condition insights
    market_condition = market_data.get("market_condition", "sideways")
    fear_greed_index = market_data.get("fear_greed_index", 50)
    btc_trend = market_data.get("btc_trend")

    # Generate insights based on Fear & Greed Index
    if fear_greed_index is not None:
        if fear_greed_index >= 80:
            insights.append(
                {
                    "type": "WARNING",
                    "message": f"Market showing extreme greed (Fear & Greed Index: {fear_greed_index}). Historical data suggests potential correction risk.",
                }
            )
        elif fear_greed_index <= 20:
            insights.append(
                {
                    "type": "OPPORTUNITY",
                    "message": f"Market showing extreme fear (Fear & Greed Index: {fear_greed_index}). Historical data suggests potential buying opportunity for quality assets.",
                }
            )

    # Generate insights based on market condition
    if market_condition == "bull_market":
        insights.append(
            {
                "type": "INFO",
                "message": "Bull market conditions detected. Focus on profit-taking strategies and managing risk as assets approach resistance levels.",
            }
        )
    elif market_condition == "bear_market":
        insights.append(
            {
                "type": "INFO",
                "message": "Bear market conditions detected. Focus on capital preservation, consider increased stablecoin allocation, and selective accumulation of quality assets.",
            }
        )

    # BTC dominance insights
    btc_dominance = market_data.get("market_metrics", {}).get("btc_dominance")
    if btc_dominance is not None:
        if btc_dominance > 60:
            insights.append(
                {
                    "type": "INFO",
                    "message": f"High Bitcoin dominance ({btc_dominance:.1f}%) suggests altcoin caution is warranted.",
                }
            )
        elif btc_dominance < 40:
            insights.append(
                {
                    "type": "INFO",
                    "message": f"Low Bitcoin dominance ({btc_dominance:.1f}%) indicates strong altcoin season, monitor for potential reversal.",
                }
            )

    # Market cap change insights
    market_cap_change = market_data.get("market_metrics", {}).get(
        "market_cap_change_24h"
    )
    if market_cap_change is not None:
        if market_cap_change > 5:
            insights.append(
                {
                    "type": "POSITIVE",
                    "message": f"Strong market growth with {market_cap_change:.1f}% increase in total market cap over 24h.",
                }
            )
        elif market_cap_change < -5:
            insights.append(
                {
                    "type": "NEGATIVE",
                    "message": f"Market under pressure with {abs(market_cap_change):.1f}% decrease in total market cap over 24h.",
                }
            )

    # Volatility insights
    btc_volatility = market_data.get("btc_volatility")
    if btc_volatility is not None:
        if btc_volatility > 80:
            insights.append(
                {
                    "type": "WARNING",
                    "message": f"High market volatility detected. Consider adjusting position sizes and implementing tighter risk management.",
                }
            )
        elif btc_volatility < 30:
            insights.append(
                {
                    "type": "INFO",
                    "message": f"Low market volatility may indicate accumulation phase or potential breakout soon.",
                }
            )

    # Asset-specific insights
    if "asset_analysis" in market_data:
        outperformers = [
            symbol
            for symbol, data in market_data["asset_analysis"].items()
            if data.get("sentiment") == "outperforming_market"
        ]

        underperformers = [
            symbol
            for symbol, data in market_data["asset_analysis"].items()
            if data.get("sentiment") == "underperforming_market"
        ]

        if outperformers:
            insights.append(
                {
                    "type": "POSITIVE",
                    "message": f"Assets outperforming the market: {', '.join(outperformers)}",
                }
            )

        if underperformers:
            insights.append(
                {
                    "type": "WARNING",
                    "message": f"Assets underperforming the market: {', '.join(underperformers)}",
                }
            )

    # Correlation insights
    if "asset_correlations" in market_data and isinstance(
        market_data["asset_correlations"], dict
    ):
        high_correlations = []
        low_correlations = []

        for symbol1, correlations in market_data["asset_correlations"].items():
            if isinstance(correlations, dict):
                for symbol2, correlation in correlations.items():
                    if symbol1 != symbol2:
                        pair = f"{symbol1}-{symbol2}"
                        if correlation > 0.8:
                            high_correlations.append((pair, correlation))
                        elif correlation < 0.2:
                            low_correlations.append((pair, correlation))

        if high_correlations:
            top_high = sorted(high_correlations, key=lambda x: x[1], reverse=True)[:3]
            insights.append(
                {
                    "type": "INFO",
                    "message": f"High correlation pairs (reduced diversification): {', '.join([f'{pair} ({corr:.2f})' for pair, corr in top_high])}",
                }
            )

        if low_correlations:
            top_low = sorted(low_correlations, key=lambda x: x[1])[:3]
            insights.append(
                {
                    "type": "POSITIVE",
                    "message": f"Low correlation pairs (good diversification): {', '.join([f'{pair} ({corr:.2f})' for pair, corr in top_low])}",
                }
            )

    return insights


@tool
def get_market_opportunities(user_id: str, opportunity_type: str = "ALL") -> Dict:
    """
    Identify market opportunities based on current conditions and portfolio.

    Args:
        user_id (str): User identifier
        opportunity_type (str): Type of opportunities (ALL, DIP_BUYING, PROFIT_TAKING, ARBITRAGE)

    Returns:
        Dict: Market opportunities with actionable recommendations
    """

    @cache_result(duration=600)  # Cache for 10 minutes
    def _get_market_opportunities(uid, opp_type):
        try:
            # Get portfolio data
            from tools.tools_crypto_portfolios import get_user_portfolio_summary

            portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

            if (
                portfolio is None
                or isinstance(portfolio, str)
                or (isinstance(portfolio, dict) and "error" in portfolio)
            ):
                return {"error": "Failed to retrieve portfolio data"}

            if isinstance(portfolio, str) or "error" in portfolio:
                return {"error": "Failed to retrieve portfolio data"}

            opportunities = []

            # Analyze market for opportunities
            market_conditions = analyze_market_conditions.invoke(
                {"asset_symbols": ["BTC", "ETH", "BNB", "SOL"]}
            )

            if (
                isinstance(market_conditions, dict)
                and "asset_analysis" in market_conditions
            ):
                # Dip buying opportunities
                if opportunity_type in ["ALL", "DIP_BUYING"]:
                    for asset in market_conditions["asset_analysis"]:
                        if asset["24h_change"] < -5 and asset["rsi"] < 35:
                            opportunities.append(
                                {
                                    "type": "DIP_BUYING",
                                    "asset": asset["symbol"],
                                    "reasoning": f"{asset['symbol']} down {abs(asset['24h_change'])*100:.1f}% with oversold RSI",
                                    "entry_strategy": "Dollar-cost average over 3 days",
                                    "risk_level": "MEDIUM",
                                    "potential_return": "10-20%",
                                    "time_horizon": "1-4 weeks",
                                    "allocation_suggestion": min(
                                        portfolio["total_value"] * 0.05, 1000
                                    ),
                                }
                            )

                # Profit taking opportunities
                if opportunity_type in ["ALL", "PROFIT_TAKING"]:
                    for position in portfolio.get("positions_by_asset", []):
                        if position.get("pnl_percentage", 0) > 50:
                            opportunities.append(
                                {
                                    "type": "PROFIT_TAKING",
                                    "asset": position["symbol"],
                                    "current_profit": f"{position['pnl_percentage']:.1f}%",
                                    "reasoning": "Significant profit achieved, consider partial exit",
                                    "exit_strategy": "Sell 25-50% of position",
                                    "risk_level": "LOW",
                                    "action": "Take partial profits to lock in gains",
                                }
                            )

                # Rebalancing opportunities
                if opportunity_type in ["ALL", "REBALANCING"]:
                    from tools.tools_crypto_portfolios import get_portfolio_allocation

                    current_allocation = get_portfolio_allocation.invoke(
                        {"user_id": user_id, "group_by": "asset"}
                    )

                    if isinstance(current_allocation, list):
                        for item in current_allocation:
                            if item["percentage"] > 30:
                                opportunities.append(
                                    {
                                        "type": "REBALANCING",
                                        "asset": item["group"],
                                        "current_allocation": f"{item['percentage']:.1f}%",
                                        "reasoning": "Over-concentrated position",
                                        "action": "Reduce allocation to 20-25%",
                                        "risk_level": "LOW",
                                        "benefit": "Improved diversification",
                                    }
                                )

            # Yield opportunities
            if opportunity_type in ["ALL", "YIELD"]:
                stablecoin_value = sum(
                    p["total_value"]
                    for p in portfolio.get("positions_by_asset", [])
                    if any(
                        stable in p["symbol"].upper()
                        for stable in ["USDT", "USDC", "DAI"]
                    )
                )

                if stablecoin_value > 1000:
                    opportunities.append(
                        {
                            "type": "YIELD",
                            "asset": "Stablecoins",
                            "amount": stablecoin_value,
                            "reasoning": "Idle stablecoins can earn yield",
                            "platforms": [
                                {"name": "Aave", "apy": "4-6%", "risk": "LOW"},
                                {"name": "Compound", "apy": "3-5%", "risk": "LOW"},
                                {"name": "Curve", "apy": "5-8%", "risk": "MEDIUM"},
                            ],
                            "recommended_allocation": stablecoin_value * 0.7,
                            "risk_level": "LOW",
                            "action": "Deploy to DeFi protocols",
                        }
                    )

            # Sort opportunities by potential
            opportunities.sort(
                key=lambda x: {
                    "DIP_BUYING": 3,
                    "PROFIT_TAKING": 2,
                    "REBALANCING": 1,
                    "YIELD": 1,
                }.get(x["type"], 0),
                reverse=True,
            )

            return {
                "opportunities": opportunities,
                "market_context": {
                    "overall_trend": market_conditions.get("market_overview", {}).get(
                        "market_trend", "UNKNOWN"
                    ),
                    "volatility": market_conditions.get("market_overview", {}).get(
                        "volatility_index", 0
                    ),
                    "sentiment": market_conditions.get("market_overview", {}).get(
                        "fear_greed_index", 50
                    ),
                },
                "portfolio_context": {
                    "total_value": portfolio["total_value"],
                    "cash_available": (
                        stablecoin_value if "stablecoin_value" in locals() else 0
                    ),
                    "current_positions": len(portfolio.get("positions_by_asset", [])),
                },
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Exception:{e}\n{traceback.format_exc()}")
            return {"error": f"Failed to get market opportunities: {str(e)}"}

    return _get_market_opportunities(user_id, opportunity_type)


tools = [
    analyze_market_conditions,
    get_market_opportunities,
]
