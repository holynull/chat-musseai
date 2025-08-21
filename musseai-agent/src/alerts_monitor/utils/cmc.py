import json
from logging import Logger
import logging
import traceback
import requests
import os


def getLatestQuote(
    symbol: str,
    logger: Logger = logging.getLogger("alert_conditions"),
) -> str:
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
    try:
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
        }
        url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol={symbol}"
        response = requests.get(url, headers=headers)
        return json.dumps(response.json())
    except Exception as e:
        logger.error(traceback.format_exc())
        return e
