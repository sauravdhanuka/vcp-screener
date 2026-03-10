"""Mean Reversion COMBINATION sweep — test winners together.

Individual sweep winners:
1. Target SMA10 + RSI exit 65 (Sharpe 1.61, best overall)
2. Entry 1.5 StdDev (Sharpe 1.59, more MR trades)
3. Stop 12% (Sharpe 1.49, -7.3% DD)
4. Entry 2.5 StdDev (Sharpe 1.46, best PF 1.82)
5. RSI(2)<5 filter (best MR PnL +25.3L)
6. IBS<0.2 filter (MR PnL +17.4L, -3% DD)
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

# Precompute MR indicators
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

# Winner building blocks
EXIT_SMA10_RSI65 = {"target": "sma10", "rsi_exit": 65}
STOP_12 = {"stop_pct": 12}
ENTRY_1_5 = {"entry_std": 1.5}
ENTRY_2_5 = {"entry_std": 2.5}
RSI5_FILTER = {"require_rsi": True, "rsi_entry": 5}
IBS02_FILTER = {"require_ibs": True, "ibs_entry": 0.2}

# Combination tests
TESTS = [
    ("Baseline", {}),

    # --- 2-way combos ---
    ("SMA10+RSI65 + Stop12", {**EXIT_SMA10_RSI65, **STOP_12}),
    ("SMA10+RSI65 + Entry1.5", {**EXIT_SMA10_RSI65, **ENTRY_1_5}),
    ("SMA10+RSI65 + Entry2.5", {**EXIT_SMA10_RSI65, **ENTRY_2_5}),
    ("SMA10+RSI65 + RSI<5", {**EXIT_SMA10_RSI65, **RSI5_FILTER}),
    ("SMA10+RSI65 + IBS<0.2", {**EXIT_SMA10_RSI65, **IBS02_FILTER}),
    ("Stop12 + Entry1.5", {**STOP_12, **ENTRY_1_5}),
    ("Stop12 + Entry2.5", {**STOP_12, **ENTRY_2_5}),
    ("Stop12 + RSI<5", {**STOP_12, **RSI5_FILTER}),
    ("Stop12 + IBS<0.2", {**STOP_12, **IBS02_FILTER}),
    ("Entry1.5 + RSI<5", {**ENTRY_1_5, **RSI5_FILTER}),
    ("Entry1.5 + IBS<0.2", {**ENTRY_1_5, **IBS02_FILTER}),
    ("Entry2.5 + RSI<5", {**ENTRY_2_5, **RSI5_FILTER}),
    ("Entry2.5 + IBS<0.2", {**ENTRY_2_5, **IBS02_FILTER}),
    ("RSI<5 + IBS<0.2", {**RSI5_FILTER, **IBS02_FILTER}),

    # --- 3-way combos (top winners) ---
    ("SMA10+RSI65+Stop12+Ent1.5", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_1_5}),
    ("SMA10+RSI65+Stop12+Ent2.5", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_2_5}),
    ("SMA10+RSI65+Stop12+RSI<5", {**EXIT_SMA10_RSI65, **STOP_12, **RSI5_FILTER}),
    ("SMA10+RSI65+Stop12+IBS<.2", {**EXIT_SMA10_RSI65, **STOP_12, **IBS02_FILTER}),
    ("SMA10+RSI65+Ent1.5+RSI<5", {**EXIT_SMA10_RSI65, **ENTRY_1_5, **RSI5_FILTER}),
    ("SMA10+RSI65+Ent1.5+IBS<.2", {**EXIT_SMA10_RSI65, **ENTRY_1_5, **IBS02_FILTER}),
    ("SMA10+RSI65+Ent2.5+RSI<5", {**EXIT_SMA10_RSI65, **ENTRY_2_5, **RSI5_FILTER}),
    ("SMA10+RSI65+Ent2.5+IBS<.2", {**EXIT_SMA10_RSI65, **ENTRY_2_5, **IBS02_FILTER}),
    ("Stop12+Ent1.5+RSI<5", {**STOP_12, **ENTRY_1_5, **RSI5_FILTER}),
    ("Stop12+Ent2.5+RSI<5", {**STOP_12, **ENTRY_2_5, **RSI5_FILTER}),
    ("Stop12+Ent1.5+IBS<0.2", {**STOP_12, **ENTRY_1_5, **IBS02_FILTER}),
    ("Stop12+Ent2.5+IBS<0.2", {**STOP_12, **ENTRY_2_5, **IBS02_FILTER}),

    # --- 4-way combos ---
    ("Exit+Stop12+Ent1.5+RSI<5", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_1_5, **RSI5_FILTER}),
    ("Exit+Stop12+Ent2.5+RSI<5", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_2_5, **RSI5_FILTER}),
    ("Exit+Stop12+Ent1.5+IBS<.2", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_1_5, **IBS02_FILTER}),
    ("Exit+Stop12+Ent2.5+IBS<.2", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_2_5, **IBS02_FILTER}),
    ("Exit+Stop12+RSI<5+IBS<.2", {**EXIT_SMA10_RSI65, **STOP_12, **RSI5_FILTER, **IBS02_FILTER}),
    ("Exit+Ent1.5+RSI<5+IBS<.2", {**EXIT_SMA10_RSI65, **ENTRY_1_5, **RSI5_FILTER, **IBS02_FILTER}),

    # --- 5-way (kitchen sink) ---
    ("All winners (Ent1.5)", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_1_5, **RSI5_FILTER, **IBS02_FILTER}),
    ("All winners (Ent2.5)", {**EXIT_SMA10_RSI65, **STOP_12, **ENTRY_2_5, **RSI5_FILTER, **IBS02_FILTER}),
]

print(f"Total configs: {len(TESTS)}")
print()

header = f"{'#':>3} {'Config':<32} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>7} {'Trades':>7} {'MR$':>10}"
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
        print(f"{i:>3} {name:<32} ERROR: {e}")
        import traceback; traceback.print_exc()
        continue

    if "error" in r or r.get("total_trades", 0) == 0:
        print(f"{i:>3} {name:<32} N/A")
        continue

    ret = r["total_return_pct"]
    maxdd = r.get("max_drawdown_pct", 0)
    sharpe = r.get("sharpe_ratio", 0)
    pf = r.get("profit_factor", 0)
    winr = r.get("win_rate_pct", 0)
    trades = r["total_trades"]

    mr_pnl = sum(t["pnl"] for t in r["trades"] if t["exit_reason"].startswith("mr_"))
    mr_trades = sum(1 for t in r["trades"] if t["exit_reason"].startswith("mr_"))

    print(f"{i:>3} {name:<32} {ret:>7.1f}% {maxdd:>6.1f}% {sharpe:>7.2f} {pf:>6.2f} {winr:>6.1f}% {trades:>7} {mr_pnl:>+10,.0f}")
    sys.stdout.flush()

    results.append({
        "name": name, "return": ret, "maxdd": maxdd, "sharpe": sharpe,
        "pf": pf, "win_rate": winr, "trades": trades, "mr_pnl": mr_pnl,
        "mr_trades": mr_trades, "overrides": overrides,
    })

# Summary
baseline = results[0] if results else None
print("\n" + "=" * 90)
print("COMBINATIONS RANKED BY SHARPE:")
print("=" * 90)
if baseline:
    for r in sorted(results[1:], key=lambda x: x["sharpe"], reverse=True)[:20]:
        d_ret = r["return"] - baseline["return"]
        d_dd = r["maxdd"] - baseline["maxdd"]
        d_sharpe = r["sharpe"] - baseline["sharpe"]
        d_mr = r["mr_pnl"] - baseline["mr_pnl"]
        print(f"  {r['name']:<32} Sharpe:{r['sharpe']:.2f}({d_sharpe:+.2f})  Ret:{r['return']:.0f}%({d_ret:+.0f}%)  DD:{r['maxdd']:.1f}%({d_dd:+.1f}%)  MR:{d_mr:+,.0f}")

print("\nBEST RISK-ADJUSTED (Sharpe>1.5 AND DD<30%):")
print("=" * 90)
if baseline:
    good = [r for r in results[1:] if r["sharpe"] >= 1.5 and r["maxdd"] <= 30.0]
    for r in sorted(good, key=lambda x: x["sharpe"], reverse=True):
        d_mr = r["mr_pnl"] - baseline["mr_pnl"]
        print(f"  {r['name']:<32} Sharpe:{r['sharpe']:.2f}  Ret:{r['return']:.0f}%  DD:{r['maxdd']:.1f}%  PF:{r['pf']:.2f}  MR PnL:{r['mr_pnl']:+,.0f}({d_mr:+,.0f})")
