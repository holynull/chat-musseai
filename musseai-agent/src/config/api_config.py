# config/api_config.py
import os
from typing import Dict, Any


class APIConfig:
    """API配置管理"""

    def __init__(self):
        self.configs = {
            "coingecko": {
                "base_url": "https://api.coingecko.com/api/v3",
                "api_key": os.getenv("COINGECKO_API_KEY"),
                "rate_limits": {
                    "free": 50,  # 每分钟50次
                    "demo": 500,  # 每分钟500次
                    "paid": 10000,  # 每分钟10000次
                },
                "cache_duration": 300,
                "timeout": 10,
                "max_retries": 3,
                "backoff_factor": 1.5,
            },
            "coincap": {
                "base_url": "https://api.coincap.io/v2",
                "api_key": None,  # 不需要API密钥
                "rate_limits": {
                    "free": 600,  # 每分钟600次
                },
                "cache_duration": 180,
                "timeout": 8,
                "max_retries": 2,
                "backoff_factor": 1.2,
            },
            "binance": {
                "base_url": "https://api.binance.com/api/v3",
                "api_key": None,  # 公共API不需要
                "rate_limits": {
                    "free": 1200,  # 每分钟1200权重
                },
                "cache_duration": 120,
                "timeout": 5,
                "max_retries": 2,
                "backoff_factor": 1.0,
            },
            "cryptocompare": {
                "base_url": "https://min-api.cryptocompare.com/data",
                "api_key": os.getenv("CRYPTOCOMPARE_API_KEY"),
                "rate_limits": {
                    "free": 100000,  # 每月100k次
                },
                "cache_duration": 360,
                "timeout": 10,
                "max_retries": 3,
                "backoff_factor": 1.3,
            },
        }

    def get_config(self, api_name: str) -> Dict[str, Any]:
        """获取指定API的配置"""
        return self.configs.get(api_name, {})

    def get_rate_limit(self, api_name: str, tier: str = "free") -> int:
        """获取API速率限制"""
        config = self.get_config(api_name)
        return config.get("rate_limits", {}).get(tier, 60)


# 全局配置实例
api_config = APIConfig()
