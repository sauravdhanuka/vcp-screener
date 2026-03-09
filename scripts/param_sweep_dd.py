"""Comprehensive parameter sweep for MaxDD reduction WITH compounding."""

import logging
import sys
from datetime import date

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import BacktestEngine

start = date(2021, 1, 1)
end = date(2025, 12, 31)

# Test configurations: (name, eq_ma_days, dd_max_pos, dd_risk_mult)
configs = [
    # Baseline
    ("Baseline (no EqMA)", 0, 5, 1.0),
    # EqMA lookback variants with max positions
    ("EqMA-10d max3", 10, 3, 1.0),
    ("EqMA-10d max4", 10, 4, 1.0),
    ("EqMA-15d max3", 15, 3, 1.0),
    ("EqMA-15d max4", 15, 4, 1.0),
    ("EqMA-20d max3", 20, 3, 1.0),
    ("EqMA-20d max4", 20, 4, 1.0),
    ("EqMA-30d max3", 30, 3, 1.0),
    ("EqMA-30d max4", 30, 4, 1.0),
    # Risk reduction only (keep max 5 positions)
    ("EqMA-10d risk50%", 10, 5, 0.5),
    ("EqMA-15d risk50%", 15, 5, 0.5),
    ("EqMA-15d risk75%", 15, 5, 0.75),
    ("EqMA-20d risk50%", 20, 5, 0.5),
    ("EqMA-20d risk75%", 20, 5, 0.75),
    # Combined: reduced positions AND risk
    ("EqMA-15d max4 risk75%", 15, 4, 0.75),
    ("EqMA-15d max4 risk50%", 15, 4, 0.5),
    ("EqMA-15d max3 risk75%", 15, 3, 0.75),
    ("EqMA-15d max3 risk50%", 15, 3, 0.5),
    ("EqMA-20d max4 risk75%", 20, 4, 0.75),
    ("EqMA-20d max3 risk75%", 20, 3, 0.75),
    ("EqMA-10d max4 risk75%", 10, 4, 0.75),
]

header = f"{'Config':<28} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>7} {'Trades':>7} {'AvgL':>7}"
print(header)
print("-" * len(header))

for name, eq_ma_days, max_pos_dd, risk_mult in configs:
    try:
        engine = BacktestEngine(
            initial_capital=500000,
            max_positions=5,
            eq_ma_days=eq_ma_days,
            dd_max_positions=max_pos_dd,
            dd_risk_mult=risk_mult,
        )
        r = engine.run(start, end)
    except Exception as e:
        print(f"{name:<28} ERROR: {e}")
        continue

    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{name:<28} N/A (no trades)")
        continue

    ret = r["total_return_pct"]
    maxdd = r.get("max_drawdown_pct", 0)
    sharpe = r.get("sharpe_ratio", 0)
    pf = r.get("profit_factor", 0)
    winr = r.get("win_rate_pct", 0)
    trades = r["total_trades"]
    avg_l = r.get("avg_loss_pct", 0)

    print(f"{name:<28} {ret:>7.1f}% {maxdd:>6.1f}% {sharpe:>7.2f} {pf:>6.2f} {winr:>6.1f}% {trades:>7} {avg_l:>6.1f}%")
    sys.stdout.flush()
