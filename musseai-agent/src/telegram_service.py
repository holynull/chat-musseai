import asyncio
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any, Tuple
from telegram import Bot
from telegram.error import TelegramError, TimedOut, NetworkError, BadRequest, Forbidden 
import json
import os
import random
import time

class TelegramNotificationService:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot = Bot(token=bot_token)
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        
        # Configure concurrent sending limits
        self.max_concurrent_sends = int(os.getenv("TELEGRAM_MAX_CONCURRENT_SENDS", "10"))
        self.send_delay = float(os.getenv("TELEGRAM_SEND_DELAY", "0.05"))  # 50ms delay
        
        # ✨ NEW: Retry configuration
        self.max_retries = int(os.getenv("TELEGRAM_MAX_RETRIES", "3"))
        self.initial_retry_delay = float(os.getenv("TELEGRAM_INITIAL_RETRY_DELAY", "1.0"))  # 1 second
        self.retry_backoff_factor = float(os.getenv("TELEGRAM_RETRY_BACKOFF_FACTOR", "2.0"))  # Exponential backoff
        self.max_retry_delay = float(os.getenv("TELEGRAM_MAX_RETRY_DELAY", "30.0"))  # Max 30 seconds
        self.retry_jitter = bool(os.getenv("TELEGRAM_RETRY_JITTER", "True").lower() == "true")  # Add randomness
        
        # ✨ NEW: Define retryable and permanent error types
        self.retryable_errors = {
            'TimedOut', 'NetworkError', 'BadGateway', 'ServiceUnavailable', 
            'TooManyRequests', 'InternalServerError', 'ConnectionError',
            'ReadTimeoutError', 'ConnectTimeoutError'
        }
        
        self.permanent_errors = {
            'Unauthorized', 'ChatNotFound', 'UserNotFound', 'BotBlocked',
            'BotKicked', 'UserDeactivated', 'ChatDeactivated', 'Forbidden'
        }
        
        # Load group chat IDs from environment variables
        self.group_chat_ids = self._load_group_chat_ids()
        # Keep backward compatibility with single group_chat_id
        self.group_chat_id = self.group_chat_ids[0] if self.group_chat_ids else None
        
        if self.group_chat_ids:
            self.logger.info(f"Group chat IDs configured: {self.group_chat_ids}")
        else:
            self.logger.warning("No group chat IDs configured, group messaging disabled")
            
        # ✨ NEW: Log retry configuration
        self.logger.info(f"Retry configuration: max_retries={self.max_retries}, "
                        f"initial_delay={self.initial_retry_delay}s, "
                        f"backoff_factor={self.retry_backoff_factor}, "
                        f"max_delay={self.max_retry_delay}s")
    
    def _load_group_chat_ids(self) -> List[str]:
        """Load group chat IDs from environment variables"""
        # First try the new multi-group environment variable
        group_ids_str = os.getenv("TELEGRAM_GROUP_CHAT_IDS")
        if group_ids_str:
            try:
                group_ids = [gid.strip() for gid in group_ids_str.split(',') if gid.strip()]
                return group_ids
            except Exception as e:
                self.logger.error(f"Failed to parse TELEGRAM_GROUP_CHAT_IDS: {e}")
        
        # Fallback to single group ID for backward compatibility
        single_group_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")
        if single_group_id:
            return [single_group_id.strip()]
            
        return []
    
    # ✨ NEW: Smart error classification
    def _classify_error(self, error: Exception) -> Tuple[bool, str]:
        """
        Classify error as retryable or permanent
        
        Returns:
            Tuple[bool, str]: (is_retryable, error_category)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Check for specific permanent errors
        permanent_keywords = [
            'chat not found', 'user not found', 'bot was blocked', 'bot was kicked',
            'user is deactivated', 'chat is deactivated', 'forbidden', 'unauthorized',
            'bad request'
        ]
        
        for keyword in permanent_keywords:
            if keyword in error_str:
                return False, f"permanent_{keyword.replace(' ', '_')}"
        
        # Check error type for retryable errors
        if error_type in self.retryable_errors:
            return True, f"retryable_{error_type.lower()}"
        
        # Check for rate limiting (special case - always retryable)
        if 'too many requests' in error_str or 'rate limit' in error_str:
            return True, "retryable_rate_limit"
        
        # Check for network-related errors in message
        retryable_keywords = [
            'timeout', 'network', 'connection', 'server error', 'service unavailable',
            'bad gateway', 'gateway timeout', 'internal server error'
        ]
        
        for keyword in retryable_keywords:
            if keyword in error_str:
                return True, f"retryable_{keyword.replace(' ', '_')}"
        
        # Default to retryable for unknown errors (conservative approach)
        return True, "retryable_unknown"
    
    # ✨ NEW: Calculate retry delay with exponential backoff and jitter
    def _calculate_retry_delay(self, attempt: int, error_category: str = "") -> float:
        """Calculate delay before retry with exponential backoff and optional jitter"""
        
        # Special handling for rate limit errors
        if "rate_limit" in error_category:
            # For rate limits, use longer delays
            base_delay = self.initial_retry_delay * 3
        else:
            base_delay = self.initial_retry_delay
        
        # Exponential backoff
        delay = base_delay * (self.retry_backoff_factor ** attempt)
        
        # Cap the delay
        delay = min(delay, self.max_retry_delay)
        
        # Add jitter to prevent thundering herd
        if self.retry_jitter:
            jitter = random.uniform(0.8, 1.2)  # ±20% jitter
            delay *= jitter
        
        return delay
    
    # ✨ ENHANCED: Single message sending with retry logic
    async def _send_single_message_with_retry(self, chat_id: str, formatted_message: str, 
                                            semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Send message to a single chat with intelligent retry mechanism"""
        async with semaphore:
            last_error = None
            error_category = "unknown"
            
            for attempt in range(self.max_retries + 1):  # +1 for initial attempt
                try:
                    # Log retry attempts
                    if attempt > 0:
                        self.logger.info(f"Retry attempt {attempt}/{self.max_retries} for chat {chat_id}")
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=formatted_message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    
                    # Success - add delay and return
                    await asyncio.sleep(self.send_delay)
                    
                    # Log successful retry
                    if attempt > 0:
                        self.logger.info(f"Successfully sent to {chat_id} after {attempt} retries")
                    
                    return {
                        "chat_id": chat_id, 
                        "success": True, 
                        "error": None,
                        "attempts": attempt + 1,
                        "retry_category": error_category if attempt > 0 else None
                    }
                    
                except TelegramError as e:
                    last_error = e
                    is_retryable, error_category = self._classify_error(e)
                    
                    self.logger.warning(f"Attempt {attempt + 1} failed for chat {chat_id}: {e} "
                                      f"(retryable: {is_retryable}, category: {error_category})")
                    
                    # If it's a permanent error, don't retry
                    if not is_retryable:
                        self.logger.error(f"Permanent error for chat {chat_id}, not retrying: {e}")
                        return {
                            "chat_id": chat_id,
                            "success": False,
                            "error": f"Permanent Telegram error: {e}",
                            "attempts": attempt + 1,
                            "retry_category": error_category,
                            "is_permanent": True
                        }
                    
                    # If we've exhausted retries, fail
                    if attempt >= self.max_retries:
                        break
                    
                    # Calculate and apply retry delay
                    retry_delay = self._calculate_retry_delay(attempt, error_category)
                    self.logger.debug(f"Waiting {retry_delay:.2f}s before retry {attempt + 1} for chat {chat_id}")
                    await asyncio.sleep(retry_delay)
                    
                except Exception as e:
                    last_error = e
                    is_retryable, error_category = self._classify_error(e)
                    
                    self.logger.warning(f"Unexpected error attempt {attempt + 1} for chat {chat_id}: {e} "
                                      f"(retryable: {is_retryable}, category: {error_category})")
                    
                    # For unexpected errors, be more conservative about retrying
                    if not is_retryable or attempt >= self.max_retries:
                        break
                    
                    retry_delay = self._calculate_retry_delay(attempt, error_category)
                    await asyncio.sleep(retry_delay)
            
            # All retries exhausted
            error_msg = f"Failed after {self.max_retries + 1} attempts: {last_error}"
            self.logger.error(f"All retries exhausted for chat {chat_id}: {error_msg}")
            
            return {
                "chat_id": chat_id,
                "success": False,
                "error": error_msg,
                "attempts": self.max_retries + 1,
                "retry_category": error_category,
                "is_permanent": False
            }

    def load_chat_ids(self) -> List[str]:
        """Load all subscribed chat IDs from storage"""
        try:
            if os.path.exists(self.chat_storage_file):
                with open(self.chat_storage_file, 'r') as f:
                    data = json.load(f)
                    return data.get('chat_ids', [])
            return []
        except Exception as e:
            self.logger.error(f"Failed to load chat IDs: {e}")
            return []

    # ✨ ENHANCED: Update original method to use retry logic
    async def _send_single_message(self, chat_id: str, formatted_message: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Send message to a single chat with semaphore control (legacy method for compatibility)"""
        return await self._send_single_message_with_retry(chat_id, formatted_message, semaphore)

    # ✨ ENHANCED: Update to include retry statistics
    async def send_to_multiple_chats(self, chat_ids: List[str], message: str, message_type: str = "signal") -> Dict[str, Any]:
        """
        Send message to multiple chats concurrently with retry mechanism
        
        Args:
            chat_ids: List of chat IDs to send to
            message: The message content to send
            message_type: Type of message (signal, backtest, etc.)
        
        Returns:
            dict: Results with success/failure details for each chat including retry statistics
        """
        if not chat_ids:
            return {
                "success": False,
                "error": "No chat IDs provided",
                "total_chats": 0,
                "sent_chats": [],
                "failed_chats": [],
                "success_count": 0,
                "failed_count": 0,
                "errors": [],
                "retry_stats": {}
            }
        
        # Format message based on type
        formatted_message = self.format_message(message, message_type)
        
        self.logger.info(f"Sending {message_type} message to {len(chat_ids)} chats with retry mechanism")
        start_time = time.time()
        
        # Create semaphore to limit concurrent sends
        semaphore = asyncio.Semaphore(self.max_concurrent_sends)
        
        # Create tasks for all chats
        tasks = [
            self._send_single_message_with_retry(chat_id, formatted_message, semaphore)
            for chat_id in chat_ids
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # ✨ NEW: Enhanced result processing with retry statistics
        sent_chats = []
        failed_chats = []
        errors = []
        permanent_failures = []
        retry_stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_after_retries": 0,
            "permanent_errors": 0,
            "retry_categories": {}
        }
        
        for result in results:
            if isinstance(result, Exception):
                # Handle unexpected exceptions from gather
                error_msg = f"Task exception: {result}"
                errors.append(error_msg)
                failed_chats.append("unknown")
                self.logger.error(error_msg)
            elif result["success"]:
                sent_chats.append(result["chat_id"])
                
                # Track retry statistics
                attempts = result.get("attempts", 1)
                retry_stats["total_attempts"] += attempts
                
                if attempts > 1:
                    retry_stats["successful_retries"] += 1
                    category = result.get("retry_category", "unknown")
                    retry_stats["retry_categories"][category] = retry_stats["retry_categories"].get(category, 0) + 1
                
                self.logger.debug(f"Successfully sent to {result['chat_id']} (attempts: {attempts})")
            else:
                failed_chats.append(result["chat_id"])
                error_msg = f"Chat {result['chat_id']}: {result['error']}"
                errors.append(error_msg)
                
                # Track retry statistics
                attempts = result.get("attempts", 1)
                retry_stats["total_attempts"] += attempts
                
                if result.get("is_permanent", False):
                    permanent_failures.append(result["chat_id"])
                    retry_stats["permanent_errors"] += 1
                else:
                    retry_stats["failed_after_retries"] += 1
                
                category = result.get("retry_category", "unknown")
                retry_stats["retry_categories"][category] = retry_stats["retry_categories"].get(category, 0) + 1
                
                self.logger.error(f"Failed to send to {result['chat_id']}: {result['error']} "
                                f"(attempts: {attempts})")
        
        # Calculate performance metrics
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Prepare enhanced response
        success = len(sent_chats) > 0
        response = {
            "success": success,
            "message_type": message_type,
            "total_chats": len(chat_ids),
            "sent_chats": sent_chats,
            "failed_chats": failed_chats,
            "permanent_failures": permanent_failures,
            "success_count": len(sent_chats),
            "failed_count": len(failed_chats),
            "errors": errors,
            "retry_stats": retry_stats,
            "performance": {
                "total_duration_seconds": round(total_duration, 2),
                "average_attempts_per_chat": round(retry_stats["total_attempts"] / len(chat_ids), 2) if chat_ids else 0,
                "success_rate": round((len(sent_chats) / len(chat_ids)) * 100, 2) if chat_ids else 0
            }
        }
        
        # ✨ Enhanced logging with retry statistics
        if success:
            if failed_chats:
                success_rate = (len(sent_chats) / len(chat_ids)) * 100
                self.logger.warning(f"Partially successful: {len(sent_chats)}/{len(chat_ids)} chats "
                                  f"({success_rate:.1f}% success rate) in {total_duration:.2f}s")
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(f"Retry mechanism recovered {retry_stats['successful_retries']} failures")
            else:
                self.logger.info(f"Successfully sent {message_type} message to all {len(sent_chats)} chats "
                               f"in {total_duration:.2f}s")
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(f"Retry mechanism recovered {retry_stats['successful_retries']} temporary failures")
        else:
            self.logger.error(f"Failed to send {message_type} message to any chats "
                            f"({retry_stats['permanent_errors']} permanent, "
                            f"{retry_stats['failed_after_retries']} exhausted retries)")
        
        # Log retry category breakdown
        if retry_stats["retry_categories"]:
            category_summary = ", ".join([f"{cat}: {count}" for cat, count in retry_stats["retry_categories"].items()])
            self.logger.info(f"Retry categories: {category_summary}")
        
        return response

    async def send_to_group(self, message: str, message_type: str = "signal", group_ids: Optional[str] = None) -> Dict[str, Any]:
        """
        Send message to specified group(s) or all configured groups concurrently
        
        Args:
            message: The message content to send
            message_type: Type of message (signal, backtest, etc.)
            group_ids: Comma-separated group IDs. If None, uses configured group_chat_ids
        
        Returns:
            dict: Results with success/failure details for each group
        """
        # Determine target groups
        if group_ids is not None:
            # Parse comma-separated group IDs from parameter
            target_groups = [gid.strip() for gid in group_ids.split(',') if gid.strip()]
            if not target_groups:
                return {
                    "success": False,
                    "error": "Invalid group_ids parameter provided",
                    "total_chats": 0,
                    "sent_chats": [],
                    "failed_chats": [],
                    "success_count": 0,
                    "failed_count": 0,
                    "errors": [],
                    "retry_stats": {}
                }
        else:
            # Use configured group chat IDs
            target_groups = self.group_chat_ids if self.group_chat_ids else []
            
            # Fallback to single group_chat_id for backward compatibility
            if not target_groups and self.group_chat_id:
                target_groups = [self.group_chat_id]
        
        if not target_groups:
            return {
                "success": False,
                "error": "No group chat IDs configured or provided",
                "total_chats": 0,
                "sent_chats": [],
                "failed_chats": [],
                "success_count": 0,
                "failed_count": 0,
                "errors": [],
                "retry_stats": {}
            }
        
        # Use the concurrent sending method with retry
        return await self.send_to_multiple_chats(target_groups, message, message_type)

    async def send_to_all_users(self, message: str, message_type: str = "signal") -> Dict[str, Any]:
        """Send message to all subscribed users concurrently with retry mechanism"""
        chat_ids = self.load_chat_ids()
        if not chat_ids:
            self.logger.warning("No subscribed users found")
            return {
                "success": False,
                "error": "No subscribed users found",
                "total_chats": 0,
                "sent_chats": [],
                "failed_chats": [],
                "success_count": 0,
                "failed_count": 0,
                "errors": [],
                "retry_stats": {}
            }
        
        # Use the concurrent sending method with retry
        result = await self.send_to_multiple_chats(chat_ids, message, message_type)
        
        # ✨ ENHANCED: Handle invalid chat IDs removal with permanent error detection
        if result["failed_chats"]:
            permanent_failures = result.get("permanent_failures", [])
            if permanent_failures:
                await self._cleanup_invalid_chat_ids(permanent_failures, result["errors"])
        
        return result

    # ✨ ENHANCED: Improved cleanup with better error detection
    async def _cleanup_invalid_chat_ids(self, failed_chat_ids: List[str], errors: List[str]):
        """Remove invalid chat IDs from storage based on permanent errors"""
        try:
            # More comprehensive permanent error detection
            permanent_error_patterns = [
                'chat not found', 'user not found', 'bot was blocked', 'bot was kicked',
                'user is deactivated', 'chat is deactivated', 'forbidden', 'unauthorized',
                'permanent telegram error'
            ]
            
            chat_ids_to_remove = []
            for i, chat_id in enumerate(failed_chat_ids):
                if i < len(errors):
                    error = errors[i].lower()
                    if any(pattern in error for pattern in permanent_error_patterns):
                        chat_ids_to_remove.append(chat_id)
                        self.logger.debug(f"Marking chat {chat_id} for removal due to: {error}")
            
            if chat_ids_to_remove:
                current_chat_ids = self.load_chat_ids()
                updated_chat_ids = [cid for cid in current_chat_ids if cid not in chat_ids_to_remove]
                
                # Backup before modification
                backup_data = {"chat_ids": current_chat_ids, "backup_timestamp": datetime.now().isoformat()}
                backup_file = f"{self.chat_storage_file}.backup"
                with open(backup_file, 'w') as f:
                    json.dump(backup_data, f)
                
                # Update main storage
                with open(self.chat_storage_file, 'w') as f:
                    json.dump({"chat_ids": updated_chat_ids}, f)
                
                self.logger.info(f"Removed {len(chat_ids_to_remove)} invalid chat IDs: {chat_ids_to_remove}")
                self.logger.debug(f"Backup created at {backup_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup invalid chat IDs: {e}")

    def _convert_markdown_titles(self, text: str) -> str:
        """Convert Markdown titles with multi-level indentation support"""
        import re
        
        # Convert ### (h3) to bold format with more indentation
        text = re.sub(r'^###\s+(.+)$', r'      ▫ *\1*', text, flags=re.MULTILINE)
        
        # Convert ## (h2) to bold format with indentation
        text = re.sub(r'^##\s+(.+)$', r'    ▪ *\1*', text, flags=re.MULTILINE)
        
        # Convert # (h1) to bold format
        text = re.sub(r'^#\s+(.+)$', r'🔶 *\1*', text, flags=re.MULTILINE)
        
        return text


    def format_message(self, text: str, message_type: str) -> str:
        """Format message with appropriate template"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Convert Markdown titles to Telegram-compatible format
        formatted_text = self._convert_markdown_titles(text)

        if message_type == "signal":
            header = "🔔 *New Trading Signal*"
        elif message_type == "backtest":
            header = "📊 *Backtest Result*"
        else:
            header = "📈 *Trading Update*"

        formatted_message = f"""
    {header}
    ⏰ *Time:* {timestamp}

    {formatted_text}

    ---
    _Automated Trading Signal System_
        """.strip()

        return formatted_message


    # ✨ NEW: Health check and diagnostics method
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the Telegram service
        
        Returns:
            dict: Health status and configuration details
        """
        try:
            # Test bot token validity
            me = await self.bot.get_me()
            bot_info = {
                "username": me.username,
                "first_name": me.first_name,
                "id": me.id
            }
            
            # Count configured chats
            user_chat_count = len(self.load_chat_ids())
            group_chat_count = len(self.group_chat_ids) if self.group_chat_ids else 0
            
            health_status = {
                "status": "healthy",
                "bot_info": bot_info,
                "configuration": {
                    "max_concurrent_sends": self.max_concurrent_sends,
                    "send_delay": self.send_delay,
                    "max_retries": self.max_retries,
                    "initial_retry_delay": self.initial_retry_delay,
                    "retry_backoff_factor": self.retry_backoff_factor,
                    "max_retry_delay": self.max_retry_delay,
                    "retry_jitter": self.retry_jitter
                },
                "chat_counts": {
                    "subscribed_users": user_chat_count,
                    "configured_groups": group_chat_count,
                    "total_chats": user_chat_count + group_chat_count
                },
                "retry_capabilities": {
                    "retryable_error_types": list(self.retryable_errors),
                    "permanent_error_types": list(self.permanent_errors)
                },
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.info(f"Health check passed - Bot: @{me.username}, "
                           f"Users: {user_chat_count}, Groups: {group_chat_count}")
            return health_status
            
        except Exception as e:
            error_status = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.logger.error(f"Health check failed: {e}")
            return error_status

    # ✨ NEW: Test retry mechanism with a dry run
    async def test_retry_mechanism(self, test_chat_id: str) -> Dict[str, Any]:
        """
        Test the retry mechanism with a specific chat ID
        
        Args:
            test_chat_id: Chat ID to test with
            
        Returns:
            dict: Test results and retry behavior analysis
        """
        test_message = "🧪 **Retry Mechanism Test**\n\nThis is a test message to verify the retry functionality."
        formatted_message = self.format_message(test_message, "test")
        
        self.logger.info(f"Testing retry mechanism with chat ID: {test_chat_id}")
        
        # Create a semaphore for the test
        semaphore = asyncio.Semaphore(1)
        
        # Test the retry mechanism
        start_time = time.time()
        result = await self._send_single_message_with_retry(test_chat_id, formatted_message, semaphore)
        end_time = time.time()
        
        test_results = {
            "test_chat_id": test_chat_id,
            "result": result,
            "duration_seconds": round(end_time - start_time, 2),
            "retry_configuration": {
                "max_retries": self.max_retries,
                "initial_retry_delay": self.initial_retry_delay,
                "backoff_factor": self.retry_backoff_factor,
                "max_retry_delay": self.max_retry_delay,
                "jitter_enabled": self.retry_jitter
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if result["success"]:
            attempts = result.get("attempts", 1)
            if attempts > 1:
                self.logger.info(f"Test successful after {attempts} attempts in {test_results['duration_seconds']}s")
            else:
                self.logger.info(f"Test successful on first attempt in {test_results['duration_seconds']}s")
        else:
            self.logger.warning(f"Test failed after {result.get('attempts', 'unknown')} attempts: {result['error']}")
        
        return test_results

    async def remove_chat_id(self, chat_id: str):
        """Remove invalid chat ID from storage"""
        try:
            chat_ids = self.load_chat_ids()
            if chat_id in chat_ids:
                chat_ids.remove(chat_id)
                with open(self.chat_storage_file, 'w') as f:
                    json.dump({"chat_ids": chat_ids}, f)
                self.logger.info(f"Removed invalid chat_id: {chat_id}")
        except Exception as e:
            self.logger.error(f"Failed to remove chat_id {chat_id}: {e}")

    async def add_chat_id(self, chat_id: str):
        """Add new chat ID to storage"""
        try:
            chat_ids = self.load_chat_ids()
            if chat_id not in chat_ids:
                chat_ids.append(chat_id)
                with open(self.chat_storage_file, 'w') as f:
                    json.dump({"chat_ids": chat_ids}, f)
                self.logger.info(f"Added new chat_id: {chat_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to add chat_id {chat_id}: {e}")
            return False

    # ✨ NEW: Get retry statistics summary
    def get_retry_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current retry configuration"""
        return {
            "retry_settings": {
                "max_retries": self.max_retries,
                "initial_retry_delay_seconds": self.initial_retry_delay,
                "backoff_factor": self.retry_backoff_factor,
                "max_retry_delay_seconds": self.max_retry_delay,
                "jitter_enabled": self.retry_jitter
            },
            "concurrency_settings": {
                "max_concurrent_sends": self.max_concurrent_sends,
                "send_delay_seconds": self.send_delay
            },
            "error_classification": {
                "retryable_errors": sorted(list(self.retryable_errors)),
                "permanent_errors": sorted(list(self.permanent_errors))
            },
            "estimated_scenarios": {
                "single_retry_delay": f"{self.initial_retry_delay}s",
                "max_total_delay": f"{self._calculate_max_total_delay()}s",
                "theoretical_max_attempts": self.max_retries + 1
            }
        }
    
    def _calculate_max_total_delay(self) -> float:
        """Calculate theoretical maximum total delay for all retries"""
        total_delay = 0
        for attempt in range(self.max_retries):
            delay = self.initial_retry_delay * (self.retry_backoff_factor ** attempt)
            delay = min(delay, self.max_retry_delay)
            total_delay += delay
        return round(total_delay, 2)
