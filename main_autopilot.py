import pandas as pd
import datetime
import time
from backtester import SilentBacktester
from alpaca_manager import AlpacaExecutor
import requests
from io import StringIO

# --- INTEGRATIONS ---
try:
    from notifier import send_msg
except ImportError:
    print("⚠️ 'notifier.py' not found. Telegram alerts disabled.")
    def send_msg(msg): print(f"[MOCK TELEGRAM] {msg}")

# --- CONFIGURATION ---
MAX_DAILY_TRADES = 2 
ALLOCATION_PER_TRADE = 0.10 

def get_market_universe():
    """
    Step 3: The 'Uncorrelated Alpha' Universe.
    Combines S&P 500 stocks with Crypto, Commodities, and Hedges.
    """
    special_assets = [
        "BTC-USD", "ETH-USD",       # Crypto (Weekend/Risk-On)
        "GLD", "SLV", "USO", "UNG", # Commodities (Inflation/Fear)
        "TLT", "UUP",               # Bonds & Dollar (Flight to Safety)
        "VNQ", "EEM",               # Real Estate & Emerging Markets
        "VIXY"                      # Volatility Hedge
    ]
    
    try:
        # Fetch S&P 500 dynamically
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        table = pd.read_html(StringIO(resp.text))
        sp500 = [t.replace('.', '-') for t in table[0]['Symbol'].tolist()]
        
        # Combine and deduplicate
        full_list = sp500 + special_assets
        return list(set(full_list))
    except Exception as e:
        print(f"⚠️ Wikipedia Scraping Failed: {e}")
        return special_assets + ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL"]

def run_autopilot():
    start_time = datetime.datetime.now()
    print(f"\n--- AUTOPILOT WITH BRACKET PROTECTION ({start_time}) ---")
    send_msg(f"🤖 **Silent Swing Bot** started scanning at {start_time.strftime('%H:%M')}...")
    
    executor = AlpacaExecutor()
    buying_power = executor.get_buying_power()
    
    if buying_power < 500:
        msg = f"⛔ Insufficient funds: ${buying_power:,.2f}"
        print(msg)
        send_msg(msg)
        return

    print("🔎 Scanning Market for Setup + Risk Levels...")
    universe = get_market_universe()
    
    momentum_candidates = []
    panic_candidates = []
    
    # Scanning entire universe
    scan_list = universe 
    
    for ticker in scan_list:
        try:
            # We look back 60 days to establish trend and average volume
            bot = SilentBacktester(ticker, 
                                   (datetime.datetime.now() - datetime.timedelta(days=60)).strftime('%Y-%m-%d'),
                                   datetime.datetime.now().strftime('%Y-%m-%d'))
            bot.fetch_data()
            bot.apply_strategy()
            if bot.data.empty: continue
            
            last = bot.data.iloc[-1]
            
            # Pack data for the Order Logic
            trade_package = {
                'ticker': ticker,
                'rvol': last.get('RVOL', 0),
                'rsi': last['RSI'],
                'close': last['Close'],
                'stop_price': last['Close'] - (last['ATR'] * 2.0) # 2x ATR Trailing Stop
            }
            
            # Strategy A: Momentum (RVOL > 1.5 + Uptrend)
            if last['RVOL'] > 1.5 and last['Close'] > last['MA20']:
                momentum_candidates.append(trade_package)
            # Strategy B: Panic Dip (RSI < 30)
            elif last['RSI'] < 30:
                panic_candidates.append(trade_package)
        except:
            continue
            
    # Sort to find the "Best Available"
    momentum_candidates.sort(key=lambda x: x['rvol'], reverse=True)
    panic_candidates.sort(key=lambda x: x['rsi']) 
    
    final_targets = []
    # We take the #1 Momentum Play and #1 Panic Play
    if momentum_candidates: final_targets.append(momentum_candidates[0])
    if panic_candidates: final_targets.append(panic_candidates[0])
    
    target_tickers = [t['ticker'] for t in final_targets]
    print(f"🎯 Targets Selected: {target_tickers}")
    
    if not final_targets:
        send_msg("✅ Scan Complete. No valid setups found today.")
    
    # Execute Trades
    for trade in final_targets:
        ticker = trade['ticker']
        stop = trade['stop_price']
        price = trade['close']
        
        # 1. Check Holdings (Do we own it?)
        if ticker in executor.get_current_positions():
            print(f"⚠️ Already holding {ticker}. Skipping.")
            continue

        # 2. Check Pending Orders (Are we trying to buy it?)
        if ticker in executor.get_pending_buy_symbols():
            print(f"⚠️ Pending BUY order found for {ticker}. Skipping to avoid duplicate.")
            continue
            
        print(f"🚀 EXECUTING BRACKET BUY: {ticker}")
        
        # Execute Order
        executor.execute_buy(ticker, stop_price=stop, allocation_pct=ALLOCATION_PER_TRADE)
        
        # Send Notification
        alert_msg = (
            f"🚀 **EXECUTED: {ticker}**\n"
            f"💰 Price: ~${price:.2f}\n"
            f"🛑 Stop Loss: ${stop:.2f}\n"
            f"📊 Strategy: {'Momentum' if trade['rvol'] > 1.5 else 'Panic Dip'}"
        )
        send_msg(alert_msg)
        
        time.sleep(1)

    print("✅ Autopilot Cycle Complete.")

if __name__ == "__main__":
    run_autopilot()