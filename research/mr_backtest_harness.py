"""MR Strategy Parameter Sweep — CLI-driven harness.

Usage:
    python research/mr_backtest_harness.py --precompute        # Cache data to pickle
    python research/mr_backtest_harness.py --baseline          # Validate baseline
    python research/mr_backtest_harness.py --gap 1             # Gap 1: stop loss
    python research/mr_backtest_harness.py --gap 2             # Gap 2: ADX filter
    python research/mr_backtest_harness.py --gap 3             # Gap 3: cumulative RSI
    python research/mr_backtest_harness.py --gap 4             # Gap 4: RSI exit
    python research/mr_backtest_harness.py --gap 5             # Gap 5: trend filter
    python research/mr_backtest_harness.py --combo-batch 1     # Combos 1-8
    python research/mr_backtest_harness.py --combo-batch 2     # Combos 9-16
    python research/mr_backtest_harness.py --combo-batch 3     # Combos 17-24
    python research/mr_backtest_harness.py --combo-batch 4     # Combos 25-32
    python research/mr_backtest_harness.py --analyze           # Merge results, rank, report
"""

import argparse
import json
import logging
import os
import pickle
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING)

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from vcp_screener.services.backtester import (
    BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators,
)

# ---------- Constants ----------

CACHE_DIR = Path(__file__).resolve().parent / "cache"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
PICKLE_PATH = CACHE_DIR / "precomputed.pkl"

START = date(2016, 4, 1)
END = date(2026, 3, 1)

BASELINE = {
    "stop_pct": 5, "target": "sma10", "rsi_exit": 65, "timeout_days": 15,
    "max_positions": 3, "risk_pct": 1.5, "entry_std": 1.5,
    "require_rsi": True, "rsi_entry": 5, "require_ibs": True, "ibs_entry": 0.2,
    "require_uptrend": False, "all_regimes": False, "vol_lookback": 1,
    "require_adx": False, "adx_max": 30, "rsi_mode": "single", "trend_filter": "none",
}

# ---------- Gap definitions ----------

GAP1_STOP = [
    ("stop_5_base", {}),
    ("stop_10", {"stop_pct": 10}),
    ("stop_15", {"stop_pct": 15}),
    ("stop_20", {"stop_pct": 20}),
    ("stop_25", {"stop_pct": 25}),
    ("stop_30", {"stop_pct": 30}),
    ("stop_50", {"stop_pct": 50}),
    ("no_stop", {"stop_pct": None}),
    ("no_stop_timeout8", {"stop_pct": None, "timeout_days": 8}),
    ("no_stop_timeout10", {"stop_pct": None, "timeout_days": 10}),
    ("no_stop_timeout12", {"stop_pct": None, "timeout_days": 12}),
    ("no_stop_timeout15", {"stop_pct": None, "timeout_days": 15}),
]

GAP2_ADX = [
    ("no_adx_base", {}),
    ("adx_lt20", {"require_adx": True, "adx_max": 20}),
    ("adx_lt25", {"require_adx": True, "adx_max": 25}),
    ("adx_lt30", {"require_adx": True, "adx_max": 30}),
    ("adx_lt35", {"require_adx": True, "adx_max": 35}),
]

GAP3_CUMRSI = [
    ("rsi_single5_base", {}),
    ("rsi_cum2_10", {"rsi_mode": "cum2", "rsi_entry": 10}),
    ("rsi_cum3_15", {"rsi_mode": "cum3", "rsi_entry": 15}),
]

GAP4_RSI_EXIT = [
    ("rsi_exit_0", {"rsi_exit": 0}),
    ("rsi_exit_60", {"rsi_exit": 60}),
    ("rsi_exit_65_base", {}),
    ("rsi_exit_70", {"rsi_exit": 70}),
    ("rsi_exit_75", {"rsi_exit": 75}),
    ("rsi_exit_80", {"rsi_exit": 80}),
]

GAP5_TREND = [
    ("trend_none_base", {}),
    ("trend_sma200", {"trend_filter": "sma200"}),
    ("trend_sma50", {"trend_filter": "sma50"}),
    ("trend_sma50_slope", {"trend_filter": "sma50_slope"}),
]

GAPS = {1: GAP1_STOP, 2: GAP2_ADX, 3: GAP3_CUMRSI, 4: GAP4_RSI_EXIT, 5: GAP5_TREND}
GAP_NAMES = {1: "stop", 2: "adx", 3: "cumrsi", 4: "rsi_exit", 5: "trend"}

# ---------- Helpers ----------

def load_pickle():
    """Load precomputed data from pickle cache."""
    if not PICKLE_PATH.exists():
        print(f"ERROR: Pickle not found at {PICKLE_PATH}. Run --precompute first.", file=sys.stderr)
        sys.exit(1)
    print(f"Loading pickle from {PICKLE_PATH}...", flush=True)
    t0 = time.time()
    with open(PICKLE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"Loaded in {time.time()-t0:.1f}s ({len(data['all_data'])} symbols)", flush=True)
    return data


def run_single(mr_overrides, all_data, breadth, screens, mr_ind):
    """Run one backtest with given MR overrides. Returns result dict."""
    mr_cfg = {**BASELINE, **mr_overrides}
    engine = BacktestEngine(
        initial_capital=500000, max_positions=5, mr_config=mr_cfg,
    )
    r = engine.run(START, END, preloaded_data=all_data, preloaded_breadth=breadth,
                   precomputed_screens=screens, precomputed_mr_ind=mr_ind)
    return r


def extract_metrics(r):
    """Extract key metrics from backtest result."""
    if "error" in r or r.get("total_trades", 0) == 0:
        return None
    trades = r.get("trades", [])
    mr_trades = [t for t in trades if t["exit_reason"].startswith("mr_")]
    mr_pnl = sum(t["pnl"] for t in mr_trades)
    mr_wins = sum(1 for t in mr_trades if t["pnl"] > 0)
    return {
        "total_return_pct": r["total_return_pct"],
        "cagr_pct": r.get("cagr_pct", 0),
        "max_drawdown_pct": r.get("max_drawdown_pct", 0),
        "sharpe_ratio": r.get("sharpe_ratio", 0),
        "profit_factor": r.get("profit_factor", 0),
        "win_rate_pct": r.get("win_rate_pct", 0),
        "total_trades": r["total_trades"],
        "mr_trades": len(mr_trades),
        "mr_wins": mr_wins,
        "mr_pnl": mr_pnl,
    }


def year_breakdown(r):
    """Compute per-year breakdown from backtest result."""
    ec = r.get("equity_curve", [])
    trades = r.get("trades", [])
    if not ec:
        return []

    years = {}
    for e in ec:
        y = e["date"].year
        if y not in years:
            years[y] = []
        years[y].append(e)

    breakdown = []
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

        # Year's trades
        yr_trades = [t for t in trades if t["entry_date"].year == y]
        yr_mr = [t for t in yr_trades if t["exit_reason"].startswith("mr_")]
        yr_mr_wins = [t for t in yr_mr if t["pnl"] > 0]
        mr_pnl = sum(t["pnl"] for t in yr_mr)

        breakdown.append({
            "year": y,
            "return_pct": round(ret_pct, 2),
            "max_dd_pct": round(max_dd, 2),
            "sharpe": round(sharpe, 2),
            "total_trades": len(yr_trades),
            "mr_trades": len(yr_mr),
            "mr_wins": len(yr_mr_wins),
            "mr_pnl": round(mr_pnl, 2),
        })
    return breakdown


def sanity_check(name, metrics):
    """Flag suspicious results."""
    if metrics is None:
        return
    if metrics["total_return_pct"] > 10000:
        print(f"  WARNING: {name} return {metrics['total_return_pct']:.0f}% > 10000% — possible bug!", flush=True)
    if metrics["max_drawdown_pct"] == 0 and metrics["total_trades"] > 10:
        print(f"  WARNING: {name} has 0% drawdown with {metrics['total_trades']} trades — suspicious!", flush=True)
    if metrics["sharpe_ratio"] < 0 and metrics["total_return_pct"] > 0:
        print(f"  WARNING: {name} negative Sharpe with positive return — check data!", flush=True)


def save_json(data, path):
    """Save data to JSON, handling non-serializable types."""
    def default(obj):
        if isinstance(obj, (date, pd.Timestamp)):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        return str(obj)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=default)
    print(f"Saved: {path}", flush=True)


def print_row(i, name, m):
    """Print a formatted result row."""
    if m is None:
        print(f"{i:>3} {name:<30} N/A")
        return
    print(f"{i:>3} {name:<30} {m['total_return_pct']:>7.1f}% {m['max_drawdown_pct']:>6.1f}% "
          f"{m['sharpe_ratio']:>7.2f} {m['profit_factor']:>6.2f} {m['win_rate_pct']:>6.1f}% "
          f"{m['total_trades']:>5} {m['mr_trades']:>4} {m['mr_pnl']:>+10,.0f}")


# ---------- Commands ----------

def cmd_precompute():
    """Load data from DB, precompute everything, save to pickle."""
    print("=" * 60)
    print("PRECOMPUTE: Loading data from DB...")
    print("=" * 60)

    t0 = time.time()
    all_data, breadth = load_backtest_data()
    print(f"Loaded {len(all_data)} stocks in {time.time()-t0:.0f}s.", flush=True)

    print("Precomputing VCP screens...", flush=True)
    t1 = time.time()
    screens = precompute_screens(all_data, START, END)
    print(f"Done in {time.time()-t1:.0f}s.", flush=True)

    print("Precomputing MR indicators (with ADX, cumRSI, SMA50)...", flush=True)
    t2 = time.time()
    mr_ind = precompute_mr_indicators(all_data)
    print(f"Done in {time.time()-t2:.0f}s.", flush=True)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "all_data": all_data,
        "breadth": breadth,
        "screens": screens,
        "mr_ind": mr_ind,
        "start": START,
        "end": END,
    }
    print(f"Saving pickle to {PICKLE_PATH}...", flush=True)
    t3 = time.time()
    with open(PICKLE_PATH, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = PICKLE_PATH.stat().st_size / (1024 * 1024)
    print(f"Saved {size_mb:.0f} MB in {time.time()-t3:.1f}s.", flush=True)
    print(f"Total precompute time: {time.time()-t0:.0f}s", flush=True)


def cmd_baseline():
    """Run baseline config and validate expected results."""
    data = load_pickle()
    print("\n" + "=" * 60)
    print("BASELINE VALIDATION")
    print("=" * 60)

    r = run_single({}, data["all_data"], data["breadth"], data["screens"], data["mr_ind"])
    m = extract_metrics(r)
    if m is None:
        print("ERROR: Baseline returned no results!", file=sys.stderr)
        sys.exit(1)

    yb = year_breakdown(r)

    print(f"\nReturn: {m['total_return_pct']:.1f}%  (expected ~3150%)")
    print(f"MaxDD:  {m['max_drawdown_pct']:.1f}%  (expected ~24.8%)")
    print(f"Sharpe: {m['sharpe_ratio']:.2f}  (expected ~1.61)")
    print(f"PF:     {m['profit_factor']:.2f}")
    print(f"Trades: {m['total_trades']}  MR: {m['mr_trades']}  MR PnL: {m['mr_pnl']:+,.0f}")

    print(f"\nYear-by-year:")
    print(f"  {'Year':<6} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'Trd':>5} {'MR':>4} {'MR W':>5} {'MR PnL':>12}")
    for yy in yb:
        print(f"  {yy['year']:<6} {yy['return_pct']:>7.1f}% {yy['max_dd_pct']:>6.1f}% {yy['sharpe']:>7.2f} "
              f"{yy['total_trades']:>5} {yy['mr_trades']:>4} {yy['mr_wins']:>5} {yy['mr_pnl']:>+12,.0f}")

    # Sanity checks
    ok = True
    if not (2800 <= m["total_return_pct"] <= 3500):
        print(f"\nWARNING: Return {m['total_return_pct']:.1f}% outside expected range 2800-3500%")
        ok = False
    if not (1.3 <= m["sharpe_ratio"] <= 1.9):
        print(f"WARNING: Sharpe {m['sharpe_ratio']:.2f} outside expected range 1.3-1.9")
        ok = False
    if not (15 <= m["max_drawdown_pct"] <= 35):
        print(f"WARNING: MaxDD {m['max_drawdown_pct']:.1f}% outside expected range 15-35%")
        ok = False

    if ok:
        print("\nBASELINE VALIDATED OK")
    else:
        print("\nBASELINE VALIDATION WARNINGS — review before proceeding")

    result = {"name": "baseline", "config": BASELINE, "metrics": m, "year_breakdown": yb}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save_json(result, RESULTS_DIR / "baseline.json")


def cmd_gap(gap_num):
    """Run all variants for a single gap."""
    if gap_num not in GAPS:
        print(f"ERROR: Invalid gap number {gap_num}. Must be 1-5.", file=sys.stderr)
        sys.exit(1)

    gap_name = GAP_NAMES[gap_num]
    variants = GAPS[gap_num]
    data = load_pickle()

    print(f"\n{'='*80}")
    print(f"GAP {gap_num}: {gap_name.upper()} ({len(variants)} variants)")
    print(f"{'='*80}")

    header = f"{'#':>3} {'Name':<30} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'WinR':>7} {'Trd':>5} {'MR':>4} {'MR PnL':>10}"
    print(header)
    print("-" * len(header))

    results = []
    for i, (name, overrides) in enumerate(variants, 1):
        try:
            r = run_single(overrides, data["all_data"], data["breadth"], data["screens"], data["mr_ind"])
            m = extract_metrics(r)
            yb = year_breakdown(r)
        except Exception as e:
            print(f"{i:>3} {name:<30} ERROR: {e}")
            import traceback; traceback.print_exc()
            continue

        print_row(i, name, m)
        if m:
            sanity_check(name, m)

        results.append({
            "name": name,
            "overrides": overrides,
            "metrics": m,
            "year_breakdown": yb,
        })

    # Rank by Sharpe
    valid = [r for r in results if r["metrics"] is not None]
    valid.sort(key=lambda x: x["metrics"]["sharpe_ratio"], reverse=True)

    print(f"\nRanked by Sharpe (Gap {gap_num} — {gap_name}):")
    for i, v in enumerate(valid, 1):
        m = v["metrics"]
        print(f"  {i}. {v['name']:<30} Sharpe:{m['sharpe_ratio']:.2f}  Ret:{m['total_return_pct']:.0f}%  DD:{m['max_drawdown_pct']:.1f}%  MR PnL:{m['mr_pnl']:+,.0f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"phase2_gap{gap_num}_{gap_name}.json"
    save_json(results, out_path)


def cmd_combo_batch(batch_num):
    """Run a batch of 8 combinations from combo_matrix.json."""
    matrix_path = RESULTS_DIR / "combo_matrix.json"
    if not matrix_path.exists():
        print(f"ERROR: {matrix_path} not found. Run --analyze after Phase 2 to generate it, "
              f"or generate it manually.", file=sys.stderr)
        sys.exit(1)

    with open(matrix_path) as f:
        combos = json.load(f)

    batch_size = 8
    start_idx = (batch_num - 1) * batch_size
    end_idx = start_idx + batch_size
    batch = combos[start_idx:end_idx]

    if not batch:
        print(f"ERROR: Batch {batch_num} is empty (combos {start_idx+1}-{end_idx} of {len(combos)})")
        sys.exit(1)

    data = load_pickle()

    print(f"\n{'='*80}")
    print(f"COMBO BATCH {batch_num}: combos {start_idx+1}-{min(end_idx, len(combos))} of {len(combos)}")
    print(f"{'='*80}")

    header = f"{'#':>3} {'Name':<40} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'PF':>7} {'Trd':>5} {'MR PnL':>10}"
    print(header)
    print("-" * len(header))

    results = []
    for i, combo in enumerate(batch, start_idx + 1):
        name = combo["name"]
        overrides = combo["overrides"]
        try:
            r = run_single(overrides, data["all_data"], data["breadth"], data["screens"], data["mr_ind"])
            m = extract_metrics(r)
            yb = year_breakdown(r)
        except Exception as e:
            print(f"{i:>3} {name:<40} ERROR: {e}")
            import traceback; traceback.print_exc()
            continue

        if m:
            print(f"{i:>3} {name:<40} {m['total_return_pct']:>7.1f}% {m['max_drawdown_pct']:>6.1f}% "
                  f"{m['sharpe_ratio']:>7.2f} {m['profit_factor']:>6.2f} {m['total_trades']:>5} {m['mr_pnl']:>+10,.0f}")
            sanity_check(name, m)
        else:
            print(f"{i:>3} {name:<40} N/A")

        results.append({
            "name": name,
            "overrides": overrides,
            "metrics": m,
            "year_breakdown": yb,
        })

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"phase3_batch{batch_num}.json"
    save_json(results, out_path)


def cmd_analyze():
    """Merge all results, generate combo matrix if needed, rank, and report."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Phase 2 analysis: find top 2 per gap ---
    phase2_results = {}
    all_phase2_exist = True
    for gap_num in range(1, 6):
        gap_name = GAP_NAMES[gap_num]
        path = RESULTS_DIR / f"phase2_gap{gap_num}_{gap_name}.json"
        if path.exists():
            with open(path) as f:
                phase2_results[gap_num] = json.load(f)
        else:
            all_phase2_exist = False
            print(f"Missing: {path}")

    if not all_phase2_exist:
        print("Not all Phase 2 results available. Run all --gap 1..5 first.")
        # Generate combo matrix from whatever we have
        if not phase2_results:
            print("No Phase 2 results found. Nothing to analyze.")
            return

    # Select top 2 per gap by Sharpe (excluding baseline variant)
    top_per_gap = {}
    print("\n" + "=" * 80)
    print("PHASE 2 SUMMARY — Top 2 per gap")
    print("=" * 80)

    for gap_num, results in sorted(phase2_results.items()):
        gap_name = GAP_NAMES[gap_num]
        valid = [r for r in results if r["metrics"] is not None]
        valid.sort(key=lambda x: x["metrics"]["sharpe_ratio"], reverse=True)
        top2 = valid[:2]
        top_per_gap[gap_num] = top2

        print(f"\nGap {gap_num} ({gap_name}):")
        for r in top2:
            m = r["metrics"]
            print(f"  {r['name']:<30} Sharpe:{m['sharpe_ratio']:.2f}  Ret:{m['total_return_pct']:.0f}%  "
                  f"DD:{m['max_drawdown_pct']:.1f}%  MR PnL:{m['mr_pnl']:+,.0f}")

    # Write Phase 2 summary
    summary_lines = ["# Phase 2 Summary — Individual Gap Results\n"]
    summary_lines.append(f"| Gap | Name | Sharpe | Return% | MaxDD% | MR PnL | Overrides |")
    summary_lines.append(f"|-----|------|--------|---------|--------|--------|-----------|")
    for gap_num, results in sorted(phase2_results.items()):
        gap_name = GAP_NAMES[gap_num]
        valid = [r for r in results if r["metrics"] is not None]
        valid.sort(key=lambda x: x["metrics"]["sharpe_ratio"], reverse=True)
        for r in valid:
            m = r["metrics"]
            summary_lines.append(
                f"| {gap_num}-{gap_name} | {r['name']} | {m['sharpe_ratio']:.2f} | "
                f"{m['total_return_pct']:.0f}% | {m['max_drawdown_pct']:.1f}% | "
                f"{m['mr_pnl']:+,.0f} | {json.dumps(r['overrides'])} |"
            )
    with open(RESULTS_DIR / "phase2_summary.md", "w") as f:
        f.write("\n".join(summary_lines))
    print(f"\nSaved: {RESULTS_DIR / 'phase2_summary.md'}")

    # --- Generate combo matrix (2^5 = 32 combinations) ---
    if top_per_gap:
        choices_per_gap = {}
        for gap_num, top2 in sorted(top_per_gap.items()):
            choices = []
            for r in top2:
                choices.append(r["overrides"])
            # Ensure we have exactly 2 choices (pad with empty if only 1)
            if len(choices) == 1:
                choices.append(choices[0])
            choices_per_gap[gap_num] = choices

        # Generate all 2^5 combos
        combos = []
        for i in range(32):
            bits = [(i >> b) & 1 for b in range(5)]
            merged = {}
            name_parts = []
            for gap_idx, bit in enumerate(bits):
                gap_num = gap_idx + 1
                gap_name = GAP_NAMES[gap_num]
                choice = choices_per_gap.get(gap_num, [{}])[bit] if gap_num in choices_per_gap else {}
                merged.update(choice)
                # Get name of the chosen variant
                if gap_num in top_per_gap and len(top_per_gap[gap_num]) > bit:
                    name_parts.append(top_per_gap[gap_num][bit]["name"])
                else:
                    name_parts.append(f"g{gap_num}_default")

            combo_name = " + ".join(name_parts)
            combos.append({"name": combo_name, "overrides": merged, "combo_index": len(combos) + 1})

        save_json(combos, RESULTS_DIR / "combo_matrix.json")
        print(f"\nGenerated {len(combos)} combinations in combo_matrix.json")

    # --- Phase 3 analysis: merge and rank ---
    phase3_results = []
    for batch in range(1, 5):
        path = RESULTS_DIR / f"phase3_batch{batch}.json"
        if path.exists():
            with open(path) as f:
                phase3_results.extend(json.load(f))

    if not phase3_results:
        print("\nNo Phase 3 results yet. Run --combo-batch 1..4 after generating combo_matrix.json.")
        return

    # Rank by Sharpe (primary), profit_factor (secondary), max_dd (tertiary, ascending)
    valid = [r for r in phase3_results if r["metrics"] is not None]
    valid.sort(key=lambda x: (
        -x["metrics"]["sharpe_ratio"],
        -x["metrics"]["profit_factor"],
        x["metrics"]["max_drawdown_pct"],
    ))

    print(f"\n{'='*100}")
    print(f"PHASE 3 — ALL COMBOS RANKED BY SHARPE ({len(valid)} valid)")
    print(f"{'='*100}")

    header = f"{'#':>3} {'Name':<50} {'Ret':>7} {'DD':>6} {'Sharpe':>7} {'PF':>6} {'Trd':>5} {'MR PnL':>10}"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(valid[:20], 1):
        m = r["metrics"]
        name = r["name"][:50]
        print(f"{i:>3} {name:<50} {m['total_return_pct']:>6.0f}% {m['max_drawdown_pct']:>5.1f}% "
              f"{m['sharpe_ratio']:>7.2f} {m['profit_factor']:>5.2f} {m['total_trades']:>5} {m['mr_pnl']:>+10,.0f}")

    # Consistency scoring for top 5
    print(f"\n{'='*100}")
    print("TOP 5 — YEAR-BY-YEAR ROBUSTNESS")
    print(f"{'='*100}")

    for i, r in enumerate(valid[:5], 1):
        m = r["metrics"]
        print(f"\n#{i}: {r['name']}")
        print(f"  Overall: Ret={m['total_return_pct']:.0f}% DD={m['max_drawdown_pct']:.1f}% Sharpe={m['sharpe_ratio']:.2f}")
        yb = r.get("year_breakdown", [])
        neg_years = [y for y in yb if y["return_pct"] < 0]
        deep_dd_years = [y for y in yb if y["max_dd_pct"] > 30]
        consistency = len(yb) - len(neg_years)
        print(f"  Positive years: {consistency}/{len(yb)}  |  Deep DD years (>30%): {len(deep_dd_years)}")
        if yb:
            print(f"  {'Year':<6} {'Return':>8} {'MaxDD':>7} {'Sharpe':>7} {'MR':>4} {'MR PnL':>10}")
            for y in yb:
                flag = " **" if y["return_pct"] < 0 or y["max_dd_pct"] > 30 else ""
                print(f"  {y['year']:<6} {y['return_pct']:>7.1f}% {y['max_dd_pct']:>6.1f}% "
                      f"{y['sharpe']:>7.2f} {y['mr_trades']:>4} {y['mr_pnl']:>+10,.0f}{flag}")

    # Load baseline for comparison
    baseline_path = RESULTS_DIR / "baseline.json"
    baseline_m = None
    if baseline_path.exists():
        with open(baseline_path) as f:
            baseline_data = json.load(f)
            baseline_m = baseline_data.get("metrics")

    # Final report
    report_lines = ["# MR Strategy Parameter Sweep — Final Report\n"]
    report_lines.append(f"Date: {date.today()}\n")

    if baseline_m:
        report_lines.append("## Baseline")
        report_lines.append(f"- Return: {baseline_m['total_return_pct']:.1f}%")
        report_lines.append(f"- MaxDD: {baseline_m['max_drawdown_pct']:.1f}%")
        report_lines.append(f"- Sharpe: {baseline_m['sharpe_ratio']:.2f}")
        report_lines.append(f"- MR PnL: {baseline_m['mr_pnl']:+,.0f}\n")

    report_lines.append("## Top 10 Combinations\n")
    report_lines.append("| Rank | Sharpe | Return% | MaxDD% | PF | MR PnL | Config |")
    report_lines.append("|------|--------|---------|--------|-----|--------|--------|")
    for i, r in enumerate(valid[:10], 1):
        m = r["metrics"]
        delta_sharpe = m["sharpe_ratio"] - baseline_m["sharpe_ratio"] if baseline_m else 0
        report_lines.append(
            f"| {i} | {m['sharpe_ratio']:.2f} ({delta_sharpe:+.2f}) | {m['total_return_pct']:.0f}% | "
            f"{m['max_drawdown_pct']:.1f}% | {m['profit_factor']:.2f} | {m['mr_pnl']:+,.0f} | "
            f"`{json.dumps(r['overrides'])}` |"
        )

    if valid:
        winner = valid[0]
        report_lines.append(f"\n## Recommended Configuration\n")
        report_lines.append(f"```json\n{json.dumps(winner['overrides'], indent=2)}\n```\n")

        report_lines.append("## Winner Year-by-Year\n")
        report_lines.append("| Year | Return% | MaxDD% | Sharpe | MR Trades | MR PnL |")
        report_lines.append("|------|---------|--------|--------|-----------|--------|")
        for y in winner.get("year_breakdown", []):
            report_lines.append(
                f"| {y['year']} | {y['return_pct']:.1f}% | {y['max_dd_pct']:.1f}% | "
                f"{y['sharpe']:.2f} | {y['mr_trades']} | {y['mr_pnl']:+,.0f} |"
            )

        # Save machine-readable config
        param_changes = {**BASELINE, **winner["overrides"]}
        save_json(param_changes, Path(__file__).resolve().parent / "PARAMETER_CHANGES.json")

    with open(Path(__file__).resolve().parent / "FINAL_REPORT.md", "w") as f:
        f.write("\n".join(report_lines))
    print(f"\nSaved: {Path(__file__).resolve().parent / 'FINAL_REPORT.md'}")


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="MR Strategy Parameter Sweep Harness")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--precompute", action="store_true", help="Precompute and cache data")
    group.add_argument("--baseline", action="store_true", help="Run and validate baseline")
    group.add_argument("--gap", type=int, choices=[1, 2, 3, 4, 5], help="Run gap N sweep")
    group.add_argument("--combo-batch", type=int, choices=[1, 2, 3, 4], help="Run combo batch N")
    group.add_argument("--analyze", action="store_true", help="Analyze all results")

    args = parser.parse_args()

    if args.precompute:
        cmd_precompute()
    elif args.baseline:
        cmd_baseline()
    elif args.gap:
        cmd_gap(args.gap)
    elif args.combo_batch:
        cmd_combo_batch(args.combo_batch)
    elif args.analyze:
        cmd_analyze()


if __name__ == "__main__":
    main()
