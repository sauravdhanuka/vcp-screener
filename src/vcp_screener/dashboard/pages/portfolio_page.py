"""Portfolio tab: current holdings, sell alerts, trade history."""

import streamlit as st
import pandas as pd

from vcp_screener.db import init_db
from vcp_screener.services.portfolio_manager import (
    get_holdings, check_sell_alerts, update_trailing_stops,
    get_closed_trades, buy_stock, sell_stock, get_effective_max_positions,
)


def render():
    tab_hold, tab_alerts, tab_history, tab_buy = st.tabs([
        "Holdings", "Sell Alerts", "Trade History", "New Position",
    ])

    with tab_hold:
        _render_holdings()

    with tab_alerts:
        _render_alerts()

    with tab_history:
        _render_history()

    with tab_buy:
        _render_buy_form()


def _render_holdings():
    holdings = get_holdings()

    if not holdings:
        st.info("No open positions.")
        return

    # Summary metrics
    total_cost = sum(h["cost"] for h in holdings)
    total_value = sum(h["market_value"] for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
    effective_max = get_effective_max_positions()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Positions", f"{len(holdings)}/{effective_max}")
    m2.metric("Invested", f"₹{total_cost:,.0f}")
    m3.metric("Market Value", f"₹{total_value:,.0f}")
    m4.metric("P&L", f"₹{total_pnl:+,.0f}")
    m5.metric("Return", f"{total_pnl_pct:+.1f}%")

    st.markdown("")

    # Holdings cards
    for h in holdings:
        pnl_color = "#2ea043" if h["pnl"] >= 0 else "#f85149"
        strategy_badge = "MR" if h.get("strategy") == "mean_reversion" else "VCP"
        strat_color = "#a371f7" if strategy_badge == "MR" else "#58a6ff"
        effective_stop = max(h["stop_loss"], h["trailing_stop"] or 0)

        col_info, col_pnl, col_sell = st.columns([4, 2, 1])

        with col_info:
            st.markdown(
                f'<span style="background:{strat_color}20;color:{strat_color};'
                f'padding:1px 8px;border-radius:8px;font-size:0.7rem;font-weight:600">'
                f'{strategy_badge}</span> &nbsp;'
                f'**{h["symbol"]}** &nbsp; '
                f'<span style="color:#8b949e">{h["shares"]} shares @ ₹{h["entry_price"]:,.1f} · '
                f'{h["entry_date"]}</span>',
                unsafe_allow_html=True,
            )

        with col_pnl:
            st.markdown(
                f'₹{h["current_price"]:,.1f} &nbsp; '
                f'<span style="color:{pnl_color};font-weight:600">'
                f'₹{h["pnl"]:+,.0f} ({h["pnl_pct"]:+.1f}%)</span><br>'
                f'<span style="color:#8b949e;font-size:0.8rem">Stop: ₹{effective_stop:,.1f}</span>',
                unsafe_allow_html=True,
            )

        with col_sell:
            if st.button("Sell", key=f"sell_{h['id']}", type="secondary", use_container_width=True):
                pos = sell_stock(h["id"], h["current_price"])
                if pos:
                    st.toast(f"Sold {pos.symbol} @ ₹{pos.exit_price:,.1f} — P&L: ₹{pos.pnl:+,.0f}")
                    st.rerun()

        st.markdown("<hr style='margin:2px 0;border-color:#21262d'>", unsafe_allow_html=True)


def _render_alerts():
    update_trailing_stops()
    alerts = check_sell_alerts()

    if not alerts:
        st.markdown(
            '<div style="background:#1a472a;border:1px solid #2ea043;padding:12px 16px;'
            'border-radius:8px;text-align:center">All positions OK — no sell alerts</div>',
            unsafe_allow_html=True,
        )
        return

    for a in alerts:
        alert_types = a["alerts"]
        strategy = a.get("strategy", "vcp")
        is_critical = any(x in str(alert_types) for x in ["STOP", "PROTECT", "FAILED", "TIMEOUT"])
        border_color = "#f85149" if is_critical else "#d29922"
        bg_color = "#5c1a1a" if is_critical else "#5c4a1e"

        alert_badges = " ".join([
            f'<span style="background:{bg_color};border:1px solid {border_color};color:white;'
            f'padding:1px 8px;border-radius:8px;font-size:0.7rem">{t}</span>'
            for t in alert_types
        ])

        label = "[MR] " if strategy == "mean_reversion" else ""
        stop_display = a.get("effective_stop", a.get("stop_loss", 0))

        st.markdown(
            f'<div style="border-left:3px solid {border_color};padding:8px 12px;'
            f'margin-bottom:8px;border-radius:0 8px 8px 0;background:{bg_color}33">'
            f'<b>{label}{a["symbol"]}</b> #{a["position_id"]} &nbsp; {alert_badges}<br>'
            f'<span style="color:#8b949e">Entry ₹{a["entry_price"]:,.1f} → '
            f'₹{a["current_price"]:,.1f} · '
            f'{a["gain_pct"]:+.1f}% · Hold {a.get("hold_days", 0)}d · '
            f'Stop ₹{stop_display:,.1f}</span></div>',
            unsafe_allow_html=True,
        )


def _render_history():
    trades = get_closed_trades()

    if not trades:
        st.info("No closed trades yet.")
        return

    wins = [t for t in trades if (t.get("pnl") or 0) > 0]
    total_pnl = sum(t.get("pnl") or 0 for t in trades)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Trades", len(trades))
    m2.metric("Win Rate", f"{len(wins) / len(trades) * 100:.0f}%" if trades else "N/A")
    m3.metric("Total P&L", f"₹{total_pnl:+,.0f}")

    df = pd.DataFrame(trades)
    display_cols = ["symbol", "entry_date", "exit_date", "entry_price", "exit_price",
                    "shares", "pnl", "pnl_pct", "exit_reason"]
    df = df[[c for c in display_cols if c in df.columns]]

    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "entry_price": st.column_config.NumberColumn("Entry", format="₹%.1f"),
            "exit_price": st.column_config.NumberColumn("Exit", format="₹%.1f"),
            "pnl": st.column_config.NumberColumn("P&L", format="₹%.0f"),
            "pnl_pct": st.column_config.NumberColumn("P&L%", format="%.1f%%"),
        },
    )


def _render_buy_form():
    st.markdown("##### Record New Position")

    c1, c2, c3 = st.columns(3)
    with c1:
        buy_symbol = st.text_input("Symbol", placeholder="e.g. RELIANCE").upper().strip()
        buy_strategy = st.selectbox("Strategy", ["vcp", "mean_reversion"])
    with c2:
        buy_entry = st.number_input("Entry Price (₹)", min_value=1.0, step=1.0)
        buy_stop = st.number_input("Stop Loss (₹, 0 = auto)", min_value=0.0, step=1.0, value=0.0)
    with c3:
        buy_shares = st.number_input("Shares (0 = auto)", min_value=0, step=1, value=0)
        buy_pivot = st.number_input("Pivot Price (₹, optional)", min_value=0.0, step=1.0, value=0.0)

    if st.button("Buy", type="primary"):
        if buy_symbol and buy_entry > 0:
            pos = buy_stock(
                symbol=buy_symbol,
                entry_price=buy_entry,
                stop_loss_price=buy_stop if buy_stop > 0 else None,
                shares=buy_shares if buy_shares > 0 else None,
                strategy=buy_strategy,
                pivot_price=buy_pivot if buy_pivot > 0 else None,
            )
            if pos:
                st.success(f"Bought {pos.shares} shares of {pos.symbol} @ ₹{pos.entry_price:,.1f}")
                st.rerun()
            else:
                st.error("Could not buy. Max positions reached or invalid prices.")
        else:
            st.warning("Enter symbol and price.")
