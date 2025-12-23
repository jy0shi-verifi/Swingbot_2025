import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
import subprocess
import sys
import os
from dotenv import load_dotenv

# --- LOAD SECRETS ---
load_dotenv()

# Load BOTH sets of keys
LIVE_KEY = os.getenv("ALPACA_KEY")
LIVE_SECRET = os.getenv("ALPACA_SECRET")
CHAMP_KEY = os.getenv("CHAMP_KEY")
CHAMP_SECRET = os.getenv("CHAMP_SECRET")
PAPER = os.getenv("ALPACA_PAPER") == "True"

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Silent Swing | Fund Terminal",
    layout="wide",
    page_icon="💸",
    initial_sidebar_state="expanded"
)

# --- STYLE ---
st.markdown("""
<style>
    .stMetric {background-color: #141414; border-radius: 8px; padding: 15px; border: 1px solid #333;}
    div[data-testid="stDataFrame"] {border: 1px solid #333; border-radius: 5px; overflow: hidden;}
    button[data-baseweb="tab"] {font-weight: 600;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR & CONNECTION SWITCHER ---
with st.sidebar:
    st.title("⚡ Silent Swing")

    # 1. READ URL: Check if ?bot=Champion is in the address bar
    # (Default to "Live" if nothing is there)
    query_params = st.query_params
    default_index = 0
    if "bot" in query_params and query_params["bot"] == "Champion":
        default_index = 1

    # 2. THE SWITCHER: Use the index from the URL
    bot_choice = st.selectbox(
        "🔌 Select Bot Engine:",
        ["🔴 Live Aggressive", "🟢 Champion Safe"],
        index=default_index
    )

    # 3. WRITE URL: Update the address bar when you switch
    if bot_choice == "🟢 Champion Safe":
        st.query_params["bot"] = "Champion"
    else:
        st.query_params["bot"] = "Live"

    # DYNAMIC CONNECTION LOGIC
    if bot_choice == "🔴 Live Aggressive":
        db_path = 'silent_swing.db'
        active_key = LIVE_KEY
        active_secret = LIVE_SECRET
    else:
        db_path = '../Swingbot_Champ/champion_swing.db'
        active_key = CHAMP_KEY
        active_secret = CHAMP_SECRET

    st.caption(f"Connected to: {db_path}")
    st.markdown("---")

    st.info(f"Server Time: **{datetime.now().strftime('%H:%M')}**")

    if st.button("🚀 Run Market Scan", type="primary"):
        with st.spinner("Scanning..."):
            subprocess.Popen([sys.executable, "main_autopilot.py"])
            st.success("Scan started!")
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

# --- INITIALIZE CLIENTS WITH SELECTED KEYS ---
try:
    engine = sqlalchemy.create_engine(f'sqlite:///{db_path}')
    alpaca = TradingClient(active_key, active_secret, paper=PAPER)
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# 1. DATABASE (History)
def load_db_history():
    try:
        if not os.path.exists(db_path): return pd.DataFrame(columns=['date', 'ticker', 'action', 'price', 'qty'])
        # Try finding the table, fallback if needed or just use 'trade_history' as default
        # Based on your previous checks, both DBs seem to use 'trade_history' now.
        try:
            df = pd.read_sql('trade_history', engine)
        except:
            # Fallback for older live db versions if they revert
            df = pd.read_sql('trades', engine)
            
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date', ascending=True)
    except:
        return pd.DataFrame(columns=['date', 'ticker', 'action', 'price', 'qty'])

# 2. ALPACA (Live Truth)
def get_live_positions():
    try:
        positions = alpaca.get_all_positions()
        data = []
        for p in positions:
            data.append({
                "Ticker": p.symbol,
                "Qty": float(p.qty),
                "Entry": float(p.avg_entry_price),
                "Price": float(p.current_price),
                "Value": float(p.market_value),
                "PnL": float(p.unrealized_pl),
                "ROI": float(p.unrealized_plpc) * 100
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_pending_orders():
    try:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=50)
        orders = alpaca.get_orders(filter=req)
        return [{
            "Date": o.created_at,
            "Ticker": o.symbol,
            "Action": "⏳ " + o.side.value.upper(),
            "Qty": float(o.qty),
            "Price": 0.0,
            "Value": 0.0
        } for o in orders]
    except:
        return []

# --- ENGINE: Balance Curve ---
def calculate_equity_curve(history_df, current_equity):
    if history_df.empty:
        return pd.DataFrame([{'Date': datetime.now(), 'Balance': 100000.0}])

    curve = []
    running_equity = current_equity
    history_rev = history_df.sort_values('date', ascending=False)

    curve.append({'Date': datetime.now(), 'Balance': running_equity})
    for _, row in history_rev.iterrows():
        curve.append({'Date': row['date'], 'Balance': running_equity})

    return pd.DataFrame(curve).sort_values('Date')

# --- ENGINE: Realized PnL (Sold Only) ---
def calculate_realized_performance(history_df):
    if history_df.empty:
        return pd.DataFrame()

    inventory = {}
    closed_trades = []

    for index, row in history_df.iterrows():
        ticker = row['ticker']
        action = row['action']
        price = float(row['price'])
        qty = float(row['qty'])
        date = row['date']

        if "BUY" in action:
            if ticker not in inventory:
                inventory[ticker] = {'qty': 0.0, 'cost': 0.0}

            curr_qty = inventory[ticker]['qty']
            curr_cost = inventory[ticker]['cost']

            new_cost = ((curr_qty * curr_cost) + (qty * price)) / (curr_qty + qty)
            inventory[ticker]['qty'] += qty
            inventory[ticker]['cost'] = new_cost

        elif "SELL" in action:
            if ticker in inventory and inventory[ticker]['qty'] > 0:
                avg_entry = inventory[ticker]['cost']
                pnl = (price - avg_entry) * qty

                closed_trades.append({
                    'Date': date,
                    'Ticker': ticker,
                    'Realized PnL': pnl
                })

                inventory[ticker]['qty'] -= qty
                if inventory[ticker]['qty'] < 0: inventory[ticker]['qty'] = 0

    if not closed_trades:
        return pd.DataFrame()

    df_closed = pd.DataFrame(closed_trades)
    df_closed['Cumulative PnL'] = df_closed['Realized PnL'].cumsum()
    return df_closed

# --- MAIN LOGIC ---
st.title(f"Control Room: {bot_choice}")

history_df = load_db_history()
active_df = get_live_positions()

try:
    account = alpaca.get_account()
    total_equity = float(account.equity)
    buying_power = float(account.buying_power)
except:
    total_equity = 100000.0
    buying_power = 0.0

# --- METRICS ---
active_exposure = active_df['Value'].sum() if not active_df.empty else 0.0
start_balance = 100000.0
ytd_pnl = total_equity - start_balance

c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio Balance", f"${total_equity:,.2f}", help="Cash + Stock Value")
c2.metric("Active Exposure", f"${active_exposure:,.2f}", help="Cash in Stocks")
c3.metric("YTD Profit/Loss", f"${ytd_pnl:,.2f}", delta_color="normal")
c4.metric("Buying Power", f"${buying_power:,.2f}", help="Available Leverage")

# --- TABS ---
tab_market, tab_perf, tab_ledger = st.tabs(["📊 Market Overview", "📈 Portfolio Performance", "📜 Transaction Ledger"])

# TAB 1: MARKET OVERVIEW
with tab_market:
    col_alloc, col_stats = st.columns(2)
    with col_alloc:
        st.subheader("Asset Allocation")
        if not active_df.empty:
            fig_pie = px.pie(active_df, values='Value', names='Ticker', hole=0.6,
                             color_discrete_sequence=px.colors.qualitative.Bold)
            fig_pie.update_traces(textposition='inside', textinfo='label+percent')
            fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Portfolio is 100% Cash.")

    with col_stats:
        st.subheader("Current Win/Loss Status")
        if not active_df.empty:
            wins = active_df[active_df['PnL'] > 0].shape[0]
            losses = active_df[active_df['PnL'] < 0].shape[0]
            status_data = pd.DataFrame({'Status': ['Winning', 'Losing'], 'Count': [wins, losses]})
            if wins + losses > 0:
                fig_donut = px.pie(status_data, values='Count', names='Status', hole=0.6,
                                   color='Status',
                                   color_discrete_map={'Winning':'#00FF00', 'Losing':'#FF4B4B'})
                fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300, showlegend=True)
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("Positions are flat.")
        else:
            st.write("No active trades.")

    st.subheader("Active Positions Ledger")
    if not active_df.empty:
        def color_pnl(val):
            if val > 0.001: return 'color: #00FF00'
            elif val < -0.001: return 'color: #FF4B4B'
            return 'color: #FFFFFF'
        st.dataframe(
            active_df[['Ticker', 'Qty', 'Entry', 'Price', 'Value', 'PnL', 'ROI']].style
            .format({'Entry': '${:,.2f}', 'Price': '${:,.2f}', 'Value': '${:,.2f}', 'PnL': '${:+,.2f}', 'ROI': '{:+.2f}%'})
            .applymap(color_pnl, subset=['PnL', 'ROI']),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No active positions.")

# TAB 2: PERFORMANCE
with tab_perf:
    st.subheader("Total Balance Growth")
    curve_df = calculate_equity_curve(history_df, total_equity)
    if not curve_df.empty:
        # Green for Champ, Red/White for Live
        line_col = '#00FF00' if "Champion" in bot_choice else '#FF4B4B'

        fig_bal = px.area(curve_df, x='Date', y='Balance', title="Account Equity Over Time")
        # Restored original color logic exactly as it was working before
        fig_bal.update_traces(line_color=line_col, fillcolor=f'rgba({0 if "Champion" in bot_choice else 255}, {255 if "Champion" in bot_choice else 75}, 75, 0.1)')
        fig_bal.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_bal, use_container_width=True)
    else:
        st.info("Insufficient data.")

    st.markdown("---")
    st.subheader("Realized Gains (Sold Orders Only)")
    realized_df = calculate_realized_performance(history_df)

    if not realized_df.empty:
        fig_real = px.line(realized_df, x='Date', y='Cumulative PnL', markers=True, title="Total Banked Profit/Loss")
        fig_real.update_traces(line_color='#00FFFF', line_width=3)
        fig_real.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_real.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_real, use_container_width=True)

        with st.expander("See Last 5 Closed Trades"):
            st.dataframe(realized_df.tail(5).sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.info("No closed trades yet.")

# TAB 3: LEDGER
with tab_ledger:
    st.subheader("Transaction History")
    pending_df = pd.DataFrame(get_pending_orders())
    t1, t2, t3, t4 = st.tabs(["📜 All Activity", "⏳ Pending", "🟢 Entries", "🔴 Exits"])
    cfg = {"date": st.column_config.DatetimeColumn("Time", format="MMM DD, HH:mm"), "price": "$%.2f", "Value": "$%.2f"}

    with t1:
        if not history_df.empty:
            df_disp = history_df.sort_values('date', ascending=False).copy()
            df_disp['Value'] = df_disp['price'] * df_disp['qty']
            df_disp['Action'] = df_disp['action'].apply(lambda x: "🟢 BUY" if "BUY" in x else "🔴 SELL")
            st.dataframe(df_disp[['date', 'ticker', 'Action', 'qty', 'price', 'Value']], column_config=cfg, use_container_width=True, hide_index=True)
    with t2:
        if not pending_df.empty:
            st.dataframe(pending_df, column_config=cfg, use_container_width=True, hide_index=True)
        else:
            st.info("No pending orders.")
    with t3:
        if not history_df.empty:
            st.dataframe(df_disp[df_disp['Action'].str.contains("BUY")], column_config=cfg, use_container_width=True, hide_index=True)
    with t4:
        if not history_df.empty:
            st.dataframe(df_disp[df_disp['Action'].str.contains("SELL")], column_config=cfg, use_container_width=True, hide_index=True)
