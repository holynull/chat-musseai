import asyncio
import logging
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError
from langgraph_sdk import get_client, get_sync_client

# Add telegramify-markdown import for converting to Telegram MarkdownV2
import telegramify_markdown
from telegramify_markdown import customize

from swap_bot_loggers import setup_swap_bot_logger

# Configure telegramify-markdown for optimal Telegram compatibility
customize.strict_markdown = False


class SwapTelegramBotService:
    """Simplified Telegram bot service focused on natural language conversation with swap functionality"""

    def __init__(self, bot_token: str, user_storage_file: str = "swap_bot_users.json"):
        self.bot_token = bot_token
        self.user_storage_file = user_storage_file
        self.logger = setup_swap_bot_logger()
        self.bot = Bot(token=bot_token)
        self.application = None

        # Rate limiting - reduced cooldown for better conversation flow
        self.last_interaction = {}
        self.interaction_cooldown = 3  # 3 seconds cooldown for natural conversation

        # Connection configuration
        self.max_connections = int(os.getenv("TELEGRAM_MAX_CONNECTIONS", "20"))
        self.pool_timeout = float(os.getenv("TELEGRAM_POOL_TIMEOUT", "30.0"))
        self.connection_timeout = float(
            os.getenv("TELEGRAM_CONNECTION_TIMEOUT", "20.0")
        )

        # LangGraph configuration - using graph_swap_v2
        self.langgraph_server_url = os.getenv("LANGGRAPH_SERVER_URL")
        self.swap_graph_name = os.getenv("SWAP_GRAPH_NAME", "graph_swap_v2")
        self.enable_swap_chat = os.getenv("ENABLE_SWAP_CHAT", "true").lower() == "true"

        # LangGraph clients
        self.async_client = None
        self.sync_client = None

        # User session management for swap workflows
        self.user_sessions = (
            {}
        )  # {user_id: {thread_id: str, run_id: str, state: str, created_at: datetime}}
        self.session_lock = threading.Lock()

        # User interrupt handling state
        self.user_interrupts = {}  # {user_id: {run_id: str, interrupt_data: dict}}

        if self.enable_swap_chat and self.langgraph_server_url:
            self.setup_langgraph_client()

    def setup_langgraph_client(self):
        """Initialize LangGraph clients for swap processing"""
        try:
            self.async_client = get_client(url=self.langgraph_server_url)
            self.sync_client = get_sync_client(url=self.langgraph_server_url)
            self.logger.info("LangGraph clients initialized for swap processing")
        except Exception as e:
            self.logger.error(f"Failed to initialize LangGraph clients: {e}")
            self.enable_swap_chat = False

    def load_user_ids(self) -> List[str]:
        """Load user IDs from storage"""
        try:
            if os.path.exists(self.user_storage_file):
                with open(self.user_storage_file, "r") as f:
                    data = json.load(f)
                    return data.get("user_ids", [])
            return []
        except Exception as e:
            self.logger.error(f"Failed to load user IDs: {e}")
            return []

    def save_user_ids(self, user_ids: List[str]) -> bool:
        """Save user IDs to storage"""
        try:
            with open(self.user_storage_file, "w") as f:
                json.dump({"user_ids": user_ids}, f)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save user IDs: {e}")
            return False

    def is_rate_limited(self, user_id: str) -> bool:
        """Check if user is rate limited"""
        current_time = time.time()
        last_time = self.last_interaction.get(user_id, 0)

        if current_time - last_time < self.interaction_cooldown:
            return True

        self.last_interaction[user_id] = current_time
        return False

    def get_or_create_user_session(self, user_id: str) -> str:
        """Get existing session or create new one for user"""
        with self.session_lock:
            if user_id in self.user_sessions:
                session_info = self.user_sessions[user_id]
                # Check if session is expired (2 hours for swap operations)
                if self._is_session_expired(session_info):
                    self._cleanup_user_session(user_id)
                else:
                    return session_info["thread_id"]

            # Create new session
            return self._create_user_session(user_id)

    def _create_user_session(self, user_id: str) -> str:
        """Create new session for user"""
        try:
            thread = self.sync_client.threads.create(
                metadata={"user_id": user_id, "session_type": "swap_chat"}
            )
            thread_id = thread["thread_id"]

            self.user_sessions[user_id] = {
                "thread_id": thread_id,
                "run_id": None,
                "state": "idle",
                "created_at": datetime.now(),
            }

            self.logger.info(
                f"Created new swap session for user {user_id}: {thread_id}"
            )
            return thread_id

        except Exception as e:
            self.logger.error(f"Failed to create session for user {user_id}: {e}")
            raise

    def _is_session_expired(self, session_info: dict) -> bool:
        """Check if session is expired (2 hours)"""
        age = datetime.now() - session_info["created_at"]
        return age.total_seconds() > 2 * 3600  # 2 hours

    def _cleanup_user_session(self, user_id: str):
        """Cleanup expired user session"""
        if user_id in self.user_sessions:
            session_info = self.user_sessions[user_id]
            try:
                if hasattr(self.sync_client.threads, "delete"):
                    self.sync_client.threads.delete(thread_id=session_info["thread_id"])
            except Exception as e:
                self.logger.warning(
                    f"Failed to delete thread {session_info['thread_id']}: {e}"
                )

            del self.user_sessions[user_id]
            # Also cleanup any pending interrupts
            if user_id in self.user_interrupts:
                del self.user_interrupts[user_id]
            self.logger.info(f"Cleaned up expired session for user {user_id}")

    async def process_message_with_swap_graph(
        self, user_message: str, user_id: str, update: Update
    ) -> str:
        """Process user message through swap graph and handle interrupts"""
        if not self.enable_swap_chat or not self.async_client:
            return "Sorry, swap functionality is currently unavailable."

        try:
            # Get or create user session
            thread_id = self.get_or_create_user_session(user_id)

            # Check if user has pending interrupts to respond to
            if user_id in self.user_interrupts:
                return await self._handle_user_interrupt_response(
                    user_message, user_id, update
                )

            # Prepare input data for swap graph
            input_data = {
                "messages": [{"type": "human", "content": user_message}],
            }

            self.logger.info(
                f"Processing swap message for user {user_id} using thread {thread_id}"
            )

            # Update user session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "processing"

            # Execute through swap graph with interrupt handling
            response_content = None
            run_id = None

            chunks = self.async_client.runs.stream(
                thread_id=thread_id,
                assistant_id=self.swap_graph_name,
                input=input_data,
                stream_mode="events",
                config={"recursion_limit": 50},
                # interrupt_before=[
                #     "node_swap_1_generate_wallet",
                #     "node_swap_2_check_token_transfer_configurations",
                # ],
            )

            async for chunk in chunks:
                chunk_data = chunk.data
                chunk_event = chunk.event
                event = chunk_data.get("event")
                if chunk_event == "values" and chunk_data.get("__interrupt__"):
                    # Handle interrupts
                    # Check if this is an interrupt
                    self.logger.warning("Thread interrupted.")
                    return await self._handle_graph_interrupt(
                        chunk_data, user_id, update
                    )
                # Track run ID
                if (
                    event == "on_chain_start"
                    and chunk_data.get("name", "") == "graph_swap_v2"
                    and not run_id
                ):
                    if not run_id:
                        run_id = chunk_data.get("run_id")
                        with self.session_lock:
                            if user_id in self.user_sessions:
                                self.user_sessions[user_id]["run_id"] = run_id

                if (
                    event == "on_chain_end"
                    and chunk_data.get("name", "") == "graph_swap_v2"
                    and chunk_data.get("run_id") == run_id
                ):
                    # Extract normal response
                    response_content = self._parse_last_ai_content(
                        chunk_data.get("data")
                    )

            # Update session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "idle"

            if not response_content:
                return "I'm ready to help you with cryptocurrency swaps! Just tell me what you'd like to exchange."

            return response_content

        except Exception as e:
            self.logger.error(f"Error processing swap message for user {user_id}: {e}")
            # Reset user state on error
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "idle"
                if user_id in self.user_interrupts:
                    del self.user_interrupts[user_id]
            return (
                "Sorry, there was an error processing your request. Please try again."
            )

    async def _handle_graph_interrupt(
        self, chunk_data: dict, user_id: str, update: Update
    ) -> str:
        """Handle interrupts from the swap graph"""
        try:
            # Extract interrupt information
            interrupt_data = chunk_data.get("__interrupt__", [])
            interrupt_value = (
                interrupt_data[0].get("value") if len(interrupt_data) > 0 else {}
            )
            run_id = chunk_data.get("run_id")

            # Store interrupt state for user
            self.user_interrupts[user_id] = {
                "run_id": run_id,
                "interrupt_data": interrupt_data,
                "timestamp": datetime.now(),
            }

            # Update session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "waiting_for_input"

            # Determine interrupt type and create appropriate response
            event_type = interrupt_value.get("event", "unknown")

            if event_type == "waiting_for_token_transfer":
                return await self._handle_token_transfer_interrupt(
                    interrupt_value, user_id, update
                )
            elif event_type == "waiting_for_token_transfer_configuration":
                return await self._handle_configuration_interrupt(
                    interrupt_value, user_id, update
                )
            else:
                return f"Please provide additional information to continue with your swap request."

        except Exception as e:
            self.logger.error(f"Error handling graph interrupt for user {user_id}: {e}")
            return "There was an issue processing your request. Please try again."

    async def _handle_token_transfer_interrupt(
        self, interrupt_value: dict, user_id: str, update: Update
    ) -> str:
        """Handle token transfer interrupt"""
        try:
            data = interrupt_value.get("data", {})
            address = data.get("address", "")
            symbol_amounts = data.get("symbol_amount", [])
            text = interrupt_value.get("text", "")

            # Format the transfer requirements message
            transfer_msg = f"🔄 **Token Transfer Required**\n\n"
            transfer_msg += f"📍 **Transfer Address:** `{address}`\n\n"
            transfer_msg += "💰 **Required Amounts:**\n"

            for item in symbol_amounts:
                symbol = item.get("symbol", "")
                amount = item.get("amount", "")
                description = item.get("description", "")
                if description:
                    transfer_msg += f"• {amount} {symbol} ({description})\n"
                else:
                    transfer_msg += f"• {amount} {symbol}\n"

            transfer_msg += f"\n⏱️ **Time limit:** 3 minutes\n\n"
            transfer_msg += "Please complete the transfer and then send me the transaction hash(es) or confirm when done."

            return transfer_msg

        except Exception as e:
            self.logger.error(f"Error handling token transfer interrupt: {e}")
            return "Please transfer the required tokens and send me the transaction hash when complete."

    async def _handle_configuration_interrupt(
        self, interrupt_value: dict, user_id: str, update: Update
    ) -> str:
        """Handle configuration wait interrupt"""
        try:
            text = interrupt_value.get("text", "")
            data = interrupt_value.get("data", {})

            # Check transaction confirmations
            transfer_txs = data.get("transfer_tx", [])
            if transfer_txs:
                confirmation_msg = "⏳ **Waiting for Transaction Confirmations**\n\n"
                confirmation_msg += "📋 **Transaction Status:**\n"

                for i, tx in enumerate(transfer_txs, 1):
                    confirmations = tx.get("configurations", 0)
                    tx_hash = tx.get("hash", f"Transaction {i}")
                    confirmation_msg += (
                        f"• {tx_hash}: {confirmations}/5 confirmations\n"
                    )

                confirmation_msg += "\n🔄 I'm monitoring the blockchain for confirmations. This usually takes a few minutes.\n"
                confirmation_msg += "You don't need to do anything - I'll continue automatically once we have enough confirmations."

                return confirmation_msg

            return (
                text
                or "⏳ Waiting for blockchain confirmations. This may take a few minutes..."
            )

        except Exception as e:
            self.logger.error(f"Error handling configuration interrupt: {e}")
            return "⏳ Processing your transaction. Please wait for confirmations..."

    async def _handle_user_interrupt_response(
        self, user_message: str, user_id: str, update: Update
    ) -> str:
        """Handle user response to an interrupt"""
        try:
            if user_id not in self.user_interrupts:
                return "I don't have any pending requests from you. How can I help you with a swap?"

            interrupt_info = self.user_interrupts[user_id]
            run_id = interrupt_info["run_id"]
            interrupt_data = interrupt_info["interrupt_data"]

            # Parse user response based on interrupt type
            event_type = interrupt_data.get("interrupt_value", {}).get("event", "")

            if event_type == "waiting_for_token_transfer":
                return await self._process_transfer_response(
                    user_message, user_id, run_id, update
                )
            elif event_type == "waiting_for_token_transfer_configuration":
                return await self._process_configuration_response(
                    user_message, user_id, run_id, update
                )
            else:
                return await self._process_generic_interrupt_response(
                    user_message, user_id, run_id, update
                )

        except Exception as e:
            self.logger.error(f"Error handling user interrupt response: {e}")
            # Clear interrupt state on error
            if user_id in self.user_interrupts:
                del self.user_interrupts[user_id]
            return "There was an error processing your response. Please start a new swap request."

    async def _process_transfer_response(
        self, user_message: str, user_id: str, run_id: str, update: Update
    ) -> str:
        """Process user response to transfer interrupt"""
        try:
            # Parse transaction hashes from user message
            import re

            tx_hash_pattern = r"0x[a-fA-F0-9]{64}"
            tx_hashes = re.findall(tx_hash_pattern, user_message)

            # Prepare response for graph
            if tx_hashes:
                # User provided transaction hashes
                response_data = {
                    "txs": [
                        {"hash": tx_hash, "configurations": 0} for tx_hash in tx_hashes
                    ]
                }
            elif any(
                word in user_message.lower()
                for word in ["done", "complete", "finished", "sent", "transferred"]
            ):
                # User indicates transfer is complete but didn't provide hash
                response_data = {
                    "txs": [{"hash": "pending_verification", "configurations": 0}]
                }
            else:
                # User message doesn't contain clear transaction info
                return "Please provide the transaction hash(es) from your transfer, or confirm that you've completed the transfer."

            # Continue the graph execution with user response
            await self._continue_graph_execution(run_id, response_data, user_id)

            # Clear interrupt state
            del self.user_interrupts[user_id]

            return "✅ Transaction received! I'm now checking the blockchain for confirmations. This may take a few minutes..."

        except Exception as e:
            self.logger.error(f"Error processing transfer response: {e}")
            return "There was an error processing your transaction information. Please try again."

    async def _process_configuration_response(
        self, user_message: str, user_id: str, run_id: str, update: Update
    ) -> str:
        """Process user response to configuration interrupt"""
        try:
            # For configuration waits, usually we just continue automatically
            # User doesn't need to provide input, but we acknowledge their message

            if "cancel" in user_message.lower():
                # User wants to cancel
                await self._cancel_graph_execution(run_id, user_id)
                del self.user_interrupts[user_id]
                return (
                    "❌ Swap cancelled. Let me know if you'd like to start a new swap."
                )

            # Continue waiting for confirmations
            await self._continue_graph_execution(run_id, "Done", user_id)
            del self.user_interrupts[user_id]

            return "✅ Continuing with your swap. Processing the exchange now..."

        except Exception as e:
            self.logger.error(f"Error processing configuration response: {e}")
            return "Continuing to wait for confirmations..."

    async def _process_generic_interrupt_response(
        self, user_message: str, user_id: str, run_id: str, update: Update
    ) -> str:
        """Process generic interrupt response"""
        try:
            # Continue with user's response
            await self._continue_graph_execution(run_id, user_message, user_id)
            del self.user_interrupts[user_id]

            return "Processing your response..."

        except Exception as e:
            self.logger.error(f"Error processing generic interrupt response: {e}")
            return "There was an error processing your response. Please try again."

    async def _continue_graph_execution(
        self, run_id: str, response_data: Any, user_id: str
    ):
        """Continue graph execution with user response"""
        try:
            # Resume the graph execution with user's response
            await self.async_client.runs.update(run_id=run_id, resume=response_data)

            # Update session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "processing"

        except Exception as e:
            self.logger.error(f"Error continuing graph execution: {e}")
            raise

    async def _cancel_graph_execution(self, run_id: str, user_id: str):
        """Cancel graph execution"""
        try:
            await self.async_client.runs.cancel(run_id=run_id)

            # Update session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "idle"

        except Exception as e:
            self.logger.error(f"Error cancelling graph execution: {e}")

    def _parse_last_ai_content(self, data: dict) -> str:
        """Parse the last AI message content from response data"""
        try:
            output = data.get("output", {})
            messages = output.get("messages", [])

            if len(messages) == 0:
                return None

            # Find the last AI message
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("type") == "ai":
                    content = message.get("content")

                    if isinstance(content, str):
                        return content
                    elif isinstance(content, list) and len(content) > 0:
                        if isinstance(content[0], dict):
                            return content[0].get("text", "")
                        return str(content[0])

            return None

        except Exception as e:
            self.logger.error(f"Error parsing AI content: {e}")
            return None

    def convert_markdown_to_telegram_markdown(self, markdown_text: str) -> str:
        """Convert standard Markdown to Telegram-friendly MarkdownV2 format"""
        try:
            # Use telegramify-markdown for conversion
            converted_markdown = telegramify_markdown.markdownify(
                markdown_text,
                max_line_length=None,
                normalize_whitespace=True,
            )
            return converted_markdown

        except Exception as e:
            self.logger.warning(f"Markdown conversion failed: {e}, using plain text")
            return self._convert_to_plain_text(markdown_text)

    def _convert_to_plain_text(self, formatted_text: str) -> str:
        """Convert formatted text to plain text"""
        import re

        # Remove markdown formatting
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", formatted_text)  # Bold
        text = re.sub(r"\*([^*]+)\*", r"\1", text)  # Italic
        text = re.sub(r"`([^`]+)`", r"\1", text)  # Code
        text = re.sub(r"#{1,6}\s*([^\n]+)", r"\1", text)  # Headers

        return text.strip()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all non-command messages"""
        try:
            user_id = str(update.effective_user.id)
            message_text = update.message.text or ""
            chat_type = update.effective_chat.type

            # Skip empty messages
            if not message_text.strip():
                return

            # Rate limiting check
            if self.is_rate_limited(user_id):
                await update.message.reply_text(
                    "Please wait a moment before sending another message.",
                    parse_mode="Markdown",
                )
                return

            # Add user to storage if not exists
            user_ids = self.load_user_ids()
            if user_id not in user_ids:
                user_ids.append(user_id)
                self.save_user_ids(user_ids)
                self.logger.info(f"New user added: {user_id}")

            # Check if swap chat is enabled
            if not self.enable_swap_chat:
                await update.message.reply_text(
                    "👋 Hello! I'm a crypto swap assistant. Swap functionality is currently being set up. Please try again later.",
                    parse_mode="Markdown",
                )
                return

            # Send typing indicator
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action="typing"
            )

            # Process message through swap graph
            response = await self.process_message_with_swap_graph(
                message_text, user_id, update
            )

            if response:
                # Convert to Telegram markdown and send
                try:
                    formatted_response = self.convert_markdown_to_telegram_markdown(
                        response
                    )
                    await update.message.reply_text(
                        formatted_response,
                        parse_mode="MarkdownV2",
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Markdown formatting failed: {e}, sending as plain text"
                    )
                    plain_response = self._convert_to_plain_text(response)
                    await update.message.reply_text(plain_response)
            else:
                await update.message.reply_text(
                    "I'm here to help you with cryptocurrency swaps! What would you like to exchange?",
                    parse_mode="Markdown",
                )

            self.logger.info(f"Processed message from user {user_id} in {chat_type}")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            await update.message.reply_text(
                "Sorry, there was an error processing your message. Please try again.",
                parse_mode="Markdown",
            )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = str(update.effective_user.id)
            user_name = update.effective_user.first_name or "there"

            # Add user to storage
            user_ids = self.load_user_ids()
            if user_id not in user_ids:
                user_ids.append(user_id)
                self.save_user_ids(user_ids)

            welcome_text = f"""👋 **Hello {user_name}!**

🔄 I'm your crypto swap assistant! I can help you:

💱 **Exchange cryptocurrencies** - Just tell me what you want to swap
🔍 **Check prices and rates** - Ask about current market prices  
📊 **Get swap quotes** - I'll find the best rates for you
⚡ **Complete transactions** - I'll guide you through the entire process

**How to use:**
Simply send me a message like:
• "I want to swap 100 USDT to BNB"
• "What's the current ETH price?"
• "How much BTC can I get for 1000 USDC?"

Let's start! What would you like to swap today? 🚀"""

            formatted_text = self.convert_markdown_to_telegram_markdown(welcome_text)
            await update.message.reply_text(formatted_text, parse_mode="MarkdownV2")

            self.logger.info(f"User {user_id} started the bot")

        except Exception as e:
            self.logger.error(f"Error handling start command: {e}")
            await update.message.reply_text(
                "Welcome! I'm here to help you with crypto swaps. What would you like to exchange?",
                parse_mode="Markdown",
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            help_text = """🤖 **Crypto Swap Assistant Help**

**What I can do:**
🔄 Help you swap cryptocurrencies
💰 Provide real-time price quotes
📊 Find the best exchange rates
⚡ Guide you through transactions
🔍 Answer crypto-related questions

**How to interact:**
Just send me natural language messages like:
• "Swap 500 USDT to ETH"
• "What's the BTC price?"
• "I need to exchange DAI for BNB"
• "Show me swap options for 1000 USDC"

**During swaps:**
• I'll ask for token transfers when needed
• Send me transaction hashes when requested
• I'll monitor confirmations automatically
• You can cancel anytime by saying "cancel"

**Commands:**
/start - Start over
/help - Show this help
/status - Check your current session
/cancel - Cancel any ongoing swap

Need help? Just ask me anything! 💬"""

            formatted_text = self.convert_markdown_to_telegram_markdown(help_text)
            await update.message.reply_text(formatted_text, parse_mode="MarkdownV2")

        except Exception as e:
            self.logger.error(f"Error handling help command: {e}")
            await update.message.reply_text(
                "I'm here to help you swap cryptocurrencies! Just tell me what you'd like to exchange.",
                parse_mode="Markdown",
            )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            user_id = str(update.effective_user.id)

            # Check user session status
            session_status = "No active session"
            if user_id in self.user_sessions:
                session_info = self.user_sessions[user_id]
                state = session_info.get("state", "unknown")
                created_at = session_info.get("created_at")

                if created_at:
                    age = datetime.now() - created_at
                    age_minutes = int(age.total_seconds() / 60)
                    session_status = (
                        f"Active session ({state}) - {age_minutes} minutes old"
                    )

            # Check interrupt status
            interrupt_status = "No pending operations"
            if user_id in self.user_interrupts:
                interrupt_info = self.user_interrupts[user_id]
                event_type = (
                    interrupt_info.get("interrupt_data", {})
                    .get("interrupt_value", {})
                    .get("event", "unknown")
                )
                interrupt_status = f"Waiting for user input: {event_type}"

            status_text = f"""📊 **Your Session Status**

🔄 **Session:** {session_status}
⏳ **Current State:** {interrupt_status}

💡 **Tip:** You can start a new swap anytime by just telling me what you want to exchange!"""

            formatted_text = self.convert_markdown_to_telegram_markdown(status_text)
            await update.message.reply_text(formatted_text, parse_mode="MarkdownV2")

        except Exception as e:
            self.logger.error(f"Error handling status command: {e}")
            await update.message.reply_text(
                "Session status: Ready for new swaps!", parse_mode="Markdown"
            )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        try:
            user_id = str(update.effective_user.id)

            # Cancel any pending operations
            cancelled_something = False

            # Cancel running graph execution
            if user_id in self.user_sessions:
                session_info = self.user_sessions[user_id]
                run_id = session_info.get("run_id")
                if run_id and session_info.get("state") != "idle":
                    try:
                        await self._cancel_graph_execution(run_id, user_id)
                        cancelled_something = True
                    except Exception as e:
                        self.logger.warning(f"Could not cancel run {run_id}: {e}")

            # Clear interrupt state
            if user_id in self.user_interrupts:
                del self.user_interrupts[user_id]
                cancelled_something = True

            # Reset session state
            with self.session_lock:
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["state"] = "idle"
                    self.user_sessions[user_id]["run_id"] = None

            if cancelled_something:
                response_text = """❌ **Operation Cancelled**

All pending operations have been cancelled. You can start a new swap anytime!

What would you like to do next? 🚀"""
            else:
                response_text = """✅ **Nothing to Cancel**

You don't have any active operations running. 

Ready to help with a new swap - just tell me what you'd like to exchange! 💱"""

            formatted_text = self.convert_markdown_to_telegram_markdown(response_text)
            await update.message.reply_text(formatted_text, parse_mode="MarkdownV2")

        except Exception as e:
            self.logger.error(f"Error handling cancel command: {e}")
            await update.message.reply_text(
                "Operations cancelled. Ready for new requests!", parse_mode="Markdown"
            )

    def cleanup_expired_sessions(self):
        """Clean up expired user sessions (call periodically)"""
        with self.session_lock:
            expired_users = []
            for user_id, session_info in self.user_sessions.items():
                if self._is_session_expired(session_info):
                    expired_users.append(user_id)

            for user_id in expired_users:
                self._cleanup_user_session(user_id)

            if expired_users:
                self.logger.info(f"Cleaned up {len(expired_users)} expired sessions")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session usage statistics"""
        with self.session_lock:
            active_sessions = len(self.user_sessions)
            pending_interrupts = len(self.user_interrupts)

        total_users = len(self.load_user_ids())

        return {
            "swap_chat_enabled": self.enable_swap_chat,
            "active_sessions": active_sessions,
            "pending_interrupts": pending_interrupts,
            "total_users": total_users,
            "session_details": (
                {
                    user_id: {
                        "thread_id": info["thread_id"],
                        "state": info["state"],
                        "created_at": info["created_at"].isoformat(),
                        "age_minutes": round(
                            (datetime.now() - info["created_at"]).total_seconds() / 60,
                            1,
                        ),
                        "has_interrupt": user_id in self.user_interrupts,
                    }
                    for user_id, info in self.user_sessions.items()
                }
                if len(self.user_sessions) < 20
                else {
                    "note": f"Too many sessions to display ({len(self.user_sessions)})"
                }
            ),
        }

    def setup_bot_handlers(self):
        """Setup bot handlers with simplified configuration"""
        from telegram.ext import Application

        # Configure application
        self.application = (
            Application.builder()
            .token(self.bot_token)
            .connection_pool_size(self.max_connections)
            .pool_timeout(self.pool_timeout)
            .read_timeout(self.connection_timeout)
            .write_timeout(self.connection_timeout)
            .connect_timeout(self.connection_timeout)
            .build()
        )

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))

        # Add message handler for all text messages (both private and group)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & (~filters.COMMAND),
                self.handle_message,
            )
        )

        self.logger.info("Bot handlers configured for swap functionality")

    async def start_bot(self):
        """Start the bot"""
        if not self.application:
            self.setup_bot_handlers()

        self.logger.info("Starting Swap Telegram bot...")

        # Start the application
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        self.logger.info("Swap Telegram bot started successfully")

    async def stop_bot(self):
        """Stop the bot gracefully"""
        if self.application and self.application.updater:
            self.logger.info("Stopping Swap Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.logger.info("Swap Telegram bot stopped successfully")

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the service"""
        try:
            me = await self.bot.get_me()
            bot_info = {
                "username": me.username,
                "first_name": me.first_name,
                "id": me.id,
            }

            user_count = len(self.load_user_ids())
            session_stats = self.get_session_stats()

            health_status = {
                "status": "healthy",
                "bot_info": bot_info,
                "configuration": {
                    "swap_graph_name": self.swap_graph_name,
                    "swap_chat_enabled": self.enable_swap_chat,
                    "langgraph_server_url": self.langgraph_server_url is not None,
                    "interaction_cooldown": self.interaction_cooldown,
                },
                "statistics": {
                    "total_users": user_count,
                    "active_sessions": session_stats["active_sessions"],
                    "pending_interrupts": session_stats["pending_interrupts"],
                },
                "timestamp": datetime.now().isoformat(),
            }

            return health_status

        except Exception as e:
            error_status = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            self.logger.error(f"Health check failed: {e}")
            return error_status


# Utility functions
def run_swap_bot(bot_token: str):
    """Run the swap bot standalone"""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    bot = SwapTelegramBotService(bot_token)
    bot.setup_bot_handlers()

    try:
        bot.application.run_polling()
    except KeyboardInterrupt:
        print("Swap bot stopped by user")


def main():
    """Main function to run the swap bot"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is required")
        return

    # Validate required environment variables
    langgraph_url = os.getenv("LANGGRAPH_SERVER_URL")
    if not langgraph_url:
        print(
            "Warning: LANGGRAPH_SERVER_URL not set - swap functionality will be limited"
        )

    swap_graph_name = os.getenv("SWAP_GRAPH_NAME", "graph_swap_v2")
    print(f"Using swap graph: {swap_graph_name}")

    run_swap_bot(bot_token)


if __name__ == "__main__":
    main()
