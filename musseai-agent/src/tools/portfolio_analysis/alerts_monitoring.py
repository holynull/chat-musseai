from decimal import Decimal
import enum
import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta
from langchain.agents import tool
from mysql.db import get_db
from mysql.model import (
    AlertStatus,
    AlertType,
    NotificationMethod,
    PortfolioAlertModel,
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
    user_id: str,
    alert_name: str,
    alert_type: str,
    conditions: Dict,
    notification_methods: List[str] = None,
    expiry_date: str = None,
) -> Dict:
    """
    Create a comprehensive portfolio alert with database persistence.

    Args:
        user_id (str): User identifier
        alert_name (str): User-defined name for the alert
        alert_type (str): Type of alert (PRICE, PORTFOLIO_VALUE, RISK, PERFORMANCE, REBALANCING, VOLUME, VOLATILITY)
        conditions (Dict): Alert conditions specific to alert type
        notification_methods (List[str]): List of notification methods (EMAIL, SMS, PUSH, WEBHOOK)
        expiry_date (str, optional): Alert expiry date (ISO format)

    Returns:
        Dict: Created alert details with validation and examples
    """
    try:
        with get_db() as db:
            # Validate alert type
            valid_alert_types = [e.value for e in AlertType]
            if alert_type not in valid_alert_types:
                return {
                    "error": f"Invalid alert type. Must be one of: {valid_alert_types}"
                }

            # Set default notification methods
            if not notification_methods:
                notification_methods = ["EMAIL"]

            # Validate notification methods
            valid_notification_methods = [e.value for e in NotificationMethod]
            for method in notification_methods:
                if method not in valid_notification_methods:
                    return {
                        "error": f"Invalid notification method '{method}'. Must be one of: {valid_notification_methods}"
                    }

            # Validate conditions based on alert type
            validation_result = _validate_alert_conditions(alert_type, conditions)
            if not validation_result["valid"]:
                return {"error": validation_result["message"]}

            # Parse expiry date if provided
            expiry_datetime = None
            if expiry_date:
                try:
                    expiry_datetime = datetime.fromisoformat(
                        expiry_date.replace("Z", "+00:00")
                    )
                except:
                    return {"error": "Invalid expiry_date format. Use ISO format."}

            # Create alert configuration (simulated database storage)
            alert_config = {
                # "alert_id": f"{user_id}_{alert_type}_{int(datetime.utcnow().timestamp())}",
                "user_id": user_id,
                "alert_name": alert_name,
                "alert_type": alert_type,
                "conditions": conditions,
                "notification_methods": notification_methods,
                "status": "ACTIVE",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "last_checked_at": None,
                "last_triggered_at": None,
                "trigger_count": 0,
                "expiry_date": expiry_datetime.isoformat() if expiry_datetime else None,
            }

            alert = PortfolioAlertModel(**alert_config)
            db.add(alert)
            db.commit()

            return {
                "success": True,
                "alert": alert_config,
                "message": f"{alert_type} alert '{alert_name}' created successfully",
                "validation": validation_result,
                "example_scenarios": _get_alert_examples(alert_type, conditions),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to create alert: {str(e)}"}


def _validate_alert_conditions(alert_type: str, conditions: Dict) -> Dict:
    """Validate alert conditions based on alert type"""
    try:
        if alert_type == "PRICE":
            required = ["asset_symbol", "asset_chain", "condition", "target_price"]
            if not all(field in conditions for field in required):
                return {"valid": False, "message": f"Price alert requires: {required}"}

            if conditions["condition"] not in [
                "above",
                "below",
                "crosses_above",
                "crosses_below",
            ]:
                return {
                    "valid": False,
                    "message": "Price condition must be: above, below, crosses_above, or crosses_below",
                }

            try:
                float(conditions["target_price"])
            except:
                return {
                    "valid": False,
                    "message": "target_price must be a valid number",
                }

        elif alert_type == "PORTFOLIO_VALUE":
            required = ["condition", "target_value"]
            if not all(field in conditions for field in required):
                return {
                    "valid": False,
                    "message": f"Portfolio value alert requires: {required}",
                }

            if conditions["condition"] not in ["above", "below", "change_percent"]:
                return {
                    "valid": False,
                    "message": "Portfolio value condition must be: above, below, or change_percent",
                }

        elif alert_type == "RISK":
            required = ["metric", "threshold"]
            if not all(field in conditions for field in required):
                return {"valid": False, "message": f"Risk alert requires: {required}"}

            valid_metrics = ["volatility", "concentration", "drawdown", "var", "beta"]
            if conditions["metric"] not in valid_metrics:
                return {
                    "valid": False,
                    "message": f"Risk metric must be one of: {valid_metrics}",
                }

        elif alert_type == "PERFORMANCE":
            required = ["metric", "condition", "threshold", "period"]
            if not all(field in conditions for field in required):
                return {
                    "valid": False,
                    "message": f"Performance alert requires: {required}",
                }

            valid_metrics = ["return", "sharpe_ratio", "sortino_ratio", "alpha"]
            if conditions["metric"] not in valid_metrics:
                return {
                    "valid": False,
                    "message": f"Performance metric must be one of: {valid_metrics}",
                }

        elif alert_type == "REBALANCING":
            required = ["deviation_threshold"]
            if not all(field in conditions for field in required):
                return {
                    "valid": False,
                    "message": f"Rebalancing alert requires: {required}",
                }

        elif alert_type == "VOLUME":
            required = ["asset_symbol", "asset_chain", "condition", "threshold"]
            if not all(field in conditions for field in required):
                return {"valid": False, "message": f"Volume alert requires: {required}"}

        elif alert_type == "VOLATILITY":
            required = ["metric", "threshold", "period"]
            if not all(field in conditions for field in required):
                return {
                    "valid": False,
                    "message": f"Volatility alert requires: {required}",
                }

        return {"valid": True, "message": "Conditions are valid"}

    except Exception as e:
        return {"valid": False, "message": f"Validation error: {str(e)}"}


def _get_alert_examples(alert_type: str, conditions: Dict) -> List[str]:
    """Generate example scenarios for alert types"""
    examples = []

    try:
        if alert_type == "PRICE":
            asset = conditions.get("asset_symbol", "BTC")
            price = conditions.get("target_price", 50000)
            condition = conditions.get("condition", "above")
            examples = [
                f"Alert when {asset} price goes {condition} ${price}",
                f"Monitor {asset} price movements around ${price} threshold",
                f"Get notified when {asset} {condition} target price",
            ]

        elif alert_type == "PORTFOLIO_VALUE":
            value = conditions.get("target_value", 10000)
            condition = conditions.get("condition", "below")
            if condition == "change_percent":
                examples = [
                    f"Alert when portfolio changes by {value}% from baseline",
                    f"Monitor significant portfolio value fluctuations",
                    f"Track portfolio performance deviations",
                ]
            else:
                examples = [
                    f"Alert when total portfolio value goes {condition} ${value}",
                    f"Monitor portfolio value crossing ${value} threshold",
                    f"Track portfolio reaching target milestones",
                ]

        elif alert_type == "RISK":
            metric = conditions.get("metric", "volatility")
            threshold = conditions.get("threshold", 20)
            examples = [
                f"Alert when portfolio {metric} exceeds {threshold}%",
                f"Monitor risk levels and portfolio stability",
                f"Get early warning on increased portfolio risk",
            ]

        elif alert_type == "PERFORMANCE":
            metric = conditions.get("metric", "return")
            threshold = conditions.get("threshold", -10)
            period = conditions.get("period", "7d")
            examples = [
                f"Alert when {period} {metric} drops below {threshold}%",
                f"Monitor portfolio performance over {period} periods",
                f"Track underperformance and opportunity signals",
            ]

        elif alert_type == "REBALANCING":
            threshold = conditions.get("deviation_threshold", 5)
            examples = [
                f"Alert when any asset deviates more than {threshold}% from target allocation",
                f"Monitor portfolio balance and rebalancing needs",
                f"Maintain optimal portfolio allocation automatically",
            ]

        elif alert_type == "VOLUME":
            asset = conditions.get("asset_symbol", "ETH")
            threshold = conditions.get("threshold", "unusual")
            examples = [
                f"Alert on {threshold} {asset} trading volume",
                f"Monitor market activity and liquidity changes",
                f"Detect potential market movements early",
            ]

        elif alert_type == "VOLATILITY":
            metric = conditions.get("metric", "price_volatility")
            threshold = conditions.get("threshold", 15)
            period = conditions.get("period", "24h")
            examples = [
                f"Alert when {period} {metric} exceeds {threshold}%",
                f"Monitor market stability and volatility spikes",
                f"Prepare for potential market turbulence",
            ]

    except Exception as e:
        logger.error(f"Error generating examples: {e}")
        examples = ["Example scenarios unavailable"]

    return examples


@tool
def get_portfolio_alerts(
    user_id: str, alert_type: str = None, status: str = None
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


@tool
def update_portfolio_alert(
    user_id: str,
    alert_id: str,
    alert_name: str = None,
    conditions: Dict = None,
    notification_methods: List[str] = None,
    status: str = None,
) -> Dict:
    """
        Update an existing portfolio alert configuration with new parameters.
    
        This function allows users to modify their existing portfolio alerts by updating
        any combination of alert name, conditions, notification methods, and status.
        All parameters are validated before applying changes to ensure data integrity.
    
        Args:
            user_id (str): Unique identifier for the user who owns the alert
            alert_id (str): Unique identifier of the alert to be updated
            alert_name (str, optional): New display name for the alert
            conditions (Dict, optional): Updated alert conditions specific to alert type
            notification_methods (List[str], optional): Updated list of notification methods
            status (str, optional): New alert status (ACTIVE, INACTIVE, PAUSED, TRIGGERED)
    
        Returns:
            Dict: Update result containing success status and updated alert information
    
        Example:
            >>> update_portfolio_alert(
            ...     user_id="user123",
            ...     alert_id="alert456",
            ...     alert_name="Updated BTC Alert",
            ...     conditions={"target_price": 45000, "condition": "below"}
            ... )
            {'success': True, 'message': 'Alert updated successfully', 'alert': {...}}
    """
    try:
        with get_db() as db:
            # Query existing alert first
            existing_alert = (
                db.query(PortfolioAlertModel)
                .filter(
                    PortfolioAlertModel.alert_id == alert_id,
                    PortfolioAlertModel.user_id == user_id,
                )
                .first()
            )

            if not existing_alert:
                return {"error": f"Alert {alert_id} not found for user {user_id}"}

            # Update fields if provided
            if alert_name:
                existing_alert.alert_name = alert_name
            if conditions:
                # Validate conditions first
                validation_result = _validate_alert_conditions(
                    existing_alert.alert_type.value, conditions
                )
                if not validation_result["valid"]:
                    return {"error": validation_result["message"]}
                existing_alert.conditions = conditions
            if notification_methods:
                existing_alert.notification_methods = notification_methods
            if status:
                existing_alert.status = AlertStatus(status)

            existing_alert.updated_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "message": "Alert updated successfully",
                "alert": {
                    "alert_id": existing_alert.alert_id,
                    "alert_name": existing_alert.alert_name,
                    "alert_type": existing_alert.alert_type.value,
                    "updated_at": existing_alert.updated_at.isoformat(),
                },
            }
    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to update alert: {str(e)}"}


@tool
def delete_portfolio_alert(user_id: str, alert_id: str) -> Dict:
    """
    Delete a portfolio alert.

    Args:
        user_id (str): User identifier
        alert_id (str): Alert identifier

    Returns:
        Dict: Deletion result
    """
    try:
        # Input validation
        if not user_id or not alert_id:
            return {"error": "user_id and alert_id are required"}
        
        with get_db() as db:
            # Check if alert exists and belongs to user
            existing_alert = (
                db.query(PortfolioAlertModel)
                .filter(
                    PortfolioAlertModel.alert_id == alert_id,
                    PortfolioAlertModel.user_id == user_id,
                )
                .first()
            )

            if not existing_alert:
                return {"error": f"Alert {alert_id} not found for user {user_id}"}

            # Store alert info before deletion
            deleted_alert_info = {
                "alert_id": existing_alert.alert_id,
                "alert_name": existing_alert.alert_name,
                "alert_type": existing_alert.alert_type.value,
                "user_id": existing_alert.user_id,
                "deleted_at": datetime.utcnow().isoformat(),
            }

            # Perform deletion
            db.delete(existing_alert)
            db.commit()

            return {
                "success": True,
                "message": f"Alert {alert_id} deleted successfully",
                "deleted_alert": deleted_alert_info,
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to delete alert: {str(e)}"}










@tool
def get_alert_history(user_id: str, alert_id: str = None, days: int = 30) -> List[Dict]:
    """
    Get alert trigger history for a user.

    Args:
        user_id (str): User identifier
        alert_id (str, optional): Specific alert ID to filter by
        days (int): Number of days of history to retrieve (default: 30)

    Returns:
        List[Dict]: Alert trigger history
    """
    try:
        # In production, query from alert_history table
        # For now, return simulated history data

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        sample_history = [
            {
                "history_id": 1,
                "alert_id": f"{user_id}_RISK_001",
                "alert_name": "High Risk Warning",
                "alert_type": "RISK",
                "triggered_at": (end_date - timedelta(hours=2)).isoformat(),
                "trigger_value": {"concentration_score": 67.5},
                "threshold_value": {"concentration_score": 60},
                "message": "Risk metric 'concentration' at 67.5 exceeds threshold 60",
                "notification_sent": True,
                "notifications_delivered": ["EMAIL", "SMS"],
            },
            {
                "history_id": 2,
                "alert_id": f"{user_id}_PERFORMANCE_001",
                "alert_name": "Weekly Performance Check",
                "alert_type": "PERFORMANCE",
                "triggered_at": (end_date - timedelta(days=5)).isoformat(),
                "trigger_value": {"weekly_return": -16.2},
                "threshold_value": {"weekly_return": -15},
                "message": "7d return at -16.2% is below threshold -15%",
                "notification_sent": True,
                "notifications_delivered": ["EMAIL"],
            },
            {
                "history_id": 3,
                "alert_id": f"{user_id}_PRICE_002",
                "alert_name": "ETH Price Alert",
                "alert_type": "PRICE",
                "triggered_at": (end_date - timedelta(days=12)).isoformat(),
                "trigger_value": {"price": 2850.75},
                "threshold_value": {"price": 3000},
                "message": "ETH price $2850.75 is below target $3000",
                "notification_sent": True,
                "notifications_delivered": ["EMAIL", "PUSH"],
            },
        ]

        # Filter by alert_id if specified
        if alert_id:
            sample_history = [h for h in sample_history if h["alert_id"] == alert_id]

        # Filter by date range
        filtered_history = []
        for history in sample_history:
            trigger_time = datetime.fromisoformat(
                history["triggered_at"].replace("Z", "+00:00")
            )
            if start_date <= trigger_time <= end_date:
                filtered_history.append(history)

        return {
            "history": filtered_history,
            "summary": {
                "total_triggers": len(filtered_history),
                "period_days": days,
                "most_triggered_type": "RISK" if filtered_history else None,
                "last_trigger": (
                    filtered_history[0]["triggered_at"] if filtered_history else None
                ),
            },
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to get alert history: {str(e)}"}


@tool
def analyze_portfolio_changes(user_id: str, period_hours: int = 24) -> Dict:
    """
    Enhanced analysis of recent changes in the portfolio with alert-relevant insights.

    Args:
        user_id (str): User identifier
        period_hours (int): Hours to look back (default: 24)

    Returns:
        Dict: Comprehensive analysis of portfolio changes with alert suggestions
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

            # Enhanced analysis with alert insights
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
                "insights": [],
                "alert_suggestions": [],
                "risk_indicators": {
                    "high_activity": False,
                    "concentration_risk": False,
                    "volatility_spike": False,
                    "liquidity_concerns": False,
                },
            }

            # Analyze significant trades
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

            # Analyze new and closed positions
            for tx in recent_transactions:
                if tx.transaction_type in [
                    TransactionType.BUY,
                    TransactionType.DEPOSIT,
                ]:
                    # Check if this created a new position
                    existing_position = any(
                        pos["asset"]["symbol"] == tx.asset.symbol
                        for pos in current_portfolio.get("positions_by_asset", [])
                    )
                    if not existing_position:
                        changes["new_positions"].append(
                            {
                                "asset": tx.asset.symbol,
                                "chain": tx.asset.chain,
                                "initial_quantity": float(tx.quantity),
                                "initial_value": (
                                    float(tx.quantity * tx.price) if tx.price else None
                                ),
                                "added_at": tx.transaction_time.isoformat(),
                            }
                        )

            # Generate alerts based on changes
            if changes["transaction_summary"]["total_transactions"] > 20:
                changes["alerts"].append(
                    {
                        "type": "HIGH_ACTIVITY",
                        "severity": "MEDIUM",
                        "message": f"High trading activity detected: {changes['transaction_summary']['total_transactions']} transactions in {period_hours} hours",
                    }
                )
                changes["risk_indicators"]["high_activity"] = True

            if (
                changes["transaction_summary"]["sells"]
                > changes["transaction_summary"]["buys"] * 2
            ):
                changes["alerts"].append(
                    {
                        "type": "SELLING_PRESSURE",
                        "severity": "HIGH",
                        "message": "Significant selling activity detected. Review your strategy.",
                    }
                )

            if len(changes["significant_trades"]) > 3:
                changes["alerts"].append(
                    {
                        "type": "LARGE_TRADES",
                        "severity": "MEDIUM",
                        "message": f"Multiple large trades detected: {len(changes['significant_trades'])} trades > 5% of portfolio",
                    }
                )

            # Generate insights
            if (
                changes["transaction_summary"]["buys"]
                > changes["transaction_summary"]["sells"]
            ):
                changes["insights"].append(
                    {
                        "type": "ACCUMULATION",
                        "message": "Net accumulation phase - more buying than selling",
                        "impact": "POSITIVE",
                    }
                )

            if changes["significant_trades"]:
                changes["insights"].append(
                    {
                        "type": "LARGE_TRADES",
                        "message": f"Made {len(changes['significant_trades'])} significant trades (>5% of portfolio)",
                        "impact": "NEUTRAL",
                    }
                )

            if len(changes["new_positions"]) > 0:
                changes["insights"].append(
                    {
                        "type": "DIVERSIFICATION",
                        "message": f"Added {len(changes['new_positions'])} new positions, increasing diversification",
                        "impact": "POSITIVE",
                    }
                )

            # Generate alert suggestions based on analysis
            changes["alert_suggestions"] = _generate_alert_suggestions(
                changes, current_portfolio
            )

            return changes

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze portfolio changes: {str(e)}"}


def _generate_alert_suggestions(changes: Dict, portfolio: Dict) -> List[Dict]:
    """Generate intelligent alert suggestions based on portfolio analysis"""
    suggestions = []

    try:
        # High activity suggestion
        if changes["risk_indicators"]["high_activity"]:
            suggestions.append(
                {
                    "alert_type": "VOLUME",
                    "priority": "MEDIUM",
                    "title": "High Activity Alert",
                    "description": "Set up volume alerts to monitor unusual trading activity",
                    "suggested_conditions": {
                        "condition": "unusual",
                        "threshold": "high",
                    },
                    "reasoning": "Recent high trading activity detected",
                }
            )

        # Portfolio value protection
        current_value = portfolio.get("total_value", 0)
        if current_value > 10000:  # Only for substantial portfolios
            suggestions.append(
                {
                    "alert_type": "PORTFOLIO_VALUE",
                    "priority": "HIGH",
                    "title": "Portfolio Value Protection",
                    "description": "Set up alerts to protect against significant portfolio losses",
                    "suggested_conditions": {
                        "condition": "below",
                        "target_value": current_value * 0.85,  # 15% drop protection
                    },
                    "reasoning": f"Current portfolio value ${current_value:.2f} needs downside protection",
                }
            )

        # Risk monitoring based on concentration
        allocation = portfolio.get("allocation", [])
        if allocation:
            max_allocation = max(alloc.get("percentage", 0) for alloc in allocation)
            if max_allocation > 40:  # High concentration
                suggestions.append(
                    {
                        "alert_type": "RISK",
                        "priority": "HIGH",
                        "title": "Concentration Risk Alert",
                        "description": "Monitor portfolio concentration to prevent over-exposure",
                        "suggested_conditions": {
                            "metric": "concentration",
                            "threshold": 70,
                        },
                        "reasoning": f"Largest position is {max_allocation:.1f}% of portfolio",
                    }
                )

        # Performance monitoring
        if changes["transaction_summary"]["total_transactions"] > 5:
            suggestions.append(
                {
                    "alert_type": "PERFORMANCE",
                    "priority": "MEDIUM",
                    "title": "Performance Tracking",
                    "description": "Monitor portfolio performance after recent trading activity",
                    "suggested_conditions": {
                        "metric": "return",
                        "condition": "below",
                        "threshold": -15,
                        "period": "7d",
                    },
                    "reasoning": "Active trading period - monitor performance impact",
                }
            )

        # Rebalancing alerts for diversified portfolios
        if len(allocation) > 3:  # Multi-asset portfolio
            suggestions.append(
                {
                    "alert_type": "REBALANCING",
                    "priority": "LOW",
                    "title": "Rebalancing Monitor",
                    "description": "Track allocation drift and rebalancing opportunities",
                    "suggested_conditions": {
                        "deviation_threshold": 10,
                        "target_allocations": {
                            f"{alloc['asset']}": alloc["percentage"]
                            for alloc in allocation[:5]  # Top 5 assets
                        },
                    },
                    "reasoning": "Diversified portfolio benefits from rebalancing monitoring",
                }
            )

        # Price alerts for significant positions
        for position in allocation[:3]:  # Top 3 positions
            if position.get("percentage", 0) > 15:  # Significant positions
                asset_name = position.get("asset", "Unknown")
                current_value = position.get("value", 0)

                # Suggest both upside and downside alerts
                suggestions.extend(
                    [
                        {
                            "alert_type": "PRICE",
                            "priority": "MEDIUM",
                            "title": f"{asset_name} Price Protection",
                            "description": f"Monitor {asset_name} price movements for major position",
                            "suggested_conditions": {
                                "asset_symbol": asset_name.split(" ")[
                                    0
                                ],  # Extract symbol
                                "asset_chain": (
                                    asset_name.split("(")[1].replace(")", "")
                                    if "(" in asset_name
                                    else "ETH"
                                ),
                                "condition": "below",
                                "target_price": current_value * 0.85,  # 15% drop alert
                            },
                            "reasoning": f"{asset_name} represents {position['percentage']:.1f}% of portfolio",
                        },
                        {
                            "alert_type": "PRICE",
                            "priority": "LOW",
                            "title": f"{asset_name} Profit Target",
                            "description": f"Track {asset_name} reaching profit targets",
                            "suggested_conditions": {
                                "asset_symbol": asset_name.split(" ")[0],
                                "asset_chain": (
                                    asset_name.split("(")[1].replace(")", "")
                                    if "(" in asset_name
                                    else "ETH"
                                ),
                                "condition": "above",
                                "target_price": current_value * 1.25,  # 25% gain alert
                            },
                            "reasoning": f"Set profit-taking alerts for major position",
                        },
                    ]
                )

        # Volatility alerts for active portfolios
        if changes["transaction_summary"]["total_transactions"] > 10:
            suggestions.append(
                {
                    "alert_type": "VOLATILITY",
                    "priority": "MEDIUM",
                    "title": "Volatility Monitor",
                    "description": "Track portfolio volatility during active trading periods",
                    "suggested_conditions": {
                        "metric": "portfolio_volatility",
                        "threshold": 25,
                        "period": "24h",
                    },
                    "reasoning": "High trading activity may increase volatility",
                }
            )

        return suggestions

    except Exception as e:
        logger.error(f"Error generating alert suggestions: {e}")
        return []


@tool
def get_alert_recommendations(user_id: str) -> Dict:
    """
    Get personalized alert recommendations based on portfolio analysis.

    Args:
        user_id (str): User identifier

    Returns:
        Dict: Personalized alert recommendations with setup guidance
    """
    try:
        # Get current portfolio data
        from tools.tools_crypto_portfolios import get_user_portfolio_summary

        portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

        if isinstance(portfolio, str) or "error" in portfolio:
            return {"error": "Unable to analyze portfolio for recommendations"}

        # Get recent changes analysis
        changes = analyze_portfolio_changes.invoke(
            {"user_id": user_id, "period_hours": 72}
        )

        if isinstance(changes, str) or "error" in changes:
            changes = {"alert_suggestions": []}

        # Get existing alerts to avoid duplicates
        existing_alerts = get_portfolio_alerts.invoke({"user_id": user_id})
        existing_types = []
        if isinstance(existing_alerts, dict) and "alerts" in existing_alerts:
            existing_types = [
                alert["alert_type"] for alert in existing_alerts["alerts"]
            ]

        # Generate comprehensive recommendations
        recommendations = {
            "user_id": user_id,
            "analysis_date": datetime.utcnow().isoformat(),
            "portfolio_summary": {
                "total_value": portfolio.get("total_value", 0),
                "asset_count": portfolio.get("asset_count", 0),
                "largest_position": 0,
                "risk_level": "UNKNOWN",
            },
            "priority_alerts": [],
            "optional_alerts": [],
            "setup_guidance": [],
            "existing_alerts": len(existing_types),
        }

        # Calculate portfolio characteristics
        allocation = portfolio.get("allocation", [])
        if allocation:
            largest_position = max(alloc.get("percentage", 0) for alloc in allocation)
            recommendations["portfolio_summary"]["largest_position"] = largest_position

            # Determine risk level
            if largest_position > 50:
                recommendations["portfolio_summary"]["risk_level"] = "HIGH"
            elif largest_position > 30:
                recommendations["portfolio_summary"]["risk_level"] = "MEDIUM"
            else:
                recommendations["portfolio_summary"]["risk_level"] = "LOW"

        # Priority recommendations (essential alerts)
        if (
            "PORTFOLIO_VALUE" not in existing_types
            and portfolio.get("total_value", 0) > 1000
        ):
            recommendations["priority_alerts"].append(
                {
                    "alert_type": "PORTFOLIO_VALUE",
                    "title": "Portfolio Protection Alert",
                    "importance": "CRITICAL",
                    "description": "Protect against significant portfolio losses",
                    "setup_steps": [
                        "Choose a protection threshold (suggested: 15-20% below current value)",
                        "Set notification methods (email + SMS recommended)",
                        "Consider setting multiple thresholds for different severity levels",
                    ],
                    "suggested_config": {
                        "alert_name": "Portfolio Loss Protection",
                        "conditions": {
                            "condition": "below",
                            "target_value": portfolio.get("total_value", 0) * 0.85,
                        },
                        "notification_methods": ["EMAIL", "SMS"],
                    },
                }
            )

        if "RISK" not in existing_types and recommendations["portfolio_summary"][
            "risk_level"
        ] in ["MEDIUM", "HIGH"]:
            recommendations["priority_alerts"].append(
                {
                    "alert_type": "RISK",
                    "title": "Concentration Risk Monitor",
                    "importance": "HIGH",
                    "description": "Monitor portfolio concentration to prevent over-exposure",
                    "setup_steps": [
                        "Set concentration threshold (suggested: 60-70%)",
                        "Choose assets to monitor",
                        "Enable regular monitoring notifications",
                    ],
                    "suggested_config": {
                        "alert_name": "High Concentration Warning",
                        "conditions": {"metric": "concentration", "threshold": 65},
                        "notification_methods": ["EMAIL"],
                    },
                }
            )

        # Optional recommendations (nice to have)
        if "PERFORMANCE" not in existing_types:
            recommendations["optional_alerts"].append(
                {
                    "alert_type": "PERFORMANCE",
                    "title": "Performance Tracking",
                    "importance": "MEDIUM",
                    "description": "Monitor portfolio performance over various time periods",
                    "setup_steps": [
                        "Choose performance metric (return, Sharpe ratio)",
                        "Set time period (daily, weekly, monthly)",
                        "Define acceptable performance thresholds",
                    ],
                    "suggested_config": {
                        "alert_name": "Weekly Performance Check",
                        "conditions": {
                            "metric": "return",
                            "condition": "below",
                            "threshold": -10,
                            "period": "7d",
                        },
                        "notification_methods": ["EMAIL"],
                    },
                }
            )

        if "REBALANCING" not in existing_types and len(allocation) > 2:
            recommendations["optional_alerts"].append(
                {
                    "alert_type": "REBALANCING",
                    "title": "Portfolio Rebalancing",
                    "importance": "LOW",
                    "description": "Maintain optimal asset allocation automatically",
                    "setup_steps": [
                        "Define target allocation percentages",
                        "Set deviation tolerance (suggested: 5-10%)",
                        "Choose rebalancing frequency",
                    ],
                    "suggested_config": {
                        "alert_name": "Rebalancing Needed",
                        "conditions": {
                            "deviation_threshold": 8,
                            "target_allocations": {
                                alloc["asset"]: alloc["percentage"]
                                for alloc in allocation[:5]
                            },
                        },
                        "notification_methods": ["EMAIL"],
                    },
                }
            )

        # Price alerts for major positions
        for i, position in enumerate(allocation[:2]):  # Top 2 positions
            if position.get("percentage", 0) > 10:  # Significant positions only
                asset_name = position.get("asset", "Unknown")
                symbol = asset_name.split(" ")[0] if " " in asset_name else asset_name

                if (
                    "PRICE" not in existing_types
                    or len([a for a in existing_types if a == "PRICE"]) < 3
                ):
                    recommendations["optional_alerts"].append(
                        {
                            "alert_type": "PRICE",
                            "title": f"{symbol} Price Alerts",
                            "importance": "MEDIUM",
                            "description": f"Monitor price movements for {symbol} (major position)",
                            "setup_steps": [
                                f"Set price thresholds for {symbol}",
                                "Choose alert conditions (above/below/crossing)",
                                "Consider both profit targets and stop-loss levels",
                            ],
                            "suggested_config": {
                                "alert_name": f"{symbol} Price Monitor",
                                "conditions": {
                                    "asset_symbol": symbol,
                                    "asset_chain": "ETH",  # Default, should be determined dynamically
                                    "condition": "below",
                                    "target_price": position.get("value", 1000)
                                    * 0.85,  # 15% drop
                                },
                                "notification_methods": ["EMAIL", "PUSH"],
                            },
                        }
                    )

        # Setup guidance based on portfolio characteristics
        if recommendations["portfolio_summary"]["risk_level"] == "HIGH":
            recommendations["setup_guidance"].extend(
                [
                    "🚨 High-risk portfolio detected - prioritize protection alerts",
                    "💡 Consider diversifying your holdings to reduce concentration risk",
                    "⚡ Set up multiple alert thresholds for different risk levels",
                    "📱 Enable SMS notifications for critical alerts",
                ]
            )
        elif recommendations["portfolio_summary"]["risk_level"] == "MEDIUM":
            recommendations["setup_guidance"].extend(
                [
                    "⚖️ Balanced portfolio - focus on performance monitoring",
                    "📊 Set up regular rebalancing alerts to maintain allocation",
                    "🎯 Consider profit-taking alerts for major positions",
                ]
            )
        else:
            recommendations["setup_guidance"].extend(
                [
                    "✅ Well-diversified portfolio detected",
                    "📈 Focus on performance tracking and growth alerts",
                    "🔄 Consider growth-oriented alert strategies",
                ]
            )

        # General setup guidance
        recommendations["setup_guidance"].extend(
            [
                "📧 Always include email notifications as a backup",
                "⏰ Test alerts with small thresholds before setting final values",
                "🔄 Review and adjust alert thresholds monthly",
                "📱 Use push notifications for time-sensitive alerts",
            ]
        )

        # Add suggestions from portfolio changes analysis
        if "alert_suggestions" in changes:
            for suggestion in changes["alert_suggestions"][:3]:  # Top 3 suggestions
                if suggestion["alert_type"] not in existing_types:
                    recommendations["optional_alerts"].append(
                        {
                            "alert_type": suggestion["alert_type"],
                            "title": suggestion["title"],
                            "importance": suggestion["priority"],
                            "description": suggestion["description"],
                            "reasoning": suggestion["reasoning"],
                            "suggested_config": {
                                "alert_name": suggestion["title"],
                                "conditions": suggestion["suggested_conditions"],
                                "notification_methods": ["EMAIL"],
                            },
                        }
                    )

        return recommendations

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to get alert recommendations: {str(e)}"}


@tool



# ========================================
# Database Migration Helper (for production)
# ========================================


def create_alert_tables():
    """
    Create alert-related database tables.
    This would be part of a database migration in production.
    """
    from sqlalchemy import create_engine, MetaData

    # This is a placeholder for the actual database migration
    # In production, you would:
    # 1. Add the alert models to the main model.py file
    # 2. Create proper Alembic migrations
    # 3. Run database migrations

    logger.info("Alert tables creation would be handled by database migrations")


# ========================================
# Export all tools
# ========================================

tools = [
    # Core alert management
    create_portfolio_alert,
    get_portfolio_alerts,
    update_portfolio_alert,
    delete_portfolio_alert,
    # Alert monitoring and checking
    get_alert_history,
    # Enhanced portfolio analysis
    analyze_portfolio_changes,
    # Recommendations and guidance
    get_alert_recommendations,
]
