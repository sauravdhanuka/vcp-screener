"""Streamlit dashboard entry point — professional multi-tab layout."""

import streamlit as st

st.set_page_config(
    page_title="VCP Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS for professional look ──
st.markdown("""
<style>
/* Hide default streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Tighter spacing */
.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 0px;
    background-color: #0e1117;
    border-bottom: 2px solid #1e2430;
    padding: 0 1rem;
}
.stTabs [data-baseweb="tab"] {
    padding: 10px 24px;
    font-weight: 600;
    font-size: 0.9rem;
    color: #8b949e;
    border-bottom: 3px solid transparent;
}
.stTabs [aria-selected="true"] {
    color: #58a6ff;
    border-bottom: 3px solid #58a6ff;
}

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Dataframe styling */
[data-testid="stDataFrame"] {
    border: 1px solid #21262d;
    border-radius: 8px;
}

/* Buttons */
.stButton > button {
    border-radius: 6px;
    font-weight: 600;
}

/* Expander styling */
.streamlit-expanderHeader {
    font-weight: 600;
    font-size: 0.9rem;
}

/* Divider styling */
hr {
    border-color: #21262d;
}
</style>
""", unsafe_allow_html=True)

from vcp_screener.db import init_db
init_db()

# Import pages
from vcp_screener.dashboard.pages import (
    screener_page,
    signals_page,
    portfolio_page,
    watchlist_page,
    market_page,
)

# ── Header bar ──
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown("### VCP Screener")
with hcol2:
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
            status = f"{stock_count:,} stocks"
            if last_screen:
                status += f" · Screened: {last_screen}"
            st.caption(status)
        finally:
            session.close()
    except Exception:
        pass

# ── Main tabs ──
tab_screener, tab_signals, tab_portfolio, tab_watchlist, tab_market = st.tabs([
    "Screener",
    "Signals",
    "Portfolio",
    "Watchlist",
    "Market",
])

with tab_screener:
    screener_page.render()

with tab_signals:
    signals_page.render()

with tab_portfolio:
    portfolio_page.render()

with tab_watchlist:
    watchlist_page.render()

with tab_market:
    market_page.render()
