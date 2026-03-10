"""Year-by-year breakdown for Winner and Runner-up MR configs."""

import logging
import sys
import time
from datetime import date

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import (
    BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators,
)

MR_WINNER = {"stop_pct": 12, "require_rsi": True, "rsi_entry": 5}
MR_RUNNERUP = {
    "stop_pct": 5, "target": "sma10", "rsi_exit": 65, "entry_std": 1.5,
    "require_rsi": True, "rsi_entry": 5, "require_ibs": True, "ibs_entry": 0.2,
}
MR_MIDDLE = {
    "stop_pct": 12, "require_rsi": True, "rsi_entry": 5, "rsi_exit": 65,
}

CONFIGS = [
    ("Winner (Stop12+RSI<5)", MR_WINNER),
    ("Runner-up (Stop5+SMA10+RSI65+Ent1.5+RSI<5+IBS<0.2)", MR_RUNNERUP),
    ("Middle (Stop12+RSI<5+RSI65exit)", MR_MIDDLE),
]

print("Loading data...", flush=True)
t0 = time.time()
all_data, breadth = load_backtest_data()
print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

start, end = date(2016, 4, 1), date(2026, 3, 1)

print("Precomputing VCP screens...", flush=True)
t0 = time.time()
screens = precompute_screens(all_data, start, end)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

print("Precomputing MR indicators...", flush=True)
t0 = time.time()
mr_ind = precompute_mr_indicators(all_data)
print(f"Done in {time.time()-t0:.0f}s.\n", flush=True)

for cfg_name, mr_cfg in CONFIGS:
    engine = BacktestEngine(initial_capital=500000, max_positions=5, mr_config=mr_cfg)
    r = engine.run(start, end, preloaded_data=all_data, preloaded_breadth=breadth,
                   precomputed_screens=screens, precomputed_mr_ind=mr_ind)

    print(f"{'='*110}")
    print(f"  {cfg_name}")
    print(f"  10Y: Return {r['total_return_pct']:.1f}%  |  CAGR {r['cagr_pct']:.1f}%  |  MaxDD {r['max_drawdown_pct']:.1f}%  |  Sharpe {r['sharpe_ratio']:.2f}  |  PF {r['profit_factor']:.2f}  |  Trades {r['total_trades']}")
    print(f"{'='*110}")

    # Group equity curve by year
    ec = r["equity_curve"]
    trades = r["trades"]

    years = {}
    for e in ec:
        y = e["date"].year
        if y not in years:
            years[y] = []
        years[y].append(e)

    print(f"  {'Year':<6} {'Start Eq':>14} {'End Eq':>14} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} | {'Trd':>4} {'W':>3} {'L':>3} {'WR':>6} | {'MR':>3} {'MR W':>4} {'MR PnL':>12} | {'VCP':>4} {'VCP W':>5} {'VCP PnL':>12}")
    print(f"  {'-'*106}")

    total_mr_pnl = 0
    total_vcp_pnl = 0

    for y in sorted(years.keys()):
        entries = years[y]
        start_eq = entries[0]["equity"]
        end_eq = entries[-1]["equity"]
        ret_pct = (end_eq / start_eq - 1) * 100

        # Max drawdown within year
        peak = start_eq
        max_dd = 0
        for e in entries:
            if e["equity"] > peak:
                peak = e["equity"]
            dd = (peak - e["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Sharpe for year
        eq_vals = [e["equity"] for e in entries]
        if len(eq_vals) >= 2:
            daily_ret = pd.Series(eq_vals).pct_change().dropna()
            sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
        else:
            sharpe = 0

        # Year's trades (by entry date)
        yr_trades = [t for t in trades if t["entry_date"].year == y]
        yr_wins = [t for t in yr_trades if t["pnl"] > 0]
        yr_losses = [t for t in yr_trades if t["pnl"] <= 0]
        wr = len(yr_wins) / len(yr_trades) * 100 if yr_trades else 0

        yr_mr = [t for t in yr_trades if t["exit_reason"].startswith("mr_")]
        yr_mr_wins = [t for t in yr_mr if t["pnl"] > 0]
        mr_pnl = sum(t["pnl"] for t in yr_mr)

        yr_vcp = [t for t in yr_trades if not t["exit_reason"].startswith("mr_")]
        yr_vcp_wins = [t for t in yr_vcp if t["pnl"] > 0]
        vcp_pnl = sum(t["pnl"] for t in yr_vcp)

        total_mr_pnl += mr_pnl
        total_vcp_pnl += vcp_pnl

        print(f"  {y:<6} {start_eq:>14,.0f} {end_eq:>14,.0f} {ret_pct:>7.1f}% {max_dd:>6.1f}% {sharpe:>7.2f} | {len(yr_trades):>4} {len(yr_wins):>3} {len(yr_losses):>3} {wr:>5.1f}% | {len(yr_mr):>3} {len(yr_mr_wins):>4} {mr_pnl:>+12,.0f} | {len(yr_vcp):>4} {len(yr_vcp_wins):>5} {vcp_pnl:>+12,.0f}")

    print(f"  {'-'*106}")
    print(f"  {'TOTAL':<6} {'500,000':>14} {end_eq:>14,.0f} {r['total_return_pct']:>7.1f}%{r['max_drawdown_pct']:>6.1f}% {r['sharpe_ratio']:>7.2f} | {r['total_trades']:>4}                    | {'':>3} {'':>4} {total_mr_pnl:>+12,.0f} | {'':>4} {'':>5} {total_vcp_pnl:>+12,.0f}")

    # Exit reason breakdown
    print(f"\n  Exit Reasons:")
    exit_stats = {}
    for t in trades:
        reason = t["exit_reason"]
        if reason not in exit_stats:
            exit_stats[reason] = {"count": 0, "pnl": 0, "wins": 0}
        exit_stats[reason]["count"] += 1
        exit_stats[reason]["pnl"] += t["pnl"]
        if t["pnl"] > 0:
            exit_stats[reason]["wins"] += 1

    for reason, stats in sorted(exit_stats.items(), key=lambda x: -x[1]["count"]):
        wr = stats["wins"] / stats["count"] * 100 if stats["count"] > 0 else 0
        print(f"    {reason:<25} {stats['count']:>4} trades  WR:{wr:>5.1f}%  PnL: Rs {stats['pnl']:>+15,.0f}")

    # Bear year analysis
    print(f"\n  Bear Year Deep Dive:")
    for bear_year in [2018, 2020, 2022]:
        yr_mr = [t for t in trades if t["entry_date"].year == bear_year and t["exit_reason"].startswith("mr_")]
        if yr_mr:
            wins = sum(1 for t in yr_mr if t["pnl"] > 0)
            pnl = sum(t["pnl"] for t in yr_mr)
            avg_hold = np.mean([t["hold_days"] for t in yr_mr])
            print(f"    {bear_year} MR: {len(yr_mr)} trades, {wins} wins ({wins/len(yr_mr)*100:.0f}%), PnL: Rs {pnl:+,.0f}, Avg hold: {avg_hold:.0f}d")
        else:
            print(f"    {bear_year} MR: 0 trades")

    print("", flush=True)

print("Done!", flush=True)
