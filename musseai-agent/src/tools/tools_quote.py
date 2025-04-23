from langchain.agents import tool
import requests
import json
from tradingview_ta import TA_Handler, Interval, Exchange
import os


@tool
def getLatestQuote(symbol: str) -> str:
    """
    Retrieves the latest cryptocurrency quotation data from CoinMarketCap API.

    This function fetches real-time price and market data for a specified cryptocurrency
    using the CoinMarketCap Pro API v2. The data includes latest price, market cap,
    volume, and other market metrics.

    Input:
    - symbol (str): Cryptocurrency symbol (e.g., 'BTC' for Bitcoin, 'ETH' for Ethereum)

    Output:
    - Returns a JSON string containing latest market data including:
        * Current price
        * Market cap
        * 24h volume
        * Circulating supply
        * Other market metrics

    Example usage:
    getLatestQuote("BTC") - Get latest Bitcoin market data
    getLatestQuote("ETH") - Get latest Ethereum market data
    """
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
    }
    url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol={symbol}"
    response = requests.get(url, headers=headers)
    return json.dumps(response.json())


@tool
def getTokenMetadata(symbol: str) -> str:
    """
    Retrieves detailed metadata and information about a cryptocurrency from CoinMarketCap API.

    This function fetches comprehensive metadata about a cryptocurrency using the CoinMarketCap
    Pro API v2. The data includes basic information, platform details, various URLs, and
    other relevant metadata.

    Input:
    - symbol (str): Cryptocurrency symbol (e.g., 'BTC' for Bitcoin, 'ETH' for Ethereum)

    Output:
    - Returns a JSON string containing cryptocurrency metadata including:
        * Basic information (name, symbol, logo)
        * Platform details (e.g., contract addresses)
        * URLs (website, technical documentation, source code)
        * Project description
        * Tag information
        * Date added to CoinMarketCap
        * Category information

    Example usage:
    getTokenMetadata("BTC") - Get Bitcoin metadata
    getTokenMetadata("ETH") - Get Ethereum metadata
    """
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
    }
    url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/info?symbol={symbol}"
    response = requests.get(url, headers=headers)
    return json.dumps(response.json())


@tool
def buy_sell_signal(symbol: str) -> str:
    """Analyzes trading signals for cryptocurrency pairs against USDT using TradingView technical analysis.

    This function provides comprehensive technical analysis including:
    - Overall market summary (buy/sell/neutral signals)
    - Oscillator analysis (RSI, Stochastic, CCI, etc.)
    - Moving averages analysis (EMA, SMA across different periods)
    - Detailed technical indicators

    Input:
    - symbol (str): Cryptocurrency symbol (e.g., 'BTC' for Bitcoin, 'ETH' for Ethereum)

    Output:
    - Returns a detailed analysis string containing:
        * Current market trend analysis
        * Signal strength score (1-10 scale)
        * Trading recommendations based on technical indicators
        * Comprehensive market analysis combining multiple technical factors

    Example usage:
    buy_sell_signal("BTC") - Analyzes BTC/USDT trading pair
    buy_sell_signal("ETH") - Analyzes ETH/USDT trading pair
    """
    btc_usdt = TA_Handler(
        symbol=f"{symbol}USDT",
        screener="crypto",
        exchange="GATEIO",
        interval=Interval.INTERVAL_1_DAY,
    )
    summary = btc_usdt.get_analysis().summary
    oscillators = btc_usdt.get_analysis().oscillators
    moving_averages = btc_usdt.get_analysis().moving_averages
    indicators = btc_usdt.get_analysis().indicators
    return {
        "summary": summary,
        "oscillators": oscillators,
        "moving_averages": moving_averages,
        "indicators": indicators,
    }


tools = [getLatestQuote, getTokenMetadata, buy_sell_signal]
