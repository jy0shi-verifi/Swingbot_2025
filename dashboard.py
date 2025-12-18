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
load_dotenv() # This pulls the keys from the .env file

API_KEY = os.getenv("ALPACA_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET")
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

# --- CONNECTIONS ---
engine = sqlalchemy.create_engine('sqlite:///silent_swing.db')
alpaca = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)

# 1. DATABASE (History)
def load_db_history():
    try:
        df = pd.read_sql('trade_history', engine)
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
        st.error(f"Alpaca Connection Error: {e}")
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
    """
    Calculates exact Profit/Loss for every SOLD order.
    Ignores active holdings.
    """
    if history_df.empty:
        return pd.DataFrame()

    inventory = {}
    closed_trades = []
    
    # Process chronologically
    for index, row in history_df.iterrows():
        ticker = row['ticker']
        action = row['action']
        price = float(row['price'])
        qty = float(row['qty'])
        date = row['date']

        if "BUY" in action:
            # Weighted Average Cost Logic
            if ticker not in inventory:
                inventory[ticker] = {'qty': 0.0, 'cost': 0.0}
            
            curr_qty = inventory[ticker]['qty']
            curr_cost = inventory[ticker]['cost']
            
            # New avg cost = ((old_qty * old_cost) + (new_qty * new_price)) / total_qty
            new_cost = ((curr_qty * curr_cost) + (qty * price)) / (curr_qty + qty)
            inventory[ticker]['qty'] += qty
            inventory[ticker]['cost'] = new_cost
            
        elif "SELL" in action:
            if ticker in inventory and inventory[ticker]['qty'] > 0:
                avg_entry = inventory[ticker]['cost']
                # PnL = (Sell Price - Avg Entry) * Qty Sold
                pnl = (price - avg_entry) * qty
                
                closed_trades.append({
                    'Date': date,
                    'Ticker': ticker,
                    'Realized PnL': pnl
                })
                
                # Update inventory
                inventory[ticker]['qty'] -= qty
                if inventory[ticker]['qty'] < 0: inventory[ticker]['qty'] = 0

    if not closed_trades:
        return pd.DataFrame()

    df_closed = pd.DataFrame(closed_trades)
    df_closed['Cumulative PnL'] = df_closed['Realized PnL'].cumsum()
    return df_closed

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ Silent Swing")
    st.caption("v14.0 | Manager Mode")
    st.info(f"Server Time: **{datetime.now().strftime('%H:%M')}**")
    
    if st.button("🚀 Run Market Scan", type="primary"):
        with st.spinner("Scanning..."):
            subprocess.Popen([sys.executable, "main_autopilot.py"])
            st.success("Scan started!")
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

# --- MAIN LOGIC ---
st.title("Manager Control Room")

history_df = load_db_history()
active_df = get_live_positions()
account = alpaca.get_account()

# --- METRICS ---
total_equity = float(account.equity)
active_exposure = active_df['Value'].sum() if not active_df.empty else 0.0
start_balance = 100000.0 
ytd_pnl = total_equity - start_balance
buying_power = float(account.buying_power)

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
        fig_bal = px.area(curve_df, x='Date', y='Balance', title="Account Equity Over Time")
        fig_bal.update_traces(line_color='#00FF00', fillcolor='rgba(0, 255, 0, 0.1)')
        fig_bal.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_bal, use_container_width=True)
    else:
        st.info("Insufficient data.")

    # --- NEW CHART: Realized PnL (Sold Only) ---
    st.markdown("---")
    st.subheader("Realized Gains (Sold Orders Only)")
    realized_df = calculate_realized_performance(history_df)
    
    if not realized_df.empty:
        # Chart 1: Cumulative Realized PnL
        fig_real = px.line(realized_df, x='Date', y='Cumulative PnL', markers=True, title="Total Banked Profit/Loss")
        fig_real.update_traces(line_color='#00FFFF', line_width=3)
        fig_real.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_real.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_real, use_container_width=True)
        
        # Optional: Last 5 Closed Trades Table
        with st.expander("See Last 5 Closed Trades"):
            st.dataframe(realized_df.tail(5).sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.info("No closed trades yet. This chart will appear once you SELL a position.")

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