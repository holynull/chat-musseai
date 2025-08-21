from loggers import logger
import traceback
from utils.api_decorators import (
    clear_cache,
)

class SmartCacheInvalidator:
    """Smart cache invalidation based on market conditions"""

    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.last_btc_price = None
        self.volatility_threshold = 0.05  # 5% price change triggers refresh

    def should_invalidate_cache(self) -> bool:
        """Check if cache should be invalidated due to high volatility"""
        try:
            # Get current BTC price as market indicator
            current_btc_data = self.api_manager.fetch_market_data("BTC")
            if not current_btc_data:
                return False

            current_price = current_btc_data.get("current_price", 0)

            if self.last_btc_price is None:
                self.last_btc_price = current_price
                return False

            # Calculate price change
            price_change = (
                abs(current_price - self.last_btc_price) / self.last_btc_price
            )

            if price_change > self.volatility_threshold:
                logger.info(
                    f"High volatility detected: {price_change:.2%} BTC price change, invalidating cache"
                )
                self.last_btc_price = current_price
                return True

            return False

        except Exception as e:
            logger.warning(
                f"Failed to check market volatility: {e}\n{traceback.format_exc()}"
            )
            return False

    def conditional_cache_refresh(self):
        """Refresh cache only if market conditions warrant it"""
        if self.should_invalidate_cache():
            logger.info("Triggering conditional cache refresh due to market volatility")
            # Clear existing cache
            clear_cache("*market*")
            # Trigger fresh data load
            self.api_manager.batch_cache_manager.preload_all_market_data()