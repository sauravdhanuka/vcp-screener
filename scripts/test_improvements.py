"""Test each improvement individually on top of compounding baseline.

Applies each change, runs 3Y backtest, reports results.
Changes that improve win rate AND reduce avg loss are kept.
"""

import logging
import sys
from datetime import date

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import run_backtest

def run_3y():
    r = run_backtest(date(2023, 1, 1), date(2025, 12, 31),
                     initial_capital=500000, max_positions=5, save=False)
    return r

def print_result(name, r):
    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{name:<40} N/A (no trades)")
        return
    print(
        f"{name:<40} {r['total_return_pct']:>7.1f}% "
        f"{r.get('cagr_pct',0):>6.1f}% {r.get('sharpe_ratio',0):>7.2f} "
        f"{r.get('max_drawdown_pct',0):>6.1f}% {r['total_trades']:>5} "
        f"{r.get('win_rate_pct',0):>6.1f}% {r.get('profit_factor',0):>6.2f} "
        f"{r.get('avg_gain_pct',0):>6.1f}% {r.get('avg_loss_pct',0):>6.1f}%"
    )
    sys.stdout.flush()

header = f"{'Change':<40} {'Return':>8} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'Trd':>5} {'WinR':>7} {'PF':>7} {'AvgG':>7} {'AvgL':>7}"
print(header)
print("-" * len(header))

# Baseline: compounding only
r = run_3y()
print_result("0. BASELINE (compounding only)", r)
