# src/utils/api_manager.py
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loggers import logger
import traceback

class MultiAPIManager:
    def __init__(self):
        self.apis = {
            'coingecko': {
                'base_url': 'https://api.coingecko.com/api/v3',
                'rate_limit': 1.2,  # 50 requests/minute
                'daily_limit': 10000,
                'priority': 1,
                'last_request': 0
            },
            'coincap': {
                'base_url': 'https://api.coincap.io/v2',
                'rate_limit': 0.1,  # 10 requests/second
                'daily_limit': None,
                'priority': 2,
                'last_request': 0
            },
            'binance': {
                'base_url': 'https://api.binance.com/api/v3',
                'rate_limit': 0.1,  # 10 requests/second
                'daily_limit': None,
                'priority': 3,
                'last_request': 0
            },
            'cryptocompare': {
                'base_url': 'https://min-api.cryptocompare.com/data',
                'rate_limit': 0.05,  # 20 requests/second
                'daily_limit': 100000,  # monthly
                'priority': 4,
                'last_request': 0
            }
        }
        self.symbol_mapping = self._init_symbol_mapping()
        
    def _init_symbol_mapping(self):
        """初始化不同API的符号映射"""
        return {
            'coingecko': {},  # Will be populated dynamically
            'coincap': {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'BNB': 'binance-coin',
                'ADA': 'cardano',
                'SOL': 'solana',
                'DOT': 'polkadot',
                'MATIC': 'polygon',
                'AVAX': 'avalanche',
                'DOGE': 'dogecoin',
                'SHIB': 'shiba-inu'
            },
            'binance': {
                # Binance uses direct symbols like BTCUSDT
            },
            'cryptocompare': {
                # CryptoCompare uses direct symbols
            }
        }

    def _wait_for_rate_limit(self, api_name: str):
        """等待满足API速率限制"""
        api_config = self.apis[api_name]
        elapsed = time.time() - api_config['last_request']
        if elapsed < api_config['rate_limit']:
            time.sleep(api_config['rate_limit'] - elapsed)
        api_config['last_request'] = time.time()

    def fetch_historical_prices_coingecko(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """从CoinGecko获取历史价格"""
        try:
            self._wait_for_rate_limit('coingecko')
            
            # Get coin ID mapping if not cached
            if not self.symbol_mapping['coingecko']:
                self.symbol_mapping['coingecko'] = self._get_coingecko_mapping()
            
            coin_id = self.symbol_mapping['coingecko'].get(symbol.upper())
            if not coin_id:
                return None
                
            url = f"{self.apis['coingecko']['base_url']}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return self._process_coingecko_data(data)
            
        except Exception as e:
            logger.error(f"CoinGecko API failed for {symbol}: {e}")
            traceback.format_exc()
            return None

    def fetch_historical_prices_coincap(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """从CoinCap获取历史价格"""
        try:
            self._wait_for_rate_limit('coincap')
            
            # CoinCap uses asset IDs
            asset_id = self.symbol_mapping['coincap'].get(symbol.upper())
            if not asset_id:
                asset_id = symbol.lower()  # fallback
            
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            url = f"{self.apis['coincap']['base_url']}/assets/{asset_id}/history"
            params = {
                'interval': 'd1',
                'start': start_time,
                'end': end_time
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return self._process_coincap_data(data)
            
        except Exception as e:
            logger.error(f"CoinCap API failed for {symbol}: {e}")
            traceback.format_exc()
            return None

    def fetch_historical_prices_binance(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """从Binance获取历史价格"""
        try:
            self._wait_for_rate_limit('binance')
            
            # Binance uses USDT pairs
            binance_symbol = f"{symbol.upper()}USDT"
            
            url = f"{self.apis['binance']['base_url']}/klines"
            params = {
                'symbol': binance_symbol,
                'interval': '1d',
                'limit': min(days, 1000)  # Binance limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return self._process_binance_data(data)
            
        except Exception as e:
            logger.error(f"Binance API failed for {symbol}: {e}")
            traceback.format_exc()
            return None

    def fetch_historical_prices_cryptocompare(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """从CryptoCompare获取历史价格"""
        try:
            self._wait_for_rate_limit('cryptocompare')
            
            url = f"{self.apis['cryptocompare']['base_url']}/v2/histoday"
            params = {
                'fsym': symbol.upper(),
                'tsym': 'USD',
                'limit': days,
                'aggregate': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return self._process_cryptocompare_data(data)
            
        except Exception as e:
            logger.error(f"CryptoCompare API failed for {symbol}: {e}")
            traceback.format_exc()
            return None

    def fetch_with_fallback(self, symbol: str, days: int = 90) -> Optional[Dict]:
        """使用多API故障转移机制"""
        # 按优先级排序API
        sorted_apis = sorted(self.apis.keys(), key=lambda x: self.apis[x]['priority'])
        
        for api_name in sorted_apis:
            try:
                logger.info(f"Trying {api_name} for {symbol}")
                
                if api_name == 'coingecko':
                    result = self.fetch_historical_prices_coingecko(symbol, days)
                elif api_name == 'coincap':
                    result = self.fetch_historical_prices_coincap(symbol, days)
                elif api_name == 'binance':
                    result = self.fetch_historical_prices_binance(symbol, days)
                elif api_name == 'cryptocompare':
                    result = self.fetch_historical_prices_cryptocompare(symbol, days)
                else:
                    continue
                
                if result and len(result.get('prices', [])) > 10:
                    logger.info(f"Successfully fetched data from {api_name} for {symbol}")
                    return result
                    
            except Exception as e:
                logger.warning(f"API {api_name} failed for {symbol}: {e}")
                traceback.format_exc()
                continue
        
        logger.error(f"All APIs failed for {symbol}")
        return None

    def _process_coingecko_data(self, data: Dict) -> Dict:
        """处理CoinGecko数据格式"""
        prices = data.get('prices', [])
        if not prices:
            return {}
            
        df = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['returns'] = df['price'].pct_change().dropna()
        
        return {
            'prices': df['price'].tolist(),
            'returns': df['returns'].tolist(),
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'volatility': df['returns'].std() * np.sqrt(365),
            'mean_return': df['returns'].mean() * 365,
        }

    def _process_coincap_data(self, data: Dict) -> Dict:
        """处理CoinCap数据格式"""
        history = data.get('data', [])
        if not history:
            return {}
            
        prices = [float(item['priceUsd']) for item in history if item['priceUsd']]
        dates = [item['date'] for item in history]
        
        if len(prices) < 2:
            return {}
            
        returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]
        
        return {
            'prices': prices,
            'returns': returns,
            'dates': dates,
            'volatility': np.std(returns) * np.sqrt(365) if returns else 0,
            'mean_return': np.mean(returns) * 365 if returns else 0,
        }

    def _process_binance_data(self, data: List) -> Dict:
        """处理Binance数据格式"""
        if not data:
            return {}
            
        prices = [float(kline[4]) for kline in data]  # Close price
        dates = [pd.to_datetime(int(kline[0]), unit='ms').strftime('%Y-%m-%d') for kline in data]
        
        if len(prices) < 2:
            return {}
            
        returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]
        
        return {
            'prices': prices,
            'returns': returns,
            'dates': dates,
            'volatility': np.std(returns) * np.sqrt(365) if returns else 0,
            'mean_return': np.mean(returns) * 365 if returns else 0,
        }

    def _process_cryptocompare_data(self, data: Dict) -> Dict:
        """处理CryptoCompare数据格式"""
        history = data.get('Data', {}).get('Data', [])
        if not history:
            return {}
            
        prices = [float(item['close']) for item in history if item['close']]
        dates = [pd.to_datetime(int(item['time']), unit='s').strftime('%Y-%m-%d') for item in history]
        
        if len(prices) < 2:
            return {}
            
        returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]
        
        return {
            'prices': prices,
            'returns': returns,
            'dates': dates,
            'volatility': np.std(returns) * np.sqrt(365) if returns else 0,
            'mean_return': np.mean(returns) * 365 if returns else 0,
        }

    def _get_coingecko_mapping(self) -> Dict[str, str]:
        """获取CoinGecko符号映射"""
        try:
            self._wait_for_rate_limit('coingecko')
            url = f"{self.apis['coingecko']['base_url']}/coins/list"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            coins = response.json()
            mapping = {}
            for coin in coins:
                symbol = coin['symbol'].upper()
                if symbol not in mapping:  # 优先保留排名靠前的币种
                    mapping[symbol] = coin['id']
            
            return mapping
            
        except Exception as e:
            logger.error(f"Failed to get CoinGecko mapping: {e}")
            traceback.format_exc()
            return {}

# 全局实例
api_manager = MultiAPIManager()
