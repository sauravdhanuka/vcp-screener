"""Portfolio page: holdings, P&L, alerts, history."""

import streamlit as st
import pandas as pd

from vcp_screener.db import init_db
from vcp_screener.services.portfolio_manager import (
    get_holdings, check_sell_alerts, update_trailing_stops, get_closed_trades,
    buy_stock, sell_stock,
)


def render():
    st.header("Portfolio")
    init_db()

    tab1, tab2, tab3 = st.tabs(["Holdings", "Sell Alerts", "Trade History"])

    with tab1:
        _render_holdings()

    with tab2:
        _render_alerts()

    with tab3:
        _render_history()


def _render_holdings():
    # Buy Stock form
    with st.expander("Buy Stock"):
        with st.form("buy_form"):
            bc1, bc2 = st.columns(2)
            with bc1:
                buy_symbol = st.text_input("Symbol", placeholder="e.g. RELIANCE").upper().strip()
                buy_entry = st.number_input("Entry Price (₹)", min_value=1.0, step=1.0)
            with bc2:
                buy_stop = st.number_input("Stop Loss (₹, 0 = auto)", min_value=0.0, step=1.0, value=0.0)
                buy_shares = st.number_input("Shares (0 = auto)", min_value=0, step=1, value=0)
            buy_submit = st.form_submit_button("Buy", type="primary")
            if buy_submit and buy_symbol and buy_entry > 0:
                pos = buy_stock(
                    symbol=buy_symbol,
                    entry_price=buy_entry,
                    stop_loss_price=buy_stop if buy_stop > 0 else None,
                    shares=buy_shares if buy_shares > 0 else None,
                )
                if pos:
                    st.success(f"Bought {pos.shares} shares of {pos.symbol} @ ₹{pos.entry_price:,.1f}")
                    st.rerun()
                else:
                    st.error("Could not buy. Max positions reached or invalid prices.")

    holdings = get_holdings()
    if not holdings:
        st.info("No open positions. Use the **Buy Stock** form above to add positions.")
        return

    total_cost = sum(h["cost"] for h in holdings)
    total_value = sum(h["market_value"] for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Positions", len(holdings))
    mc2.metric("Total Cost", f"₹{total_cost:,.0f}")
    mc3.metric("Market Value", f"₹{total_value:,.0f}")
    mc4.metric("P&L", f"₹{total_pnl:+,.0f}", delta=f"{total_pnl_pct:+.1f}%")

    # Holdings table with sell buttons
    for h in holdings:
        col_info, col_sell = st.columns([5, 1])
        with col_info:
            pnl_color = "green" if h["pnl"] >= 0 else "red"
            st.markdown(
                f"**{h['symbol']}** — {h['shares']} @ ₹{h['entry_price']:,.1f} → "
                f"₹{h['current_price']:,.1f} · "
                f"P&L: :{pnl_color}[₹{h['pnl']:+,.0f} ({h['pnl_pct']:+.1f}%)]"
            )
        with col_sell:
            if st.button("Sell", key=f"sell_{h['id']}"):
                pos = sell_stock(h["id"], h["current_price"])
                if pos:
                    st.success(f"Sold {pos.symbol} @ ₹{pos.exit_price:,.1f} — P&L: ₹{pos.pnl:+,.0f}")
                    st.rerun()

    # Also show as table for detailed view
    with st.expander("Detailed Table"):
        df = pd.DataFrame(holdings)
        display_cols = ["symbol", "entry_date", "entry_price", "shares", "current_price",
                        "cost", "market_value", "pnl", "pnl_pct", "stop_loss", "trailing_stop"]
        df = df[[c for c in display_cols if c in df.columns]]
        st.dataframe(df, hide_index=True)


def _render_alerts():
    update_trailing_stops()
    alerts = check_sell_alerts()
    if not alerts:
        st.success("No sell alerts. All positions OK.")
    else:
        for a in alerts:
            alert_types = ", ".join(a["alerts"])
            color = "🔴" if any(x in alert_types for x in ["STOP", "PROTECT"]) else "🟡"
            st.warning(f"{color} **{a['symbol']}** (#{a['position_id']}): {alert_types}\n\n"
                       f"Entry: ₹{a['entry_price']:,.1f} | Current: ₹{a['current_price']:,.1f} | "
                       f"Gain: {a['gain_pct']:+.1f}% | Stop: ₹{a['effective_stop']:,.1f}")


def _render_history():
    trades = get_closed_trades()
    if not trades:
        st.info("No closed trades yet.")
        return

    df = pd.DataFrame(trades)
    wins = len([t for t in trades if (t.get("pnl") or 0) > 0])
    total = len(trades)
    total_pnl = sum(t.get("pnl") or 0 for t in trades)

    tc1, tc2, tc3 = st.columns(3)
    tc1.metric("Total Trades", total)
    tc2.metric("Win Rate", f"{wins / total * 100:.0f}%" if total else "N/A")
    tc3.metric("Total P&L", f"₹{total_pnl:+,.0f}")

    st.dataframe(df, hide_index=True)
