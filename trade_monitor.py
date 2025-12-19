import time
import os
import pandas as pd
import sqlalchemy
import math
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, ReplaceOrderRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus
from datetime import datetime, timedelta
import pytz
from notifier import send_msg

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET")
PAPER = os.getenv("ALPACA_PAPER") == "True"

if not API_KEY or not SECRET_KEY:
    raise ValueError("❌ Monitor Error: API Keys missing in .env")

engine = sqlalchemy.create_engine('sqlite:///silent_swing.db')

class TradeMonitor:
    def __init__(self):
        self.client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
        # Track local High Water Marks to know when to trail
        self.high_water_marks = {} 

    def update_trailing_stops(self):
        """Dynamic logic to lock in profits as prices rise."""
        try:
            positions = self.client.get_all_positions()
            orders = self.client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, nested=True))
            
            for pos in positions:
                symbol = pos.symbol
                curr_price = float(pos.current_price)
                
                # 1. Update High Water Mark
                if symbol not in self.high_water_marks or curr_price > self.high_water_marks[symbol]:
                    self.high_water_marks[symbol] = curr_price
                    print(f"📈 New high for {symbol}: ${curr_price}")

                # 2. Find the Stop Loss order for this position
                # Alpaca lists legs under the primary filled order
                for order in orders:
                    if order.symbol == symbol and order.side == OrderSide.SELL and order.stop_price:
                        old_stop = float(order.stop_price)
                        # Rule: Trail at 5% below the highest price seen
                        new_stop = round(self.high_water_marks[symbol] * 0.95, 2)
                        
                        # 3. If new stop is significantly higher (> 0.5%), replace it
                        if new_stop > old_stop * 1.005:
                            print(f"🔄 Trailing Stop for {symbol}: {old_stop} -> {new_stop}")
                            self.client.replace_order_by_id(order.id, ReplaceOrderRequest(stop_price=new_stop))
                            send_msg(f"🛡️ **PROFIT LOCKED:** {symbol}\nSafety net moved up to **${new_stop}**")
                            
        except Exception as e:
            print(f"⚠️ Trailing Loop Error: {e}")

    def check_fills(self):
        """Checks for recent trade fills that aren't in our DB yet."""
        try:
            now = datetime.now(pytz.utc)
            filter_req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=now - timedelta(days=1))
            orders = self.client.get_orders(filter=filter_req)
            
            try:
                history = pd.read_sql('trade_history', engine)
                known_ids = history['order_id'].astype(str).tolist()
            except:
                known_ids = []
        
            for order in orders:
                if str(order.id) not in known_ids and order.filled_qty and float(order.filled_qty) > 0:
                    self.process_fill(order)
        except Exception as e:
            print(f"⚠️ Fill Check Error: {e}")

    def process_fill(self, order):
        side = "BUY" if order.side == OrderSide.BUY else "SELL"
        symbol = order.symbol
        qty = float(order.filled_qty)
        price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
        
        # Log to DB (Needed for Dashboard)
        df = pd.DataFrame([{'date': order.filled_at, 'ticker': symbol, 'action': side, 'price': price, 'qty': qty, 'order_id': str(order.id)}])
        df.to_sql('trade_history', engine, if_exists='append', index=False)
        
        # Notification
        if side == "BUY":
            send_msg(f"🔵 **NEW POSITION:** {symbol}\nFilled {qty} @ ${price:.2f}")
        else:
            send_msg(f"🛑 **CLOSED:** {symbol}\nSold {qty} @ ${price:.2f}\n✅ Profit/Loss captured.")

if __name__ == "__main__":
    send_msg("👀 **Trade Monitor Active**\nTracking high-water marks and profit locks.")
    monitor = TradeMonitor()
    while True:
        monitor.check_fills()
        monitor.update_trailing_stops() # Run the trailing logic
        time.sleep(60)
