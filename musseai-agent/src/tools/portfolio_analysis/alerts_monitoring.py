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


tools = [
    create_portfolio_alert,
    get_portfolio_alerts,
    analyze_portfolio_changes,
]
