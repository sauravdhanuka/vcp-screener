"""Market tab: Nifty chart with SMAs, regime detection, guidance."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from vcp_screener.db import init_db
from vcp_screener.services.market_regime import detect_market_regime, get_nifty_data
from vcp_screener.services.indicators import sma


@st.cache_data(ttl=600, show_spinner="Loading Nifty data...")
def _load_market_data():
    """Fetch Nifty data + regime. Cached 10 min."""
    nifty = get_nifty_data(period="2y")
    regime = detect_market_regime(nifty)

    # Convert to serializable format for caching
    nifty_dict = None
    if not nifty.empty:
        close = nifty["Close"].squeeze()
        sma_50 = sma(close, 50)
        sma_200 = sma(close, 200)

        vol = nifty["Volume"].squeeze() if "Volume" in nifty.columns else pd.Series(dtype=float)

        nifty_dict = {
            "dates": close.index.tolist(),
            "close": close.values.tolist(),
            "sma_50": sma_50.values.tolist(),
            "sma_200": sma_200.values.tolist(),
            "volume": vol.values.tolist() if len(vol) > 0 else [],
        }

    return regime, nifty_dict


def render():
    init_db()

    regime, nifty_dict = _load_market_data()
    regime_name = regime["regime"]

    if regime_name == "UNKNOWN":
        st.warning("Could not determine market regime. Check internet connectivity.")
        return

    # Regime banner
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

    if regime.get("method") == "breadth":
        m1, m2, m3 = st.columns(3)
        m1.metric("Breadth", f"{regime['breadth_pct']:.1f}%")
        m2.metric("Bull Threshold", f">= {regime['bull_threshold']}%")
        m3.metric("Bear Threshold", f"< {regime['bear_threshold']}%")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Nifty 50", f"{regime['nifty_close']:,.0f}")
        m2.metric("50-day SMA", f"{regime['nifty_sma50']:,.0f}",
                  delta="Above" if regime["above_50sma"] else "Below")
        m3.metric("200-day SMA", f"{regime['nifty_sma200']:,.0f}",
                  delta="Above" if regime["above_200sma"] else "Below")
        m4.metric("Regime", regime_name)

    # Chart
    if nifty_dict:
        tf = st.radio("Timeframe", ["3M", "6M", "1Y", "2Y"], horizontal=True, index=2)
        tf_days = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504}
        n = tf_days.get(tf, 252)

        dates = nifty_dict["dates"][-n:]
        close = nifty_dict["close"][-n:]
        sma_50 = nifty_dict["sma_50"][-n:]
        sma_200 = nifty_dict["sma_200"][-n:]
        volume = nifty_dict["volume"][-n:] if nifty_dict["volume"] else []

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, row_heights=[0.75, 0.25])

        fig.add_trace(go.Scatter(
            x=dates, y=close, name="Nifty 50",
            line=dict(color="#58a6ff", width=2),
            fill="tozeroy", fillcolor="rgba(88,166,255,0.05)",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=dates, y=sma_50, name="SMA 50",
            line=dict(width=1.5, color="#ff7b72"),
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=dates, y=sma_200, name="SMA 200",
            line=dict(width=1.5, color="#7ee787", dash="dot"),
        ), row=1, col=1)

        if volume:
            fig.add_trace(go.Bar(
                x=dates, y=volume, name="Volume",
                marker_color="rgba(88,166,255,0.3)",
            ), row=2, col=1)

        fig.update_layout(
            height=550, template="plotly_dark",
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font_size=10),
            plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(gridcolor="#21262d", zeroline=False)
        fig.update_yaxes(gridcolor="#21262d", zeroline=False)

        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Trading Rules by Regime"):
        st.markdown("""
| Regime | VCP Entries | MR Entries | Position Size | Max Positions |
|--------|-------------|------------|---------------|---------------|
| **BULLISH** | Full | Disabled | 100% | 5 (or EqMA adjusted) |
| **CAUTIOUS** | Selective | Disabled | 50-75% | 3-5 |
| **BEARISH** | Disabled | Active | MR: 1.5% risk | 3 MR positions |

**Regime Detection**: Primary = Market breadth (% stocks > 50-day SMA).
Bull >= 55%, Bear < 35%, Cautious in between.
Fallback = Nifty 50 vs 50/200-day SMA.
        """)
