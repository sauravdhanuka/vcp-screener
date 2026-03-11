"""Screener tab: Top 25 VCP + MR candidates, clickable stock detail, regime display."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from vcp_screener.db import get_session, init_db
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import run_screening, get_stock_detail, get_mr_signals
from vcp_screener.services.market_regime import detect_market_regime
from vcp_screener.services.indicators import sma, rsi, internal_bar_strength
from vcp_screener.services.data_fetcher import (
    fetch_nse_stock_list, save_stock_list, download_ohlcv,
    get_active_symbols,
)
from vcp_screener.services.portfolio_manager import save_equity_snapshot
from vcp_screener.services.watchlist_service import add_to_watchlist


def _regime_badge(regime: str) -> str:
    """Return HTML badge for market regime."""
    colors = {
        "BULLISH": ("#1a472a", "#2ea043", "BULL"),
        "CAUTIOUS": ("#5c4a1e", "#d29922", "CAUTIOUS"),
        "BEARISH": ("#5c1a1a", "#f85149", "BEAR"),
    }
    bg, border, label = colors.get(regime, ("#2d333b", "#444c56", regime))
    return (
        f'<span style="background:{bg};border:1px solid {border};color:white;'
        f'padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:600">'
        f'{label}</span>'
    )


def _update_and_screen(period: str = "10d"):
    """Update prices + run screening with progress bar."""
    symbols = get_active_symbols()
    if not symbols:
        progress = st.progress(0, text="Fetching NSE stock list...")
        stocks = fetch_nse_stock_list()
        save_stock_list(stocks)
        symbols = [s["symbol"] for s in stocks]
        progress.progress(5, text=f"Downloading {period} data for {len(symbols)} stocks...")
    else:
        progress = st.progress(5, text=f"Updating {period} data for {len(symbols)} stocks...")

    def on_progress(batch_num, total):
        pct = 5 + int(80 * batch_num / total)
        progress.progress(pct, text=f"Batch {batch_num}/{total}...")

    download_ohlcv(symbols, period=period, progress_callback=on_progress,
                   batch_size=100, batch_delay=0.5)

    progress.progress(88, text="Running VCP screening...")
    run_screening()
    progress.progress(94, text="Saving equity snapshot...")
    save_equity_snapshot()
    progress.progress(100, text="Done!")


def _render_stock_detail(symbol: str):
    """Render detailed stock analysis in an expander-like view."""
    detail = get_stock_detail(symbol)
    if not detail:
        st.error(f"No data for {symbol}")
        return

    df = detail["price_data"]
    vcp = detail["vcp"]

    # Metrics row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Close", f"₹{detail['close']:,.2f}")
    m2.metric("RS Percentile", f"{detail['rs_percentile']:.0f}")
    m3.metric("VCP Score", f"{detail['vcp_score']:.0f}")
    m4.metric("Pivot", f"₹{vcp['pivot_price']:,.2f}" if vcp.get("found") else "N/A")
    m5.metric("Base Depth", f"{vcp.get('base_depth_pct', 0):.1f}%" if vcp.get("found") else "N/A")

    # Chart with timeframe selector
    tf_col, wl_col = st.columns([4, 1])
    with tf_col:
        tf = st.radio(
            "Timeframe",
            ["3M", "6M", "1Y", "2Y", "All"],
            horizontal=True,
            key=f"tf_{symbol}",
        )
    with wl_col:
        wl_list = st.number_input("WL #", min_value=1, max_value=10, value=1, key=f"wl_num_{symbol}")
        if st.button("+ Watchlist", key=f"wl_add_{symbol}", use_container_width=True):
            add_to_watchlist(
                symbol, list_number=wl_list,
                pivot_price=vcp.get("pivot_price"),
                strategy="vcp",
            )
            st.toast(f"Added {symbol} to Watchlist #{wl_list}")

    # Slice data based on timeframe
    tf_days = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504, "All": len(df)}
    chart_df = df.tail(tf_days.get(tf, 252))

    # Build chart
    contractions = vcp.get("contractions") if vcp.get("found") else None
    pivot = vcp.get("pivot_price") if vcp.get("found") else None

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.75, 0.25],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=chart_df.index, open=chart_df["open"], high=chart_df["high"],
        low=chart_df["low"], close=chart_df["close"], name="OHLC",
        increasing_line_color="#2ea043", decreasing_line_color="#f85149",
    ), row=1, col=1)

    # SMAs
    for period, color, dash in [(20, "#ff7b72", None), (50, "#79c0ff", None), (100, "#d2a8ff", "dot"), (200, "#7ee787", "dot")]:
        if len(chart_df) >= period:
            sma_vals = chart_df["close"].rolling(period).mean()
            fig.add_trace(go.Scatter(
                x=chart_df.index, y=sma_vals, name=f"SMA {period}",
                line=dict(width=1.2, color=color, dash=dash),
            ), row=1, col=1)

    # Pivot line
    if pivot:
        fig.add_hline(y=pivot, line_dash="dash", line_color="#d29922", line_width=1.5,
                      annotation_text=f"Pivot ₹{pivot:,.0f}",
                      annotation_font_color="#d29922", row=1, col=1)

    # Contraction zones
    if contractions:
        for c in contractions:
            fig.add_shape(
                type="rect",
                x0=c.get("high_date"), x1=c.get("low_date"),
                y0=c["low_val"], y1=c["high_val"],
                fillcolor="rgba(210,169,34,0.08)", line=dict(color="#d29922", width=1),
                row=1, col=1,
            )

    # Volume
    vol_colors = ["#f85149" if chart_df["close"].iloc[i] < chart_df["open"].iloc[i] else "#2ea043"
                  for i in range(len(chart_df))]
    fig.add_trace(go.Bar(
        x=chart_df.index, y=chart_df["volume"], name="Volume",
        marker_color=vol_colors, opacity=0.5,
    ), row=2, col=1)

    fig.update_layout(
        height=500, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font_size=10),
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
    )
    fig.update_xaxes(gridcolor="#21262d", zeroline=False)
    fig.update_yaxes(gridcolor="#21262d", zeroline=False)
    st.plotly_chart(fig, use_container_width=True)

    # Trend Template + VCP detail in columns
    col_trend, col_vcp = st.columns(2)
    with col_trend:
        st.markdown("**Trend Template**")
        trend = detail["trend_template"]
        if trend.get("conditions"):
            for name, passes in trend["conditions"].items():
                icon = "✅" if passes else "❌"
                label = name.split("_", 1)[1].replace("_", " ").title() if "_" in name else name
                st.markdown(f"{icon} {label}", unsafe_allow_html=True)

    with col_vcp:
        st.markdown("**VCP Pattern**")
        if vcp.get("found"):
            st.write(f"Contractions: **{vcp['num_contractions']}** · "
                     f"Tightness: **{vcp['tightness_ratio']:.2f}** · "
                     f"Vol Dry-up: **{vcp['volume_dry_up_pct']:.0f}%**")
            st.write(f"Duration: **{vcp['base_duration_days']} days** · "
                     f"Monotonic: {'Yes' if vcp.get('is_monotonic') else 'No'} · "
                     f"Shakeout: {'Yes' if vcp.get('shakeout_detected') else 'No'}")
            for i, c in enumerate(vcp["contractions"], 1):
                st.caption(f"T{i}: {c['range_pct']:.1f}% range · "
                           f"₹{c['high_val']:,.0f} → ₹{c['low_val']:,.0f}")
        else:
            st.warning(f"No VCP pattern: {vcp.get('reason', 'unknown')}")


def render():
    # ── Update button row ──
    btn_col, regime_col = st.columns([1, 2])

    with btn_col:
        c1, c2 = st.columns(2)
        with c1:
            update_clicked = st.button("Update & Screen", type="primary", use_container_width=True)
        with c2:
            with st.popover("Full Download"):
                st.caption("First-time setup: download 3 years of history (~30-60 min)")
                if st.button("Download 3Y History"):
                    try:
                        _update_and_screen("3y")
                        st.success("Done!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    if update_clicked:
        try:
            _update_and_screen("10d")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    # ── Load screening data ──
    session = get_session()
    try:
        dates = [
            r[0] for r in
            session.query(ScreeningResult.run_date)
            .distinct()
            .order_by(ScreeningResult.run_date.desc())
            .all()
        ]

        if not dates:
            st.info("No screening data. Click **Update & Screen** to get started.")
            return

        # Regime badge
        results = (
            session.query(ScreeningResult)
            .filter(ScreeningResult.run_date == dates[0])
            .order_by(ScreeningResult.rank)
            .limit(25)
            .all()
        )
        if not results:
            st.info("No results found.")
            return

        regime = results[0].market_regime
        with regime_col:
            st.markdown(
                f"Market Regime: {_regime_badge(regime)} &nbsp;&nbsp; "
                f"<span style='color:#8b949e;font-size:0.8rem'>Screened: {dates[0]}</span>",
                unsafe_allow_html=True,
            )

        # ── VCP Top 25 + MR Side-by-side ──
        vcp_col, mr_col = st.columns([3, 2])

        with vcp_col:
            st.markdown("##### VCP Candidates")

            data = []
            for r in results:
                data.append({
                    "Rank": r.rank,
                    "Symbol": r.symbol,
                    "Close": r.close_price,
                    "VCP": r.vcp_score,
                    "RS": r.rs_percentile,
                    "Pivot": r.pivot_price,
                    "Depth%": r.base_depth_pct,
                    "Contr": r.num_contractions,
                    "Tight": r.tightness_ratio,
                    "VolDry%": r.volume_dry_up,
                    "Days": r.base_duration_days,
                })

            df = pd.DataFrame(data)

            # Display as interactive table
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                height=400,
                column_config={
                    "Close": st.column_config.NumberColumn(format="₹%.1f"),
                    "Pivot": st.column_config.NumberColumn(format="₹%.1f"),
                    "VCP": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                    "RS": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                    "Tight": st.column_config.NumberColumn(format="%.2f"),
                    "Depth%": st.column_config.NumberColumn(format="%.1f"),
                    "VolDry%": st.column_config.NumberColumn(format="%.0f"),
                },
            )

            # CSV export
            csv = df.to_csv(index=False)
            st.download_button("Export CSV", csv, f"vcp_top25_{dates[0]}.csv", "text/csv")

        with mr_col:
            st.markdown("##### Mean Reversion Candidates")
            if "mr_cache" not in st.session_state or st.session_state.get("mr_cache_stale"):
                mr_signals = get_mr_signals()
                st.session_state["mr_cache"] = mr_signals
                st.session_state["mr_cache_stale"] = False
            else:
                mr_signals = st.session_state["mr_cache"]

            if mr_signals:
                mr_data = []
                for s in mr_signals:
                    mr_data.append({
                        "Symbol": s["symbol"],
                        "Close": s["close"],
                        "RSI(2)": s["rsi_2"],
                        "IBS": s["ibs"],
                        "Z": s["z_score"],
                        "VolR": s["volume_ratio"],
                        "Target": s["target_price"],
                    })

                mr_df = pd.DataFrame(mr_data)
                st.dataframe(
                    mr_df,
                    hide_index=True,
                    use_container_width=True,
                    height=400,
                    column_config={
                        "Close": st.column_config.NumberColumn(format="₹%.1f"),
                        "RSI(2)": st.column_config.NumberColumn(format="%.1f"),
                        "IBS": st.column_config.NumberColumn(format="%.3f"),
                        "Z": st.column_config.NumberColumn(format="%.1f"),
                        "VolR": st.column_config.NumberColumn(format="%.1fx"),
                        "Target": st.column_config.NumberColumn(format="₹%.0f"),
                    },
                )
            else:
                st.caption("No MR candidates right now. MR requires extreme oversold conditions "
                           "(RSI(2) < 5, IBS < 0.2, below Bollinger Band).")

        # ── Stock Detail Section ──
        st.markdown("---")
        all_symbols = [r.symbol for r in results]
        mr_symbols = [s["symbol"] for s in (mr_signals if mr_signals else [])]
        combined = list(dict.fromkeys(all_symbols + mr_symbols))  # dedupe preserving order

        selected = st.selectbox(
            "Select stock for detailed analysis",
            [""] + combined,
            format_func=lambda x: "Choose a stock..." if x == "" else x,
            key="screener_stock_select",
        )

        if selected:
            _render_stock_detail(selected)

    finally:
        session.close()
