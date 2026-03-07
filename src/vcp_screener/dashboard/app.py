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

st.sidebar.markdown("---")

# Data status in sidebar
try:
    from vcp_screener.db import get_session, init_db
    from vcp_screener.models.screening_result import ScreeningResult
    from vcp_screener.models.stock import Stock
    from sqlalchemy import func

    init_db()
    session = get_session()
    try:
        stock_count = session.query(func.count(Stock.symbol)).filter(Stock.is_active == True).scalar() or 0
        last_screen = session.query(func.max(ScreeningResult.run_date)).scalar()
        last_update = session.query(func.max(Stock.last_updated)).scalar()

        st.sidebar.caption("Data Status")
        st.sidebar.text(f"Stocks: {stock_count:,}")
        if last_screen:
            st.sidebar.text(f"Last screen: {last_screen}")
        else:
            st.sidebar.text("Last screen: Never")
        if last_update:
            st.sidebar.text(f"Last update: {last_update:%Y-%m-%d %H:%M}")
        else:
            st.sidebar.text("Last update: Never")
    finally:
        session.close()
except Exception:
    pass

# Run the selected page
PAGE_MAP[selection].render()
