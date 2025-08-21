import json
from logging import Logger
import logging
import traceback
import requests
import os

from utils.api_decorators import api_call_with_cache_and_rate_limit


@api_call_with_cache_and_rate_limit(
    cache_duration=300,  # 5分钟缓存
    rate_limit_interval=1.2,  # 1.2秒间隔
    max_retries=2,
    retry_delay=1,
)
def getLatestQuote(
    symbols: str,
    logger: Logger = None,
) -> str:
    """
    Retrieves the latest cryptocurrency quotation data from CoinMarketCap API.

    This function fetches real-time price and market data for a specified cryptocurrency
    using the CoinMarketCap Pro API v2. The data includes latest price, market cap,
    volume, and other market metrics.

    Input:
    - symbols (str): Alternatively pass one or more comma-separated cryptocurrency symbols. Example: "BTC,ETH". At least one "id" or "slug" or "symbol" is required for this request.

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
    if logger is None:
        logger = logging.getLogger("alert_conditions")
    try:
        logger.info(f"Get latest quote from CMC API. {symbols}")
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
        }
        url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol={symbols}"
        response = requests.get(url, headers=headers)
        return json.dumps(response.json())
    except Exception as e:
        logger.error(traceback.format_exc())
        return e
