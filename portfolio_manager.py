import pandas as pd
from backtester import SilentBacktester
import datetime

# --- CONFIGURATION ---
# We use the 'Approved' universe from our stress tests
UNIVERSE = ["SPY", "NVDA", "BTC-USD", "USO", "AAPL", "MSFT", "QQQ"]
TOTAL_CAPITAL = 10000  
MAX_ALLOCATION_PER_TICKER = 0.10  # 10% per position

print(f"--- SILENT SWING BOT: PORTFOLIO REPORT ({datetime.date.today()}) ---")
print(f"{'TICKER':<10} | {'ACTION':<12} | {'PRICE':<10} | {'SHARES':<8} | {'INVESTMENT':<10}")
print("-" * 65)

for ticker in UNIVERSE:
    try:
        # Check the last year of data to get trend and RSI
        bot = SilentBacktester(ticker, 
                               (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'),
                               datetime.datetime.now().strftime('%Y-%m-%d'))
        bot.fetch_data()
        bot.apply_strategy()
        
        last_row = bot.data.iloc[-1]
        price = last_row['Close']
        
        if last_row['Signal'] == 1:
            target_spend = TOTAL_CAPITAL * MAX_ALLOCATION_PER_TICKER
            share_count = int(target_spend // price)
            actual_investment = share_count * price
            action = "BUY/HOLD"
            shares = share_count
            invested = f"${actual_investment:,.2f}"
        else:
            action = "CASH/SELL"
            shares = 0
            invested = "$0.00"

        print(f"{ticker:<10} | {action:<12} | ${price:<9.2f} | {shares:<8} | {invested:<10}")
        
    except Exception as e:
        print(f"Error checking {ticker}: {e}")