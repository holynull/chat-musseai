import asyncio
import logging
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError
import random
from langgraph_sdk import get_client, get_sync_client
import re
from typing import List, Tuple


class EnhancedTelegramBotService:
    """Enhanced Telegram bot service combining subscription management and notification features"""

    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot_token = bot_token
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        self.bot = Bot(token=bot_token)
        self.application = None

        # Anti-spam mechanism
        self.last_interaction = {}
        self.interaction_cooldown = 30  # 30 seconds cooldown

        # Configure concurrent sending limits
        self.max_concurrent_sends = int(
            os.getenv("TELEGRAM_MAX_CONCURRENT_SENDS", "10")
        )
        self.send_delay = float(os.getenv("TELEGRAM_SEND_DELAY", "0.05"))  # 50ms delay

        # Retry configuration
        self.max_retries = int(os.getenv("TELEGRAM_MAX_RETRIES", "3"))
        self.initial_retry_delay = float(
            os.getenv("TELEGRAM_INITIAL_RETRY_DELAY", "1.0")
        )
        self.retry_backoff_factor = float(
            os.getenv("TELEGRAM_RETRY_BACKOFF_FACTOR", "2.0")
        )
        self.max_retry_delay = float(os.getenv("TELEGRAM_MAX_RETRY_DELAY", "30.0"))
        self.retry_jitter = bool(
            os.getenv("TELEGRAM_RETRY_JITTER", "True").lower() == "true"
        )

        # Error classification
        self.retryable_errors = {
            "TimedOut",
            "NetworkError",
            "BadGateway",
            "ServiceUnavailable",
            "TooManyRequests",
            "InternalServerError",
            "ConnectionError",
            "ReadTimeoutError",
            "ConnectTimeoutError",
        }

        self.permanent_errors = {
            "Unauthorized",
            "ChatNotFound",
            "UserNotFound",
            "BotBlocked",
            "BotKicked",
            "UserDeactivated",
            "ChatDeactivated",
            "Forbidden",
        }

        # 新增 LangGraph 配置
        self.langgraph_server_url = os.getenv("LANGGRAPH_SERVER_URL")
        self.chat_graph_name = os.getenv("CHAT_GRAPH_NAME", os.getenv("GRAPH_NAME"))
        self.enable_langgraph_chat = (
            os.getenv("ENABLE_LANGGRAPH_CHAT", "false").lower() == "true"
        )

        # LangGraph 客户端
        self.async_client = None
        self.sync_client = None

        # 用户对话线程管理
        self.user_threads = {}  # {user_id: {thread_id: str, created_at: datetime}}
        self.thread_lock = threading.Lock()

        if self.enable_langgraph_chat and self.langgraph_server_url:
            self.setup_langgraph_client()

        # 添加格式化统计追踪

        self.formatting_stats = {
            "total_formatted": 0,
            "successful_formatting": 0,
            "fallback_used": 0,
            "plain_text_used": 0,
            "messages_split": 0,
            "average_length": 0,
            "last_reset": datetime.now(),
        }

        # 格式化配置
        self.max_message_length = int(os.getenv("TELEGRAM_MAX_MESSAGE_LENGTH", "4000"))
        self.enable_message_splitting = (
            os.getenv("TELEGRAM_ENABLE_SPLITTING", "true").lower() == "true"
        )
        self.formatting_fallback_mode = os.getenv(
            "TELEGRAM_FORMATTING_FALLBACK", "safe_escape"
        )  # safe_escape, plain_text

    async def send_to_channel(
        self,
        message: str,
        channel_ids: str,
        message_type: str = "signal",
    ) -> Dict[str, Any]:
        """Send message to specified channel(s) or all configured channels"""
        if channel_ids is not None:
            target_channels = [
                cid.strip() for cid in channel_ids.split(",") if cid.strip()
            ]
            if not target_channels:
                return {
                    "success": False,
                    "error": "Invalid channel_ids parameter provided",
                    "total_chats": 0,
                    "sent_chats": [],
                    "failed_chats": [],
                    "success_count": 0,
                    "failed_count": 0,
                    "errors": [],
                    "retry_stats": {},
                }
            return await self.send_formatted_message_safely(
                target_channels, message, message_type
            )

    async def send_to_group_and_channel(
        self,
        message: str,
        message_type: str = "signal",
        group_ids: Optional[str] = None,
        channel_ids: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enhanced send_to_group_and_channel with improved formatting
        """
        results = {}

        # Pre-validate message before sending
        validation = self.validate_message_before_send(message, message_type)
        if not validation["is_valid"]:
            self.logger.error(f"Message validation failed: {validation['errors']}")
            return {
                "success": False,
                "error": f"Message validation failed: {', '.join(validation['errors'])}",
                "validation_details": validation,
            }

        # Log validation warnings
        if validation["warnings"]:
            for warning in validation["warnings"]:
                self.logger.warning(f"Message validation warning: {warning}")

        # Send to groups
        if group_ids:
            group_result = await self.send_to_group(message, group_ids, message_type)
            results["group"] = group_result
            self.logger.info(
                f"Group send result: {group_result['success_count']}/{group_result['total_chats']} successful"
            )

        # Send to channels
        if channel_ids:
            channel_result = await self.send_to_channel(
                message, channel_ids, message_type
            )
            results["channel"] = channel_result
            self.logger.info(
                f"Channel send result: {channel_result['success_count']}/{channel_result['total_chats']} successful"
            )

        # Combine results
        total_sent = sum(r.get("success_count", 0) for r in results.values())
        total_failed = sum(r.get("failed_count", 0) for r in results.values())
        total_chats = sum(r.get("total_chats", 0) for r in results.values())

        combined_result = {
            "success": total_sent > 0,
            "message_type": message_type,
            "total_chats": total_chats,
            "success_count": total_sent,
            "failed_count": total_failed,
            "detailed_results": results,
            "validation_info": validation,
            "summary": {
                "groups_sent": results.get("group", {}).get("success_count", 0),
                "channels_sent": results.get("channel", {}).get("success_count", 0),
                "groups_failed": results.get("group", {}).get("failed_count", 0),
                "channels_failed": results.get("channel", {}).get("failed_count", 0),
            },
        }

        return combined_result

    def setup_langgraph_client(self):
        """Initialize LangGraph clients for chat processing"""
        try:
            self.async_client = get_client(url=self.langgraph_server_url)
            self.sync_client = get_sync_client(url=self.langgraph_server_url)
            self.logger.info("LangGraph clients initialized for chat processing")
        except Exception as e:
            self.logger.error(f"Failed to initialize LangGraph clients: {e}")
            self.enable_langgraph_chat = False

    def get_or_create_user_thread(self, user_id: str) -> str:
        """Get existing thread or create new one for user"""
        with self.thread_lock:
            if user_id in self.user_threads:
                thread_info = self.user_threads[user_id]
                # 检查线程是否过期（可选，如24小时重建）
                if self._is_thread_expired(thread_info):
                    self._cleanup_user_thread(user_id)
                else:
                    return thread_info["thread_id"]

            # 创建新线程
            return self._create_user_thread(user_id)

    def _create_user_thread(self, user_id: str) -> str:
        """Create new thread for user"""
        try:
            thread = self.sync_client.threads.create(
                metadata={"user_id": user_id, "chat_user_id": user_id}
            )
            thread_id = thread["thread_id"]

            self.user_threads[user_id] = {
                "thread_id": thread_id,
                "created_at": datetime.now(),
            }

            self.logger.info(f"Created new chat thread for user {user_id}: {thread_id}")
            return thread_id

        except Exception as e:
            self.logger.error(f"Failed to create thread for user {user_id}: {e}")
            raise

    def _is_thread_expired(self, thread_info: dict) -> bool:
        """Check if thread is expired (24 hours)"""
        age = datetime.now() - thread_info["created_at"]
        return age.total_seconds() > 24 * 3600  # 24 hours

    def _cleanup_user_thread(self, user_id: str):
        """Cleanup expired user thread"""
        if user_id in self.user_threads:
            thread_info = self.user_threads[user_id]
            try:
                if hasattr(self.sync_client.threads, "delete"):
                    self.sync_client.threads.delete(thread_id=thread_info["thread_id"])
            except Exception as e:
                self.logger.warning(
                    f"Failed to delete thread {thread_info['thread_id']}: {e}"
                )

            del self.user_threads[user_id]
            self.logger.info(f"Cleaned up expired thread for user {user_id}")

    async def process_message_with_langgraph(
        self, user_message: str, user_id: str
    ) -> str:
        """Process user message through LangGraph and return response"""
        if not self.enable_langgraph_chat or not self.async_client:
            return "Sorry, chat processing is currently unavailable."

        try:
            # Get or create user thread
            thread_id = self.get_or_create_user_thread(user_id)

            # Prepare input data
            input_data = {
                "messages": [{"type": "human", "content": user_message}],
                "wallet_is_connected": False,  # 对话模式不需要钱包连接
                "time_zone": "UTC",
                "chain_id": -1,
                "wallet_address": "",
                "llm": "anthropic_claude_4_sonnet",
                "user_id": user_id,
            }

            self.logger.info(
                f"Processing message for user {user_id} using thread {thread_id}"
            )

            # Execute through LangGraph
            response_content = None
            chunks = self.async_client.runs.stream(
                thread_id=thread_id,
                assistant_id=self.chat_graph_name,
                input=input_data,
                stream_mode="events",
                config={"recursion_limit": 50},
            )
            run_id = ""
            async for chunk in chunks:
                chunk_data = chunk.data
                if chunk_data.get("event") == "on_chain_start" and chunk_data.get(
                    "name", "graph_network"
                ):
                    if run_id == "":
                        run_id = chunk_data.get("run_id", "run_id")
                if (
                    chunk_data.get("event") == "on_chain_end"
                    and chunk_data.get("run_id") == run_id
                ):
                    # 提取最后的AI响应
                    response_content = self._parse_last_ai_content(
                        chunk_data.get("data")
                    )
                    if response_content:
                        break

            if not response_content:
                return "Sorry, I couldn't process your message right now. Please try again."

            return response_content

        except Exception as e:
            self.logger.error(f"Error processing message for user {user_id}: {e}")
            return "Sorry, there was an error processing your message. Please try again later."

    def _parse_last_ai_content(self, data: dict) -> str:
        """Parse the last AI message content from response data (复用 trading_signal.py 的逻辑)"""
        try:
            output = data.get("output", {})
            messages = output.get("messages", [])
            if len(messages) == 0:
                self.logger.error("Messages len is: 0")
                return None

            last_ai_message = None
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("type", "") == "ai":
                    last_ai_message = m
                    break

            if not last_ai_message:
                self.logger.error(f"Can't find last AiMessage in: {messages}")
                return None

            content = last_ai_message.get("content")
            content_txt = ""
            if content and isinstance(content, str):
                content_txt = content
            elif content and isinstance(content, list):
                if not content or len(content) == 0:
                    self.logger.error("content len is 0 or is None")
                    return None
                text = (
                    content[0].get("text", "") if isinstance(content[0], dict) else ""
                )
                content_txt = text
            else:
                self.logger.error("content is None or type unknown.")
                return None

            if content_txt == "":
                self.logger.error("text is None or empty string.")
                return None

            return content_txt

        except Exception as e:
            self.logger.error(f"Error parsing AI content: {e}")
            return None

    def load_chat_ids(self) -> List[str]:
        """Load chat IDs from storage"""
        try:
            if os.path.exists(self.chat_storage_file):
                with open(self.chat_storage_file, "r") as f:
                    data = json.load(f)
                    return data.get("chat_ids", [])
            return []
        except Exception as e:
            self.logger.error(f"Failed to load chat IDs: {e}")
            return []

    def save_chat_ids(self, chat_ids: List[str]) -> bool:
        """Save chat IDs to storage"""
        try:
            with open(self.chat_storage_file, "w") as f:
                json.dump({"chat_ids": chat_ids}, f)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save chat IDs: {e}")
            return False

    def is_rate_limited(self, user_id: str) -> bool:
        """Check if user is rate limited"""
        current_time = time.time()
        last_time = self.last_interaction.get(user_id, 0)

        if current_time - last_time < self.interaction_cooldown:
            return True

        self.last_interaction[user_id] = current_time
        return False

    def create_main_menu(self) -> InlineKeyboardMarkup:
        """Create main menu with inline buttons"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Check Status", callback_data="status"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
            [
                InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe"),
                InlineKeyboardButton("🔄 Refresh Menu", callback_data="refresh"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_unsubscribe_menu(self) -> InlineKeyboardMarkup:
        """Create unsubscribe confirmation menu"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes, Unsubscribe", callback_data="confirm_unsubscribe"
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_subscribe_menu(self) -> InlineKeyboardMarkup:
        """Create subscribe menu for non-subscribed users"""
        keyboard = [
            [
                InlineKeyboardButton("🔔 Subscribe Now", callback_data="subscribe"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_welcome_message(
        self, chat_type: str, user_name: str = None, is_new_member: bool = False
    ) -> str:
        """Generate context-aware welcome message"""
        if is_new_member and chat_type in ["group", "supergroup"]:
            greeting = (
                f"👋 Welcome to the group, {user_name}!"
                if user_name
                else "👋 Welcome to the group!"
            )
            return (
                f"🎉 *{greeting}*\\n\\n"
                "🤖 I'm your Trading Signal Bot! I provide:\\n"
                "📈 Real-time trading signals for ETH and BTC\\n"
                "📊 Automated backtest results\\n"
                "⏰ Updates every 15 minutes\\n\\n"
                "Use the menu below to get started:"
            )
        elif chat_type in ["group", "supergroup"]:
            return (
                "🤖 *Trading Signal Bot Menu*\\n\\n"
                "Hello! I provide automated trading signals and analysis.\\n\\n"
                "📋 *Available Features:*\\n"
                "• Real-time ETH/BTC signals\\n"
                "• Backtest results\\n"
                "• Portfolio analysis\\n"
                "• Regular market updates\\n\\n"
                "Use the menu below to manage your subscription:"
            )
        else:
            return (
                "👋 *Welcome to Trading Signal Bot!*\\n\\n"
                "I'm here to help you with cryptocurrency trading signals and analysis.\\n\\n"
                "🔔 Subscribe to receive:\\n"
                "📈 Trading signals for ETH and BTC\\n"
                "📊 Backtest results and analysis\\n"
                "⏰ Regular market updates\\n\\n"
                "Use the menu below to get started:"
            )

    async def handle_new_chat_members(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle new members joining the chat"""
        try:
            if not update.message or not update.message.new_chat_members:
                return

            for new_member in update.message.new_chat_members:
                if new_member.is_bot and new_member.id != context.bot.id:
                    continue

                if new_member.id == context.bot.id:
                    continue

                user_id = str(new_member.id)
                if self.is_rate_limited(user_id):
                    self.logger.info(f"Rate limited new member welcome for {user_id}")
                    continue

                chat_type = update.effective_chat.type
                user_name = new_member.first_name or new_member.username or "there"

                welcome_text = self.get_welcome_message(
                    chat_type=chat_type, user_name=user_name, is_new_member=True
                )

                chat_ids = self.load_chat_ids()
                is_subscribed = user_id in chat_ids

                reply_markup = (
                    self.create_main_menu()
                    if is_subscribed
                    else self.create_subscribe_menu()
                )

                await update.message.reply_text(
                    welcome_text, parse_mode="Markdown", reply_markup=reply_markup
                )

                self.logger.info(
                    f"Welcomed new member {user_name} ({user_id}) in {chat_type}"
                )

        except Exception as e:
            self.logger.error(f"Error handling new chat members: {e}")

    def _extract_reply_context(self, update: Update) -> Dict[str, Any]:
        """Extract context from reply message"""
        context = {
            "has_reply": False,
            "original_message": None,
            "original_sender": None,
            "original_timestamp": None,
            "is_bot_message": False,
        }

        if update.message.reply_to_message:
            reply_msg = update.message.reply_to_message
            context.update(
                {
                    "has_reply": True,
                    "original_message": reply_msg.text or "[Non-text message]",
                    "original_sender": {
                        "id": reply_msg.from_user.id,
                        "username": reply_msg.from_user.username,
                        "first_name": reply_msg.from_user.first_name,
                        "is_bot": reply_msg.from_user.is_bot,
                    },
                    "original_timestamp": reply_msg.date.isoformat(),
                    "is_bot_message": reply_msg.from_user.is_bot,
                }
            )

        return context

    def _build_contextual_message(
        self, user_message: str, reply_context: Dict[str, Any]
    ) -> str:
        """Build message with reply context for LangGraph processing"""

        if not reply_context["has_reply"]:
            return user_message

        # 构建包含上下文的消息
        if reply_context["is_bot_message"]:
            # 回复bot的消息
            contextual_message = f"""
    [用户回复了我之前的消息]
    我之前说: "{reply_context['original_message']}"
    发送时间: {reply_context['original_timestamp']}
    
    用户现在回复: "{user_message}"
    
    请基于这个对话上下文来回应用户。
    """
        else:
            # 回复其他用户的消息
            original_sender = reply_context["original_sender"]
            sender_name = (
                original_sender["first_name"] or original_sender["username"] or "某用户"
            )

            contextual_message = f"""
    [用户回复了群组中的消息]
    原消息发送者: {sender_name}
    原消息内容: "{reply_context['original_message']}"
    发送时间: {reply_context['original_timestamp']}
    
    用户现在回复: "{user_message}"
    
    请帮助用户回应这个对话，考虑完整的上下文。
    """

        return contextual_message.strip()

    async def handle_mention(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages that mention the bot"""
        try:
            bot_username = context.bot.username
            message_text = update.message.text or ""

            is_mentioned = False

            # Check for direct @username mention
            if f"@{bot_username}" in message_text:
                is_mentioned = True

            # Check if message has entities (mentions)
            if update.message.entities:
                for entity in update.message.entities:
                    if entity.type == "mention":
                        mentioned_text = message_text[
                            entity.offset : entity.offset + entity.length
                        ]
                        if mentioned_text == f"@{bot_username}":
                            is_mentioned = True
                            break

            # Check if it's a reply to bot's message
            if (
                update.message.reply_to_message
                and update.message.reply_to_message.from_user.id == context.bot.id
            ):
                is_mentioned = True

            if not is_mentioned:
                return

            user_id = str(update.effective_user.id)
            if self.is_rate_limited(user_id):
                self.logger.info(f"Rate limited mention response for {user_id}")
                return

            if self.enable_langgraph_chat and not self._is_command_message(
                message_text
            ):
                # 🆕 提取回复上下文
                reply_context = self._extract_reply_context(update)

                # 清理用户消息
                clean_message = self._clean_mention_text(message_text, bot_username)

                if clean_message.strip():
                    # 🆕 构建包含上下文的完整消息
                    full_message = self._build_contextual_message(
                        clean_message, reply_context
                    )

                    # 通过 LangGraph 处理包含上下文的消息
                    response = await self.process_message_with_langgraph(
                        full_message, user_id
                    )
                    response = self._convert_markdown_titles(response)

                    if response:
                        await update.message.reply_text(
                            response,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                        self.logger.info(
                            f"Responded to user {user_id} via LangGraph in group with reply context"
                        )
                        return

            # 如果不是对话消息或LangGraph处理失败，使用原有逻辑
            chat_type = update.effective_chat.type
            user_name = (
                update.effective_user.first_name
                or update.effective_user.username
                or "User"
            )

            response_text = self.get_welcome_message(chat_type=chat_type)

            chat_ids = self.load_chat_ids()
            is_subscribed = user_id in chat_ids

            reply_markup = (
                self.create_main_menu()
                if is_subscribed
                else self.create_subscribe_menu()
            )

            if chat_type in ["group", "supergroup"]:
                response_text = f"Hi {user_name}! 👋\\n\\n" + response_text

            await update.message.reply_text(
                response_text, parse_mode="Markdown", reply_markup=reply_markup
            )

            self.logger.info(
                f"Responded to mention from {user_name} ({user_id}) in {chat_type}"
            )

        except Exception as e:
            self.logger.error(f"Error handling mention: {e}")

    def _is_command_message(self, message_text: str) -> bool:
        """Check if message is a command (starts with /)"""
        return message_text.strip().startswith("/")

    def _clean_mention_text(self, message_text: str, bot_username: str) -> str:
        """Remove bot mention from message text"""
        import re

        # 移除 @username 提及
        cleaned = re.sub(rf"@{re.escape(bot_username)}\s*", "", message_text)
        return cleaned.strip()

    async def handle_private_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle private messages (non-command) with LangGraph"""
        try:
            if update.effective_chat.type != "private":
                return  # 只处理私聊消息

            user_id = str(update.effective_user.id)
            message_text = update.message.text or ""

            # 跳过命令消息
            if self._is_command_message(message_text):
                return

            if self.is_rate_limited(user_id):
                self.logger.info(f"Rate limited private message for {user_id}")
                await update.message.reply_text(
                    "Please wait a moment before sending another message.",
                    parse_mode="Markdown",
                )
                return

            # 检查是否启用 LangGraph 对话功能
            if not self.enable_langgraph_chat:
                # 如果未启用对话功能，显示帮助信息
                await update.message.reply_text(
                    "👋 Hello! I'm a trading signal bot. Use /help to see available commands.",
                    parse_mode="Markdown",
                    reply_markup=self.create_main_menu(),
                )
                return

            # 发送"正在输入"指示
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action="typing"
            )

            # 通过 LangGraph 处理消息
            response = await self.process_message_with_langgraph(message_text, user_id)
            response = self._convert_markdown_titles(response)

            if response:
                await update.message.reply_text(
                    response, parse_mode="Markdown", disable_web_page_preview=True
                )
                self.logger.info(f"Responded to private message from user {user_id}")
            else:
                await update.message.reply_text(
                    "Sorry, I couldn't process your message right now. Please try again or use /help for available commands.",
                    parse_mode="Markdown",
                )

        except Exception as e:
            self.logger.error(f"Error handling private message: {e}")
            await update.message.reply_text(
                "Sorry, there was an error processing your message. Please try again later.",
                parse_mode="Markdown",
            )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with menu"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()
        chat_type = update.effective_chat.type

        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            self.save_chat_ids(chat_ids)

            welcome_text = self.get_welcome_message(chat_type=chat_type)
            if chat_type == "private":
                welcome_text = (
                    "🎉 *Welcome to Trading Signal Bot!*\\n\\n"
                    "✅ You have been subscribed to receive trading signals and backtest results.\\n\\n"
                    "Use the menu below to manage your subscription:"
                )

            self.logger.info(f"New user subscribed: {chat_id}")
            reply_markup = self.create_main_menu()
        else:
            if chat_type == "private":
                welcome_text = (
                    "👋 *Welcome back!*\\n\\n"
                    "📱 You are already subscribed to trading signals!\\n\\n"
                    "Use the menu below to manage your subscription:"
                )
            else:
                welcome_text = self.get_welcome_message(chat_type=chat_type)

            reply_markup = self.create_main_menu()

        await update.message.reply_text(
            welcome_text, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all button callbacks"""
        query = update.callback_query
        await query.answer()

        chat_id = str(query.from_user.id)
        chat_ids = self.load_chat_ids()
        is_subscribed = chat_id in chat_ids

        if query.data == "main_menu" or query.data == "refresh":
            if is_subscribed:
                text = "🏠 *Main Menu*\\n\\nYou are subscribed to trading signals. Choose an option:"
                reply_markup = self.create_main_menu()
            else:
                text = "🏠 *Main Menu*\\n\\nYou are not subscribed. Would you like to subscribe?"
                reply_markup = self.create_subscribe_menu()

            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )

        elif query.data == "status":
            if is_subscribed:
                total_subscribers = len(chat_ids)
                status_text = (
                    f"✅ *Subscription Status: ACTIVE*\\n\\n"
                    f"📊 Total Subscribers: {total_subscribers}\\n"
                    f"🔔 You will receive trading signals for: ETH, BTC\\n"
                    f"⏰ Signal frequency: Every 15 minutes\\n\\n"
                    f"Use the menu below to manage your subscription:"
                )
            else:
                status_text = (
                    "❌ *Subscription Status: INACTIVE*\\n\\n"
                    "You are not currently subscribed to notifications.\\n"
                    "Use the menu below to subscribe:"
                )

            reply_markup = (
                self.create_main_menu()
                if is_subscribed
                else self.create_subscribe_menu()
            )

            await query.edit_message_text(
                status_text, parse_mode="Markdown", reply_markup=reply_markup
            )

        elif query.data == "help":
            help_text = f"""
🤖 *Trading Signal Bot Help*

This bot provides automated trading signals and backtest results for cryptocurrency pairs.

*Features:*
📈 Real-time trading signals for ETH and BTC
📊 Backtest results for generated signals
⏰ Automated updates every 15 minutes
🔔 Instant notifications when signals are generated

*How to use:*
• Use the menu buttons to navigate
• Subscribe to receive notifications
• Check your status anytime
• Unsubscribe when needed

*Group Features:*
• Mention me (@{context.bot.username or "tradingbot"}) to see this menu
• I'll welcome new members automatically
• All features work in both private and group chats

*Support:*
If you encounter any issues, please contact the administrator.
            """

            keyboard = [
                [InlineKeyboardButton("◀️ Back to Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                help_text, parse_mode="Markdown", reply_markup=reply_markup
            )

        elif query.data == "subscribe":
            if not is_subscribed:
                chat_ids.append(chat_id)
                self.save_chat_ids(chat_ids)

                subscribe_text = (
                    "🎉 *Successfully Subscribed!*\\n\\n"
                    "✅ You will now receive trading signals and backtest results.\\n\\n"
                    "Welcome to our community of traders!"
                )
                self.logger.info(f"User subscribed via button: {chat_id}")
            else:
                subscribe_text = (
                    "✅ *Already Subscribed!*\\n\\n"
                    "You are already receiving trading signals.\\n\\n"
                    "Use the menu below to manage your subscription:"
                )

            await query.edit_message_text(
                subscribe_text,
                parse_mode="Markdown",
                reply_markup=self.create_main_menu(),
            )

        elif query.data == "unsubscribe":
            if is_subscribed:
                confirm_text = (
                    "⚠️ *Confirm Unsubscribe*\\n\\n"
                    "Are you sure you want to unsubscribe from trading signal notifications?\\n\\n"
                    "You will no longer receive signals and backtest results."
                )
                await query.edit_message_text(
                    confirm_text,
                    parse_mode="Markdown",
                    reply_markup=self.create_unsubscribe_menu(),
                )
            else:
                await query.edit_message_text(
                    "❌ You are not currently subscribed to notifications.",
                    parse_mode="Markdown",
                    reply_markup=self.create_subscribe_menu(),
                )

        elif query.data == "confirm_unsubscribe":
            if is_subscribed:
                chat_ids.remove(chat_id)
                self.save_chat_ids(chat_ids)

                unsubscribe_text = (
                    "😢 *Unsubscribed Successfully*\\n\\n"
                    "You will no longer receive trading signal notifications.\\n\\n"
                    "To re-subscribe, use the button below:"
                )
                self.logger.info(f"User unsubscribed via button: {chat_id}")
                reply_markup = self.create_subscribe_menu()
            else:
                unsubscribe_text = "❌ You were not subscribed."
                reply_markup = self.create_subscribe_menu()

            await query.edit_message_text(
                unsubscribe_text, parse_mode="Markdown", reply_markup=reply_markup
            )

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id in chat_ids:
            chat_ids.remove(chat_id)
            self.save_chat_ids(chat_ids)

            await update.message.reply_text(
                "😢 *Unsubscribed Successfully*\\n\\n"
                "You will no longer receive trading signal notifications.\\n\\n"
                "To re-subscribe, simply send /start anytime.",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu(),
            )
            self.logger.info(f"User unsubscribed: {chat_id}")
        else:
            await update.message.reply_text(
                "❌ You are not currently subscribed to notifications.\\n\\n"
                "Use /start to subscribe to trading signals.",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu(),
            )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id in chat_ids:
            total_subscribers = len(chat_ids)
            await update.message.reply_text(
                f"✅ *Subscription Status: ACTIVE*\\n\\n"
                f"📊 Total Subscribers: {total_subscribers}\\n"
                f"🔔 You will receive trading signals for: ETH, BTC\\n"
                f"⏰ Signal frequency: Every 15 minutes\\n\\n"
                f"Use the menu below to manage your subscription:",
                parse_mode="Markdown",
                reply_markup=self.create_main_menu(),
            )
        else:
            await update.message.reply_text(
                "❌ *Subscription Status: INACTIVE*\\n\\n"
                "You are not currently subscribed to notifications.\\n"
                "Use the menu below to subscribe:",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu(),
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = f"""
🤖 *Trading Signal Bot Help*

This bot provides automated trading signals and backtest results for cryptocurrency pairs.

*Available Commands:*
/start - Subscribe to trading signal notifications
/stop - Unsubscribe from notifications  
/status - Check your subscription status
/help - Show this help message

*Features:*
📈 Real-time trading signals for ETH and BTC
📊 Backtest results for generated signals
⏰ Automated updates every 15 minutes
🔔 Instant notifications when signals are generated

*Group Features:*
• Mention me (@{context.bot.username or "tradingbot"}) to see the menu
• I'll automatically welcome new members
• All subscription features work in groups

*Support:*
If you encounter any issues, please contact the administrator.
        """

        await update.message.reply_text(
            help_text, parse_mode="Markdown", reply_markup=self.create_main_menu()
        )

    # Error classification and retry methods (from telegram_service.py)
    def _classify_error(self, error: Exception) -> Tuple[bool, str]:
        """Classify error as retryable or permanent"""
        error_str = str(error).lower()
        error_type = type(error).__name__

        permanent_keywords = [
            "chat not found",
            "user not found",
            "bot was blocked",
            "bot was kicked",
            "user is deactivated",
            "chat is deactivated",
            "forbidden",
            "unauthorized",
            "bad request",
        ]

        for keyword in permanent_keywords:
            if keyword in error_str:
                return False, f"permanent_{keyword.replace(' ', '_')}"

        if error_type in self.retryable_errors:
            return True, f"retryable_{error_type.lower()}"

        if "too many requests" in error_str or "rate limit" in error_str:
            return True, "retryable_rate_limit"

        retryable_keywords = [
            "timeout",
            "network",
            "connection",
            "server error",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
            "internal server error",
        ]

        for keyword in retryable_keywords:
            if keyword in error_str:
                return True, f"retryable_{keyword.replace(' ', '_')}"

        return True, "retryable_unknown"

    def _calculate_retry_delay(self, attempt: int, error_category: str = "") -> float:
        """Calculate delay before retry with exponential backoff and optional jitter"""
        if "rate_limit" in error_category:
            base_delay = self.initial_retry_delay * 3
        else:
            base_delay = self.initial_retry_delay

        delay = base_delay * (self.retry_backoff_factor**attempt)
        delay = min(delay, self.max_retry_delay)

        if self.retry_jitter:
            jitter = random.uniform(0.8, 1.2)
            delay *= jitter

        return delay

    def format_message(self, text: str, message_type: str) -> str:
        """
        Enhanced message formatting with complete Telegram compatibility and table support
        """
        try:
            # Input validation
            if not text or not isinstance(text, str):
                self.logger.warning(
                    f"Invalid text input for message formatting: {type(text)}"
                )
                text = str(text) if text else "No content available"

            if not message_type:
                message_type = "update"

            # Step 1: Clean input text - remove any existing footers
            cleaned_text = self._remove_existing_footers(text)

            # Step 2: Detect and convert tables BEFORE other processing
            text_with_tables = self._advanced_table_format(cleaned_text)

            # Step 3: Sanitize content
            sanitized_text = self._sanitize_message_content(text_with_tables)

            # Step 4: Convert remaining markdown titles
            formatted_text = self._convert_markdown_titles(sanitized_text)

            # Step 5: Validate markdown syntax
            is_valid, error_msg = self._validate_telegram_markdown_with_tables(
                formatted_text
            )
            if not is_valid:
                self.logger.warning(f"Markdown validation failed: {error_msg}")
                formatted_text = self._selective_escape_preserve_tables(formatted_text)
                self.logger.info("Applied selective escaping while preserving tables")

            # Step 6: Generate message header
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            header_mapping = {
                "signal": "🔔 *New Trading Signal*",
                "backtest": "📊 *Backtest Result*",
                "alert": "🚨 *Trading Alert*",
                "analysis": "📈 *Market Analysis*",
                "update": "📢 *Trading Update*",
                "notification": "🔔 *Notification*",
            }

            header = header_mapping.get(message_type.lower(), "📈 *Trading Update*")

            # Step 7: Build complete message (确保只有一个尾部)
            complete_message = f"""{header}
    ⏰ *Time:* {timestamp}

    {formatted_text}

    ---
    _Automated Trading Signal System_"""

            # Step 8: Handle message length
            if len(complete_message) > 4000:
                self.logger.warning(
                    f"Message too long ({len(complete_message)} chars), optimizing..."
                )
                complete_message = self._optimize_long_message_with_tables(
                    header, timestamp, formatted_text
                )

            # Step 9: Final validation
            final_is_valid, final_error = self._validate_telegram_markdown_with_tables(
                complete_message
            )
            if not final_is_valid:
                self.logger.error(f"Final message validation failed: {final_error}")
                complete_message = self._create_safe_fallback_with_tables(
                    message_type, timestamp, sanitized_text
                )

            self.logger.debug(
                f"Successfully formatted {message_type} message with tables ({len(complete_message)} chars)"
            )

            return complete_message

        except Exception as e:
            self.logger.error(f"Critical error in message formatting: {e}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            return f"""📢 TRADING UPDATE
    Time: {timestamp}

    {self._escape_telegram_markdown(str(text)[:3000])}

    ---
    Automated Trading Signal System"""

    def _remove_existing_footers(self, text: str) -> str:
        """
        Remove any existing footers from the input text to prevent duplication

        Args:
            text (str): Input text that might contain existing footers

        Returns:
            str: Cleaned text without footers
        """
        if not text:
            return ""

        # Common footer patterns to remove
        footer_patterns = [
            r"\n?---\n?_?Automated Trading Signal System_?\n?$",
            r"\n?---\n?Automated Trading Signal System\n?$",
            r"\n?_Automated Trading Signal System_\n?$",
            r"\n?Automated Trading Signal System\n?$",
            r"\n?---\n?_自动交易信号系统_\n?$",
            r"\n?自动交易信号系统\n?$",
        ]

        cleaned_text = text
        for pattern in footer_patterns:
            cleaned_text = re.sub(
                pattern, "", cleaned_text, flags=re.MULTILINE | re.IGNORECASE
            )

        # Remove trailing whitespace and multiple newlines
        cleaned_text = re.sub(r"\n{3,}$", "\n\n", cleaned_text)
        cleaned_text = cleaned_text.rstrip()

        return cleaned_text

    def _convert_markdown_titles(self, text: str) -> str:
        """Convert Markdown titles with multi-level indentation support"""
        import re

        # Convert ### (h3) to bold format with more indentation
        text = re.sub(r"^###\s+(.+)$", r"      ▫️ **\1**", text, flags=re.MULTILINE)

        # Convert ## (h2) to bold format with indentation
        text = re.sub(r"^##\s+(.+)$", r"    ▪️ **\1**", text, flags=re.MULTILINE)

        # Convert # (h1) to bold format
        text = re.sub(r"^#\s+(.+)$", r"🔶 **\1**", text, flags=re.MULTILINE)

        # Handle edge case: remove any remaining markdown-style headers that weren't caught
        text = re.sub(r"^#{4,}\s+(.+)$", r"        • *\1*", text, flags=re.MULTILINE)

        return text

    def _escape_telegram_markdown(self, text: str) -> str:
        """
        Safely escape special characters for Telegram Markdown V2 compatibility

        Args:
            text (str): Raw text to escape

        Returns:
            str: Safely escaped text for Telegram
        """
        if not text:
            return ""

        # Characters that need escaping in Telegram Markdown
        # Based on Telegram Bot API documentation
        special_chars = {
            "_": "\\_",
            "*": "\\*",
            "[": "\\[",
            "]": "\\]",
            "(": "\\(",
            ")": "\\)",
            "~": "\\~",
            "`": "\\`",
            ">": "\\>",
            "#": "\\#",
            "+": "\\+",
            "-": "\\-",
            "=": "\\=",
            "|": "\\|",
            "{": "\\{",
            "}": "\\}",
            ".": "\\.",
            "!": "\\!",
        }

        # Escape special characters
        escaped_text = text
        for char, escaped_char in special_chars.items():
            escaped_text = escaped_text.replace(char, escaped_char)

        return escaped_text

    def _validate_telegram_markdown(self, text: str) -> Tuple[bool, str]:
        """
        Validate if text contains valid Telegram Markdown syntax

        Args:
            text (str): Text to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Check for unmatched markdown pairs
            markdown_pairs = [
                ("*", "bold"),
                ("_", "italic"),
                ("`", "code"),
                ("```", "code block"),
            ]

            for marker, name in markdown_pairs:
                count = text.count(marker)
                if marker == "```":
                    # Code blocks should have even count (opening and closing)
                    if count % 2 != 0:
                        return False, f"Unmatched {name} markers (```)"
                else:
                    # Other markers should have even count
                    if count % 2 != 0:
                        return False, f"Unmatched {name} markers ({marker})"

            # Check for nested markdown conflicts
            if re.search(r"\*.*_.*\*", text) or re.search(r"_.*\*.*_", text):
                self.logger.warning("Detected potentially nested markdown formatting")

            return True, ""

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _split_long_message(self, text: str, max_length: int = 4000) -> List[str]:
        """
        Split long messages into multiple parts while preserving formatting

        Args:
            text (str): Text to split
            max_length (int): Maximum length per message (Telegram limit is 4096)

        Returns:
            List[str]: List of message parts
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        lines = text.split("\n")
        current_part = ""

        for line in lines:
            # If adding this line would exceed limit
            if len(current_part) + len(line) + 1 > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = ""

                # If single line is too long, split it
                if len(line) > max_length:
                    words = line.split(" ")
                    temp_line = ""

                    for word in words:
                        if len(temp_line) + len(word) + 1 <= max_length:
                            temp_line += (" " if temp_line else "") + word
                        else:
                            if temp_line:
                                parts.append(temp_line)
                            temp_line = word

                    if temp_line:
                        current_part = temp_line
                else:
                    current_part = line
            else:
                current_part += ("\n" if current_part else "") + line

        if current_part:
            parts.append(current_part.strip())

        return parts

    def _sanitize_message_content(self, text: str) -> str:
        """
        Sanitize message content for safe Telegram transmission

        Args:
            text (str): Raw message content

        Returns:
            str: Sanitized content
        """
        if not text:
            return ""

        # Remove or replace problematic characters
        sanitized = text

        # Replace multiple consecutive newlines with maximum of 2
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)

        # Remove leading/trailing whitespace from each line
        lines = sanitized.split("\n")
        sanitized_lines = [line.strip() for line in lines]
        sanitized = "\n".join(sanitized_lines)

        # Remove excessive whitespace
        sanitized = re.sub(r" {2,}", " ", sanitized)

        return sanitized.strip()

    def _convert_markdown_titles(self, text: str) -> str:
        """
        Enhanced Markdown title conversion with better Telegram compatibility
        """
        import re

        # Convert ### (h3) to bold format with more indentation
        text = re.sub(r"^###\s+(.+)$", r"      ▫️ **\1**", text, flags=re.MULTILINE)

        # Convert ## (h2) to bold format with indentation
        text = re.sub(r"^##\s+(.+)$", r"    ▪️ **\1**", text, flags=re.MULTILINE)

        # Convert # (h1) to bold format
        text = re.sub(r"^#\s+(.+)$", r"🔶 **\1**", text, flags=re.MULTILINE)

        # Handle edge case: remove any remaining markdown-style headers
        text = re.sub(r"^#{4,}\s+(.+)$", r"        • *\1*", text, flags=re.MULTILINE)

        # Fix potential double escaping in converted titles
        text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)

        return text

    def _detect_and_convert_tables(self, text: str) -> str:
        """
        Detect Markdown tables and convert them to Telegram-friendly format

        Args:
            text (str): Text potentially containing Markdown tables

        Returns:
            str: Text with tables converted to readable format
        """
        import re

        # Regex to match Markdown table pattern
        table_pattern = (
            r"(\n\s*\|[^\n]+\|\s*\n\s*\|[-\s\|:]+\|\s*\n(?:\s*\|[^\n]+\|\s*\n?)*)"
        )

        def convert_table(match):
            table_text = match.group(1).strip()
            lines = [line.strip() for line in table_text.split("\n") if line.strip()]

            if len(lines) < 3:  # Need header, separator, and at least one data row
                return table_text

            try:
                # Parse header row
                header_line = lines[0]
                headers = [cell.strip() for cell in header_line.split("|")[1:-1]]

                # Skip separator line (lines[1])

                # Parse data rows
                data_rows = []
                for line in lines[2:]:
                    if "|" in line:
                        cells = [cell.strip() for cell in line.split("|")[1:-1]]
                        if len(cells) == len(headers):
                            data_rows.append(cells)

                # Convert to Telegram-friendly format
                if not data_rows:
                    return table_text

                # Create formatted table
                formatted_lines = []

                # Add header with emoji
                formatted_lines.append("📊 **Table Data:**")
                formatted_lines.append("")

                # Method 1: Vertical list format (most readable on mobile)
                for i, row in enumerate(data_rows):
                    formatted_lines.append(f"**Entry {i+1}:**")
                    for j, (header, value) in enumerate(zip(headers, row)):
                        # Clean header and value
                        clean_header = header.replace("*", "").replace("_", "").strip()
                        clean_value = value.replace("*", "").replace("_", "").strip()
                        formatted_lines.append(f"  • {clean_header}: `{clean_value}`")
                    formatted_lines.append("")

                return "\n".join(formatted_lines)

            except Exception as e:
                self.logger.warning(f"Table conversion failed: {e}")
                # Fallback: convert to simple list
                return self._table_fallback_format(table_text)

        # Apply table conversion
        converted_text = re.sub(table_pattern, convert_table, text, flags=re.MULTILINE)
        return converted_text

    def _table_fallback_format(self, table_text: str) -> str:
        """
        Fallback table formatting when parsing fails

        Args:
            table_text (str): Raw table text

        Returns:
            str: Simple formatted version
        """
        lines = table_text.split("\n")
        formatted_lines = ["📋 **Data Table:**", ""]

        for line in lines:
            if "|" in line and not line.strip().startswith("|---"):
                # Extract cells and format as bullet points
                cells = [cell.strip() for cell in line.split("|") if cell.strip()]
                if cells:
                    formatted_line = " | ".join(f"`{cell}`" for cell in cells)
                    formatted_lines.append(f"  {formatted_line}")

        return "\n".join(formatted_lines)

    def _advanced_table_format(self, text: str) -> str:
        """
        Advanced table formatting with multiple layout options

        Args:
            text (str): Text with potential tables

        Returns:
            str: Text with optimally formatted tables
        """
        import re

        # Enhanced table detection
        table_pattern = (
            r"(\n\s*\|[^\n]+\|\s*\n\s*\|[-\s\|:]+\|\s*\n(?:\s*\|[^\n]+\|\s*\n?)*)"
        )

        def smart_table_converter(match):
            table_text = match.group(1).strip()
            lines = [line.strip() for line in table_text.split("\n") if line.strip()]

            if len(lines) < 3:
                return table_text

            try:
                # Parse table structure
                header_line = lines[0]
                headers = [cell.strip() for cell in header_line.split("|")[1:-1]]

                # Parse data rows
                data_rows = []
                for line in lines[2:]:
                    if "|" in line:
                        cells = [cell.strip() for cell in line.split("|")[1:-1]]
                        if len(cells) == len(headers):
                            data_rows.append(cells)

                if not data_rows:
                    return table_text

                # Determine best format based on table characteristics
                return self._choose_table_format(headers, data_rows)

            except Exception as e:
                self.logger.debug(f"Advanced table parsing failed: {e}")
                return self._table_fallback_format(table_text)

        return re.sub(table_pattern, smart_table_converter, text, flags=re.MULTILINE)

    def _choose_table_format(self, headers: list, data_rows: list) -> str:
        """
        Choose the best table format based on content characteristics

        Args:
            headers (list): Table headers
            data_rows (list): Table data rows

        Returns:
            str: Optimally formatted table
        """
        num_cols = len(headers)
        num_rows = len(data_rows)

        # Calculate content characteristics
        max_cell_length = max(
            max(len(str(cell)) for cell in row) for row in data_rows + [headers]
        )

        total_width = (
            sum(len(str(cell)) for cell in headers) + num_cols * 3
        )  # spaces and separators

        # Choose format based on characteristics
        if num_cols <= 2 and num_rows <= 5:
            # Small table: Use inline format
            return self._format_table_inline(headers, data_rows)
        elif num_cols <= 3 and max_cell_length <= 15:
            # Medium table: Use compact format
            return self._format_table_compact(headers, data_rows)
        elif num_cols <= 4 and total_width <= 60:
            # Wide table: Use aligned format
            return self._format_table_aligned(headers, data_rows)
        else:
            # Large table: Use vertical list format
            return self._format_table_vertical(headers, data_rows)

    def _format_table_inline(self, headers: list, data_rows: list) -> str:
        """Inline format for small tables (2 columns, ≤5 rows)"""
        formatted = ["📊 **Quick Stats:**", ""]

        for row in data_rows:
            if len(row) >= 2:
                key = row[0].replace("*", "").replace("_", "").strip()
                value = row[1].replace("*", "").replace("_", "").strip()
                formatted.append(f"**{key}:** `{value}`")

        return "\n".join(formatted)

    def _format_table_compact(self, headers: list, data_rows: list) -> str:
        """Compact format for medium tables (≤3 columns, short content)"""
        formatted = ["📋 **Data Summary:**", ""]

        # Add headers
        header_line = " | ".join(f"**{h}**" for h in headers)
        formatted.append(header_line)
        formatted.append("─" * min(40, len(header_line)))

        # Add rows
        for row in data_rows:
            clean_row = [cell.replace("*", "").replace("_", "").strip() for cell in row]
            row_line = " | ".join(f"`{cell}`" for cell in clean_row)
            formatted.append(row_line)

        return "\n".join(formatted)

    def _format_table_aligned(self, headers: list, data_rows: list) -> str:
        """Aligned format for wider tables with good readability"""
        formatted = ["📊 **Detailed Table:**", "```"]

        # Calculate column widths
        all_rows = [headers] + data_rows
        col_widths = []
        for i in range(len(headers)):
            max_width = max(len(str(row[i])) if i < len(row) else 0 for row in all_rows)
            col_widths.append(min(max_width + 2, 20))  # Cap at 20 chars

        # Format header
        header_line = "|".join(h.center(w) for h, w in zip(headers, col_widths))
        separator_line = "|".join("─" * w for w in col_widths)

        formatted.append(header_line)
        formatted.append(separator_line)

        # Format rows
        for row in data_rows:
            padded_row = []
            for i, (cell, width) in enumerate(zip(row, col_widths)):
                if i < len(row):
                    cell_str = str(cell)[: width - 2]  # Truncate if too long
                    padded_row.append(cell_str.ljust(width))
                else:
                    padded_row.append(" " * width)

            row_line = "|".join(padded_row)
            formatted.append(row_line)

        formatted.append("```")
        return "\n".join(formatted)

    def _format_table_vertical(self, headers: list, data_rows: list) -> str:
        """Vertical list format for large/complex tables"""
        formatted = ["📊 **Comprehensive Data:**", ""]

        for i, row in enumerate(data_rows, 1):
            formatted.append(f"**📌 Record {i}:**")

            for j, (header, value) in enumerate(zip(headers, row)):
                clean_header = header.replace("*", "").replace("_", "").strip()
                clean_value = str(value).replace("*", "").replace("_", "").strip()

                # Add appropriate emoji for common data types
                emoji = self._get_data_emoji(clean_header.lower(), clean_value)
                formatted.append(f"  {emoji} **{clean_header}:** `{clean_value}`")

            formatted.append("")  # Empty line between records

        return "\n".join(formatted)

    def _get_data_emoji(self, header: str, value: str) -> str:
        """Get appropriate emoji for data field"""
        header_lower = header.lower()
        value_lower = value.lower()

        # Price/Money indicators
        if any(
            word in header_lower for word in ["price", "cost", "fee", "amount", "value"]
        ):
            return "💰"
        if "$" in value or "€" in value or "£" in value:
            return "💰"

        # Percentage indicators
        if "%" in value or "percent" in header_lower:
            if "+" in value or value_lower.startswith("up"):
                return "📈"
            elif "-" in value or value_lower.startswith("down"):
                return "📉"
            else:
                return "📊"

        # Volume/Quantity indicators
        if any(
            word in header_lower for word in ["volume", "quantity", "count", "total"]
        ):
            return "📦"

        # Time indicators
        if any(word in header_lower for word in ["time", "date", "timestamp", "when"]):
            return "⏰"

        # Symbol/Asset indicators
        if any(
            word in header_lower
            for word in ["symbol", "asset", "coin", "token", "pair"]
        ):
            return "🪙"

        # Status indicators
        if any(word in header_lower for word in ["status", "state", "condition"]):
            if any(
                word in value_lower for word in ["active", "open", "buy", "bullish"]
            ):
                return "🟢"
            elif any(
                word in value_lower
                for word in ["inactive", "closed", "sell", "bearish"]
            ):
                return "🔴"
            else:
                return "🟡"

        # Default
        return "▫️"

    async def _send_single_message_with_retry(
        self, chat_id: str, formatted_message: str, semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """Send message to a single chat with intelligent retry mechanism"""
        async with semaphore:
            last_error = None
            error_category = "unknown"

            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        self.logger.info(
                            f"Retry attempt {attempt}/{self.max_retries} for chat {chat_id}"
                        )

                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=formatted_message,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )

                    await asyncio.sleep(self.send_delay)

                    if attempt > 0:
                        self.logger.info(
                            f"Successfully sent to {chat_id} after {attempt} retries"
                        )

                    return {
                        "chat_id": chat_id,
                        "success": True,
                        "error": None,
                        "attempts": attempt + 1,
                        "retry_category": error_category if attempt > 0 else None,
                    }

                except TelegramError as e:
                    last_error = e
                    is_retryable, error_category = self._classify_error(e)

                    self.logger.warning(
                        f"Attempt {attempt + 1} failed for chat {chat_id}: {e} "
                        f"(retryable: {is_retryable}, category: {error_category})"
                    )

                    if not is_retryable:
                        self.logger.error(
                            f"Permanent error for chat {chat_id}, not retrying: {e}"
                        )
                        return {
                            "chat_id": chat_id,
                            "success": False,
                            "error": f"Permanent Telegram error: {e}",
                            "attempts": attempt + 1,
                            "retry_category": error_category,
                            "is_permanent": True,
                        }

                    if attempt >= self.max_retries:
                        break

                    retry_delay = self._calculate_retry_delay(attempt, error_category)
                    self.logger.debug(
                        f"Waiting {retry_delay:.2f}s before retry {attempt + 1} for chat {chat_id}"
                    )
                    await asyncio.sleep(retry_delay)

                except Exception as e:
                    last_error = e
                    is_retryable, error_category = self._classify_error(e)

                    self.logger.warning(
                        f"Unexpected error attempt {attempt + 1} for chat {chat_id}: {e} "
                        f"(retryable: {is_retryable}, category: {error_category})"
                    )

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
                "is_permanent": False,
            }

    def _validate_telegram_markdown_with_tables(self, text: str) -> tuple:
        """
        Enhanced validation that preserves table formatting

        Args:
            text (str): Text to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Extract table sections to validate separately
            table_pattern = r"```[^`]+```"
            tables = re.findall(table_pattern, text)

            # Remove tables for general markdown validation
            text_without_tables = re.sub(table_pattern, "[TABLE]", text)

            # Validate non-table content
            is_valid, error_msg = self._validate_telegram_markdown(text_without_tables)

            if not is_valid:
                return False, error_msg

            # Validate table sections (they should be in code blocks, so safer)
            for table in tables:
                # Tables in code blocks are generally safe, but check for basic issues
                if table.count("```") % 2 != 0:
                    return False, "Unmatched code block markers in table"

            return True, ""

        except Exception as e:
            return False, f"Table validation error: {str(e)}"

    def _selective_escape_preserve_tables(self, text: str) -> str:
        """
        Escape special characters while preserving table formatting

        Args:
            text (str): Text with tables to selectively escape

        Returns:
            str: Safely escaped text with preserved tables
        """
        # Pattern to match formatted tables and code blocks
        protected_patterns = [
            r"```[^`]*```",  # Code blocks (including table formatting)
            r"📊 \*\*[^*]+\*\*:",  # Table headers
            r"📋 \*\*[^*]+\*\*:",  # Table headers
            r"  [▫️•] \*\*[^*]+\*\*: `[^`]*`",  # Table rows
        ]

        # Store protected content
        protected_content = {}
        placeholder_counter = 0

        # Replace protected content with placeholders
        working_text = text
        for pattern in protected_patterns:
            matches = re.finditer(pattern, working_text)
            for match in matches:
                placeholder = f"__PROTECTED_{placeholder_counter}__"
                protected_content[placeholder] = match.group(0)
                working_text = working_text.replace(match.group(0), placeholder, 1)
                placeholder_counter += 1

        # Escape the remaining content
        escaped_text = self._escape_telegram_markdown(working_text)

        # Restore protected content
        for placeholder, original in protected_content.items():
            escaped_text = escaped_text.replace(placeholder, original)

        return escaped_text

    def _optimize_long_message_with_tables(
        self, header: str, timestamp: str, content: str
    ) -> str:
        """
        Optimize long messages while preserving table readability and avoiding footer duplication
        """
        # Clean content first to avoid duplicated footers
        clean_content = self._remove_existing_footers(content)

        # Try simplified header first
        simplified_message = f"""{header}
    ⏰ {timestamp}

    {clean_content}

    ---
    Automated System"""

        if len(simplified_message) <= 4000:
            return simplified_message

        # If still too long, try to compress tables
        compressed_content = self._compress_table_content(clean_content)

        compressed_message = f"""{header}
    ⏰ {timestamp}

    {compressed_content}

    ---
    Automated System"""

        if len(compressed_message) <= 4000:
            return compressed_message

        # Last resort: truncate but preserve table structure
        return self._truncate_preserve_tables(compressed_message)

    def _compress_table_content(self, content: str) -> str:
        """
        Compress table content while maintaining readability and removing footers
        """
        # First remove any existing footers
        clean_content = self._remove_existing_footers(content)

        # Replace verbose table introductions
        replacements = {
            "📊 **Comprehensive Data:**": "📊 **Data:**",
            "📋 **Data Summary:**": "📋 **Summary:**",
            "📊 **Detailed Table:**": "📊 **Table:**",
            "📊 **Quick Stats:**": "📊 **Stats:**",
            "**📌 Record ": "**Record ",
        }

        compressed = clean_content
        for old, new in replacements.items():
            compressed = compressed.replace(old, new)

        # Compress excessive whitespace in tables
        compressed = re.sub(r"\n\n\n+", "\n\n", compressed)

        # Shorten long data values in tables
        compressed = re.sub(
            r"`([^`]{25,})`", lambda m: f"`{m.group(1)[:22]}...`", compressed
        )

        return compressed

    def _truncate_preserve_tables(self, message: str) -> str:
        """
        Truncate message while preserving table structure and ensuring single footer
        """
        # Remove any existing footers first
        clean_message = self._remove_existing_footers(message)

        lines = clean_message.split("\n")
        result_lines = []
        current_length = 0
        in_table = False

        for i, line in enumerate(lines):
            line_length = len(line) + 1  # +1 for newline

            # Check if we're starting a table
            if any(marker in line for marker in ["📊 **", "📋 **", "```"]):
                in_table = True

            # Check if we're ending a table
            if in_table and (
                line.strip() == ""
                and i < len(lines) - 1
                and not any(
                    marker in lines[i + 1]
                    for marker in ["  •", "  ▫️", "**Record", "```"]
                )
            ):
                in_table = False

            # If adding this line would exceed limit (留出空间给尾部)
            if current_length + line_length > 3700:  # 给尾部预留更多空间
                if in_table:
                    # Complete the current table
                    result_lines.append("  ...")
                    result_lines.append("")

                # Add truncation notice
                result_lines.append("📄 **[Message truncated due to length]**")
                break

            result_lines.append(line)
            current_length += line_length

        # 确保添加统一的尾部
        if result_lines:
            # 清理末尾空行
            while result_lines and result_lines[-1].strip() == "":
                result_lines.pop()

            # 添加统一尾部
            result_lines.extend(["", "---", "Automated Trading Signal System"])

        return "\n".join(result_lines)

    def _create_safe_fallback_with_tables(
        self, message_type: str, timestamp: str, content: str
    ) -> str:
        """
        Create safe fallback message that preserves basic table data and avoids duplication
        """
        # Clean content to remove existing footers
        clean_content = self._remove_existing_footers(content)

        # Extract basic table data if present
        table_data = self._extract_basic_table_data(clean_content)

        safe_content = self._escape_telegram_markdown(clean_content[:2000])

        fallback_message = f"""📢 {message_type.upper()}
    Time: {timestamp}

    {safe_content}"""

        if table_data:
            fallback_message += f"\n\n📊 **Table Data:**\n{table_data}"

        fallback_message += "\n\n---\nAutomated Trading Signal System"

        return fallback_message

    def _extract_basic_table_data(self, content: str) -> str:
        """
        Extract basic table data for fallback display

        Args:
            content (str): Content with potential tables

        Returns:
            str: Basic table data as simple list
        """
        # Look for table-like patterns
        table_patterns = [
            r"  [▫️•] \*\*([^*]+)\*\*: `([^`]+)`",  # Vertical table format
            r"\*\*([^*]+):\*\* `([^`]+)`",  # Inline format
        ]

        extracted = []
        for pattern in table_patterns:
            matches = re.findall(pattern, content)
            for key, value in matches[:10]:  # Limit to first 10 entries
                clean_key = key.strip()
                clean_value = value.strip()
                extracted.append(f"• {clean_key}: {clean_value}")

        return "\n".join(extracted) if extracted else ""

    # 添加表格预览功能
    def preview_table_formatting(self, markdown_table: str) -> Dict[str, Any]:
        """
        Preview how a Markdown table will be formatted for Telegram

        Args:
            markdown_table (str): Raw Markdown table

        Returns:
            Dict[str, Any]: Preview information
        """
        try:
            # Test table conversion
            converted = self._advanced_table_format(markdown_table)

            # Analyze table characteristics
            lines = markdown_table.strip().split("\n")
            table_lines = [line for line in lines if "|" in line]

            if len(table_lines) >= 3:
                header_line = table_lines[0]
                headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
                data_lines = table_lines[2:]  # Skip separator

                preview_info = {
                    "original_table": markdown_table,
                    "converted_table": converted,
                    "table_stats": {
                        "columns": len(headers),
                        "data_rows": len(data_lines),
                        "headers": headers,
                        "original_length": len(markdown_table),
                        "converted_length": len(converted),
                    },
                    "format_used": self._detect_format_used(converted),
                    "readability_score": self._calculate_table_readability(converted),
                    "telegram_compatibility": True,
                }

                return preview_info
            else:
                return {
                    "error": "Invalid table format",
                    "original_table": markdown_table,
                    "telegram_compatibility": False,
                }

        except Exception as e:
            return {
                "error": f"Table preview failed: {str(e)}",
                "original_table": markdown_table,
                "telegram_compatibility": False,
            }

    def _detect_format_used(self, converted_text: str) -> str:
        """Detect which table format was used"""
        if "📊 **Quick Stats:**" in converted_text:
            return "inline"
        elif "📋 **Data Summary:**" in converted_text:
            return "compact"
        elif "```" in converted_text:
            return "aligned"
        elif (
            "📊 **Comprehensive Data:**" in converted_text
            or "**Record" in converted_text
        ):
            return "vertical"
        else:
            return "fallback"

    def _calculate_table_readability(self, converted_text: str) -> str:
        """Calculate readability score for converted table"""
        lines = converted_text.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) <= 10:
            return "excellent"
        elif len(non_empty_lines) <= 20:
            return "good"
        elif len(non_empty_lines) <= 30:
            return "fair"
        else:
            return "poor"

    async def send_formatted_message_safely(
        self, chat_ids: List[str], message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """
        Enhanced message sending with automatic splitting for long messages

        Args
            chat_ids (List[str]): List of chat IDs to send to
            message (str): Raw message content
            message_type (str): Message type

        Returns:
            Dict[str, Any]: Detailed sending results
        """
        try:
            # Format the message
            formatted_message = self.format_message(message, message_type)

            # Check if message needs splitting
            if len(formatted_message) > 4000:
                self.logger.info("Message requires splitting due to length")
                message_parts = self._split_long_message(formatted_message)

                # Send multiple parts
                all_results = []
                for i, part in enumerate(message_parts):
                    part_header = (
                        f"📄 *Part {i+1}/{len(message_parts)}*\n\n"
                        if len(message_parts) > 1
                        else ""
                    )
                    final_part = part_header + part

                    result = await self.send_to_multiple_chats(
                        chat_ids, final_part, f"{message_type}_part_{i+1}"
                    )
                    all_results.append(result)

                    # Small delay between parts to avoid rate limiting
                    if i < len(message_parts) - 1:
                        await asyncio.sleep(0.5)

                # Combine results
                total_success = sum(r.get("success_count", 0) for r in all_results)
                total_failed = sum(r.get("failed_count", 0) for r in all_results)

                return {
                    "success": total_success > 0,
                    "message_type": f"{message_type}_multipart",
                    "parts_sent": len(message_parts),
                    "total_chats": len(chat_ids),
                    "success_count": total_success,
                    "failed_count": total_failed,
                    "detailed_results": all_results,
                    "was_split": True,
                }
            else:
                # Send as single message using existing method
                result = await self.send_to_multiple_chats(
                    chat_ids, formatted_message, message_type
                )
                result["was_split"] = False
                return result

        except Exception as e:
            self.logger.error(f"Error in safe message sending: {e}")
            return {
                "success": False,
                "error": f"Message sending failed: {str(e)}",
                "message_type": message_type,
                "total_chats": len(chat_ids),
                "success_count": 0,
                "failed_count": len(chat_ids),
                "was_split": False,
            }

    # Enhanced method to replace the existing send_to_multiple_chats for better integration
    async def send_to_multiple_chats_enhanced(
        self, chat_ids: List[str], message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """
        Enhanced version of send_to_multiple_chats with automatic message formatting

        This method replaces the direct call to format_message in the original method
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
                "retry_stats": {},
                "formatting_info": {"status": "skipped", "reason": "no_chats"},
            }

        # Use enhanced formatting
        try:
            formatted_message = self.format_message(message, message_type)
            formatting_success = True
            formatting_info = {
                "status": "success",
                "original_length": len(message),
                "formatted_length": len(formatted_message),
                "was_truncated": len(formatted_message) < len(message),
            }
        except Exception as e:
            self.logger.error(f"Message formatting failed, using fallback: {e}")
            formatted_message = (
                f"📢 {message_type.upper()}\n\n{message}\n\n---\nAutomated System"
            )
            formatting_success = False
            formatting_info = {
                "status": "fallback_used",
                "error": str(e),
                "formatted_length": len(formatted_message),
            }

        self.logger.info(
            f"Sending {message_type} message to {len(chat_ids)} chats "
            f"(formatted: {len(formatted_message)} chars, success: {formatting_success})"
        )
        start_time = time.time()

        semaphore = asyncio.Semaphore(self.max_concurrent_sends)

        tasks = [
            self._send_single_message_with_retry(chat_id, formatted_message, semaphore)
            for chat_id in chat_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results (keeping the existing logic)
        sent_chats = []
        failed_chats = []
        errors = []
        permanent_failures = []
        retry_stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_after_retries": 0,
            "permanent_errors": 0,
            "retry_categories": {},
        }

        for result in results:
            if isinstance(result, Exception):
                error_msg = f"Task exception: {result}"
                errors.append(error_msg)
                failed_chats.append("unknown")
                self.logger.error(error_msg)
            elif result["success"]:
                sent_chats.append(result["chat_id"])

                attempts = result.get("attempts", 1)
                retry_stats["total_attempts"] += attempts

                if attempts > 1:
                    retry_stats["successful_retries"] += 1
                    category = result.get("retry_category", "unknown")
                    retry_stats["retry_categories"][category] = (
                        retry_stats["retry_categories"].get(category, 0) + 1
                    )

                self.logger.debug(
                    f"Successfully sent to {result['chat_id']} (attempts: {attempts})"
                )
            else:
                failed_chats.append(result["chat_id"])
                error_msg = f"Chat {result['chat_id']}: {result['error']}"
                errors.append(error_msg)

                attempts = result.get("attempts", 1)
                retry_stats["total_attempts"] += attempts

                if result.get("is_permanent", False):
                    permanent_failures.append(result["chat_id"])
                    retry_stats["permanent_errors"] += 1
                else:
                    retry_stats["failed_after_retries"] += 1

                category = result.get("retry_category", "unknown")
                retry_stats["retry_categories"][category] = (
                    retry_stats["retry_categories"].get(category, 0) + 1
                )

                self.logger.error(
                    f"Failed to send to {result['chat_id']}: {result['error']} "
                    f"(attempts: {attempts})"
                )

        end_time = time.time()
        total_duration = end_time - start_time

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
            "formatting_info": formatting_info,
            "performance": {
                "total_duration_seconds": round(total_duration, 2),
                "average_attempts_per_chat": (
                    round(retry_stats["total_attempts"] / len(chat_ids), 2)
                    if chat_ids
                    else 0
                ),
                "success_rate": (
                    round((len(sent_chats) / len(chat_ids)) * 100, 2) if chat_ids else 0
                ),
            },
        }

        # Enhanced logging with formatting information
        if success:
            if failed_chats:
                success_rate = (len(sent_chats) / len(chat_ids)) * 100
                self.logger.warning(
                    f"Partially successful: {len(sent_chats)}/{len(chat_ids)} chats "
                    f"({success_rate:.1f}% success rate) in {total_duration:.2f}s "
                    f"[Formatting: {formatting_info['status']}]"
                )
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(
                        f"Retry mechanism recovered {retry_stats['successful_retries']} failures"
                    )
            else:
                self.logger.info(
                    f"Successfully sent {message_type} message to all {len(sent_chats)} chats "
                    f"in {total_duration:.2f}s [Formatting: {formatting_info['status']}]"
                )
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(
                        f"Retry mechanism recovered {retry_stats['successful_retries']} temporary failures"
                    )
        else:
            self.logger.error(
                f"Failed to send {message_type} message to any chats "
                f"({retry_stats['permanent_errors']} permanent, "
                f"{retry_stats['failed_after_retries']} exhausted retries) "
                f"[Formatting: {formatting_info['status']}]"
            )

        return response

    def get_message_formatting_stats(self) -> Dict[str, Any]:
        """
        Get statistics about message formatting performance and issues

        Returns:
            Dict[str, Any]: Formatting statistics and health info
        """
        return {
            "telegram_compatibility": {
                "markdown_validation_enabled": True,
                "auto_escaping_enabled": True,
                "message_splitting_enabled": True,
                "max_message_length": 4000,
                "telegram_limit": 4096,
            },
            "supported_message_types": [
                "signal",
                "backtest",
                "alert",
                "analysis",
                "update",
                "notification",
            ],
            "safety_features": {
                "special_character_escaping": True,
                "markdown_validation": True,
                "automatic_fallback": True,
                "emergency_plain_text": True,
                "message_length_checking": True,
            },
            "fallback_mechanisms": [
                "markdown_validation_failure -> safe_escaping",
                "safe_escaping_failure -> plain_text",
                "length_exceeded -> truncation_with_warning",
                "critical_error -> emergency_plain_text",
            ],
            "performance_optimizations": {
                "content_sanitization": True,
                "efficient_regex_processing": True,
                "minimal_string_operations": True,
            },
        }

    def validate_message_before_send(
        self, message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """
        Pre-validate message content before attempting to send

        Args:
            message (str): Raw message content to validate
            message_type (str): Type of message

        Returns:
            Dict[str, Any]: Validation results and recommendations
        """
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "estimated_length": 0,
            "will_be_split": False,
            "formatting_preview": "",
        }

        try:
            # Basic input validation
            if not message or not isinstance(message, str):
                validation_result["is_valid"] = False
                validation_result["errors"].append("Invalid or empty message content")
                return validation_result

            # Estimate formatted length
            try:
                formatted_preview = self.format_message(message, message_type)
                validation_result["estimated_length"] = len(formatted_preview)
                validation_result["formatting_preview"] = (
                    formatted_preview[:200] + "..."
                    if len(formatted_preview) > 200
                    else formatted_preview
                )

                # Check if splitting will be needed
                if len(formatted_preview) > 4000:
                    validation_result["will_be_split"] = True
                    validation_result["warnings"].append(
                        f"Message is long ({len(formatted_preview)} chars) and will be split into multiple parts"
                    )

                    # Estimate number of parts
                    parts = self._split_long_message(formatted_preview)
                    validation_result["estimated_parts"] = len(parts)
                    validation_result["recommendations"].append(
                        f"Consider shortening content to avoid {len(parts)}-part message"
                    )

            except Exception as e:
                validation_result["warnings"].append(
                    f"Formatting preview failed: {str(e)}"
                )
                validation_result["estimated_length"] = (
                    len(message) + 200
                )  # Rough estimate

            # Content analysis
            if len(message) > 10000:
                validation_result["warnings"].append(
                    "Very long original content may cause processing delays"
                )

            # Check for potentially problematic patterns
            problematic_patterns = [
                (r"`{3,}", "Multiple code block markers detected"),
                (r"\*{3,}", "Multiple bold markers detected"),
                (r"_{3,}", "Multiple italic markers detected"),
                (r"https?://[^\s]{200,}", "Very long URLs detected"),
            ]

            for pattern, warning in problematic_patterns:
                if re.search(pattern, message):
                    validation_result["warnings"].append(warning)

            # Performance recommendations
            if validation_result["estimated_length"] > 2000:
                validation_result["recommendations"].append(
                    "Consider using bullet points or shorter paragraphs for better readability"
                )

            if len(validation_result["warnings"]) > 3:
                validation_result["recommendations"].append(
                    "Multiple formatting issues detected - consider simplifying message structure"
                )

        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Validation process failed: {str(e)}")

        return validation_result

    async def send_to_multiple_chats(
        self, chat_ids: List[str], message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """
        Backward compatibility wrapper - now uses enhanced formatting

        This method maintains the original interface while providing enhanced functionality
        """
        return await self.send_to_multiple_chats_enhanced(
            chat_ids, message, message_type
        )

    def preview_formatted_message(
        self, message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """
        Preview how a message will be formatted without sending it

        Args:
            message (str): Raw message content
            message_type (str): Type of message

        Returns:
            Dict[str, Any]: Preview information including formatted content
        """
        try:
            validation = self.validate_message_before_send(message, message_type)

            preview_info = {
                "original_message": message,
                "message_type": message_type,
                "validation": validation,
                "preview_available": True,
            }

            if validation["is_valid"] or validation["warnings"]:
                try:
                    formatted = self.format_message(message, message_type)
                    preview_info.update(
                        {
                            "formatted_message": formatted,
                            "character_count": len(formatted),
                            "will_be_split": len(formatted) > self.max_message_length,
                            "estimated_telegram_length": len(formatted.encode("utf-8")),
                        }
                    )

                    if preview_info["will_be_split"]:
                        parts = self._split_long_message(formatted)
                        preview_info.update(
                            {
                                "split_parts_count": len(parts),
                                "split_parts_preview": [
                                    part[:100] + "..." if len(part) > 100 else part
                                    for part in parts[:3]  # Show first 3 parts preview
                                ],
                            }
                        )

                except Exception as e:
                    preview_info.update(
                        {"formatting_error": str(e), "fallback_would_be_used": True}
                    )

            return preview_info

        except Exception as e:
            return {
                "original_message": message,
                "message_type": message_type,
                "preview_available": False,
                "error": f"Preview generation failed: {str(e)}",
            }

    def get_telegram_formatting_capabilities(self) -> Dict[str, Any]:
        """
        Get information about current Telegram formatting capabilities and limits

        Returns:
            Dict[str, Any]: Complete capability and configuration information
        """
        return {
            "telegram_limits": {
                "max_message_length": 4096,
                "configured_safe_limit": self.max_message_length,
                "max_caption_length": 1024,
                "max_inline_query_length": 256,
            },
            "formatting_features": {
                "markdown_support": True,
                "html_support": False,  # We focus on Markdown
                "automatic_escaping": True,
                "title_conversion": True,
                "message_splitting": self.enable_message_splitting,
                "fallback_modes": ["safe_escape", "plain_text", "emergency"],
            },
            "supported_markdown_elements": {
                "bold": "*text*",
                "italic": "_text_",
                "code": "`code`",
                "code_block": "```code```",
                "links": "[text](url)",
                "mentions": "@username",
            },
            "auto_converted_elements": {
                "h1_headers": "🔶 **Title**",
                "h2_headers": "    ▪️ **Subtitle**",
                "h3_headers": "      ▫️ **Subsubtitle**",
                "h4_plus": "        • *Item*",
            },
            "safety_features": {
                "special_character_escaping": True,
                "unmatched_markdown_detection": True,
                "length_validation": True,
                "encoding_validation": True,
                "emergency_fallback": True,
            },
            "performance_settings": {
                "max_concurrent_sends": self.max_concurrent_sends,
                "send_delay_seconds": self.send_delay,
                "retry_attempts": self.max_retries,
                "formatting_timeout": "No timeout set",
            },
            "current_configuration": {
                "fallback_mode": self.formatting_fallback_mode,
                "splitting_enabled": self.enable_message_splitting,
                "max_length": self.max_message_length,
                "statistics_tracking": True,
            },
        }

    async def send_to_group(
        self,
        message: str,
        group_ids: str,
        message_type: str = "signal",
    ) -> Dict[str, Any]:
        """Send message to specified group(s) or all configured groups"""
        if group_ids is not None:
            target_groups = [gid.strip() for gid in group_ids.split(",") if gid.strip()]
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
                    "retry_stats": {},
                }
            return await self.send_formatted_message_safely(
                target_groups, message, message_type
            )

    async def send_to_all_users(
        self, message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
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
                "retry_stats": {},
            }

        result = await self.send_formatted_message_safely(
            chat_ids, message, message_type
        )

        # Handle invalid chat IDs removal with permanent error detection
        if result["failed_chats"]:
            permanent_failures = result.get("permanent_failures", [])
            if permanent_failures:
                await self._cleanup_invalid_chat_ids(
                    permanent_failures, result["errors"]
                )

        # Update formatting statistics
        self._update_formatting_stats(result)

        return result

    def _update_formatting_stats(self, send_result: Dict[str, Any]):
        """
        Update internal formatting statistics

        Args:
            send_result (Dict[str, Any]): Result from message sending operation
        """
        try:
            self.formatting_stats["total_formatted"] += 1

            formatting_info = send_result.get("formatting_info", {})
            if formatting_info.get("status") == "success":
                self.formatting_stats["successful_formatting"] += 1
            elif formatting_info.get("status") == "fallback_used":
                self.formatting_stats["fallback_used"] += 1
            elif formatting_info.get("status") == "plain_text":
                self.formatting_stats["plain_text_used"] += 1

            if send_result.get("was_split", False):
                self.formatting_stats["messages_split"] += 1

            # Update average length (rolling average)
            if "formatted_length" in formatting_info:
                current_avg = self.formatting_stats["average_length"]
                total_count = self.formatting_stats["total_formatted"]
                new_length = formatting_info["formatted_length"]

                self.formatting_stats["average_length"] = (
                    current_avg * (total_count - 1) + new_length
                ) / total_count

        except Exception as e:
            self.logger.debug(f"Error updating formatting stats: {e}")

    def get_formatting_health_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive formatting health report

        Returns:
            Dict[str, Any]: Detailed formatting performance and health metrics
        """
        stats = self.formatting_stats.copy()
        total_messages = stats["total_formatted"]

        if total_messages == 0:
            return {
                "status": "no_data",
                "message": "No messages have been formatted yet",
                "timestamp": datetime.now().isoformat(),
            }

        # Calculate success rates
        success_rate = (stats["successful_formatting"] / total_messages) * 100
        fallback_rate = (stats["fallback_used"] / total_messages) * 100
        plain_text_rate = (stats["plain_text_used"] / total_messages) * 100
        split_rate = (stats["messages_split"] / total_messages) * 100

        # Determine overall health status
        if success_rate >= 95:
            health_status = "excellent"
        elif success_rate >= 90:
            health_status = "good"
        elif success_rate >= 80:
            health_status = "fair"
        elif success_rate >= 70:
            health_status = "poor"
        else:
            health_status = "critical"

        # Generate recommendations
        recommendations = []
        if fallback_rate > 10:
            recommendations.append(
                "High fallback usage detected - check message content quality"
            )
        if plain_text_rate > 5:
            recommendations.append(
                "Frequent plain text fallback - consider content formatting review"
            )
        if split_rate > 20:
            recommendations.append(
                "Many messages being split - consider shorter content guidelines"
            )
        if stats["average_length"] > 3000:
            recommendations.append(
                "Average message length is high - consider content optimization"
            )

        return {
            "status": health_status,
            "overall_metrics": {
                "total_messages_formatted": total_messages,
                "success_rate_percent": round(success_rate, 2),
                "average_message_length": round(stats["average_length"], 0),
                "uptime_hours": (datetime.now() - stats["last_reset"]).total_seconds()
                / 3600,
            },
            "formatting_breakdown": {
                "successful_formatting": {
                    "count": stats["successful_formatting"],
                    "percentage": round(success_rate, 2),
                },
                "fallback_used": {
                    "count": stats["fallback_used"],
                    "percentage": round(fallback_rate, 2),
                },
                "plain_text_fallback": {
                    "count": stats["plain_text_used"],
                    "percentage": round(plain_text_rate, 2),
                },
            },
            "message_handling": {
                "messages_split": {
                    "count": stats["messages_split"],
                    "percentage": round(split_rate, 2),
                },
                "average_length_chars": round(stats["average_length"], 0),
                "max_allowed_length": self.max_message_length,
            },
            "configuration": {
                "splitting_enabled": self.enable_message_splitting,
                "fallback_mode": self.formatting_fallback_mode,
                "max_message_length": self.max_message_length,
            },
            "recommendations": recommendations,
            "last_reset": stats["last_reset"].isoformat(),
            "timestamp": datetime.now().isoformat(),
        }

    def reset_formatting_stats(self):
        """
        Reset formatting statistics (useful for monitoring periods)
        """
        self.formatting_stats = {
            "total_formatted": 0,
            "successful_formatting": 0,
            "fallback_used": 0,
            "plain_text_used": 0,
            "messages_split": 0,
            "average_length": 0,
            "last_reset": datetime.now(),
        }
        self.logger.info("Formatting statistics reset")

    async def _cleanup_invalid_chat_ids(
        self, failed_chat_ids: List[str], errors: List[str]
    ):
        """Remove invalid chat IDs from storage based on permanent errors"""
        try:
            permanent_error_patterns = [
                "chat not found",
                "user not found",
                "bot was blocked",
                "bot was kicked",
                "user is deactivated",
                "chat is deactivated",
                "forbidden",
                "unauthorized",
                "permanent telegram error",
            ]

            chat_ids_to_remove = []
            for i, chat_id in enumerate(failed_chat_ids):
                if i < len(errors):
                    error = errors[i].lower()
                    if any(pattern in error for pattern in permanent_error_patterns):
                        chat_ids_to_remove.append(chat_id)
                        self.logger.debug(
                            f"Marking chat {chat_id} for removal due to: {error}"
                        )

            if chat_ids_to_remove:
                current_chat_ids = self.load_chat_ids()
                updated_chat_ids = [
                    cid for cid in current_chat_ids if cid not in chat_ids_to_remove
                ]

                # Backup before modification
                backup_data = {
                    "chat_ids": current_chat_ids,
                    "backup_timestamp": datetime.now().isoformat(),
                }
                backup_file = f"{self.chat_storage_file}.backup"
                with open(backup_file, "w") as f:
                    json.dump(backup_data, f)

                # Update main storage
                with open(self.chat_storage_file, "w") as f:
                    json.dump({"chat_ids": updated_chat_ids}, f)

                self.logger.info(
                    f"Removed {len(chat_ids_to_remove)} invalid chat IDs: {chat_ids_to_remove}"
                )
                self.logger.debug(f"Backup created at {backup_file}")

        except Exception as e:
            self.logger.error(f"Failed to cleanup invalid chat IDs: {e}")

    def setup_bot_handlers(self):
        """Setup bot handlers"""
        self.application = Application.builder().token(self.bot_token).build()

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Add callback query handler for buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Add new member handler
        self.application.add_handler(
            MessageHandler(
                filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_chat_members
            )
        )

        # 修改：添加私聊消息处理器
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE & (~filters.COMMAND),
                self.handle_private_message,
            )
        )

        # Add message handler for mentions and replies in groups
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.GROUPS & (~filters.COMMAND),
                self.handle_mention,
            )
        )

    def cleanup_expired_threads(self):
        """Clean up expired user threads (定期调用)"""
        with self.thread_lock:
            expired_users = []
            for user_id, thread_info in self.user_threads.items():
                if self._is_thread_expired(thread_info):
                    expired_users.append(user_id)

            for user_id in expired_users:
                self._cleanup_user_thread(user_id)

            if expired_users:
                self.logger.info(
                    f"Cleaned up {len(expired_users)} expired chat threads"
                )

    def get_chat_stats(self) -> Dict[str, Any]:
        """Get chat usage statistics"""
        with self.thread_lock:
            active_threads = len(self.user_threads)

        subscribed_users = len(self.load_chat_ids())

        return {
            "langgraph_chat_enabled": self.enable_langgraph_chat,
            "active_chat_threads": active_threads,
            "subscribed_users": subscribed_users,
            "thread_details": (
                {
                    user_id: {
                        "thread_id": info["thread_id"],
                        "created_at": info["created_at"].isoformat(),
                        "age_hours": round(
                            (datetime.now() - info["created_at"]).total_seconds()
                            / 3600,
                            2,
                        ),
                    }
                    for user_id, info in self.user_threads.items()
                }
                if len(self.user_threads) < 20
                else {"note": f"Too many threads to display ({len(self.user_threads)})"}
            ),
        }

    async def start_bot(self):
        """Start the bot in background"""
        if not self.application:
            self.setup_bot_handlers()

        self.logger.info("Starting Telegram bot...")

        # Start the application in background
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        self.logger.info("Telegram bot started successfully")

    async def stop_bot(self):
        """Stop the bot gracefully"""
        if self.application and self.application.updater:
            self.logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.logger.info("Telegram bot stopped successfully")

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the Telegram service"""
        try:
            me = await self.bot.get_me()
            bot_info = {
                "username": me.username,
                "first_name": me.first_name,
                "id": me.id,
            }

            user_chat_count = len(self.load_chat_ids())

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
                    "retry_jitter": self.retry_jitter,
                },
                "chat_counts": {
                    "subscribed_users": user_chat_count,
                    "total_chats": user_chat_count,
                },
                "retry_capabilities": {
                    "retryable_error_types": list(self.retryable_errors),
                    "permanent_error_types": list(self.permanent_errors),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.info(f"Health check passed - Bot: @{me.username}, ")
            return health_status

        except Exception as e:
            error_status = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self.logger.error(f"Health check failed: {e}")
            return error_status

    # Legacy compatibility methods
    async def broadcast_signal(
        self, message: str, parse_mode: str = "Markdown"
    ) -> Dict[str, Any]:
        """Legacy method for backward compatibility - sends to all users"""
        # Convert to new format
        result = await self.send_to_all_users(message, "signal")

        # Convert response format for backward compatibility
        return {
            "successful": result.get("success_count", 0),
            "failed": result.get("failed_count", 0),
        }

    async def add_chat_id(self, chat_id: str) -> bool:
        """Add new chat ID to storage"""
        try:
            chat_ids = self.load_chat_ids()
            if chat_id not in chat_ids:
                chat_ids.append(chat_id)
                success = self.save_chat_ids(chat_ids)
                if success:
                    self.logger.info(f"Added new chat_id: {chat_id}")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to add chat_id {chat_id}: {e}")
            return False

    async def remove_chat_id(self, chat_id: str):
        """Remove invalid chat ID from storage"""
        try:
            chat_ids = self.load_chat_ids()
            if chat_id in chat_ids:
                chat_ids.remove(chat_id)
                self.save_chat_ids(chat_ids)
                self.logger.info(f"Removed invalid chat_id: {chat_id}")
        except Exception as e:
            self.logger.error(f"Failed to remove chat_id {chat_id}: {e}")

    def get_retry_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current retry configuration"""
        return {
            "retry_settings": {
                "max_retries": self.max_retries,
                "initial_retry_delay_seconds": self.initial_retry_delay,
                "backoff_factor": self.retry_backoff_factor,
                "max_retry_delay_seconds": self.max_retry_delay,
                "jitter_enabled": self.retry_jitter,
            },
            "concurrency_settings": {
                "max_concurrent_sends": self.max_concurrent_sends,
                "send_delay_seconds": self.send_delay,
            },
            "error_classification": {
                "retryable_errors": sorted(list(self.retryable_errors)),
                "permanent_errors": sorted(list(self.permanent_errors)),
            },
            "estimated_scenarios": {
                "single_retry_delay": f"{self.initial_retry_delay}s",
                "max_total_delay": f"{self._calculate_max_total_delay()}s",
                "theoretical_max_attempts": self.max_retries + 1,
            },
        }

    def _calculate_max_total_delay(self) -> float:
        """Calculate theoretical maximum total delay for all retries"""
        total_delay = 0
        for attempt in range(self.max_retries):
            delay = self.initial_retry_delay * (self.retry_backoff_factor**attempt)
            delay = min(delay, self.max_retry_delay)
            total_delay += delay
        return round(total_delay, 2)


# Standalone function to run bot (for backward compatibility)
def run_telegram_bot(bot_token: str):
    """Run the telegram bot standalone"""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    bot = EnhancedTelegramBotService(bot_token)
    bot.setup_bot_handlers()

    try:
        bot.application.run_polling()
    except KeyboardInterrupt:
        print("Bot stopped by user")


def main():
    """Main function to run the subscription bot"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is required")
        return

    run_telegram_bot(bot_token)


if __name__ == "__main__":
    main()
