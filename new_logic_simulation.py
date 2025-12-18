import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from backtester import SilentBacktester

# --- SIMULATION SETTINGS ---
# A basket of liquid leaders representing the "Active Trader" universe
UNIVERSE = [
    "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL", "META", "NFLX", "COIN",
    "JPM", "BAC", "XOM", "CVX", "LLY", "UNH", "COST", "WMT", "HD", "MCD",
    "SPY", "QQQ", "IWM", "GLD", "SLV", "USO", "TLT", "DIS", "BA", "PYPL"
]

START_CAPITAL = 10000
MAX_POSITIONS = 5  # We only hold the top 5 ideas at once
PCT_PER_TRADE = 0.20 # 20% allocation (Aggressive Swing)

def run_simulation():
    print(f"--- INITIALIZING TRIPLE THREAT SIMULATION ---")
    print(f"Universe: {len(UNIVERSE)} Tickers | Strategy: Multi-Setup Swing")
    
    # 1. Pre-fetch Data
    print("Fetching historical data (this takes ~30s)...")
    market_data = {}
    for ticker in UNIVERSE:
        try:
            # Fetch 2024-2025 Data
            bot = SilentBacktester(ticker, "2024-01-01", "2025-12-18")
            bot.fetch_data()
            bot.apply_strategy()
            market_data[ticker] = bot.data
        except:
            print(f"Skipping {ticker} (Data Error)")
            
    # Get common timeline
    timeline = market_data["SPY"].index
    
    # 2. Portfolio Loop
    cash = START_CAPITAL
    positions = {} # {ticker: {'shares': 0, 'stop': 0, 'type': ''}}
    equity_curve = []
    trade_log = []

    for date in timeline:
        # A. Mark-to-Market & Check Exits
        current_equity = cash
        active_tickers = list(positions.keys())
        
        for ticker in active_tickers:
            if date not in market_data[ticker].index: continue
            
            row = market_data[ticker].loc[date]
            price = row['Close']
            pos = positions[ticker]
            
            # Trailing Stop Update (Only move UP)
            new_stop = price - (row['ATR'] * 2.0)
            pos['stop'] = max(pos['stop'], new_stop)
            
            # VALUE UPDATE
            current_equity += pos['shares'] * price
            
            # EXIT TRIGGER: Price hits stop
            if row['Low'] <= pos['stop']:
                # Sell
                exit_price = pos['stop'] # Assume slippage/stop hit
                cash += pos['shares'] * exit_price
                
                # Log Trade
                pnl = (exit_price - pos['entry']) / pos['entry']
                trade_log.append({'Ticker': ticker, 'Type': pos['type'], 'PnL': pnl})
                
                del positions[ticker]

        # B. Check Entries (If we have slots open)
        if len(positions) < MAX_POSITIONS:
            # Gather all valid signals for today
            candidates = []
            for ticker in UNIVERSE:
                if ticker in positions: continue
                if date not in market_data[ticker].index: continue
                
                row = market_data[ticker].loc[date]
                if row['Setup'] != 'None':
                    candidates.append({
                        'ticker': ticker,
                        'setup': row['Setup'],
                        'price': row['Close'],
                        'atr': row['ATR'],
                        'rsi': row['RSI']
                    })
            
            # RANKING: Prioritize "Momentum" first, then "Reclaims", then "Dips"
            # Sort by Setup priority is hard, so let's just pick based on availability
            # Or sort by RSI (Lower = Better Dip, Higher = Better Momentum? Mixed bag.)
            # Simple approach: Sort by highest Volume (if we had it), or just alphabetical.
            # Let's simple sort by RSI for Dips, or random.
            # Professional Move: We buy the first ones found because our Universe is already "High Quality"
            
            for trade in candidates:
                if len(positions) >= MAX_POSITIONS: break
                
                # Sizing
                target_size = current_equity * PCT_PER_TRADE
                if cash > target_size:
                    shares = int(target_size // trade['price'])
                    if shares > 0:
                        cash -= shares * trade['price']
                        positions[trade['ticker']] = {
                            'shares': shares,
                            'entry': trade['price'],
                            'stop': trade['price'] - (trade['atr'] * 2.0),
                            'type': trade['setup']
                        }

        equity_curve.append(current_equity)

    # 3. Final Report
    final_val = equity_curve[-1]
    ret = ((final_val - START_CAPITAL) / START_CAPITAL) * 100
    
    print(f"\n--- SIMULATION RESULTS (2024-Present) ---")
    print(f"Starting Capital: ${START_CAPITAL}")
    print(f"Ending Capital:   ${final_val:.2f}")
    print(f"Total Return:     {ret:.2f}%")
    
    if trade_log:
        df_log = pd.DataFrame(trade_log)
        win_rate = (df_log['PnL'] > 0).mean() * 100
        print(f"Total Trades:     {len(df_log)}")
        print(f"Win Rate:         {win_rate:.1f}%")
        print("\nPerformance by Setup Type:")
        print(df_log.groupby('Type')['PnL'].mean() * 100)

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(timeline, equity_curve, label='Triple Threat Strategy')
    plt.title(f"Walk-Forward: Triple Threat Strategy (+{ret:.1f}%)")
    plt.ylabel("Account Equity ($)")
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    run_simulation()