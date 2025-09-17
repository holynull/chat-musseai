# telegram_service.py
import asyncio
from datetime import datetime
import logging
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError
import json
import os

class TelegramNotificationService:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users/telegram_users.json"):
        self.bot = Bot(token=bot_token)
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        
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
    
    async def send_to_all_users(self, message: str, message_type: str = "signal") -> dict:
        """Send message to all subscribed users"""
        chat_ids = self.load_chat_ids()
        if not chat_ids:
            self.logger.warning("No subscribed users found")
            return {"success": 0, "failed": 0, "errors": []}
        
        success_count = 0
        failed_count = 0
        errors = []
        
        # Format message based on type
        formatted_message = self.format_message(message, message_type)
        
        # Send to all users with rate limiting
        for chat_id in chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                success_count += 1
                # Rate limiting to avoid Telegram API limits
                await asyncio.sleep(0.1)  # 100ms delay between messages
                
            except TelegramError as e:
                failed_count += 1
                error_msg = f"Failed to send to {chat_id}: {e}"
                errors.append(error_msg)
                self.logger.error(error_msg)
                
                # Remove invalid chat_ids (user blocked bot, etc.)
                if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                    await self.remove_chat_id(chat_id)
            
            except Exception as e:
                failed_count += 1
                error_msg = f"Unexpected error for {chat_id}: {e}"
                errors.append(error_msg)
                self.logger.error(error_msg)
        
        result = {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
            "total_users": len(chat_ids)
        }
        
        self.logger.info(f"Telegram broadcast completed: {result}")
        return result
    
    def format_message(self, text: str, message_type: str) -> str:
        """Format message with appropriate template"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        if message_type == "signal":
            header = "🔔 *New Trading Signal*"
        elif message_type == "backtest":
            header = "📊 *Backtest Result*"
        else:
            header = "📈 *Trading Update*"
        
        
        # Format the message with proper structure
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
