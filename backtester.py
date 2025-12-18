import pandas as pd
import numpy as np
import yfinance as yf

class SilentBacktester:
    def __init__(self, ticker, start_date, end_date, initial_capital=10000, fee=0.001):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.fee_rate = fee
        self.data = None

    def fetch_data(self):
        # We need 40 days of history to calculate average volume properly
        start_dt = pd.to_datetime(self.start_date) - pd.Timedelta(days=40)
        df = yf.download(self.ticker, start=start_dt, end=self.end_date, progress=False)
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
        self.data = df
        return self.data

    def apply_strategy(self):
        df = self.data.copy()
        
        # 1. Indicators
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        
        # RSI (7-period for speed)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # RVOL (Relative Volume)
        df['AvgVol'] = df['Volume'].rolling(window=20).mean()
        df['RVOL'] = df['Volume'] / df['AvgVol']
        
        # Volatility (ATR)
        high_low = df['High'] - df['Low']
        df['ATR'] = high_low.rolling(14).mean()

        # 2. Strategy Classification
        df['Setup'] = 'None'
        
        # Setup A: Oversold Bounce (Panic)
        df.loc[df['RSI'] < 30, 'Setup'] = 'OVERSOLD_DIP'
        
        # Setup B: Momentum Breakout (Volume Rush)
        # High Volume + Price Up + Price above MA20
        df.loc[(df['RVOL'] > 1.5) & (df['Close'] > df['Open']) & (df['Close'] > df['MA20']), 'Setup'] = 'MOMENTUM_BREAK'
        
        # Setup C: Trend Reclaim (Crossing the line)
        # Yesterday was below MA20, Today is above MA20
        df.loc[(df['Close'] > df['MA20']) & (df['Close'].shift(1) < df['MA20'].shift(1)), 'Setup'] = 'TREND_RECLAIM'

        self.data = df.loc[self.start_date:]