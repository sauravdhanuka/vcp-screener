"""Quick backtest: only Full 3Y for fast iteration."""

import logging
import sys
from datetime import date

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import run_backtest

periods = [
    ("Full 5Y (2021-2025)", date(2021, 1, 1), date(2025, 12, 31)),
]

header = f"{'Period':<25} {'Return':>8} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'Trades':>7} {'WinR':>7} {'PF':>7} {'AvgG':>7} {'AvgL':>7} {'HoldD':>7}"
print(header)
print("-" * len(header))

for name, start, end in periods:
    try:
        r = run_backtest(start, end, initial_capital=500000, max_positions=5, save=False)
    except Exception as e:
        print(f"{name:<25} ERROR: {e}")
        continue

    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{name:<25} {'N/A':>8}  (no trades)")
        continue

    ret = r["total_return_pct"]
    cagr = r.get("cagr_pct", 0)
    sharpe = r.get("sharpe_ratio", 0)
    maxdd = r.get("max_drawdown_pct", 0)
    trades = r["total_trades"]
    winr = r.get("win_rate_pct", 0)
    pf = r.get("profit_factor", 0)
    avg_g = r.get("avg_gain_pct", 0)
    avg_l = r.get("avg_loss_pct", 0)
    hold = r.get("avg_hold_days", 0)

    print(
        f"{name:<25} {ret:>7.1f}% {cagr:>6.1f}% {sharpe:>7.2f} "
        f"{maxdd:>6.1f}% {trades:>7} {winr:>6.1f}% {pf:>6.2f} "
        f"{avg_g:>6.1f}% {avg_l:>6.1f}% {hold:>6.0f}d"
    )
    sys.stdout.flush()
