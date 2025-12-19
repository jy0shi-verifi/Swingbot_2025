import os
import telebot
import requests
import datetime
from dotenv import load_dotenv

# Path logic for server-side reliability
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_msg(message):
    """Standard outbound alerts used by Autopilot, Monitor, and Boot Alert."""
    if not TOKEN or not CHAT_ID:
        print(f"🚫 Alert Skipped (No Keys): {message}")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

# Command handlers for interacting with your bot from your phone
if TOKEN:
    bot = telebot.TeleBot(TOKEN)
    
    @bot.message_handler(commands=['ping'])
    def check_status(message):
        uptime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot.reply_to(message, f"🟢 **Silent Swing Bot is ONLINE**\n🕒 Server Time: {uptime}\n🛰️ All systems nominal.")

    @bot.message_handler(commands=['status'])
    def account_status(message):
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
