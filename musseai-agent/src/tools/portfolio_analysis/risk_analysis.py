import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime
from langchain.agents import tool
from mysql.db import get_db
from mysql.model import (
    AssetModel,
    PortfolioSourceModel,
    PositionModel,
)
from loggers import logger
import traceback


from utils.enhance_multi_api_manager import api_manager

# ========================================
# Configuration and Constants
# ========================================

# Asset categorization for better risk assessment
ASSET_CATEGORIES = {
    "stablecoins": ["USDT", "USDC", "DAI", "BUSD", "FRAX", "TUSD", "FDUSD"],
    "blue_chip": ["BTC", "ETH"],
    "layer1": ["BNB", "SOL", "ADA", "DOT", "AVAX", "MATIC", "ATOM", "NEAR"],
    "layer2": ["OP", "ARB", "LRC"],
    "defi": ["UNI", "AAVE", "COMP", "MKR", "CRV", "SUSHI", "1INCH"],
    "meme": ["DOGE", "SHIB", "PEPE", "FLOKI"],
    "ai": ["FET", "AGIX", "OCEAN", "RLC"],
    "gaming": ["AXS", "SAND", "MANA", "ENJ", "GALA"],
}

# Risk configuration
RISK_CONFIG = {
    "var_confidence_levels": [0.95, 0.99],
    "correlation_threshold": 0.7,
    "high_risk_threshold": 70,
    "medium_risk_threshold": 40,
    "max_position_risk_threshold": 25,  # Percentage
    "liquidity_thresholds": {"high": 80, "medium": 50, "low": 20},
}


def classify_asset(symbol: str) -> str:
    """
    Classify asset into risk categories.

    Args:
        symbol (str): Asset symbol

    Returns:
        str: Asset category
    """
    symbol = symbol.upper()

    for category, symbols in ASSET_CATEGORIES.items():
        if symbol in symbols:
            return category

    # Default to 'other' for unclassified assets
    return "other"


# ========================================
# Risk Calculation Functions
# ========================================


def calculate_portfolio_volatility(
    positions: List[Dict], historical_data: Dict
) -> float:
    """
    Calculate portfolio volatility using real historical data.

    Args:
        positions: List of portfolio positions
        historical_data: Historical price data for assets

    Returns:
        float: Annualized portfolio volatility
    """
    try:
        if not positions or not historical_data:
            return 0.25  # Default fallback

        # Get weights and returns for each asset
        total_value = sum(pos["total_value"] for pos in positions)
        if total_value <= 0:
            return 0.25

        weights = []
        returns_matrix = []

        for pos in positions:
            symbol = pos["symbol"].upper()
            weight = pos["total_value"] / total_value

            if symbol in historical_data and historical_data[symbol]:
                returns = historical_data[symbol]["returns"]
                if returns and len(returns) > 10:  # Minimum data points
                    weights.append(weight)
                    returns_matrix.append(
                        returns[: min(len(returns), 90)]
                    )  # Use up to 90 days

        if not weights:
            return 0.25

        # Align return series to same length
        min_length = min(len(r) for r in returns_matrix)
        aligned_returns = [r[:min_length] for r in returns_matrix]

        # Calculate portfolio returns
        portfolio_returns = []
        for i in range(min_length):
            daily_return = sum(w * r[i] for w, r in zip(weights, aligned_returns))
            portfolio_returns.append(daily_return)

        # Calculate annualized volatility
        if len(portfolio_returns) > 1:
            volatility = np.std(portfolio_returns) * np.sqrt(365)
            return max(0.05, min(2.0, volatility))  # Bound between 5% and 200%
        else:
            return 0.25

    except Exception as e:
        logger.error(
            f"Error calculating portfolio volatility: {e}\n{traceback.format_exc()}"
        )
        return 0.25


def calculate_correlation_matrix(
    positions: List[Dict], historical_data: Dict
) -> Tuple[np.ndarray, List[str]]:
    """
    Calculate actual correlation matrix using historical price data.

    Args:
        positions: List of portfolio positions
        historical_data: Historical price data

    Returns:
        Tuple: (correlation_matrix, asset_symbols)
    """
    try:
        # Filter positions with available data
        valid_assets = []
        returns_data = []

        for pos in positions[:20]:  # Limit to top 20 positions
            symbol = pos["symbol"].upper()
            if symbol in historical_data and historical_data[symbol]:
                returns = historical_data[symbol]["returns"]
                if returns and len(returns) > 30:  # Minimum 30 data points
                    valid_assets.append(symbol)
                    returns_data.append(returns)

        if len(valid_assets) < 2:
            # Return identity matrix for single asset or no data
            n = max(2, len(valid_assets))
            return np.eye(n), valid_assets if valid_assets else ["BTC", "ETH"]

        # Align return series
        min_length = min(len(r) for r in returns_data)
        aligned_returns = np.array([r[:min_length] for r in returns_data])

        # Calculate correlation matrix
        correlation_matrix = np.corrcoef(aligned_returns)

        # Handle NaN values
        correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)

        # Ensure diagonal is 1.0
        np.fill_diagonal(correlation_matrix, 1.0)

        return correlation_matrix, valid_assets

    except Exception as e:
        logger.error(
            f"Error calculating correlation matrix: {e}\n{traceback.format_exc()}"
        )
        # Return default correlation matrix
        n = min(len(positions), 10)
        return np.eye(n), [pos["symbol"] for pos in positions[:n]]


def calculate_var_monte_carlo(
    portfolio_value: float,
    volatility: float,
    confidence_level: float = 0.95,
    num_simulations: int = 10000,
) -> float:
    """
    Calculate Value at Risk using Monte Carlo simulation.

    Args:
        portfolio_value: Current portfolio value
        volatility: Portfolio volatility
        confidence_level: Confidence level (0.95 for 95%)
        num_simulations: Number of Monte Carlo simulations

    Returns:
        float: VaR value
    """
    try:
        if portfolio_value <= 0 or volatility <= 0:
            return 0.0

        # Daily volatility
        daily_vol = volatility / np.sqrt(365)

        # Generate random returns
        random_returns = np.random.normal(0, daily_vol, num_simulations)

        # Calculate portfolio values
        portfolio_values = portfolio_value * (1 + random_returns)
        portfolio_changes = portfolio_values - portfolio_value

        # Calculate VaR
        var_percentile = (1 - confidence_level) * 100
        var_value = -np.percentile(portfolio_changes, var_percentile)

        return max(0, var_value)

    except Exception as e:
        logger.error(f"Error calculating VaR: {e}\n{traceback.format_exc()}")
        # Fallback to parametric VaR
        from scipy import stats

        z_score = stats.norm.ppf(confidence_level)
        daily_vol = volatility / np.sqrt(365)
        return portfolio_value * z_score * daily_vol


def assess_liquidity_risk(positions: List[Dict], market_data: Dict) -> Dict:
    """
    Assess liquidity risk based on market cap and volume data.

    Args:
        positions: Portfolio positions
        market_data: Current market data

    Returns:
        Dict: Liquidity risk assessment
    """
    try:
        total_value = sum(pos["total_value"] for pos in positions)

        liquidity_scores = []
        illiquid_value = 0

        for pos in positions:
            symbol = pos["symbol"].upper()
            pos_value = pos["total_value"]

            # Get coin ID
            if not symbol or symbol not in market_data:
                # Assume low liquidity for unknown assets
                liquidity_scores.append(30)
                illiquid_value += pos_value * 0.7
                continue

            market_info = market_data[symbol]
            market_cap = market_info.get("market_cap", 0)
            volume_24h = market_info.get("total_volume", 0)

            # Calculate liquidity score (0-100)
            if market_cap > 10_000_000_000:  # >$10B
                base_score = 90
            elif market_cap > 1_000_000_000:  # >$1B
                base_score = 75
            elif market_cap > 100_000_000:  # >$100M
                base_score = 60
            elif market_cap > 10_000_000:  # >$10M
                base_score = 40
            else:
                base_score = 20

            # Adjust based on volume
            if volume_24h > market_cap * 0.1:  # High turnover
                volume_bonus = 10
            elif volume_24h > market_cap * 0.05:  # Medium turnover
                volume_bonus = 5
            elif volume_24h > market_cap * 0.01:  # Low turnover
                volume_bonus = 0
            else:
                volume_bonus = -10  # Very low turnover

            liquidity_score = max(0, min(100, base_score + volume_bonus))
            liquidity_scores.append(liquidity_score)

            # Calculate illiquid portion
            if liquidity_score < RISK_CONFIG["liquidity_thresholds"]["medium"]:
                illiquid_ratio = (50 - liquidity_score) / 50
                illiquid_value += pos_value * illiquid_ratio

        # Overall liquidity assessment
        weighted_liquidity = (
            sum(
                score * pos["total_value"]
                for score, pos in zip(liquidity_scores, positions)
            )
            / total_value
            if total_value > 0
            else 0
        )

        return {
            "overall_liquidity_score": weighted_liquidity,
            "illiquid_percentage": (
                (illiquid_value / total_value * 100) if total_value > 0 else 0
            ),
            "estimated_liquidation_days": max(1, int(10 - weighted_liquidity / 15)),
            "low_liquidity_positions": [
                {
                    "symbol": pos["symbol"],
                    "value": pos["total_value"],
                    "liquidity_score": score,
                }
                for pos, score in zip(positions, liquidity_scores)
                if score < RISK_CONFIG["liquidity_thresholds"]["medium"]
            ],
        }

    except Exception as e:
        logger.error(f"Error assessing liquidity risk: {e}\n{traceback.format_exc()}")
        return {
            "overall_liquidity_score": 70,
            "illiquid_percentage": 30,
            "estimated_liquidation_days": 3,
            "low_liquidity_positions": [],
        }


# ========================================
# Main Risk Analysis Tools
# ========================================


# 在 risk_analysis.py 中更新 analyze_portfolio_risk 函数
@tool
def analyze_portfolio_risk(user_id: str) -> Dict:
    """
    改进的投资组合风险分析，使用多API源和优化的数据获取
    """
    try:
        # 获取投资组合数据（保持原有逻辑）
        with get_db() as db:
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
            positions = (
                db.query(PositionModel)
                .join(AssetModel)
                .filter(
                    PositionModel.source_id.in_(source_ids), PositionModel.quantity > 0
                )
                .all()
            )

            if not positions:
                return {"error": "No positions found"}

            # 转换为分析格式
            position_data = []
            total_value = 0

            for pos in positions:
                if pos.last_price and pos.quantity:
                    pos_value = float(pos.quantity * pos.last_price)
                    total_value += pos_value
                    position_data.append(
                        {
                            "symbol": pos.asset.symbol,
                            "quantity": float(pos.quantity),
                            "price": float(pos.last_price),
                            "total_value": pos_value,
                            "chain": getattr(pos.asset, "chain", "unknown"),
                        }
                    )

            if total_value <= 0:
                return {"error": "Portfolio has no value"}

            # 按价值排序（最大的在前）
            position_data.sort(key=lambda x: x["total_value"], reverse=True)

            # 使用改进的批量数据获取
            symbols = [
                pos["symbol"].upper() for pos in position_data[:15]
            ]  # 限制前15个

            # 批量获取历史数据
            logger.info(f"Fetching historical data for {len(symbols)} symbols")
            historical_data = {}
            for symbol in symbols:
                try:
                    # 使用api_manager的多API fallback机制
                    symbol_data = api_manager.fetch_with_fallback(symbol, days=90)
                    if symbol_data and symbol_data.get("prices"):
                        historical_data[symbol.upper()] = symbol_data
                        logger.debug(f"Successfully fetched data for {symbol}")
                    else:
                        logger.warning(f"No data available for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {symbol}: {e}")
                    continue

            logger.info(
                f"Successfully fetched data for {len(historical_data)}/{len(symbols)} symbols"
            )

            # 获取当前市场数据
            logger.info("Fetching current market data")
            market_data = {}
            try:
                # 使用批量市场数据获取
                batch_market_data = api_manager.fetch_multiple_market_data(symbols)
                if batch_market_data:
                    # 转换格式以匹配现有代码期望
                    for symbol in symbols:
                        if symbol and symbol in batch_market_data:
                            market_data[symbol] = batch_market_data[symbol]
                        elif symbol.upper() in batch_market_data:
                            market_data[symbol.upper()] = batch_market_data[
                                symbol.upper()
                            ]

                logger.info(
                    f"Successfully fetched market data for {len(market_data)} assets"
                )
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                market_data = {}

            # 计算风险指标（保持原有逻辑）
            portfolio_volatility = calculate_portfolio_volatility(
                position_data, historical_data
            )
            correlation_matrix, correlation_assets = calculate_correlation_matrix(
                position_data, historical_data
            )
            liquidity_assessment = assess_liquidity_risk(position_data, market_data)

            # 计算VaR指标
            var_95 = calculate_var_monte_carlo(total_value, portfolio_volatility, 0.95)
            var_99 = calculate_var_monte_carlo(total_value, portfolio_volatility, 0.99)
            cvar_95 = var_95 * 1.3

            # 集中度风险分析
            max_position_value = max(pos["total_value"] for pos in position_data)
            max_position_percentage = max_position_value / total_value * 100

            # Herfindahl指数计算
            weights = [pos["total_value"] / total_value for pos in position_data]
            herfindahl_index = sum(w**2 for w in weights)
            effective_positions = 1 / herfindahl_index if herfindahl_index > 0 else 1

            # 资产类别多样化分析
            category_exposure = {}
            for pos in position_data:
                category = classify_asset(pos["symbol"])
                category_exposure[category] = (
                    category_exposure.get(category, 0) + pos["total_value"]
                )

            category_percentages = {
                cat: (value / total_value * 100)
                for cat, value in category_exposure.items()
            }

            # 风险评分
            concentration_score = min(100, herfindahl_index * 10000)
            volatility_score = min(100, portfolio_volatility * 200)
            liquidity_score = 100 - liquidity_assessment["overall_liquidity_score"]

            overall_risk_score = (
                concentration_score * 0.3
                + volatility_score * 0.4
                + liquidity_score * 0.3
            )

            # 风险等级
            if overall_risk_score > RISK_CONFIG["high_risk_threshold"]:
                risk_rating = "High"
            elif overall_risk_score > RISK_CONFIG["medium_risk_threshold"]:
                risk_rating = "Medium"
            else:
                risk_rating = "Low"

            # 生成建议
            recommendations = generate_risk_recommendations(
                position_data,
                max_position_percentage,
                portfolio_volatility,
                liquidity_assessment,
                category_percentages,
                effective_positions,
            )

            # 相关性洞察
            correlation_insights = generate_correlation_insights(
                correlation_matrix, correlation_assets
            )

            # 数据质量报告
            data_quality = {
                "total_symbols_requested": len(symbols),
                "historical_data_available": len(historical_data),
                "market_data_available": len(market_data),
                "data_coverage_percentage": round(
                    (len(historical_data) / len(symbols)) * 100, 1
                ),
                "apis_used": list(
                    set(["coingecko", "coincap", "binance", "cryptocompare"])
                ),
                "analysis_limitations": [],
            }

            # 添加分析限制说明
            if len(historical_data) < len(symbols) * 0.8:
                data_quality["analysis_limitations"].append(
                    f"Limited historical data for {len(symbols) - len(historical_data)} assets"
                )

            return {
                "risk_summary": {
                    "overall_risk_score": round(overall_risk_score, 1),
                    "risk_rating": risk_rating,
                    "portfolio_value": total_value,
                    "number_of_positions": len(position_data),
                    "effective_positions": round(effective_positions, 1),
                },
                "volatility_metrics": {
                    "annualized_volatility": round(portfolio_volatility * 100, 2),
                    "daily_volatility": round(
                        portfolio_volatility / np.sqrt(365) * 100, 2
                    ),
                    "volatility_score": round(volatility_score, 1),
                },
                "value_at_risk": {
                    "var_95_1day": round(var_95, 2),
                    "var_95_1day_percentage": round((var_95 / total_value * 100), 2),
                    "var_99_1day": round(var_99, 2),
                    "var_99_1day_percentage": round((var_99 / total_value * 100), 2),
                    "cvar_95_1day": round(cvar_95, 2),
                    "cvar_95_1day_percentage": round((cvar_95 / total_value * 100), 2),
                },
                "concentration_risk": {
                    "herfindahl_index": round(herfindahl_index, 4),
                    "concentration_score": round(concentration_score, 1),
                    "top_position_weight": round(max_position_percentage, 1),
                    "top_position_asset": position_data[0]["symbol"],
                    "effective_number_of_positions": round(effective_positions, 1),
                },
                "liquidity_risk": liquidity_assessment,
                "diversification_analysis": {
                    "category_exposure": {
                        k: round(v, 1) for k, v in category_percentages.items()
                    },
                    "diversification_score": round(100 - concentration_score, 1),
                    "correlation_insights": correlation_insights,
                },
                "recommendations": recommendations,
                "risk_factors": generate_risk_factors(
                    portfolio_volatility,
                    concentration_score,
                    liquidity_assessment,
                    category_percentages,
                ),
                "data_quality": data_quality,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "methodology": "Multi-API enhanced risk analysis with real-time market data",
            }

    except Exception as e:
        logger.error(
            f"Exception in analyze_portfolio_risk: {e}\n{traceback.format_exc()}"
        )
        return {
            "error": f"Failed to analyze portfolio risk: {str(e)}\n{traceback.format_exc()}"
        }


def generate_risk_recommendations(
    position_data,
    max_position_percentage,
    portfolio_volatility,
    liquidity_assessment,
    category_percentages,
    effective_positions,
):
    """生成风险建议"""
    recommendations = []

    if max_position_percentage > RISK_CONFIG["max_position_risk_threshold"]:
        recommendations.append(
            f"🔴 Consider reducing exposure to {position_data[0]['symbol']} "
            f"({max_position_percentage:.1f}% of portfolio)"
        )

    if portfolio_volatility > 0.5:
        recommendations.append(
            "🟡 Portfolio shows high volatility. Consider adding stable assets."
        )

    if liquidity_assessment["illiquid_percentage"] > 30:
        recommendations.append(
            f"🔴 High illiquid exposure ({liquidity_assessment['illiquid_percentage']:.1f}%). "
            "Consider improving liquidity buffer."
        )

    if len([c for c in category_percentages.values() if c > 40]) > 0:
        dominant_category = max(category_percentages.items(), key=lambda x: x[1])
        recommendations.append(
            f"🟡 Over-concentrated in {dominant_category[0]} ({dominant_category[1]:.1f}%). "
            "Consider diversifying across asset categories."
        )

    if effective_positions < 5:
        recommendations.append(
            f"🔴 Low effective diversification ({effective_positions:.1f} effective positions). "
            "Consider adding more uncorrelated assets."
        )

    # 添加积极建议
    if not recommendations:
        recommendations.append("✅ Portfolio risk profile appears well-balanced")

    return recommendations


def generate_correlation_insights(correlation_matrix, correlation_assets):
    """生成相关性洞察"""
    correlation_insights = []

    if len(correlation_assets) > 1:
        high_correlations = []
        n_assets = len(correlation_assets)

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                corr_value = correlation_matrix[i, j]
                if abs(corr_value) > RISK_CONFIG["correlation_threshold"]:
                    high_correlations.append(
                        {
                            "asset1": correlation_assets[i],
                            "asset2": correlation_assets[j],
                            "correlation": float(corr_value),
                        }
                    )

        if high_correlations:
            correlation_insights.append(
                f"⚠️ Found {len(high_correlations)} highly correlated asset pairs. "
                "This reduces effective diversification."
            )
        else:
            correlation_insights.append(
                "✅ Good diversification with low asset correlations."
            )

    return correlation_insights


def generate_risk_factors(
    portfolio_volatility,
    concentration_score,
    liquidity_assessment,
    category_percentages,
):
    """生成风险因子分析"""
    return [
        {
            "factor": "Market Risk",
            "impact": (
                "High"
                if portfolio_volatility > 0.4
                else "Medium" if portfolio_volatility > 0.2 else "Low"
            ),
            "description": f"Portfolio volatility: {portfolio_volatility*100:.1f}%",
            "mitigation": "Consider adding stable assets or hedging positions",
        },
        {
            "factor": "Concentration Risk",
            "impact": (
                "High"
                if concentration_score > 50
                else "Medium" if concentration_score > 25 else "Low"
            ),
            "description": f"Portfolio concentration score: {concentration_score:.1f}",
            "mitigation": "Diversify holdings across more assets",
        },
        {
            "factor": "Liquidity Risk",
            "impact": (
                "High"
                if liquidity_assessment["overall_liquidity_score"] < 50
                else (
                    "Medium"
                    if liquidity_assessment["overall_liquidity_score"] < 75
                    else "Low"
                )
            ),
            "description": f"Liquidity score: {liquidity_assessment['overall_liquidity_score']:.1f}",
            "mitigation": "Maintain liquid assets for emergency exits",
        },
        {
            "factor": "Category Concentration",
            "impact": (
                "High"
                if max(category_percentages.values()) > 60
                else "Medium" if max(category_percentages.values()) > 40 else "Low"
            ),
            "description": f"Largest category exposure: {max(category_percentages.values()):.1f}%",
            "mitigation": "Diversify across different asset categories",
        },
    ]


@tool
def portfolio_stress_test(user_id: str, scenarios: List[Dict] = None) -> Dict:
    """
    Enhanced stress testing with real market data and dynamic scenarios.

    Args:
        user_id (str): User identifier
        scenarios (List[Dict], optional): Custom scenarios to test

    Returns:
        Dict: Comprehensive stress test results
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

        current_value = portfolio["total_value"]
        positions = portfolio["positions_by_asset"]

        # Enhanced scenarios based on historical market events
        if not scenarios:
            scenarios = [
                {
                    "name": "Crypto Winter (2022-style)",
                    "description": "Extended bear market with regulatory pressure",
                    "market_change": -70,
                    "btc_change": -65,
                    "eth_change": -75,
                    "altcoin_change": -80,
                    "stablecoin_change": -2,
                    "defi_change": -85,
                    "meme_change": -90,
                    "probability": "Medium",
                },
                {
                    "name": "Flash Crash (May 2021-style)",
                    "description": "Sudden liquidity crisis and panic selling",
                    "market_change": -40,
                    "btc_change": -35,
                    "eth_change": -45,
                    "altcoin_change": -55,
                    "stablecoin_change": 0,
                    "defi_change": -60,
                    "meme_change": -70,
                    "probability": "Low",
                },
                {
                    "name": "Bull Market Rally",
                    "description": "Strong institutional adoption and favorable regulation",
                    "market_change": 100,
                    "btc_change": 80,
                    "eth_change": 120,
                    "altcoin_change": 150,
                    "stablecoin_change": 0,
                    "defi_change": 200,
                    "meme_change": 300,
                    "probability": "Medium",
                },
                {
                    "name": "Regulatory Crackdown",
                    "description": "Major jurisdictions ban or heavily restrict crypto",
                    "market_change": -60,
                    "btc_change": -50,
                    "eth_change": -65,
                    "altcoin_change": -75,
                    "stablecoin_change": -10,
                    "defi_change": -80,
                    "meme_change": -85,
                    "probability": "Low",
                },
                {
                    "name": "Stablecoin Depeg Crisis",
                    "description": "Major stablecoin loses peg, market confidence shaken",
                    "market_change": -30,
                    "btc_change": -25,
                    "eth_change": -35,
                    "altcoin_change": -40,
                    "stablecoin_change": -15,
                    "defi_change": -50,
                    "meme_change": -45,
                    "probability": "Medium",
                },
                {
                    "name": "Black Swan Event",
                    "description": "Extreme unforeseen market event",
                    "market_change": -80,
                    "btc_change": -75,
                    "eth_change": -85,
                    "altcoin_change": -90,
                    "stablecoin_change": -5,
                    "defi_change": -95,
                    "meme_change": -98,
                    "probability": "Very Low",
                },
            ]

        results = []

        for scenario in scenarios:
            # Calculate impact on each position with enhanced categorization
            scenario_value = 0
            impacted_positions = []

            for position in positions:
                symbol = position["symbol"].upper()
                current_pos_value = position["total_value"]
                asset_category = classify_asset(symbol)

                # Determine impact based on asset category and specific rules
                if asset_category == "stablecoins":
                    change = scenario.get("stablecoin_change", 0)
                elif symbol == "BTC":
                    change = scenario.get("btc_change", scenario["market_change"])
                elif symbol == "ETH":
                    change = scenario.get("eth_change", scenario["market_change"] * 1.1)
                elif asset_category == "defi":
                    change = scenario.get(
                        "defi_change", scenario["market_change"] * 1.3
                    )
                elif asset_category == "meme":
                    change = scenario.get(
                        "meme_change", scenario["market_change"] * 1.5
                    )
                elif asset_category == "blue_chip":
                    change = scenario["market_change"] * 0.9
                elif asset_category == "layer1":
                    change = scenario.get(
                        "altcoin_change", scenario["market_change"] * 1.2
                    )
                else:
                    change = scenario.get(
                        "altcoin_change", scenario["market_change"] * 1.1
                    )

                # Apply change
                new_value = current_pos_value * (1 + change / 100)
                impact = new_value - current_pos_value
                scenario_value += new_value

                impacted_positions.append(
                    {
                        "asset": f"{position['symbol']} ({position.get('chain', 'Unknown')})",
                        "category": asset_category,
                        "current_value": current_pos_value,
                        "scenario_value": new_value,
                        "change_amount": impact,
                        "change_percentage": change,
                        "weight": current_pos_value / current_value * 100,
                    }
                )

            # Sort by impact (most negative first)
            impacted_positions.sort(key=lambda x: x["change_amount"])

            total_impact = scenario_value - current_value
            impact_percentage = (
                (total_impact / current_value * 100) if current_value > 0 else 0
            )

            # Risk level assessment
            if impact_percentage < -50:
                risk_level = "EXTREME"
            elif impact_percentage < -30:
                risk_level = "SEVERE"
            elif impact_percentage < -20:
                risk_level = "HIGH"
            elif impact_percentage < -10:
                risk_level = "MODERATE"
            else:
                risk_level = "LOW"

            # Calculate recovery time estimate (simplified)
            if impact_percentage < 0:
                # Assume 20% annual recovery rate for estimation
                recovery_years = abs(impact_percentage) / 20
                recovery_time = (
                    f"{recovery_years:.1f} years"
                    if recovery_years > 1
                    else f"{recovery_years*12:.0f} months"
                )
            else:
                recovery_time = "N/A (positive scenario)"

            results.append(
                {
                    "scenario": scenario["name"],
                    "description": scenario["description"],
                    "probability": scenario.get("probability", "Unknown"),
                    "portfolio_impact": {
                        "current_value": current_value,
                        "scenario_value": scenario_value,
                        "change_amount": total_impact,
                        "change_percentage": round(impact_percentage, 2),
                    },
                    "risk_level": risk_level,
                    "estimated_recovery_time": recovery_time,
                    "most_impacted": impacted_positions[:5],  # Top 5 most impacted
                    "category_impacts": {
                        category: {
                            "total_impact": sum(
                                pos["change_amount"]
                                for pos in impacted_positions
                                if pos["category"] == category
                            ),
                            "avg_change": (
                                np.mean(
                                    [
                                        pos["change_percentage"]
                                        for pos in impacted_positions
                                        if pos["category"] == category
                                    ]
                                )
                                if any(
                                    pos["category"] == category
                                    for pos in impacted_positions
                                )
                                else 0
                            ),
                        }
                        for category in set(
                            pos["category"] for pos in impacted_positions
                        )
                    },
                }
            )

        # Summary statistics
        negative_scenarios = [
            r for r in results if r["portfolio_impact"]["change_percentage"] < 0
        ]
        positive_scenarios = [
            r for r in results if r["portfolio_impact"]["change_percentage"] > 0
        ]

        worst_case = min(
            results, key=lambda x: x["portfolio_impact"]["change_percentage"]
        )
        best_case = max(
            results, key=lambda x: x["portfolio_impact"]["change_percentage"]
        )

        # Risk metrics
        downside_scenarios = len(negative_scenarios)
        severe_scenarios = len(
            [r for r in results if r["risk_level"] in ["SEVERE", "EXTREME"]]
        )

        average_downside = (
            sum(r["portfolio_impact"]["change_percentage"] for r in negative_scenarios)
            / len(negative_scenarios)
            if negative_scenarios
            else 0
        )

        # Value at Risk estimate from stress tests
        stress_var_95 = (
            np.percentile([r["portfolio_impact"]["change_amount"] for r in results], 5)
            if results
            else 0
        )

        return {
            "stress_test_results": results,
            "summary": {
                "total_scenarios_tested": len(results),
                "downside_scenarios": downside_scenarios,
                "severe_risk_scenarios": severe_scenarios,
                "worst_case_scenario": worst_case["scenario"],
                "worst_case_loss": worst_case["portfolio_impact"]["change_percentage"],
                "best_case_scenario": best_case["scenario"],
                "best_case_gain": best_case["portfolio_impact"]["change_percentage"],
                "average_downside": round(average_downside, 2),
                "stress_test_var_95": abs(stress_var_95) if stress_var_95 < 0 else 0,
            },
            "risk_insights": [
                f"Portfolio could lose up to {abs(worst_case['portfolio_impact']['change_percentage']):.1f}% in extreme scenarios",
                f"Average downside risk across negative scenarios: {abs(average_downside):.1f}%",
                f"{severe_scenarios} out of {len(results)} scenarios pose severe risk",
                f"Recovery time for worst case: {worst_case['estimated_recovery_time']}",
            ],
            "test_date": datetime.utcnow().isoformat(),
            "methodology": "Enhanced stress testing using historical market event patterns and asset categorization",
        }

    except Exception as e:
        logger.error(
            f"Exception in portfolio_stress_test: {e}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to run stress test: {str(e)}"}


@tool
def analyze_asset_correlations(user_id: str, period_days: int = 90) -> Dict:
    """
    Analyze correlations between portfolio assets using real historical data.

    Args:
        user_id (str): User identifier
        period_days (int): Period for correlation calculation (default: 90 days)

    Returns:
        Dict: Detailed correlation analysis with real market data
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

        if len(positions) < 2:
            return {"error": "Need at least 2 assets for correlation analysis"}

        # Limit to top 15 positions for API efficiency
        top_positions = sorted(positions, key=lambda x: x["total_value"], reverse=True)[
            :15
        ]

        historical_data = {}
        valid_assets = []

        for pos in top_positions:
            symbol = pos["symbol"].upper()
            coin_id = symbol

            if coin_id:
                historical_data = {}
                valid_assets = []

                # Extract symbols for batch processing
                symbols_to_fetch = [pos["symbol"].upper() for pos in top_positions]

                logger.info(
                    f"Fetching historical data for {len(symbols_to_fetch)} symbols over {period_days} days"
                )

                # Use improved batch fetching with multiple API fallbacks
                # Primary: Use batch API call with cache
                batch_historical_data={}
                for symbol in symbols_to_fetch:
                    try:
                        # 使用 fetch_with_fallback 方法替代错误的 get_crypto_historical_data 调用
                        symbol_data = api_manager.fetch_with_fallback(symbol, days=period_days)
                        if symbol_data and symbol_data.get("prices"):
                            batch_historical_data[symbol] = symbol_data
                            logger.debug(f"Successfully fetched data for {symbol}")
                        else:
                            logger.warning(f"No data available for {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch data for {symbol}: {e}")
                        continue

                # Process batch results
                for pos in top_positions:
                    symbol = pos["symbol"].upper()

                    if symbol in batch_historical_data:
                        hist_data = batch_historical_data[symbol]
                        if (
                            hist_data and len(hist_data["returns"]) > 30
                        ):  # Minimum data requirement
                            historical_data[symbol] = hist_data
                            valid_assets.append(symbol)
                    else:
                        logger.warning(f"No historical data available for {symbol}")
        if len(valid_assets) < 2:
            return {"error": "Insufficient historical data for correlation analysis"}

        # Calculate correlation matrix
        correlation_matrix, assets = calculate_correlation_matrix(
            [pos for pos in top_positions if pos["symbol"].upper() in valid_assets],
            historical_data,
        )

        # Create correlation pairs
        correlations = []
        n_assets = len(assets)

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                correlation_value = correlation_matrix[i, j]

                # Classify relationship strength
                abs_corr = abs(correlation_value)
                if abs_corr > 0.8:
                    strength = "Very Strong"
                elif abs_corr > 0.6:
                    strength = "Strong"
                elif abs_corr > 0.4:
                    strength = "Moderate"
                elif abs_corr > 0.2:
                    strength = "Weak"
                else:
                    strength = "Very Weak"

                direction = "Positive" if correlation_value > 0 else "Negative"
                relationship = f"{strength} {direction}"

                correlations.append(
                    {
                        "asset1": assets[i],
                        "asset2": assets[j],
                        "correlation": round(float(correlation_value), 3),
                        "relationship": relationship,
                        "strength": strength,
                        "direction": direction,
                        "abs_correlation": round(abs_corr, 3),
                    }
                )

        # Sort by absolute correlation (strongest first)
        correlations.sort(key=lambda x: x["abs_correlation"], reverse=True)

        # Analysis metrics
        high_correlations = [
            c
            for c in correlations
            if c["abs_correlation"] > RISK_CONFIG["correlation_threshold"]
        ]
        moderate_correlations = [
            c
            for c in correlations
            if 0.4 <= c["abs_correlation"] <= RISK_CONFIG["correlation_threshold"]
        ]

        avg_correlation = np.mean([c["abs_correlation"] for c in correlations])
        max_correlation = (
            max([c["abs_correlation"] for c in correlations]) if correlations else 0
        )

        # Portfolio diversification score (100 = perfect diversification, 0 = no diversification)
        diversification_score = max(0, 100 - (avg_correlation * 100))

        # Identify correlation clusters
        correlation_clusters = []
        processed_assets = set()

        for correlation in high_correlations:
            if (
                correlation["asset1"] not in processed_assets
                and correlation["asset2"] not in processed_assets
            ):
                cluster_assets = [correlation["asset1"], correlation["asset2"]]
                cluster_correlations = [correlation["correlation"]]

                # Find other assets highly correlated with this cluster
                for other_corr in high_correlations:
                    if (
                        other_corr["asset1"] in cluster_assets
                        and other_corr["asset2"] not in cluster_assets
                    ):
                        cluster_assets.append(other_corr["asset2"])
                        cluster_correlations.append(other_corr["correlation"])
                    elif (
                        other_corr["asset2"] in cluster_assets
                        and other_corr["asset1"] not in cluster_assets
                    ):
                        cluster_assets.append(other_corr["asset1"])
                        cluster_correlations.append(other_corr["correlation"])

                if len(cluster_assets) >= 2:
                    correlation_clusters.append(
                        {
                            "assets": cluster_assets,
                            "avg_correlation": round(
                                np.mean([abs(c) for c in cluster_correlations]), 3
                            ),
                            "size": len(cluster_assets),
                        }
                    )
                    processed_assets.update(cluster_assets)

        # Generate insights and recommendations
        insights = []
        recommendations = []

        if (
            len(high_correlations) > len(assets) * 0.3
        ):  # More than 30% of pairs highly correlated
            insights.append(
                {
                    "type": "WARNING",
                    "message": f"High correlation detected: {len(high_correlations)} asset pairs show correlation > {RISK_CONFIG['correlation_threshold']}",
                }
            )
            recommendations.append(
                "Consider diversifying into less correlated asset classes"
            )

        if correlation_clusters:
            largest_cluster = max(correlation_clusters, key=lambda x: x["size"])
            insights.append(
                {
                    "type": "INFO",
                    "message": f"Identified correlation cluster with {largest_cluster['size']} assets: {', '.join(largest_cluster['assets'])}",
                }
            )

        if diversification_score > 80:
            insights.append(
                {
                    "type": "SUCCESS",
                    "message": f"Excellent diversification score: {diversification_score:.1f}/100",
                }
            )
        elif diversification_score > 60:
            insights.append(
                {
                    "type": "INFO",
                    "message": f"Good diversification score: {diversification_score:.1f}/100",
                }
            )
        else:
            insights.append(
                {
                    "type": "WARNING",
                    "message": f"Low diversification score: {diversification_score:.1f}/100",
                }
            )
            recommendations.append(
                "Portfolio lacks diversification - consider adding uncorrelated assets"
            )

        # Market regime analysis
        btc_correlations = [
            c for c in correlations if "BTC" in [c["asset1"], c["asset2"]]
        ]
        eth_correlations = [
            c for c in correlations if "ETH" in [c["asset1"], c["asset2"]]
        ]

        market_regime_analysis = {
            "btc_influence": {
                "average_correlation": (
                    round(np.mean([c["abs_correlation"] for c in btc_correlations]), 3)
                    if btc_correlations
                    else 0
                ),
                "highly_correlated_assets": len(
                    [c for c in btc_correlations if c["abs_correlation"] > 0.7]
                ),
            },
            "eth_influence": {
                "average_correlation": (
                    round(np.mean([c["abs_correlation"] for c in eth_correlations]), 3)
                    if eth_correlations
                    else 0
                ),
                "highly_correlated_assets": len(
                    [c for c in eth_correlations if c["abs_correlation"] > 0.7]
                ),
            },
        }

        # Risk assessment based on correlations
        correlation_risk_score = min(100, avg_correlation * 150)  # Scale to 0-100

        return {
            "correlation_analysis": {
                "period_days": period_days,
                "number_of_assets": n_assets,
                "total_pairs_analyzed": len(correlations),
                "average_correlation": round(avg_correlation, 3),
                "maximum_correlation": round(max_correlation, 3),
                "high_correlation_pairs": len(high_correlations),
                "moderate_correlation_pairs": len(moderate_correlations),
            },
            "diversification_metrics": {
                "diversification_score": round(diversification_score, 1),
                "correlation_risk_score": round(correlation_risk_score, 1),
                "effective_diversification": (
                    "High"
                    if diversification_score > 70
                    else "Medium" if diversification_score > 50 else "Low"
                ),
            },
            "correlation_pairs": correlations,
            "top_correlations": correlations[:10],
            "correlation_clusters": correlation_clusters,
            "market_regime_analysis": market_regime_analysis,
            "insights": insights,
            "recommendations": recommendations,
            "risk_warnings": [
                (
                    f"⚠️ {len(high_correlations)} asset pairs show high correlation (>{RISK_CONFIG['correlation_threshold']})"
                    if high_correlations
                    else "✅ No high correlation pairs detected"
                ),
                (
                    f"⚠️ Correlation clusters detected - reduces effective diversification"
                    if correlation_clusters
                    else "✅ No significant correlation clusters"
                ),
                (
                    f"⚠️ Low diversification score: {diversification_score:.1f}"
                    if diversification_score < 50
                    else f"✅ Good diversification score: {diversification_score:.1f}"
                ),
            ],
            "analysis_date": datetime.utcnow().isoformat(),
            "data_source": "CoinGecko API with 90-day historical data",
        }

    except Exception as e:
        logger.error(
            f"Exception in analyze_asset_correlations: {e}\n{traceback.format_exc()}"
        )
        return {"error": f"Failed to analyze correlations: {str(e)}"}


tools = [
    analyze_portfolio_risk,
    portfolio_stress_test,
    analyze_asset_correlations,
]
