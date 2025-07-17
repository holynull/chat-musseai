import numpy as np
import requests
import json
from typing import List, Dict, Optional
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

# ========================================
# Enhanced Market Condition Analyzer
# ========================================


def get_dynamic_performance_thresholds(positions, total_cost, total_value):
    """
    Calculate dynamic performance thresholds based on market conditions and portfolio characteristics

    Args:
        positions: List of portfolio positions
        total_cost: Total cost basis
        total_value: Total current value

    Returns:
        dict: Contains thresholds for different performance levels
    """

    # 1. Estimate investment holding period (simplified, should calculate from transaction records)
    estimated_holding_period_months = (
        6  # Default 6 months, should be calculated from actual data
    )

    # 2. Calculate portfolio risk level
    portfolio_risk_level = calculate_portfolio_risk_level(positions, total_value)

    # 3. Estimate market condition (simplified version)
    market_condition = estimate_market_condition(positions)

    # 4. Calculate dynamic thresholds based on above factors
    base_thresholds = {
        "bull_market": {
            "excellent": 30,  # 30% is excellent in bull market
            "good": 15,  # 15% is good
            "neutral": 0,  # 0% is neutral
            "concern": -15,  # -15% needs attention
            "alert": -30,  # -30% needs alert
        },
        "bear_market": {
            "excellent": 0,  # Not losing money is excellent in bear market
            "good": -10,  # -10% is good
            "neutral": -20,  # -20% is neutral
            "concern": -35,  # -35% needs attention
            "alert": -50,  # -50% needs alert
        },
        "sideways": {
            "excellent": 20,  # 20% is excellent in sideways market
            "good": 10,  # 10% is good
            "neutral": -5,  # -5% is neutral
            "concern": -20,  # -20% needs attention
            "alert": -35,  # -35% needs alert
        },
    }

    # Get base thresholds
    thresholds = base_thresholds.get(market_condition, base_thresholds["sideways"])

    # 5. Adjust thresholds based on investment period
    time_adjustment = calculate_time_adjustment(estimated_holding_period_months)

    # 6. Adjust thresholds based on risk level
    risk_adjustment = calculate_risk_adjustment(portfolio_risk_level)

    # Apply adjustments
    adjusted_thresholds = {}
    for level, threshold in thresholds.items():
        adjusted_thresholds[level] = threshold * time_adjustment * risk_adjustment

    return {
        "thresholds": adjusted_thresholds,
        "market_condition": market_condition,
        "portfolio_risk_level": portfolio_risk_level,
        "estimated_holding_period": estimated_holding_period_months,
    }


def calculate_portfolio_risk_level(positions, total_value):
    """
    Calculate portfolio risk level based on asset composition and volatility

    Args:
        positions: List of portfolio positions
        total_value: Total portfolio value

    Returns:
        str: Risk level ('low', 'medium', 'high')
    """
    if not positions or total_value <= 0:
        return "medium"

    # Calculate concentration risk using Herfindahl Index
    concentration_score = 0
    for position in positions:
        weight = position["total_value"] / total_value
        concentration_score += weight**2

    # Calculate asset type risk
    high_risk_assets = ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK"]  # Meme coins
    medium_risk_assets = ["BTC", "ETH", "BNB", "ADA", "DOT"]  # Established crypto
    low_risk_assets = ["USDT", "USDC", "DAI", "BUSD"]  # Stablecoins

    high_risk_value = sum(
        p["total_value"] for p in positions if p["symbol"].upper() in high_risk_assets
    )
    medium_risk_value = sum(
        p["total_value"] for p in positions if p["symbol"].upper() in medium_risk_assets
    )
    low_risk_value = sum(
        p["total_value"] for p in positions if p["symbol"].upper() in low_risk_assets
    )

    high_risk_ratio = high_risk_value / total_value
    medium_risk_ratio = medium_risk_value / total_value
    low_risk_ratio = low_risk_value / total_value

    # Determine risk level
    if concentration_score > 0.6 or high_risk_ratio > 0.5:
        return "high"
    elif concentration_score > 0.3 or high_risk_ratio > 0.2 or medium_risk_ratio < 0.3:
        return "medium"
    else:
        return "low"


def estimate_market_condition(positions):
    """
    Estimate market condition based on portfolio performance patterns

    Args:
        positions: List of portfolio positions

    Returns:
        str: Market condition ('bull_market', 'bear_market', 'sideways')
    """
    if not positions:
        return "sideways"

    # Calculate average PnL percentage across all positions
    pnl_percentages = [
        p.get("pnl_percentage", 0)
        for p in positions
        if p.get("pnl_percentage") is not None
    ]

    if not pnl_percentages:
        return "sideways"

    avg_pnl = sum(pnl_percentages) / len(pnl_percentages)
    positive_count = sum(1 for pnl in pnl_percentages if pnl > 0)
    positive_ratio = positive_count / len(pnl_percentages)

    # Simple market condition estimation
    if avg_pnl > 10 and positive_ratio > 0.6:
        return "bull_market"
    elif avg_pnl < -10 and positive_ratio < 0.4:
        return "bear_market"
    else:
        return "sideways"


def calculate_time_adjustment(holding_period_months):
    """
    Calculate time adjustment factor for performance thresholds

    Args:
        holding_period_months: Estimated holding period in months

    Returns:
        float: Time adjustment factor
    """
    # Annualize the thresholds based on holding period
    if holding_period_months <= 1:
        return 0.3  # Short-term trades should have lower thresholds
    elif holding_period_months <= 3:
        return 0.6  # Medium-term should have moderate thresholds
    elif holding_period_months <= 12:
        return 1.0  # Annual thresholds are baseline
    else:
        return 1.2  # Long-term investments can have higher thresholds


def calculate_risk_adjustment(portfolio_risk_level):
    """
    Calculate risk adjustment factor for performance thresholds

    Args:
        portfolio_risk_level: Portfolio risk level ('low', 'medium', 'high')

    Returns:
        float: Risk adjustment factor
    """
    risk_adjustments = {
        "low": 0.7,  # Lower risk portfolios should have lower return expectations
        "medium": 1.0,  # Medium risk is baseline
        "high": 1.4,  # Higher risk portfolios should have higher return expectations
    }
    return risk_adjustments.get(portfolio_risk_level, 1.0)


def generate_performance_insights(roi, threshold_data):
    """
    Generate performance insights based on dynamic thresholds

    Args:
        roi: Return on investment percentage
        threshold_data: Dictionary containing thresholds and market data

    Returns:
        list: List of insight dictionaries
    """
    insights = []
    thresholds = threshold_data["thresholds"]
    market_condition = threshold_data["market_condition"]

    # Determine performance level
    if roi >= thresholds["excellent"]:
        insights.append(
            {
                "type": "SUCCESS",
                "message": f"Outstanding performance! Portfolio gained {roi:.1f}% in {market_condition.replace('_', ' ')} conditions.",
            }
        )
    elif roi >= thresholds["good"]:
        insights.append(
            {
                "type": "SUCCESS",
                "message": f"Good performance! Portfolio gained {roi:.1f}%, outperforming typical {market_condition.replace('_', ' ')} expectations.",
            }
        )
    elif roi >= thresholds["neutral"]:
        insights.append(
            {
                "type": "INFO",
                "message": f"Neutral performance. Portfolio return of {roi:.1f}% is within expected range for {market_condition.replace('_', ' ')}.",
            }
        )
    elif roi >= thresholds["concern"]:
        insights.append(
            {
                "type": "WARNING",
                "message": f"Below-average performance. Portfolio down {abs(roi):.1f}% in {market_condition.replace('_', ' ')} conditions.",
            }
        )
    else:
        insights.append(
            {
                "type": "ALERT",
                "message": f"Significant underperformance. Portfolio down {abs(roi):.1f}%, consider reviewing strategy for {market_condition.replace('_', ' ')}.",
            }
        )

    return insights


# 修改后的主函数相关部分
@tool
def analyze_portfolio_overview(user_id: str) -> Dict:
    """
    Get a comprehensive portfolio analysis overview including key metrics,
    performance, and risk indicators with dynamic thresholds.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Comprehensive portfolio analysis including:
            - Portfolio value and composition
            - Performance metrics with dynamic thresholds
            - Risk indicators
            - Key insights and alerts
    """
    try:
        with get_db() as db:
            # Get basic portfolio data
            from tools.tools_crypto_portfolios import get_user_portfolio_summary

            portfolio_summary = get_user_portfolio_summary.invoke({"user_id": user_id})

            if (
                portfolio_summary is None
                or isinstance(portfolio_summary, str)
                or (
                    isinstance(portfolio_summary, dict) and "error" in portfolio_summary
                )
            ):
                return {"error": "Failed to retrieve portfolio data"}

            # Calculate additional metrics
            total_value = portfolio_summary.get("total_value", 0)
            total_cost = portfolio_summary.get("total_cost", 0)
            total_pnl = portfolio_summary.get("total_pnl", 0)

            # Calculate volatility (simplified)
            positions = portfolio_summary.get("positions_by_asset", [])

            # Risk metrics
            concentration_score = 0
            if positions and total_value > 0:
                # Calculate Herfindahl Index
                for position in positions:
                    weight = position["total_value"] / total_value
                    concentration_score += weight**2

            # Performance metrics
            roi = (total_pnl / total_cost * 100) if total_cost > 0 else 0

            # === 替换固定阈值的部分 ===
            # Get dynamic thresholds instead of using fixed values
            threshold_data = get_dynamic_performance_thresholds(
                positions, total_cost, total_value
            )

            # Generate insights using dynamic thresholds
            performance_insights = generate_performance_insights(roi, threshold_data)

            # Identify top performers and losers
            top_performers = sorted(
                [p for p in positions if p.get("pnl_percentage", 0) > 0],
                key=lambda x: x.get("pnl_percentage", 0),
                reverse=True,
            )[:3]

            top_losers = sorted(
                [p for p in positions if p.get("pnl_percentage", 0) < 0],
                key=lambda x: x.get("pnl_percentage", 0),
            )[:3]

            # Generate additional insights
            insights = performance_insights.copy()  # Start with performance insights

            # Risk concentration insights
            if concentration_score > 0.5:
                insights.append(
                    {
                        "type": "WARNING",
                        "message": "High concentration risk detected. Portfolio is heavily concentrated in few assets.",
                    }
                )

            # Check for stablecoin allocation
            stablecoin_value = sum(
                p["total_value"]
                for p in positions
                if any(
                    stable in p["symbol"].upper()
                    for stable in ["USDT", "USDC", "DAI", "BUSD"]
                )
            )
            stablecoin_percentage = (
                (stablecoin_value / total_value * 100) if total_value > 0 else 0
            )

            # Dynamic stablecoin allocation advice based on market condition
            market_condition = threshold_data["market_condition"]
            if market_condition == "bull_market" and stablecoin_percentage > 20:
                insights.append(
                    {
                        "type": "INFO",
                        "message": f"High stablecoin allocation ({stablecoin_percentage:.1f}%) in bull market. Consider increasing risk asset exposure.",
                    }
                )
            elif market_condition == "bear_market" and stablecoin_percentage < 10:
                insights.append(
                    {
                        "type": "WARNING",
                        "message": f"Low stablecoin allocation ({stablecoin_percentage:.1f}%) in bear market. Consider defensive positioning.",
                    }
                )
            elif market_condition == "sideways" and stablecoin_percentage < 5:
                insights.append(
                    {
                        "type": "INFO",
                        "message": "Low stablecoin allocation. Consider holding some for stability and opportunities.",
                    }
                )

            return {
                "overview": {
                    "total_value": total_value,
                    "total_cost": total_cost,
                    "total_pnl": total_pnl,
                    "roi_percentage": roi,
                    "asset_count": len(positions),
                    "source_count": portfolio_summary.get("source_count", 0),
                },
                "performance_analysis": {
                    "market_condition": threshold_data["market_condition"],
                    "portfolio_risk_level": threshold_data["portfolio_risk_level"],
                    "estimated_holding_period": threshold_data[
                        "estimated_holding_period"
                    ],
                    "dynamic_thresholds": threshold_data["thresholds"],
                },
                "risk_metrics": {
                    "concentration_score": concentration_score,
                    "risk_level": (
                        "High"
                        if concentration_score > 0.5
                        else "Medium" if concentration_score > 0.3 else "Low"
                    ),
                    "stablecoin_percentage": stablecoin_percentage,
                },
                "top_performers": top_performers,
                "top_losers": top_losers,
                "insights": insights,
                "last_updated": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio overview: {str(e)}"}
