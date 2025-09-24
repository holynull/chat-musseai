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

        # Load group chat IDs
        self.group_chat_ids = self._load_group_chat_ids()
        self.group_chat_id = self.group_chat_ids[0] if self.group_chat_ids else None

        if self.group_chat_ids:
            self.logger.info(f"Group chat IDs configured: {self.group_chat_ids}")
        else:
            self.logger.warning(
                "No group chat IDs configured, group messaging disabled"
            )

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

    def _load_group_chat_ids(self) -> List[str]:
        """Load group chat IDs from environment variables"""
        group_ids_str = os.getenv("TELEGRAM_GROUP_CHAT_IDS")
        if group_ids_str:
            try:
                group_ids = [
                    gid.strip() for gid in group_ids_str.split(",") if gid.strip()
                ]
                return group_ids
            except Exception as e:
                self.logger.error(f"Failed to parse TELEGRAM_GROUP_CHAT_IDS: {e}")

        single_group_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")
        if single_group_id:
            return [single_group_id.strip()]

        return []

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
                # 提取用户消息内容（移除机器人提及部分）
                clean_message = self._clean_mention_text(message_text, bot_username)

                if clean_message.strip():
                    # 通过 LangGraph 处理消息
                    response = await self.process_message_with_langgraph(
                        clean_message, user_id
                    )
                    response = self._convert_markdown_titles(response)

                    if response:
                        await update.message.reply_text(
                            response,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                        self.logger.info(
                            f"Responded to user {user_id} via LangGraph in group"
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

    def _convert_markdown_titles(self, text: str) -> str:
        """Convert Markdown titles with multi-level indentation support"""
        import re

        # Convert ### (h3) to bold format with more indentation
        text = re.sub(r"^###\\s+(.+)$", r"      ▫ *\\1*", text, flags=re.MULTILINE)

        # Convert ## (h2) to bold format with indentation
        text = re.sub(r"^##\\s+(.+)$", r"    ▪ *\\1*", text, flags=re.MULTILINE)

        # Convert # (h1) to bold format
        text = re.sub(r"^#\\s+(.+)$", r"🔶 *\\1*", text, flags=re.MULTILINE)

        return text

    def format_message(self, text: str, message_type: str) -> str:
        """Format message with appropriate template"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
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

    async def send_to_multiple_chats(
        self, chat_ids: List[str], message: str, message_type: str = "signal"
    ) -> Dict[str, Any]:
        """Send message to multiple chats concurrently with retry mechanism"""
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
            }

        formatted_message = self.format_message(message, message_type)

        self.logger.info(
            f"Sending {message_type} message to {len(chat_ids)} chats with retry mechanism"
        )
        start_time = time.time()

        semaphore = asyncio.Semaphore(self.max_concurrent_sends)

        tasks = [
            self._send_single_message_with_retry(chat_id, formatted_message, semaphore)
            for chat_id in chat_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
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

        # Log results
        if success:
            if failed_chats:
                success_rate = (len(sent_chats) / len(chat_ids)) * 100
                self.logger.warning(
                    f"Partially successful: {len(sent_chats)}/{len(chat_ids)} chats "
                    f"({success_rate:.1f}% success rate) in {total_duration:.2f}s"
                )
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(
                        f"Retry mechanism recovered {retry_stats['successful_retries']} failures"
                    )
            else:
                self.logger.info(
                    f"Successfully sent {message_type} message to all {len(sent_chats)} chats "
                    f"in {total_duration:.2f}s"
                )
                if retry_stats["successful_retries"] > 0:
                    self.logger.info(
                        f"Retry mechanism recovered {retry_stats['successful_retries']} temporary failures"
                    )
        else:
            self.logger.error(
                f"Failed to send {message_type} message to any chats "
                f"({retry_stats['permanent_errors']} permanent, "
                f"{retry_stats['failed_after_retries']} exhausted retries)"
            )

        return response

    async def send_to_group(
        self,
        message: str,
        message_type: str = "signal",
        group_ids: Optional[str] = None,
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
        else:
            target_groups = self.group_chat_ids if self.group_chat_ids else []

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
                "retry_stats": {},
            }

        return await self.send_to_multiple_chats(target_groups, message, message_type)

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

        result = await self.send_to_multiple_chats(chat_ids, message, message_type)

        # Handle invalid chat IDs removal with permanent error detection
        if result["failed_chats"]:
            permanent_failures = result.get("permanent_failures", [])
            if permanent_failures:
                await self._cleanup_invalid_chat_ids(
                    permanent_failures, result["errors"]
                )

        return result

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
            "configured_groups": len(self.group_chat_ids) if self.group_chat_ids else 0,
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
                    "retry_jitter": self.retry_jitter,
                },
                "chat_counts": {
                    "subscribed_users": user_chat_count,
                    "configured_groups": group_chat_count,
                    "total_chats": user_chat_count + group_chat_count,
                },
                "retry_capabilities": {
                    "retryable_error_types": list(self.retryable_errors),
                    "permanent_error_types": list(self.permanent_errors),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.info(
                f"Health check passed - Bot: @{me.username}, "
                f"Users: {user_chat_count}, Groups: {group_chat_count}"
            )
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
