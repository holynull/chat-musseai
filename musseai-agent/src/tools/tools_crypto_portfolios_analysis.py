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

from tools.portfolio_analysis.portfolio_overview import (
    tools as tools_portfolio_overview,
)
from tools.portfolio_analysis.performance_analysis import (
    tools as tools_performance_analysis,
)
from tools.portfolio_analysis.risk_analysis import tools as tools_risk_analysis
from tools.portfolio_analysis.recommendations import tools as tools_recommendations
from tools.portfolio_analysis.market_analysis import tools as tools_market_analysis
from tools.portfolio_analysis.reporting import tools as tools_reporting
from tools.portfolio_analysis.alerts_monitoring import tools as tools_alert_monitoring


@tool
def get_portfolio_allocation(user_id: str, group_by: str = "asset") -> List[Dict]:
    """
    Get portfolio allocation breakdown.

    Args:
        user_id (str): User identifier
        group_by (str): Grouping method ('asset', 'chain', 'source_type')

    Returns:
        List[Dict]: Allocation breakdown with percentages
    """
    try:
        with get_db() as db:
            # Get user's active sources
            sources = (
                db.query(PortfolioSourceModel)
                .filter(
                    PortfolioSourceModel.user_id == user_id,
                    PortfolioSourceModel.is_active == True,
                )
                .all()
            )

            source_ids = [s.source_id for s in sources]

            if not source_ids:
                return []

            # Get all positions with values
            positions = (
                db.query(PositionModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            # Calculate allocations based on grouping
            allocations = {}
            total_value = Decimal("0")

            for position in positions:
                if not position.last_price:
                    continue

                value = position.quantity * position.last_price
                total_value += value

                # Determine grouping key
                if group_by == "asset":
                    key = f"{position.asset.symbol} ({position.asset.chain})"
                    metadata = {
                        "symbol": position.asset.symbol,
                        "chain": position.asset.chain,
                        "name": position.asset.name,
                    }
                elif group_by == "chain":
                    key = position.asset.chain
                    metadata = {"chain": position.asset.chain}
                elif group_by == "source_type":
                    source = next(
                        s for s in sources if s.source_id == position.source_id
                    )
                    key = source.source_type.value
                    metadata = {"source_type": source.source_type.value}
                else:
                    key = "Unknown"
                    metadata = {}

                if key not in allocations:
                    allocations[key] = {
                        "key": key,
                        "value": Decimal("0"),
                        "quantity": Decimal("0"),
                        "metadata": metadata,
                    }

                allocations[key]["value"] += value
                allocations[key]["quantity"] += position.quantity

            # Convert to list with percentages
            result = []
            if total_value > 0:
                for key, data in allocations.items():
                    result.append(
                        {
                            "group": key,
                            "value": float(data["value"]),
                            "percentage": float((data["value"] / total_value) * 100),
                            "metadata": data["metadata"],
                        }
                    )

            # Sort by value descending
            result.sort(key=lambda x: x["value"], reverse=True)

            return result

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return f"Failed to get portfolio allocation: {str(e)}"


tools = (
    tools_portfolio_overview  # Portfolio Overview
    + tools_performance_analysis  # Performance Analysis
    + tools_risk_analysis  # Risk Analysis
    + tools_recommendations  # Recommendations
    + tools_market_analysis  # Market Analysis
    + tools_reporting  # Reporting
    + tools_alert_monitoring  # Alerts and Monitoring
)
