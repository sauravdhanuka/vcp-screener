"""Comprehensive backtest with runner-up MR config.

Config: SMA10 exit + RSI65 exit + Entry1.5 StdDev + RSI(2)<5 + IBS<0.2
Sweep result: 3150%, 24.8% DD, 1.61 Sharpe, 1.74 PF
"""

import logging
import sys
import time
from datetime import date

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators

MR_CONFIG = {
    "stop_pct": 5,           # Keep default stop
    "target": "sma10",       # Exit at SMA10 instead of SMA20
    "rsi_exit": 65,          # Also exit when RSI(2) > 65
    "timeout_days": 15,
    "max_positions": 3,
    "risk_pct": 1.5,
    "entry_std": 1.5,        # Entry at 1.5 StdDev (lower = more trades)
    "require_rsi": True,     # Require RSI(2) < 5
    "rsi_entry": 5,
    "require_ibs": True,     # Require IBS < 0.2
    "ibs_entry": 0.2,
    "require_uptrend": False,
    "all_regimes": False,
    "vol_lookback": 1,
}

# Load data once
print("Loading stock data...", flush=True)
t0 = time.time()
all_data, breadth = load_backtest_data()
print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

print("Precomputing MR indicators...", flush=True)
t0 = time.time()
mr_ind = precompute_mr_indicators(all_data)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

# ---- 7-year continuous backtest ----
start_7y = date(2019, 1, 1)
end_7y = date(2026, 3, 1)

print(f"\nPrecomputing VCP screens for {start_7y} to {end_7y}...", flush=True)
t0 = time.time()
screens = precompute_screens(all_data, start_7y, end_7y)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

print(f"\n{'='*70}")
print(f"7-YEAR BACKTEST (Runner-up): {start_7y} to {end_7y}")
print(f"MR Config: SMA10+RSI65 exit, Entry1.5std, RSI<5+IBS<0.2 filters")
print(f"{'='*70}", flush=True)

engine = BacktestEngine(initial_capital=500000, max_positions=5, mr_config=MR_CONFIG)
r = engine.run(start_7y, end_7y, preloaded_data=all_data, preloaded_breadth=breadth,
               precomputed_screens=screens, precomputed_mr_ind=mr_ind)

print(f"\nInitial: Rs {r['initial_capital']:>12,.0f}")
print(f"Final:   Rs {r['final_capital']:>12,.0f}")
print(f"Return:  {r['total_return_pct']:.1f}%")
print(f"CAGR:    {r['cagr_pct']:.1f}%")
print(f"MaxDD:   {r['max_drawdown_pct']:.1f}%")
print(f"Sharpe:  {r['sharpe_ratio']:.2f}")
print(f"PF:      {r['profit_factor']:.2f}")
print(f"Trades:  {r['total_trades']}")
print(f"Win Rate:{r['win_rate_pct']:.1f}%")
print(f"Avg Gain:{r['avg_gain_pct']:.1f}%")
print(f"Avg Loss:{r['avg_loss_pct']:.1f}%")
print(f"Avg Hold:{r['avg_hold_days']:.0f}d")

# Year-end equity
print("\nYear-end equity:", flush=True)
for eq in r["equity_curve"]:
    d = eq["date"]
    if d.month == 12 and d.day >= 28:
        print(f"  {d.strftime('%Y-%m-%d')}: Rs {eq['equity']:>15,.0f}  (DD: {eq['drawdown_pct']:.1f}%)")

# Exit reasons
print("\nEXIT REASONS:", flush=True)
exit_stats = {}
for t in r["trades"]:
    reason = t["exit_reason"]
    if reason not in exit_stats:
        exit_stats[reason] = {"count": 0, "pnl": 0}
    exit_stats[reason]["count"] += 1
    exit_stats[reason]["pnl"] += t["pnl"]

for reason, stats in sorted(exit_stats.items(), key=lambda x: -x[1]["count"]):
    print(f"  {reason:<25} {stats['count']:>4} trades  PnL: Rs {stats['pnl']:>15,.0f}")

mr_trades = [t for t in r["trades"] if t["exit_reason"].startswith("mr_")]
vcp_trades = [t for t in r["trades"] if not t["exit_reason"].startswith("mr_")]
print(f"\nMR trades: {len(mr_trades)}, PnL: Rs {sum(t['pnl'] for t in mr_trades):>+12,.0f}")
print(f"VCP trades: {len(vcp_trades)}, PnL: Rs {sum(t['pnl'] for t in vcp_trades):>+12,.0f}")
if mr_trades:
    mr_wins = sum(1 for t in mr_trades if t["pnl"] > 0)
    print(f"MR win rate: {mr_wins/len(mr_trades)*100:.1f}%")

# ---- 10-year continuous backtest ----
start_10y = date(2016, 4, 1)
end_10y = date(2026, 3, 1)

print(f"\n{'='*70}")
print(f"10-YEAR BACKTEST (Runner-up): {start_10y} to {end_10y}")
print(f"{'='*70}", flush=True)

print("Precomputing VCP screens for 10Y...", flush=True)
t0 = time.time()
screens_10y = precompute_screens(all_data, start_10y, end_10y)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

engine2 = BacktestEngine(initial_capital=500000, max_positions=5, mr_config=MR_CONFIG)
r2 = engine2.run(start_10y, end_10y, preloaded_data=all_data, preloaded_breadth=breadth,
                 precomputed_screens=screens_10y, precomputed_mr_ind=mr_ind)

print(f"\nInitial: Rs {r2['initial_capital']:>12,.0f}")
print(f"Final:   Rs {r2['final_capital']:>12,.0f}")
print(f"Return:  {r2['total_return_pct']:.1f}%")
print(f"CAGR:    {r2['cagr_pct']:.1f}%")
print(f"MaxDD:   {r2['max_drawdown_pct']:.1f}%")
print(f"Sharpe:  {r2['sharpe_ratio']:.2f}")
print(f"PF:      {r2['profit_factor']:.2f}")
print(f"Trades:  {r2['total_trades']}")
print(f"Win Rate:{r2['win_rate_pct']:.1f}%")

# Year-end equity for 10Y
print("\nYear-end equity:", flush=True)
for eq in r2["equity_curve"]:
    d = eq["date"]
    if d.month == 12 and d.day >= 28:
        print(f"  {d.strftime('%Y-%m-%d')}: Rs {eq['equity']:>15,.0f}  (DD: {eq['drawdown_pct']:.1f}%)")

# Exit reasons 10Y
print("\nEXIT REASONS:", flush=True)
exit_stats2 = {}
for t in r2["trades"]:
    reason = t["exit_reason"]
    if reason not in exit_stats2:
        exit_stats2[reason] = {"count": 0, "pnl": 0}
    exit_stats2[reason]["count"] += 1
    exit_stats2[reason]["pnl"] += t["pnl"]

for reason, stats in sorted(exit_stats2.items(), key=lambda x: -x[1]["count"]):
    print(f"  {reason:<25} {stats['count']:>4} trades  PnL: Rs {stats['pnl']:>15,.0f}")

mr2 = [t for t in r2["trades"] if t["exit_reason"].startswith("mr_")]
vcp2 = [t for t in r2["trades"] if not t["exit_reason"].startswith("mr_")]
print(f"\nMR trades: {len(mr2)}, PnL: Rs {sum(t['pnl'] for t in mr2):>+12,.0f}")
print(f"VCP trades: {len(vcp2)}, PnL: Rs {sum(t['pnl'] for t in vcp2):>+12,.0f}")

print("\nDone!", flush=True)
