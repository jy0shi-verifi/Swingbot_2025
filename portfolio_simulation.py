import pandas as pd
import numpy as np
import yfinance as yf
from backtester import SilentBacktester
import matplotlib.pyplot as plt

# --- SETTINGS ---
UNIVERSE = ["SPY", "NVDA", "BTC-USD", "USO", "AAPL", "MSFT", "QQQ"]
START_CAPITAL = 10000
ALLOCATION_PER_TRADE = 0.10 
MAX_ACTIVE_TRADES = 3 # New: Prevents being over-leveraged in a crash

def run_portfolio_sim():
    print("Fetching universe data...")
    all_data = {}
    for ticker in UNIVERSE:
        bot = SilentBacktester(ticker, "2024-01-01", "2025-01-01")
        bot.fetch_data()
        bot.apply_strategy()
        all_data[ticker] = bot.data

    dates = all_data["SPY"].index
    cash = START_CAPITAL
    portfolio_value = []
    active_positions = {} 

    for date in dates:
        current_total_value = cash
        
        # 1. Update/Exit positions
        to_liquidate = []
        for ticker, pos in active_positions.items():
            current_price = all_data[ticker].loc[date, 'Close']
            current_atr = all_data[ticker].loc[date, 'ATR']
            # Using 3.0x ATR for more breathing room
            pos['stop'] = max(pos['stop'], current_price - (current_atr * 3.0))
            
            if current_price <= pos['stop'] or all_data[ticker].loc[date, 'Signal'] == 0:
                cash += (pos['shares'] * current_price) * (1 - 0.001)
                to_liquidate.append(ticker)
            else:
                current_total_value += (pos['shares'] * current_price)

        for ticker in to_liquidate:
            del active_positions[ticker]

        # 2. Entry (Only if we have less than MAX_ACTIVE_TRADES)
        if len(active_positions) < MAX_ACTIVE_TRADES:
            for ticker in UNIVERSE:
                if ticker not in active_positions and len(active_positions) < MAX_ACTIVE_TRADES:
                    row = all_data[ticker].loc[date]
                    if row['Signal'] == 1:
                        max_spend = current_total_value * ALLOCATION_PER_TRADE
                        if cash >= max_spend:
                            price = row['Close']
                            shares = int(max_spend // price)
                            if shares > 0:
                                cash -= (shares * price) * (1 + 0.001)
                                active_positions[ticker] = {
                                    'shares': shares,
                                    'stop': price - (row['ATR'] * 3.0)
                                }

        portfolio_value.append(current_total_value)

    final_df = pd.DataFrame({'Date': dates, 'Portfolio_Value': portfolio_value})
    final_df.set_index('Date', inplace=True)
    
    print(f"\n--- REFINED SIMULATION COMPLETE ---")
    print(f"Ending Capital: ${portfolio_value[-1]:.2f}")
    print(f"Total Return: {((portfolio_value[-1]/START_CAPITAL)-1)*100:.2f}%")
    
    final_df.plot(title="Refined Portfolio Simulation (Max 3 Trades)")
    plt.show()

if __name__ == "__main__":
    run_portfolio_sim()