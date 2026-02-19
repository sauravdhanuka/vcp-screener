"""Streamlit multipage dashboard entry point."""

import streamlit as st

st.set_page_config(
    page_title="VCP Screener - NSE",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import all pages at top level (avoids conditional import issues)
from vcp_screener.dashboard.pages import signals_page
from vcp_screener.dashboard.pages import screener_page
from vcp_screener.dashboard.pages import stock_detail_page
from vcp_screener.dashboard.pages import portfolio_page
from vcp_screener.dashboard.pages import backtest_page
from vcp_screener.dashboard.pages import market_page

PAGE_MAP = {
    "Buy Signals": signals_page,
    "Screener": screener_page,
    "Stock Detail": stock_detail_page,
    "Portfolio": portfolio_page,
    "Backtest": backtest_page,
    "Market Overview": market_page,
}

st.sidebar.title("VCP Screener")
selection = st.sidebar.radio("Navigate", list(PAGE_MAP.keys()))

# Run the selected page
PAGE_MAP[selection].render()
