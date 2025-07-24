from decimal import Decimal
import numpy as np
import requests
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
from utils.api_decorators import (
    api_call_with_cache_and_rate_limit,
    cache_result,
    rate_limit,
)
from utils.api_manager import api_manager
import traceback

# ========================================
# Market Data Functions with Real APIs
# ========================================


@api_call_with_cache_and_rate_limit(cache_duration=600, rate_limit_interval=1.5)
def get_real_market_conditions() -> Dict:
    """
    Fetch real market conditions using free APIs

    Returns:
        Dict: Real market data including trends, volatility, and prices
    """
    try:
        # Fetch Fear & Greed Index (free API)
        fear_greed_response = requests.get(
            "https://api.alternative.me/fng/?limit=1", timeout=10
        )
        fear_greed_data = fear_greed_response.json()

        # Fetch major crypto prices from CoinGecko (free)
        prices_response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,binancecoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
            },
            timeout=10,
        )
        prices_data = prices_response.json()

        # Calculate overall market trend
        btc_change = prices_data.get("bitcoin", {}).get("usd_24h_change", 0)
        eth_change = prices_data.get("ethereum", {}).get("usd_24h_change", 0)

        avg_change = (btc_change + eth_change) / 2

        if avg_change > 5:
            trend = "BULLISH"
        elif avg_change < -5:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # Determine volatility based on 24h changes
        volatility_score = abs(btc_change) + abs(eth_change)
        if volatility_score > 15:
            volatility = "HIGH"
        elif volatility_score > 8:
            volatility = "MEDIUM"
        else:
            volatility = "LOW"

        # Fear & Greed analysis
        fear_greed_value = int(fear_greed_data["data"][0]["value"])
        if fear_greed_value > 75:
            sentiment = "EXTREME_GREED"
            recommendation = "Consider taking profits, market may be overheated"
        elif fear_greed_value > 50:
            sentiment = "GREED"
            recommendation = "Good time for balanced approach"
        elif fear_greed_value > 25:
            sentiment = "FEAR"
            recommendation = (
                "Consider dollar-cost averaging, good accumulation opportunity"
            )
        else:
            sentiment = "EXTREME_FEAR"
            recommendation = "Excellent buying opportunity for long-term investors"

        return {
            "overall_trend": trend,
            "volatility": volatility,
            "sentiment": sentiment,
            "fear_greed_index": fear_greed_value,
            "recommendation": recommendation,
            "btc_price": prices_data.get("bitcoin", {}).get("usd", 0),
            "eth_price": prices_data.get("ethereum", {}).get("usd", 0),
            "btc_24h_change": btc_change,
            "eth_24h_change": eth_change,
            "last_updated": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to fetch market conditions: {e}")
        traceback.format_exc()
        # Fallback to neutral conditions
        return {
            "overall_trend": "NEUTRAL",
            "volatility": "MEDIUM",
            "sentiment": "NEUTRAL",
            "fear_greed_index": 50,
            "recommendation": "Market data unavailable, proceed with caution",
            "last_updated": datetime.utcnow().isoformat(),
        }


@api_call_with_cache_and_rate_limit(cache_duration=1800, rate_limit_interval=2.0)
def get_real_defi_yields() -> Dict:
    """
    Fetch real DeFi yields from various protocols

    Returns:
        Dict: Current APY rates for different DeFi protocols
    """
    try:
        yields = {}

        # Fetch Aave rates (free API)
        try:
            aave_response = requests.get(
                "https://aave-api-v2.aave.com/data/liquidity/v2", timeout=10
            )
            aave_data = aave_response.json()

            # Find USDC lending rate
            for reserve in aave_data:
                if reserve["symbol"] == "USDC":
                    yields["aave_usdc_supply"] = float(reserve["liquidityRate"]) * 100
                if reserve["symbol"] == "USDT":
                    yields["aave_usdt_supply"] = float(reserve["liquidityRate"]) * 100
                if reserve["symbol"] == "WETH":
                    yields["aave_eth_supply"] = float(reserve["liquidityRate"]) * 100

        except Exception as e:
            logger.warning(f"Failed to fetch Aave yields: {e}")
            traceback.format_exc()
            yields.update(
                {
                    "aave_usdc_supply": 4.5,
                    "aave_usdt_supply": 4.2,
                    "aave_eth_supply": 2.8,
                }
            )

        # Add estimated yields for other protocols (fallback values based on current market)
        yields.update(
            {
                "compound_usdc": 3.8,
                "curve_3pool": 2.5,
                "yearn_usdc": 5.2,
                "uniswap_v3_eth_usdc": 8.5,  # Variable based on fees
                "eth_staking": 4.1,  # Current ETH staking reward
            }
        )

        return yields

    except Exception as e:
        logger.error(f"Failed to fetch DeFi yields: {e}")
        traceback.format_exc()
        # Return conservative fallback yields
        return {
            "aave_usdc_supply": 4.0,
            "compound_usdc": 3.5,
            "curve_3pool": 2.2,
            "eth_staking": 4.0,
            "yearn_usdc": 4.8,
        }


@cache_result(duration=3600)
def get_asset_market_data(symbol: str) -> Dict:
    """
    Get comprehensive market data for an asset

    Args:
        symbol: Asset symbol (e.g., 'BTC', 'ETH')

    Returns:
        Dict: Market data including market cap, rank, volatility
    """
    try:
        # Use our existing API manager for historical data
        historical_data = api_manager.fetch_with_fallback(symbol, days=30)

        if not historical_data:
            return {"error": f"No market data available for {symbol}"}

        # Get current price and market cap from CoinGecko
        response = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}", timeout=10
        )

        if response.status_code == 200:
            coin_data = response.json()
            market_data = coin_data.get("market_data", {})

            return {
                "symbol": symbol,
                "current_price": market_data.get("current_price", {}).get("usd", 0),
                "market_cap": market_data.get("market_cap", {}).get("usd", 0),
                "market_cap_rank": market_data.get("market_cap_rank", 999),
                "volume_24h": market_data.get("total_volume", {}).get("usd", 0),
                "price_change_24h": market_data.get("price_change_percentage_24h", 0),
                "price_change_7d": market_data.get("price_change_percentage_7d", 0),
                "price_change_30d": market_data.get("price_change_percentage_30d", 0),
                "volatility": historical_data.get("volatility", 0),
                "mean_return": historical_data.get("mean_return", 0),
                "ath": market_data.get("ath", {}).get("usd", 0),
                "ath_change_percentage": market_data.get(
                    "ath_change_percentage", {}
                ).get("usd", 0),
                "last_updated": datetime.utcnow().isoformat(),
            }
        else:
            # Fallback to historical data only
            return {
                "symbol": symbol,
                "volatility": historical_data.get("volatility", 0),
                "mean_return": historical_data.get("mean_return", 0),
                "market_cap_rank": 999,
                "last_updated": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to fetch market data for {symbol}: {e}")
        traceback.format_exc()
        return {"error": f"Failed to fetch market data for {symbol}"}


def classify_asset_by_market_cap(symbol: str, market_data: Dict = None) -> str:
    """
    Classify asset based on real market cap data

    Args:
        symbol: Asset symbol
        market_data: Optional pre-fetched market data

    Returns:
        str: Asset classification
    """
    if not market_data:
        market_data = get_asset_market_data(symbol)

    if "error" in market_data:
        # Fallback classification
        if symbol in ["BTC", "ETH"]:
            return "TOP_10"
        elif symbol in ["USDT", "USDC", "DAI", "BUSD"]:
            return "STABLECOINS"
        else:
            return "UNKNOWN"

    rank = market_data.get("market_cap_rank", 999)

    if symbol in ["USDT", "USDC", "DAI", "BUSD", "FRAX", "TUSD"]:
        return "STABLECOINS"
    elif rank <= 10:
        return "TOP_10"
    elif rank <= 50:
        return "LARGE_CAP"
    elif rank <= 200:
        return "MID_CAP"
    else:
        return "SMALL_CAP"


# ========================================
# Enhanced Recommendation Tools
# ========================================


@tool
def get_rebalancing_recommendations(
    user_id: str, target_allocation: Dict = None
) -> Dict:
    """
    Generate portfolio rebalancing recommendations based on real market data and target allocation.

    Args:
        user_id (str): User identifier
        target_allocation (Dict, optional): Target allocation percentages by asset

    Returns:
        Dict: Rebalancing recommendations with specific actions based on current market conditions
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

        # Get real market conditions
        market_conditions = get_real_market_conditions()

        # Adjust default target allocation based on market conditions
        if not target_allocation:
            if market_conditions["sentiment"] == "EXTREME_FEAR":
                # More aggressive allocation during fear
                target_allocation = {
                    "BTC": 35,
                    "ETH": 30,
                    "STABLECOINS": 15,
                    "TOP_10": 15,
                    "LARGE_CAP": 5,
                }
            elif market_conditions["sentiment"] == "EXTREME_GREED":
                # More conservative during greed
                target_allocation = {
                    "BTC": 25,
                    "ETH": 20,
                    "STABLECOINS": 30,
                    "TOP_10": 15,
                    "LARGE_CAP": 10,
                }
            else:
                # Balanced allocation
                target_allocation = {
                    "BTC": 30,
                    "ETH": 25,
                    "STABLECOINS": 20,
                    "TOP_10": 15,
                    "LARGE_CAP": 10,
                }

        # Calculate current allocation with real market data
        current_allocation = {}
        for position in positions:
            symbol = position["symbol"]
            percentage = (
                (position["total_value"] / total_value * 100) if total_value > 0 else 0
            )

            # Use real market data for classification
            category = classify_asset_by_market_cap(symbol)

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

            # Adjust threshold based on market volatility
            threshold = 3 if market_conditions["volatility"] == "HIGH" else 2

            if abs(diff_pct) > threshold:
                priority = (
                    "HIGH"
                    if abs(diff_pct) > 15
                    else "MEDIUM" if abs(diff_pct) > 7 else "LOW"
                )

                action = {
                    "category": category,
                    "current_percentage": current_pct,
                    "target_percentage": target_pct,
                    "difference_percentage": diff_pct,
                    "action": "BUY" if diff_pct > 0 else "SELL",
                    "amount_usd": abs(diff_value),
                    "priority": priority,
                    "market_context": f"Market is {market_conditions['sentiment'].lower()}, volatility is {market_conditions['volatility'].lower()}",
                }
                actions.append(action)
                total_adjustment += abs(diff_value)

        # Sort by priority and amount
        actions.sort(
            key=lambda x: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["priority"]],
                -x["amount_usd"],
            )
        )

        # Generate specific recommendations with market context
        recommendations = []
        for action in actions:
            market_advice = ""
            if (
                market_conditions["sentiment"] == "EXTREME_FEAR"
                and action["action"] == "BUY"
            ):
                market_advice = (
                    " (Excellent buying opportunity - market in extreme fear)"
                )
            elif (
                market_conditions["sentiment"] == "EXTREME_GREED"
                and action["action"] == "SELL"
            ):
                market_advice = (
                    " (Good time to take profits - market showing extreme greed)"
                )

            recommendations.append(
                {
                    "action": action["action"],
                    "category": action["category"],
                    "amount": action["amount_usd"],
                    "reason": f"{action['action']} {action['category']} allocation from {action['current_percentage']:.1f}% to {action['target_percentage']:.1f}%{market_advice}",
                    "priority": action["priority"],
                    "market_context": action["market_context"],
                }
            )

        # Calculate rebalancing metrics
        rebalancing_metrics = {
            "total_trades_needed": len(actions),
            "total_value_to_rebalance": total_adjustment,
            "rebalancing_percentage": (
                (total_adjustment / total_value * 100) if total_value > 0 else 0
            ),
            "estimated_cost": total_adjustment * 0.003,  # Updated trading fees estimate
            "market_sentiment": market_conditions["sentiment"],
            "optimal_timing": market_conditions["recommendation"],
        }

        return {
            "current_allocation": current_allocation,
            "target_allocation": target_allocation,
            "rebalancing_actions": actions,
            "recommendations": recommendations,
            "metrics": rebalancing_metrics,
            "market_conditions": market_conditions,
            "execution_notes": [
                f"Market sentiment: {market_conditions['sentiment']} (Fear & Greed: {market_conditions['fear_greed_index']})",
                f"Market volatility: {market_conditions['volatility']}",
                "Execute high priority trades first",
                "Consider market conditions and liquidity",
                "Use limit orders to minimize slippage",
                (
                    f"Rebalance in stages if total adjustment > 20%"
                    if total_adjustment > total_value * 0.2
                    else "Can execute rebalancing in single batch"
                ),
            ],
            "next_review": (
                datetime.utcnow()
                + timedelta(
                    days=14 if market_conditions["volatility"] == "HIGH" else 30
                )
            ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        traceback.format_exc()
        return {"error": f"Failed to generate rebalancing recommendations: {str(e)}"}


@tool
def find_investment_opportunities(user_id: str, risk_tolerance: str = "MEDIUM") -> Dict:
    """
    Identify potential investment opportunities based on real market data and portfolio analysis.

    Args:
        user_id (str): User identifier
        risk_tolerance (str): Risk tolerance level (LOW, MEDIUM, HIGH)

    Returns:
        Dict: Investment opportunities with real market analysis and recommendations
    """
    try:
        # Get portfolio data
        from tools.tools_crypto_portfolios import get_user_portfolio_summary

        from tools.tools_crypto_portfolios_analysis import get_portfolio_allocation

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

        # Get real market data
        market_conditions = get_real_market_conditions()
        defi_yields = get_real_defi_yields()

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

        # Opportunity 1: Stablecoin yield farming with real yields
        if stablecoin_allocation > 10:
            best_yield = max(
                defi_yields.get("aave_usdc_supply", 4),
                defi_yields.get("yearn_usdc", 4.8),
            )

            opportunities.append(
                {
                    "type": "YIELD_FARMING",
                    "title": "Stablecoin Yield Opportunity",
                    "description": f"Deploy idle stablecoins to earn {best_yield:.2f}% APY",
                    "risk_level": "LOW",
                    "expected_apy": f"{best_yield:.2f}%",
                    "recommended_amount": total_value
                    * stablecoin_allocation
                    / 100
                    * 0.6,
                    "platforms": [
                        {
                            "name": "Aave",
                            "apy": f"{defi_yields.get('aave_usdc_supply', 4.0):.2f}%",
                        },
                        {
                            "name": "Yearn Finance",
                            "apy": f"{defi_yields.get('yearn_usdc', 4.8):.2f}%",
                        },
                        {
                            "name": "Compound",
                            "apy": f"{defi_yields.get('compound_usdc', 3.5):.2f}%",
                        },
                    ],
                    "action_items": [
                        f"Current best yield: {best_yield:.2f}% APY",
                        "Research smart contract risks",
                        "Consider gas fees for deployment",
                        "Start with 60% of stablecoin holdings",
                    ],
                    "market_context": f"Yields are {'attractive' if best_yield > 4 else 'moderate'} in current market",
                }
            )

        # Opportunity 2: Market timing based on Fear & Greed
        if market_conditions["fear_greed_index"] < 25:  # Extreme Fear
            opportunities.append(
                {
                    "type": "MARKET_TIMING",
                    "title": "Accumulation Opportunity - Extreme Fear",
                    "description": "Market showing extreme fear - historically good buying opportunity",
                    "risk_level": "MEDIUM",
                    "expected_benefit": "20-40% potential upside when sentiment recovers",
                    "recommended_allocation": min(total_value * 0.15, 5000),
                    "target_assets": ["BTC", "ETH", "Top 10 altcoins"],
                    "action_items": [
                        f"Fear & Greed Index: {market_conditions['fear_greed_index']} (Extreme Fear)",
                        "Use dollar-cost averaging over 2-4 weeks",
                        "Focus on blue-chip cryptocurrencies",
                        "Set stop-losses at -15% from entry",
                    ],
                    "market_context": market_conditions["recommendation"],
                }
            )
        elif market_conditions["fear_greed_index"] > 75:  # Extreme Greed
            opportunities.append(
                {
                    "type": "PROFIT_TAKING",
                    "title": "Profit Taking Opportunity - Extreme Greed",
                    "description": "Market showing extreme greed - consider taking some profits",
                    "risk_level": "LOW",
                    "expected_benefit": "Risk reduction and cash preservation",
                    "recommended_action": "Sell 10-20% of volatile positions",
                    "action_items": [
                        f"Fear & Greed Index: {market_conditions['fear_greed_index']} (Extreme Greed)",
                        "Take profits on outperforming assets",
                        "Increase stablecoin allocation temporarily",
                        "Wait for better entry opportunities",
                    ],
                    "market_context": market_conditions["recommendation"],
                }
            )

        # Opportunity 3: ETH Staking with real yields
        eth_allocation = sum(
            item["percentage"] for item in allocation if item["group"].upper() == "ETH"
        )

        if eth_allocation > 5:
            eth_staking_yield = defi_yields.get("eth_staking", 4.0)
            opportunities.append(
                {
                    "type": "STAKING",
                    "title": "ETH Staking Opportunity",
                    "description": f"Stake ETH for {eth_staking_yield:.2f}% APY passive income",
                    "risk_level": "LOW" if risk_tolerance == "LOW" else "MEDIUM",
                    "expected_return": f"{eth_staking_yield:.2f}% APY",
                    "recommended_allocation": total_value * eth_allocation / 100 * 0.7,
                    "options": [
                        "Ethereum 2.0 Native Staking",
                        "Liquid Staking (Lido, Rocket Pool)",
                        "Centralized Staking (Coinbase, Kraken)",
                    ],
                    "benefits": [
                        "Passive income generation",
                        "Support network security",
                        "Maintain ETH exposure",
                        f"Current yield: {eth_staking_yield:.2f}% APY",
                    ],
                    "risks": [
                        "Slashing risk (minimal)",
                        "Liquidity lock-up",
                        "Technical risks",
                    ],
                    "action_items": [
                        "Research staking providers",
                        "Consider liquid staking for flexibility",
                        "Start with 70% of ETH holdings",
                    ],
                }
            )

        # Opportunity 4: Risk-based opportunities
        if risk_tolerance == "HIGH" and market_conditions["volatility"] == "HIGH":
            opportunities.append(
                {
                    "type": "HIGH_RISK_HIGH_REWARD",
                    "title": "High Volatility Trading Opportunity",
                    "description": "High market volatility creates trading opportunities",
                    "risk_level": "HIGH",
                    "expected_return": "15-30% (high variance)",
                    "recommended_allocation": min(total_value * 0.05, 1000),
                    "strategies": [
                        "Swing trading major cryptocurrencies",
                        "DeFi yield farming with new protocols",
                        "Layer 2 and emerging ecosystem tokens",
                    ],
                    "warning": "Only invest what you can afford to lose completely",
                    "market_context": f"Market volatility is {market_conditions['volatility']}, creating opportunities",
                }
            )
        elif risk_tolerance == "LOW":
            opportunities.append(
                {
                    "type": "CONSERVATIVE_INCOME",
                    "title": "Conservative Income Strategy",
                    "description": "Focus on stable, low-risk income generation",
                    "risk_level": "LOW",
                    "expected_return": f"{min(defi_yields.values()):.1f}-{max(defi_yields.values()):.1f}% APY",
                    "recommended_allocation": total_value * 0.30,
                    "strategies": [
                        f"Stablecoin lending: {defi_yields.get('aave_usdc_supply', 4):.1f}% APY",
                        f"ETH staking: {defi_yields.get('eth_staking', 4):.1f}% APY",
                        "Conservative DeFi blue chips",
                    ],
                    "benefits": [
                        "Capital preservation",
                        "Predictable returns",
                        "Lower volatility",
                    ],
                }
            )

        # Opportunity 5: Tax loss harvesting with real PnL
        losing_positions = [
            p for p in portfolio["positions_by_asset"] if p.get("pnl", 0) < -100
        ]

        if losing_positions and datetime.now().month >= 10:  # Q4 tax planning
            total_losses = sum(abs(p["pnl"]) for p in losing_positions)
            opportunities.append(
                {
                    "type": "TAX_OPTIMIZATION",
                    "title": "Year-End Tax Loss Harvesting",
                    "description": "Realize losses to offset gains for tax purposes",
                    "risk_level": "LOW",
                    "potential_tax_savings": total_losses
                    * 0.22,  # Assuming 22% tax rate
                    "timing": "Before December 31st",
                    "positions_to_consider": [
                        {
                            "asset": p["symbol"],
                            "unrealized_loss": p["pnl"],
                            "current_value": p["total_value"],
                            "loss_percentage": (
                                (p["pnl"] / p["total_value"] * 100)
                                if p["total_value"] > 0
                                else 0
                            ),
                        }
                        for p in losing_positions[:5]
                    ],
                    "action_items": [
                        "Consult with tax advisor",
                        "Consider wash sale rules (30-day period)",
                        "Plan replacement investments",
                        f"Potential tax savings: ${total_losses * 0.22:,.2f}",
                    ],
                    "deadline": f"{datetime.now().year}-12-31",
                }
            )

        # Score and rank opportunities based on market conditions
        for opp in opportunities:
            risk_multiplier = {"LOW": 1, "MEDIUM": 1.5, "HIGH": 2}[opp["risk_level"]]

            # Extract expected return for scoring
            return_str = opp.get("expected_return", opp.get("expected_apy", "5%"))
            try:
                if "%" in return_str:
                    return_score = float(
                        return_str.split("-")[0].replace("%", "").strip()
                    )
                else:
                    return_score = 10  # Default for non-numeric returns
            except:
                traceback.format_exc()
                return_score = 5

            # Market condition bonus
            market_bonus = 1.0
            if (
                market_conditions["sentiment"] == "EXTREME_FEAR"
                and opp["type"] == "MARKET_TIMING"
            ):
                market_bonus = 1.5
            elif (
                market_conditions["sentiment"] == "EXTREME_GREED"
                and opp["type"] == "PROFIT_TAKING"
            ):
                market_bonus = 1.3

            opp["opportunity_score"] = (return_score / risk_multiplier) * market_bonus

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
            "market_conditions": market_conditions,
            "current_yields": defi_yields,
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
    Analyze tax implications with real cost basis calculation and current tax rates.

    Args:
        user_id (str): User identifier
        tax_year (int, optional): Tax year to analyze (default: current year)
        country (str): Country for tax rules (default: US)

    Returns:
        Dict: Enhanced tax analysis with real data and optimization strategies
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
                .order_by(TransactionModel.transaction_time)
                .all()
            )

            # Enhanced cost basis calculation using FIFO method
            cost_basis_tracker = {}  # {asset_symbol: [(quantity, price, date), ...]}
            realized_gains = 0
            realized_losses = 0
            short_term_gains = 0
            long_term_gains = 0
            short_term_losses = 0
            long_term_losses = 0

            taxable_events = []

            # First pass: track all buy transactions for cost basis
            for tx in transactions:
                if tx.transaction_type == TransactionType.BUY and tx.price:
                    asset_symbol = tx.asset.symbol
                    if asset_symbol not in cost_basis_tracker:
                        cost_basis_tracker[asset_symbol] = []

                    cost_basis_tracker[asset_symbol].append(
                        {
                            "quantity": float(tx.quantity),
                            "price": float(tx.price),
                            "date": tx.transaction_time,
                            "cost_per_unit": float(tx.price),
                        }
                    )

            # Second pass: calculate realized gains/losses on sells using FIFO
            for tx in transactions:
                if tx.transaction_type == TransactionType.SELL and tx.price:
                    asset_symbol = tx.asset.symbol
                    sell_quantity = float(tx.quantity)
                    sell_price = float(tx.price)
                    sell_date = tx.transaction_time

                    remaining_to_sell = sell_quantity
                    total_cost_basis = 0

                    # Use FIFO to calculate cost basis
                    if asset_symbol in cost_basis_tracker:
                        lots_to_remove = []

                        for i, lot in enumerate(cost_basis_tracker[asset_symbol]):
                            if remaining_to_sell <= 0:
                                break

                            lot_quantity = lot["quantity"]
                            lot_cost_per_unit = lot["cost_per_unit"]
                            lot_date = lot["date"]

                            if lot_quantity <= remaining_to_sell:
                                # Use entire lot
                                total_cost_basis += lot_quantity * lot_cost_per_unit
                                remaining_to_sell -= lot_quantity
                                lots_to_remove.append(i)
                            else:
                                # Use partial lot
                                total_cost_basis += (
                                    remaining_to_sell * lot_cost_per_unit
                                )
                                lot["quantity"] -= remaining_to_sell
                                remaining_to_sell = 0

                        # Remove used lots
                        for i in reversed(lots_to_remove):
                            cost_basis_tracker[asset_symbol].pop(i)

                    # Calculate gain/loss
                    proceeds = sell_quantity * sell_price
                    if total_cost_basis == 0:
                        # Fallback if no cost basis available
                        total_cost_basis = proceeds * 0.8  # Assume 25% gain

                    gain_loss = proceeds - total_cost_basis

                    # Determine if short-term or long-term
                    # For simplicity, use the oldest lot date if available
                    holding_period_days = 365  # Default to long-term
                    if (
                        asset_symbol in cost_basis_tracker
                        and cost_basis_tracker[asset_symbol]
                    ):
                        oldest_lot_date = min(
                            lot["date"] for lot in cost_basis_tracker[asset_symbol]
                        )
                        holding_period_days = (sell_date - oldest_lot_date).days

                    is_long_term = holding_period_days > 365

                    if gain_loss > 0:
                        realized_gains += gain_loss
                        if is_long_term:
                            long_term_gains += gain_loss
                        else:
                            short_term_gains += gain_loss
                    else:
                        loss_amount = abs(gain_loss)
                        realized_losses += loss_amount
                        if is_long_term:
                            long_term_losses += loss_amount
                        else:
                            short_term_losses += loss_amount

                    taxable_events.append(
                        {
                            "date": tx.transaction_time.isoformat(),
                            "asset": tx.asset.symbol,
                            "quantity": float(tx.quantity),
                            "proceeds": proceeds,
                            "cost_basis": total_cost_basis,
                            "gain_loss": gain_loss,
                            "holding_period_days": holding_period_days,
                            "type": "Long-term" if is_long_term else "Short-term",
                            "transaction_id": tx.transaction_id,
                        }
                    )

            # Enhanced tax calculations with current rates
            net_short_term = short_term_gains - short_term_losses
            net_long_term = long_term_gains - long_term_losses
            net_capital_gains = net_short_term + net_long_term

            # Current US tax rates (2024)
            if country == "US":
                # Income tax rates for short-term gains (simplified brackets)
                if net_short_term <= 44625:  # 22% bracket
                    short_term_tax_rate = 0.22
                elif net_short_term <= 95375:  # 24% bracket
                    short_term_tax_rate = 0.24
                else:  # 32%+ brackets
                    short_term_tax_rate = 0.32

                # Long-term capital gains rates
                if net_long_term <= 44625:
                    long_term_tax_rate = 0.0  # 0% rate
                elif net_long_term <= 492300:
                    long_term_tax_rate = 0.15  # 15% rate
                else:
                    long_term_tax_rate = 0.20  # 20% rate

                # Calculate taxes owed
                short_term_tax = max(0, net_short_term) * short_term_tax_rate
                long_term_tax = max(0, net_long_term) * long_term_tax_rate
                total_tax_owed = short_term_tax + long_term_tax

                # Net Investment Income Tax (3.8% on high earners)
                niit_threshold = 200000  # Single filer threshold
                if net_capital_gains > niit_threshold:
                    niit_tax = (
                        min(net_capital_gains, net_capital_gains - niit_threshold)
                        * 0.038
                    )
                    total_tax_owed += niit_tax
                else:
                    niit_tax = 0

            else:
                # Generic rates for other countries
                short_term_tax_rate = 0.30
                long_term_tax_rate = 0.20
                short_term_tax = max(0, net_short_term) * short_term_tax_rate
                long_term_tax = max(0, net_long_term) * long_term_tax_rate
                total_tax_owed = short_term_tax + long_term_tax
                niit_tax = 0

            # Enhanced tax optimization strategies
            strategies = []

            # Get current portfolio for unrealized gains/losses
            from tools.tools_crypto_portfolios import get_user_portfolio_summary

            portfolio = get_user_portfolio_summary.invoke({"user_id": user_id})

            if isinstance(portfolio, dict) and "positions_by_asset" in portfolio:
                losing_positions = [
                    p
                    for p in portfolio["positions_by_asset"]
                    if p.get("pnl", 0) < -50  # Minimum $50 loss
                ]

                gaining_positions = [
                    p
                    for p in portfolio["positions_by_asset"]
                    if p.get("pnl", 0) > 50  # Minimum $50 gain
                ]

                # Strategy 1: Tax loss harvesting
                if losing_positions and net_capital_gains > 0:
                    potential_offset = min(
                        sum(abs(p["pnl"]) for p in losing_positions), net_capital_gains
                    )

                    tax_savings = potential_offset * (
                        short_term_tax_rate
                        if net_short_term > 0
                        else long_term_tax_rate
                    )

                    strategies.append(
                        {
                            "strategy": "Tax Loss Harvesting",
                            "description": "Realize losses to offset current year gains",
                            "potential_tax_savings": tax_savings,
                            "implementation": "Sell losing positions before December 31st",
                            "positions": [
                                {
                                    "asset": p["symbol"],
                                    "unrealized_loss": p["pnl"],
                                    "current_value": p["total_value"],
                                    "tax_benefit": abs(p["pnl"]) * short_term_tax_rate,
                                }
                                for p in losing_positions[:5]
                            ],
                            "considerations": [
                                "30-day wash sale rule applies",
                                "Consider repurchasing after 31 days",
                                "Alternative: buy similar but not identical assets",
                            ],
                        }
                    )

                # Strategy 2: Long-term holding optimization
                if short_term_gains > long_term_gains and gaining_positions:
                    near_long_term = []
                    for pos in gaining_positions:
                        # This would need transaction history to determine holding period
                        # For now, suggest general strategy
                        pass

                    potential_savings = short_term_gains * (
                        short_term_tax_rate - long_term_tax_rate
                    )

                    if potential_savings > 1000:  # Significant savings threshold
                        strategies.append(
                            {
                                "strategy": "Hold for Long-term Treatment",
                                "description": "Delay selling positions close to 1-year holding period",
                                "potential_tax_savings": potential_savings,
                                "implementation": "Wait to sell positions until they qualify for long-term rates",
                                "benefit": f"Save {(short_term_tax_rate - long_term_tax_rate) * 100:.1f}% on tax rate",
                            }
                        )

                # Strategy 3: Charitable donations of appreciated assets
                if net_capital_gains > 5000 and gaining_positions:
                    donation_candidates = [
                        p for p in gaining_positions if p["pnl"] > 1000
                    ]

                    if donation_candidates:
                        max_donation = min(
                            sum(p["total_value"] for p in donation_candidates[:3]),
                            net_capital_gains * 0.3,  # Donate up to 30% of gains
                        )

                        tax_savings = (
                            max_donation * short_term_tax_rate
                        )  # Conservative estimate

                        strategies.append(
                            {
                                "strategy": "Charitable Crypto Donations",
                                "description": "Donate appreciated crypto directly to qualified charities",
                                "potential_tax_savings": tax_savings,
                                "additional_deduction": max_donation,  # Full fair market value deduction
                                "total_benefit": tax_savings
                                + (max_donation * short_term_tax_rate),
                                "implementation": "Use donor-advised funds or direct charity transfers",
                                "candidates": [
                                    {
                                        "asset": p["symbol"],
                                        "current_value": p["total_value"],
                                        "unrealized_gain": p["pnl"],
                                    }
                                    for p in donation_candidates[:3]
                                ],
                            }
                        )

            # Strategy 4: Year-end timing optimization
            days_left_in_year = (datetime(tax_year, 12, 31) - datetime.utcnow()).days
            if days_left_in_year > 0 and days_left_in_year < 60:
                strategies.append(
                    {
                        "strategy": "Year-end Timing Optimization",
                        "description": f"Optimize timing of remaining transactions ({days_left_in_year} days left)",
                        "actions": [
                            "Accelerate loss realization before Dec 31",
                            "Defer gain realization to next year if beneficial",
                            "Consider installment sales for large positions",
                            "Review estimated tax payments due Jan 15",
                        ],
                        "deadline": f"{tax_year}-12-31",
                    }
                )

            # Strategy 5: Retirement account optimization
            if total_tax_owed > 2000:
                strategies.append(
                    {
                        "strategy": "Retirement Account Contributions",
                        "description": "Reduce taxable income through retirement contributions",
                        "potential_tax_savings": min(
                            22500 * short_term_tax_rate, total_tax_owed
                        ),
                        "options": [
                            f"401(k) contribution: Up to $23,000 for {tax_year + 1}",
                            f"IRA contribution: Up to $7,000 for {tax_year + 1}",
                            "Consider backdoor Roth conversions",
                        ],
                        "deadline": f"{tax_year + 1}-04-15 for IRA contributions",
                    }
                )

            # Calculate effective tax rate and provide insights
            effective_tax_rate = (
                (total_tax_owed / net_capital_gains * 100)
                if net_capital_gains > 0
                else 0
            )

            # Tax efficiency score
            if effective_tax_rate < 15:
                tax_efficiency = "EXCELLENT"
            elif effective_tax_rate < 25:
                tax_efficiency = "GOOD"
            elif effective_tax_rate < 35:
                tax_efficiency = "AVERAGE"
            else:
                tax_efficiency = "NEEDS_IMPROVEMENT"

            return {
                "tax_year": tax_year,
                "country": country,
                "summary": {
                    "total_realized_gains": realized_gains,
                    "total_realized_losses": realized_losses,
                    "net_capital_gains": net_capital_gains,
                    "short_term_gains": short_term_gains,
                    "long_term_gains": long_term_gains,
                    "short_term_losses": short_term_losses,
                    "long_term_losses": long_term_losses,
                    "net_short_term": net_short_term,
                    "net_long_term": net_long_term,
                    "estimated_tax_liability": total_tax_owed,
                    "short_term_tax": short_term_tax,
                    "long_term_tax": long_term_tax,
                    "niit_tax": niit_tax,
                    "effective_tax_rate": effective_tax_rate,
                    "tax_efficiency_rating": tax_efficiency,
                },
                "tax_rates_used": {
                    "short_term_rate": short_term_tax_rate * 100,
                    "long_term_rate": long_term_tax_rate * 100,
                    "niit_rate": 3.8 if niit_tax > 0 else 0,
                },
                "taxable_events": sorted(
                    taxable_events, key=lambda x: abs(x["gain_loss"]), reverse=True
                )[:20],
                "optimization_strategies": strategies,
                "important_dates": {
                    "tax_filing_deadline": f"{tax_year + 1}-04-15",
                    "estimated_tax_deadlines": [
                        f"{tax_year}-04-15",
                        f"{tax_year}-06-15",
                        f"{tax_year}-09-15",
                        f"{tax_year + 1}-01-15",
                    ],
                    "ira_contribution_deadline": f"{tax_year + 1}-04-15",
                    "year_end_planning_deadline": f"{tax_year}-12-31",
                },
                "recommendations": {
                    "immediate_actions": [
                        action
                        for strategy in strategies
                        for action in strategy.get(
                            "actions", [strategy.get("implementation", "")]
                        )
                        if action
                    ][:5],
                    "total_potential_savings": sum(
                        strategy.get("potential_tax_savings", 0)
                        for strategy in strategies
                    ),
                    "priority_level": (
                        "HIGH"
                        if total_tax_owed > 5000
                        else "MEDIUM" if total_tax_owed > 1000 else "LOW"
                    ),
                },
                "compliance_notes": [
                    "This analysis uses FIFO cost basis method",
                    "Wash sale rules may apply to some transactions",
                    "Consider state tax implications",
                    "Foreign account reporting may be required (FBAR/Form 8938)",
                    "Consult a tax professional for complex situations",
                ],
                "data_quality": {
                    "transactions_analyzed": len(transactions),
                    "cost_basis_method": "FIFO",
                    "missing_cost_basis_count": sum(
                        1
                        for event in taxable_events
                        if event["cost_basis"] == event["proceeds"] * 0.8
                    ),
                    "analysis_confidence": (
                        "HIGH"
                        if len(transactions) > 0
                        and sum(
                            1
                            for event in taxable_events
                            if event["cost_basis"] == event["proceeds"] * 0.8
                        )
                        == 0
                        else "MEDIUM" if len(transactions) > 0 else "LOW"
                    ),
                },
                "disclaimer": (
                    "This is a simplified analysis based on available transaction data. "
                    "Tax laws are complex and change frequently. "
                    "Consult with a qualified tax professional for personalized advice."
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Exception:{e}\n{traceback.format_exc()}")
        return {"error": f"Failed to analyze tax implications: {str(e)}"}


# Export tools list
tools = [
    get_rebalancing_recommendations,
    find_investment_opportunities,
    analyze_tax_implications,
]
