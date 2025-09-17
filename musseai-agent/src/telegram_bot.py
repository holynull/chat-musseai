# telegram_bot.py
import asyncio
import logging
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv(".env.trading_signal")


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
                "*Available Commands:*\n"
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

    def run(self):
        """Start the subscription bot"""
        application = Application.builder().token(self.bot_token).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("stop", self.stop_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("help", self.help_command))

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
