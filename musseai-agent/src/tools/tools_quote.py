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


@tool
def getLatestContent(
    contentType: str = None, latestId: str = None, count: int = 10, page: int = 1
) -> str:
    """
    Retrieves the latest content from CoinMarketCap including news, trending coins, and educational materials.

    This function fetches the latest content using the CoinMarketCap Content API v1. Users can
    filter by content type and set pagination parameters.

    Input:
    - contentType (str, optional): Filter content by type. Available options:
      * 'news' - Latest news articles
      * 'trending' - Trending cryptocurrencies
      * 'education' - Educational content
      * 'calendars' - Upcoming events
      * 'statistics' - Market statistics
      If not specified, returns all content types.
    - latestId (str, optional): Get content newer than the specified content ID
    - count (int, optional): Number of content items to return (default: 10, max: 100)
    - page (int, optional): Page number for pagination (default: 1)

    Output:
    - Returns a JSON string containing latest content items with metadata including:
      * Content ID
      * Title
      * Publication date
      * URL
      * Source
      * Description
      * Related cryptocurrency data

    Example usage:
    getLatestContent() - Get latest mixed content
    getLatestContent(contentType="news") - Get latest news articles
    getLatestContent(contentType="trending", count=5) - Get top 5 trending cryptocurrencies
    """
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
    }

    # Build URL with query parameters
    url = "https://pro-api.coinmarketcap.com/v1/content/latest"
    params = {}

    # Add parameters only if they are provided
    if contentType:
        params["content_type"] = contentType
    if latestId:
        params["latest_id"] = latestId
    if count:
        params["count"] = min(count, 100)  # Ensure count doesn't exceed API limit
    if page:
        params["page"] = max(1, page)  # Ensure page is at least 1

    # Make the API request
    response = requests.get(url, headers=headers, params=params)

    # Return the response as a JSON string
    return json.dumps(response.json())


@tool
def getCommunityTrendingToken(
    timePeriod: str = "24h", timeStart: str = None, timeEnd: str = None
) -> str:
    """
    Retrieves trending tokens based on community activity from CoinMarketCap.

    This function fetches trending tokens data based on community activity metrics using
    the CoinMarketCap API v1. Users can specify different time periods for the analysis.

    Input:
    - timePeriod (str, optional): Time period for the trending analysis. Available options:
      * '24h' - Last 24 hours (default)
      * '7d' - Last 7 days
      * '30d' - Last 30 days
      * 'custom' - Custom time period (requires timeStart and timeEnd)
    - timeStart (str, optional): Start time for custom period (ISO 8601 format)
      Required if timePeriod is 'custom'
    - timeEnd (str, optional): End time for custom period (ISO 8601 format)
      Required if timePeriod is 'custom'

    Output:
    - Returns a JSON string containing trending tokens data including:
      * Token ranking
      * Token name and symbol
      * Community metrics
      * Price and market data
      * Trending score
      * Trading activity
      * Social media statistics

    Example usage:
    getCommunityTrendingToken() - Get trending tokens for last 24 hours
    getCommunityTrendingToken("7d") - Get trending tokens for last 7 days
    getCommunityTrendingToken("custom", "2023-01-01T00:00:00Z", "2023-01-07T00:00:00Z")
    """
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
    }

    # Base URL for the API endpoint
    url = "https://pro-api.coinmarketcap.com/v1/community/trending-token"

    # Initialize parameters dictionary
    params = {}

    # Validate and set time period
    valid_time_periods = ["24h", "7d", "30d", "custom"]
    if timePeriod not in valid_time_periods:
        raise ValueError(f"Invalid time_period. Must be one of {valid_time_periods}")

    params["time_period"] = timePeriod

    # Handle custom time period
    if timePeriod == "custom":
        if not timeStart or not timeEnd:
            raise ValueError(
                "timeStart and timeEnd are required for custom time period"
            )
        params["time_start"] = timeStart
        params["time_end"] = timeEnd

    # Make the API request
    response = requests.get(url, headers=headers, params=params)

    # Return the response as a JSON string
    return json.dumps(response.json())


tools = [
    getLatestQuote,
    getTokenMetadata,
    buy_sell_signal,
    getLatestContent,
    getCommunityTrendingToken,
]
