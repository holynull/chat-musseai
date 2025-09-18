import asyncio
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError
import json
import os

class TelegramNotificationService:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot = Bot(token=bot_token)
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        
        # Configure concurrent sending limits
        self.max_concurrent_sends = int(os.getenv("TELEGRAM_MAX_CONCURRENT_SENDS", "10"))
        self.send_delay = float(os.getenv("TELEGRAM_SEND_DELAY", "0.05"))  # 50ms delay
        
        # Load group chat IDs from environment variables
        self.group_chat_ids = self._load_group_chat_ids()
        # Keep backward compatibility with single group_chat_id
        self.group_chat_id = self.group_chat_ids[0] if self.group_chat_ids else None
        
        if self.group_chat_ids:
            self.logger.info(f"Group chat IDs configured: {self.group_chat_ids}")
        else:
            self.logger.warning("No group chat IDs configured, group messaging disabled")
    
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

    async def _send_single_message(self, chat_id: str, formatted_message: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Send message to a single chat with semaphore control"""
        async with semaphore:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                # Small delay to respect rate limits
                await asyncio.sleep(self.send_delay)
                return {"chat_id": chat_id, "success": True, "error": None}
            except TelegramError as e:
                error_msg = f"Telegram error: {e}"
                return {"chat_id": chat_id, "success": False, "error": error_msg}
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                return {"chat_id": chat_id, "success": False, "error": error_msg}

    async def send_to_multiple_chats(self, chat_ids: List[str], message: str, message_type: str = "signal") -> Dict[str, Any]:
        """
        Send message to multiple chats concurrently
        
        Args:
            chat_ids: List of chat IDs to send to
            message: The message content to send
            message_type: Type of message (signal, backtest, etc.)
        
        Returns:
            dict: Results with success/failure details for each chat
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
                "errors": []
            }
        
        # Format message based on type
        formatted_message = self.format_message(message, message_type)
        
        self.logger.info(f"Sending {message_type} message to {len(chat_ids)} chats concurrently")
        
        # Create semaphore to limit concurrent sends
        semaphore = asyncio.Semaphore(self.max_concurrent_sends)
        
        # Create tasks for all chats
        tasks = [
            self._send_single_message(chat_id, formatted_message, semaphore)
            for chat_id in chat_ids
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        sent_chats = []
        failed_chats = []
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                # Handle unexpected exceptions from gather
                error_msg = f"Task exception: {result}"
                errors.append(error_msg)
                failed_chats.append("unknown")
                self.logger.error(error_msg)
            elif result["success"]:
                sent_chats.append(result["chat_id"])
                self.logger.debug(f"Successfully sent to {result['chat_id']}")
            else:
                failed_chats.append(result["chat_id"])
                error_msg = f"Chat {result['chat_id']}: {result['error']}"
                errors.append(error_msg)
                self.logger.error(f"Failed to send to {result['chat_id']}: {result['error']}")
        
        # Prepare response
        success = len(sent_chats) > 0
        response = {
            "success": success,
            "message_type": message_type,
            "total_chats": len(chat_ids),
            "sent_chats": sent_chats,
            "failed_chats": failed_chats,
            "success_count": len(sent_chats),
            "failed_count": len(failed_chats),
            "errors": errors
        }
        
        # Log summary
        if success:
            if failed_chats:
                self.logger.warning(f"Partially successful: sent to {len(sent_chats)}/{len(chat_ids)} chats")
            else:
                self.logger.info(f"Successfully sent {message_type} message to all {len(sent_chats)} chats")
        else:
            self.logger.error(f"Failed to send {message_type} message to any chats")
        
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
                    "errors": []
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
                "errors": []
            }
        
        # Use the concurrent sending method
        return await self.send_to_multiple_chats(target_groups, message, message_type)

    async def send_to_all_users(self, message: str, message_type: str = "signal") -> Dict[str, Any]:
        """Send message to all subscribed users concurrently"""
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
                "errors": []
            }
        
        # Use the concurrent sending method
        result = await self.send_to_multiple_chats(chat_ids, message, message_type)
        
        # Handle invalid chat IDs removal for user chats
        if result["failed_chats"]:
            await self._cleanup_invalid_chat_ids(result["failed_chats"], result["errors"])
        
        return result

    async def _cleanup_invalid_chat_ids(self, failed_chat_ids: List[str], errors: List[str]):
        """Remove invalid chat IDs from storage"""
        try:
            # Check which failures are due to blocked/not found errors
            chat_ids_to_remove = []
            for i, chat_id in enumerate(failed_chat_ids):
                if i < len(errors):
                    error = errors[i].lower()
                    if "chat not found" in error or "blocked" in error or "user not found" in error:
                        chat_ids_to_remove.append(chat_id)
            
            if chat_ids_to_remove:
                current_chat_ids = self.load_chat_ids()
                updated_chat_ids = [cid for cid in current_chat_ids if cid not in chat_ids_to_remove]
                
                with open(self.chat_storage_file, 'w') as f:
                    json.dump({"chat_ids": updated_chat_ids}, f)
                
                self.logger.info(f"Removed {len(chat_ids_to_remove)} invalid chat IDs: {chat_ids_to_remove}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup invalid chat IDs: {e}")

    def format_message(self, text: str, message_type: str) -> str:
        """Format message with appropriate template"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        if message_type == "signal":
            header = "🔔 *New Trading Signal*"
        elif message_type == "backtest":
            header = "📊 *Backtest Result*"
        else:
            header = "📈 *Trading Update*"
        
        formatted_message = f"""
{header}
⏰ *Time:* {timestamp}

{text}

---
_Automated Trading Signal System_
        """.strip()
        
        return formatted_message

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