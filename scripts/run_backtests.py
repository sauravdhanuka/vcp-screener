"""Run comprehensive backtests across multiple market periods."""

import logging
import sys
from datetime import date

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs

from vcp_screener.services.backtester import run_backtest

periods = [
    ("2021 H1",               date(2021, 1, 1),  date(2021, 6, 30)),
    ("2021 H2 (Bull)",        date(2021, 7, 1),  date(2021, 12, 31)),
    ("2022 H1 (Bear)",        date(2022, 1, 1),  date(2022, 6, 30)),
    ("2022 H2 (Recovery)",    date(2022, 7, 1),  date(2022, 12, 31)),
    ("2023 H1",               date(2023, 1, 1),  date(2023, 6, 30)),
    ("2023 H2",               date(2023, 7, 1),  date(2023, 12, 31)),
    ("2024 H1 (Bull Run)",    date(2024, 1, 1),  date(2024, 6, 30)),
    ("2024 H2 (Correction)",  date(2024, 7, 1),  date(2024, 12, 31)),
    ("2025 H1",               date(2025, 1, 1),  date(2025, 6, 30)),
    ("2025 H2",               date(2025, 7, 1),  date(2025, 12, 31)),
    ("Full 2021",             date(2021, 1, 1),  date(2021, 12, 31)),
    ("Full 2022",             date(2022, 1, 1),  date(2022, 12, 31)),
    ("Full 2023",             date(2023, 1, 1),  date(2023, 12, 31)),
    ("Full 2024",             date(2024, 1, 1),  date(2024, 12, 31)),
    ("Full 2025",             date(2025, 1, 1),  date(2025, 12, 31)),
    ("Full 5Y (2021-2025)",   date(2021, 1, 1),  date(2025, 12, 31)),
]

header = f"{'Period':<25} {'Return':>8} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>7} {'Trades':>7} {'WinR':>7} {'PF':>7} {'AvgG':>7} {'AvgL':>7} {'HoldD':>7}"
print(header)
print("-" * len(header))

results_all = []

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

    results_all.append(r)

    print(
        f"{name:<25} {ret:>7.1f}% {cagr:>6.1f}% {sharpe:>7.2f} "
        f"{maxdd:>6.1f}% {trades:>7} {winr:>6.1f}% {pf:>6.2f} "
        f"{avg_g:>6.1f}% {avg_l:>6.1f}% {hold:>6.0f}d"
    )
    sys.stdout.flush()

print("-" * len(header))
if results_all:
    avg_ret = sum(r["total_return_pct"] for r in results_all) / len(results_all)
    avg_sharpe = sum(r.get("sharpe_ratio", 0) for r in results_all) / len(results_all)
    worst_dd = max(r.get("max_drawdown_pct", 0) for r in results_all)
    total_trades = sum(r["total_trades"] for r in results_all)
    total_wins = sum(int(r["total_trades"] * r.get("win_rate_pct", 0) / 100) for r in results_all)
    avg_winr = total_wins / total_trades * 100 if total_trades else 0
    print(f"{'AVERAGE (all periods)':<25} {avg_ret:>7.1f}%         {avg_sharpe:>7.2f} {worst_dd:>6.1f}% {total_trades:>7} {avg_winr:>6.1f}%")
