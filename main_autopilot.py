import pandas as pd
import datetime
import time
from backtester import SilentBacktester
from alpaca_manager import AlpacaExecutor
import requests
from io import StringIO
from notifier import send_msg

# --- CONFIGURATION ---
MAX_DAILY_TRADES = 4           
ALLOCATION_PER_TRADE = 0.10    

def get_market_universe():
    special_assets = ["BTC-USD", "ETH-USD", "GLD", "SLV", "USO", "UNG", "TLT", "VIXY"]
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
    send_msg("🔍 **MORNING SCAN STARTING**\nSearching 500+ tickers for Momentum and Panic setups...")
    
    executor = AlpacaExecutor()
    if executor.get_buying_power() < 500:
        send_msg("⛔ **Scan Aborted:** Insufficient funds in Alpaca account.")
        return

    universe = get_market_universe()
    momentum_candidates = []
    panic_candidates = []
    
    for ticker in universe:
        try:
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
            
            if last['RVOL'] > 1.5 and last['Close'] > last['MA20']:
                momentum_candidates.append(trade_package)
            elif last['RSI'] < 35:
                panic_candidates.append(trade_package)
        except:
            continue
            
    momentum_candidates.sort(key=lambda x: x['rvol'], reverse=True)
    panic_candidates.sort(key=lambda x: x['rsi']) 
    
    final_targets = []
    combined_list = momentum_candidates[:4] + panic_candidates[:4]
    seen = set()
    for trade in combined_list:
        if trade['ticker'] not in seen and len(final_targets) < MAX_DAILY_TRADES:
            final_targets.append(trade)
            seen.add(trade['ticker'])
    
    if not final_targets:
        send_msg("✅ **SCAN COMPLETE**\nNo high-probability setups found today.")
        return
    
    send_msg(f"🎯 **TARGETS FOUND:** {', '.join([t['ticker'] for t in final_targets])}\nPreparing execution...")

    for trade in final_targets:
        ticker = trade['ticker']
        stop = trade['stop_price']
        
        if ticker in executor.get_current_positions():
            continue

        if ticker in executor.get_pending_buy_symbols():
            continue
            
        executor.execute_buy(ticker, stop_price=stop, allocation_pct=ALLOCATION_PER_TRADE)
        
        alert_msg = (
            f"🚀 **EXECUTED: {ticker}**\n"
            f"💰 Price: ~${trade['close']:.2f}\n"
            f"🛑 Stop Loss: ${stop:.2f}\n"
            f"📊 Strategy: {'Momentum' if trade['rvol'] > 1.5 else 'Panic Dip'}"
        )
        send_msg(alert_msg)
        time.sleep(1)

    print("✅ Autopilot Cycle Complete.")

if __name__ == "__main__":
    send_msg("🚀 **Autopilot Engaged**\nStarting daily 9:35 AM market scan...")
    run_autopilot()
