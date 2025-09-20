import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, cast
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor as ConcurrentThreadPoolExecutor

from langgraph_sdk import get_client, get_sync_client
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from loggers import DEFAULT_LOG_LEVEL
from telegram_service import TelegramNotificationService
import traceback

# Load environment configuration
load_dotenv(".env.trading_signal")


@dataclass
class TradingConfig:
    """Trading signal configuration"""

    langgraph_server_url: str
    user_id: str
    graph_name: str
    group_id: str
    timezone: str = "UTC"
    execution_interval: int = 15  # minutes
    thread_rebuild_hours: int = 24  # hours
    max_retries: int = 3
    retry_delay: int = 30  # seconds
    max_concurrent_symbols: int = 5  # NEW: Maximum concurrent symbol processing
    enable_backtest_processing: bool = False
    log_level: int = logging.INFO


@dataclass
class ThreadInfo:
    """Thread information with creation timestamp"""

    thread_id: str
    created_at: datetime
    symbol: str


class TradingSignalScheduler:
    """Trading signal scheduler with APScheduler and async symbol processing"""

    def __init__(self, config: TradingConfig):
        self.config = config
        self.scheduler = None
        self.sync_client = None
        self.async_client = None
        # Thread-safe storage for thread information
        self.threads: Dict[str, ThreadInfo] = {}
        self.threads_lock = threading.Lock()  # NEW: Thread safety

        self.setup_logging(config)
        self.setup_clients()

        # Initialize Telegram service
        self.telegram_service = None
        self.setup_telegram_service()

        self.group_id = config.group_id

        self.enable_backtest_processing = config.enable_backtest_processing

    def setup_telegram_service(self):
        """Initialize Telegram notification service"""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            try:
                self.telegram_service = TelegramNotificationService(
                    bot_token=bot_token, chat_storage_file="telegram_users.json"
                )
                self.logger.info("Telegram service initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize Telegram service: {e}")
                self.telegram_service = None
        else:
            self.logger.warning(
                "TELEGRAM_BOT_TOKEN not found, Telegram notifications disabled"
            )

    def setup_logging(self, config: TradingConfig):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)

        logging.basicConfig(
            level=config.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("logs/trading_signal.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def setup_clients(self):
        """Initialize LangGraph clients"""
        try:
            self.sync_client = get_sync_client(url=self.config.langgraph_server_url)
            self.async_client = get_client(url=self.config.langgraph_server_url)
            self.logger.info("Successfully initialized LangGraph clients")
        except Exception as e:
            self.logger.error(f"Failed to initialize LangGraph clients: {e}")
            raise

    def setup_scheduler(self):
        """Setup APScheduler with thread pool executor"""
        executors = {"default": ThreadPoolExecutor(max_workers=5)}

        self.scheduler = BlockingScheduler(
            executors=executors, timezone=self.config.timezone
        )

        # Add job to run every 15 minutes
        self.scheduler.add_job(
            func=self.execute_trading_signals_wrapper,  # Changed: wrapper for async execution
            trigger=IntervalTrigger(minutes=self.config.execution_interval),
            id="trading_signal_job",
            name="Trading Signal Generation",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping executions
        )

        self.logger.info(
            f"Scheduler configured to run every {self.config.execution_interval} minutes"
        )
        self.logger.info(
            f"Threads will be rebuilt every {self.config.thread_rebuild_hours} hours"
        )
        self.logger.info(
            f"Max concurrent symbols: {self.config.max_concurrent_symbols}"
        )

    def is_thread_expired(self, thread_info: ThreadInfo) -> bool:
        """Check if thread has exceeded the rebuild interval"""
        current_time = datetime.now()
        thread_age = current_time - thread_info.created_at
        rebuild_interval = timedelta(hours=self.config.thread_rebuild_hours)

        is_expired = thread_age >= rebuild_interval
        if is_expired:
            self.logger.info(
                f"Thread for {thread_info.symbol} is expired. "
                f"Age: {thread_age.total_seconds()/3600:.2f} hours, "
                f"Limit: {self.config.thread_rebuild_hours} hours"
            )

        return is_expired

    def delete_thread(self, symbol: str) -> bool:
        """Delete an existing thread (thread-safe)"""
        with self.threads_lock:
            if symbol not in self.threads:
                return True

            thread_info = self.threads[symbol]
            try:
                # Attempt to delete the thread via API if available
                if hasattr(self.sync_client.threads, "delete"):
                    self.sync_client.threads.delete(thread_id=thread_info.thread_id)
                    self.logger.info(
                        f"Successfully deleted thread {thread_info.thread_id} for {symbol}"
                    )
                else:
                    self.logger.warning(
                        f"Thread deletion not supported by client, marking as obsolete: {thread_info.thread_id}"
                    )

                # Remove from local tracking
                del self.threads[symbol]
                return True

            except Exception as e:
                self.logger.error(
                    f"Failed to delete thread {thread_info.thread_id} for {symbol}: {e}"
                )
                # Even if deletion fails, remove from local tracking to force recreation
                if symbol in self.threads:
                    del self.threads[symbol]
                return False

    def create_new_thread(self, symbol: str) -> str:
        """Create a new thread for the given symbol (thread-safe)"""
        with self.threads_lock:
            try:
                thread = self.sync_client.threads.create(
                    metadata={"user_id": self.config.user_id, "symbol": symbol}
                )

                thread_id = thread["thread_id"]
                thread_info = ThreadInfo(
                    thread_id=thread_id, created_at=datetime.now(), symbol=symbol
                )

                self.threads[symbol] = thread_info
                self.logger.info(
                    f"Created new thread for {symbol}: {thread_id} at {thread_info.created_at}"
                )

                return thread_id

            except Exception as e:
                self.logger.error(f"Failed to create new thread for {symbol}: {e}")
                raise

    def rebuild_thread_if_needed(self, symbol: str) -> str:
        """Rebuild thread if it's expired or doesn't exist (thread-safe)"""
        with self.threads_lock:
            # Check if thread exists and is still valid
            if symbol in self.threads:
                thread_info = self.threads[symbol]
                if not self.is_thread_expired(thread_info):
                    # Thread is still valid
                    self.logger.debug(
                        f"Using existing thread for {symbol}: {thread_info.thread_id}"
                    )
                    return thread_info.thread_id
                else:
                    # Thread is expired, need to rebuild
                    self.logger.info(f"Rebuilding expired thread for {symbol}")

        # Delete and create new thread (outside the lock to avoid deadlock)
        self.delete_thread(symbol)
        return self.create_new_thread(symbol)

    def create_or_get_thread(self, symbol: str) -> str:
        """Create or reuse thread for given symbol with 24-hour rebuild logic"""
        return self.rebuild_thread_if_needed(symbol)

    def cleanup_all_threads(self):
        """Cleanup all existing threads"""
        self.logger.info("Starting cleanup of all threads...")
        with self.threads_lock:
            symbols_to_cleanup = list(self.threads.keys())

        for symbol in symbols_to_cleanup:
            try:
                self.delete_thread(symbol)
            except Exception as e:
                self.logger.error(f"Error during cleanup of thread for {symbol}: {e}")

        self.logger.info(
            f"Thread cleanup completed. Cleaned up {len(symbols_to_cleanup)} threads"
        )

    def get_thread_status_summary(self) -> Dict[str, Any]:
        """Get summary of current thread status (thread-safe)"""
        current_time = datetime.now()
        with self.threads_lock:
            summary = {"total_threads": len(self.threads), "threads_detail": {}}

            for symbol, thread_info in self.threads.items():
                age_hours = (
                    current_time - thread_info.created_at
                ).total_seconds() / 3600
                summary["threads_detail"][symbol] = {
                    "thread_id": thread_info.thread_id,
                    "created_at": thread_info.created_at.isoformat(),
                    "age_hours": round(age_hours, 2),
                    "is_expired": self.is_thread_expired(thread_info),
                }

        return summary

    def _parse_content(self, data: dict) -> str:
        output = data.get("output", {})
        messages = output.get("messages", [])
        if len(messages) == 0:
            self.logger.error(f"Messages len is : 0")
            return None
        if not isinstance(messages[-1], dict):
            self.logger.error(f"Last message is not a ditc. {messages[-1]}")
            return None
        content = cast(dict, messages[-1]).get("content")
        content_txt = ""
        if content and isinstance(content, str):
            content_txt = content
        elif content and isinstance(content, list):
            if not content or len(content) == 0:
                self.logger.error("content len is 0 or is None")
                return None
            text = cast(dict, content[0]).get("text", "")
            content_txt = text
        else:
            self.logger.error("content is None or type unknow.")
            return None
        if content_txt == "":
            self.logger.error(f"text is None or empty string.")
            return None
        return content_txt

    async def execute_signal_for_symbol_async(
        self, symbol: str, retries: int = 0
    ) -> Dict[str, Any]:
        """Execute trading signal for a specific symbol asynchronously"""
        result = {
            "symbol": symbol,
            "status": "FAILED",
            "error": None,
            "start_time": datetime.now(),
            "end_time": None,
            "thread_id": None,
        }

        try:
            # Get thread with automatic rebuild if needed
            thread_id = self.create_or_get_thread(symbol)
            result["thread_id"] = thread_id

            input_data = {
                "messages": [
                    {
                        "type": "human",
                        "content": f"""任务：分析对话历史中{symbol.lower()}的交易信号并执行相应操作

执行步骤：
1. 找到对话历史中最近一次关于{symbol.lower()}的交易信号
2. 提取交易号、交易类型、价格、时间等关键信息

条件处理：
- 如找到历史交易信号：使用交易信号进行回测分析
- 如未找到交易信号：生成新的{symbol.lower()}交易信号（包含交易方向、价格区间、止损位、目标位），无需回测
""",
                    }
                ],
                "wallet_is_connected": True,
                "time_zone": self.config.timezone,
                "chain_id": -1,
                "wallet_address": "",
                "llm": "anthropic_claude_4_sonnet",
                "user_id": self.config.user_id,
            }

            self.logger.info(
                f"Starting signal generation for {symbol} using thread {thread_id}"
            )

            # Execute the signal generation asynchronously
            chunks = self.async_client.runs.stream(
                thread_id=thread_id,
                assistant_id=self.config.graph_name,
                input=input_data,
                stream_mode="events",
                config={"recursion_limit": 50},
            )

            # Process the response
            result_count = 0
            run_id_trading_signal = ""
            run_id_signal_backtest = ""
            async for _chunk in chunks:
                chunk = _chunk.data
                if chunk.get("error", None):
                    self.logger.error(f"Error: {chunk}")
                if chunk.get("event", "") != "":
                    self.logger.debug(f"{symbol} - Event: {chunk.get('event','')}")
                if chunk.get("data", None):
                    result_count += 1
                    # Log important events, but avoid flooding logs
                    # if chunk.get("event", "") in ["on_chat_model_end", "on_tool_end"]:
                    #     self.logger.info(
                    #         f"{symbol} - {chunk.get('event','')}: {str(chunk.get('data',{}))[:200]}..."
                    #     )
                    event = chunk.get("event", "")
                    data = chunk.get("data", {})
                    if event and event == "on_chain_start":
                        if chunk.get("name", "") == "graph_trading_signal":
                            if run_id_trading_signal == "":
                                run_id_trading_signal = chunk.get("run_id", "")
                                self.logger.info(
                                    f"Catch graph_trading_signal run_id:{run_id_trading_signal}"
                                )
                        if chunk.get("name", "") == "graph_signal_backtest":
                            if run_id_signal_backtest == "":
                                run_id_signal_backtest = chunk.get("run_id", "")
                                self.logger.info(
                                    f"Catch graph_signal_backtest run_id:{run_id_signal_backtest}"
                                )
                    if event == "on_chain_end":
                        if (
                            chunk.get("name", "") == "graph_trading_signal"
                            and chunk.get("run_id", "run_id") == run_id_trading_signal
                        ):
                            self.logger.info("Get a genreted trading signal.")
                            content = self._parse_content(data)
                            self.logger.info(f"{symbol}'s new signal: \n{content}")
                            # Send trading signal to Telegram
                            if self.telegram_service:
                                try:
                                    await self.telegram_service.send_to_group(
                                        message=f"*{symbol} Trading Signal:*\n\n{content}",
                                        message_type="signal",
                                        group_ids=self.group_id,
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"Failed to send Telegram notification for {symbol} signal: {e}"
                                    )
                                    self.logger.debug(f"{traceback.format_exc()}")
                            else:
                                self.logger.warning(
                                    "Telegram service not available, skipping notification"
                                )
                        if (
                            chunk.get("name", "") == "graph_signal_backtest"
                            and chunk.get("run_id", "run_id") == run_id_signal_backtest
                        ):
                            self.logger.info("Get a backtest result.")
                            content = self._parse_content(data)
                            self.logger.info(f"{symbol}'s backtest result: \n{content}")
                            if (
                                self.telegram_service
                                and self.enable_backtest_processing
                            ):
                                try:
                                    await self.telegram_service.send_to_group(
                                        message=f"*{symbol} Backtest Result:*\n\n{content}",
                                        message_type="backtest",
                                        group_ids=self.group_id,
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"Failed to send Telegram notification for {symbol} backtest: {e}"
                                    )
                                    self.logger.debug(f"{traceback.format_exc()}")
                            else:
                                self.logger.warning(
                                    "Telegram service not available, skipping backtest notification"
                                )
            result["status"] = "SUCCESS"
            result["end_time"] = datetime.now()
            self.logger.info(
                f"Successfully processed {result_count} events for {symbol}"
            )

        except Exception as e:
            result["error"] = str(e)
            result["end_time"] = datetime.now()
            self.logger.error(
                f"Error executing signal for {symbol} (attempt {retries + 1}): {e}"
            )
            self.logger.debug(f"{traceback.format_exc()}")

            # If thread-related error, try to rebuild thread
            if "thread" in str(e).lower() and retries == 0:
                self.logger.info(
                    f"Thread error detected for {symbol}, forcing thread rebuild..."
                )
                self.delete_thread(symbol)

            if retries < self.config.max_retries:
                self.logger.info(
                    f"Retrying {symbol} in {self.config.retry_delay} seconds..."
                )
                await asyncio.sleep(self.config.retry_delay)
                return await self.execute_signal_for_symbol_async(symbol, retries + 1)
            else:
                self.logger.error(f"Max retries exceeded for {symbol}")
                result["status"] = "FAILED"

        return result

    async def execute_symbols_concurrently(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Execute trading signals for multiple symbols concurrently"""
        self.logger.info(
            f"Starting concurrent execution for {len(symbols)} symbols: {symbols}"
        )

        # Create semaphore to limit concurrent executions
        semaphore = asyncio.Semaphore(self.config.max_concurrent_symbols)

        async def execute_with_semaphore(symbol: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.execute_signal_for_symbol_async(symbol)

        # Execute all symbols concurrently
        tasks = [execute_with_semaphore(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle exceptions
        processed_results = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                self.logger.error(f"Unexpected exception for {symbol}: {result}")
                processed_results[symbol] = {
                    "symbol": symbol,
                    "status": "ERROR",
                    "error": str(result),
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "thread_id": None,
                }
            else:
                processed_results[symbol] = result

        return processed_results

    def execute_trading_signals_wrapper(self):
        """Wrapper function to handle async execution in sync scheduler"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the async function
                loop.run_until_complete(self.execute_trading_signals())
            finally:
                loop.close()

        except Exception as e:
            self.logger.error(f"Error in async wrapper: {e}")
            raise

    async def execute_trading_signals(self):
        """Main execution function called by scheduler (async version)"""
        execution_start = datetime.now()
        self.logger.info(
            f"=== Trading Signal Execution Started at {execution_start} ==="
        )

        # Log current thread status before execution
        thread_status = self.get_thread_status_summary()
        self.logger.info(
            f"Current thread status: {thread_status['total_threads']} active threads"
        )

        for symbol, details in thread_status["threads_detail"].items():
            status = "EXPIRED" if details["is_expired"] else "VALID"
            self.logger.info(f"  {symbol}: {status} (age: {details['age_hours']}h)")

        symbols = ["ETH", "BTC"]

        # Execute all symbols concurrently
        results = await self.execute_symbols_concurrently(symbols)

        execution_end = datetime.now()
        duration = (execution_end - execution_start).total_seconds()

        # Log execution summary
        self.logger.info(f"=== Execution Summary ===")
        self.logger.info(f"Total Duration: {duration:.2f} seconds")

        success_count = 0
        failed_count = 0
        error_count = 0

        for symbol, result in results.items():
            status = result["status"]
            if result["start_time"] and result["end_time"]:
                symbol_duration = (
                    result["end_time"] - result["start_time"]
                ).total_seconds()
                self.logger.info(
                    f"{symbol}: {status} (duration: {symbol_duration:.2f}s, thread: {result.get('thread_id', 'N/A')})"
                )
            else:
                self.logger.info(
                    f"{symbol}: {status} (thread: {result.get('thread_id', 'N/A')})"
                )

            if result.get("error"):
                self.logger.error(f"  Error details for {symbol}: {result['error']}")

            # Count results
            if status == "SUCCESS":
                success_count += 1
            elif status == "FAILED":
                failed_count += 1
            else:  # ERROR
                error_count += 1

        # Log statistics
        total_symbols = len(symbols)
        self.logger.info(
            f"Results: {success_count}/{total_symbols} successful, {failed_count} failed, {error_count} errors"
        )

        # Log final thread status
        final_thread_status = self.get_thread_status_summary()
        self.logger.info(f"Final thread count: {final_thread_status['total_threads']}")
        self.logger.info(f"=== Execution Completed at {execution_end} ===")

    def start(self):
        """Start the scheduler"""
        try:
            self.setup_scheduler()
            self.logger.info("Trading Signal Scheduler starting...")
            self.logger.info(
                f"Thread rebuild interval: {self.config.thread_rebuild_hours} hours"
            )
            self.logger.info(
                f"Max concurrent symbols: {self.config.max_concurrent_symbols}"
            )
            self.logger.info("Press Ctrl+C to stop the scheduler")

            # Execute once immediately on startup
            self.logger.info("Executing initial trading signals...")
            self.execute_trading_signals_wrapper()

            # Start the scheduler
            self.scheduler.start()

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal, shutting down...")
            self.stop()
        except Exception as e:
            self.logger.error(f"Scheduler failed to start: {e}")
            raise

    def stop(self):
        """Stop the scheduler gracefully"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            self.logger.info("Scheduler stopped successfully")

        # Cleanup all threads before shutting down
        self.cleanup_all_threads()

        # Close client connections if needed
        if hasattr(self.sync_client, "close"):
            self.sync_client.close()
        if hasattr(self.async_client, "close"):
            self.async_client.close()

        self.logger.info("All resources cleaned up")


def load_config() -> TradingConfig:
    """Load configuration from environment variables"""
    required_vars = {
        "LANGGRAPH_SERVER_URL": "langgraph_server_url",
        "TRADING_SIGNAL_THREAD_USER_ID": "user_id",
        "GRAPH_NAME": "graph_name",
    }

    config_dict = {}
    missing_vars = []

    for env_var, config_key in required_vars.items():
        value = os.getenv(env_var)
        if not value:
            missing_vars.append(env_var)
        else:
            config_dict[config_key] = value

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    # Optional configuration with defaults
    config_dict["timezone"] = os.getenv("TIMEZONE", "UTC")
    config_dict["execution_interval"] = int(
        os.getenv("EXECUTION_INTERVAL_MINUTES", "15")
    )
    config_dict["thread_rebuild_hours"] = int(os.getenv("THREAD_REBUILD_HOURS", "24"))
    config_dict["max_concurrent_symbols"] = int(
        os.getenv("MAX_CONCURRENT_SYMBOLS", "5")
    )  # NEW
    config_dict["max_retries"] = int(os.getenv("MAX_RETRIES", "3"))
    config_dict["retry_delay"] = int(os.getenv("RETRY_DELAY_SECONDS", "30"))
    config_dict["log_level"] = getattr(
        logging, os.getenv("LOG_LEVEL").upper(), DEFAULT_LOG_LEVEL
    )
    config_dict["group_id"] = os.getenv("TELEGRAM_GROUP_CHAT_ID")
    config_dict["enable_backtest_processing"] = (
        os.getenv("ENABLE_BACKTEST_PROCESSING") == "True"
    )
    return TradingConfig(**config_dict)


def main():
    """Main function to start the trading signal scheduler"""
    try:
        # Load configuration
        config = load_config()
        print(f"Configuration loaded successfully:")
        print(f"- Server URL: {config.langgraph_server_url}")
        print(f"- Graph Name: {config.graph_name}")
        print(f"- Execution Interval: {config.execution_interval} minutes")
        print(f"- Thread Rebuild Interval: {config.thread_rebuild_hours} hours")
        print(f"- Max Concurrent Symbols: {config.max_concurrent_symbols}")
        print(f"- Timezone: {config.timezone}")

        # Create and start scheduler
        scheduler = TradingSignalScheduler(config)
        scheduler.start()

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Application failed to start: {e}")
        logging.error(f"Application failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
