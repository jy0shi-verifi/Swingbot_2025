import os
import telebot # pip install pyTelegramBotAPI
import requests
import datetime
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv() # Load keys from .env

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Safety Check
if not TOKEN or not CHAT_ID:
    print("⚠️ Telegram keys missing in .env. Notifications will fail.")
    # We don't raise error here so the rest of the bot can still run, 
    # but we initialize the bot conditionally to prevent crashes.
    bot = None
else:
    bot = telebot.TeleBot(TOKEN)

def send_msg(message):
    """Standard outbound alerts used by Autopilot & Monitor."""
    if not TOKEN or not CHAT_ID:
        print(f"🚫 Alert Skipped (No Keys): {message}")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

# Only set up handlers if bot is active
if bot:
    @bot.message_handler(commands=['ping'])
    def check_status(message):
        """Responds when you text /ping to the bot."""
        uptime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            bot.reply_to(message, f"🟢 **Silent Swing Bot is ONLINE**\n🕒 Server Time: {uptime}\n🛰️ All systems nominal.")
        except Exception as e:
            print(f"Ping Error: {e}")

    @bot.message_handler(commands=['status'])
    def account_status(message):
        """Future QOL: Could fetch Alpaca balance here."""
        bot.reply_to(message, "📊 Check the Dashboard for full financial breakdown!")

if __name__ == "__main__":
    if bot:
        print("📡 Telegram Listener Active... Text /ping to your bot now!")
        try:
            bot.polling(non_stop=True)
        except Exception as e:
            print(f"⚠️ Bot Polling Crashed: {e}")
    else:
        print("❌ Telegram Bot disabled (Missing Keys).")