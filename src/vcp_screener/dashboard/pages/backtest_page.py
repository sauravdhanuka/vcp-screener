"""Backtest page: config form, KPIs, equity curve, trade distribution."""

from datetime import date

import streamlit as st
import pandas as pd

from vcp_screener.db import get_session, init_db
from vcp_screener.models.backtest import BacktestRun, BacktestTrade, BacktestEquity
from vcp_screener.dashboard.components.charts import equity_curve_chart


def render():
    st.header("Backtesting")
    init_db()

    tab1, tab2 = st.tabs(["Run Backtest", "Past Results"])

    with tab1:
        _render_run_form()

    with tab2:
        _render_past_results()


def _render_run_form():
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start Date", value=date(2024, 1, 1))
        capital = st.number_input("Initial Capital (₹)", value=100000, step=50000)
    with col2:
        end = st.date_input("End Date", value=date(2024, 9, 30))
        max_pos = st.number_input("Max Positions", value=5, min_value=1, max_value=20)

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Running backtest... This may take several minutes."):
            from vcp_screener.services.backtester import run_backtest
            results = run_backtest(start, end, initial_capital=capital, max_positions=max_pos)

        if "error" in results:
            st.error(results["error"])
            return

        if results.get("total_trades", 0) == 0:
            st.warning("No trades were executed during this period. Try a longer date range or check if enough historical data exists.")
            return

        _display_results(results)


def _render_past_results():
    session = get_session()
    try:
        runs = session.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(10).all()
        if not runs:
            st.info("No past backtest results.")
            return

        for run in runs:
            with st.expander(f"Run #{run.id}: {run.start_date} to {run.end_date} | Return: {run.total_return_pct:+.1f}%"):
                kc1, kc2, kc3, kc4 = st.columns(4)
                kc1.metric("Return", f"{run.total_return_pct:+.1f}%")
                kc2.metric("Max DD", f"{run.max_drawdown_pct:.1f}%")
                kc3.metric("Trades", run.total_trades)
                kc4.metric("Win Rate", f"{run.win_rate_pct:.0f}%")

                eq_data = (
                    session.query(BacktestEquity)
                    .filter(BacktestEquity.run_id == run.id)
                    .order_by(BacktestEquity.date)
                    .all()
                )
                if eq_data:
                    fig = equity_curve_chart([
                        {"date": e.date, "equity": e.equity, "drawdown_pct": e.drawdown_pct}
                        for e in eq_data
                    ])
                    st.plotly_chart(fig)
    finally:
        session.close()


def _display_results(results: dict):
    st.subheader("Results")

    kc1, kc2, kc3, kc4, kc5 = st.columns(5)
    kc1.metric("Total Return", f"{results['total_return_pct']:+.1f}%")
    kc2.metric("CAGR", f"{results.get('cagr_pct', 0):.1f}%")
    kc3.metric("Max Drawdown", f"{results.get('max_drawdown_pct', 0):.1f}%")
    kc4.metric("Sharpe Ratio", f"{results.get('sharpe_ratio', 0):.2f}")
    kc5.metric("Win Rate", f"{results['win_rate_pct']:.0f}%")

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Initial Capital", f"₹{results['initial_capital']:,.0f}")
    mc2.metric("Final Capital", f"₹{results['final_capital']:,.0f}")
    mc3.metric("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
    mc4.metric("Avg Hold Days", f"{results.get('avg_hold_days', 0):.0f}")

    eq = results.get("equity_curve", [])
    if eq:
        fig = equity_curve_chart(eq)
        st.plotly_chart(fig)

    trades = results.get("trades", [])
    if trades:
        st.subheader(f"Trade Log ({len(trades)} trades)")
        df = pd.DataFrame(trades)
        for col in ["entry_date", "exit_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        st.dataframe(df, hide_index=True)
