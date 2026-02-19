"""Buy Signals page: actionable buy signals with color-coded categories."""

import streamlit as st

from vcp_screener.db import init_db, get_session
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import get_buy_signals, run_screening
from vcp_screener.services.data_fetcher import fetch_nse_stock_list, save_stock_list, download_ohlcv


def _has_screening_data() -> bool:
    """Check if there's any screening data in the DB."""
    session = get_session()
    try:
        return session.query(ScreeningResult.run_date).first() is not None
    finally:
        session.close()


def _run_download_and_screen():
    """Download data and run screening in one go for fresh deployments."""
    with st.spinner("Step 1/3: Fetching NSE stock list..."):
        stocks = fetch_nse_stock_list()
        save_stock_list(stocks)
        symbols = [s["symbol"] for s in stocks]

    with st.spinner(f"Step 2/3: Downloading price data for {len(symbols)} stocks (30 days)..."):
        download_ohlcv(symbols, period="30d")

    with st.spinner("Step 3/3: Running VCP screening..."):
        run_screening()


def _render_signal_card(s: dict):
    """Render a single signal as a compact card."""
    symbol = s["symbol"]
    signal = s["signal"]
    close = s["close"]
    pivot = s["pivot"]
    vcp_score = s["vcp_score"]
    rs_pct = s["rs_percentile"]

    if signal == "BUY":
        entry = s["entry_price"]
        stop = s["stop_price"]
        shares = s["shares"]
        cost = s["cost"]
        st.markdown(
            f"**{symbol}** — VCP {vcp_score:.0f} | RS {rs_pct:.0f}  \n"
            f"Entry ₹{entry:,.0f} · Stop ₹{stop:,.0f} · "
            f"{shares} shares · ₹{cost:,.0f}  \n"
            f"_{s['reason']}_"
        )
    elif signal == "WATCH_VOLUME":
        st.markdown(
            f"**{symbol}** — VCP {vcp_score:.0f} | RS {rs_pct:.0f} | "
            f"Vol {s['vol_ratio']:.1f}x  \n"
            f"Close ₹{close:,.0f} · Pivot ₹{pivot:,.0f}  \n"
            f"_{s['reason']}_"
        )
    elif signal == "NEAR_PIVOT":
        st.markdown(
            f"**{symbol}** — VCP {vcp_score:.0f} | RS {rs_pct:.0f} | "
            f"{s['distance_to_pivot_pct']:.1f}% to pivot  \n"
            f"Close ₹{close:,.0f} · Pivot ₹{pivot:,.0f}  \n"
            f"_{s['reason']}_"
        )
    else:  # FORMING
        st.markdown(
            f"**{symbol}** — VCP {vcp_score:.0f} | RS {rs_pct:.0f} | "
            f"{s['distance_to_pivot_pct']:.1f}% to pivot  \n"
            f"Close ₹{close:,.0f} · Pivot ₹{pivot:,.0f}"
        )


def render():
    st.header("Buy Signals")
    init_db()

    # Check for screening data
    if not _has_screening_data():
        st.warning("No screening data found. Download data and run screening first.")
        if st.button("Download Data & Run Screening", type="primary"):
            try:
                _run_download_and_screen()
                st.success("Done! Screening complete.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        st.info(
            "**First time on Streamlit Cloud?** This will download ~30 days of NSE data "
            "and run the VCP screener. Takes 5-10 minutes."
        )
        return

    # Main action button
    if st.button("Check Buy Signals", type="primary"):
        with st.spinner("Analyzing candidates for buy signals..."):
            signals = get_buy_signals()
        st.session_state["signals"] = signals

    # Also offer re-screening
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Re-run Screening"):
            with st.spinner("Running VCP screening..."):
                run_screening()
            st.success("Screening complete! Click 'Check Buy Signals' to see results.")
            st.rerun()
    with col2:
        if st.button("Refresh Price Data (30d)"):
            try:
                _run_download_and_screen()
                st.success("Data refreshed and screening complete!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    signals = st.session_state.get("signals")
    if signals is None:
        st.info("Click **Check Buy Signals** to analyze the latest screening results.")
        return

    if not signals:
        st.info("No signals found. The screener may not have found actionable candidates.")
        return

    # Market regime banner
    regime = signals[0].get("market_regime", "UNKNOWN")
    regime_map = {
        "BULLISH": ("green", "BULLISH — Full position sizes"),
        "CAUTIOUS": ("orange", "CAUTIOUS — Reduce position sizes"),
        "BEARISH": ("red", "BEARISH — Avoid new positions"),
    }
    color, label = regime_map.get(regime, ("gray", regime))
    st.markdown(
        f'<div style="background-color:{color};color:white;padding:8px 16px;'
        f'border-radius:8px;text-align:center;font-weight:bold;margin-bottom:16px">'
        f'Market: {label}</div>',
        unsafe_allow_html=True,
    )

    # Group signals by type
    groups = {"BUY": [], "WATCH_VOLUME": [], "NEAR_PIVOT": [], "FORMING": []}
    for s in signals:
        groups.get(s["signal"], groups["FORMING"]).append(s)

    # BUY signals — green
    if groups["BUY"]:
        st.markdown(
            f'<div style="background-color:#1a472a;padding:4px 12px;border-radius:6px;'
            f'margin:8px 0"><b>BUY ({len(groups["BUY"])})</b> — Breakout confirmed</div>',
            unsafe_allow_html=True,
        )
        for s in groups["BUY"]:
            _render_signal_card(s)
            st.divider()

    # WATCH_VOLUME — yellow
    if groups["WATCH_VOLUME"]:
        st.markdown(
            f'<div style="background-color:#5c4a1e;padding:4px 12px;border-radius:6px;'
            f'margin:8px 0"><b>WATCH VOLUME ({len(groups["WATCH_VOLUME"])})</b> — Above pivot, needs volume</div>',
            unsafe_allow_html=True,
        )
        for s in groups["WATCH_VOLUME"]:
            _render_signal_card(s)
            st.divider()

    # NEAR_PIVOT — blue
    if groups["NEAR_PIVOT"]:
        st.markdown(
            f'<div style="background-color:#1a3a5c;padding:4px 12px;border-radius:6px;'
            f'margin:8px 0"><b>NEAR PIVOT ({len(groups["NEAR_PIVOT"])})</b> — Within 3% of breakout</div>',
            unsafe_allow_html=True,
        )
        for s in groups["NEAR_PIVOT"]:
            _render_signal_card(s)
            st.divider()

    # FORMING — gray
    if groups["FORMING"]:
        st.markdown(
            f'<div style="background-color:#3a3a3a;padding:4px 12px;border-radius:6px;'
            f'margin:8px 0"><b>FORMING ({len(groups["FORMING"])})</b> — VCP in progress</div>',
            unsafe_allow_html=True,
        )
        for s in groups["FORMING"]:
            _render_signal_card(s)
            st.divider()

    # Summary
    st.caption(
        f"Total: {len(signals)} candidates — "
        f"{len(groups['BUY'])} BUY · {len(groups['WATCH_VOLUME'])} Watch · "
        f"{len(groups['NEAR_PIVOT'])} Near Pivot · {len(groups['FORMING'])} Forming"
    )
