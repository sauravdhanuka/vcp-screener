"""Streamlit dashboard entry point — professional layout with single-page rendering."""

import streamlit as st

st.set_page_config(
    page_title="VCP Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.block-container { padding-top: 1rem; padding-bottom: 0rem; }

[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.05em;
}
[data-testid="stDataFrame"] { border: 1px solid #21262d; border-radius: 8px; }
.stButton > button { border-radius: 6px; font-weight: 600; }
hr { border-color: #21262d; }

/* Sidebar nav styling */
[data-testid="stSidebar"] [data-testid="stRadio"] > label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

from vcp_screener.db import init_db
init_db()

# ── Sidebar navigation (only active page renders) ──
st.sidebar.markdown("### VCP Screener")

page = st.sidebar.radio(
    "Navigate",
    ["Screener", "Signals", "Portfolio", "Watchlist", "Market"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")

# Data status
try:
    from vcp_screener.db import get_session
    from vcp_screener.models.screening_result import ScreeningResult
    from vcp_screener.models.stock import Stock
    from sqlalchemy import func

    session = get_session()
    try:
        stock_count = session.query(func.count(Stock.symbol)).filter(Stock.is_active == True).scalar() or 0
        last_screen = session.query(func.max(ScreeningResult.run_date)).scalar()
        st.sidebar.caption(f"{stock_count:,} stocks · Last screen: {last_screen or 'Never'}")
    finally:
        session.close()
except Exception:
    pass

# ── Render only the active page ──
if page == "Screener":
    from vcp_screener.dashboard.pages import screener_page
    screener_page.render()
elif page == "Signals":
    from vcp_screener.dashboard.pages import signals_page
    signals_page.render()
elif page == "Portfolio":
    from vcp_screener.dashboard.pages import portfolio_page
    portfolio_page.render()
elif page == "Watchlist":
    from vcp_screener.dashboard.pages import watchlist_page
    watchlist_page.render()
elif page == "Market":
    from vcp_screener.dashboard.pages import market_page
    market_page.render()
