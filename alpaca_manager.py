import os
import pandas as pd
import sqlalchemy
from datetime import datetime
from dotenv import load_dotenv

# Alpaca Imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

# --- CONFIGURATION ---
load_dotenv()  # <--- LOADS KEYS FROM .env FILE

API_KEY = os.getenv("ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET")
PAPER = os.getenv("ALPACA_PAPER") == "True"

if not API_KEY or not SECRET_KEY:
    raise ValueError("❌ CRITICAL: API Keys not found in .env file!")

# Database Setup
engine = sqlalchemy.create_engine('sqlite:///silent_swing.db')

class AlpacaExecutor:
    def __init__(self):
        # 1. Trading Client (Executes Orders)
        self.trading_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
        
        # 2. Data Client (Fetches Live Prices FAST)
        self.data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
        
        # 3. Cache Account Info
        self.account = self.trading_client.get_account()
        
    def get_buying_power(self):
        # Refresh account data to get accurate BP
        self.account = self.trading_client.get_account()
        return float(self.account.buying_power)

    def get_current_positions(self):
        """Returns a list of symbols we currently own."""
        try:
            positions = self.trading_client.get_all_positions()
            return [p.symbol for p in positions]
        except Exception as e:
            print(f"⚠️ Error fetching positions: {e}")
            return []

    def get_pending_buy_symbols(self):
        """
        Returns a list of tickers that have active BUY orders waiting to fill.
        """
        try:
            req = GetOrdersRequest(status=QueryOrderStatus.OPEN, side=OrderSide.BUY)
            orders = self.trading_client.get_orders(filter=req)
            return [o.symbol for o in orders]
        except Exception as e:
            print(f"⚠️ Error fetching pending orders: {e}")
            return []

    def get_latest_price(self, ticker):
        """
        Fetches the latest trade price directly from Alpaca (Much faster than YFinance).
        """
        try:
            req = StockLatestTradeRequest(symbol_or_symbols=ticker)
            trade = self.data_client.get_stock_latest_trade(req)
            return float(trade[ticker].price)
        except Exception as e:
            print(f"⚠️ Alpaca Data Failed for {ticker}: {e}. Falling back to estimate.")
            # Fallback is dangerous, better to skip or return None, but keeping 100 for safety logic
            return 0.0

    def execute_buy(self, ticker, stop_price, allocation_pct=0.10):
        try:
            # 1. Get accurate price
            latest_price = self.get_latest_price(ticker)
            if latest_price == 0.0:
                print(f"❌ Aborting Buy: Could not fetch price for {ticker}")
                return

            # 2. Calculate Quantity
            # Note: Using 'cash' is safer than buying_power for beginners
            account_cash = float(self.trading_client.get_account().cash)
            spend_amount = account_cash * allocation_pct
            
            qty = int(spend_amount // latest_price)
            
            if qty < 1:
                print(f"⚠️ Insufficient funds to buy {ticker} (Cash: ${account_cash:.2f})")
                return

            # 3. Define The Bracket
            # Take Profit: +15%
            take_profit_price = round(latest_price * 1.15, 2)
            # Stop Loss: Passed from Scanner
            stop_loss_price = round(stop_price, 2)

            print(f"🔒 Setting Bracket for {ticker}: Entry ~${latest_price} | Stop ${stop_loss_price} | Target ${take_profit_price}")

            # 4. Construct Order
            order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                take_profit=TakeProfitRequest(limit_price=take_profit_price),
                stop_loss=StopLossRequest(stop_price=stop_loss_price)
            )

            # 5. Submit
            order = self.trading_client.submit_order(order_data)
            
            # 6. Log
            self.log_trade(ticker, "BUY_BRACKET", latest_price, qty, order.id)
            print(f"✅ EXECUTED: {qty} shares of {ticker}")
            
        except Exception as e:
            print(f"❌ EXECUTION ERROR ({ticker}): {e}")

    def log_trade(self, ticker, action, price, qty, order_id):
        df = pd.DataFrame([{
            'date': datetime.now(),
            'ticker': ticker,
            'action': action,
            'price': price,
            'qty': qty,
            'order_id': str(order_id)
        }])
        df.to_sql('trade_history', engine, if_exists='append', index=False)

if __name__ == "__main__":
    try:
        bot = AlpacaExecutor()
        print(f"Executor Online. Buying Power: ${bot.get_buying_power():,.2f}")
    except Exception as e:
        print(f"Startup Failed: {e}")