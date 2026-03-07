"""Stock detail page: candlestick chart + VCP annotations."""

import streamlit as st

from vcp_screener.db import init_db, get_session
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import get_stock_detail
from vcp_screener.dashboard.components.charts import candlestick_chart


def _get_recent_symbols() -> list[str]:
    """Get symbols from the most recent screening run."""
    from sqlalchemy import func
    session = get_session()
    try:
        latest_date = session.query(func.max(ScreeningResult.run_date)).scalar()
        if not latest_date:
            return []
        results = (
            session.query(ScreeningResult.symbol)
            .filter(ScreeningResult.run_date == latest_date)
            .order_by(ScreeningResult.rank)
            .all()
        )
        return [r[0] for r in results]
    finally:
        session.close()


def render():
    st.header("Stock Detail")
    init_db()

    # Pre-populate from session state (e.g., when user clicks a symbol elsewhere)
    default_symbol = st.session_state.get("detail_symbol", "")

    recent_symbols = _get_recent_symbols()

    if recent_symbols:
        options = [""] + recent_symbols
        default_idx = 0
        if default_symbol and default_symbol in recent_symbols:
            default_idx = options.index(default_symbol)
        symbol = st.selectbox(
            "Select a recently screened stock",
            options,
            index=default_idx,
            format_func=lambda x: "Type or select..." if x == "" else x,
        )
    else:
        symbol = st.text_input("Enter NSE Symbol", value=default_symbol).upper().strip()

    if not symbol:
        st.info("Select or enter a stock symbol to view detailed analysis.")
        return

    symbol = symbol.upper().strip()

    with st.spinner(f"Analyzing {symbol}..."):
        detail = get_stock_detail(symbol)

    if not detail:
        st.error(f"No data found for {symbol}. Make sure data is downloaded.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Close Price", f"₹{detail['close']:,.2f}")
    c2.metric("RS Percentile", f"{detail['rs_percentile']:.0f}")
    c3.metric("VCP Score", f"{detail['vcp_score']:.0f}")
    vcp = detail["vcp"]
    c4.metric("Pivot", f"₹{vcp['pivot_price']:,.2f}" if vcp.get("found") else "N/A")

    df = detail["price_data"]
    contractions = vcp.get("contractions") if vcp.get("found") else None
    pivot = vcp.get("pivot_price") if vcp.get("found") else None

    fig = candlestick_chart(df, symbol, contractions=contractions, pivot_price=pivot)
    st.plotly_chart(fig)

    st.subheader("Trend Template")
    trend = detail["trend_template"]
    if trend.get("conditions"):
        cols = st.columns(4)
        for i, (name, passes) in enumerate(trend["conditions"].items()):
            icon = "✅" if passes else "❌"
            label = name.split("_", 1)[1].replace("_", " ").title() if "_" in name else name
            cols[i % 4].write(f"{icon} {label}")

    st.subheader("VCP Analysis")
    if vcp.get("found"):
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Contractions", vcp["num_contractions"])
        vc2.metric("Tightness", f"{vcp['tightness_ratio']:.2f}")
        vc3.metric("Volume Dry-up", f"{vcp['volume_dry_up_pct']:.0f}%")
        vc4.metric("Base Duration", f"{vcp['base_duration_days']} days")

        st.write("**Contraction Details:**")
        for i, c in enumerate(vcp["contractions"], 1):
            st.write(f"  T{i}: Range {c['range_pct']:.1f}%, "
                     f"High ₹{c['high_val']:,.1f} → Low ₹{c['low_val']:,.1f}, "
                     f"Avg Vol {c['avg_volume']:,.0f}")
    else:
        st.warning(f"No VCP pattern: {vcp.get('reason', 'unknown')}")
