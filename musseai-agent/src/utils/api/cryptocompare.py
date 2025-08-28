import json
from logging import Logger
import logging
import traceback
import requests
import os

from utils.api_decorators import api_call_with_cache_and_rate_limit

@api_call_with_cache_and_rate_limit(
    cache_duration=3600,
    rate_limit_interval=1.2,  # 1.2 seconds interval
    max_retries=2,
    retry_delay=1,
)
def getLatestQuote(
    symbols: str,
    logger: Logger = None,
) -> str:
    """
    Retrieves the latest cryptocurrency quotation data from CryptoCompare API.

    This function fetches real-time price and market data for specified cryptocurrencies
    using the CryptoCompare API. The data includes latest price, market cap,
    volume, and other market metrics.

    Input:
    - symbols (str): Comma-separated cryptocurrency symbols. Example: "BTC,ETH". 
                    CryptoCompare supports up to 100 symbols per request.

    Output:
    - Returns a JSON string containing latest market data including:
        * Current price in multiple currencies (USD, EUR, etc.)
        * Market cap
        * 24h volume
        * 24h price changes
        * Supply information
        * Other market metrics

    Example usage:
    _getLatestQuote("BTC") - Get latest Bitcoin market data
    _getLatestQuote("ETH") - Get latest Ethereum market data
    _getLatestQuote("BTC,ETH,ADA") - Get multiple cryptocurrencies data
    """
    if logger is None:
        logger = logging.getLogger("alert_conditions")
    
    try:
        logger.info(f"Get latest quote from CryptoCompare API. {symbols}")
        
        # CryptoCompare API endpoint for multiple symbol price data
        base_url = "https://min-api.cryptocompare.com/data/pricemultifull"
        
        # Parameters for the API request
        params = {
            'fsyms': symbols,  # From symbols (the cryptocurrencies we want data for)
            'tsyms': 'USD,EUR,BTC',  # To symbols (currencies to convert to)
            'tryConversion': 'true',  # Try conversion even if direct trading pair doesn't exist
        }
        
        # Add API key if available (CryptoCompare has free tier but API key improves limits)
        api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        if api_key:
            params['api_key'] = api_key
        
        # Make the API request
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()  # Raise exception for bad status codes
        
        data = response.json()
        
        # Check if the response contains error
        if 'Response' in data and data['Response'] == 'Error':
            error_msg = data.get('Message', 'Unknown error from CryptoCompare API')
            logger.error(f"CryptoCompare API error: {error_msg}")
            return json.dumps({
                "error": True,
                "message": error_msg,
                "requested_symbols": symbols
            })
        
        # Process and enhance the response data
        processed_data = {
            "source": "CryptoCompare",
            "timestamp": data.get("MetaData", {}).get("LastUpdateTS", ""),
            "symbols_requested": symbols.split(","),
            "data": {}
        }
        
        # Extract DISPLAY data (formatted for humans) and RAW data (for calculations)
        display_data = data.get("DISPLAY", {})
        raw_data = data.get("RAW", {})
        
        # Process each requested symbol
        for symbol in symbols.split(","):
            symbol = symbol.strip().upper()
            
            if symbol in display_data and symbol in raw_data:
                # Combine display and raw data for comprehensive information
                symbol_data = {
                    "symbol": symbol,
                    "prices": {},
                    "market_data": {},
                    "changes": {},
                    "volume": {},
                    "supply": {}
                }
                
                # Extract price data for different currencies
                for currency in ['USD', 'EUR', 'BTC']:
                    if currency in display_data[symbol]:
                        display_curr = display_data[symbol][currency]
                        raw_curr = raw_data[symbol][currency]
                        
                        symbol_data["prices"][currency] = {
                            "price": display_curr.get("PRICE", ""),
                            "price_raw": raw_curr.get("PRICE", 0),
                            "market_cap": display_curr.get("MKTCAP", ""),
                            "market_cap_raw": raw_curr.get("MKTCAP", 0)
                        }
                        
                        symbol_data["changes"][currency] = {
                            "change_24h": display_curr.get("CHANGE24HOUR", ""),
                            "change_24h_pct": display_curr.get("CHANGEPCT24HOUR", ""),
                            "change_24h_raw": raw_curr.get("CHANGE24HOUR", 0),
                            "change_24h_pct_raw": raw_curr.get("CHANGEPCT24HOUR", 0)
                        }
                        
                        symbol_data["volume"][currency] = {
                            "volume_24h": display_curr.get("VOLUME24HOUR", ""),
                            "volume_24h_to": display_curr.get("VOLUME24HOURTO", ""),
                            "volume_24h_raw": raw_curr.get("VOLUME24HOUR", 0),
                            "volume_24h_to_raw": raw_curr.get("VOLUME24HOURTO", 0)
                        }
                
                # Add additional market data from USD data (most comprehensive)
                if 'USD' in raw_data[symbol]:
                    usd_raw = raw_data[symbol]['USD']
                    symbol_data["market_data"] = {
                        "circulating_supply": usd_raw.get("CIRCULATINGSUPPLY", 0),
                        "total_supply": usd_raw.get("SUPPLY", 0),
                        "last_update": usd_raw.get("LASTUPDATE", 0),
                        "high_24h": usd_raw.get("HIGH24HOUR", 0),
                        "low_24h": usd_raw.get("LOW24HOUR", 0),
                        "open_24h": usd_raw.get("OPEN24HOUR", 0)
                    }
                
                processed_data["data"][symbol] = symbol_data
            else:
                # Symbol not found in response
                processed_data["data"][symbol] = {
                    "error": f"Symbol {symbol} not found or not supported",
                    "symbol": symbol
                }
                logger.warning(f"Symbol {symbol} not found in CryptoCompare response")
        
        return json.dumps(processed_data, ensure_ascii=False, indent=2)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "error": True,
            "message": error_msg,
            "requested_symbols": symbols,
            "error_type": "network_error"
        })
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response from CryptoCompare API: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "error": True,
            "message": error_msg,
            "requested_symbols": symbols,
            "error_type": "json_decode_error"
        })
    except Exception as e:
        error_msg = f"Unexpected error when calling CryptoCompare API: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return json.dumps({
            "error": True,
            "message": error_msg,
            "requested_symbols": symbols,
            "error_type": "unexpected_error"
        })