"""Screener page: Top 50 VCP candidates with filters."""

import streamlit as st
import pandas as pd

from vcp_screener.db import get_session, init_db
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.screener import run_screening
from vcp_screener.services.data_fetcher import fetch_nse_stock_list, save_stock_list, download_ohlcv


def render():
    st.header("VCP Screener Results")

    init_db()

    # Action buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Run Screening Now", type="primary"):
            with st.spinner("Running VCP screening pipeline..."):
                results = run_screening()
            st.success(f"Screening complete! Found {len(results)} candidates.")
            st.rerun()
    with col_b:
        if st.button("Download Data (30d)"):
            with st.spinner("Fetching NSE stock list..."):
                stocks = fetch_nse_stock_list()
                save_stock_list(stocks)
                symbols = [s["symbol"] for s in stocks]
            with st.spinner(f"Downloading 30d prices for {len(symbols)} stocks..."):
                download_ohlcv(symbols, period="30d")
            st.success("Data downloaded! Click 'Run Screening Now' next.")
            st.rerun()

    session = get_session()
    try:
        dates = [r[0] for r in session.query(ScreeningResult.run_date).distinct().order_by(ScreeningResult.run_date.desc()).all()]

        if not dates:
            st.warning("No screening results found. Click **Download Data** then **Run Screening Now**.")
            return

        selected_date = st.selectbox("Screening Date", dates)

        results = (
            session.query(ScreeningResult)
            .filter(ScreeningResult.run_date == selected_date)
            .order_by(ScreeningResult.rank)
            .all()
        )

        if not results:
            st.info("No results for this date.")
            return

        regime = results[0].market_regime
        regime_colors = {"BULLISH": "🟢", "CAUTIOUS": "🟡", "BEARISH": "🔴"}
        st.markdown(f"**Market Regime:** {regime_colors.get(regime, '⚪')} {regime}")

        col1, col2, col3 = st.columns(3)
        with col1:
            min_score = st.slider("Min VCP Score", 0, 100, 0)
        with col2:
            min_rs = st.slider("Min RS Percentile", 0, 100, 0)
        with col3:
            min_contractions = st.slider("Min Contractions", 1, 6, 2)

        data = [{
            "Rank": r.rank,
            "Symbol": r.symbol,
            "Close": r.close_price,
            "VCP Score": r.vcp_score,
            "RS %ile": r.rs_percentile,
            "Pivot": r.pivot_price,
            "Depth %": r.base_depth_pct,
            "Contractions": r.num_contractions,
            "Tightness": r.tightness_ratio,
            "Vol Dry %": r.volume_dry_up,
            "Duration": r.base_duration_days,
        } for r in results]

        df = pd.DataFrame(data)
        df = df[
            (df["VCP Score"] >= min_score) &
            (df["RS %ile"] >= min_rs) &
            (df["Contractions"] >= min_contractions)
        ]

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Candidates", len(df))
        mc2.metric("Avg VCP Score", f"{df['VCP Score'].mean():.1f}" if len(df) else "N/A")
        mc3.metric("Avg RS %ile", f"{df['RS %ile'].mean():.0f}" if len(df) else "N/A")
        mc4.metric("Regime", regime)

        st.dataframe(
            df,
            hide_index=True,
            column_config={
                "Close": st.column_config.NumberColumn(format="₹%.1f"),
                "Pivot": st.column_config.NumberColumn(format="₹%.1f"),
                "VCP Score": st.column_config.NumberColumn(format="%.1f"),
                "RS %ile": st.column_config.NumberColumn(format="%.0f"),
            },
        )
    finally:
        session.close()
