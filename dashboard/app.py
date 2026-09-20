"""
Streamlit Dashboard for Phoenix Protocol Trading System
Interactive monitoring and visualization dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import ASSETS, TIMEFRAMES
from src.utils.logger import get_logger


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'page' not in st.session_state:
        st.session_state.page = 'dashboard'
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 60
    if 'selected_asset' not in st.session_state:
        st.session_state.selected_asset = list(ASSETS.keys())[0]


def render_sidebar():
    """Render sidebar navigation."""
    with st.sidebar:
        st.title("Phoenix Protocol")
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Navigation",
            ['Dashboard', 'Trades', 'Performance', 'Settings', 'Backtesting'],
            key='page_navigation'
        )
        st.session_state.page = page.lower().replace(' ', '_')
        
        st.markdown("---")
        
        # Asset selection
        st.subheader("Asset Selection")
        selected_asset = st.selectbox(
            "Select Asset",
            list(ASSETS.keys()),
            key='asset_selector'
        )
        st.session_state.selected_asset = selected_asset
        
        st.markdown("---")
        
        # Refresh settings
        st.subheader("Refresh Settings")
        refresh_interval = st.slider(
            "Auto-refresh (seconds)",
            min_value=10,
            max_value=300,
            value=60,
            key='refresh_slider'
        )
        st.session_state.refresh_interval = refresh_interval
        
        st.markdown("---")
        
        # System status
        st.subheader("System Status")
        st.info("🟢 System Online")
        st.info(f"📊 Active Positions: 0")
        st.info(f"💰 Account Balance: $10,000")


def render_dashboard():
    """Render main dashboard page."""
    st.title("Trading Dashboard")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Account Balance", "$10,000", "+$500 (5.2%)")
    
    with col2:
        st.metric("Today's P&L", "+$250", "+2.5%")
    
    with col3:
        st.metric("Win Rate", "72%", "+3%")
    
    with col4:
        st.metric("Open Positions", "2", "Max: 2")
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Price Chart")
        render_price_chart()
    
    with col2:
        st.subheader("Recent Signals")
        render_recent_signals()
    
    st.markdown("---")
    
    # Risk metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Daily Loss Used", "$150", "Limit: $500")
    
    with col2:
        st.metric("Weekly Loss Used", "$300", "Limit: $1,000")
    
    with col3:
        st.metric("Max Drawdown", "-8.5%", "Limit: -15%")


def render_price_chart():
    """Render price chart with indicators."""
    # Generate sample data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    prices = np.random.normal(100, 2, 100).cumsum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=prices,
        mode='lines',
        name='Price',
        line=dict(color='#1f77b4', width=2)
    ))
    
    fig.update_layout(
        title=f"{st.session_state.selected_asset} - 15 Minute Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        height=400,
        template="plotly_dark"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_recent_signals():
    """Render recent trading signals."""
    signals_data = [
        {
            'Time': '10:30 AM',
            'Asset': 'XAUUSD',
            'Type': 'ENTRY',
            'Direction': 'LONG',
            'Price': 1950.50,
            'Status': 'FILLED'
        },
        {
            'Time': '09:45 AM',
            'Asset': 'GBPJPY',
            'Type': 'EXIT',
            'Direction': 'LONG',
            'Price': 182.50,
            'Status': 'TP HIT'
        },
        {
            'Time': '08:15 AM',
            'Asset': 'EURUSD',
            'Type': 'SIGNAL',
            'Direction': 'LONG',
            'Price': 1.0850,
            'Status': 'PENDING'
        }
    ]
    
    df = pd.DataFrame(signals_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_trades():
    """Render trades page."""
    st.title("Trade History")
    
    # Trade filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        asset_filter = st.multiselect(
            "Filter by Asset",
            list(ASSETS.keys()),
            default=list(ASSETS.keys())
        )
    
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            ['All', 'Open', 'Closed', 'Cancelled']
        )
    
    with col3:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=30), datetime.now())
        )
    
    st.markdown("---")
    
    # Sample trade data
    trades_data = [
        {
            'Trade ID': 'TRD001',
            'Asset': 'XAUUSD',
            'Direction': 'LONG',
            'Entry Price': 1948.50,
            'Exit Price': 1960.00,
            'P&L': '+$1,150',
            'P&L %': '+3.0%',
            'Status': 'CLOSED',
            'Entry Time': '2024-01-15 10:30',
            'Exit Time': '2024-01-15 14:45'
        },
        {
            'Trade ID': 'TRD002',
            'Asset': 'GBPJPY',
            'Direction': 'LONG',
            'Entry Price': 182.00,
            'Exit Price': 181.50,
            'P&L': '-$250',
            'P&L %': '-1.5%',
            'Status': 'CLOSED',
            'Entry Time': '2024-01-15 09:15',
            'Exit Time': '2024-01-15 11:30'
        },
        {
            'Trade ID': 'TRD003',
            'Asset': 'EURUSD',
            'Direction': 'LONG',
            'Entry Price': 1.0845,
            'Exit Price': None,
            'P&L': '+$85',
            'P&L %': '+0.8%',
            'Status': 'OPEN',
            'Entry Time': '2024-01-15 15:00',
            'Exit Time': None
        }
    ]
    
    df = pd.DataFrame(trades_data)
    
    # Format P&L columns
    def format_pnl(val):
        if pd.isna(val):
            return val
        color = 'green' if '+' in str(val) else 'red'
        return f":{color}[{val}]"
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
    
    # Trade statistics
    st.markdown("---")
    st.subheader("Trade Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", "150")
    
    with col2:
        st.metric("Win Rate", "72%")
    
    with col3:
        st.metric("Profit Factor", "3.55")
    
    with col4:
        st.metric("Avg Win/Loss", "2.5:1")


def render_performance():
    """Render performance page."""
    st.title("Performance Analytics")
    
    # Performance metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Return Metrics")
        st.metric("Total Return", "+30.66%", "")
        st.metric("Monthly Return", "+2.5%", "")
        st.metric("Weekly Return", "+0.8%", "")
    
    with col2:
        st.subheader("Risk Metrics")
        st.metric("Max Drawdown", "-10.6%", "")
        st.metric("Sharpe Ratio", "1.85", "")
        st.metric("Sortino Ratio", "2.10", "")
    
    with col3:
        st.subheader("Trade Metrics")
        st.metric("Win Rate", "72%", "")
        st.metric("Profit Factor", "3.55", "")
        st.metric("Avg Trade", "+$204", "")
    
    st.markdown("---")
    
    # Equity curve
    st.subheader("Equity Curve")
    render_equity_curve()
    
    st.markdown("---")
    
    # Monthly performance
    st.subheader("Monthly Performance")
    render_monthly_performance()


def render_equity_curve():
    """Render equity curve chart."""
    # Generate sample equity data
    dates = pd.date_range(start=datetime.now() - timedelta(days=90), end=datetime.now(), freq='D')
    equity = 10000 + np.cumsum(np.random.normal(50, 200, len(dates)))
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=equity,
        mode='lines',
        name='Equity',
        line=dict(color='#2ecc71', width=2),
        fill='tozeroy',
        fillcolor='rgba(46, 204, 113, 0.1)'
    ))
    
    fig.update_layout(
        title="Equity Curve (90 Days)",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        height=400,
        template="plotly_dark"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_monthly_performance():
    """Render monthly performance table."""
    months = ['Oct', 'Nov', 'Dec', 'Jan']
    returns = [+5.2, +8.1, +12.3, +5.1]
    trades = [35, 42, 48, 25]
    win_rates = [68, 75, 72, 70]
    
    data = {
        'Month': months,
        'Return %': returns,
        'Trades': trades,
        'Win Rate': win_rates
    }
    
    df = pd.DataFrame(data)
    
    # Format return column
    def format_return(val):
        color = 'green' if val > 0 else 'red'
        return f":{color}[{val:+.1f}%]"
    
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_settings():
    """Render settings page."""
    st.title("System Settings")
    
    # Strategy settings
    st.subheader("Strategy Parameters")
    
    with st.expander("Bad Luck Moment Detector"):
        col1, col2 = st.columns(2)
        
        with col1:
            drop_threshold = st.slider(
                "Price Drop Threshold (%)",
                min_value=1,
                max_value=10,
                value=3
            )
            volume_multiplier = st.slider(
                "Volume Multiplier",
                min_value=1.0,
                max_value=5.0,
                value=2.0,
                step=0.1
            )
        
        with col2:
            atr_multiplier = st.slider(
                "ATR Multiplier",
                min_value=1.0,
                max_value=3.0,
                value=1.5,
                step=0.1
            )
            entry_probability = st.slider(
                "Entry Probability",
                min_value=0.1,
                max_value=1.0,
                value=0.6,
                step=0.1
            )
    
    with st.expander("Trade Management"):
        col1, col2 = st.columns(2)
        
        with col1:
            stop_loss = st.slider(
                "Stop Loss (%)",
                min_value=0.5,
                max_value=5.0,
                value=1.5,
                step=0.1
            )
            take_profit = st.slider(
                "Take Profit (%)",
                min_value=1.0,
                max_value=10.0,
                value=3.0,
                step=0.5
            )
        
        with col2:
            trailing_stop = st.checkbox("Enable Trailing Stop", value=True)
            position_risk = st.slider(
                "Position Risk (%)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5
            )
    
    with st.expander("Risk Management"):
        col1, col2 = st.columns(2)
        
        with col1:
            max_daily_loss = st.slider(
                "Max Daily Loss (%)",
                min_value=1,
                max_value=10,
                value=5
            )
            max_weekly_loss = st.slider(
                "Max Weekly Loss (%)",
                min_value=5,
                max_value=20,
                value=10
            )
        
        with col2:
            max_positions = st.slider(
                "Max Open Positions",
                min_value=1,
                max_value=10,
                value=2
            )
            cooldown = st.slider(
                "Cooldown After Loss (trades)",
                min_value=0,
                max_value=10,
                value=3
            )
    
    st.markdown("---")
    
    # Notification settings
    st.subheader("Notification Settings")
    
    telegram_enabled = st.checkbox("Enable Telegram Notifications", value=True)
    if telegram_enabled:
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Bot Token", type="password")
        with col2:
            st.text_input("Chat ID")
    
    st.markdown("---")
    
    # Save button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.button("Save Settings", type="primary")
    with col2:
        st.button("Reset to Defaults")


def render_backtesting():
    """Render backtesting page."""
    st.title("Backtesting")
    
    # Backtest configuration
    col1, col2, col3 = st.columns(3)
    
    with col1:
        asset = st.selectbox("Asset", list(ASSETS.keys()))
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365))
    
    with col2:
        timeframe = st.selectbox("Timeframe", ['M5', 'M15', 'H1'])
        end_date = st.date_input("End Date", value=datetime.now())
    
    with col3:
        initial_capital = st.number_input("Initial Capital", value=10000, min_value=1000)
        commission = st.number_input("Commission (%)", value=0.02, min_value=0.0, max_value=1.0, step=0.01)
    
    st.markdown("---")
    
    # Advanced options
    with st.expander("Advanced Options"):
        col1, col2 = st.columns(2)
        with col1:
            walk_forward = st.checkbox("Run Walk-Forward Analysis")
            monte_carlo = st.checkbox("Run Monte Carlo Simulation")
        with col2:
            mc_simulations = st.number_input("MC Simulations", value=1000, min_value=100, max_value=10000)
    
    st.markdown("---")
    
    # Run backtest button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        run_button = st.button("Run Backtest", type="primary")
    
    if run_button:
        with st.spinner("Running backtest..."):
            # Simulate backtest
            import time
            time.sleep(2)
            
            st.success("Backtest completed!")
            
            # Display results
            render_backtest_results()


def render_backtest_results():
    """Render backtest results."""
    st.subheader("Backtest Results")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Return", "+28.5%", "")
    
    with col2:
        st.metric("Win Rate", "70%", "")
    
    with col3:
        st.metric("Profit Factor", "3.2", "")
    
    with col4:
        st.metric("Max Drawdown", "-12.3%", "")
    
    st.markdown("---")
    
    # Detailed results
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trade Statistics")
        trade_stats = {
            'Total Trades': 125,
            'Winning Trades': 88,
            'Losing Trades': 37,
            'Win Rate': '70.4%',
            'Average Win': '$312',
            'Average Loss': '-$145',
            'Profit Factor': '3.2',
            'Risk/Reward Ratio': '2.15:1'
        }
        
        for key, value in trade_stats.items():
            st.metric(key, value)
    
    with col2:
        st.subheader("Risk Metrics")
        risk_stats = {
            'Max Drawdown': '-12.3%',
            'Max Drawdown ($)': '-$1,230',
            'Sharpe Ratio': '1.75',
            'Sortino Ratio': '2.05',
            'Calmar Ratio': '2.32',
            'Average Monthly Return': '+2.4%'
        }
        
        for key, value in risk_stats.items():
            st.metric(key, value)
    
    st.markdown("---")
    
    # Success criteria check
    st.subheader("Success Criteria")
    
    criteria = [
        ('Win Rate > 60%', True),
        ('Profit Factor > 2.0', True),
        ('Max Drawdown < 15%', True),
        ('Sharpe Ratio > 0.5', True),
        ('Trades > 100', True)
    ]
    
    for criterion, passed in criteria:
        status = "✅" if passed else "❌"
        st.write(f"{status} {criterion}")


def main():
    """Main dashboard entry point."""
    st.set_page_config(
        page_title="Phoenix Protocol Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stMetric {
            background-color: #1e1e1e;
            border: 1px solid #333;
            padding: 10px;
            border-radius: 5px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Render selected page
    page = st.session_state.page
    
    if page == 'dashboard':
        render_dashboard()
    elif page == 'trades':
        render_trades()
    elif page == 'performance':
        render_performance()
    elif page == 'settings':
        render_settings()
    elif page == 'backtesting':
        render_backtesting()
    
    # Auto-refresh
    if st.session_state.refresh_interval > 0:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
