"""Comprehensive parameter sweep for MaxDD reduction WITH compounding.

Tests every permutation of:
- eq_ma_days: 0 (disabled), 5, 10, 15, 20, 25, 30, 40, 50
- dd_max_positions: 2, 3, 4, 5
- dd_risk_mult: 0.25, 0.5, 0.75, 1.0

Loads data ONCE, precomputes screens ONCE, then replays across all configs.
"""

import logging
import sys
import time
from datetime import date
from itertools import product

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_candidates

start = date(2021, 1, 1)
end = date(2025, 12, 31)

# Load data once
print("Loading stock data...", flush=True)
t0 = time.time()
all_data, breadth = load_backtest_data()
print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

# Precompute screening results (the expensive VCP detection)
print("Precomputing VCP screens for all dates...", flush=True)
t0 = time.time()
screens = precompute_screens(all_data, start, end)
print(f"Precomputed {len(screens)} screen dates in {time.time()-t0:.0f}s.", flush=True)

print("Precomputing mean reversion candidates...", flush=True)
t0 = time.time()
mr_candidates = precompute_mr_candidates(all_data, start, end)
print(f"Precomputed MR candidates in {time.time()-t0:.0f}s.\n", flush=True)

# Parameter ranges
eq_ma_days_range = [0, 5, 10, 15, 20, 25, 30, 40, 50]
dd_max_pos_range = [2, 3, 4, 5]
dd_risk_mult_range = [0.25, 0.5, 0.75, 1.0]

# Build configs
configs = []

# Baseline first
configs.append(("Baseline (no EqMA)", 0, 5, 1.0))

# All permutations where EqMA is active
for eq_ma, max_pos, risk_mult in product(eq_ma_days_range[1:], dd_max_pos_range, dd_risk_mult_range):
    name = f"EqMA-{eq_ma}d max{max_pos} risk{int(risk_mult*100)}%"
    configs.append((name, eq_ma, max_pos, risk_mult))

print(f"Total configs to test: {len(configs)}")
print()

header = f"{'#':>3} {'Config':<30} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>7} {'Trades':>7} {'AvgL':>7}"
print(header)
print("-" * len(header))

results = []

for i, (name, eq_ma_days, max_pos_dd, risk_mult) in enumerate(configs, 1):
    try:
        engine = BacktestEngine(
            initial_capital=500000,
            max_positions=5,
            eq_ma_days=eq_ma_days,
            dd_max_positions=max_pos_dd,
            dd_risk_mult=risk_mult,
        )
        r = engine.run(start, end, preloaded_data=all_data, preloaded_breadth=breadth,
                       precomputed_screens=screens, precomputed_mr=mr_candidates)
    except Exception as e:
        print(f"{i:>3} {name:<30} ERROR: {e}")
        import traceback; traceback.print_exc()
        continue

    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{i:>3} {name:<30} N/A (no trades)")
        continue

    ret = r["total_return_pct"]
    maxdd = r.get("max_drawdown_pct", 0)
    sharpe = r.get("sharpe_ratio", 0)
    pf = r.get("profit_factor", 0)
    winr = r.get("win_rate_pct", 0)
    trades = r["total_trades"]
    avg_l = r.get("avg_loss_pct", 0)

    print(f"{i:>3} {name:<30} {ret:>7.1f}% {maxdd:>6.1f}% {sharpe:>7.2f} {pf:>6.2f} {winr:>6.1f}% {trades:>7} {avg_l:>6.1f}%")
    sys.stdout.flush()

    results.append({
        "name": name, "eq_ma_days": eq_ma_days, "dd_max_pos": max_pos_dd,
        "dd_risk_mult": risk_mult, "return": ret, "maxdd": maxdd,
        "sharpe": sharpe, "pf": pf, "win_rate": winr, "trades": trades,
        "avg_loss": avg_l,
    })

# Summary
print("\n" + "=" * 80)
print("TOP 10 BY SHARPE RATIO:")
print("=" * 80)
for r in sorted(results, key=lambda x: x["sharpe"], reverse=True)[:10]:
    print(f"  {r['name']:<30} Sharpe={r['sharpe']:.2f}  Return={r['return']:.1f}%  MaxDD={r['maxdd']:.1f}%")

print("\nTOP 10 BY RETURN:")
print("=" * 80)
for r in sorted(results, key=lambda x: x["return"], reverse=True)[:10]:
    print(f"  {r['name']:<30} Return={r['return']:.1f}%  MaxDD={r['maxdd']:.1f}%  Sharpe={r['sharpe']:.2f}")

print("\nTOP 10 BY LOWEST MAX DRAWDOWN:")
print("=" * 80)
for r in sorted(results, key=lambda x: x["maxdd"])[:10]:
    print(f"  {r['name']:<30} MaxDD={r['maxdd']:.1f}%  Return={r['return']:.1f}%  Sharpe={r['sharpe']:.2f}")

print("\nBEST RETURN/DD RATIO (return > 500%):")
print("=" * 80)
high_ret = [r for r in results if r["return"] > 500]
for r in sorted(high_ret, key=lambda x: x["return"] / max(x["maxdd"], 1), reverse=True)[:10]:
    ratio = r["return"] / max(r["maxdd"], 1)
    print(f"  {r['name']:<30} Ret/DD={ratio:.1f}  Return={r['return']:.1f}%  MaxDD={r['maxdd']:.1f}%")
