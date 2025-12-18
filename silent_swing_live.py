import pandas as pd
from backtester import SilentBacktester
import datetime

UNIVERSE = ["SPY", "NVDA", "BTC-USD", "USO", "AAPL", "MSFT", "QQQ"]
TOTAL_CAPITAL = 11158 # Your current simulated capital
MAX_PER_TICKER = 0.10

print(f"--- SILENT SWING BOT: LIVE COMMAND CENTER ({datetime.date.today()}) ---")
print(f"{'TICKER':<10} | {'ACTION':<12} | {'PRICE':<10} | {'STOP-LOSS':<10} | {'SHARES'}")
print("-" * 65)

for ticker in UNIVERSE:
    try:
        # Fetch data up to today
        bot = SilentBacktester(ticker, 
                               (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'),
                               datetime.datetime.now().strftime('%Y-%m-%d'))
        bot.fetch_data()
        bot.apply_strategy()
        
        last = bot.data.iloc[-1]
        price = last['Close']
        atr_stop = price - (last['ATR'] * 4.0)
        
        if last['Close'] > last['MA50']:
            action = "BUY/HOLD"
            shares = int((TOTAL_CAPITAL * MAX_PER_TICKER) // price)
        else:
            action = "CASH/SELL"
            shares = 0
            atr_stop = 0
            
        print(f"{ticker:<10} | {action:<12} | ${price:<9.2f} | ${atr_stop:<9.2f} | {shares}")
        
    except Exception as e:
        print(f"Error checking {ticker}: {e}")