from datetime import datetime
import traceback
from langchain.agents import tool
from typing import Dict, List, Optional
import json
import time
from loggers import logger


@tool
def generate_scalping_strategy(
    symbol: str, timeframe: str = "1m", risk_level: str = "medium"
) -> str:
    """
    Generates a specialized scalping strategy for ultra-short-term trading (1-5 minutes).

    This function creates high-frequency trading strategies designed for quick profits
    from small price movements, typically holding positions for minutes.

    Args:
        symbol (str): Cryptocurrency symbol (e.g., "BTC", "ETH")
        timeframe (str): Trading timeframe ("1m", "5m" - default: "1m")
        risk_level (str): Risk tolerance ("low", "medium", "high" - default: "medium")

    Returns:
        str: JSON string containing scalping strategy with:
             - Entry/exit signals based on micro-movements
             - Tight stop-loss levels (0.1-0.3%)
             - Quick take-profit targets (0.2-0.8%)
             - High-frequency signal generation
             - Market microstructure considerations

    Example usage:
        generate_scalping_strategy("BTC", "1m", "medium")
        generate_scalping_strategy("ETH", "5m", "low")
    """

    risk_multipliers = {"low": 0.5, "medium": 1.0, "high": 1.5}

    multiplier = risk_multipliers.get(risk_level, 1.0)

    strategy = {
        "strategy_type": "Scalping",
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "risk_level": risk_level,
        "generated_at": int(time.time()),
        "entry_conditions": {
            "primary_signal": "RSI(14) crosses above 30 from oversold",
            "confirmation": "Volume > 20-period moving average",
            "price_action": "Price breaks above previous 5-minute high",
            "order_book": "Bid-ask spread < 0.1% for good liquidity",
            "additional_filters": [
                "No major news events in next 30 minutes",
                "Market volatility (ATR) within normal range",
                "Avoid first/last 30 minutes of trading day",
            ],
        },
        "exit_strategy": {
            "take_profit": {
                "target_1": f"{0.2 * multiplier:.1f}% profit",
                "target_2": f"{0.5 * multiplier:.1f}% profit",
                "target_3": f"{0.8 * multiplier:.1f}% profit",
            },
            "stop_loss": {
                "initial": f"{0.15 * multiplier:.1f}% loss",
                "trailing": "Move to breakeven after 0.3% profit",
                "time_based": "Exit after 15 minutes regardless",
            },
        },
        "position_sizing": {
            "base_size": f"{2 / multiplier:.1f}% of portfolio per trade",
            "max_concurrent": 3,
            "daily_limit": "10 trades maximum",
        },
        "risk_management": {
            "max_daily_loss": f"{1.5 * multiplier:.1f}% of portfolio",
            "win_rate_target": "65-70%",
            "risk_reward_ratio": "1:2 minimum",
            "cooldown_period": "5 minutes after stop loss",
        },
        "monitoring": {
            "key_levels": "Watch for support/resistance breaks",
            "volume_confirmation": "Ensure volume supports price movement",
            "market_structure": "Monitor for trend continuation signals",
        },
    }

    return json.dumps(strategy, ensure_ascii=False, indent=2)


@tool
def generate_day_trading_strategy(
    symbol: str,
    timeframe: str = "15m",
    risk_level: str = "medium",
    market_condition: str = "trending",
) -> str:
    """
    Generates comprehensive day trading strategies for intraday positions (hold 1-8 hours).

    Creates strategies designed to capture larger intraday price movements,
    typically holding positions for several hours within the same trading day.

    Args:
        symbol (str): Cryptocurrency symbol
        timeframe (str): Primary timeframe ("5m", "15m", "30m", "1h" - default: "15m")
        risk_level (str): Risk tolerance level
        market_condition (str): Current market state ("trending", "ranging", "volatile")

    Returns:
        str: JSON string containing day trading strategy with:
             - Multi-timeframe analysis approach
             - Moderate stop-loss levels (1-3%)
             - Substantial take-profit targets (2-8%)
             - Trend-following or counter-trend signals
             - Session-based timing considerations
    """

    risk_multipliers = {"low": 0.6, "medium": 1.0, "high": 1.4}

    condition_adjustments = {
        "trending": {"sl": 1.0, "tp": 1.2, "confidence": 0.8},
        "ranging": {"sl": 0.8, "tp": 0.9, "confidence": 0.6},
        "volatile": {"sl": 1.3, "tp": 1.1, "confidence": 0.5},
    }

    multiplier = risk_multipliers.get(risk_level, 1.0)
    adjustment = condition_adjustments.get(
        market_condition, condition_adjustments["trending"]
    )

    strategy = {
        "strategy_type": "Day Trading",
        "symbol": symbol.upper(),
        "primary_timeframe": timeframe,
        "market_condition": market_condition,
        "risk_level": risk_level,
        "generated_at": int(time.time()),
        "multi_timeframe_setup": {
            "higher_timeframe": "1h - for trend direction",
            "primary_timeframe": f"{timeframe} - for entry signals",
            "lower_timeframe": "5m - for precise entry timing",
            "alignment_rule": "All timeframes must confirm direction",
        },
        "entry_conditions": {
            "trend_following": {
                "condition": "Price above 20 EMA on higher timeframe",
                "trigger": "Break of previous swing high with volume",
                "confirmation": "MACD histogram turning positive",
                "additional": "RSI between 50-70 (not overbought)",
            },
            "counter_trend": {
                "condition": "Price at key support/resistance level",
                "trigger": "Reversal candlestick pattern",
                "confirmation": "Divergence in RSI or MACD",
                "volume_requirement": "Above average volume on reversal",
            },
        },
        "exit_strategy": {
            "take_profit_levels": {
                "conservative": f"{2.0 * multiplier * adjustment['tp']:.1f}%",
                "moderate": f"{4.0 * multiplier * adjustment['tp']:.1f}%",
                "aggressive": f"{6.0 * multiplier * adjustment['tp']:.1f}%",
            },
            "stop_loss": {
                "initial": f"{1.5 * multiplier * adjustment['sl']:.1f}%",
                "trailing": "Trail by 50% of unrealized profit",
                "time_based": "Exit 30 minutes before major news",
            },
            "partial_exits": {
                "first_target": "Take 50% profit at first level",
                "second_target": "Take 30% profit at second level",
                "final_runner": "Let 20% run to final target",
            },
        },
        "position_sizing": {
            "base_size": f"{5 / multiplier:.1f}% of portfolio per trade",
            "pyramid_rules": "Add 25% on confirmation after initial entry",
            "max_risk_per_trade": f"{2.0 * multiplier:.1f}% of portfolio",
            "correlation_limit": "Maximum 3 correlated positions",
        },
        "timing_considerations": {
            "best_sessions": ["Asian overlap", "European open", "US morning"],
            "avoid_times": ["Low volume periods", "15min before/after news"],
            "day_structure": "Focus on first 4 hours of major sessions",
        },
        "risk_management": {
            "daily_loss_limit": f"{5.0 * multiplier:.1f}% of portfolio",
            "max_drawdown": f"{8.0 * multiplier:.1f}% of portfolio",
            "win_rate_target": "55-65%",
            "profit_factor": "1.5 minimum",
            "consecutive_losses": "Stop after 3 losses in a row",
        },
        "market_adaptation": {
            "trending_markets": "Focus on breakout strategies",
            "ranging_markets": "Use mean reversion approaches",
            "high_volatility": "Reduce position size by 50%",
            "low_volatility": "Avoid trading or use scalping",
        },
        "monitoring_checklist": [
            "Check higher timeframe trend alignment",
            "Monitor key support/resistance levels",
            "Watch for volume confirmation",
            "Track correlation with major cryptos",
            "Be aware of upcoming news events",
        ],
        "confidence_level": adjustment["confidence"],
    }

    return json.dumps(strategy, ensure_ascii=False, indent=2)


@tool
def generate_swing_trading_strategy(
    symbol: str,
    timeframe: str = "4h",
    risk_level: str = "medium",
    trend_bias: str = "bullish",
) -> str:
    """
    Generates swing trading strategies for medium-term positions (hold 1-5 days).

    Creates strategies designed to capture larger price swings over several days,
    focusing on major trend movements and market cycles.

    Args:
        symbol (str): Cryptocurrency symbol
        timeframe (str): Primary analysis timeframe ("1h", "4h", "1d" - default: "4h")
        risk_level (str): Risk tolerance level
        trend_bias (str): Market bias ("bullish", "bearish", "neutral")

    Returns:
        str: JSON string containing swing trading strategy with:
             - Weekly/daily trend analysis
             - Wider stop-loss levels (3-8%)
             - Larger take-profit targets (8-25%)
             - Fundamental analysis integration
             - Multi-day holding considerations
    """

    risk_multipliers = {"low": 0.7, "medium": 1.0, "high": 1.3}

    trend_adjustments = {
        "bullish": {"direction": "long", "confidence": 0.8, "tp_mult": 1.2},
        "bearish": {"direction": "short", "confidence": 0.8, "tp_mult": 1.2},
        "neutral": {"direction": "both", "confidence": 0.6, "tp_mult": 1.0},
    }

    multiplier = risk_multipliers.get(risk_level, 1.0)
    trend_adj = trend_adjustments.get(trend_bias, trend_adjustments["neutral"])

    strategy = {
        "strategy_type": "Swing Trading",
        "symbol": symbol.upper(),
        "primary_timeframe": timeframe,
        "trend_bias": trend_bias,
        "risk_level": risk_level,
        "holding_period": "1-5 days",
        "generated_at": int(time.time()),
        "trend_analysis": {
            "weekly_trend": "Analyze weekly chart for major direction",
            "daily_structure": "Identify daily support/resistance zones",
            "key_levels": "Mark significant swing highs/lows",
            "volume_profile": "Identify high-volume nodes as key levels",
        },
        "entry_setup": {
            "long_conditions": {
                "trend": "Higher highs and higher lows on daily",
                "pullback": "Retest of broken resistance as support",
                "indicators": "RSI oversold bounce from 30-40 zone",
                "volume": "Volume expansion on bounce confirmation",
                "pattern": "Bull flag, cup & handle, or ascending triangle",
            },
            "short_conditions": {
                "trend": "Lower highs and lower lows on daily",
                "rejection": "Rejection from key resistance level",
                "indicators": "RSI overbought rejection from 60-70 zone",
                "volume": "Volume expansion on breakdown",
                "pattern": "Bear flag, head & shoulders, or descending triangle",
            },
        },
        "position_management": {
            "initial_size": f"{10 / multiplier:.1f}% of portfolio",
            "scaling": "Add 25% on breakout confirmation",
            "maximum_size": f"{15 / multiplier:.1f}% of portfolio per position",
            "correlation_check": "Limit exposure to correlated assets",
        },
        "exit_strategy": {
            "take_profit_targets": {
                "target_1": f"{8 * multiplier * trend_adj['tp_mult']:.1f}% - Take 40%",
                "target_2": f"{15 * multiplier * trend_adj['tp_mult']:.1f}% - Take 35%",
                "target_3": f"{25 * multiplier * trend_adj['tp_mult']:.1f}% - Take 25%",
            },
            "stop_loss": {
                "initial": f"{5 * multiplier:.1f}% below entry",
                "adjustment": "Move to breakeven after 8% profit",
                "trailing": "Trail by previous swing low/high",
                "time_stop": "Exit if no progress after 7 days",
            },
            "early_exit_signals": [
                "Break of major trend line",
                "Volume drying up significantly",
                "Negative divergence in momentum",
                "Major fundamental news change",
            ],
        },
        "risk_controls": {
            "portfolio_heat": f"{15 * multiplier:.1f}% maximum portfolio risk",
            "single_position": f"{5 * multiplier:.1f}% maximum loss per trade",
            "drawdown_limit": f"{12 * multiplier:.1f}% maximum drawdown",
            "win_rate_target": "45-55% (higher reward/risk ratio)",
            "profit_factor": "2.0+ target",
        },
        "fundamental_considerations": {
            "news_impact": "Monitor major announcements and partnerships",
            "market_events": "Track regulatory news and adoption trends",
            "seasonal_factors": "Consider crypto market cycles",
            "correlation_analysis": "Monitor Bitcoin dominance and market correlation",
        },
        "timing_optimization": {
            "entry_timing": "Enter during pullbacks in strong trends",
            "avoid_periods": "Major option expirations, holiday periods",
            "best_setups": "Sunday-Tuesday for entries, Friday for exits",
            "news_filter": "Avoid entries 24h before major events",
        },
        "monitoring_protocol": {
            "daily_review": "Check key levels and trend integrity",
            "weekly_assessment": "Review overall market structure",
            "position_health": "Monitor unrealized P&L and time decay",
            "exit_preparation": "Prepare exit plan at resistance levels",
        },
        "confidence_level": trend_adj["confidence"],
        "expected_metrics": {
            "win_rate": "45-55%",
            "avg_win": f"{12 * trend_adj['tp_mult']:.1f}%",
            "avg_loss": f"{4 * multiplier:.1f}%",
            "profit_factor": "2.5+",
            "max_drawdown": f"{10 * multiplier:.1f}%",
        },
    }

    return json.dumps(strategy, ensure_ascii=False, indent=2)


@tool
def generate_risk_management_plan(
    portfolio_size: float,
    risk_tolerance: str = "medium",
    trading_style: str = "day_trading",
) -> str:
    """
    Generates comprehensive risk management plan tailored to trading style and risk tolerance.

    Creates detailed risk management framework with position sizing,
    stop-loss rules, and portfolio protection measures.

    Args:
        portfolio_size (float): Total portfolio value in USD
        risk_tolerance (str): Risk level ("conservative", "medium", "aggressive")
        trading_style (str): Trading approach ("scalping", "day_trading", "swing_trading")

    Returns:
        str: JSON string containing comprehensive risk management plan
    """

    risk_profiles = {
        "conservative": {
            "max_risk_per_trade": 1.0,
            "max_daily_risk": 2.0,
            "max_portfolio_risk": 10.0,
            "max_drawdown": 8.0,
        },
        "medium": {
            "max_risk_per_trade": 2.0,
            "max_daily_risk": 4.0,
            "max_portfolio_risk": 15.0,
            "max_drawdown": 12.0,
        },
        "aggressive": {
            "max_risk_per_trade": 3.0,
            "max_daily_risk": 6.0,
            "max_portfolio_risk": 20.0,
            "max_drawdown": 15.0,
        },
    }

    style_adjustments = {
        "scalping": {"trades_per_day": 10, "hold_time": "minutes", "win_rate": 70},
        "day_trading": {"trades_per_day": 3, "hold_time": "hours", "win_rate": 60},
        "swing_trading": {"trades_per_day": 0.5, "hold_time": "days", "win_rate": 50},
    }

    profile = risk_profiles.get(risk_tolerance, risk_profiles["medium"])
    style = style_adjustments.get(trading_style, style_adjustments["day_trading"])

    plan = {
        "risk_management_plan": {
            "portfolio_size": portfolio_size,
            "risk_tolerance": risk_tolerance,
            "trading_style": trading_style,
            "generated_at": int(time.time()),
            "position_sizing_rules": {
                "max_risk_per_trade": f"{profile['max_risk_per_trade']:.1f}% (${portfolio_size * profile['max_risk_per_trade'] / 100:.0f})",
                "position_size_formula": "Risk Amount / (Entry Price - Stop Loss Price)",
                "max_position_size": f"{profile['max_portfolio_risk'] / 2:.1f}% of portfolio per single position",
                "correlation_limit": "Maximum 50% in correlated assets",
            },
            "daily_limits": {
                "max_daily_risk": f"{profile['max_daily_risk']:.1f}% (${portfolio_size * profile['max_daily_risk'] / 100:.0f})",
                "max_trades_per_day": int(style["trades_per_day"] * 2),
                "loss_limit_rule": "Stop trading after reaching daily loss limit",
                "profit_target": f"Take profits at {profile['max_daily_risk'] * 2:.1f}% daily gain",
            },
            "stop_loss_framework": {
                "technical_stops": "Based on support/resistance levels",
                "percentage_stops": f"{profile['max_risk_per_trade'] / 2:.1f}% for tight stops",
                "volatility_stops": "2x ATR for swing trades",
                "time_stops": f"Exit after {style['hold_time']} without progress",
                "trailing_stops": "Trail by 50% of unrealized profit",
            },
            "portfolio_protection": {
                "max_drawdown_limit": f"{profile['max_drawdown']:.1f}%",
                "drawdown_action": "Reduce position sizes by 50% at limit",
                "recovery_protocol": "Gradual size increase after 3 consecutive wins",
                "emergency_exit": "Close all positions if drawdown exceeds limit",
            },
            "psychological_rules": {
                "consecutive_loss_limit": 3,
                "cooling_off_period": "1 hour after 3 losses",
                "revenge_trading_prevention": "Mandatory break after emotional trades",
                "profit_protection": "Take 50% off table after 10% account growth",
            },
            "monitoring_system": {
                "daily_review": "Calculate P&L and risk exposure",
                "weekly_assessment": "Review strategy performance",
                "monthly_analysis": "Comprehensive risk metrics review",
                "key_metrics": [
                    "Win rate",
                    "Profit factor",
                    "Maximum drawdown",
                    "Sharpe ratio",
                ],
            },
        }
    }

    return json.dumps(plan, ensure_ascii=False, indent=2)


# 将新工具添加到工具列表
additional_tools = [
    generate_scalping_strategy,
    generate_day_trading_strategy,
    generate_swing_trading_strategy,
    generate_risk_management_plan,
]
