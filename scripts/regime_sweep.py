"""Regime detection sweep — test different regime methods × MR configs × time periods.

Tests:
- 3 MR configs: Winner, Runner-up, Middle ground
- 8 regime detection methods
- 3 time periods: 10Y, 5Y-A (2016-2021), 5Y-B (2021-2026)
- Year-by-year breakdown for 10Y runs

Total: ~72 configs (8 regimes × 3 MR × 3 periods)
"""

import logging
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import (
    BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators,
)

# ─── MR Configs ────────────────────────────────────────────────
MR_WINNER = {
    "stop_pct": 12, "require_rsi": True, "rsi_entry": 5,
}
MR_RUNNERUP = {
    "stop_pct": 5, "target": "sma10", "rsi_exit": 65, "entry_std": 1.5,
    "require_rsi": True, "rsi_entry": 5, "require_ibs": True, "ibs_entry": 0.2,
}
MR_MIDDLE = {
    "stop_pct": 12, "require_rsi": True, "rsi_entry": 5, "rsi_exit": 65,
}

MR_CONFIGS = [
    ("Winner", MR_WINNER),
    ("RunnerUp", MR_RUNNERUP),
    ("Middle", MR_MIDDLE),
]

# ─── Regime Configs ────────────────────────────────────────────
REGIME_CONFIGS = [
    ("Breadth<35 (baseline)", {"method": "breadth", "bear_threshold": 35, "bull_threshold": 55}),
    ("Breadth<40 (looser)", {"method": "breadth", "bear_threshold": 40, "bull_threshold": 55}),
    ("Breadth<45 (very loose)", {"method": "breadth", "bear_threshold": 45, "bull_threshold": 55}),
    ("Breadth<30 (stricter)", {"method": "breadth", "bear_threshold": 30, "bull_threshold": 55}),
    ("BreadthCross<40", {"method": "breadth_cross", "bear_threshold": 40, "bull_threshold": 55}),
    ("BreadthROC -15", {"method": "breadth_roc", "bear_threshold": 35, "bull_threshold": 55, "roc_threshold": -15}),
    ("Nifty<200MA", {"method": "nifty_ma", "nifty_ma_period": 200}),
    ("Nifty|Breadth<35", {"method": "nifty_or_breadth", "bear_threshold": 35, "bull_threshold": 55, "nifty_ma_period": 200}),
]

# ─── Time Periods ──────────────────────────────────────────────
PERIODS = [
    ("10Y", date(2016, 4, 1), date(2026, 3, 1)),
    ("5Y-A", date(2016, 4, 1), date(2021, 3, 1)),
    ("5Y-B", date(2021, 3, 1), date(2026, 3, 1)),
]

# ─── Load Data ─────────────────────────────────────────────────
print("Loading stock data...", flush=True)
t0 = time.time()
all_data, breadth = load_backtest_data()
print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

# Download Nifty data for Nifty-based regime methods
print("Downloading Nifty 50 data...", flush=True)
nifty_raw = yf.download("^NSEI", start="2015-01-01", end="2026-03-10", progress=False, auto_adjust=False)
if not nifty_raw.empty:
    nifty_close = nifty_raw["Close"].squeeze()
    nifty_df = pd.DataFrame(index=nifty_close.index)
    nifty_df["close"] = nifty_close.values
    # Precompute SMAs for different periods
    for period in [50, 200]:
        nifty_df[f"sma_{period}"] = nifty_df["close"].rolling(period, min_periods=period).mean()
    nifty_df["sma"] = nifty_df["sma_200"]  # default
    print(f"Nifty data: {len(nifty_df)} rows.", flush=True)
else:
    nifty_df = None
    print("WARNING: No Nifty data available!", flush=True)

# Precompute MR indicators (shared across all configs)
print("Precomputing MR indicators...", flush=True)
t0 = time.time()
mr_ind = precompute_mr_indicators(all_data)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

# Precompute VCP screens for each period
screens_cache = {}
for pname, pstart, pend in PERIODS:
    print(f"Precomputing VCP screens for {pname} ({pstart} to {pend})...", flush=True)
    t0 = time.time()
    screens_cache[pname] = precompute_screens(all_data, pstart, pend)
    print(f"Done in {time.time()-t0:.0f}s.", flush=True)


def year_breakdown(result: dict) -> list[dict]:
    """Compute per-year metrics from a backtest result."""
    ec = result["equity_curve"]
    trades = result["trades"]
    if not ec:
        return []

    years = {}
    for e in ec:
        y = e["date"].year
        if y not in years:
            years[y] = {"entries": [], "peak": 0}
        years[y]["entries"].append(e)

    breakdown = []
    for y in sorted(years.keys()):
        entries = years[y]["entries"]
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

        # Year's trades
        yr_trades = [t for t in trades if t["entry_date"].year == y]
        yr_mr = [t for t in yr_trades if t["exit_reason"].startswith("mr_")]
        yr_vcp = [t for t in yr_trades if not t["exit_reason"].startswith("mr_")]
        mr_pnl = sum(t["pnl"] for t in yr_mr)
        vcp_pnl = sum(t["pnl"] for t in yr_vcp)

        # Sharpe for year
        eq_vals = [e["equity"] for e in entries]
        if len(eq_vals) >= 2:
            daily_ret = pd.Series(eq_vals).pct_change().dropna()
            sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
        else:
            sharpe = 0

        breakdown.append({
            "year": y, "return_pct": ret_pct, "max_dd": max_dd,
            "sharpe": sharpe, "trades": len(yr_trades),
            "mr_trades": len(yr_mr), "vcp_trades": len(yr_vcp),
            "mr_pnl": mr_pnl, "vcp_pnl": vcp_pnl,
            "start_eq": start_eq, "end_eq": end_eq,
        })
    return breakdown


# ─── Run Sweep ─────────────────────────────────────────────────
print(f"\n{'='*120}")
print(f"REGIME DETECTION SWEEP: {len(REGIME_CONFIGS)} regimes × {len(MR_CONFIGS)} MR × {len(PERIODS)} periods = {len(REGIME_CONFIGS)*len(MR_CONFIGS)*len(PERIODS)} configs")
print(f"{'='*120}\n", flush=True)

header = f"{'#':>3} {'Period':<5} {'MR Config':<10} {'Regime':<22} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>6} {'Trd':>5} {'MR PnL':>12} {'VCP PnL':>12}"
print(header)
print("-" * len(header))

all_results = []
config_num = 0

for pname, pstart, pend in PERIODS:
    screens = screens_cache[pname]

    for mr_name, mr_cfg in MR_CONFIGS:
        for reg_name, reg_cfg in REGIME_CONFIGS:
            config_num += 1

            # Set nifty SMA period if needed
            nifty_for_run = None
            if nifty_df is not None and reg_cfg.get("method", "").startswith("nifty"):
                nifty_for_run = nifty_df.copy()
                ma_period = reg_cfg.get("nifty_ma_period", 200)
                nifty_for_run["sma"] = nifty_for_run["close"].rolling(ma_period, min_periods=ma_period).mean()

            try:
                engine = BacktestEngine(
                    initial_capital=500000, max_positions=5,
                    mr_config=mr_cfg, regime_config=reg_cfg,
                )
                r = engine.run(
                    pstart, pend,
                    preloaded_data=all_data, preloaded_breadth=breadth,
                    precomputed_screens=screens, precomputed_mr_ind=mr_ind,
                    nifty_data=nifty_for_run,
                )
            except Exception as e:
                print(f"{config_num:>3} {pname:<5} {mr_name:<10} {reg_name:<22} ERROR: {e}")
                import traceback; traceback.print_exc()
                continue

            if "error" in r or r.get("total_trades", 0) == 0:
                print(f"{config_num:>3} {pname:<5} {mr_name:<10} {reg_name:<22} N/A")
                continue

            ret = r["total_return_pct"]
            maxdd = r.get("max_drawdown_pct", 0)
            sharpe = r.get("sharpe_ratio", 0)
            pf = r.get("profit_factor", 0)
            winr = r.get("win_rate_pct", 0)
            trades = r["total_trades"]
            mr_pnl = sum(t["pnl"] for t in r["trades"] if t["exit_reason"].startswith("mr_"))
            vcp_pnl = sum(t["pnl"] for t in r["trades"] if not t["exit_reason"].startswith("mr_"))

            print(f"{config_num:>3} {pname:<5} {mr_name:<10} {reg_name:<22} {ret:>7.1f}% {maxdd:>6.1f}% {sharpe:>7.2f} {pf:>6.2f} {winr:>5.1f}% {trades:>5} {mr_pnl:>+12,.0f} {vcp_pnl:>+12,.0f}")
            sys.stdout.flush()

            result_entry = {
                "period": pname, "mr_name": mr_name, "regime": reg_name,
                "return": ret, "maxdd": maxdd, "sharpe": sharpe,
                "pf": pf, "win_rate": winr, "trades": trades,
                "mr_pnl": mr_pnl, "vcp_pnl": vcp_pnl,
            }
            all_results.append(result_entry)

            # Year-by-year breakdown for 10Y runs
            if pname == "10Y":
                yb = year_breakdown(r)
                result_entry["year_breakdown"] = yb

# ─── Summary Tables ────────────────────────────────────────────
print(f"\n{'='*120}")
print("BEST CONFIGS BY PERIOD (sorted by Sharpe):")
print(f"{'='*120}")

for pname, _, _ in PERIODS:
    period_results = [r for r in all_results if r["period"] == pname]
    if not period_results:
        continue
    print(f"\n--- {pname} ---")
    for r in sorted(period_results, key=lambda x: x["sharpe"], reverse=True)[:10]:
        print(f"  {r['mr_name']:<10} {r['regime']:<22} Sharpe:{r['sharpe']:.2f}  Ret:{r['return']:.0f}%  DD:{r['maxdd']:.1f}%  PF:{r['pf']:.2f}  MR:{r['mr_pnl']:+,.0f}")

# Best risk-adjusted across all
print(f"\n{'='*120}")
print("BEST RISK-ADJUSTED (Sharpe>1.4 AND DD<30%) across all periods:")
print(f"{'='*120}")
good = [r for r in all_results if r["sharpe"] >= 1.4 and r["maxdd"] <= 30.0]
for r in sorted(good, key=lambda x: x["sharpe"], reverse=True)[:20]:
    print(f"  {r['period']:<5} {r['mr_name']:<10} {r['regime']:<22} Sharpe:{r['sharpe']:.2f}  Ret:{r['return']:.0f}%  DD:{r['maxdd']:.1f}%  PF:{r['pf']:.2f}")

# Year-by-year for top 10Y configs
print(f"\n{'='*120}")
print("YEAR-BY-YEAR BREAKDOWN (top 5 configs by 10Y Sharpe):")
print(f"{'='*120}")
ten_y = [r for r in all_results if r["period"] == "10Y" and "year_breakdown" in r]
for r in sorted(ten_y, key=lambda x: x["sharpe"], reverse=True)[:5]:
    print(f"\n  {r['mr_name']} + {r['regime']} — 10Y Sharpe:{r['sharpe']:.2f} Ret:{r['return']:.0f}% DD:{r['maxdd']:.1f}%")
    print(f"  {'Year':<6} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'Trades':>6} {'MR':>4} {'VCP':>4} {'MR PnL':>12} {'VCP PnL':>12} {'End Equity':>14}")
    for yb in r["year_breakdown"]:
        print(f"  {yb['year']:<6} {yb['return_pct']:>7.1f}% {yb['max_dd']:>6.1f}% {yb['sharpe']:>7.2f} {yb['trades']:>6} {yb['mr_trades']:>4} {yb['vcp_trades']:>4} {yb['mr_pnl']:>+12,.0f} {yb['vcp_pnl']:>+12,.0f} {yb['end_eq']:>14,.0f}")

print("\nDone!", flush=True)
