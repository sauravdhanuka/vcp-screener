"""Market overview page: Nifty chart, regime, sector performance."""

import streamlit as st
import plotly.graph_objects as go

from vcp_screener.db import init_db
from vcp_screener.services.market_regime import detect_market_regime, get_nifty_data
from vcp_screener.services.indicators import sma


def render():
    st.header("Market Overview")
    init_db()

    with st.spinner("Fetching market data..."):
        nifty = get_nifty_data(period="1y")
        regime = detect_market_regime(nifty)

    regime_name = regime["regime"]
    regime_icons = {"BULLISH": "🟢", "CAUTIOUS": "🟡", "BEARISH": "🔴", "UNKNOWN": "⚪"}
    st.markdown(f"### Market Regime: {regime_icons.get(regime_name, '⚪')} {regime_name}")

    if regime_name == "UNKNOWN":
        st.warning("Could not determine market regime. Check data connectivity.")
        return

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Nifty 50", f"{regime['nifty_close']:,.0f}")
    mc2.metric("50-day SMA", f"{regime['nifty_sma50']:,.0f}",
               delta="Above" if regime["above_50sma"] else "Below")
    mc3.metric("200-day SMA", f"{regime['nifty_sma200']:,.0f}",
               delta="Above" if regime["above_200sma"] else "Below")
    mc4.metric("Regime", regime_name)

    if not nifty.empty:
        close = nifty["Close"].squeeze()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=close.index, y=close.values, name="Nifty 50",
            line=dict(color="#4ECDC4", width=2),
        ))
        sma_50 = sma(close, 50)
        sma_200 = sma(close, 200)
        fig.add_trace(go.Scatter(
            x=sma_50.index, y=sma_50.values, name="50 SMA",
            line=dict(color="#FF6B6B", width=1.5, dash="dot"),
        ))
        fig.add_trace(go.Scatter(
            x=sma_200.index, y=sma_200.values, name="200 SMA",
            line=dict(color="#45B7D1", width=1.5, dash="dot"),
        ))
        fig.update_layout(
            title="Nifty 50 Index",
            height=500, template="plotly_dark",
            yaxis_title="Price",
        )
        st.plotly_chart(fig)

    st.subheader("Trading Guidance")
    if regime_name == "BULLISH":
        st.success(
            "**BULLISH regime** — Best conditions for VCP breakout entries. "
            "Full position sizes. Focus on top-ranked VCP candidates with RS > 80."
        )
    elif regime_name == "CAUTIOUS":
        st.warning(
            "**CAUTIOUS regime** — Nifty above 200 SMA but below 50 SMA. "
            "Reduce position sizes to 50-75%. Be selective, only top 10-15 candidates."
        )
    else:
        st.error(
            "**BEARISH regime** — Nifty below 200 SMA. Avoid new entries. "
            "Focus on protecting existing positions with tight stops. Cash is a position."
        )
