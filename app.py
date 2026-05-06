import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ===================== CONFIG =====================
st.set_page_config(page_title="Velocity Trading Journal", layout="wide")
st.title("🔑 Velocity Trading Journal")
st.markdown("**Professional Options & Stock Trading Journal**")

# Google Sheets Connection
@st.cache_resource
def get_google_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
    return client.open("Trading Journal").worksheet("Sheet1")  # Change sheet name if needed

sheet = get_google_sheet()

def load_trades():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['PnL'] = pd.to_numeric(df.get('PnL', 0), errors='coerce')
    return df

def save_trade(trade_dict):
    sheet.append_row(list(trade_dict.values()), value_input_option="RAW")

# ===================== HEADERS =====================
COLUMNS = [
    "Date", "Time", "Instrument", "Strategy", "Expiry", "Strike", 
    "Position Size", "Entry", "Exit", "PnL", "R_Multiple",
    "Market Bias", "Setup Type", "Indicators", "Volatility Context", 
    "Expected Move", "Time Horizon", "Stop Loss", "Target", "RR Ratio",
    "Did you follow your plan?", "Slippage / Adjustment", 
    "Emotion Before", "Emotion During", "Emotion After",
    "What Worked", "What Failed", "Improvement"
]

# ===================== UI =====================
tab1, tab2, tab3 = st.tabs(["📝 New Trade", "📊 Trade History", "📈 Analytics"])

# ------------------- TAB 1: New Trade -------------------
with tab1:
    st.header("Log New Trade")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date = st.date_input("Date", datetime.now().date())
        time = st.time_input("Time", datetime.now().time())
        instrument = st.selectbox("Instrument", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "STOCK", "Other"])
        strategy = st.text_input("Strategy (e.g., Bull Call Spread)")
        expiry = st.text_input("Expiry (e.g., 28-May-2026)")
        strike = st.text_input("Strike Prices")
    
    with col2:
        pos_size = st.number_input("Position Size (lots/shares)", min_value=1, value=1)
        entry = st.number_input("Entry Price", format="%.2f", value=0.0)
        exit_price = st.number_input("Exit Price", format="%.2f", value=0.0)
        stop_loss = st.number_input("Stop Loss", format="%.2f")
        target = st.number_input("Target", format="%.2f")
    
    with col3:
        bias = st.selectbox("Market Bias", ["Bullish", "Bearish", "Neutral"])
        setup = st.selectbox("Setup Type", ["Breakout", "Pullback", "Support/Resistance", "Reversal", "Continuation", "Other"])
        indicators = st.text_input("Indicators Used")
        volatility = st.selectbox("IV Context", ["High IV", "Low IV", "Normal"])
        expected_move = st.text_input("Expected Move")
        time_horizon = st.selectbox("Time Horizon", ["Intraday", "1-3 Days", "Weekly", "Monthly"])
    
    # Risk & Execution
    rr = round((target - entry) / (entry - stop_loss), 2) if (entry - stop_loss) != 0 else 0
    st.info(f"**Risk-Reward Ratio: 1:{rr}**")
    
    followed = st.radio("Did you follow your plan?", ["Yes", "No", "Partially"])
    slippage = st.text_area("Slippage / Late Entry / Early Exit / Adjustments")
    
    # Psychology
    emo_before = st.multiselect("Emotion Before Trade", ["Confident", "Fearful", "FOMO", "Neutral", "Excited"])
    emo_during = st.multiselect("Emotion During Trade", ["Patience", "Panic", "Overconfidence", "Calm"])
    emo_after = st.multiselect("Emotion After Trade", ["Satisfaction", "Regret", "Neutral", "Frustrated"])
    
    worked = st.text_area("What Worked?")
    failed = st.text_area("What Failed?")
    improvement = st.text_area("One Actionable Improvement")
    
    if st.button("💾 Save Trade", type="primary", use_container_width=True):
        pnl = (exit_price - entry) * pos_size * 50 if "NIFTY" in instrument else (exit_price - entry) * pos_size  # Rough multiplier
        
        trade = {
            "Date": str(date),
            "Time": str(time),
            "Instrument": instrument,
            "Strategy": strategy,
            "Expiry": expiry,
            "Strike": strike,
            "Position Size": pos_size,
            "Entry": entry,
            "Exit": exit_price,
            "PnL": round(pnl, 2),
            "R_Multiple": round(pnl / ((entry - stop_loss) * pos_size * 50 if "NIFTY" in instrument else (entry - stop_loss) * pos_size), 2) if (entry - stop_loss) != 0 else 0,
            "Market Bias": bias,
            "Setup Type": setup,
            "Indicators": indicators,
            "Volatility Context": volatility,
            "Expected Move": expected_move,
            "Time Horizon": time_horizon,
            "Stop Loss": stop_loss,
            "Target": target,
            "RR Ratio": rr,
            "Did you follow your plan?": followed,
            "Slippage / Adjustment": slippage,
            "Emotion Before": ", ".join(emo_before),
            "Emotion During": ", ".join(emo_during),
            "Emotion After": ", ".join(emo_after),
            "What Worked": worked,
            "What Failed": failed,
            "Improvement": improvement
        }
        
        save_trade(trade)
        st.success("✅ Trade Saved Successfully!")
        st.rerun()

# ------------------- TAB 2: Trade History -------------------
with tab2:
    st.header("Trade History")
    df = load_trades()
    
    if not df.empty:
        st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, height=600)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download as CSV", csv, "trading_journal.csv", "text/csv")
    else:
        st.info("No trades yet. Log your first trade!")

# ------------------- TAB 3: Analytics -------------------
with tab3:
    st.header("Performance Analytics")
    df = load_trades()
    
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        total_trades = len(df)
        win_rate = len(df[df['PnL'] > 0]) / total_trades * 100 if total_trades > 0 else 0
        total_pnl = df['PnL'].sum()
        avg_rr = df['R_Multiple'].mean()
        
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Total PnL", f"₹{total_pnl:,.0f}", delta=None)
        col4.metric("Avg R-Multiple", f"{avg_rr:.2f}R")
        
        # Equity Curve
        df_sorted = df.sort_values("Date")
        df_sorted['Cumulative PnL'] = df_sorted['PnL'].cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_sorted['Date'], y=df_sorted['Cumulative PnL'], mode='lines+markers', name='Equity Curve'))
        fig.update_layout(title="Equity Curve", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Win Rate by Strategy
        strategy_perf = df.groupby('Strategy').agg(
            Trades=('PnL', 'count'),
            WinRate=('PnL', lambda x: (x > 0).mean() * 100),
            AvgPnL=('PnL', 'mean')
        ).round(2)
        st.plotly_chart(px.bar(strategy_perf, y='WinRate', title="Win Rate by Strategy"), use_container_width=True)
        
        # Psychology Analysis
        st.subheader("Psychology Impact")
        emo_df = df.copy()
        emo_df['Emotion Before'] = emo_df['Emotion Before'].str.split(', ')
        emo_exploded = emo_df.explode('Emotion Before')
        emo_perf = emo_exploded.groupby('Emotion Before')['PnL'].agg(['count', 'mean']).round(2)
        st.dataframe(emo_perf)
        
    else:
        st.warning("Add some trades to see analytics!")

# Sidebar Info
with st.sidebar:
    st.header("About")
    st.info("Your trading edge compounds through disciplined journaling.")
    st.caption("Built for Saurav • Velocity Trading")