# telegram_bot.py (Enhanced with Button Menu, New Member Welcome, and Mention Handling)
import asyncio
import logging
import json
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv(".env.telegram_bot")


class TelegramSubscriptionBot:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot_token = bot_token
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        # Anti-spam mechanism: track last interaction time for each user
        self.last_interaction = {}
        self.interaction_cooldown = 30  # 30 seconds cooldown

    def load_chat_ids(self) -> list:
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

    def save_chat_ids(self, chat_ids: list):
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
            # New member in group
            greeting = (
                f"👋 Welcome to the group, {user_name}!"
                if user_name
                else "👋 Welcome to the group!"
            )
            return (
                f"🎉 *{greeting}*\n\n"
                "🤖 I'm your Trading Signal Bot! I provide:\n"
                "📈 Real-time trading signals for ETH and BTC\n"
                "📊 Automated backtest results\n"
                "⏰ Updates every 15 minutes\n\n"
                "Use the menu below to get started:"
            )
        elif chat_type in ["group", "supergroup"]:
            # Mentioned in group
            return (
                "🤖 *Trading Signal Bot Menu*\n\n"
                "Hello! I provide automated trading signals and analysis.\n\n"
                "📋 *Available Features:*\n"
                "• Real-time ETH/BTC signals\n"
                "• Backtest results\n"
                "• Portfolio analysis\n"
                "• Regular market updates\n\n"
                "Use the menu below to manage your subscription:"
            )
        else:
            # Private chat
            return (
                "👋 *Welcome to Trading Signal Bot!*\n\n"
                "I'm here to help you with cryptocurrency trading signals and analysis.\n\n"
                "🔔 Subscribe to receive:\n"
                "📈 Trading signals for ETH and BTC\n"
                "📊 Backtest results and analysis\n"
                "⏰ Regular market updates\n\n"
                "Use the menu below to get started:"
            )

    async def handle_new_chat_members(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle new members joining the chat"""
        try:
            # Check if this is a status update (new members joining)
            if not update.message or not update.message.new_chat_members:
                return

            for new_member in update.message.new_chat_members:
                # Skip if the new member is a bot (except our bot)
                if new_member.is_bot and new_member.id != context.bot.id:
                    continue

                # Skip if it's our bot being added (handled separately)
                if new_member.id == context.bot.id:
                    continue

                # Check rate limiting
                user_id = str(new_member.id)
                if self.is_rate_limited(user_id):
                    self.logger.info(f"Rate limited new member welcome for {user_id}")
                    continue

                chat_type = update.effective_chat.type
                user_name = new_member.first_name or new_member.username or "there"

                # Generate welcome message
                welcome_text = self.get_welcome_message(
                    chat_type=chat_type, user_name=user_name, is_new_member=True
                )

                # Check if user is already subscribed
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
            # Get bot info
            bot_username = context.bot.username
            message_text = update.message.text or ""

            # Check for @username mention or reply to bot
            is_mentioned = False

            # Check for direct @username mention
            if f"@{bot_username}" in message_text:
                is_mentioned = True

            # Check if message has entities (mentions)
            if update.message.entities:
                for entity in update.message.entities:
                    if entity.type == "mention":
                        # Extract the mentioned username
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

            # Check rate limiting
            if self.is_rate_limited(user_id):
                self.logger.info(f"Rate limited mention response for {user_id}")
                return

            chat_type = update.effective_chat.type
            user_name = (
                update.effective_user.first_name
                or update.effective_user.username
                or "User"
            )

            # Generate context-aware response
            response_text = self.get_welcome_message(chat_type=chat_type)

            # Check subscription status
            chat_ids = self.load_chat_ids()
            is_subscribed = user_id in chat_ids

            reply_markup = (
                self.create_main_menu()
                if is_subscribed
                else self.create_subscribe_menu()
            )

            # Add personal greeting for group mentions
            if chat_type in ["group", "supergroup"]:
                response_text = f"Hi {user_name}! 👋\n\n" + response_text

            await update.message.reply_text(
                response_text, parse_mode="Markdown", reply_markup=reply_markup
            )

            self.logger.info(
                f"Responded to mention from {user_name} ({user_id}) in {chat_type}"
            )

        except Exception as e:
            self.logger.error(f"Error handling mention: {e}")

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
                    "🎉 *Welcome to Trading Signal Bot!*\n\n"
                    "✅ You have been subscribed to receive trading signals and backtest results.\n\n"
                    "Use the menu below to manage your subscription:"
                )

            self.logger.info(f"New user subscribed: {chat_id}")
            reply_markup = self.create_main_menu()
        else:
            if chat_type == "private":
                welcome_text = (
                    "👋 *Welcome back!*\n\n"
                    "📱 You are already subscribed to trading signals!\n\n"
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
                text = "🏠 *Main Menu*\n\nYou are subscribed to trading signals. Choose an option:"
                reply_markup = self.create_main_menu()
            else:
                text = "🏠 *Main Menu*\n\nYou are not subscribed. Would you like to subscribe?"
                reply_markup = self.create_subscribe_menu()

            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=reply_markup
            )

        elif query.data == "status":
            if is_subscribed:
                total_subscribers = len(chat_ids)
                status_text = (
                    f"✅ *Subscription Status: ACTIVE*\n\n"
                    f"📊 Total Subscribers: {total_subscribers}\n"
                    f"🔔 You will receive trading signals for: ETH, BTC\n"
                    f"⏰ Signal frequency: Every 15 minutes\n\n"
                    f"Use the menu below to manage your subscription:"
                )
            else:
                status_text = (
                    "❌ *Subscription Status: INACTIVE*\n\n"
                    "You are not currently subscribed to notifications.\n"
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
            help_text = """
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
• Mention me (@{}) to see this menu
• I'll welcome new members automatically
• All features work in both private and group chats

*Support:*
If you encounter any issues, please contact the administrator.
            """.format(
                context.bot.username or "tradingbot"
            )

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
                    "🎉 *Successfully Subscribed!*\n\n"
                    "✅ You will now receive trading signals and backtest results.\n\n"
                    "Welcome to our community of traders!"
                )
                self.logger.info(f"User subscribed via button: {chat_id}")
            else:
                subscribe_text = (
                    "✅ *Already Subscribed!*\n\n"
                    "You are already receiving trading signals.\n\n"
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
                    "⚠️ *Confirm Unsubscribe*\n\n"
                    "Are you sure you want to unsubscribe from trading signal notifications?\n\n"
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
                    "😢 *Unsubscribed Successfully*\n\n"
                    "You will no longer receive trading signal notifications.\n\n"
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

    # Keep original command handlers for backward compatibility
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id in chat_ids:
            chat_ids.remove(chat_id)
            self.save_chat_ids(chat_ids)

            await update.message.reply_text(
                "😢 *Unsubscribed Successfully*\n\n"
                "You will no longer receive trading signal notifications.\n\n"
                "To re-subscribe, simply send /start anytime.",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu(),
            )
            self.logger.info(f"User unsubscribed: {chat_id}")
        else:
            await update.message.reply_text(
                "❌ You are not currently subscribed to notifications.\n\n"
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
                f"✅ *Subscription Status: ACTIVE*\n\n"
                f"📊 Total Subscribers: {total_subscribers}\n"
                f"🔔 You will receive trading signals for: ETH, BTC\n"
                f"⏰ Signal frequency: Every 15 minutes\n\n"
                f"Use the menu below to manage your subscription:",
                parse_mode="Markdown",
                reply_markup=self.create_main_menu(),
            )
        else:
            await update.message.reply_text(
                "❌ *Subscription Status: INACTIVE*\n\n"
                "You are not currently subscribed to notifications.\n"
                "Use the menu below to subscribe:",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu(),
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
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
• Mention me (@{}) to see the menu
• I'll automatically welcome new members
• All subscription features work in groups

*Support:*
If you encounter any issues, please contact the administrator.
        """.format(
            context.bot.username or "tradingbot"
        )

        await update.message.reply_text(
            help_text, parse_mode="Markdown", reply_markup=self.create_main_menu()
        )

    async def broadcast_signal(self, message: str, parse_mode: str = "Markdown"):
        """Send trading signal to all subscribers"""
        chat_ids = self.load_chat_ids()
        successful_sends = 0
        failed_sends = 0

        if not chat_ids:
            self.logger.warning("No subscribers to send signals to")
            return {"successful": 0, "failed": 0}

        application = Application.builder().token(self.bot_token).build()

        for chat_id in chat_ids[:]:  # Create a copy to iterate safely
            try:
                await application.bot.send_message(
                    chat_id=chat_id, text=message, parse_mode=parse_mode
                )
                successful_sends += 1
                self.logger.info(f"Signal sent successfully to {chat_id}")

            except Exception as e:
                self.logger.error(f"Failed to send signal to {chat_id}: {e}")
                failed_sends += 1

                # Remove inactive users (e.g., blocked bot, deleted account)
                if (
                    "bot was blocked" in str(e).lower()
                    or "chat not found" in str(e).lower()
                ):
                    chat_ids.remove(chat_id)
                    self.logger.info(f"Removed inactive user: {chat_id}")

        # Save updated chat_ids (removed inactive users)
        if failed_sends > 0:
            self.save_chat_ids(chat_ids)

        self.logger.info(
            f"Broadcast complete: {successful_sends} successful, {failed_sends} failed"
        )
        return {"successful": successful_sends, "failed": failed_sends}

    def run(self):
        """Start the subscription bot"""
        application = Application.builder().token(self.bot_token).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("stop", self.stop_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("help", self.help_command))

        # Add callback query handler for buttons
        application.add_handler(CallbackQueryHandler(self.button_callback))

        # Add new member handler - using MessageHandler instead of ChatMemberHandler
        application.add_handler(
            MessageHandler(
                filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_chat_members
            )
        )

        # Add message handler for mentions and replies (must be after command handlers)
        application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_mention)
        )

        self.logger.info("Telegram subscription bot starting...")
        application.run_polling()


def main():
    """Main function to run the subscription bot"""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is required")
        return

    bot = TelegramSubscriptionBot(bot_token)
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Bot stopped by user")


if __name__ == "__main__":
    main()
