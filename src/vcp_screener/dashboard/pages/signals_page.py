"""Signals tab: VCP buy/sell signals + MR signals, with watchlist integration."""

import streamlit as st

from vcp_screener.db import init_db, get_session
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import get_buy_signals, get_mr_signals
from vcp_screener.services.watchlist_service import add_to_watchlist


def _signal_badge(signal_type: str) -> str:
    """Colored badge for signal type."""
    styles = {
        "BUY": ("background:#1a472a;border-color:#2ea043", "BUY"),
        "WATCH_VOLUME": ("background:#5c4a1e;border-color:#d29922", "WATCH VOL"),
        "NEAR_PIVOT": ("background:#1a3a5c;border-color:#58a6ff", "NEAR PIVOT"),
        "FORMING": ("background:#2d333b;border-color:#444c56", "FORMING"),
        "MR_BUY": ("background:#3d1f5c;border-color:#a371f7", "MR BUY"),
    }
    style, label = styles.get(signal_type, ("background:#2d333b;border-color:#444c56", signal_type))
    return (f'<span style="{style};border:1px solid;color:white;padding:2px 10px;'
            f'border-radius:10px;font-size:0.75rem;font-weight:600">{label}</span>')


def _render_vcp_signal(s: dict, idx: int):
    """Render a single VCP signal card."""
    signal = s["signal"]
    symbol = s["symbol"]

    col_main, col_action = st.columns([5, 1])

    with col_main:
        badge = _signal_badge(signal)

        if signal == "BUY":
            st.markdown(
                f"{badge} &nbsp; **{symbol}** &nbsp; "
                f"<span style='color:#8b949e'>VCP {s['vcp_score']:.0f} · RS {s['rs_percentile']:.0f}</span><br>"
                f"<span style='color:#7ee787'>Entry ₹{s['entry_price']:,.0f}</span> · "
                f"Stop ₹{s['stop_price']:,.0f} · {s['shares']} shares · ₹{s['cost']:,.0f}<br>"
                f"<span style='color:#8b949e;font-size:0.8rem'>{s['reason']}</span>",
                unsafe_allow_html=True,
            )
        elif signal == "WATCH_VOLUME":
            st.markdown(
                f"{badge} &nbsp; **{symbol}** &nbsp; "
                f"<span style='color:#8b949e'>VCP {s['vcp_score']:.0f} · RS {s['rs_percentile']:.0f} · "
                f"Vol {s['vol_ratio']:.1f}x</span><br>"
                f"Close ₹{s['close']:,.0f} · Pivot ₹{s['pivot']:,.0f}<br>"
                f"<span style='color:#8b949e;font-size:0.8rem'>{s['reason']}</span>",
                unsafe_allow_html=True,
            )
        elif signal == "NEAR_PIVOT":
            st.markdown(
                f"{badge} &nbsp; **{symbol}** &nbsp; "
                f"<span style='color:#8b949e'>VCP {s['vcp_score']:.0f} · RS {s['rs_percentile']:.0f} · "
                f"{s['distance_to_pivot_pct']:.1f}% away</span><br>"
                f"Close ₹{s['close']:,.0f} · Pivot ₹{s['pivot']:,.0f}<br>"
                f"<span style='color:#8b949e;font-size:0.8rem'>{s['reason']}</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"{badge} &nbsp; **{symbol}** &nbsp; "
                f"<span style='color:#8b949e'>VCP {s['vcp_score']:.0f} · RS {s['rs_percentile']:.0f} · "
                f"{s['distance_to_pivot_pct']:.1f}% away</span>",
                unsafe_allow_html=True,
            )

    with col_action:
        if st.button("+ WL", key=f"sig_wl_{idx}_{symbol}", use_container_width=True):
            add_to_watchlist(symbol, pivot_price=s.get("pivot"), strategy="vcp")
            st.toast(f"Added {symbol} to Watchlist #1")


def _render_mr_signal(s: dict, idx: int):
    """Render a single MR signal card."""
    symbol = s["symbol"]
    col_main, col_action = st.columns([5, 1])

    with col_main:
        badge = _signal_badge("MR_BUY")
        st.markdown(
            f"{badge} &nbsp; **{symbol}** &nbsp; "
            f"<span style='color:#8b949e'>RSI(2) {s['rsi_2']:.1f} · IBS {s['ibs']:.2f} · "
            f"Z {s['z_score']:.1f}</span><br>"
            f"<span style='color:#a371f7'>Entry ₹{s['entry_price']:,.0f}</span> · "
            f"Stop ₹{s['stop_price']:,.0f} · Target ₹{s['target_price']:,.0f} · "
            f"{s['shares']} shares<br>"
            f"<span style='color:#8b949e;font-size:0.8rem'>{s['reason']}</span>",
            unsafe_allow_html=True,
        )

    with col_action:
        if st.button("+ WL", key=f"mr_wl_{idx}_{symbol}", use_container_width=True):
            add_to_watchlist(symbol, strategy="mean_reversion")
            st.toast(f"Added {symbol} to Watchlist #1")


def render():
    # Load signals
    if "vcp_signals" not in st.session_state:
        with st.spinner("Loading signals..."):
            st.session_state["vcp_signals"] = get_buy_signals()

    signals = st.session_state.get("vcp_signals", [])

    if st.button("Refresh Signals", use_container_width=False):
        with st.spinner("Refreshing..."):
            st.session_state["vcp_signals"] = get_buy_signals()
            st.session_state.pop("mr_signals_tab", None)
        st.rerun()

    # ── VCP and MR side by side ──
    vcp_tab, mr_tab = st.tabs(["VCP Signals", "MR Signals"])

    with vcp_tab:
        if not signals:
            st.info("No VCP signals. Run screening from the Screener tab first.")
            return

        # Regime banner
        regime = signals[0].get("market_regime", "UNKNOWN")
        regime_colors = {"BULLISH": "#1a472a", "CAUTIOUS": "#5c4a1e", "BEARISH": "#5c1a1a"}
        regime_text = {"BULLISH": "Full positions", "CAUTIOUS": "Reduce size", "BEARISH": "Avoid VCP entries"}
        st.markdown(
            f'<div style="background:{regime_colors.get(regime, "#2d333b")};'
            f'padding:8px 16px;border-radius:8px;text-align:center;font-weight:600;'
            f'margin-bottom:12px;font-size:0.9rem">'
            f'Market: {regime} — {regime_text.get(regime, "")}</div>',
            unsafe_allow_html=True,
        )

        # Group by signal type
        groups = {"BUY": [], "WATCH_VOLUME": [], "NEAR_PIVOT": [], "FORMING": []}
        for s in signals:
            groups.get(s["signal"], groups["FORMING"]).append(s)

        # BUY
        if groups["BUY"]:
            st.markdown(f"**Breakout Confirmed** ({len(groups['BUY'])})")
            for i, s in enumerate(groups["BUY"]):
                _render_vcp_signal(s, i)
                st.markdown("<hr style='margin:4px 0;border-color:#21262d'>", unsafe_allow_html=True)

        # WATCH_VOLUME
        if groups["WATCH_VOLUME"]:
            st.markdown(f"**Above Pivot — Needs Volume** ({len(groups['WATCH_VOLUME'])})")
            for i, s in enumerate(groups["WATCH_VOLUME"]):
                _render_vcp_signal(s, 100 + i)
                st.markdown("<hr style='margin:4px 0;border-color:#21262d'>", unsafe_allow_html=True)

        # NEAR_PIVOT
        if groups["NEAR_PIVOT"]:
            st.markdown(f"**Near Pivot — Watchlist** ({len(groups['NEAR_PIVOT'])})")
            for i, s in enumerate(groups["NEAR_PIVOT"]):
                _render_vcp_signal(s, 200 + i)
                st.markdown("<hr style='margin:4px 0;border-color:#21262d'>", unsafe_allow_html=True)

        # FORMING
        if groups["FORMING"]:
            with st.expander(f"Forming ({len(groups['FORMING'])} stocks)"):
                for i, s in enumerate(groups["FORMING"]):
                    _render_vcp_signal(s, 300 + i)

        # Summary
        st.caption(
            f"{len(groups['BUY'])} BUY · {len(groups['WATCH_VOLUME'])} Watch · "
            f"{len(groups['NEAR_PIVOT'])} Near Pivot · {len(groups['FORMING'])} Forming"
        )

    with mr_tab:
        if "mr_signals_tab" not in st.session_state:
            with st.spinner("Scanning for MR candidates..."):
                st.session_state["mr_signals_tab"] = get_mr_signals()

        mr_signals = st.session_state.get("mr_signals_tab", [])

        st.markdown(
            '<div style="background:#3d1f5c;padding:8px 16px;border-radius:8px;'
            'text-align:center;font-weight:600;margin-bottom:12px;font-size:0.9rem">'
            'Mean Reversion — Oversold bounce candidates (RSI(2) &lt; 5, IBS &lt; 0.2)</div>',
            unsafe_allow_html=True,
        )

        if not mr_signals:
            st.info("No MR candidates found. Requires extreme oversold conditions.")
        else:
            for i, s in enumerate(mr_signals):
                _render_mr_signal(s, i)
                st.markdown("<hr style='margin:4px 0;border-color:#21262d'>", unsafe_allow_html=True)
