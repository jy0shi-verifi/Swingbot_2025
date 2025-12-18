import pandas as pd
import requests
from backtester import SilentBacktester
import datetime
from io import StringIO

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        table = pd.read_html(StringIO(response.text))
        return [t.replace('.', '-') for t in table[0]['Symbol'].tolist()]
    except:
        return ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL"]

UNIVERSE = get_sp500_tickers()
dips = []
breakouts = []

print(f"--- SILENT SWING: LIVE MARKET SCANNER ({datetime.date.today()}) ---")
print(f"Scanning {len(UNIVERSE)} Tickers... (Targeting Momentum & Panic)")

for ticker in UNIVERSE:
    try:
        # Fetch 60 days for accurate MA and Volume data
        bot = SilentBacktester(ticker, 
                               (datetime.datetime.now() - datetime.timedelta(days=60)).strftime('%Y-%m-%d'),
                               datetime.datetime.now().strftime('%Y-%m-%d'))
        bot.fetch_data()
        bot.apply_strategy()
        
        if bot.data.empty: continue
        
        last = bot.data.iloc[-1]
        
        info = {
            'ticker': ticker,
            'price': last['Close'],
            'rvol': last.get('RVOL', 0),
            'rsi': last['RSI'],
            'stop': last['Close'] - (last['ATR'] * 2.0)
        }
        
        # STRATEGY 1: MOMENTUM (The Big Winner)
        if last['RVOL'] > 1.5 and last['Close'] > last['Open'] and last['Close'] > last['MA20']:
            breakouts.append(info)
            
        # STRATEGY 2: OVERSOLD PANIC (The Reliable Dip)
        elif last['RSI'] < 30:
            dips.append(info)
            
    except:
        continue

print("\n" + "="*50)
print(f"✅ SCAN COMPLETE")
print("="*50)

breakouts.sort(key=lambda x: x['rvol'], reverse=True)
print(f"\n🚀 MOMENTUM BREAKOUTS (Target: Quick 5-10% move)")
print(f"{'TICKER':<8} | {'RVOL':<6} | {'PRICE':<8} | {'STOP':<8}")
print("-" * 40)
for i in breakouts[:5]:
    print(f"{i['ticker']:<8} | {i['rvol']:<6.1f} | ${i['price']:<7.2f} | ${i['stop']:<7.2f}")

dips.sort(key=lambda x: x['rsi'])
print(f"\n📉 PANIC DIPS (Target: Reversion Bounce)")
print(f"{'TICKER':<8} | {'RSI':<6} | {'PRICE':<8} | {'STOP':<8}")
print("-" * 40)
for i in dips[:5]:
    print(f"{i['ticker']:<8} | {i['rsi']:<6.1f} | ${i['price']:<7.2f} | ${i['stop']:<7.2f}")