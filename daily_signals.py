import pandas as pd
from backtester import SilentBacktester
import datetime

# Our approved 'Healthy' Universe
universe = ["SPY", "NVDA", "BTC-USD", "USO", "AAPL", "MSFT", "QQQ"]

print(f"--- SILENT SWING BOT: ACTION REPORT ({datetime.date.today()}) ---")
print(f"{'TICKER':<10} | {'SIGNAL':<12} | {'PRICE':<10} | {'RSI':<6}")
print("-" * 50)

for ticker in universe:
    try:
        # We look at the last 250 days to calculate the MA200 and RSI
        bot = SilentBacktester(ticker, 
                               (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'),
                               datetime.datetime.now().strftime('%Y-%m-%d'))
        df = bot.fetch_data()
        bot.apply_strategy()
        
        last_row = bot.data.iloc[-1]
        rsi_val = round(last_row['RSI'], 2)
        price = round(last_row['Close'], 2)
        
        # Determine the Actionable Advice
        if last_row['Signal'] == 1:
            action = "BUY / HOLD"
        else:
            action = "CASH / SELL"
            
        print(f"{ticker:<10} | {action:<12} | {price:<10} | {rsi_val:<6}")
        
    except Exception as e:
        print(f"Error checking {ticker}: {e}")