"""Buy Signals page: actionable buy signals with color-coded categories."""

import streamlit as st

from vcp_screener.db import init_db, get_session
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import get_buy_signals, run_screening
from vcp_screener.services.data_fetcher import (
    fetch_nse_stock_list, save_stock_list, download_ohlcv,
    get_active_symbols, update_prices,
)


def _has_screening_data() -> bool:
    """Check if there's any screening data in the DB."""
    session = get_session()
    try:
        return session.query(ScreeningResult.run_date).first() is not None
    finally:
        session.close()


def _get_last_screen_date():
    """Get the most recent screening date."""
    from sqlalchemy import func
    session = get_session()
    try:
        return session.query(func.max(ScreeningResult.run_date)).scalar()
    finally:
        session.close()


def _update_and_screen(period: str = "10d"):
    """Shared helper: update prices from DB stock list + run screening with progress bar.

    Skips NSE website fetch (blocked on cloud) — uses stocks already in DB.
    Uses larger batches (100) and shorter delays (0.5s) for speed.
    """
    symbols = get_active_symbols()
    if not symbols:
        # First time: must fetch from NSE (only works locally)
        progress = st.progress(0, text="Fetching NSE stock list (first-time setup)...")
        stocks = fetch_nse_stock_list()
        save_stock_list(stocks)
        symbols = [s["symbol"] for s in stocks]
        progress.progress(5, text=f"Downloading {period} data for {len(symbols)} stocks...")
    else:
        progress = st.progress(5, text=f"Updating {period} data for {len(symbols)} stocks...")

    def on_progress(batch_num, total):
        pct = 5 + int(85 * batch_num / total)
        progress.progress(pct, text=f"Downloading batch {batch_num}/{total}...")

    download_ohlcv(symbols, period=period, progress_callback=on_progress,
                   batch_size=100, batch_delay=0.5)

    progress.progress(92, text="Running VCP screening...")
    run_screening()
    progress.progress(100, text="Done!")


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

    # Show data freshness
    last_screen = _get_last_screen_date()
    if last_screen:
        st.caption(f"Last screened: {last_screen}")

    # Check for screening data
    if not _has_screening_data():
        st.warning("No screening data found. Download data and run screening first.")

        if st.button("Update Data & Screen", type="primary"):
            try:
                _update_and_screen("10d")
                st.success("Done! Screening complete.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        with st.expander("Full History Download (3y) — for first-time setup"):
            st.info(
                "Use this only if you have no data at all. "
                "The screener needs 200+ days of history. This will take ~30-60 minutes."
            )
            if st.button("Download Full History"):
                try:
                    _update_and_screen("3y")
                    st.success("Full setup complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        return

    # Primary action button
    if st.button("Update Data & Screen", type="primary"):
        try:
            _update_and_screen("10d")
            with st.spinner("Analyzing buy signals..."):
                signals = get_buy_signals()
            st.session_state["signals"] = signals
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    with st.expander("Full History Download (3y)"):
        if st.button("Download Full History", key="full_hist_main"):
            try:
                _update_and_screen("3y")
                st.success("Full data refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Auto-load last signals on page load
    if "signals" not in st.session_state:
        with st.spinner("Loading latest buy signals..."):
            signals = get_buy_signals()
        st.session_state["signals"] = signals

    signals = st.session_state.get("signals")

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
