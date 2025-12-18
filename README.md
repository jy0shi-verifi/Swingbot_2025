# 🤖 Silent Swing Bot - Documentation

## 1. Core Architecture
| Script | Function |
| :--- | :--- |
| `backtester.py` | **The Brain.** Contains the strategy logic (RSI, RVOL, ATR). |
| `alpaca_manager.py` | **The Hands.** Connects to Alpaca API to execute Bracket Orders. |
| `main_autopilot.py` | **The Captain.** Runs the scan, picks top 2 stocks, and orders the execution. |
| `dashboard.py` | **The Eyes.** Web interface to monitor trades and performance. |

## 2. Strategy Logic ("The Triple Threat")
* **🚀 Momentum:** Buy when Relative Volume > 1.5 and Price > 20-Day MA.
* **📉 Panic Dip:** Buy when RSI(7) < 30.
* **Risk Management:** 2x ATR Trailing Stop (Calculated dynamically).
* **Profit Taking:** +15% Limit Order (Moonshot).

## 3. Operations Guide
* **To Run Manually:** `python main_autopilot.py`
* **To View Dashboard:** `streamlit run dashboard.py`
* **To Reset Database:** Delete `silent_swing.db`

## 4. Troubleshooting
* **"Insufficient Funds":** Check Alpaca paper balance. Bot requires >$500.
* **"Module Not Found":** Run `pip install -r requirements.txt`.