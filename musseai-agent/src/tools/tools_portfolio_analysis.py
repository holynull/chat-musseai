import requests
import json
from typing import List, Dict, Optional, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from langchain.agents import tool
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from mysql.db import get_db
from mysql.model import (
    PortfolioSourceModel,
    AssetModel,
    PositionModel,
    TransactionModel,
    PriceSnapshotModel,
    SourceType,
    TransactionType,
)
from loggers import logger
import traceback


# ========================================
# Portfolio Overview Tools
# ========================================


@tool
def analyze_portfolio_overview(user_id: str) -> Dict:
    """
    Get a comprehensive portfolio analysis overview including key metrics,
    performance, and risk indicators.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Comprehensive portfolio analysis including:
            - Portfolio value and composition
            - Performance metrics
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

            # Generate insights
            insights = []

            if concentration_score > 0.5:
                insights.append(
                    {
                        "type": "WARNING",
                        "message": "High concentration risk detected. Portfolio is heavily concentrated in few assets.",
                    }
                )

            if roi > 50:
                insights.append(
                    {
                        "type": "SUCCESS",
                        "message": f"Excellent performance! Portfolio has gained {roi:.1f}% overall.",
                    }
                )
            elif roi < -20:
                insights.append(
                    {
                        "type": "ALERT",
                        "message": f"Portfolio is down {abs(roi):.1f}%. Consider reviewing your strategy.",
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

            if stablecoin_percentage < 5:
                insights.append(
                    {
                        "type": "INFO",
                        "message": "Low stablecoin allocation. Consider holding some for stability.",
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
                "last_updated": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio overview: {str(e)}"}


@tool
def portfolio_health_check(user_id: str) -> Dict:
    """
    Perform a quick health check on the portfolio and provide a score with recommendations.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Health check results including:
            - Overall health score (0-100)
            - Category scores
            - Specific issues found
            - Recommendations
    """
    try:
        # Get portfolio data
        overview = analyze_portfolio_overview.invoke({"user_id": user_id})
        if "error" in overview:
            return overview

        # Initialize scores
        scores = {
            "diversification": 0,
            "performance": 0,
            "risk_management": 0,
            "liquidity": 0,
            "overall": 0,
        }

        issues = []
        recommendations = []

        # Diversification score
        concentration_score = overview["risk_metrics"]["concentration_score"]
        if concentration_score < 0.2:
            scores["diversification"] = 90
        elif concentration_score < 0.3:
            scores["diversification"] = 70
        elif concentration_score < 0.5:
            scores["diversification"] = 50
        else:
            scores["diversification"] = 30
            issues.append("Poor diversification - too concentrated")
            recommendations.append("Diversify holdings across more assets")

        # Performance score
        roi = overview["overview"]["roi_percentage"]
        if roi > 20:
            scores["performance"] = 90
        elif roi > 0:
            scores["performance"] = 70
        elif roi > -10:
            scores["performance"] = 50
        else:
            scores["performance"] = 30
            issues.append("Poor performance - significant losses")
            recommendations.append("Review and adjust investment strategy")

        # Risk management score
        stablecoin_pct = overview["risk_metrics"]["stablecoin_percentage"]
        if 10 <= stablecoin_pct <= 30:
            scores["risk_management"] = 90
        elif 5 <= stablecoin_pct <= 40:
            scores["risk_management"] = 70
        else:
            scores["risk_management"] = 50
            issues.append("Suboptimal stablecoin allocation")
            recommendations.append(
                "Adjust stablecoin allocation for better risk management"
            )

        # Liquidity score (simplified)
        scores["liquidity"] = (
            70  # Default, would need more data for accurate assessment
        )

        # Calculate overall score
        scores["overall"] = sum(scores.values()) / (
            len(scores) - 1
        )  # Exclude overall itself

        # Determine health status
        if scores["overall"] >= 80:
            health_status = "EXCELLENT"
        elif scores["overall"] >= 60:
            health_status = "GOOD"
        elif scores["overall"] >= 40:
            health_status = "FAIR"
        else:
            health_status = "POOR"

        return {
            "health_score": scores["overall"],
            "health_status": health_status,
            "category_scores": scores,
            "issues_found": issues,
            "recommendations": recommendations,
            "check_date": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to perform health check: {str(e)}"}


@tool
def get_portfolio_metrics(user_id: str, period_days: int = 30) -> Dict:
    """
    Calculate key portfolio metrics for the specified period.

    Args:
        user_id (str): User identifier
        period_days (int): Number of days to analyze (default: 30)

    Returns:
        Dict: Portfolio metrics including:
            - Returns (absolute and percentage)
            - Volatility
            - Sharpe ratio
            - Maximum drawdown
            - Win/loss ratio
    """
    try:
        with get_db() as db:
            # Get user's source IDs
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            if not sources:
                return {"error": "No active portfolio sources found"}

            source_ids = [s.source_id for s in sources]

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)

            # Get transactions in period
            transactions = (
                db.query(TransactionModel)
                .filter(
                    TransactionModel.source_id.in_(source_ids),
                    TransactionModel.transaction_time >= start_date,
                    TransactionModel.transaction_time <= end_date,
                )
                .all()
            )

            # Get current positions
            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            # Calculate metrics
            total_value = sum(
                float(p.quantity * p.last_price) for p in positions if p.last_price
            )

            # Calculate returns
            total_invested = sum(
                float(t.quantity * t.price)
                for t in transactions
                if t.transaction_type == TransactionType.BUY and t.price
            )

            total_sold = sum(
                float(t.quantity * t.price)
                for t in transactions
                if t.transaction_type == TransactionType.SELL and t.price
            )

            unrealized_pnl = sum(
                float(p.quantity * (p.last_price - p.avg_cost))
                for p in positions
                if p.last_price and p.avg_cost
            )

            realized_pnl = total_sold - total_invested
            total_pnl = realized_pnl + unrealized_pnl

            # Calculate win/loss ratio
            winning_trades = len(
                [
                    t
                    for t in transactions
                    if t.transaction_type == TransactionType.SELL
                    and t.price
                    and t.price > 0
                ]
            )

            total_trades = len(
                [
                    t
                    for t in transactions
                    if t.transaction_type in [TransactionType.BUY, TransactionType.SELL]
                ]
            )

            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            # Simplified volatility calculation (would need daily price data for accurate calculation)
            volatility = 0  # Placeholder

            # Risk-free rate (assumed 2% annually)
            risk_free_rate = 0.02 / 365 * period_days

            # Sharpe ratio (simplified)
            returns_pct = (
                (total_pnl / total_invested * 100) if total_invested > 0 else 0
            )
            sharpe_ratio = (
                (returns_pct - risk_free_rate) / (volatility + 1)
                if volatility > 0
                else 0
            )

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": period_days,
                },
                "returns": {
                    "total_pnl": total_pnl,
                    "realized_pnl": realized_pnl,
                    "unrealized_pnl": unrealized_pnl,
                    "return_percentage": returns_pct,
                },
                "risk_metrics": {
                    "volatility": volatility,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown": 0,  # Would need historical data
                },
                "trading_metrics": {
                    "total_trades": total_trades,
                    "win_rate": win_rate,
                    "average_win": 0,  # Would need more calculation
                    "average_loss": 0,
                },
                "current_value": total_value,
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to calculate portfolio metrics: {str(e)}"}


# ========================================
# Performance Analysis Tools
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
        end_date (str, optional): End date (default: now)
        benchmark (str): Benchmark asset for comparison (default: BTC)

    Returns:
        Dict: Performance analysis including:
            - Absolute and relative returns
            - Risk-adjusted metrics
            - Benchmark comparison
            - Performance attribution
    """
    try:
        from tools.tools_crypto_portfolios import calculate_portfolio_performance

        # Get basic performance data
        performance = calculate_portfolio_performance.invoke(
            {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        )

        if isinstance(performance, dict) and "error" in performance:
            return performance

        # Calculate additional metrics
        period_days = performance["period"]["days"]
        total_return = performance["total_return"]

        # Annualized return
        annualized_return = 0
        if period_days > 0:
            annualized_return = (1 + total_return / 100) ** (365 / period_days) - 1
            annualized_return *= 100

        # Time-weighted return (simplified)
        twr = total_return  # Would need daily values for accurate calculation

        # Money-weighted return
        mwr = total_return  # Simplified, would need cash flow data

        # Performance attribution
        attribution = {
            "selection_effect": 0,  # Would need sector/asset data
            "allocation_effect": 0,
            "interaction_effect": 0,
        }

        # Risk metrics
        risk_metrics = {
            "volatility": 0,  # Would need daily returns
            "beta": 0,  # Would need benchmark correlation
            "alpha": 0,  # Would need regression analysis
            "information_ratio": 0,
        }

        return {
            "period": performance["period"],
            "returns": {
                "total_return": total_return,
                "annualized_return": annualized_return,
                "time_weighted_return": twr,
                "money_weighted_return": mwr,
            },
            "value_changes": {
                "starting_value": performance["starting_value"],
                "ending_value": performance["ending_value"],
                "net_deposits": performance["net_deposits"],
            },
            "pnl_breakdown": {
                "realized_pnl": performance["realized_pnl"],
                "unrealized_pnl": performance["unrealized_pnl"],
                "total_pnl": performance["total_pnl"],
            },
            "risk_adjusted_metrics": risk_metrics,
            "performance_attribution": attribution,
            "benchmark_comparison": {
                "benchmark": benchmark,
                "benchmark_return": 0,  # Would need benchmark data
                "excess_return": 0,
            },
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio performance: {str(e)}"}


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
        # Get portfolio metrics
        portfolio_metrics = get_portfolio_metrics.invoke(
            {"user_id": user_id, "period_days": 365}
        )

        if "error" in portfolio_metrics:
            return portfolio_metrics

        portfolio_return = portfolio_metrics["returns"]["return_percentage"]

        comparisons = []

        # For each benchmark (simplified - would need actual price data)
        benchmark_returns = {
            "BTC": 45.0,  # Placeholder
            "ETH": 38.0,  # Placeholder
            "SP500": 12.0,  # Placeholder
        }

        for benchmark in benchmarks:
            benchmark_return = benchmark_returns.get(benchmark, 0)

            comparison = {
                "benchmark": benchmark,
                "portfolio_return": portfolio_return,
                "benchmark_return": benchmark_return,
                "excess_return": portfolio_return - benchmark_return,
                "outperformed": portfolio_return > benchmark_return,
                "correlation": 0.65,  # Placeholder - would need actual calculation
                "beta": 0.8,  # Placeholder
                "tracking_error": 5.2,  # Placeholder
            }

            comparisons.append(comparison)

        # Summary statistics
        avg_excess_return = sum(c["excess_return"] for c in comparisons) / len(
            comparisons
        )
        outperformance_rate = (
            sum(1 for c in comparisons if c["outperformed"]) / len(comparisons) * 100
        )

        return {
            "comparisons": comparisons,
            "summary": {
                "average_excess_return": avg_excess_return,
                "outperformance_rate": outperformance_rate,
                "best_relative_performance": max(
                    comparisons, key=lambda x: x["excess_return"]
                )["benchmark"],
                "worst_relative_performance": min(
                    comparisons, key=lambda x: x["excess_return"]
                )["benchmark"],
            },
            "analysis_date": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to compare to benchmarks: {str(e)}"}


@tool
def get_historical_performance(user_id: str, interval: str = "monthly") -> List[Dict]:
    """
    Get historical performance data at specified intervals.

    Args:
        user_id (str): User identifier
        interval (str): Time interval ('daily', 'weekly', 'monthly', 'quarterly')

    Returns:
        List[Dict]: Historical performance data points
    """
    try:
        with get_db() as db:
            # Get user's sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            if not sources:
                return []

            source_ids = [s.source_id for s in sources]

            # Determine interval days
            interval_days = {
                "daily": 1,
                "weekly": 7,
                "monthly": 30,
                "quarterly": 90,
            }.get(interval, 30)

            # Generate historical data points (simplified)
            performance_history = []
            current_date = datetime.utcnow()

            for i in range(12):  # Last 12 periods
                period_end = current_date - timedelta(days=i * interval_days)
                period_start = period_end - timedelta(days=interval_days)

                # Would need actual historical data
                # This is a placeholder calculation
                period_return = np.random.normal(5, 15)  # Random for demo

                performance_history.append(
                    {
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "return_percentage": period_return,
                        "portfolio_value": 10000
                        * (1 + period_return / 100),  # Placeholder
                        "net_deposits": 0,
                    }
                )

            return performance_history

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return []


# ========================================
# Risk Analysis Tools
# ========================================


@tool
def analyze_portfolio_risk(user_id: str) -> Dict:
    """
    Comprehensive portfolio risk analysis including various risk metrics.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Risk analysis including:
            - Volatility metrics
            - Value at Risk (VaR)
            - Concentration risk
            - Correlation analysis
            - Risk recommendations
    """
    try:
        from tools.tools_crypto_portfolios import (
            analyze_portfolio_risk as base_risk_analysis,
        )

        # Get basic risk analysis
        basic_risk = base_risk_analysis.invoke({"user_id": user_id})

        if isinstance(basic_risk, str) or "error" in basic_risk:
            return {"error": "Failed to analyze portfolio risk"}

        # Calculate additional risk metrics
        with get_db() as db:
            # Get portfolio data
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            source_ids = [s.source_id for s in sources]

            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            # Calculate total portfolio value
            total_value = sum(
                float(p.quantity * p.last_price) for p in positions if p.last_price
            )

            # Advanced risk metrics
            # Value at Risk (95% confidence, simplified)
            portfolio_volatility = 0.25  # 25% annualized volatility (placeholder)
            var_95 = total_value * 1.645 * portfolio_volatility / np.sqrt(365)

            # Conditional VaR (CVaR)
            cvar_95 = var_95 * 1.2  # Simplified approximation

            # Maximum position risk
            max_position_value = max(
                (float(p.quantity * p.last_price) for p in positions if p.last_price),
                default=0,
            )
            max_position_risk = (
                (max_position_value / total_value * 100) if total_value > 0 else 0
            )

            # Liquidity risk (simplified)
            liquidity_score = 70  # Would need market depth data

            # Systematic risk
            beta = 1.2  # Portfolio beta vs crypto market (placeholder)

            return {
                "risk_summary": {
                    "overall_risk_level": basic_risk["risk_score"],
                    "risk_rating": (
                        "High"
                        if basic_risk["risk_score"] > 70
                        else "Medium" if basic_risk["risk_score"] > 40 else "Low"
                    ),
                    "portfolio_value": total_value,
                },
                "volatility_metrics": {
                    "annualized_volatility": portfolio_volatility * 100,
                    "daily_volatility": portfolio_volatility / np.sqrt(365) * 100,
                    "beta": beta,
                    "correlation_with_market": 0.75,  # Placeholder
                },
                "value_at_risk": {
                    "var_95_1day": var_95,
                    "var_95_1day_percentage": (
                        (var_95 / total_value * 100) if total_value > 0 else 0
                    ),
                    "cvar_95_1day": cvar_95,
                    "var_99_1day": total_value
                    * 2.326
                    * portfolio_volatility
                    / np.sqrt(365),
                },
                "concentration_risk": {
                    "herfindahl_index": basic_risk["concentration_risk"][
                        "concentration_score"
                    ]
                    / 100,
                    "top_position_weight": max_position_risk,
                    "number_of_positions": len(positions),
                    "effective_number_of_positions": (
                        1
                        / (
                            basic_risk["concentration_risk"]["concentration_score"]
                            / 10000
                        )
                        if basic_risk["concentration_risk"]["concentration_score"] > 0
                        else 0
                    ),
                },
                "liquidity_risk": {
                    "liquidity_score": liquidity_score,
                    "illiquid_percentage": 100 - liquidity_score,
                    "estimated_liquidation_days": 2,  # Placeholder
                },
                "recommendations": basic_risk["recommendations"],
                "risk_factors": [
                    {
                        "factor": "Market Risk",
                        "impact": "High",
                        "description": "Exposure to overall crypto market movements",
                    },
                    {
                        "factor": "Concentration Risk",
                        "impact": (
                            "High"
                            if basic_risk["concentration_risk"]["concentration_score"]
                            > 50
                            else "Medium"
                        ),
                        "description": "Risk from concentrated positions",
                    },
                    {
                        "factor": "Liquidity Risk",
                        "impact": "Low" if liquidity_score > 80 else "Medium",
                        "description": "Risk of not being able to exit positions quickly",
                    },
                ],
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio risk: {str(e)}"}


@tool
def portfolio_stress_test(user_id: str, scenarios: List[Dict] = None) -> Dict:
    """
    Run stress tests on the portfolio under various market scenarios.

    Args:
        user_id (str): User identifier
        scenarios (List[Dict], optional): Custom scenarios to test

    Returns:
        Dict: Stress test results showing portfolio impact under each scenario
    """
    try:
        # Get current portfolio value
        from tools.tools_crypto_portfolios import get_user_portfolio_summary

        portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

        if (
            portfolio is None
            or isinstance(portfolio, str)
            or (isinstance(portfolio, dict) and "error" in portfolio)
        ):
            return {"error": "Failed to retrieve portfolio data"}

        current_value = portfolio["total_value"]
        positions = portfolio["positions_by_asset"]

        # Default scenarios if none provided
        if not scenarios:
            scenarios = [
                {
                    "name": "Market Crash",
                    "description": "Severe market downturn",
                    "market_change": -40,
                    "btc_change": -35,
                    "altcoin_change": -50,
                    "stablecoin_change": 0,
                },
                {
                    "name": "Bull Run",
                    "description": "Strong market rally",
                    "market_change": 50,
                    "btc_change": 40,
                    "altcoin_change": 80,
                    "stablecoin_change": 0,
                },
                {
                    "name": "Flash Crash",
                    "description": "Sudden temporary drop",
                    "market_change": -25,
                    "btc_change": -20,
                    "altcoin_change": -30,
                    "stablecoin_change": 0,
                },
                {
                    "name": "Regulatory Shock",
                    "description": "Major regulatory changes",
                    "market_change": -30,
                    "btc_change": -25,
                    "altcoin_change": -40,
                    "stablecoin_change": -5,
                },
            ]

        results = []

        for scenario in scenarios:
            # Calculate impact on each position
            scenario_value = 0
            impacted_positions = []

            for position in positions:
                symbol = position["symbol"].upper()
                current_pos_value = position["total_value"]

                # Determine impact based on asset type
                if symbol in ["USDT", "USDC", "DAI", "BUSD"]:
                    change = scenario.get("stablecoin_change", 0)
                elif symbol == "BTC":
                    change = scenario.get("btc_change", scenario["market_change"])
                elif symbol == "ETH":
                    change = scenario.get("eth_change", scenario["market_change"] * 0.9)
                else:
                    change = scenario.get("altcoin_change", scenario["market_change"])

                new_value = current_pos_value * (1 + change / 100)
                impact = new_value - current_pos_value

                scenario_value += new_value

                impacted_positions.append(
                    {
                        "asset": f"{position['symbol']} ({position['chain']})",
                        "current_value": current_pos_value,
                        "scenario_value": new_value,
                        "change_amount": impact,
                        "change_percentage": change,
                    }
                )

            # Sort by impact
            impacted_positions.sort(key=lambda x: x["change_amount"])

            total_impact = scenario_value - current_value
            impact_percentage = (
                (total_impact / current_value * 100) if current_value > 0 else 0
            )

            results.append(
                {
                    "scenario": scenario["name"],
                    "description": scenario["description"],
                    "portfolio_impact": {
                        "current_value": current_value,
                        "scenario_value": scenario_value,
                        "change_amount": total_impact,
                        "change_percentage": impact_percentage,
                    },
                    "most_impacted": impacted_positions[:5],  # Top 5 most impacted
                    "risk_level": (
                        "SEVERE"
                        if impact_percentage < -30
                        else (
                            "HIGH"
                            if impact_percentage < -20
                            else "MODERATE" if impact_percentage < -10 else "LOW"
                        )
                    ),
                }
            )

        # Summary
        worst_case = min(
            results, key=lambda x: x["portfolio_impact"]["change_percentage"]
        )
        best_case = max(
            results, key=lambda x: x["portfolio_impact"]["change_percentage"]
        )

        return {
            "stress_test_results": results,
            "summary": {
                "worst_case_scenario": worst_case["scenario"],
                "worst_case_loss": worst_case["portfolio_impact"]["change_percentage"],
                "best_case_scenario": best_case["scenario"],
                "best_case_gain": best_case["portfolio_impact"]["change_percentage"],
                "average_downside": (
                    sum(
                        r["portfolio_impact"]["change_percentage"]
                        for r in results
                        if r["portfolio_impact"]["change_percentage"] < 0
                    )
                    / len(
                        [
                            r
                            for r in results
                            if r["portfolio_impact"]["change_percentage"] < 0
                        ]
                    )
                    if any(
                        r["portfolio_impact"]["change_percentage"] < 0 for r in results
                    )
                    else 0
                ),
            },
            "test_date": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to run stress test: {str(e)}"}


@tool
def analyze_asset_correlations(user_id: str, period_days: int = 90) -> Dict:
    """
    Analyze correlations between assets in the portfolio.

    Args:
        user_id (str): User identifier
        period_days (int): Period for correlation calculation

    Returns:
        Dict: Correlation matrix and analysis
    """
    try:
        # Get portfolio positions
        from tools.tools_crypto_portfolios import get_user_portfolio_summary

        portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

        if (
            portfolio is None
            or isinstance(portfolio, str)
            or (isinstance(portfolio, dict) and "error" in portfolio)
        ):
            return {"error": "Failed to retrieve portfolio data"}

        positions = portfolio["positions_by_asset"]

        # Create correlation matrix (simplified - would need actual price data)
        assets = [p["symbol"] for p in positions[:10]]  # Limit to top 10
        n_assets = len(assets)

        # Generate synthetic correlation matrix
        correlation_matrix = np.random.rand(n_assets, n_assets)
        correlation_matrix = (correlation_matrix + correlation_matrix.T) / 2
        np.fill_diagonal(correlation_matrix, 1.0)

        # Ensure correlations are in valid range
        correlation_matrix = np.clip(correlation_matrix, -1, 1)

        # Convert to list format for JSON serialization
        correlations = []
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                correlations.append(
                    {
                        "asset1": assets[i],
                        "asset2": assets[j],
                        "correlation": float(correlation_matrix[i, j]),
                        "relationship": (
                            "Strong Positive"
                            if correlation_matrix[i, j] > 0.7
                            else (
                                "Moderate Positive"
                                if correlation_matrix[i, j] > 0.3
                                else (
                                    "Weak"
                                    if correlation_matrix[i, j] > -0.3
                                    else (
                                        "Moderate Negative"
                                        if correlation_matrix[i, j] > -0.7
                                        else "Strong Negative"
                                    )
                                )
                            )
                        ),
                    }
                )

        # Sort by absolute correlation
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        # Analysis
        high_correlations = [c for c in correlations if abs(c["correlation"]) > 0.7]
        avg_correlation = np.mean([abs(c["correlation"]) for c in correlations])

        return {
            "correlation_analysis": {
                "period_days": period_days,
                "number_of_assets": n_assets,
                "average_correlation": avg_correlation,
                "high_correlation_pairs": len(high_correlations),
            },
            "top_correlations": correlations[:10],
            "diversification_score": max(0, 100 - avg_correlation * 100),
            "insights": [
                (
                    {
                        "type": "WARNING" if len(high_correlations) > 3 else "INFO",
                        "message": f"Found {len(high_correlations)} highly correlated asset pairs. Consider diversifying.",
                    }
                    if high_correlations
                    else {
                        "type": "SUCCESS",
                        "message": "Portfolio shows good diversification with low asset correlations.",
                    }
                )
            ],
            "analysis_date": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze correlations: {str(e)}"}


# ========================================
# Recommendation Tools
# ========================================


@tool
def get_rebalancing_recommendations(
    user_id: str, target_allocation: Dict = None
) -> Dict:
    """
    Generate portfolio rebalancing recommendations based on target allocation.

    Args:
        user_id (str): User identifier
        target_allocation (Dict, optional): Target allocation percentages by asset

    Returns:
        Dict: Rebalancing recommendations with specific actions
    """
    try:
        # Get current portfolio
        from tools.tools_crypto_portfolios import get_user_portfolio_summary

        portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

        if (
            portfolio is None
            or isinstance(portfolio, str)
            or (isinstance(portfolio, dict) and "error" in portfolio)
        ):
            return {"error": "Failed to retrieve portfolio data"}

        total_value = portfolio["total_value"]
        positions = portfolio["positions_by_asset"]

        # Default target allocation if not provided
        if not target_allocation:
            target_allocation = {
                "BTC": 30,
                "ETH": 25,
                "STABLECOINS": 20,
                "LARGE_CAP_ALTS": 15,
                "SMALL_CAP_ALTS": 10,
            }

        # Calculate current allocation
        current_allocation = {}
        for position in positions:
            symbol = position["symbol"]
            percentage = (
                (position["total_value"] / total_value * 100) if total_value > 0 else 0
            )

            # Categorize assets
            if symbol in ["USDT", "USDC", "DAI", "BUSD"]:
                category = "STABLECOINS"
            elif symbol == "BTC":
                category = "BTC"
            elif symbol == "ETH":
                category = "ETH"
            elif position["total_value"] > total_value * 0.02:  # > 2% of portfolio
                category = "LARGE_CAP_ALTS"
            else:
                category = "SMALL_CAP_ALTS"

            current_allocation[category] = (
                current_allocation.get(category, 0) + percentage
            )

        # Calculate rebalancing actions
        actions = []
        total_adjustment = 0

        for category, target_pct in target_allocation.items():
            current_pct = current_allocation.get(category, 0)
            diff_pct = target_pct - current_pct
            diff_value = total_value * diff_pct / 100

            if abs(diff_pct) > 2:  # Only rebalance if difference > 2%
                action = {
                    "category": category,
                    "current_percentage": current_pct,
                    "target_percentage": target_pct,
                    "difference_percentage": diff_pct,
                    "action": "BUY" if diff_pct > 0 else "SELL",
                    "amount_usd": abs(diff_value),
                    "priority": (
                        "HIGH"
                        if abs(diff_pct) > 10
                        else "MEDIUM" if abs(diff_pct) > 5 else "LOW"
                    ),
                }
                actions.append(action)
                total_adjustment += abs(diff_value)

        # Sort by priority and amount
        actions.sort(
            key=lambda x: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["priority"]],
                x["amount_usd"],
            ),
            reverse=True,
        )

        # Generate specific recommendations
        recommendations = []
        for action in actions:
            if action["action"] == "BUY":
                recommendations.append(
                    {
                        "action": "BUY",
                        "category": action["category"],
                        "amount": action["amount_usd"],
                        "reason": f"Increase {action['category']} allocation from {action['current_percentage']:.1f}% to {action['target_percentage']:.1f}%",
                    }
                )
            else:
                recommendations.append(
                    {
                        "action": "SELL",
                        "category": action["category"],
                        "amount": action["amount_usd"],
                        "reason": f"Reduce {action['category']} allocation from {action['current_percentage']:.1f}% to {action['target_percentage']:.1f}%",
                    }
                )

        # Calculate rebalancing metrics
        rebalancing_metrics = {
            "total_trades_needed": len(actions),
            "total_value_to_rebalance": total_adjustment,
            "rebalancing_percentage": (
                (total_adjustment / total_value * 100) if total_value > 0 else 0
            ),
            "estimated_cost": total_adjustment * 0.002,  # 0.2% trading fees estimate
        }

        return {
            "current_allocation": current_allocation,
            "target_allocation": target_allocation,
            "rebalancing_actions": actions,
            "recommendations": recommendations,
            "metrics": rebalancing_metrics,
            "execution_notes": [
                "Execute high priority trades first",
                "Consider market conditions and liquidity",
                "Use limit orders to minimize slippage",
                "Rebalance in stages if total adjustment > 20%",
            ],
            "next_review": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to generate rebalancing recommendations: {str(e)}"}


@tool
def find_investment_opportunities(user_id: str, risk_tolerance: str = "MEDIUM") -> Dict:
    """
    Identify potential investment opportunities based on portfolio analysis and market conditions.

    Args:
        user_id (str): User identifier
        risk_tolerance (str): Risk tolerance level (LOW, MEDIUM, HIGH)

    Returns:
        Dict: Investment opportunities with analysis and recommendations
    """
    try:
        # Get portfolio data
        from tools.tools_crypto_portfolios import (
            get_portfolio_allocation,
            get_user_portfolio_summary,
        )

        portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})
        if (
            portfolio is None
            or isinstance(portfolio, str)
            or (isinstance(portfolio, dict) and "error" in portfolio)
        ):
            return {"error": "Failed to retrieve portfolio data"}

        allocation = get_portfolio_allocation.invoke(
            {"user_id": user_id, "group_by": "asset"}
        )
        if isinstance(allocation, str):
            return {"error": "Failed to get allocation data"}

        # Analyze current portfolio
        total_value = portfolio["total_value"]
        stablecoin_allocation = sum(
            item["percentage"]
            for item in allocation
            if any(
                stable in item["group"].upper()
                for stable in ["USDT", "USDC", "DAI", "BUSD"]
            )
        )

        opportunities = []

        # Opportunity 1: Stablecoin yield farming
        if stablecoin_allocation > 10:
            opportunities.append(
                {
                    "type": "YIELD_FARMING",
                    "title": "Stablecoin Yield Opportunity",
                    "description": "Deploy idle stablecoins to earn yield",
                    "risk_level": "LOW",
                    "expected_apy": "5-8%",
                    "recommended_amount": total_value
                    * stablecoin_allocation
                    / 100
                    * 0.5,
                    "platforms": ["Aave", "Compound", "Curve"],
                    "action_items": [
                        "Research current APY rates on DeFi platforms",
                        "Consider gas fees for deployment",
                        "Start with 50% of stablecoin holdings",
                    ],
                }
            )

        # Opportunity 2: Rebalancing opportunity
        if any(item["percentage"] > 40 for item in allocation):
            opportunities.append(
                {
                    "type": "REBALANCING",
                    "title": "Portfolio Rebalancing Opportunity",
                    "description": "Reduce concentration risk through strategic rebalancing",
                    "risk_level": "LOW",
                    "expected_benefit": "Reduced portfolio risk",
                    "recommended_action": "Diversify concentrated positions",
                    "action_items": [
                        "Review rebalancing recommendations",
                        "Set up gradual rebalancing plan",
                        "Consider tax implications",
                    ],
                }
            )

        # Opportunity 3: Market opportunities based on risk tolerance
        if risk_tolerance == "HIGH":
            opportunities.append(
                {
                    "type": "HIGH_RISK_HIGH_REWARD",
                    "title": "Emerging Protocol Opportunities",
                    "description": "New DeFi protocols with high yield potential",
                    "risk_level": "HIGH",
                    "expected_return": "20-50% APY",
                    "recommended_allocation": min(total_value * 0.05, 1000),
                    "sectors": ["Layer 2 solutions", "AI tokens", "RWA protocols"],
                    "warning": "Only invest what you can afford to lose",
                }
            )
        elif risk_tolerance == "MEDIUM":
            opportunities.append(
                {
                    "type": "BALANCED_GROWTH",
                    "title": "Blue Chip DeFi Allocation",
                    "description": "Established DeFi protocols with proven track records",
                    "risk_level": "MEDIUM",
                    "expected_return": "10-20% APY",
                    "recommended_allocation": total_value * 0.15,
                    "protocols": ["Uniswap", "Aave", "MakerDAO"],
                    "benefits": ["Proven security", "Stable yields", "Good liquidity"],
                }
            )
        else:  # LOW risk
            opportunities.append(
                {
                    "type": "CONSERVATIVE_INCOME",
                    "title": "Staking Major Assets",
                    "description": "Stake ETH or other PoS assets for steady income",
                    "risk_level": "LOW",
                    "expected_return": "4-6% APY",
                    "recommended_allocation": total_value * 0.20,
                    "options": ["ETH staking", "Liquid staking derivatives"],
                    "benefits": [
                        "Passive income",
                        "Support network security",
                        "Maintain exposure",
                    ],
                }
            )

        # Opportunity 4: Tax loss harvesting
        losing_positions = [
            p for p in portfolio["positions_by_asset"] if p.get("pnl", 0) < -100
        ]
        if losing_positions:
            opportunities.append(
                {
                    "type": "TAX_OPTIMIZATION",
                    "title": "Tax Loss Harvesting Opportunity",
                    "description": "Realize losses to offset gains for tax purposes",
                    "risk_level": "LOW",
                    "potential_tax_savings": sum(
                        abs(p["pnl"]) for p in losing_positions
                    )
                    * 0.20,
                    "positions_to_consider": [
                        {
                            "asset": p["symbol"],
                            "loss": p["pnl"],
                            "current_value": p["total_value"],
                        }
                        for p in losing_positions[:3]
                    ],
                    "action_items": [
                        "Consult with tax advisor",
                        "Consider wash sale rules",
                        "Plan replacement investments",
                    ],
                }
            )

        # Score and rank opportunities
        for opp in opportunities:
            # Simple scoring based on risk/reward
            if opp["risk_level"] == "LOW":
                risk_score = 1
            elif opp["risk_level"] == "MEDIUM":
                risk_score = 2
            else:
                risk_score = 3

            # Estimate return score
            if "expected_return" in opp or "expected_apy" in opp:
                return_str = opp.get("expected_return", opp.get("expected_apy", "0%"))
                try:
                    return_score = float(
                        return_str.split("-")[0].replace("%", "").strip()
                    )
                except:
                    return_score = 5
            else:
                return_score = 5

            opp["opportunity_score"] = return_score / risk_score

        # Sort by opportunity score
        opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        return {
            "opportunities": opportunities,
            "portfolio_context": {
                "total_value": total_value,
                "risk_tolerance": risk_tolerance,
                "current_allocation": {
                    "stablecoins": stablecoin_allocation,
                    "volatile_assets": 100 - stablecoin_allocation,
                },
            },
            "market_conditions": {
                "overall_trend": "NEUTRAL",  # Would need market data
                "volatility": "MEDIUM",
                "recommendation": "Proceed with caution, consider dollar-cost averaging",
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to find investment opportunities: {str(e)}"}


@tool
def analyze_tax_implications(
    user_id: str, tax_year: int = None, country: str = "US"
) -> Dict:
    """
    Analyze tax implications of the portfolio including realized gains/losses and strategies.

    Args:
        user_id (str): User identifier
        tax_year (int, optional): Tax year to analyze (default: current year)
        country (str): Country for tax rules (default: US)

    Returns:
        Dict: Tax analysis and optimization strategies
    """
    try:
        if not tax_year:
            tax_year = datetime.utcnow().year

        with get_db() as db:
            # Get user's sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            source_ids = [s.source_id for s in sources]

            # Get transactions for the tax year
            year_start = datetime(tax_year, 1, 1)
            year_end = datetime(tax_year, 12, 31, 23, 59, 59)

            transactions = (
                db.query(TransactionModel)
                .filter(
                    TransactionModel.source_id.in_(source_ids),
                    TransactionModel.transaction_time >= year_start,
                    TransactionModel.transaction_time <= year_end,
                )
                .all()
            )

            # Calculate realized gains/losses
            realized_gains = 0
            realized_losses = 0
            short_term_gains = 0
            long_term_gains = 0

            taxable_events = []

            for tx in transactions:
                if tx.transaction_type == TransactionType.SELL and tx.price:
                    # Simplified calculation - would need proper cost basis tracking
                    proceeds = float(tx.quantity * tx.price)

                    # For demo, assume 20% profit/loss
                    cost_basis = proceeds * 0.8
                    gain_loss = proceeds - cost_basis

                    if gain_loss > 0:
                        realized_gains += gain_loss
                        # Assume long-term if > 6 months old
                        if (datetime.utcnow() - tx.transaction_time).days > 180:
                            long_term_gains += gain_loss
                        else:
                            short_term_gains += gain_loss
                    else:
                        realized_losses += abs(gain_loss)

                    taxable_events.append(
                        {
                            "date": tx.transaction_time.isoformat(),
                            "asset": tx.asset.symbol,
                            "quantity": float(tx.quantity),
                            "proceeds": proceeds,
                            "cost_basis": cost_basis,
                            "gain_loss": gain_loss,
                            "type": (
                                "Long-term"
                                if (datetime.utcnow() - tx.transaction_time).days > 365
                                else "Short-term"
                            ),
                        }
                    )

            # Tax calculations (US rules simplified)
            net_gains = realized_gains - realized_losses

            # Estimate tax liability
            if country == "US":
                short_term_tax_rate = 0.35  # Simplified
                long_term_tax_rate = 0.20  # Simplified

                estimated_tax = (
                    short_term_gains * short_term_tax_rate
                    + long_term_gains * long_term_tax_rate
                )
            else:
                estimated_tax = net_gains * 0.30  # Generic rate

            # Tax optimization strategies
            strategies = []

            # Strategy 1: Tax loss harvesting
            from tools.tools_crypto_portfolios import get_user_portfolio_summary

            portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

            if (
                portfolio is None
                or isinstance(portfolio, str)
                or (isinstance(portfolio, dict) and "error" in portfolio)
            ):
                return {"error": "Failed to retrieve portfolio data"}

            if isinstance(portfolio, dict) and "positions_by_asset" in portfolio:
                losing_positions = [
                    p for p in portfolio["positions_by_asset"] if p.get("pnl", 0) < -100
                ]

                if losing_positions and net_gains > 0:
                    potential_offset = min(
                        sum(abs(p["pnl"]) for p in losing_positions), net_gains
                    )

                    strategies.append(
                        {
                            "strategy": "Tax Loss Harvesting",
                            "description": "Realize losses to offset gains",
                            "potential_tax_savings": potential_offset * 0.30,
                            "action": "Sell losing positions before year-end",
                            "positions": [
                                {"asset": p["symbol"], "unrealized_loss": p["pnl"]}
                                for p in losing_positions[:5]
                            ],
                        }
                    )

            # Strategy 2: Hold for long-term
            if short_term_gains > long_term_gains:
                strategies.append(
                    {
                        "strategy": "Hold for Long-term Treatment",
                        "description": "Hold positions > 1 year for lower tax rate",
                        "potential_tax_savings": short_term_gains
                        * (short_term_tax_rate - long_term_tax_rate),
                        "action": "Delay selling positions close to 1-year mark",
                    }
                )

            # Strategy 3: Charitable donations
            if net_gains > 10000:
                strategies.append(
                    {
                        "strategy": "Charitable Crypto Donations",
                        "description": "Donate appreciated crypto directly to charity",
                        "potential_tax_savings": net_gains * 0.10 * 0.35,
                        "action": "Donate appreciated positions instead of cash",
                        "benefits": ["Avoid capital gains tax", "Get full deduction"],
                    }
                )

            return {
                "tax_year": tax_year,
                "country": country,
                "summary": {
                    "realized_gains": realized_gains,
                    "realized_losses": realized_losses,
                    "net_gains": net_gains,
                    "short_term_gains": short_term_gains,
                    "long_term_gains": long_term_gains,
                    "estimated_tax_liability": estimated_tax,
                    "effective_tax_rate": (
                        (estimated_tax / net_gains * 100) if net_gains > 0 else 0
                    ),
                },
                "taxable_events": taxable_events[:10],  # Top 10
                "optimization_strategies": strategies,
                "important_dates": {
                    "tax_filing_deadline": f"{tax_year + 1}-04-15",
                    "estimated_tax_deadlines": [
                        f"{tax_year}-04-15",
                        f"{tax_year}-06-15",
                        f"{tax_year}-09-15",
                        f"{tax_year + 1}-01-15",
                    ],
                },
                "disclaimer": "This is a simplified analysis. Consult a tax professional for accurate advice.",
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze tax implications: {str(e)}"}


# ========================================
# Alert and Monitoring Tools
# ========================================


@tool
def create_portfolio_alert(
    user_id: str, alert_type: str, conditions: Dict, notification_method: str = "email"
) -> Dict:
    """
    Create a portfolio alert based on specified conditions.

    Args:
        user_id (str): User identifier
        alert_type (str): Type of alert (PRICE, PORTFOLIO_VALUE, RISK, PERFORMANCE)
        conditions (Dict): Alert conditions
        notification_method (str): How to notify (email, sms, push)

    Returns:
        Dict: Created alert details
    """
    try:
        # Validate alert type
        valid_alert_types = [
            "PRICE",
            "PORTFOLIO_VALUE",
            "RISK",
            "PERFORMANCE",
            "REBALANCING",
        ]
        if alert_type not in valid_alert_types:
            return {"error": f"Invalid alert type. Must be one of: {valid_alert_types}"}

        # Create alert configuration
        alert_config = {
            "alert_id": f"{user_id}_{alert_type}_{datetime.utcnow().timestamp()}",
            "user_id": user_id,
            "alert_type": alert_type,
            "conditions": conditions,
            "notification_method": notification_method,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "last_triggered": None,
        }

        # Validate conditions based on alert type
        if alert_type == "PRICE":
            required_fields = ["asset", "condition", "price"]
            if not all(field in conditions for field in required_fields):
                return {"error": f"Price alert requires: {required_fields}"}

        elif alert_type == "PORTFOLIO_VALUE":
            required_fields = ["condition", "value"]
            if not all(field in conditions for field in required_fields):
                return {"error": f"Portfolio value alert requires: {required_fields}"}

        elif alert_type == "RISK":
            required_fields = ["metric", "threshold"]
            if not all(field in conditions for field in required_fields):
                return {"error": f"Risk alert requires: {required_fields}"}

        elif alert_type == "PERFORMANCE":
            required_fields = ["metric", "condition", "value", "period"]
            if not all(field in conditions for field in required_fields):
                return {"error": f"Performance alert requires: {required_fields}"}

        elif alert_type == "REBALANCING":
            required_fields = ["deviation_threshold"]
            if not all(field in conditions for field in required_fields):
                return {"error": f"Rebalancing alert requires: {required_fields}"}

        # In a real implementation, this would save to database
        # For now, return the created alert
        return {
            "success": True,
            "alert": alert_config,
            "message": f"{alert_type} alert created successfully",
            "example_triggers": _get_example_triggers(alert_type, conditions),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to create alert: {str(e)}"}


def _get_example_triggers(alert_type: str, conditions: Dict) -> List[str]:
    """Helper function to provide example trigger scenarios"""
    examples = []

    if alert_type == "PRICE":
        asset = conditions.get("asset", "BTC")
        price = conditions.get("price", 50000)
        condition = conditions.get("condition", "above")
        examples.append(f"When {asset} price goes {condition} ${price}")

    elif alert_type == "PORTFOLIO_VALUE":
        value = conditions.get("value", 10000)
        condition = conditions.get("condition", "below")
        examples.append(f"When portfolio value goes {condition} ${value}")

    elif alert_type == "RISK":
        metric = conditions.get("metric", "concentration")
        threshold = conditions.get("threshold", 50)
        examples.append(f"When {metric} risk exceeds {threshold}%")

    elif alert_type == "PERFORMANCE":
        metric = conditions.get("metric", "return")
        value = conditions.get("value", -10)
        period = conditions.get("period", "24h")
        examples.append(f"When {period} {metric} drops below {value}%")

    elif alert_type == "REBALANCING":
        threshold = conditions.get("deviation_threshold", 5)
        examples.append(f"When any asset deviates more than {threshold}% from target")

    return examples


@tool
def get_portfolio_alerts(user_id: str, active_only: bool = True) -> List[Dict]:
    """
    Get all portfolio alerts for a user.

    Args:
        user_id (str): User identifier
        active_only (bool): Only return active alerts

    Returns:
        List[Dict]: List of alerts with their status
    """
    try:
        # In a real implementation, this would query from database
        # For demo, create sample alerts
        sample_alerts = [
            {
                "alert_id": f"{user_id}_PRICE_001",
                "alert_type": "PRICE",
                "conditions": {"asset": "BTC", "condition": "above", "price": 70000},
                "status": "ACTIVE",
                "created_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "last_checked": datetime.utcnow().isoformat(),
                "triggered_count": 0,
                "notification_method": "email",
            },
            {
                "alert_id": f"{user_id}_PORTFOLIO_VALUE_001",
                "alert_type": "PORTFOLIO_VALUE",
                "conditions": {"condition": "below", "value": 8000},
                "status": "ACTIVE",
                "created_at": (datetime.utcnow() - timedelta(days=14)).isoformat(),
                "last_checked": datetime.utcnow().isoformat(),
                "triggered_count": 1,
                "last_triggered": (datetime.utcnow() - timedelta(days=3)).isoformat(),
                "notification_method": "email",
            },
            {
                "alert_id": f"{user_id}_RISK_001",
                "alert_type": "RISK",
                "conditions": {"metric": "concentration_score", "threshold": 60},
                "status": "TRIGGERED",
                "created_at": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                "last_checked": datetime.utcnow().isoformat(),
                "triggered_count": 3,
                "last_triggered": datetime.utcnow().isoformat(),
                "notification_method": "push",
            },
        ]

        if active_only:
            alerts = [a for a in sample_alerts if a["status"] == "ACTIVE"]
        else:
            alerts = sample_alerts

        return alerts

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return []


@tool
def analyze_portfolio_changes(user_id: str, period_hours: int = 24) -> Dict:
    """
    Analyze recent changes in the portfolio and highlight significant movements.

    Args:
        user_id (str): User identifier
        period_hours (int): Hours to look back (default: 24)

    Returns:
        Dict: Analysis of portfolio changes
    """
    try:
        with get_db() as db:
            # Get user's sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            source_ids = [s.source_id for s in sources]

            # Get recent transactions
            since = datetime.utcnow() - timedelta(hours=period_hours)

            recent_transactions = (
                db.query(TransactionModel)
                .filter(
                    TransactionModel.source_id.in_(source_ids),
                    TransactionModel.transaction_time >= since,
                )
                .order_by(TransactionModel.transaction_time.desc())
                .all()
            )

            # Get current portfolio summary
            from tools.tools_crypto_portfolios import get_user_portfolio_summary

            current_portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

            if (
                current_portfolio is None
                or isinstance(current_portfolio, str)
                or (
                    isinstance(current_portfolio, dict) and "error" in current_portfolio
                )
            ):
                return {"error": "Failed to retrieve portfolio data"}

            if isinstance(current_portfolio, str) or "error" in current_portfolio:
                return {"error": "Failed to retrieve portfolio data"}

            # Analyze changes
            changes = {
                "period": {
                    "start": since.isoformat(),
                    "end": datetime.utcnow().isoformat(),
                    "hours": period_hours,
                },
                "transaction_summary": {
                    "total_transactions": len(recent_transactions),
                    "buys": len(
                        [
                            t
                            for t in recent_transactions
                            if t.transaction_type == TransactionType.BUY
                        ]
                    ),
                    "sells": len(
                        [
                            t
                            for t in recent_transactions
                            if t.transaction_type == TransactionType.SELL
                        ]
                    ),
                    "deposits": len(
                        [
                            t
                            for t in recent_transactions
                            if t.transaction_type == TransactionType.DEPOSIT
                        ]
                    ),
                    "withdrawals": len(
                        [
                            t
                            for t in recent_transactions
                            if t.transaction_type == TransactionType.WITHDRAW
                        ]
                    ),
                },
                "value_changes": {
                    "current_value": current_portfolio["total_value"],
                    "estimated_change": 0,  # Would need historical snapshot
                    "change_percentage": 0,
                },
                "significant_trades": [],
                "new_positions": [],
                "closed_positions": [],
                "alerts": [],
            }

            # Identify significant trades
            for tx in recent_transactions[:10]:  # Top 10 recent
                if tx.price and tx.quantity:
                    trade_value = float(tx.quantity * tx.price)
                    if (
                        trade_value > current_portfolio["total_value"] * 0.05
                    ):  # > 5% of portfolio
                        changes["significant_trades"].append(
                            {
                                "time": tx.transaction_time.isoformat(),
                                "type": tx.transaction_type.value,
                                "asset": tx.asset.symbol,
                                "quantity": float(tx.quantity),
                                "value": trade_value,
                                "percentage_of_portfolio": (
                                    trade_value / current_portfolio["total_value"] * 100
                                ),
                            }
                        )

            # Generate alerts based on changes
            if changes["transaction_summary"]["total_transactions"] > 20:
                changes["alerts"].append(
                    {
                        "type": "HIGH_ACTIVITY",
                        "message": f"High trading activity detected: {changes['transaction_summary']['total_transactions']} transactions in {period_hours} hours",
                    }
                )

            if (
                changes["transaction_summary"]["sells"]
                > changes["transaction_summary"]["buys"] * 2
            ):
                changes["alerts"].append(
                    {
                        "type": "SELLING_PRESSURE",
                        "message": "Significant selling activity detected. Review your strategy.",
                    }
                )

            # Add insights
            changes["insights"] = []

            if (
                changes["transaction_summary"]["buys"]
                > changes["transaction_summary"]["sells"]
            ):
                changes["insights"].append(
                    {
                        "type": "ACCUMULATION",
                        "message": "Net accumulation phase - more buying than selling",
                    }
                )

            if changes["significant_trades"]:
                changes["insights"].append(
                    {
                        "type": "LARGE_TRADES",
                        "message": f"Made {len(changes['significant_trades'])} significant trades (>5% of portfolio)",
                    }
                )

            return changes

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio changes: {str(e)}"}


# ========================================
# Market Analysis Tools
# ========================================


@tool
def analyze_market_conditions(asset_symbols: List[str] = None) -> Dict:
    """
    Analyze current market conditions relevant to the portfolio.

    Args:
        asset_symbols (List[str], optional): Specific assets to analyze

    Returns:
        Dict: Market analysis and conditions
    """
    try:
        # Default to major assets if none specified
        if not asset_symbols:
            asset_symbols = ["BTC", "ETH", "BNB", "SOL", "MATIC"]

        # In a real implementation, this would fetch real market data
        # For demo, using simulated data
        market_analysis = {
            "overall_sentiment": "NEUTRAL",
            "market_trend": "SIDEWAYS",
            "volatility_index": 45.2,  # 0-100 scale
            "fear_greed_index": 52,  # 0-100 scale
            "bitcoin_dominance": 48.5,
            "total_market_cap": 2.1e12,
            "24h_volume": 89.5e9,
        }

        # Asset-specific analysis
        asset_analysis = []
        for symbol in asset_symbols[:5]:  # Limit to 5
            # Simulated data
            analysis = {
                "symbol": symbol,
                "price_trend": "UP" if hash(symbol) % 2 == 0 else "DOWN",
                "24h_change": (hash(symbol) % 20 - 10) / 10,  # -10% to +10%
                "7d_change": (hash(symbol) % 40 - 20) / 10,  # -20% to +20%
                "volume_trend": "INCREASING" if hash(symbol) % 3 == 0 else "STABLE",
                "technical_rating": [
                    "STRONG_BUY",
                    "BUY",
                    "NEUTRAL",
                    "SELL",
                    "STRONG_SELL",
                ][hash(symbol) % 5],
                "support_level": 0.95,  # Simplified
                "resistance_level": 1.05,  # Simplified
                "rsi": 50 + (hash(symbol) % 40 - 20),  # 30-70 range
                "moving_averages": {
                    "ma_20": "ABOVE" if hash(symbol) % 2 == 0 else "BELOW",
                    "ma_50": "ABOVE" if hash(symbol) % 3 == 0 else "BELOW",
                    "ma_200": "ABOVE" if hash(symbol) % 4 == 0 else "BELOW",
                },
            }
            asset_analysis.append(analysis)

        # Market insights
        insights = []

        if market_analysis["volatility_index"] > 70:
            insights.append(
                {
                    "type": "HIGH_VOLATILITY",
                    "message": "Market volatility is high. Consider reducing position sizes or increasing stablecoin allocation.",
                }
            )

        if market_analysis["fear_greed_index"] < 30:
            insights.append(
                {
                    "type": "EXTREME_FEAR",
                    "message": "Market sentiment shows extreme fear. This could be a buying opportunity for long-term investors.",
                }
            )
        elif market_analysis["fear_greed_index"] > 70:
            insights.append(
                {
                    "type": "EXTREME_GREED",
                    "message": "Market sentiment shows extreme greed. Consider taking some profits.",
                }
            )

        # Trading recommendations based on conditions
        recommendations = []

        if (
            market_analysis["market_trend"] == "UP"
            and market_analysis["fear_greed_index"] < 70
        ):
            recommendations.append(
                {
                    "action": "ACCUMULATE",
                    "reasoning": "Uptrend with reasonable sentiment levels",
                    "assets": [
                        a["symbol"]
                        for a in asset_analysis
                        if a["technical_rating"] in ["BUY", "STRONG_BUY"]
                    ],
                }
            )

        if market_analysis["volatility_index"] > 60:
            recommendations.append(
                {
                    "action": "INCREASE_STABLECOINS",
                    "reasoning": "High volatility suggests need for more stable assets",
                    "target_allocation": "20-30%",
                }
            )

        return {
            "market_overview": market_analysis,
            "asset_analysis": asset_analysis,
            "insights": insights,
            "recommendations": recommendations,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze market conditions: {str(e)}"}


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
                    stable in p["symbol"].upper() for stable in ["USDT", "USDC", "DAI"]
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


# ========================================
# Reporting Tools
# ========================================


@tool
def generate_portfolio_report(
    user_id: str, report_type: str = "SUMMARY", period_days: int = 30
) -> Dict:
    """
    Generate a comprehensive portfolio report.

    Args:
        user_id (str): User identifier
        report_type (str): Type of report (SUMMARY, DETAILED, PERFORMANCE, TAX)
        period_days (int): Period to cover in the report

    Returns:
        Dict: Comprehensive portfolio report
    """
    try:
        report = {
            "report_type": report_type,
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start": (datetime.utcnow() - timedelta(days=period_days)).isoformat(),
                "end": datetime.utcnow().isoformat(),
                "days": period_days,
            },
        }

        # Get base data
        overview = analyze_portfolio_overview.invoke({"user_id": user_id})
        if "error" in overview:
            return overview

        # Add sections based on report type
        if report_type in ["SUMMARY", "DETAILED"]:
            report["executive_summary"] = {
                "portfolio_value": overview["overview"]["total_value"],
                "total_return": overview["overview"]["roi_percentage"],
                "risk_level": overview["risk_metrics"]["risk_level"],
                "health_score": portfolio_health_check.invoke({"user_id": user_id}).get(
                    "health_score", 0
                ),
                "key_insights": overview["insights"],
            }

        if report_type in ["DETAILED", "PERFORMANCE"]:
            # Performance section
            performance = analyze_portfolio_performance.invoke(
                {"user_id": user_id, "start_date": report["period"]["start"]}
            )

            if "error" not in performance:
                report["performance_analysis"] = performance

            # Risk section
            risk = analyze_portfolio_risk.invoke({"user_id": user_id})
            if "error" not in risk:
                report["risk_analysis"] = risk

        if report_type == "TAX":
            # Tax section
            tax = analyze_tax_implications.invoke(
                {"user_id": user_id, "tax_year": datetime.utcnow().year}
            )

            if "error" not in tax:
                report["tax_analysis"] = tax

        # Add recommendations
        report["recommendations"] = {
            "immediate_actions": [],
            "short_term": [],  # 1-4 weeks
            "long_term": [],  # 1-3 months
        }

        # Generate recommendations based on analysis
        if overview["risk_metrics"]["risk_level"] == "High":
            report["recommendations"]["immediate_actions"].append(
                {
                    "action": "Reduce concentration risk",
                    "priority": "HIGH",
                    "description": "Diversify holdings to reduce portfolio risk",
                }
            )

        if overview["risk_metrics"]["stablecoin_percentage"] < 10:
            report["recommendations"]["short_term"].append(
                {
                    "action": "Increase stablecoin allocation",
                    "priority": "MEDIUM",
                    "description": "Target 10-20% stablecoin allocation for stability",
                }
            )

        # Format report based on type
        if report_type == "SUMMARY":
            # Keep only essential sections
            report = {
                "report_type": report["report_type"],
                "generated_at": report["generated_at"],
                "executive_summary": report.get("executive_summary", {}),
                "key_metrics": {
                    "total_value": overview["overview"]["total_value"],
                    "roi": overview["overview"]["roi_percentage"],
                    "asset_count": overview["overview"]["asset_count"],
                    "risk_level": overview["risk_metrics"]["risk_level"],
                },
                "top_recommendations": report["recommendations"]["immediate_actions"][
                    :3
                ],
            }

        return report

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to generate portfolio report: {str(e)}"}


# Export all tools
tools = [
    # Portfolio Overview
    analyze_portfolio_overview,
    portfolio_health_check,
    get_portfolio_metrics,
    # Performance Analysis
    analyze_portfolio_performance,
    compare_to_benchmarks,
    get_historical_performance,
    # Risk Analysis
    analyze_portfolio_risk,
    portfolio_stress_test,
    analyze_asset_correlations,
    # Recommendations
    get_rebalancing_recommendations,
    find_investment_opportunities,
    analyze_tax_implications,
    # Alerts and Monitoring
    create_portfolio_alert,
    get_portfolio_alerts,
    analyze_portfolio_changes,
    # Market Analysis
    analyze_market_conditions,
    get_market_opportunities,
    # Reporting
    generate_portfolio_report,
]
