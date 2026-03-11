"""Market tab: Nifty chart with SMAs, regime detection, guidance."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from vcp_screener.db import init_db
from vcp_screener.services.market_regime import detect_market_regime, get_nifty_data
from vcp_screener.services.indicators import sma


def render():
    init_db()

    with st.spinner("Loading market data..."):
        nifty = get_nifty_data(period="2y")
        regime = detect_market_regime(nifty)

    regime_name = regime["regime"]

    if regime_name == "UNKNOWN":
        st.warning("Could not determine market regime. Check internet connectivity.")
        return

    # ── Regime + Metrics ──
    regime_styles = {
        "BULLISH": ("#1a472a", "#2ea043", "Full position sizes — best conditions for VCP entries"),
        "CAUTIOUS": ("#5c4a1e", "#d29922", "Reduce position sizes — be selective, top 10-15 only"),
        "BEARISH": ("#5c1a1a", "#f85149", "Avoid VCP entries — focus on MR signals and cash preservation"),
    }
    bg, border, guidance = regime_styles.get(regime_name, ("#2d333b", "#444c56", ""))

    st.markdown(
        f'<div style="background:{bg};border:1px solid {border};padding:12px 20px;'
        f'border-radius:8px;margin-bottom:16px">'
        f'<span style="font-size:1.1rem;font-weight:700">Market: {regime_name}</span><br>'
        f'<span style="color:#c9d1d9;font-size:0.85rem">{guidance}</span></div>',
        unsafe_allow_html=True,
    )

    # Method-specific info
    if regime.get("method") == "breadth":
        m1, m2, m3 = st.columns(3)
        m1.metric("Breadth", f"{regime['breadth_pct']:.1f}%")
        m2.metric("Bull Threshold", f"≥ {regime['bull_threshold']}%")
        m3.metric("Bear Threshold", f"< {regime['bear_threshold']}%")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Nifty 50", f"{regime['nifty_close']:,.0f}")
        m2.metric("50-day SMA", f"{regime['nifty_sma50']:,.0f}",
                  delta="Above" if regime["above_50sma"] else "Below")
        m3.metric("200-day SMA", f"{regime['nifty_sma200']:,.0f}",
                  delta="Above" if regime["above_200sma"] else "Below")
        m4.metric("Regime", regime_name)

    # ── Nifty Chart ──
    if not nifty.empty:
        # Timeframe selector
        tf = st.radio("Timeframe", ["3M", "6M", "1Y", "2Y"], horizontal=True, index=2)
        tf_days = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504}
        chart_data = nifty.tail(tf_days.get(tf, 252))

        close = chart_data["Close"].squeeze()

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03, row_heights=[0.75, 0.25],
        )

        # Price line
        fig.add_trace(go.Scatter(
            x=close.index, y=close.values, name="Nifty 50",
            line=dict(color="#58a6ff", width=2),
            fill="tozeroy", fillcolor="rgba(88,166,255,0.05)",
        ), row=1, col=1)

        # SMAs
        for period, color, dash in [(50, "#ff7b72", None), (200, "#7ee787", "dot")]:
            sma_vals = sma(nifty["Close"].squeeze(), period)
            sma_sliced = sma_vals[sma_vals.index.isin(chart_data.index)]
            fig.add_trace(go.Scatter(
                x=sma_sliced.index, y=sma_sliced.values, name=f"SMA {period}",
                line=dict(width=1.5, color=color, dash=dash),
            ), row=1, col=1)

        # Volume
        if "Volume" in chart_data.columns:
            vol = chart_data["Volume"].squeeze()
            fig.add_trace(go.Bar(
                x=vol.index, y=vol.values, name="Volume",
                marker_color="rgba(88,166,255,0.3)",
            ), row=2, col=1)

        fig.update_layout(
            height=550,
            template="plotly_dark",
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font_size=10),
            plot_bgcolor="#0d1117",
            paper_bgcolor="#0d1117",
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(gridcolor="#21262d", zeroline=False)
        fig.update_yaxes(gridcolor="#21262d", zeroline=False)
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

    # ── Trading Rules ──
    with st.expander("Trading Rules by Regime"):
        st.markdown("""
| Regime | VCP Entries | MR Entries | Position Size | Max Positions |
|--------|-------------|------------|---------------|---------------|
| **BULLISH** | Full | Disabled | 100% | 5 (or EqMA adjusted) |
| **CAUTIOUS** | Selective | Disabled | 50-75% | 3-5 |
| **BEARISH** | Disabled | Active | MR: 1.5% risk | 3 MR positions |

**Regime Detection**: Primary = Market breadth (% stocks > 50-day SMA).
Bull ≥ 55%, Bear < 35%, Cautious in between.
Fallback = Nifty 50 vs 50/200-day SMA.
        """)
