"""Mean Reversion parameter sweep — test each change independently.

Tests one change at a time vs baseline to find clear winners,
then tests combinations of winners.
"""

import logging
import sys
import time
from datetime import date

logging.basicConfig(level=logging.WARNING)

from vcp_screener.services.backtester import BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators

start = date(2016, 4, 1)
end = date(2026, 3, 1)

# Load data once
print("Loading stock data...", flush=True)
t0 = time.time()
all_data, breadth = load_backtest_data()
print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

# Precompute VCP screens
print("Precomputing VCP screens...", flush=True)
t0 = time.time()
screens = precompute_screens(all_data, start, end)
print(f"Done in {time.time()-t0:.0f}s.", flush=True)

# Precompute MR indicators (RSI, IBS, SMA200, Bollinger, volume)
print("Precomputing MR indicators...", flush=True)
t0 = time.time()
mr_ind = precompute_mr_indicators(all_data)
print(f"Done in {time.time()-t0:.0f}s.\n", flush=True)

# Baseline MR config (current defaults)
BASELINE = {
    "stop_pct": 5, "target": "sma20", "rsi_exit": 0, "timeout_days": 15,
    "max_positions": 3, "risk_pct": 1.5, "entry_std": 2.0,
    "require_rsi": False, "rsi_entry": 10, "require_ibs": False, "ibs_entry": 0.3,
    "require_uptrend": False, "all_regimes": False, "vol_lookback": 1,
}

# Individual changes to test (name, {param overrides})
TESTS = [
    # --- Stop Loss ---
    ("Baseline (5% stop)", {}),
    ("Stop 8%", {"stop_pct": 8}),
    ("Stop 10%", {"stop_pct": 10}),
    ("Stop 12%", {"stop_pct": 12}),
    ("Stop 15%", {"stop_pct": 15}),
    ("Stop 20%", {"stop_pct": 20}),

    # --- Exit Target ---
    ("Target SMA10", {"target": "sma10"}),
    ("Target SMA5", {"target": "sma5"}),
    ("RSI exit 50", {"rsi_exit": 50}),
    ("RSI exit 65", {"rsi_exit": 65}),
    ("RSI exit 80", {"rsi_exit": 80}),
    ("Target SMA10 + RSI65", {"target": "sma10", "rsi_exit": 65}),
    ("Target SMA5 + RSI50", {"target": "sma5", "rsi_exit": 50}),

    # --- Timeout ---
    ("Timeout 7d", {"timeout_days": 7}),
    ("Timeout 10d", {"timeout_days": 10}),
    ("Timeout 20d", {"timeout_days": 20}),
    ("Timeout 25d", {"timeout_days": 25}),

    # --- Entry Filters ---
    ("RSI(2)<10 filter", {"require_rsi": True, "rsi_entry": 10}),
    ("RSI(2)<5 filter", {"require_rsi": True, "rsi_entry": 5}),
    ("RSI(2)<15 filter", {"require_rsi": True, "rsi_entry": 15}),
    ("IBS<0.3 filter", {"require_ibs": True, "ibs_entry": 0.3}),
    ("IBS<0.2 filter", {"require_ibs": True, "ibs_entry": 0.2}),
    ("RSI<10 + IBS<0.3", {"require_rsi": True, "rsi_entry": 10, "require_ibs": True, "ibs_entry": 0.3}),
    ("Uptrend (>SMA200)", {"require_uptrend": True}),

    # --- Entry Std Dev ---
    ("Entry 1.5 StdDev", {"entry_std": 1.5}),
    ("Entry 2.5 StdDev", {"entry_std": 2.5}),
    ("Entry 3.0 StdDev", {"entry_std": 3.0}),

    # --- Volume Lookback ---
    ("Vol 3-day lookback", {"vol_lookback": 3}),
    ("Vol 5-day lookback", {"vol_lookback": 5}),

    # --- All Regimes ---
    ("MR all regimes", {"all_regimes": True}),
    ("MR all + uptrend", {"all_regimes": True, "require_uptrend": True}),
    ("MR all + RSI<10", {"all_regimes": True, "require_rsi": True, "rsi_entry": 10}),
    ("MR all + uptrend + RSI", {"all_regimes": True, "require_uptrend": True, "require_rsi": True, "rsi_entry": 10}),

    # --- Risk/Position Size ---
    ("Risk 1.0%", {"risk_pct": 1.0}),
    ("Risk 2.0%", {"risk_pct": 2.0}),
    ("Risk 2.5%", {"risk_pct": 2.5}),
    ("Max 2 MR pos", {"max_positions": 2}),
    ("Max 4 MR pos", {"max_positions": 4}),
    ("Max 5 MR pos", {"max_positions": 5}),
]

print(f"Total configs: {len(TESTS)}")
print()

header = f"{'#':>3} {'Config':<30} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>7} {'Trades':>7} {'MR$':>10}"
print(header)
print("-" * len(header))

results = []

for i, (name, overrides) in enumerate(TESTS, 1):
    mr_cfg = {**BASELINE, **overrides}
    try:
        engine = BacktestEngine(
            initial_capital=500000, max_positions=5,
            mr_config=mr_cfg,
        )
        r = engine.run(start, end, preloaded_data=all_data, preloaded_breadth=breadth,
                       precomputed_screens=screens, precomputed_mr_ind=mr_ind)
    except Exception as e:
        print(f"{i:>3} {name:<30} ERROR: {e}")
        import traceback; traceback.print_exc()
        continue

    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{i:>3} {name:<30} N/A")
        continue

    ret = r["total_return_pct"]
    maxdd = r.get("max_drawdown_pct", 0)
    sharpe = r.get("sharpe_ratio", 0)
    pf = r.get("profit_factor", 0)
    winr = r.get("win_rate_pct", 0)
    trades = r["total_trades"]

    # Calculate MR-specific PnL
    mr_pnl = sum(t["pnl"] for t in r["trades"] if t["exit_reason"].startswith("mr_"))
    mr_trades = sum(1 for t in r["trades"] if t["exit_reason"].startswith("mr_"))

    print(f"{i:>3} {name:<30} {ret:>7.1f}% {maxdd:>6.1f}% {sharpe:>7.2f} {pf:>6.2f} {winr:>6.1f}% {trades:>7} {mr_pnl:>+10,.0f}")
    sys.stdout.flush()

    results.append({
        "name": name, "return": ret, "maxdd": maxdd, "sharpe": sharpe,
        "pf": pf, "win_rate": winr, "trades": trades, "mr_pnl": mr_pnl,
        "mr_trades": mr_trades, "overrides": overrides,
    })

# Summary
baseline = results[0] if results else None
print("\n" + "=" * 80)
print("IMPROVEMENT vs BASELINE (sorted by Sharpe):")
print("=" * 80)
if baseline:
    for r in sorted(results[1:], key=lambda x: x["sharpe"], reverse=True)[:15]:
        d_ret = r["return"] - baseline["return"]
        d_dd = r["maxdd"] - baseline["maxdd"]
        d_sharpe = r["sharpe"] - baseline["sharpe"]
        d_mr = r["mr_pnl"] - baseline["mr_pnl"]
        print(f"  {r['name']:<30} Sharpe:{r['sharpe']:.2f}({d_sharpe:+.2f})  Ret:{r['return']:.0f}%({d_ret:+.0f}%)  DD:{r['maxdd']:.1f}%({d_dd:+.1f}%)  MR PnL:{d_mr:+,.0f}")

print("\nBEST MR PnL IMPROVEMENT:")
print("=" * 80)
if baseline:
    for r in sorted(results[1:], key=lambda x: x["mr_pnl"], reverse=True)[:10]:
        d_mr = r["mr_pnl"] - baseline["mr_pnl"]
        print(f"  {r['name']:<30} MR PnL:{r['mr_pnl']:>+12,.0f}  (vs baseline: {d_mr:+,.0f})  DD:{r['maxdd']:.1f}%")
