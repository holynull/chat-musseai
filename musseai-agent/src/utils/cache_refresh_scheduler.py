import threading
import time
from loggers import logger
import traceback

class CacheRefreshScheduler:
    """Background scheduler for cache refresh"""

    def __init__(self, batch_cache_manager):
        self.batch_cache_manager = batch_cache_manager
        self.scheduler_thread = None
        self.running = False

    def start_scheduler(self):
        """Start background cache refresh scheduler"""
        if self.running:
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Cache refresh scheduler started")

    def stop_scheduler(self):
        """Stop background scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Cache refresh scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Refresh every 4 hours
                time.sleep(4 * 3600)

                if self.running:
                    logger.info("Starting scheduled cache refresh...")
                    self.batch_cache_manager.preload_all_market_data()
                    logger.info("Scheduled cache refresh completed")

            except Exception as e:
                logger.error(
                    f"Scheduled cache refresh failed: {e}\n{traceback.format_exc()}"
                )
                # Continue running even if refresh fails
                time.sleep(300)  # Wait 5 minutes before retrying