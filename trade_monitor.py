import time
import os
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus
from datetime import datetime, timedelta
import pytz

# --- CONFIGURATION ---
load_dotenv()

API_KEY = os.getenv("ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET")
PAPER = os.getenv("ALPACA_PAPER") == "True"

if not API_KEY or not SECRET_KEY:
    raise ValueError("❌ Monitor Error: API Keys missing in .env")

# Database
engine = sqlalchemy.create_engine('sqlite:///silent_swing.db')

# Telegram Integration
try:
    from notifier import send_msg
except ImportError:
    def send_msg(msg): print(f"[MOCK NOTIFY] {msg}")

class TradeMonitor:
    def __init__(self):
        self.client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
        
    def check_fills(self):
        """Checks for recent trade fills that aren't in our DB yet."""
        try:
            # 1. Get recent closed orders (last 24 hours)
            now = datetime.now(pytz.utc)
            filter_req = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                after=now - timedelta(days=1),
                limit=50
            )
            orders = self.client.get_orders(filter=filter_req)
            
            # 2. Load known trades from DB
            try:
                history = pd.read_sql('trade_history', engine)
                known_ids = history['order_id'].astype(str).tolist()
            except Exception:
                # Table might not exist yet
                known_ids = []
                
            # 3. Compare and Alert
            for order in orders:
                if str(order.id) not in known_ids and order.filled_qty is not None and float(order.filled_qty) > 0:
                    self.process_fill(order)
                    
        except Exception as e:
            print(f"⚠️ Check Loop Error: {e}")

    def process_fill(self, order):
        side = "BUY" if order.side == OrderSide.BUY else "SELL"
        symbol = order.symbol
        qty = float(order.filled_qty)
        price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
        
        # Log to DB
        df = pd.DataFrame([{
            'date': order.filled_at,
            'ticker': symbol,
            'action': side,
            'price': price,
            'qty': qty,
            'order_id': str(order.id)
        }])
        
        try:
            df.to_sql('trade_history', engine, if_exists='append', index=False)
            print(f"✅ Logged Fill: {side} {symbol}")
        except Exception as e:
            print(f"❌ DB Write Error: {e}")
        
        # Determine Notification Message
        if side == "BUY":
            msg = f"🔵 **FILLED BUY:** {symbol}\nQty: {qty} @ ${price:.2f}"
        else:
            # THIS IS YOUR STOP LOSS / TAKE PROFIT ALERT
            msg = (
                f"🛑 **POSITION CLOSED:** {symbol}\n"
                f"📉 Sold {qty} shares @ ${price:.2f}\n"
                f"✅ Trade Completed."
            )
            
        send_msg(msg)

if __name__ == "__main__":
    print("👀 Trade Monitor Active... (Press Ctrl+C to stop)")
    monitor = TradeMonitor()
    
    # Simple loop to check every minute
    while True:
        monitor.check_fills()
        time.sleep(60)