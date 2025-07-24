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
    cache_duration=300,
    rate_limit_interval=1.2,
    max_retries=3,
    retry_delay=2,
)
def fetch_coingecko_market_data(symbol):
    """Fetch market data from CoinGecko using api_manager"""
    from utils.api_manager import api_manager

    return api_manager.fetch_market_data_coingecko(symbol)


@api_call_with_cache_and_rate_limit(
    cache_duration=1800,
    rate_limit_interval=1.2,
    max_retries=3,
    retry_delay=2,
)
def fetch_coingecko_market_chart(symbol, days="30", interval="daily"):
    """Fetch market chart data from CoinGecko using api_manager"""
    from utils.api_manager import api_manager

    return api_manager.fetch_market_chart_coingecko(symbol, days, interval)


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

                        # Try to fetch data, handle missing assets gracefully
                        try:
                            asset_data = fetch_coingecko_market_data(symbol)

                            # Check if valid data was returned
                            if not asset_data or len(asset_data) == 0:
                                asset_specific_analysis[symbol_upper] = {
                                    "error": f"No data found for {symbol}. Verify the asset symbol is correct."
                                }
                                continue

                            data = asset_data[0]

                            # Get additional technical indicators
                            technical_indicators = fetch_technical_indicators(symbol)

                            # Extract price changes
                            price_change_24h = data.get(
                                "price_change_percentage_24h", 0
                            )
                            price_change_7d = data.get("price_change_percentage_7d", 0)
                            price_change_1h = data.get(
                                "price_change_percentage_1h_in_currency", 0
                            )

                            # Get volume and market cap data for additional context
                            volume_24h = data.get("total_volume", 0)
                            market_cap = data.get("market_cap", 0)
                            volume_to_mcap_ratio = (
                                volume_24h / market_cap if market_cap > 0 else 0
                            )

                            # Determine asset category for adaptive thresholds
                            if market_cap > 10000000000:  # $10B+
                                asset_category = "large_cap"
                                volatility_factor = 1.0
                            elif market_cap > 1000000000:  # $1B+
                                asset_category = "mid_cap"
                                volatility_factor = 1.5
                            else:
                                asset_category = "small_cap"
                                volatility_factor = 2.0

                            # Adaptive thresholds based on asset category and market condition
                            is_bear_market = result["market_condition"] == "bear_market"
                            threshold_multiplier = 0.8 if is_bear_market else 1.0

                            # Adaptive trend thresholds based on asset category and market condition
                            strong_bull_24h = (
                                5 * volatility_factor * threshold_multiplier
                            )
                            strong_bull_7d = (
                                10 * volatility_factor * threshold_multiplier
                            )
                            bull_24h = 2 * volatility_factor * threshold_multiplier
                            bull_7d = 5 * volatility_factor * threshold_multiplier

                            # RSI interpretation
                            rsi = technical_indicators.get("rsi_14", 50)
                            rsi_signal = "neutral"
                            if rsi >= 70:
                                rsi_signal = "overbought"
                            elif rsi <= 30:
                                rsi_signal = "oversold"

                            # Determine trend based on multiple indicators
                            # Short-term (1-3 days)
                            if (
                                price_change_24h > strong_bull_24h
                                and price_change_1h > 0
                            ):
                                short_term_trend = "strong_bullish"
                            elif price_change_24h > bull_24h:
                                short_term_trend = "bullish"
                            elif (
                                price_change_24h < -strong_bull_24h
                                and price_change_1h < 0
                            ):
                                short_term_trend = "strong_bearish"
                            elif price_change_24h < -bull_24h:
                                short_term_trend = "bearish"
                            else:
                                short_term_trend = "sideways"

                            # Medium-term (1-2 weeks)
                            if price_change_7d > strong_bull_7d:
                                medium_term_trend = "strong_bullish"
                            elif price_change_7d > bull_7d:
                                medium_term_trend = "bullish"
                            elif price_change_7d < -strong_bull_7d:
                                medium_term_trend = "strong_bearish"
                            elif price_change_7d < -bull_7d:
                                medium_term_trend = "bearish"
                            else:
                                medium_term_trend = "sideways"

                            # Combined trend analysis
                            if (
                                short_term_trend == "strong_bullish"
                                and medium_term_trend in ["strong_bullish", "bullish"]
                            ):
                                asset_trend = "strong_bullish"
                            elif (
                                short_term_trend == "strong_bearish"
                                and medium_term_trend in ["strong_bearish", "bearish"]
                            ):
                                asset_trend = "strong_bearish"
                            elif (
                                short_term_trend in ["bullish", "strong_bullish"]
                                and medium_term_trend != "strong_bearish"
                            ):
                                asset_trend = "bullish"
                            elif (
                                short_term_trend in ["bearish", "strong_bearish"]
                                and medium_term_trend != "strong_bullish"
                            ):
                                asset_trend = "bearish"
                            else:
                                asset_trend = "mixed"

                            # Volume analysis
                            volume_signal = "neutral"
                            avg_volume = technical_indicators.get(
                                "average_volume_10d", volume_24h
                            )
                            if volume_24h > avg_volume * 1.5:
                                volume_signal = "high"
                            elif volume_24h < avg_volume * 0.5:
                                volume_signal = "low"

                            # Trend confirmation by volume
                            if (
                                asset_trend in ["strong_bullish", "bullish"]
                                and volume_signal == "high"
                            ):
                                trend_strength = "confirmed"
                            elif (
                                asset_trend in ["strong_bearish", "bearish"]
                                and volume_signal == "high"
                            ):
                                trend_strength = "confirmed"
                            else:
                                trend_strength = "unconfirmed"

                            # Market vs Asset trend comparison for relative performance
                            market_trend_map = {
                                "bull_market": ["bullish", "strong_bullish"],
                                "bear_market": ["bearish", "strong_bearish"],
                                "sideways": ["mixed", "sideways"],
                            }

                            # Determine if asset is outperforming or underperforming the market
                            market_trend = result["market_condition"]
                            expected_asset_trends = market_trend_map.get(
                                market_trend, ["mixed"]
                            )

                            if (
                                asset_trend == "strong_bullish"
                                and market_trend != "bull_market"
                            ):
                                asset_sentiment = "strongly_outperforming"
                            elif (
                                asset_trend == "strong_bearish"
                                and market_trend != "bear_market"
                            ):
                                asset_sentiment = "strongly_underperforming"
                            elif (
                                asset_trend in ["bullish", "strong_bullish"]
                                and market_trend == "bear_market"
                            ):
                                asset_sentiment = "outperforming"
                            elif (
                                asset_trend in ["bearish", "strong_bearish"]
                                and market_trend == "bull_market"
                            ):
                                asset_sentiment = "underperforming"
                            elif asset_trend in expected_asset_trends:
                                asset_sentiment = "market_aligned"
                            else:
                                asset_sentiment = "mixed_signals"

                            # Support and resistance levels
                            support_level = technical_indicators.get(
                                "support_level", data.get("low_24h", 0) * 0.95
                            )
                            resistance_level = technical_indicators.get(
                                "resistance_level", data.get("high_24h", 0) * 1.05
                            )

                            # Calculate distance to key levels as percentages
                            current_price = data.get("current_price", 0)
                            distance_to_support = (
                                ((current_price - support_level) / current_price * 100)
                                if current_price > 0
                                else 0
                            )
                            distance_to_resistance = (
                                (
                                    (resistance_level - current_price)
                                    / current_price
                                    * 100
                                )
                                if current_price > 0
                                else 0
                            )

                            # Store asset analysis with comprehensive data
                            asset_specific_analysis[symbol_upper] = {
                                "current_price": data.get("current_price", 0),
                                "market_cap": market_cap,
                                "market_cap_rank": data.get("market_cap_rank"),
                                "price_changes": {
                                    "1h": price_change_1h,
                                    "24h": price_change_24h,
                                    "7d": price_change_7d,
                                    "30d": data.get(
                                        "price_change_percentage_30d_in_currency", 0
                                    ),
                                },
                                "volume": {
                                    "24h": volume_24h,
                                    "volume_to_mcap": round(volume_to_mcap_ratio, 4),
                                    "signal": volume_signal,
                                },
                                "technical_indicators": {
                                    "rsi_14d": rsi,
                                    "rsi_signal": rsi_signal,
                                    "macd": technical_indicators.get("macd", 0),
                                    "ema_20": technical_indicators.get("ema_20", 0),
                                    "ema_50": technical_indicators.get("ema_50", 0),
                                },
                                "key_levels": {
                                    "support": support_level,
                                    "resistance": resistance_level,
                                    "distance_to_support": round(
                                        distance_to_support, 2
                                    ),
                                    "distance_to_resistance": round(
                                        distance_to_resistance, 2
                                    ),
                                    "ath": data.get("ath", 0),
                                    "ath_change_percentage": data.get(
                                        "ath_change_percentage", 0
                                    ),
                                    "atl": data.get("atl", 0),
                                    "atl_change_percentage": data.get(
                                        "atl_change_percentage", 0
                                    ),
                                },
                                "trends": {
                                    "short_term": short_term_trend,
                                    "medium_term": medium_term_trend,
                                    "overall": asset_trend,
                                    "strength": trend_strength,
                                },
                                "sentiment": asset_sentiment,
                                "asset_category": asset_category,
                                "recommendation": get_asset_recommendation(
                                    asset_trend,
                                    result["market_condition"],
                                    rsi,
                                    distance_to_support,
                                    distance_to_resistance,
                                    trend_strength,
                                ),
                            }
                        except requests.exceptions.HTTPError as e:
                            if e.response.status_code == 404:
                                asset_specific_analysis[symbol_upper] = {
                                    "error": f"Asset {symbol} not found. Please verify the symbol."
                                }
                            else:
                                asset_specific_analysis[symbol_upper] = {
                                    "error": f"API error: {str(e)}"
                                }
                            traceback.format_exc()
                    except Exception as e:
                        logger.warning(f"Failed to analyze asset {symbol}: {e}")
                        asset_specific_analysis[symbol_upper] = {
                            "error": f"Analysis failed: {str(e)}"
                        }
                        traceback.format_exc()

                # Add asset-specific analysis to result
                result["asset_analysis"] = asset_specific_analysis

                # Add correlations between assets if multiple assets
                if len(asset_specific_analysis) > 1:
                    try:
                        correlations = calculate_asset_correlations(asset_symbols)
                        result["asset_correlations"] = correlations

                        # Add diversification score based on correlations
                        if (
                            isinstance(correlations, dict)
                            and not "error" in correlations
                        ):
                            avg_correlation = calculate_average_correlation(
                                correlations
                            )
                            result["portfolio_metrics"] = {
                                "average_correlation": avg_correlation,
                                "diversification_score": (
                                    100 - (avg_correlation * 100)
                                    if avg_correlation <= 1
                                    else 0
                                ),
                            }
                    except Exception as e:
                        logger.warning(f"Failed to calculate asset correlations: {e}")
                        traceback.format_exc()

            # Add market insights based on conditions
            result["market_insights"] = generate_market_insights(result)

            # Add market regime identification
            result["market_regime"] = identify_market_regime(result)

            # Add seasonal factors if available
            result["seasonal_factors"] = analyze_seasonal_factors()

            # Add risk levels for the overall market
            result["risk_metrics"] = calculate_market_risk_metrics(result)

            return result

        except Exception as e:
            logger.error(
                f"Failed to analyze market conditions: {e}\n{traceback.format_exc()}"
            )
            traceback.format_exc()
            return {
                "error": f"Failed to analyze market conditions: {str(e)}",
                "market_condition": "unknown",
            }

    return _analyze_market_conditions(tuple(asset_symbols) if asset_symbols else None)


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
                traceback.format_exc()

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
        traceback.format_exc()
        return {"error": str(e)}


def fetch_technical_indicators(symbol):
    """Fetch or calculate technical indicators for an asset"""
    try:
        # This would ideally come from an API or be calculated from historical price data
        # For this example, we'll return placeholder values
        # In a real implementation, you would calculate these from price data

        # Get historical price data
        historical_data = fetch_coingecko_market_chart(symbol, days="30")

        if not historical_data or "prices" not in historical_data:
            return {
                "rsi_14": 50,  # Neutral RSI
                "macd": 0,
                "ema_20": 0,
                "ema_50": 0,
                "support_level": 0,
                "resistance_level": 0,
                "average_volume_10d": 0,
            }

        # Extract price and volume data
        prices = [price[1] for price in historical_data.get("prices", [])]
        volumes = [vol[1] for vol in historical_data.get("total_volumes", [])]

        if len(prices) < 14 or len(volumes) < 10:
            return {
                "rsi_14": 50,
                "macd": 0,
                "ema_20": 0,
                "ema_50": 0,
                "support_level": 0,
                "resistance_level": 0,
                "average_volume_10d": 0,
            }

        # Calculate RSI (14-day)
        rsi = calculate_rsi(prices, period=14)

        # Calculate EMAs
        ema_20 = calculate_ema(prices, period=20) if len(prices) >= 20 else prices[-1]
        ema_50 = calculate_ema(prices, period=50) if len(prices) >= 50 else prices[-1]

        # Calculate MACD
        macd = calculate_macd(prices) if len(prices) >= 26 else 0

        # Calculate support and resistance levels
        support_level, resistance_level = calculate_support_resistance(prices)

        # Calculate average volume
        avg_volume_10d = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volumes[-1]

        return {
            "rsi_14": rsi,
            "macd": macd,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "support_level": support_level,
            "resistance_level": resistance_level,
            "average_volume_10d": avg_volume_10d,
        }

    except Exception as e:
        logger.warning(f"Failed to calculate technical indicators for {symbol}: {e}")
        traceback.format_exc()
        return {
            "rsi_14": 50,
            "macd": 0,
            "ema_20": 0,
            "ema_50": 0,
            "support_level": 0,
            "resistance_level": 0,
            "average_volume_10d": 0,
        }


def calculate_rsi(prices, period=14):
    """Calculate the Relative Strength Index"""
    if len(prices) <= period:
        return 50  # Default to neutral if not enough data

    # Calculate price changes
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Separate gains and losses
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [abs(delta) if delta < 0 else 0 for delta in deltas]

    # Calculate average gain and loss
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100  # Prevent division by zero

    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return prices[-1]

    # Start with SMA for the first EMA value
    ema = sum(prices[:period]) / period

    # Multiplier for weighting the EMA
    multiplier = 2 / (period + 1)

    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return round(ema, 2)


def calculate_macd(prices):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    if len(prices) < 26:
        return 0

    # Calculate 12-day EMA
    ema_12 = calculate_ema(prices, 12)

    # Calculate 26-day EMA
    ema_26 = calculate_ema(prices, 26)

    # Calculate MACD line
    macd_line = ema_12 - ema_26

    return round(macd_line, 2)


def calculate_support_resistance(prices):
    """Calculate basic support and resistance levels"""
    if not prices or len(prices) < 7:
        return 0, 0

    # Get recent price range
    recent_prices = prices[-30:] if len(prices) >= 30 else prices

    # Simplistic approach - use recent lows/highs
    lowest_price = min(recent_prices)
    highest_price = max(recent_prices)
    current_price = prices[-1]

    # Support levels - look for recent lows below current price
    support_candidates = [p for p in recent_prices if p < current_price]
    support_level = max(support_candidates) if support_candidates else lowest_price

    # Resistance levels - look for recent highs above current price
    resistance_candidates = [p for p in recent_prices if p > current_price]
    resistance_level = (
        min(resistance_candidates) if resistance_candidates else highest_price
    )

    return round(support_level, 2), round(resistance_level, 2)


def calculate_average_correlation(correlation_matrix):
    """Calculate average correlation from a correlation matrix"""
    if not correlation_matrix or not isinstance(correlation_matrix, dict):
        return 0

    total_correlation = 0
    pair_count = 0

    for symbol1, correlations in correlation_matrix.items():
        if isinstance(correlations, dict):
            for symbol2, corr_value in correlations.items():
                if symbol1 != symbol2 and isinstance(corr_value, (int, float)):
                    total_correlation += abs(
                        corr_value
                    )  # Use absolute value for correlation strength
                    pair_count += 1

    if pair_count == 0:
        return 0

    return round(total_correlation / pair_count, 2)


def identify_market_regime(market_data):
    """Identify the current market regime based on various indicators"""
    market_condition = market_data.get("market_condition", "sideways")
    fear_greed = market_data.get("fear_greed_index", 50)
    btc_volatility = market_data.get("btc_volatility", 50)

    # Market regime classification
    if market_condition == "bull_market" and fear_greed > 70:
        regime = "euphoria"
    elif market_condition == "bull_market" and fear_greed > 50:
        regime = "optimism"
    elif market_condition == "bear_market" and fear_greed < 30:
        regime = "fear"
    elif market_condition == "bear_market" and fear_greed < 20:
        regime = "capitulation"
    elif market_condition == "sideways" and btc_volatility < 30:
        regime = "accumulation"
    elif market_condition == "sideways" and btc_volatility > 70:
        regime = "distribution"
    else:
        regime = "neutral"

    # Additional context for the regime
    regime_context = {
        "euphoria": "Market showing signs of excessive optimism, consider defensive positioning",
        "optimism": "Bullish market with healthy sentiment, maintain balanced exposure",
        "fear": "Bearish market with pessimistic sentiment, potential opportunities emerging",
        "capitulation": "Extreme bearish sentiment may signal approaching market bottom",
        "accumulation": "Range-bound market with declining volatility, potential base building",
        "distribution": "Range-bound market with high volatility, possible trend change ahead",
        "neutral": "Mixed signals, maintain normal positioning",
    }

    return {
        "regime": regime,
        "description": regime_context.get(regime, ""),
        "indicators": {
            "market_condition": market_condition,
            "fear_greed": fear_greed,
            "volatility": btc_volatility,
        },
    }


def analyze_seasonal_factors():
    """Analyze seasonal patterns that might affect the market"""
    current_date = datetime.now()
    month = current_date.month
    day = current_date.day

    # Check for known seasonal patterns
    seasonal_factors = []

    # Q1 tax season effects
    if month in [3, 4]:
        seasonal_factors.append(
            {
                "factor": "Tax season",
                "impact": "Potential selling pressure as investors liquidate for tax payments",
                "relevance": "MEDIUM",
            }
        )

    # End of quarter effects
    if month in [3, 6, 9, 12] and day > 25:
        seasonal_factors.append(
            {
                "factor": "Quarter-end rebalancing",
                "impact": "Institutional portfolio adjustments may increase volatility",
                "relevance": "MEDIUM",
            }
        )

    # Historical "Uptober" pattern
    if month == 10:
        seasonal_factors.append(
            {
                "factor": "Historical October strength",
                "impact": "Bitcoin has historically performed well in October",
                "relevance": "LOW",
            }
        )

    # Historical Q4 bull runs
    if month in [11, 12]:
        seasonal_factors.append(
            {
                "factor": "Q4 historical performance",
                "impact": "Q4 has historically been strong for crypto markets",
                "relevance": "MEDIUM",
            }
        )

    # January effect
    if month == 1:
        seasonal_factors.append(
            {
                "factor": "January effect",
                "impact": "New year portfolio positioning and investment flows",
                "relevance": "MEDIUM",
            }
        )

    # Return seasonal factors or a default message
    if not seasonal_factors:
        return {
            "message": "No significant seasonal factors identified for the current period",
            "relevance": "LOW",
        }

    return {
        "factors": seasonal_factors,
        "current_date": current_date.strftime("%Y-%m-%d"),
    }


def calculate_market_risk_metrics(market_data):
    """Calculate various risk metrics for the current market"""
    fear_greed = market_data.get("fear_greed_index", 50)
    btc_volatility = market_data.get("btc_volatility", 50)
    market_condition = market_data.get("market_condition", "sideways")

    # Calculate market risk score (0-100)
    # Higher score = higher risk
    if market_condition == "bull_market":
        base_risk = 40
    elif market_condition == "bear_market":
        base_risk = 70
    else:  # sideways
        base_risk = 50

    # Adjust risk based on fear/greed
    if fear_greed > 75:  # Extreme greed
        sentiment_risk = 30
    elif fear_greed > 60:  # Greed
        sentiment_risk = 20
    elif fear_greed < 25:  # Extreme fear
        sentiment_risk = -10
    elif fear_greed < 40:  # Fear
        sentiment_risk = -5
    else:  # Neutral
        sentiment_risk = 0

    # Adjust risk based on volatility
    if btc_volatility > 75:
        volatility_risk = 20
    elif btc_volatility > 60:
        volatility_risk = 10
    elif btc_volatility < 25:
        volatility_risk = -10
    elif btc_volatility < 40:
        volatility_risk = -5
    else:
        volatility_risk = 0

    # Calculate final risk score, capped between 0-100
    risk_score = min(max(base_risk + sentiment_risk + volatility_risk, 0), 100)

    # Determine risk level
    if risk_score >= 75:
        risk_level = "VERY_HIGH"
    elif risk_score >= 60:
        risk_level = "HIGH"
    elif risk_score >= 40:
        risk_level = "MODERATE"
    elif risk_score >= 25:
        risk_level = "LOW"
    else:
        risk_level = "VERY_LOW"

    # Generate risk recommendations
    if risk_level in ["VERY_HIGH", "HIGH"]:
        recommendations = [
            "Consider reducing position sizes",
            "Tighten stop losses",
            "Maintain higher cash reserves",
            "Focus on capital preservation",
        ]
    elif risk_level == "MODERATE":
        recommendations = [
            "Balanced approach to risk",
            "Normal position sizing",
            "Mix of conservative and growth assets",
        ]
    else:
        recommendations = [
            "Potential opportunity to increase exposure",
            "Consider deploying additional capital",
            "Look for assets near support levels",
        ]

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "contributing_factors": {
            "market_condition": market_condition,
            "sentiment": fear_greed,
            "volatility": btc_volatility,
        },
        "recommendations": recommendations,
    }


def get_asset_recommendation(
    asset_trend,
    market_condition,
    rsi,
    distance_to_support,
    distance_to_resistance,
    trend_strength,
):
    """Generate asset-specific recommendation based on comprehensive analysis"""

    # Base recommendation on trend alignment with market
    if asset_trend == "strong_bullish" and market_condition == "bull_market":
        if rsi > 70:
            return "Consider taking partial profits as asset approaches overbought conditions"
        else:
            return "Hold position with trailing stop-loss, consider adding on healthy pullbacks"

    elif asset_trend == "strong_bullish" and market_condition != "bull_market":
        return "Asset showing significant strength against market trend, monitor closely and consider taking profits if RSI exceeds 75"

    elif asset_trend == "bullish" and market_condition == "bull_market":
        if distance_to_resistance < 5:  # Close to resistance
            return "Approaching resistance level, consider taking partial profits or tightening stop-loss"
        else:
            return "Hold position and consider adding on dips that maintain bullish structure"

    elif asset_trend == "strong_bearish" and market_condition == "bear_market":
        if rsi < 30:
            return "Approaching oversold conditions, consider covering short positions or small speculative long with tight stop-loss"
        else:
            return "Consider reducing exposure or implementing hedging strategies as downtrend continues"

    elif asset_trend == "bearish" and market_condition != "bear_market":
        return "Asset underperforming broader market, evaluate position fundamentals and consider reducing exposure on relief rallies"

    elif asset_trend == "mixed" or asset_trend == "sideways":
        if distance_to_support < 5:  # Close to support
            return "Near support level, potential for accumulation if support holds with increasing volume"
        elif distance_to_resistance < 5:  # Close to resistance
            return "Near resistance level, watch for rejection or breakout confirmation with volume"
        else:
            return "Range-bound price action, monitor key support/resistance levels for breakout signals"

    elif trend_strength == "unconfirmed":
        return "Trend lacks volume confirmation, exercise caution with position sizing and wait for stronger signals"

    else:
        return "Maintain current position and monitor for change in market conditions"


def generate_market_insights(market_data):
    """Generate market insights based on current conditions with improved logic"""
    insights = []

    # Market condition insights
    market_condition = market_data.get("market_condition", "sideways")
    fear_greed_index = market_data.get("fear_greed_index", 50)
    fear_greed_classification = market_data.get("fear_greed_classification", "neutral")
    btc_trend = market_data.get("btc_trend")

    # Generate insights based on Fear & Greed Index and its trend
    if fear_greed_index is not None:
        if fear_greed_index >= 80:
            insights.append(
                {
                    "type": "WARNING",
                    "importance": "HIGH",
                    "message": f"Extreme market greed detected (Fear & Greed Index: {fear_greed_index}). Historical data suggests increased correction risk in the coming weeks.",
                    "recommendation": "Consider profit-taking strategies and reducing exposure to high-beta assets.",
                }
            )
        elif fear_greed_index >= 70:
            insights.append(
                {
                    "type": "CAUTION",
                    "importance": "MEDIUM",
                    "message": f"Elevated market greed (Fear & Greed Index: {fear_greed_index}). Market approaching potential overvaluation territory.",
                    "recommendation": "Consider trimming positions that have seen substantial gains.",
                }
            )
        elif fear_greed_index <= 20:
            insights.append(
                {
                    "type": "OPPORTUNITY",
                    "importance": "HIGH",
                    "message": f"Extreme market fear detected (Fear & Greed Index: {fear_greed_index}). Historical data suggests potential buying opportunities in quality assets.",
                    "recommendation": "Consider gradual capital deployment into fundamentally strong assets.",
                }
            )
        elif fear_greed_index <= 30:
            insights.append(
                {
                    "type": "OPPORTUNITY",
                    "importance": "MEDIUM",
                    "message": f"Elevated fear levels (Fear & Greed Index: {fear_greed_index}). Market sentiment potentially overly pessimistic.",
                    "recommendation": "Watch for stabilization signals to initiate selective positions.",
                }
            )

    # Generate insights based on market condition with improved context
    if market_condition == "bull_market":
        insights.append(
            {
                "type": "INFO",
                "importance": "HIGH",
                "message": "Bull market conditions confirmed by multiple indicators. Focus on managing risk as assets appreciate.",
                "recommendation": "Implement profit-taking strategies at psychological resistance levels while maintaining core positions.",
            }
        )
    elif market_condition == "bear_market":
        insights.append(
            {
                "type": "INFO",
                "importance": "HIGH",
                "message": "Bear market conditions prevail across multiple timeframes. Focus on capital preservation and selective accumulation.",
                "recommendation": "Maintain higher cash allocation, consider stablecoin yield strategies, and build watchlists of quality assets for future accumulation.",
            }
        )
    elif market_condition == "sideways":
        insights.append(
            {
                "type": "INFO",
                "importance": "MEDIUM",
                "message": "Market in consolidation phase with no clear directional bias. Range-bound trading strategies may be effective.",
                "recommendation": "Focus on assets with strong fundamentals showing relative strength, consider reduced position sizes.",
            }
        )

    # BTC dominance insights with more nuanced thresholds
    btc_dominance = market_data.get("market_metrics", {}).get("btc_dominance")
    if btc_dominance is not None:
        if btc_dominance > 55:
            insights.append(
                {
                    "type": "INFO",
                    "importance": "MEDIUM",
                    "message": f"Elevated Bitcoin dominance ({btc_dominance:.1f}%) suggests capital concentration in Bitcoin over altcoins.",
                    "recommendation": "Exercise caution with small-cap altcoin exposure until dominance stabilizes or decreases.",
                }
            )
        elif btc_dominance < 40:
            insights.append(
                {
                    "type": "INFO",
                    "importance": "MEDIUM",
                    "message": f"Low Bitcoin dominance ({btc_dominance:.1f}%) indicates strong altcoin cycle, historically a late-cycle phenomenon.",
                    "recommendation": "Monitor for potential reversal signals that could indicate cycle maturity.",
                }
            )
        elif btc_dominance < 45 and market_condition == "bull_market":
            insights.append(
                {
                    "type": "OPPORTUNITY",
                    "importance": "MEDIUM",
                    "message": f"Decreasing Bitcoin dominance ({btc_dominance:.1f}%) in bull market suggests ongoing capital rotation to altcoins.",
                    "recommendation": "Consider strategic exposure to mid-cap altcoins with strong fundamentals and use cases.",
                }
            )

    # Market cap change insights with more context
    market_cap_change = market_data.get("market_metrics", {}).get(
        "market_cap_change_24h"
    )
    total_market_cap = market_data.get("market_metrics", {}).get("total_market_cap")
    if market_cap_change is not None:
        if market_cap_change > 5:
            insights.append(
                {
                    "type": "POSITIVE",
                    "importance": "MEDIUM",
                    "message": f"Strong market growth with {market_cap_change:.1f}% increase in total market cap over 24h.",
                    "context": f"Total market capitalization now at {format_market_cap(total_market_cap)}.",
                    "recommendation": "Monitor for continuation pattern in price action with supporting volume.",
                }
            )
        elif market_cap_change < -5:
            insights.append(
                {
                    "type": "NEGATIVE",
                    "importance": "MEDIUM",
                    "message": f"Market under pressure with {abs(market_cap_change):.1f}% decrease in total market cap over 24h.",
                    "context": f"Total market capitalization now at {format_market_cap(total_market_cap)}.",
                    "recommendation": "Watch key support levels for potential stabilization or further breakdown.",
                }
            )

    # Volatility insights with improved analysis
    btc_volatility = market_data.get("btc_volatility")
    if btc_volatility is not None:
        if btc_volatility > 75:
            insights.append(
                {
                    "type": "WARNING",
                    "importance": "HIGH",
                    "message": f"Unusually high market volatility detected ({btc_volatility}/100). Risk of sharp price movements in either direction.",
                    "recommendation": "Reduce position sizes, widen stop-losses, and consider hedging strategies for large positions.",
                }
            )
        elif btc_volatility < 25 and btc_volatility > 0:
            insights.append(
                {
                    "type": "INFO",
                    "importance": "MEDIUM",
                    "message": f"Market volatility at multi-month lows ({btc_volatility}/100). Historical patterns suggest potential for volatility expansion soon.",
                    "recommendation": "Prepare for potential breakout by identifying key technical levels and having capital ready to deploy.",
                }
            )

    # Asset-specific insights with improved classification
    if "asset_analysis" in market_data and isinstance(
        market_data["asset_analysis"], dict
    ):
        outperformers = []
        underperformers = []
        overbought_assets = []
        oversold_assets = []

        for symbol, data in market_data["asset_analysis"].items():
            if "error" in data:
                continue

            if data.get("sentiment") in ["strongly_outperforming", "outperforming"]:
                outperformers.append(symbol)
            elif data.get("sentiment") in [
                "strongly_underperforming",
                "underperforming",
            ]:
                underperformers.append(symbol)

            # Check technical indicators for overbought/oversold conditions
            if (
                "technical_indicators" in data
                and data["technical_indicators"].get("rsi_signal") == "overbought"
            ):
                overbought_assets.append(symbol)
            elif (
                "technical_indicators" in data
                and data["technical_indicators"].get("rsi_signal") == "oversold"
            ):
                oversold_assets.append(symbol)

        if outperformers:
            insights.append(
                {
                    "type": "POSITIVE",
                    "importance": "MEDIUM",
                    "message": f"Assets outperforming the market: {', '.join(outperformers)}",
                    "recommendation": "Monitor these assets for trend continuation signals and potential leadership roles.",
                }
            )

        if underperformers:
            insights.append(
                {
                    "type": "WARNING",
                    "importance": "MEDIUM",
                    "message": f"Assets underperforming the market: {', '.join(underperformers)}",
                    "recommendation": "Evaluate fundamentals for these assets and consider position sizing adjustments.",
                }
            )

        if overbought_assets:
            insights.append(
                {
                    "type": "CAUTION",
                    "importance": "MEDIUM",
                    "message": f"Potentially overbought assets: {', '.join(overbought_assets)}",
                    "recommendation": "Consider taking partial profits or tightening stop-losses on these positions.",
                }
            )

        if oversold_assets:
            insights.append(
                {
                    "type": "OPPORTUNITY",
                    "importance": "MEDIUM",
                    "message": f"Potentially oversold assets: {', '.join(oversold_assets)}",
                    "recommendation": "Watch for reversal patterns with volume confirmation for potential entry points.",
                }
            )

    # Correlation insights with improved interpretation
    if "asset_correlations" in market_data and isinstance(
        market_data["asset_correlations"], dict
    ):
        high_correlations = []
        low_correlations = []
        negative_correlations = []

        for symbol1, correlations in market_data["asset_correlations"].items():
            if isinstance(correlations, dict):
                for symbol2, correlation in correlations.items():
                    if symbol1 != symbol2:
                        pair = f"{symbol1}-{symbol2}"
                        if correlation > 0.8:
                            high_correlations.append((pair, correlation))
                        elif correlation < 0.2 and correlation >= 0:
                            low_correlations.append((pair, correlation))
                        elif correlation < 0:
                            negative_correlations.append((pair, correlation))

        if high_correlations:
            top_high = sorted(high_correlations, key=lambda x: x[1], reverse=True)[:3]
            insights.append(
                {
                    "type": "INFO",
                    "importance": "MEDIUM",
                    "message": f"High correlation pairs (reduced diversification benefit): {', '.join([f'{pair} ({corr:.2f})' for pair, corr in top_high])}",
                    "recommendation": "Consider reducing exposure to one asset from each highly correlated pair to improve diversification.",
                }
            )

        if low_correlations:
            top_low = sorted(low_correlations, key=lambda x: x[1])[:3]
            insights.append(
                {
                    "type": "POSITIVE",
                    "importance": "MEDIUM",
                    "message": f"Low correlation pairs (good diversification): {', '.join([f'{pair} ({corr:.2f})' for pair, corr in top_low])}",
                    "recommendation": "These pairings offer strong diversification benefits in your portfolio.",
                }
            )

        if negative_correlations:
            top_negative = sorted(negative_correlations, key=lambda x: x[1])[:3]
            insights.append(
                {
                    "type": "POSITIVE",
                    "importance": "HIGH",
                    "message": f"Negative correlation pairs (excellent hedging): {', '.join([f'{pair} ({corr:.2f})' for pair, corr in top_negative])}",
                    "recommendation": "These pairs can provide effective hedging during market volatility.",
                }
            )

    # Sort insights by importance
    importance_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    insights.sort(
        key=lambda x: importance_rank.get(x.get("importance", "LOW"), 0), reverse=True
    )

    return insights


def format_market_cap(market_cap):
    """Format market cap value to human-readable format"""
    if market_cap is None:
        return "Unknown"

    if market_cap >= 1_000_000_000_000:
        return f"${market_cap / 1_000_000_000_000:.2f}T"
    elif market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.2f}M"
    else:
        return f"${market_cap / 1_000:.2f}K"


@tool
def get_market_opportunities(user_id: str, opportunity_type: str = "ALL") -> Dict:
    """
    Identify market opportunities based on current conditions and portfolio.

    Args:
        user_id (str): User identifier
        opportunity_type (str): Type of opportunities (ALL, DIP_BUYING, PROFIT_TAKING, ARBITRAGE, YIELD, TRENDING)

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

            opportunities = []

            # Analyze market for opportunities
            # Include more comprehensive list of major assets to analyze
            market_conditions = analyze_market_conditions.invoke(
                {
                    "asset_symbols": [
                        "BTC",
                        "ETH",
                        "BNB",
                        "SOL",
                        "XRP",
                        "ADA",
                        "DOT",
                        "MATIC",
                        "AVAX",
                        "LINK",
                    ]
                }
            )

            if (
                isinstance(market_conditions, dict)
                and "asset_analysis" in market_conditions
                and isinstance(market_conditions["asset_analysis"], dict)
            ):
                # Get market context for opportunity assessment
                market_regime = market_conditions.get("market_regime", {}).get(
                    "regime", "neutral"
                )
                fear_greed_index = market_conditions.get("fear_greed_index", 50)
                risk_metrics = market_conditions.get("risk_metrics", {})
                risk_level = risk_metrics.get("risk_level", "MODERATE")

                # DIP buying opportunities with improved criteria
                if opportunity_type in ["ALL", "DIP_BUYING"]:
                    for symbol, asset_data in market_conditions[
                        "asset_analysis"
                    ].items():
                        if "error" in asset_data:
                            continue

                        # Extract relevant metrics
                        price_changes = asset_data.get("price_changes", {})
                        price_change_24h = price_changes.get("24h", 0)
                        price_change_7d = price_changes.get("7d", 0)

                        technical = asset_data.get("technical_indicators", {})
                        rsi = technical.get("rsi_14d", 50)

                        key_levels = asset_data.get("key_levels", {})
                        distance_to_support = key_levels.get("distance_to_support", 15)

                        trends = asset_data.get("trends", {})
                        trend = trends.get("overall", "mixed")

                        volume = asset_data.get("volume", {})
                        volume_signal = volume.get("signal", "neutral")

                        # Improved dip buying criteria
                        is_dip_opportunity = False
                        opportunity_strength = "MEDIUM"
                        reasoning = []

                        # Strong oversold conditions
                        if rsi < 30:
                            is_dip_opportunity = True
                            reasoning.append(f"RSI is oversold at {rsi}")
                            opportunity_strength = "HIGH"

                        # Significant price drop with moderate RSI
                        elif (
                            price_change_24h < -10 and price_change_7d < -5 and rsi < 40
                        ):
                            is_dip_opportunity = True
                            reasoning.append(
                                f"Sharp correction: 24h: {price_change_24h:.1f}%, 7d: {price_change_7d:.1f}% with RSI at {rsi}"
                            )

                        # Near strong support level
                        elif (
                            distance_to_support < 5
                            and trend not in ["strong_bearish"]
                            and rsi < 45
                        ):
                            is_dip_opportunity = True
                            reasoning.append(
                                f"Price near support level ({distance_to_support:.1f}% away)"
                            )

                        # Adjust opportunity strength based on market regime
                        if is_dip_opportunity:
                            # Reduce opportunity strength in bear markets unless extreme oversold
                            if market_regime in ["fear", "capitulation"] and rsi > 25:
                                opportunity_strength = "LOW"

                            # Increase strength in bull markets near support
                            elif (
                                market_regime in ["optimism", "neutral"]
                                and distance_to_support < 3
                            ):
                                opportunity_strength = "HIGH"

                            # Adjust based on volume
                            if volume_signal == "high":
                                reasoning.append("High volume supporting the dip")
                                if opportunity_strength != "HIGH":
                                    opportunity_strength = "MEDIUM"

                            # Get asset category for allocation suggestion
                            asset_category = asset_data.get("asset_category", "mid_cap")

                            # Calculate suggested allocation based on portfolio size and risk
                            total_value = portfolio.get("total_value", 10000)
                            base_allocation = min(
                                total_value * 0.03, 1000
                            )  # Default 3% of portfolio or $1000

                            # Adjust allocation based on opportunity strength and asset category
                            allocation_multiplier = {
                                "HIGH": 1.5,
                                "MEDIUM": 1.0,
                                "LOW": 0.5,
                            }.get(opportunity_strength, 1.0)

                            category_multiplier = {
                                "large_cap": 1.2,
                                "mid_cap": 1.0,
                                "small_cap": 0.7,
                            }.get(asset_category, 1.0)

                            # Final allocation suggestion
                            allocation_suggestion = round(
                                base_allocation
                                * allocation_multiplier
                                * category_multiplier,
                                2,
                            )

                            # Entry strategy based on market conditions
                            if risk_level in ["HIGH", "VERY_HIGH"]:
                                entry_strategy = (
                                    "Gradual entry with 3-4 tranches over 1 week"
                                )
                            else:
                                entry_strategy = (
                                    "Split entry into 2 tranches over 2-3 days"
                                )

                            # Add the opportunity
                            opportunities.append(
                                {
                                    "type": "DIP_BUYING",
                                    "asset": symbol,
                                    "reasoning": ", ".join(reasoning),
                                    "entry_strategy": entry_strategy,
                                    "risk_level": opportunity_strength,
                                    "potential_return": get_potential_return_estimate(
                                        symbol, asset_data
                                    ),
                                    "time_horizon": get_time_horizon_estimate(
                                        symbol, asset_data, market_regime
                                    ),
                                    "allocation_suggestion": allocation_suggestion,
                                    "key_metrics": {
                                        "rsi": rsi,
                                        "price_change_24h": price_change_24h,
                                        "price_change_7d": price_change_7d,
                                        "distance_to_support": distance_to_support,
                                    },
                                    "stop_loss_suggestion": f"{distance_to_support + 2:.1f}% below entry",
                                }
                            )

                # Profit taking opportunities with improved criteria
                if opportunity_type in ["ALL", "PROFIT_TAKING"]:
                    for position in portfolio.get("positions_by_asset", []):
                        symbol = position.get("symbol", "").upper()
                        pnl_percentage = position.get("pnl_percentage", 0)
                        position_value = position.get("total_value", 0)

                        # Skip small or losing positions
                        if position_value < 100 or pnl_percentage <= 5:
                            continue

                        # Get market data for this asset if available
                        asset_data = market_conditions["asset_analysis"].get(symbol, {})

                        is_profit_opportunity = False
                        opportunity_strength = "MEDIUM"
                        reasoning = []
                        exit_strategy = ""

                        # Check profit percentage thresholds
                        if pnl_percentage > 100:
                            is_profit_opportunity = True
                            reasoning.append(
                                f"Significant profit achieved ({pnl_percentage:.1f}%)"
                            )
                            opportunity_strength = "HIGH"
                            exit_strategy = (
                                "Consider taking 50-75% profit to secure gains"
                            )
                        elif pnl_percentage > 50:
                            is_profit_opportunity = True
                            reasoning.append(
                                f"Healthy profit achieved ({pnl_percentage:.1f}%)"
                            )
                            opportunity_strength = "MEDIUM"
                            exit_strategy = "Consider taking 25-50% profit"
                        elif pnl_percentage > 20:
                            # Only flag smaller profits in certain conditions
                            if "technical_indicators" in asset_data:
                                rsi = asset_data["technical_indicators"].get(
                                    "rsi_14d", 50
                                )
                                if rsi > 70:
                                    is_profit_opportunity = True
                                    reasoning.append(
                                        f"Moderate profit ({pnl_percentage:.1f}%) with overbought conditions (RSI: {rsi})"
                                    )
                                    exit_strategy = "Consider taking 15-25% profit"

                        # Check technical signals for profit taking
                        if (
                            "technical_indicators" in asset_data
                            and not is_profit_opportunity
                        ):
                            rsi = asset_data["technical_indicators"].get("rsi_14d", 50)
                            if rsi > 75 and pnl_percentage > 15:
                                is_profit_opportunity = True
                                reasoning.append(
                                    f"Overbought technical conditions (RSI: {rsi})"
                                )
                                exit_strategy = "Consider taking 15-30% profit"

                        # Check proximity to resistance for profit taking
                        if "key_levels" in asset_data and not is_profit_opportunity:
                            distance_to_resistance = asset_data["key_levels"].get(
                                "distance_to_resistance", 20
                            )
                            if distance_to_resistance < 3 and pnl_percentage > 15:
                                is_profit_opportunity = True
                                reasoning.append(
                                    f"Price approaching resistance ({distance_to_resistance:.1f}% away)"
                                )
                                exit_strategy = (
                                    "Consider taking 15-25% profit near resistance"
                                )

                        # Check market regime for profit taking adjustments
                        if is_profit_opportunity:
                            # In euphoria, increase profit taking
                            if market_regime == "euphoria":
                                if opportunity_strength != "HIGH":
                                    opportunity_strength = "HIGH"
                                reasoning.append(
                                    "Market showing signs of excessive optimism"
                                )
                                exit_strategy = exit_strategy.replace(
                                    "25-50%", "40-60%"
                                ).replace("15-25%", "30-40%")

                            # In fear/capitulation, be more selective with profit taking
                            elif (
                                market_regime in ["fear", "capitulation"]
                                and opportunity_strength != "HIGH"
                            ):
                                if pnl_percentage < 50:
                                    is_profit_opportunity = False
                                else:
                                    opportunity_strength = "LOW"
                                    exit_strategy = "Consider taking only 15-20% profit, keeping core position"

                            # Add opportunity if still valid
                            if is_profit_opportunity:
                                opportunities.append(
                                    {
                                        "type": "PROFIT_TAKING",
                                        "asset": symbol,
                                        "current_profit": f"{pnl_percentage:.1f}%",
                                        "position_value": position_value,
                                        "reasoning": ", ".join(reasoning),
                                        "exit_strategy": exit_strategy,
                                        "risk_level": opportunity_strength,
                                        "action": "Take partial profits to lock in gains",
                                        "market_context": {
                                            "asset_trend": asset_data.get(
                                                "trends", {}
                                            ).get("overall", "unknown"),
                                            "market_regime": market_regime,
                                        },
                                    }
                                )

                # Rebalancing opportunities with improved criteria
                if opportunity_type in ["ALL", "REBALANCING"]:
                    from tools.tools_crypto_portfolios_analysis import get_portfolio_allocation

                    current_allocation = get_portfolio_allocation.invoke(
                        {"user_id": user_id, "group_by": "asset"}
                    )

                    if isinstance(current_allocation, list):
                        # Calculate portfolio concentration metrics
                        total_items = len(current_allocation)

                        if total_items > 0:
                            # Check for over-concentrated positions
                            for item in current_allocation:
                                percentage = item.get("percentage", 0)
                                asset_symbol = item.get("group", "")

                                # Skip small allocations
                                if percentage < 5:
                                    continue

                                # Get market data for this asset if available
                                asset_data = market_conditions["asset_analysis"].get(
                                    asset_symbol.upper(), {}
                                )
                                asset_trend = asset_data.get("trends", {}).get(
                                    "overall", "unknown"
                                )

                                # Determine if rebalancing is needed based on allocation percentage
                                is_rebalance_needed = False
                                target_allocation = 0
                                reasoning = []

                                # Handle extreme concentration
                                if percentage > 40:
                                    is_rebalance_needed = True
                                    reasoning.append(
                                        f"Extremely concentrated position ({percentage:.1f}% of portfolio)"
                                    )
                                    target_allocation = 25
                                # Handle significant concentration
                                elif percentage > 30:
                                    is_rebalance_needed = True
                                    reasoning.append(
                                        f"Highly concentrated position ({percentage:.1f}% of portfolio)"
                                    )
                                    target_allocation = 20
                                # Handle moderate concentration with negative trend
                                elif percentage > 20 and asset_trend in [
                                    "bearish",
                                    "strong_bearish",
                                ]:
                                    is_rebalance_needed = True
                                    reasoning.append(
                                        f"Concentrated position ({percentage:.1f}%) with bearish trend"
                                    )
                                    target_allocation = 15

                                # Add context based on market regime
                                if is_rebalance_needed:
                                    if market_regime in ["euphoria", "distribution"]:
                                        reasoning.append(
                                            "Market showing signs of excessive optimism or distribution"
                                        )
                                        target_allocation -= (
                                            5  # Reduce target allocation further
                                        )

                                    # Calculate amount to rebalance
                                    portfolio_value = portfolio.get("total_value", 0)
                                    current_value = (percentage / 100) * portfolio_value
                                    target_value = (
                                        target_allocation / 100
                                    ) * portfolio_value
                                    rebalance_amount = current_value - target_value

                                    # Risk level based on the concentration and market conditions
                                    risk_level = "MEDIUM"
                                    if percentage > 40 or market_regime in [
                                        "euphoria",
                                        "distribution",
                                    ]:
                                        risk_level = "HIGH"
                                    elif percentage < 25:
                                        risk_level = "LOW"

                                    opportunities.append(
                                        {
                                            "type": "REBALANCING",
                                            "asset": asset_symbol,
                                            "current_allocation": f"{percentage:.1f}%",
                                            "target_allocation": f"{target_allocation:.1f}%",
                                            "rebalance_amount": round(
                                                rebalance_amount, 2
                                            ),
                                            "reasoning": ", ".join(reasoning),
                                            "action": f"Reduce allocation from {percentage:.1f}% to {target_allocation:.1f}%",
                                            "risk_level": risk_level,
                                            "benefit": "Improved diversification and risk management",
                                            "reinvestment_suggestion": "Reallocate to underweight quality assets or stablecoins",
                                        }
                                    )

                            # Check for portfolio diversification opportunities
                            if (
                                "asset_correlations" in market_conditions
                                and total_items >= 3
                            ):
                                avg_correlation = market_conditions.get(
                                    "portfolio_metrics", {}
                                ).get("average_correlation", 0.5)

                                if avg_correlation > 0.7:
                                    # Find highly correlated pairs to suggest diversification
                                    high_correlation_pairs = []

                                    for symbol1, correlations in market_conditions[
                                        "asset_correlations"
                                    ].items():
                                        if isinstance(correlations, dict):
                                            for (
                                                symbol2,
                                                correlation,
                                            ) in correlations.items():
                                                if (
                                                    symbol1 != symbol2
                                                    and correlation > 0.8
                                                ):
                                                    high_correlation_pairs.append(
                                                        (symbol1, symbol2, correlation)
                                                    )

                                    if high_correlation_pairs:
                                        # Sort by highest correlation
                                        high_correlation_pairs.sort(
                                            key=lambda x: x[2], reverse=True
                                        )
                                        top_pairs = high_correlation_pairs[
                                            :2
                                        ]  # Top 2 most correlated pairs

                                        for symbol1, symbol2, correlation in top_pairs:
                                            # Find which one to reduce based on performance or allocation
                                            symbol1_allocation = next(
                                                (
                                                    item.get("percentage", 0)
                                                    for item in current_allocation
                                                    if item.get("group", "") == symbol1
                                                ),
                                                0,
                                            )
                                            symbol2_allocation = next(
                                                (
                                                    item.get("percentage", 0)
                                                    for item in current_allocation
                                                    if item.get("group", "") == symbol2
                                                ),
                                                0,
                                            )

                                            # Default to reducing the higher allocated one
                                            reduce_symbol = (
                                                symbol1
                                                if symbol1_allocation
                                                > symbol2_allocation
                                                else symbol2
                                            )
                                            keep_symbol = (
                                                symbol2
                                                if reduce_symbol == symbol1
                                                else symbol1
                                            )

                                            opportunities.append(
                                                {
                                                    "type": "DIVERSIFICATION",
                                                    "correlated_assets": f"{symbol1}-{symbol2}",
                                                    "correlation": f"{correlation:.2f}",
                                                    "reasoning": f"High correlation ({correlation:.2f}) reduces diversification benefit",
                                                    "action": f"Consider reducing {reduce_symbol} while maintaining {keep_symbol}",
                                                    "risk_level": "MEDIUM",
                                                    "benefit": "Improved portfolio diversification and risk-adjusted returns",
                                                    "alternative_suggestions": get_diversification_alternatives(
                                                        market_conditions
                                                    ),
                                                }
                                            )

                # Yield opportunities with improved analysis
                if opportunity_type in ["ALL", "YIELD"]:
                    # Calculate total stablecoin value with improved detection
                    stablecoin_positions = [
                        p
                        for p in portfolio.get("positions_by_asset", [])
                        if any(
                            stable in p.get("symbol", "").upper()
                            for stable in [
                                "USDT",
                                "USDC",
                                "DAI",
                                "BUSD",
                                "TUSD",
                                "USDP",
                                "USDD",
                                "FRAX",
                            ]
                        )
                    ]

                    stablecoin_value = sum(
                        p.get("total_value", 0) for p in stablecoin_positions
                    )
                    stablecoin_breakdown = {
                        p.get("symbol", "Unknown"): p.get("total_value", 0)
                        for p in stablecoin_positions
                    }

                    # Include idle cash in regular account as potential yield opportunity
                    idle_cash = portfolio.get("cash_balance", 0)
                    if idle_cash > 0:
                        stablecoin_value += idle_cash
                        stablecoin_breakdown["Cash"] = idle_cash

                    if (
                        stablecoin_value > 500
                    ):  # Minimum threshold for meaningful yield strategies
                        # Get current DeFi yield rates from a theoretical API or service
                        # In a real implementation, this would call an external API
                        current_yield_rates = get_current_yield_rates()

                        # Generate yield opportunity based on amount and market conditions
                        yield_opportunity = {
                            "type": "YIELD",
                            "asset_type": "Stablecoins",
                            "total_value": stablecoin_value,
                            "breakdown": stablecoin_breakdown,
                            "reasoning": f"{stablecoin_value:.2f} in stablecoins can be deployed to generate yield",
                            "risk_level": (
                                "LOW"
                                if market_regime not in ["fear", "capitulation"]
                                else "VERY_LOW"
                            ),
                            "platforms": [],
                        }

                        # Add platform recommendations based on current rates
                        # Sort platforms by risk-adjusted yield (yield / risk factor)
                        risk_adjusted_platforms = []
                        for platform in current_yield_rates:
                            risk_factor = {
                                "VERY_LOW": 0.8,
                                "LOW": 1.0,
                                "MEDIUM": 1.5,
                                "HIGH": 2.5,
                                "VERY_HIGH": 4.0,
                            }.get(platform.get("risk", "MEDIUM"), 1.0)

                            risk_adjusted_yield = platform.get("apy", 0) / risk_factor
                            risk_adjusted_platforms.append(
                                (platform, risk_adjusted_yield)
                            )

                        # Sort by risk-adjusted yield
                        risk_adjusted_platforms.sort(key=lambda x: x[1], reverse=True)

                        # Add top platforms
                        for platform, _ in risk_adjusted_platforms[
                            :5
                        ]:  # Top 5 platforms
                            yield_opportunity["platforms"].append(platform)

                        # Add allocation recommendations
                        if market_regime in ["fear", "capitulation"]:
                            # More conservative in fearful markets
                            yield_opportunity["recommended_allocation"] = (
                                stablecoin_value * 0.5
                            )
                            yield_opportunity["allocation_strategy"] = (
                                "Conservative deployment due to market uncertainty"
                            )
                        else:
                            # More aggressive in normal/bullish markets
                            yield_opportunity["recommended_allocation"] = (
                                stablecoin_value * 0.7
                            )
                            yield_opportunity["allocation_strategy"] = (
                                "Standard deployment across recommended platforms"
                            )

                        # Add action steps
                        yield_opportunity["action"] = (
                            "Deploy capital to DeFi protocols for passive income"
                        )
                        yield_opportunity["implementation_steps"] = [
                            "Start with smaller allocations to test each platform",
                            "Diversify across at least 3 different protocols",
                            "Monitor protocol health indicators weekly",
                            "Set calendar reminders for fixed-term deposits",
                        ]

                        opportunities.append(yield_opportunity)

                # Trending assets opportunities (new category)
                if opportunity_type in ["ALL", "TRENDING"]:
                    # Identify trending assets with strong momentum
                    trending_assets = []

                    for symbol, asset_data in market_conditions[
                        "asset_analysis"
                    ].items():
                        if "error" in asset_data:
                            continue

                        # Extract momentum indicators
                        price_changes = asset_data.get("price_changes", {})
                        price_change_24h = price_changes.get("24h", 0)
                        price_change_7d = price_changes.get("7d", 0)

                        volume = asset_data.get("volume", {})
                        volume_signal = volume.get("signal", "neutral")
                        volume_to_mcap = volume.get("volume_to_mcap", 0)

                        trends = asset_data.get("trends", {})
                        trend = trends.get("overall", "mixed")
                        trend_strength = trends.get("strength", "unconfirmed")

                        # Criteria for trending assets
                        is_trending = False
                        trend_strength_score = "MEDIUM"
                        reasoning = []

                        # Strong uptrend with volume confirmation
                        if (
                            trend in ["strong_bullish", "bullish"]
                            and volume_signal == "high"
                        ):
                            is_trending = True
                            reasoning.append(f"Strong uptrend with high volume")
                            if trend == "strong_bullish":
                                trend_strength_score = "HIGH"

                        # Significant recent momentum
                        elif price_change_24h > 8 and price_change_7d > 15:
                            is_trending = True
                            reasoning.append(
                                f"Strong momentum: 24h: +{price_change_24h:.1f}%, 7d: +{price_change_7d:.1f}%"
                            )
                            if price_change_24h > 15 and price_change_7d > 30:
                                trend_strength_score = "HIGH"

                        # High relative volume indicating increased interest
                        elif volume_to_mcap > 0.2 and price_change_24h > 5:
                            is_trending = True
                            reasoning.append(
                                f"High trading volume relative to market cap with positive price action"
                            )

                        # Add trending asset if criteria met
                        if is_trending:
                            # Calculate risk level based on asset category and volatility
                            asset_category = asset_data.get("asset_category", "mid_cap")
                            risk_level = {
                                "large_cap": "MEDIUM",
                                "mid_cap": "HIGH",
                                "small_cap": "VERY_HIGH",
                            }.get(asset_category, "HIGH")

                            # Calculate suitable position size
                            total_value = portfolio.get("total_value", 10000)

                            # More conservative sizing for trending assets
                            base_allocation = min(
                                total_value * 0.02, 500
                            )  # Default 2% of portfolio or $500

                            # Adjust allocation based on market regime
                            regime_multiplier = {
                                "euphoria": 0.5,  # Reduce size in euphoric markets
                                "optimism": 0.8,
                                "neutral": 1.0,
                                "accumulation": 1.2,
                                "fear": 0.7,
                                "capitulation": 0.5,
                            }.get(market_regime, 1.0)

                            # Final allocation
                            allocation_suggestion = round(
                                base_allocation * regime_multiplier, 2
                            )

                            # Add the trending opportunity
                            trending_assets.append(
                                {
                                    "type": "TRENDING",
                                    "asset": symbol,
                                    "momentum_metrics": {
                                        "price_change_24h": price_change_24h,
                                        "price_change_7d": price_change_7d,
                                        "volume_to_mcap": volume_to_mcap,
                                    },
                                    "reasoning": ", ".join(reasoning),
                                    "risk_level": risk_level,
                                    "trend_strength": trend_strength_score,
                                    "allocation_suggestion": allocation_suggestion,
                                    "entry_strategy": "Scale in with multiple entries, use 2-3 tranches",
                                    "stop_loss_suggestion": "Use 10-15% stop loss from entry price",
                                    "take_profit_levels": [
                                        {
                                            "level": 1,
                                            "percentage": "15-20%",
                                            "action": "Take 20% of position",
                                        },
                                        {
                                            "level": 2,
                                            "percentage": "40-50%",
                                            "action": "Take another 30% of position",
                                        },
                                        {
                                            "level": 3,
                                            "percentage": "100%+",
                                            "action": "Consider full exit or trailing stop",
                                        },
                                    ],
                                }
                            )

                    # Add top trending assets to opportunities
                    if trending_assets:
                        # Sort by trend strength and momentum
                        def trend_sort_key(item):
                            strength_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                                item.get("trend_strength", "MEDIUM"), 0
                            )
                            momentum = item.get("momentum_metrics", {}).get(
                                "price_change_7d", 0
                            )
                            return (strength_score, momentum)

                        trending_assets.sort(key=trend_sort_key, reverse=True)

                        # Add top trending assets to opportunities
                        max_trending = 3  # Limit to top 3 trending assets
                        for asset in trending_assets[:max_trending]:
                            opportunities.append(asset)

                # Sort opportunities by priority and relevance
                def opportunity_priority_key(item):
                    # Define priority scores for different opportunity types
                    type_priority = {
                        "PROFIT_TAKING": 5,  # Highest priority - secure profits first
                        "REBALANCING": 4,  # High priority - manage risk
                        "DIP_BUYING": 3,  # Medium-high priority - tactical opportunities
                        "TRENDING": 2,  # Medium priority - momentum plays
                        "DIVERSIFICATION": 1,  # Medium-low priority - strategic adjustments
                        "YIELD": 0,  # Lower priority - ongoing optimization
                    }.get(item.get("type", ""), 0)

                    # Within each type, sort by risk level and other factors
                    risk_priority = {
                        "VERY_HIGH": 4,
                        "HIGH": 3,
                        "MEDIUM": 2,
                        "LOW": 1,
                        "VERY_LOW": 0,
                    }.get(item.get("risk_level", "MEDIUM"), 2)

                    return (type_priority, risk_priority)

                # Sort opportunities by priority
                opportunities.sort(key=opportunity_priority_key, reverse=True)

                # Add market context to response
                market_context = {
                    "overall_trend": market_conditions.get(
                        "market_condition", "unknown"
                    ),
                    "market_regime": market_regime,
                    "fear_greed_index": fear_greed_index,
                    "risk_level": risk_level,
                    "btc_dominance": market_conditions.get("market_metrics", {}).get(
                        "btc_dominance", 0
                    ),
                    "market_insights": summarize_market_insights(
                        market_conditions.get("market_insights", [])
                    ),
                }

                # Add portfolio context to response
                portfolio_context = {
                    "total_value": portfolio.get("total_value", 0),
                    "cash_available": (
                        stablecoin_value if "stablecoin_value" in locals() else 0
                    ),
                    "current_positions": len(portfolio.get("positions_by_asset", [])),
                    "average_correlation": market_conditions.get(
                        "portfolio_metrics", {}
                    ).get("average_correlation", 0),
                    "diversification_score": market_conditions.get(
                        "portfolio_metrics", {}
                    ).get("diversification_score", 0),
                }

                return {
                    "opportunities": opportunities,
                    "opportunity_count": len(opportunities),
                    "market_context": market_context,
                    "portfolio_context": portfolio_context,
                    "generated_at": datetime.utcnow().isoformat(),
                    "seasonal_factors": market_conditions.get("seasonal_factors", {}),
                }

            else:
                return {
                    "error": "Failed to analyze market conditions",
                    "opportunities": [],
                    "generated_at": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Exception:{e}\n{traceback.format_exc()}")
            traceback.format_exc()
            return {"error": f"Failed to get market opportunities: {str(e)}"}

    return _get_market_opportunities(user_id, opportunity_type)


def get_current_yield_rates():
    """Get current DeFi yield rates from various platforms

    In a real implementation, this would call APIs for current rates.
    For this example, we'll return realistic but static data.
    """
    # Current date for reference in the response
    current_date = datetime.now().strftime("%Y-%m-%d")

    return [
        {
            "name": "Aave",
            "apy": 3.8,
            "token_types": ["USDC", "USDT", "DAI"],
            "risk": "LOW",
            "liquidity": "HIGH",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Compound",
            "apy": 3.2,
            "token_types": ["USDC", "USDT", "DAI"],
            "risk": "LOW",
            "liquidity": "HIGH",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Curve",
            "apy": 4.5,
            "token_types": ["3pool (USDC/USDT/DAI)"],
            "risk": "MEDIUM",
            "liquidity": "HIGH",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Convex",
            "apy": 5.8,
            "token_types": ["Curve LP tokens"],
            "risk": "MEDIUM",
            "liquidity": "MEDIUM",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Yearn Finance",
            "apy": 6.2,
            "token_types": ["USDC", "USDT", "DAI"],
            "risk": "MEDIUM",
            "liquidity": "MEDIUM",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Binance Earn",
            "apy": 5.0,
            "token_types": ["USDT", "USDC", "BUSD"],
            "risk": "LOW",
            "liquidity": "MEDIUM",
            "min_lockup": "30 days (for highest rates)",
            "updated_at": current_date,
        },
        {
            "name": "dYdX",
            "apy": 2.8,
            "token_types": ["USDC"],
            "risk": "LOW",
            "liquidity": "HIGH",
            "min_lockup": "None",
            "updated_at": current_date,
        },
        {
            "name": "Anchor Protocol",
            "apy": 7.5,
            "token_types": ["UST"],
            "risk": "HIGH",
            "liquidity": "MEDIUM",
            "min_lockup": "None",
            "updated_at": current_date,
        },
    ]


def get_potential_return_estimate(symbol, asset_data):
    """Estimate potential return ranges based on asset data and technical analysis"""
    # Extract data points we need for the estimate
    trends = asset_data.get("trends", {})
    trend = trends.get("overall", "mixed")

    key_levels = asset_data.get("key_levels", {})
    distance_to_resistance = key_levels.get("distance_to_resistance", 20)
    ath_change_percentage = key_levels.get("ath_change_percentage", -50)

    technical = asset_data.get("technical_indicators", {})
    rsi = technical.get("rsi_14d", 50)

    asset_category = asset_data.get("asset_category", "mid_cap")

    # Base return estimates by asset category (more conservative for large caps)
    base_returns = {
        "large_cap": {"low": 5, "mid": 15, "high": 30},
        "mid_cap": {"low": 10, "mid": 25, "high": 50},
        "small_cap": {"low": 15, "mid": 40, "high": 100},
    }.get(asset_category, {"low": 10, "mid": 25, "high": 50})

    # Adjust based on trend
    trend_multiplier = {
        "strong_bullish": 1.5,
        "bullish": 1.2,
        "mixed": 1.0,
        "bearish": 0.7,
        "strong_bearish": 0.5,
    }.get(trend, 1.0)

    # Adjust based on RSI (more conservative when overbought)
    rsi_multiplier = 1.0
    if rsi > 70:
        rsi_multiplier = 0.8
    elif rsi < 30:
        rsi_multiplier = 1.2

    # Adjust based on distance to ATH (more upside if far from ATH)
    ath_multiplier = 1.0
    if ath_change_percentage < -70:
        ath_multiplier = 1.3
    elif ath_change_percentage < -50:
        ath_multiplier = 1.2
    elif ath_change_percentage < -30:
        ath_multiplier = 1.1
    elif ath_change_percentage > -10:
        ath_multiplier = 0.8

    # Final calculations
    low_return = max(
        base_returns["low"] * trend_multiplier * rsi_multiplier * ath_multiplier, 5
    )
    mid_return = max(
        base_returns["mid"] * trend_multiplier * rsi_multiplier * ath_multiplier, 10
    )
    high_return = max(
        base_returns["high"] * trend_multiplier * rsi_multiplier * ath_multiplier, 15
    )

    # Limit by distance to resistance for near-term estimates
    if distance_to_resistance < 10:
        low_return = min(low_return, distance_to_resistance * 1.2)
        mid_return = min(mid_return, distance_to_resistance * 2)

    # Round to nearest whole number
    low_return = round(low_return)
    mid_return = round(mid_return)
    high_return = round(high_return)

    # Format the return estimate
    return f"{low_return}-{high_return}% (target: {mid_return}%)"


def get_time_horizon_estimate(symbol, asset_data, market_regime):
    """Estimate appropriate time horizon based on asset data and market conditions"""
    # Extract data we need
    trends = asset_data.get("trends", {})
    trend = trends.get("overall", "mixed")

    asset_category = asset_data.get("asset_category", "mid_cap")

    # Base time horizons by asset category
    base_horizons = {
        "large_cap": {
            "short": "2-4 weeks",
            "medium": "1-3 months",
            "long": "3-6 months",
        },
        "mid_cap": {"short": "1-3 weeks", "medium": "3-8 weeks", "long": "2-4 months"},
        "small_cap": {
            "short": "1-2 weeks",
            "medium": "2-6 weeks",
            "long": "1-3 months",
        },
    }.get(
        asset_category,
        {"short": "1-3 weeks", "medium": "1-3 months", "long": "3-6 months"},
    )

    # Select horizon based on trend and market regime
    if trend in ["strong_bullish", "bullish"] and market_regime in [
        "optimism",
        "euphoria",
    ]:
        return base_horizons["short"]  # Shorter timeframes in strong uptrends
    elif trend in ["strong_bearish", "bearish"] or market_regime in [
        "fear",
        "capitulation",
    ]:
        return base_horizons["long"]  # Longer timeframes in downtrends or fear
    else:
        return base_horizons["medium"]  # Medium timeframe for mixed conditions


def get_diversification_alternatives(market_conditions):
    """Generate diversification alternatives based on correlations and market data"""
    alternatives = []

    # Look for assets with low correlations to major assets
    if "asset_correlations" in market_conditions and isinstance(
        market_conditions["asset_correlations"], dict
    ):
        # Find assets with low average correlation to others
        asset_avg_correlations = {}

        for symbol, correlations in market_conditions["asset_correlations"].items():
            if isinstance(correlations, dict):
                correlation_values = [v for k, v in correlations.items() if k != symbol]
                if correlation_values:
                    asset_avg_correlations[symbol] = sum(correlation_values) / len(
                        correlation_values
                    )

        # Sort by lowest average correlation
        low_correlation_assets = sorted(
            asset_avg_correlations.items(), key=lambda x: x[1]
        )[:3]

        for symbol, avg_corr in low_correlation_assets:
            if avg_corr < 0.5:  # Only suggest truly low correlation assets
                alternatives.append(
                    {
                        "asset": symbol,
                        "reason": f"Low average correlation ({avg_corr:.2f}) to other assets",
                    }
                )

    # Add some standard diversifiers if we have few alternatives
    if len(alternatives) < 2:
        standard_diversifiers = [
            {"asset": "PAXG", "reason": "Gold-backed token, traditional safe haven"},
            {"asset": "MKR", "reason": "DeFi governance with different market drivers"},
            {"asset": "ATOM", "reason": "Interoperability focus with unique ecosystem"},
        ]

        for diversifier in standard_diversifiers:
            if diversifier["asset"] not in [a["asset"] for a in alternatives]:
                alternatives.append(diversifier)
                if len(alternatives) >= 3:
                    break

    return alternatives


def summarize_market_insights(insights):
    """Summarize key market insights for the opportunities context"""
    if not insights or not isinstance(insights, list):
        return {"summary": "No significant market insights available"}

    # Categorize insights by type
    warnings = [i for i in insights if i.get("type") == "WARNING"]
    opportunities = [i for i in insights if i.get("type") == "OPPORTUNITY"]
    positive = [i for i in insights if i.get("type") == "POSITIVE"]
    negative = [i for i in insights if i.get("type") == "NEGATIVE"]

    # Create summary counts
    counts = {
        "warnings": len(warnings),
        "opportunities": len(opportunities),
        "positive_signals": len(positive),
        "negative_signals": len(negative),
        "total_insights": len(insights),
    }

    # Extract high importance insights for summary
    high_importance = [i for i in insights if i.get("importance") == "HIGH"]

    # Create summary text
    summary = ""
    if high_importance:
        high_messages = [
            i.get("message", "").split(".")[0] for i in high_importance[:2]
        ]
        summary += " ".join(high_messages) + ". "

    # Add overall sentiment
    if len(positive) > len(negative) + len(warnings):
        summary += "Overall market signals are predominantly positive. "
    elif len(warnings) > len(positive) + len(negative):
        summary += "Multiple warning signals present in current market. "
    elif len(negative) > len(positive):
        summary += "Market showing more negative than positive signals. "
    else:
        summary += (
            "Mixed market signals with balanced positive and negative indicators. "
        )

    return {
        "summary": summary.strip(),
        "counts": counts,
        "key_insights": [i.get("message") for i in high_importance[:3]],
    }


tools = [
    analyze_market_conditions,
    get_market_opportunities,
]
