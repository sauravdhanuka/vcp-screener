"""Watchlist tab: numbered watchlists with live prices."""

import streamlit as st
import pandas as pd

from vcp_screener.db import init_db
from vcp_screener.services.watchlist_service import (
    add_to_watchlist, remove_from_watchlist, get_watchlist, get_watchlist_numbers,
)


def render():
    init_db()

    # ── Add to watchlist form ──
    with st.expander("Add Stock to Watchlist"):
        ac1, ac2, ac3, ac4 = st.columns([2, 1, 1, 1])
        with ac1:
            wl_symbol = st.text_input("Symbol", placeholder="e.g. RELIANCE", key="wl_add_sym").upper().strip()
        with ac2:
            wl_num = st.number_input("Watchlist #", min_value=1, max_value=10, value=1, key="wl_add_num")
        with ac3:
            wl_strategy = st.selectbox("Strategy", ["vcp", "mean_reversion"], key="wl_add_strat")
        with ac4:
            wl_notes = st.text_input("Notes", placeholder="Optional", key="wl_add_notes")

        if st.button("Add to Watchlist", use_container_width=True):
            if wl_symbol:
                item = add_to_watchlist(
                    wl_symbol, list_number=wl_num,
                    strategy=wl_strategy,
                    notes=wl_notes if wl_notes else None,
                )
                if item:
                    st.toast(f"Added {wl_symbol} to Watchlist #{wl_num}")
                    st.rerun()
            else:
                st.warning("Enter a symbol.")

    # ── Display watchlists ──
    wl_numbers = get_watchlist_numbers()

    if not wl_numbers:
        st.info("No watchlist items. Add stocks from the Screener or Signals tab, or use the form above.")
        return

    # Create tabs for each watchlist
    tab_labels = [f"Watchlist #{n}" for n in wl_numbers]
    tabs = st.tabs(tab_labels)

    for tab, list_num in zip(tabs, wl_numbers):
        with tab:
            items = get_watchlist(list_number=list_num)

            if not items:
                st.info(f"Watchlist #{list_num} is empty.")
                continue

            # Summary
            total = len(items)
            gainers = len([i for i in items if (i.get("change_pct") or 0) > 0])
            losers = len([i for i in items if (i.get("change_pct") or 0) < 0])
            st.caption(f"{total} stocks · {gainers} gainers · {losers} losers")

            # Render items
            for item in items:
                col_info, col_price, col_rm = st.columns([4, 3, 1])

                with col_info:
                    strat = item.get("strategy", "vcp")
                    strat_color = "#a371f7" if strat == "mean_reversion" else "#58a6ff"
                    strat_label = "MR" if strat == "mean_reversion" else "VCP"

                    notes_text = f" · {item['notes']}" if item.get("notes") else ""

                    st.markdown(
                        f'<span style="background:{strat_color}20;color:{strat_color};'
                        f'padding:1px 6px;border-radius:8px;font-size:0.7rem;font-weight:600">'
                        f'{strat_label}</span> &nbsp;'
                        f'**{item["symbol"]}**'
                        f'<span style="color:#8b949e;font-size:0.8rem">{notes_text}</span>',
                        unsafe_allow_html=True,
                    )

                with col_price:
                    current = item.get("current_price")
                    added = item.get("added_price")
                    change = item.get("change_pct")
                    pivot = item.get("pivot_price")

                    price_parts = []
                    if current:
                        price_parts.append(f"₹{current:,.1f}")
                    if change is not None:
                        color = "#2ea043" if change >= 0 else "#f85149"
                        price_parts.append(f'<span style="color:{color}">{change:+.1f}%</span>')
                    if pivot:
                        dist = (pivot - (current or 0)) / pivot * 100 if current and pivot > 0 else 0
                        if dist > 0:
                            price_parts.append(f'<span style="color:#8b949e">{dist:.1f}% to pivot</span>')
                        else:
                            price_parts.append(f'<span style="color:#2ea043">Above pivot</span>')

                    st.markdown(" · ".join(price_parts) if price_parts else "—", unsafe_allow_html=True)

                with col_rm:
                    if st.button("✕", key=f"rm_wl_{item['id']}", use_container_width=True):
                        remove_from_watchlist(item["id"])
                        st.rerun()

                st.markdown("<hr style='margin:2px 0;border-color:#21262d'>", unsafe_allow_html=True)
