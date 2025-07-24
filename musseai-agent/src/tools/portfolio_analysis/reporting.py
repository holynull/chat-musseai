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

from tools.portfolio_analysis.portfolio_overview import analyze_portfolio_overview
from tools.portfolio_analysis.portfolio_overview import portfolio_health_check
from tools.portfolio_analysis.performance_analysis import analyze_portfolio_performance
from tools.portfolio_analysis.risk_analysis import analyze_portfolio_risk
from tools.portfolio_analysis.recommendations import analyze_tax_implications


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


tools = [generate_portfolio_report]
