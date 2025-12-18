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
    def send_msg(msg): print(f"[MOCK TELEGRAM] {msg}")

# --- CONFIGURATION (UPDATED) ---
MAX_DAILY_TRADES = 4           # Increased from 2 to catch more opportunities
ALLOCATION_PER_TRADE = 0.10    # Keeps risk distributed (10% per trade)

def get_market_universe():
    special_assets = [
        "BTC-USD", "ETH-USD", "GLD", "SLV", "USO", "UNG", 
        "TLT", "UUP", "VNQ", "EEM", "VIXY"
    ]
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        table = pd.read_html(StringIO(resp.text))
        sp500 = [t.replace('.', '-') for t in table[0]['Symbol'].tolist()]
        return list(set(sp500 + special_assets))
    except Exception as e:
        print(f"⚠️ Wikipedia Scraping Failed: {e}")
        return special_assets + ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL"]

def run_autopilot():
    start_time = datetime.datetime.now()
    print(f"\n--- AUTOPILOT WITH BRACKET PROTECTION ({start_time}) ---")
    send_msg(f"🤖 **Silent Swing Bot** scanning markets...")
    
    executor = AlpacaExecutor()
    if executor.get_buying_power() < 500:
        send_msg("⛔ Insufficient funds.")
        return

    print("🔎 Scanning Market...")
    universe = get_market_universe()
    
    momentum_candidates = []
    panic_candidates = []
    
    for ticker in universe:
        try:
            # Look back 60 days
            bot = SilentBacktester(ticker, 
                                   (datetime.datetime.now() - datetime.timedelta(days=60)).strftime('%Y-%m-%d'),
                                   datetime.datetime.now().strftime('%Y-%m-%d'))
            bot.fetch_data()
            bot.apply_strategy()
            if bot.data.empty: continue
            
            last = bot.data.iloc[-1]
            
            trade_package = {
                'ticker': ticker,
                'rvol': last.get('RVOL', 0),
                'rsi': last['RSI'],
                'close': last['Close'],
                'stop_price': last['Close'] - (last['ATR'] * 2.0)
            }
            
            # Strategy A: Momentum
            if last['RVOL'] > 1.5 and last['Close'] > last['MA20']:
                momentum_candidates.append(trade_package)
            
            # Strategy B: Panic Dip (UPDATED: RSI < 35)
            elif last['RSI'] < 35:
                panic_candidates.append(trade_package)
        except:
            continue
            
    # Sort for best quality
    momentum_candidates.sort(key=lambda x: x['rvol'], reverse=True)
    panic_candidates.sort(key=lambda x: x['rsi']) 
    
    # Select Targets (Up to MAX_DAILY_TRADES)
    final_targets = []
    
    # We alternate picking Momentum and Panic until we hit our limit of 4
    # This ensures a balanced mix of strategies
    combined_list = []
    for m in momentum_candidates[:4]: combined_list.append(m)
    for p in panic_candidates[:4]: combined_list.append(p)
    
    # Deduplicate and limit
    seen = set()
    for trade in combined_list:
        if trade['ticker'] not in seen and len(final_targets) < MAX_DAILY_TRADES:
            final_targets.append(trade)
            seen.add(trade['ticker'])
    
    if not final_targets:
        send_msg("✅ Scan Complete. No setups found.")
        return
    
    print(f"🎯 Targets Selected: {[t['ticker'] for t in final_targets]}")

    # Execute Trades
    for trade in final_targets:
        ticker = trade['ticker']
        stop = trade['stop_price']
        
        # Double Check Holdings
        if ticker in executor.get_current_positions():
            print(f"⚠️ Already holding {ticker}. Skipping.")
            continue

        if ticker in executor.get_pending_buy_symbols():
            print(f"⚠️ Pending BUY for {ticker}. Skipping.")
            continue
            
        print(f"🚀 EXECUTING BUY: {ticker}")
        executor.execute_buy(ticker, stop_price=stop, allocation_pct=ALLOCATION_PER_TRADE)
        
        alert_msg = (
            f"🚀 **EXECUTED: {ticker}**\n"
            f"💰 Price: ~${trade['close']:.2f}\n"
            f"🛑 Stop Loss: ${stop:.2f}\n"
            f"📊 Strategy: {'Momentum' if trade['rvol'] > 1.5 else 'Panic Dip (RSI < 35)'}"
        )
        send_msg(alert_msg)
        time.sleep(1)

    print("✅ Autopilot Cycle Complete.")

if __name__ == "__main__":
    run_autopilot()