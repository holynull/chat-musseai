# telegram_bot.py
import asyncio
import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv(".env.telegram_bot")


class TelegramSubscriptionBot:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot_token = bot_token
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)
        self.application = None

    async def set_bot_commands(self):
        """Set bot commands that will appear in the menu button"""
        commands = [
            BotCommand("menu", "Display interactive menu"),
            BotCommand("start", "Subscribe to trading signals"),
            BotCommand("status", "Check subscription status"),
            BotCommand("help", "Get help information"),
            BotCommand("stop", "Unsubscribe"),
        ]

        try:
            await self.application.bot.set_my_commands(commands)
            self.logger.info("Bot commands set successfully")
        except Exception as e:
            self.logger.error(f"Failed to set bot commands: {e}")

    def create_main_menu(self) -> InlineKeyboardMarkup:
        """Create simple inline keyboard menu"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Subscription Status", callback_data="action:status"),
                InlineKeyboardButton("🔔 Subscribe", callback_data="action:subscribe"),
            ],
            [
                InlineKeyboardButton("🔕 Unsubscribe", callback_data="action:unsubscribe"),
                InlineKeyboardButton("❓ Help", callback_data="action:help"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - show inline keyboard menu"""
        menu_markup = self.create_main_menu()

        chat_type = (
            "Group" if update.effective_chat.type in ["group", "supergroup"] else "Private"
        )

        await update.message.reply_text(
            f"🤖 **Trading Signal Bot Menu**\n\n"
            f"📱 Current Environment: {chat_type}\n"
            f"👤 User: @{update.effective_user.username or 'Unknown'}\n\n"
            f"Please select an operation:",
            reply_markup=menu_markup,
            parse_mode="Markdown",
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button callbacks"""
        query = update.callback_query
        await query.answer()

        action = query.data.split(":")[1]

        if action == "status":
            await self.handle_status_callback(query)
        elif action == "subscribe":
            await self.handle_subscribe_callback(query)
        elif action == "unsubscribe":
            await self.handle_unsubscribe_callback(query)
        elif action == "help":
            await self.handle_help_callback(query)

    async def handle_status_callback(self, query):
        """Handle status button click"""
        chat_id = str(query.message.chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id in chat_ids:
            total_subscribers = len(chat_ids)
            status_text = (
                f"✅ **Subscription Status: ACTIVE**\n\n"
                f"📊 Total Subscribers: {total_subscribers}\n"
                f"🔔 Receiving signals: ETH, BTC\n"
                f"⏰ Signal frequency: Every 15 minutes\n\n"
                f"💡 Click buttons below for other operations"
            )
        else:
            status_text = (
                "❌ **Subscription Status: INACTIVE**\n\n"
                "You are not currently subscribed to signal notifications.\n"
                "Click '🔔 Subscribe' button to start receiving notifications."
            )

        await query.edit_message_text(
            status_text, reply_markup=self.create_main_menu(), parse_mode="Markdown"
        )

    async def handle_subscribe_callback(self, query):
        """Handle subscribe button click"""
        chat_id = str(query.message.chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            self.save_chat_ids(chat_ids)

            subscribe_text = (
                "🎉 **Subscription Successful!**\n\n"
                "✅ You have successfully subscribed to trading signal notifications\n"
                "🔔 Will receive ETH, BTC trading signals\n"
                "⏰ Signal frequency: Every 15 minutes\n"
                "📱 Available in both group and private chat environments"
            )
            self.logger.info(f"User subscribed via menu: {chat_id}")
        else:
            subscribe_text = (
                "📱 **Already Subscribed**\n\n"
                "You are already subscribed to trading signal notifications.\n"
                "If you need to unsubscribe, please click '🔕 Unsubscribe' button."
            )

        await query.edit_message_text(
            subscribe_text, reply_markup=self.create_main_menu(), parse_mode="Markdown"
        )

    async def handle_unsubscribe_callback(self, query):
        """Handle unsubscribe button click"""
        chat_id = str(query.message.chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id in chat_ids:
            chat_ids.remove(chat_id)
            self.save_chat_ids(chat_ids)

            unsubscribe_text = (
                "😢 **Unsubscription Successful**\n\n"
                "You have unsubscribed from trading signal notifications.\n"
                "To resubscribe, please click '🔔 Subscribe' button."
            )
            self.logger.info(f"User unsubscribed via menu: {chat_id}")
        else:
            unsubscribe_text = (
                "❌ **Subscription Not Found**\n\n"
                "You are not currently subscribed to notifications.\n"
                "Click '🔔 Subscribe' button to start receiving notifications."
            )

        await query.edit_message_text(
            unsubscribe_text,
            reply_markup=self.create_main_menu(),
            parse_mode="Markdown",
        )

    async def handle_help_callback(self, query):
        """Handle help button click"""
        help_text = """
🤖 **Trading Signal Bot Help**

**🎯 Main Features:**
📈 Provides real-time ETH and BTC trading signals
📊 Updates signals every 15 minutes
🔔 Instant push notifications to groups and private chats

**📱 Menu Description:**
📊 Subscription Status - Check current subscription status and statistics
🔔 Subscribe - Start receiving trading signal notifications
🔕 Unsubscribe - Stop receiving all notifications
❓ Help - Display this help information

**⌨️ Command List:**
/menu - Display interactive menu (recommended)
/start - Quick subscribe
/stop - Quick unsubscribe
/status - Check status
/help - Display help

**🔧 Technical Support:**
Contact administrator if you encounter any issues
        """

        await query.edit_message_text(
            help_text, reply_markup=self.create_main_menu(), parse_mode="Markdown"
        )

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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            self.save_chat_ids(chat_ids)

            await update.message.reply_text(
                "🎉 *Welcome to Trading Signal Bot!*\n\n"
                "✅ You have been subscribed to receive trading signals and backtest results.\n\n"
                "*💡 How to use:*\n"
                "• Click the **Menu Button** 📋 in the chat\n"
                "• Or send /menu command\n\n"
                "*Available Commands:*\n"
                "/menu - Display interactive menu (recommended)\n"
                "/start - Subscribe to notifications\n"
                "/stop - Unsubscribe from notifications\n"
                "/status - Check your subscription status\n"
                "/help - Show this help message",
                parse_mode="Markdown",
            )

            self.logger.info(f"New user subscribed: {chat_id}")
        else:
            await update.message.reply_text(
                "📱 You are already subscribed to trading signals!\n\n"
                "Use /stop to unsubscribe or /status to check your subscription.",
                parse_mode="Markdown",
            )

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
            )
            self.logger.info(f"User unsubscribed: {chat_id}")
        else:
            await update.message.reply_text(
                "❌ You are not currently subscribed to notifications.\n\n"
                "Use /start to subscribe to trading signals.",
                parse_mode="Markdown",
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
                f"Use /stop to unsubscribe.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ *Subscription Status: INACTIVE*\n\n"
                "You are not currently subscribed to notifications.\n"
                "Use /start to subscribe to trading signals.",
                parse_mode="Markdown",
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

*Support:*
If you encounter any issues, please contact the administrator.
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")

    def setup_handlers(self):
        """Setup all command and callback handlers"""
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))

        # Add callback query handler for inline keyboard buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

    async def initialize(self):
        """Initialize the bot application"""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Initialize the application
        await self.application.initialize()
        
        # Set bot commands for menu button
        await self.set_bot_commands()

    async def start_polling(self):
        """Start the bot with polling"""
        try:
            await self.initialize()
            self.logger.info("Telegram subscription bot starting...")
            
            # Start polling
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.logger.info("Bot is now polling for updates...")
            
            # Keep the bot running
            await self.application.updater.idle()
            
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            raise
        finally:
            # Cleanup
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

    async def run(self):
        """Main run method - simplified version"""
        await self.start_polling()


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
    
    # Use asyncio.run for clean event loop management
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot encountered an error: {e}")
        logging.error(f"Bot error: {e}")


if __name__ == "__main__":
    main()