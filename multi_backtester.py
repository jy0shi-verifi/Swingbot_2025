import pandas as pd
from backtester import SilentBacktester

# Define our "Universe" of different asset classes
# SPY (Stocks), GLD (Gold), TLT (Bonds), BTC-USD (Crypto), USO (Oil)
universe = ["SPY", "GLD", "TLT", "BTC-USD", "USO", "AAPL", "MSFT"]

results = []

print("--- STARTING UNIVERSE TEST ---")

for ticker in universe:
    try:
        # We reuse our class from the first file
        bot = SilentBacktester(ticker, "2023-01-01", "2025-01-01")
        bot.fetch_data()
        bot.apply_strategy()
        bot.run_backtest()
        
        # Pull metrics from the bot data
        final_val = bot.data['Cumulative_Strategy'].iloc[-1]
        returns = bot.data['Strategy_Return'].replace(0, pd.NA).dropna()
        sharpe = (returns.mean() / returns.std()) * (252**0.5) if len(returns) > 0 else 0
        
        results.append({
            "Ticker": ticker,
            "Final_Value": round(final_val, 2),
            "Sharpe": round(sharpe, 2)
        })
    except Exception as e:
        print(f"Error testing {ticker}: {e}")

# Final Summary Table
summary_df = pd.DataFrame(results)
print("\n--- UNIVERSE SUMMARY ---")
print(summary_df.to_string(index=False))

summary_df.to_csv("universe_results.csv", index=False)