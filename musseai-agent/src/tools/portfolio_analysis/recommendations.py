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


tools = [
    get_rebalancing_recommendations,
    find_investment_opportunities,
    analyze_tax_implications,
]
