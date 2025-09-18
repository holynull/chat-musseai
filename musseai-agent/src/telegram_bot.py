# telegram_bot.py (Enhanced with Button Menu)
import asyncio
import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

load_dotenv(".env.telegram_bot")


class TelegramSubscriptionBot:
    def __init__(self, bot_token: str, chat_storage_file: str = "telegram_users.json"):
        self.bot_token = bot_token
        self.chat_storage_file = chat_storage_file
        self.logger = logging.getLogger(__name__)

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

    def create_main_menu(self) -> InlineKeyboardMarkup:
        """Create main menu with inline buttons"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Check Status", callback_data="status"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe"),
                InlineKeyboardButton("🔄 Refresh Menu", callback_data="refresh")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_unsubscribe_menu(self) -> InlineKeyboardMarkup:
        """Create unsubscribe confirmation menu"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Unsubscribe", callback_data="confirm_unsubscribe"),
                InlineKeyboardButton("❌ Cancel", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_subscribe_menu(self) -> InlineKeyboardMarkup:
        """Create subscribe menu for non-subscribed users"""
        keyboard = [
            [
                InlineKeyboardButton("🔔 Subscribe Now", callback_data="subscribe"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with menu"""
        chat_id = str(update.effective_chat.id)
        chat_ids = self.load_chat_ids()

        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            self.save_chat_ids(chat_ids)

            welcome_text = (
                "🎉 *Welcome to Trading Signal Bot!*\n\n"
                "✅ You have been subscribed to receive trading signals and backtest results.\n\n"
                "Use the menu below to manage your subscription:"
            )
            self.logger.info(f"New user subscribed: {chat_id}")
            reply_markup = self.create_main_menu()
        else:
            welcome_text = (
                "👋 *Welcome back!*\n\n"
                "📱 You are already subscribed to trading signals!\n\n"
                "Use the menu below to manage your subscription:"
            )
            reply_markup = self.create_main_menu()

        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
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
                text,
                parse_mode="Markdown",
                reply_markup=reply_markup
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
            
            reply_markup = self.create_main_menu() if is_subscribed else self.create_subscribe_menu()
            
            await query.edit_message_text(
                status_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
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

*Support:*
If you encounter any issues, please contact the administrator.
            """
            
            keyboard = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                help_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
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
                reply_markup=self.create_main_menu()
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
                    reply_markup=self.create_unsubscribe_menu()
                )
            else:
                await query.edit_message_text(
                    "❌ You are not currently subscribed to notifications.",
                    parse_mode="Markdown",
                    reply_markup=self.create_subscribe_menu()
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
                unsubscribe_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
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
                reply_markup=self.create_subscribe_menu()
            )
            self.logger.info(f"User unsubscribed: {chat_id}")
        else:
            await update.message.reply_text(
                "❌ You are not currently subscribed to notifications.\n\n"
                "Use /start to subscribe to trading signals.",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu()
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
                reply_markup=self.create_main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ *Subscription Status: INACTIVE*\n\n"
                "You are not currently subscribed to notifications.\n"
                "Use the menu below to subscribe:",
                parse_mode="Markdown",
                reply_markup=self.create_subscribe_menu()
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

        await update.message.reply_text(
            help_text, 
            parse_mode="Markdown",
            reply_markup=self.create_main_menu()
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
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
                successful_sends += 1
                self.logger.info(f"Signal sent successfully to {chat_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to send signal to {chat_id}: {e}")
                failed_sends += 1
                
                # Remove inactive users (e.g., blocked bot, deleted account)
                if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    chat_ids.remove(chat_id)
                    self.logger.info(f"Removed inactive user: {chat_id}")
        
        # Save updated chat_ids (removed inactive users)
        if failed_sends > 0:
            self.save_chat_ids(chat_ids)
        
        self.logger.info(f"Broadcast complete: {successful_sends} successful, {failed_sends} failed")
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
