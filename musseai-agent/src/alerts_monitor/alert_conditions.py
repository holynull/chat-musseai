from datetime import datetime, timedelta
import traceback
from typing import Dict

# Import from existing modules
from mysql.db import get_db
from mysql.model import (
    PortfolioAlertModel,
)
import numpy as np
import logging
from logging import Logger
from .portfolio_db import (
    get_user_portfolio_summary,
    get_transactions,
)


def _get_portfolio_data_for_alerts(
    user_id: str,
    db,
    pre_fetched_prices: Dict = None,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Get comprehensive portfolio data for alert evaluation with optional pre-fetched prices"""
    try:
        # Import portfolio tools

        # Get basic portfolio summary
        portfolio_summary = get_user_portfolio_summary(user_id=user_id)
        if isinstance(portfolio_summary, str) or "error" in portfolio_summary:
            return {}

        # Use pre-fetched prices if available, otherwise fetch individually
        latest_prices = {}

        if pre_fetched_prices:
            # Use batch-fetched price data
            logger.info(
                f"Using pre-fetched prices for {len(pre_fetched_prices)} symbols"
            )

            for asset in portfolio_summary.get("positions_by_asset", []):
                symbol = asset.get("symbol")
                if symbol and symbol in pre_fetched_prices:
                    price_info = pre_fetched_prices[symbol]
                    asset_key = asset.get(
                        "asset_id", f"{symbol}_{asset.get('chain', 'unknown')}"
                    )

                    latest_prices[asset_key] = {
                        "price": price_info["price"],
                        "timestamp": price_info["timestamp"],
                        "source": price_info["source"],
                        "asset": {
                            "symbol": symbol,
                            "chain": asset.get("chain", ""),
                            "name": asset.get("name", symbol),
                        },
                        # Additional market data
                        "market_cap": price_info.get("market_cap"),
                        "volume_24h": price_info.get("volume_24h"),
                        "percent_change_24h": price_info.get("percent_change_24h"),
                    }
                    logger.debug(
                        f"Using pre-fetched price for {symbol}: ${price_info['price']}"
                    )
        else:
            # Fallback to individual API calls (existing logic)
            logger.error("No pre-fetched prices available, fetching individually")

        # Calculate additional metrics for alerts
        portfolio_data = {
            **portfolio_summary,
            "latest_prices": latest_prices,
            "risk_metrics": _calculate_portfolio_risk_metrics(portfolio_summary),
            "performance_metrics": _calculate_performance_metrics(user_id, db),
            "concentration_score": _calculate_concentration_score(portfolio_summary),
            "volatility_score": _calculate_volatility_score(
                portfolio_summary, latest_prices
            ),
        }

        return portfolio_data

    except Exception as e:
        logger.error(f"Error getting portfolio data for alerts: {e}")
        return {}


def _calculate_portfolio_risk_metrics(
    portfolio_summary: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Calculate risk metrics for alert evaluation"""
    try:
        risk_metrics = {
            "concentration_score": 0,
            "largest_position_percent": 0,
            "top_3_concentration": 0,
            "diversification_score": 0,
        }

        allocations = portfolio_summary.get("allocation", [])
        if not allocations:
            return risk_metrics

        # Sort by percentage descending
        sorted_allocations = sorted(
            allocations, key=lambda x: x.get("percentage", 0), reverse=True
        )

        # Concentration metrics
        if sorted_allocations:
            risk_metrics["largest_position_percent"] = sorted_allocations[0].get(
                "percentage", 0
            )

            # Top 3 concentration
            top_3_percent = sum(
                alloc.get("percentage", 0) for alloc in sorted_allocations[:3]
            )
            risk_metrics["top_3_concentration"] = top_3_percent

            # Overall concentration score (higher = more concentrated)
            concentration = (
                sum(pow(alloc.get("percentage", 0) / 100, 2) for alloc in allocations)
                * 100
            )
            risk_metrics["concentration_score"] = concentration

            # Diversification score (inverse of concentration)
            risk_metrics["diversification_score"] = max(0, 100 - concentration)

        return risk_metrics

    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        return {
            "concentration_score": 0,
            "largest_position_percent": 0,
            "top_3_concentration": 0,
            "diversification_score": 0,
        }


def _calculate_performance_metrics(
    user_id: str,
    db,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Calculate performance metrics for alert evaluation"""
    try:
        # Get transactions from last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        transactions_result = get_transactions(
            user_id=user_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=1000,
        )

        performance_metrics = {
            "daily_return": 0,
            "weekly_return": 0,
            "monthly_return": 0,
            "volatility": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
        }

        # For now, return simulated metrics (in production, calculate from historical data)
        if (
            isinstance(transactions_result, dict)
            and "transactions" in transactions_result
        ):
            transaction_count = len(transactions_result["transactions"])

            # Simulate performance based on transaction activity
            performance_metrics.update(
                {
                    "daily_return": np.random.normal(
                        -0.5, 3.0
                    ),  # Simulated daily return
                    "weekly_return": np.random.normal(
                        -2.0, 8.0
                    ),  # Simulated weekly return
                    "monthly_return": np.random.normal(
                        -5.0, 15.0
                    ),  # Simulated monthly return
                    "volatility": max(
                        5, min(50, 15 + transaction_count * 0.5)
                    ),  # Based on activity
                    "sharpe_ratio": np.random.normal(0.8, 0.4),
                    "max_drawdown": abs(np.random.normal(-8.0, 5.0)),
                }
            )

        return performance_metrics

    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        return {
            "daily_return": 0,
            "weekly_return": 0,
            "monthly_return": 0,
            "volatility": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
        }


def _calculate_concentration_score(
    portfolio_summary: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> float:
    """Calculate portfolio concentration score (0-100, higher = more concentrated)"""
    try:
        allocations = portfolio_summary.get("allocation", [])
        if not allocations:
            return 0

        # Herfindahl-Hirschman Index adapted for portfolios
        hhi = sum(pow(alloc.get("percentage", 0) / 100, 2) for alloc in allocations)
        concentration_score = hhi * 100

        return min(100, max(0, concentration_score))

    except Exception as e:
        logger.error(f"Error calculating concentration score: {e}")
        return 0


def _calculate_volatility_score(
    portfolio_summary: Dict,
    latest_prices: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> float:
    """Calculate portfolio volatility score"""
    try:
        # Simplified volatility calculation based on price data availability
        volatility_score = 15.0  # Default moderate volatility

        # In production, this would calculate actual volatility from historical price data
        # For now, simulate based on portfolio composition
        positions = portfolio_summary.get("positions_by_asset", [])
        if positions:
            # Higher volatility for portfolios with more assets (simplified assumption)
            asset_count = len(positions)
            volatility_score = max(5, min(50, 10 + asset_count * 2))

        return volatility_score

    except Exception as e:
        logger.error(f"Error calculating volatility score: {e}")
        return 15.0


def _evaluate_alert_condition(
    alert: Dict,
    portfolio_data: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate if an alert condition is met"""
    try:
        alert_type = alert.get("alert_type")
        conditions = alert.get("conditions", {})

        result = {
            "triggered": False,
            "current_value": None,
            "threshold_value": None,
            "message": "",
            "distance_to_trigger": "",
        }
        logger.debug(f"Alert type is {alert_type}")
        if alert_type == "PRICE":
            return _evaluate_price_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "PORTFOLIO_VALUE":
            return _evaluate_portfolio_value_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "RISK":
            return _evaluate_risk_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "PERFORMANCE":
            return _evaluate_performance_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "REBALANCING":
            return _evaluate_rebalancing_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "VOLUME":
            return _evaluate_volume_alert(
                conditions, portfolio_data, result, logger=logger
            )
        elif alert_type == "VOLATILITY":
            return _evaluate_volatility_alert(
                conditions, portfolio_data, result, logger=logger
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating alert condition: {e}")
        return {
            "triggered": False,
            "current_value": None,
            "threshold_value": None,
            "message": f"Error: {str(e)}",
            "distance_to_trigger": "",
        }


def _evaluate_price_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate price alert conditions"""
    try:
        asset_symbol = conditions.get("asset_symbol")
        asset_chain = conditions.get("asset_chain")
        condition = conditions.get("condition")
        target_price = float(conditions.get("target_price", 0))

        # Find current price from latest prices
        current_price = None
        latest_prices = portfolio_data.get("latest_prices", {})

        for asset_id, price_data in latest_prices.items():
            asset_info = price_data.get("asset", {})
            if (
                asset_info.get("symbol") == asset_symbol
                and asset_info.get("chain") == asset_chain
            ):
                current_price = price_data.get("price")
                break

        if current_price is None:
            result["message"] = f"Price data not available for {asset_symbol}"
            return result

        result["current_value"] = current_price
        result["threshold_value"] = target_price

        # Evaluate condition
        if condition == "above" and current_price > target_price:
            result["triggered"] = True
            result["message"] = (
                f"{asset_symbol} price ${current_price:.2f} is above target ${target_price}"
            )
        elif condition == "below" and current_price < target_price:
            result["triggered"] = True
            result["message"] = (
                f"{asset_symbol} price ${current_price:.2f} is below target ${target_price}"
            )
        elif condition in ["crosses_above", "crosses_below"]:
            # For crosses, would need historical data to determine crossing
            result["message"] = (
                f"{asset_symbol} price monitoring for crossing ${target_price}"
            )

        # Calculate distance to trigger
        if not result["triggered"]:
            distance_percent = abs((current_price - target_price) / target_price * 100)
            direction = "above" if current_price > target_price else "below"
            result["distance_to_trigger"] = (
                f"{distance_percent:.1f}% {direction} target"
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating price alert: {e}")
        result["message"] = f"Price alert evaluation error: {str(e)}"
        return result


def _evaluate_portfolio_value_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate portfolio value alert conditions"""
    try:
        condition = conditions.get("condition")
        target_value = float(conditions.get("target_value", 0))
        current_value = portfolio_data.get("total_value", 0)

        result["current_value"] = current_value
        result["threshold_value"] = target_value

        if condition == "above" and current_value > target_value:
            result["triggered"] = True
            result["message"] = (
                f"Portfolio value ${current_value:.2f} exceeded target ${target_value}"
            )
        elif condition == "below" and current_value < target_value:
            result["triggered"] = True
            result["message"] = (
                f"Portfolio value ${current_value:.2f} dropped below target ${target_value}"
            )
        elif condition == "change_percent":
            # For percentage change, need baseline value (would be stored in alert history)
            # For now, simulate with a baseline
            baseline_value = target_value  # Using target as baseline for demo
            if baseline_value > 0:
                change_percent = (
                    (current_value - baseline_value) / baseline_value
                ) * 100
                threshold_percent = float(conditions.get("change_threshold", 10))

                if abs(change_percent) >= threshold_percent:
                    result["triggered"] = True
                    direction = "increased" if change_percent > 0 else "decreased"
                    result["message"] = (
                        f"Portfolio value {direction} by {abs(change_percent):.1f}% (threshold: {threshold_percent}%)"
                    )

        # Calculate distance to trigger
        if not result["triggered"] and condition in ["above", "below"]:
            distance_percent = abs((current_value - target_value) / target_value * 100)
            direction = "above" if current_value > target_value else "below"
            result["distance_to_trigger"] = (
                f"{distance_percent:.1f}% {direction} target"
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating portfolio value alert: {e}")
        result["message"] = f"Portfolio value alert evaluation error: {str(e)}"
        return result


def _evaluate_risk_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate risk alert conditions"""
    try:
        metric = conditions.get("metric")
        threshold = float(conditions.get("threshold", 0))

        risk_metrics = portfolio_data.get("risk_metrics", {})
        current_value = None

        if metric == "concentration":
            current_value = risk_metrics.get("concentration_score", 0)
        elif metric == "volatility":
            current_value = portfolio_data.get("volatility_score", 0)
        elif metric == "drawdown":
            performance_metrics = portfolio_data.get("performance_metrics", {})
            current_value = performance_metrics.get("max_drawdown", 0)
        elif metric == "var":
            # Value at Risk calculation (simplified)
            current_value = (
                portfolio_data.get("volatility_score", 15) * 1.65
            )  # 95% VaR approximation
        elif metric == "beta":
            # Beta calculation (simplified, would need market data)
            current_value = 1.0  # Simplified beta

        if current_value is None:
            result["message"] = f"Risk metric '{metric}' not available"
            return result

        result["current_value"] = current_value
        result["threshold_value"] = threshold

        if current_value > threshold:
            result["triggered"] = True
            result["message"] = (
                f"Risk metric '{metric}' at {current_value:.1f} exceeds threshold {threshold}"
            )
        else:
            distance = (threshold - current_value) / threshold * 100
            result["distance_to_trigger"] = f"{distance:.1f}% below threshold"

        return result

    except Exception as e:
        logger.error(f"Error evaluating risk alert: {e}")
        result["message"] = f"Risk alert evaluation error: {str(e)}"
        return result


def _evaluate_performance_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate performance alert conditions"""
    try:
        metric = conditions.get("metric")
        condition = conditions.get("condition", "below")
        threshold = float(conditions.get("threshold", 0))
        period = conditions.get("period", "7d")

        performance_metrics = portfolio_data.get("performance_metrics", {})
        current_value = None

        if metric == "return":
            if period == "1d":
                current_value = performance_metrics.get("daily_return", 0)
            elif period == "7d":
                current_value = performance_metrics.get("weekly_return", 0)
            elif period == "30d":
                current_value = performance_metrics.get("monthly_return", 0)
        elif metric == "sharpe_ratio":
            current_value = performance_metrics.get("sharpe_ratio", 0)
        elif metric == "sortino_ratio":
            # Simplified Sortino ratio calculation
            current_value = (
                performance_metrics.get("sharpe_ratio", 0) * 1.2
            )  # Approximation
        elif metric == "alpha":
            # Alpha calculation (simplified)
            current_value = (
                performance_metrics.get("weekly_return", 0) - 0.1
            )  # Market return approximation

        if current_value is None:
            result["message"] = (
                f"Performance metric '{metric}' not available for period '{period}'"
            )
            return result

        result["current_value"] = current_value
        result["threshold_value"] = threshold

        if condition == "below" and current_value < threshold:
            result["triggered"] = True
            result["message"] = (
                f"{period} {metric} at {current_value:.1f}% is below threshold {threshold}%"
            )
        elif condition == "above" and current_value > threshold:
            result["triggered"] = True
            result["message"] = (
                f"{period} {metric} at {current_value:.1f}% exceeds threshold {threshold}%"
            )
        else:
            if condition == "below":
                distance = (
                    ((current_value - threshold) / abs(threshold) * 100)
                    if threshold != 0
                    else 0
                )
                result["distance_to_trigger"] = f"{distance:.1f}% above threshold"
            else:
                distance = (
                    ((threshold - current_value) / abs(threshold) * 100)
                    if threshold != 0
                    else 0
                )
                result["distance_to_trigger"] = f"{distance:.1f}% below threshold"

        return result

    except Exception as e:
        logger.error(f"Error evaluating performance alert: {e}")
        result["message"] = f"Performance alert evaluation error: {str(e)}"
        return result


def _evaluate_rebalancing_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate rebalancing alert conditions"""
    try:
        deviation_threshold = float(conditions.get("deviation_threshold", 5))
        target_allocations = conditions.get("target_allocations", {})

        current_allocations = {}
        for asset in portfolio_data.get("positions_by_asset", []):
            asset_key = f"{asset.get('symbol')}_{asset.get('chain')}"
            current_allocations[asset_key] = asset.get("total_value", 0)

        total_value = portfolio_data.get("total_value", 1)
        max_deviation = 0
        deviating_assets = []

        for asset_key, target_percent in target_allocations.items():
            current_value = current_allocations.get(asset_key, 0)
            current_percent = (
                (current_value / total_value * 100) if total_value > 0 else 0
            )
            deviation = abs(current_percent - target_percent)

            if deviation > deviation_threshold:
                deviating_assets.append(
                    {
                        "asset": asset_key,
                        "current": current_percent,
                        "target": target_percent,
                        "deviation": deviation,
                    }
                )
                max_deviation = max(max_deviation, deviation)

        result["current_value"] = max_deviation
        result["threshold_value"] = deviation_threshold

        if deviating_assets:
            result["triggered"] = True
            asset_names = [asset["asset"] for asset in deviating_assets[:3]]
            result["message"] = (
                f"Rebalancing needed: {', '.join(asset_names)} deviate by up to {max_deviation:.1f}%"
            )
        else:
            result["distance_to_trigger"] = (
                f"All assets within {deviation_threshold}% of target allocation"
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating rebalancing alert: {e}")
        result["message"] = f"Rebalancing alert evaluation error: {str(e)}"
        return result


def _evaluate_volume_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate volume alert conditions"""
    try:
        asset_symbol = conditions.get("asset_symbol")
        asset_chain = conditions.get("asset_chain")
        condition = conditions.get("condition", "unusual")
        threshold = conditions.get("threshold", "high")

        # Volume data would come from external APIs in production
        # For now, simulate volume alert
        current_volume = np.random.uniform(1000000, 10000000)  # Simulated volume
        avg_volume = 5000000  # Simulated average volume

        result["current_value"] = current_volume
        result["threshold_value"] = avg_volume

        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        if condition == "unusual" and (volume_ratio > 2.0 or volume_ratio < 0.5):
            result["triggered"] = True
            volume_type = "high" if volume_ratio > 2.0 else "low"
            result["message"] = (
                f"{asset_symbol} experiencing {volume_type} volume: {volume_ratio:.1f}x average"
            )
        elif condition == "high" and volume_ratio > 1.5:
            result["triggered"] = True
            result["message"] = (
                f"{asset_symbol} high volume detected: {volume_ratio:.1f}x average"
            )
        elif condition == "low" and volume_ratio < 0.7:
            result["triggered"] = True
            result["message"] = (
                f"{asset_symbol} low volume detected: {volume_ratio:.1f}x average"
            )
        else:
            result["distance_to_trigger"] = (
                f"Volume at {volume_ratio:.1f}x average (normal range)"
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating volume alert: {e}")
        result["message"] = f"Volume alert evaluation error: {str(e)}"
        return result


def _evaluate_volatility_alert(
    conditions: Dict,
    portfolio_data: Dict,
    result: Dict,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Evaluate volatility alert conditions"""
    try:
        metric = conditions.get("metric", "price_volatility")
        threshold = float(conditions.get("threshold", 20))
        period = conditions.get("period", "24h")

        current_volatility = portfolio_data.get("volatility_score", 15)

        result["current_value"] = current_volatility
        result["threshold_value"] = threshold

        if current_volatility > threshold:
            result["triggered"] = True
            result["message"] = (
                f"Portfolio volatility at {current_volatility:.1f}% exceeds {threshold}% threshold"
            )
        else:
            distance = (threshold - current_volatility) / threshold * 100
            result["distance_to_trigger"] = (
                f"{distance:.1f}% below volatility threshold"
            )

        return result

    except Exception as e:
        logger.error(f"Error evaluating volatility alert: {e}")
        result["message"] = f"Volatility alert evaluation error: {str(e)}"
        return result


def check_alert_conditions(
    user_id: str,
    portfolio_summary: any = None,
    latest_prices: any = None,
    alert_id: str = None,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """
    Check alert conditions and trigger notifications if needed.

    Args:
        user_id (str): User identifier
        portfolio_summary: Pre-computed portfolio summary (optional)
        latest_prices: Pre-fetched price data (optional)
        alert_id (str, optional): Specific alert to check, if None checks all active alerts

    Returns:
        Dict: Check results with triggered alerts and current status
    """
    try:
        with get_db() as db:
            # Get user's portfolio data for evaluation
            # Pass pre-fetched prices if available
            portfolio_data = _get_portfolio_data_for_alerts(
                user_id, db, pre_fetched_prices=latest_prices, logger=logger
            )

            if not portfolio_data:
                return {"error": "No portfolio data found for alert evaluation"}

            # Get alerts to check
            alerts_to_check = []
            if alert_id:
                # Check specific alert (simulated)
                alerts_to_check = [
                    {"alert_id": alert_id, "alert_type": "PRICE", "conditions": {}}
                ]
            else:
                # Get all active alerts for user (simulated)
                alerts_result = get_portfolio_alerts(user_id=user_id, status="ACTIVE")
                if isinstance(alerts_result, dict) and "alerts" in alerts_result:
                    alerts_to_check = alerts_result["alerts"]

            triggered_alerts = []
            checked_alerts = []
            logger.debug(f"{len(alerts_to_check)} alerts to check")
            for alert in alerts_to_check:
                try:
                    check_result = _evaluate_alert_condition(
                        alert, portfolio_data, logger=logger
                    )
                    checked_alerts.append(
                        {
                            "alert_id": alert["alert_id"],
                            "alert_name": alert.get("alert_name", "Unnamed Alert"),
                            "checked_at": datetime.utcnow().isoformat(),
                            "current_value": check_result.get("current_value"),
                            "condition_met": check_result.get("triggered", False),
                            "distance_to_trigger": check_result.get(
                                "distance_to_trigger"
                            ),
                        }
                    )

                    if check_result.get("triggered", False):
                        triggered_alert = {
                            "alert_id": alert["alert_id"],
                            "alert_name": alert.get("alert_name", "Unnamed Alert"),
                            "alert_type": alert["alert_type"],
                            "triggered_at": datetime.utcnow().isoformat(),
                            "trigger_message": check_result.get(
                                "message", "Alert condition met"
                            ),
                            "current_value": check_result.get("current_value"),
                            "threshold_value": check_result.get("threshold_value"),
                            "notification_methods": alert.get(
                                "notification_methods", ["EMAIL"]
                            ),
                        }
                        triggered_alerts.append(triggered_alert)

                        # Send notifications (simulated)
                        # _send_alert_notifications(triggered_alert)

                except Exception as e:
                    logger.error(f"Error checking alert {alert.get('alert_id')}: {e}")
                    continue

            return {
                "success": True,
                "check_completed_at": datetime.utcnow().isoformat(),
                "alerts_checked": len(checked_alerts),
                "alerts_triggered": len(triggered_alerts),
                "triggered_alerts": triggered_alerts,
                "checked_alerts": checked_alerts,
                "portfolio_snapshot": {
                    "total_value": portfolio_data.get("total_value", 0),
                    "total_pnl": portfolio_data.get("total_pnl", 0),
                    "asset_count": portfolio_data.get("asset_count", 0),
                },
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to check alert conditions: {str(e)}"}


def get_portfolio_alerts(
    user_id: str,
    alert_type: str = None,
    status: str = None,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> Dict:
    """Get portfolio alerts for a user with filtering options."""
    try:
        with get_db() as db:
            # Build query with filters
            query = db.query(PortfolioAlertModel).filter(
                PortfolioAlertModel.user_id == user_id
            )

            if alert_type:
                query = query.filter(
                    PortfolioAlertModel.alert_type == alert_type.upper()
                )
            if status:
                query = query.filter(PortfolioAlertModel.status == status.upper())

            alerts = query.order_by(PortfolioAlertModel.created_at.desc()).all()

            # Convert to dict format
            alert_list = []
            for alert in alerts:
                alert_dict = {
                    "alert_id": alert.alert_id,
                    "alert_name": alert.alert_name,
                    "alert_type": alert.alert_type.value,
                    "conditions": alert.conditions,
                    "notification_methods": alert.notification_methods,
                    "status": alert.status.value,
                    "created_at": alert.created_at.isoformat(),
                    "updated_at": alert.updated_at.isoformat(),
                    "last_checked_at": (
                        alert.last_checked_at.isoformat()
                        if alert.last_checked_at
                        else None
                    ),
                    "last_triggered_at": (
                        alert.last_triggered_at.isoformat()
                        if alert.last_triggered_at
                        else None
                    ),
                    "trigger_count": alert.trigger_count,
                    "expiry_date": (
                        alert.expiry_date.isoformat() if alert.expiry_date else None
                    ),
                }
                alert_list.append(alert_dict)

            # Calculate summary statistics
            total_alerts = len(alert_list)
            active_alerts = len([a for a in alert_list if a["status"] == "ACTIVE"])
            triggered_alerts = len(
                [a for a in alert_list if a["status"] == "TRIGGERED"]
            )

            return {
                "success": True,
                "alerts": alert_list,
                "summary": {
                    "total_alerts": total_alerts,
                    "active_alerts": active_alerts,
                    "triggered_alerts": triggered_alerts,
                    "filtered_count": len(alert_list),
                    "last_updated": datetime.utcnow().isoformat(),
                },
            }

    except Exception as e:
        logger.error(
            f"Exception in get_portfolio_alerts: {e}\n{traceback.format_exc()}"
        )
        return {
            "success": False,
            "error": f"Failed to get portfolio alerts: {str(e)}",
            "alerts": [],
            "summary": {
                "total_alerts": 0,
                "active_alerts": 0,
                "triggered_alerts": 0,
                "filtered_count": 0,
                "last_updated": datetime.utcnow().isoformat(),
            },
        }
