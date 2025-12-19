# nano ~/Swingbot_2025/boot_alert.py
from notifier import send_msg
import datetime

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
send_msg(f"⚠️ **SERVER REBOOTED**\n\nThe trading server finished startup at {now} UTC.\nDashboard and Monitor services should be auto-restarting.")
