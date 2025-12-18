import pandas as pd
import requests
from backtester import SilentBacktester
import datetime
from io import StringIO

# --- 1. Get the S&P 500 List ---
def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        table = pd.read_html(StringIO(response.text))
        tickers = table[0]['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except:
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "SPY", "QQQ", "IWM"]

UNIVERSE = get_sp500_tickers()

# --- 2. Scanning Buckets ---
dips = []
breakouts = []
reclaims = []

print(f"--- SWING TRADER'S DAILY ACTION REPORT ({datetime.date.today()}) ---")
print(f"Scanning {len(UNIVERSE)} Tickers... (This may take 2-3 minutes)")

for ticker in UNIVERSE:
    try:
        # Fetching strictly the recent data
        bot = SilentBacktester(ticker, 
                               (datetime.datetime.now() - datetime.timedelta(days=60)).strftime('%Y-%m-%d'),
                               datetime.datetime.now().strftime('%Y-%m-%d'))
        bot.fetch_data()
        bot.apply_strategy()
        
        if bot.data.empty: continue
        
        last = bot.data.iloc[-1]
        setup = last['Setup']
        
        info = {
            'ticker': ticker,
            'price': last['Close'],
            'rvol': last.get('RVOL', 0),
            'rsi': last['RSI'],
            'stop': last['Close'] - (last['ATR'] * 2.0) # Standard 2x ATR Swing Stop
        }
        
        if setup == 'OVERSOLD_DIP':
            dips.append(info)
        elif setup == 'MOMENTUM_BREAK':
            breakouts.append(info)
        elif setup == 'TREND_RECLAIM':
            reclaims.append(info)
            
    except Exception as e:
        continue

# --- 3. The Report ---

print("\n" + "="*60)
print(f"REPORT COMPLETE")
print("="*60)

# Sort Breakouts by highest Relative Volume
breakouts.sort(key=lambda x: x['rvol'], reverse=True)
print(f"\n🚀 MOMENTUM BREAKOUTS (High Volume + Uptrend) - Found: {len(breakouts)}")
print(f"{'TICKER':<8} | {'RVOL':<6} | {'PRICE':<8} | {'STOP':<8}")
print("-" * 40)
for i in breakouts[:5]:
    print(f"{i['ticker']:<8} | {i['rvol']:<6.1f} | ${i['price']:<7.2f} | ${i['stop']:<7.2f}")

# Sort Dips by lowest RSI
dips.sort(key=lambda x: x['rsi'])
print(f"\n📉 OVERSOLD DIPS (RSI < 30) - Found: {len(dips)}")
print(f"{'TICKER':<8} | {'RSI':<6} | {'PRICE':<8} | {'STOP':<8}")
print("-" * 40)
for i in dips[:5]:
    print(f"{i['ticker']:<8} | {i['rsi']:<6.1f} | ${i['price']:<7.2f} | ${i['stop']:<7.2f}")

# Sort Reclaims by RSI
reclaims.sort(key=lambda x: x['rsi'])
print(f"\n♻️ TREND RECLAIMS (Crossed above MA20) - Found: {len(reclaims)}")
print(f"{'TICKER':<8} | {'RSI':<6} | {'PRICE':<8} | {'STOP':<8}")
print("-" * 40)
for i in reclaims[:5]:
    print(f"{i['ticker']:<8} | {i['rsi']:<6.1f} | ${i['price']:<7.2f} | ${i['stop']:<7.2f}")