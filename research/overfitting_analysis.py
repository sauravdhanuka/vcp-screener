"""Overfitting Analysis — 8-test validation suite for VCP + MR strategies.

Usage:
    python research/overfitting_analysis.py --quick-tests       # Tests 1 + 2c + 6 (~4 min)
    python research/overfitting_analysis.py --sensitivity-rsi   # Test 2a (~9 min)
    python research/overfitting_analysis.py --sensitivity-sma   # Test 2b (~4 min)
    python research/overfitting_analysis.py --walk-forward      # Test 3 (~17 min)
    python research/overfitting_analysis.py --year-exclusion    # Test 4 (~5 min)
    python research/overfitting_analysis.py --analysis-only     # Tests 5 + 7 + 8 (<10s)
    python research/overfitting_analysis.py --report            # Generate report (<5s)
    python research/overfitting_analysis.py --all               # Run everything
"""

import argparse
import json
import logging
import pickle
import sys
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

logging.basicConfig(level=logging.WARNING)

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from vcp_screener.services.backtester import (
    BacktestEngine, load_backtest_data, precompute_screens, precompute_mr_indicators,
)
from vcp_screener.config import settings

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

WINNER_MR = {"rsi_exit": 75}
ADX30_MR = {"require_adx": True, "adx_max": 30}

# Walk-forward folds (5Y IS, 1Y OOS)
WF_FOLDS = [
    {"is_start": date(2016, 4, 1), "is_end": date(2021, 3, 31),
     "oos_start": date(2021, 4, 1), "oos_end": date(2022, 3, 31)},
    {"is_start": date(2017, 4, 1), "is_end": date(2022, 3, 31),
     "oos_start": date(2022, 4, 1), "oos_end": date(2023, 3, 31)},
    {"is_start": date(2018, 4, 1), "is_end": date(2023, 3, 31),
     "oos_start": date(2023, 4, 1), "oos_end": date(2024, 3, 31)},
    {"is_start": date(2019, 4, 1), "is_end": date(2024, 3, 31),
     "oos_start": date(2024, 4, 1), "oos_end": date(2025, 3, 31)},
    {"is_start": date(2020, 4, 1), "is_end": date(2025, 3, 31),
     "oos_start": date(2025, 4, 1), "oos_end": date(2026, 3, 1)},
]

# Walk-forward IS configs
WF_CONFIGS = [
    ("rsi60", {"rsi_exit": 60}),
    ("rsi65", {"rsi_exit": 65}),
    ("rsi70", {"rsi_exit": 70}),
    ("rsi75", {"rsi_exit": 75}),
    ("rsi80", {"rsi_exit": 80}),
    ("adx30", {"require_adx": True, "adx_max": 30}),
]

# SMA triplets for Test 2b
SMA_TRIPLETS = [
    ("20/50/100", 20, 50, 100),
    ("50/150/200", 50, 150, 200),
    ("30/80/150", 30, 80, 150),
]

# MR configs for SMA and regime tests
SMA_MR_CONFIGS = [
    ("baseline", {}),
    ("rsi75", {"rsi_exit": 75}),
    ("adx30", {"require_adx": True, "adx_max": 30}),
]

# Regime threshold pairs for Test 2c
REGIME_THRESHOLDS = [
    ("35/55", 35, 55),
    ("30/50", 30, 50),
    ("40/60", 40, 60),
]

REGIME_MR_CONFIGS = [
    ("baseline", {}),
    ("rsi75", {"rsi_exit": 75}),
]


# ---------- Helpers ----------

def load_pickle():
    """Load precomputed data from pickle cache."""
    if not PICKLE_PATH.exists():
        print(f"ERROR: Pickle not found at {PICKLE_PATH}. "
              f"Run mr_backtest_harness.py --precompute first.", file=sys.stderr)
        sys.exit(1)
    print(f"Loading pickle from {PICKLE_PATH}...", flush=True)
    t0 = time.time()
    with open(PICKLE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"Loaded in {time.time()-t0:.1f}s ({len(data['all_data'])} symbols)", flush=True)
    return data


def run_single(mr_overrides, all_data, breadth, screens, mr_ind,
               start=None, end=None, regime_overrides=None, screens_override=None):
    """Run one backtest with given MR overrides. Returns result dict."""
    mr_cfg = {**BASELINE, **mr_overrides}
    s = start or START
    e = end or END
    use_screens = screens if screens_override is None else screens_override
    engine = BacktestEngine(
        initial_capital=500000, max_positions=5, mr_config=mr_cfg,
        regime_config=regime_overrides,
    )
    r = engine.run(s, e, preloaded_data=all_data, preloaded_breadth=breadth,
                   precomputed_screens=use_screens, precomputed_mr_ind=mr_ind)
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

        peak = start_eq
        max_dd = 0
        for e in entries:
            if e["equity"] > peak:
                peak = e["equity"]
            dd = (peak - e["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        eq_vals = [e["equity"] for e in entries]
        if len(eq_vals) >= 2:
            daily_ret = pd.Series(eq_vals).pct_change().dropna()
            sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
        else:
            sharpe = 0

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


def get_daily_returns(result):
    """Extract daily returns from backtest equity curve."""
    ec = result.get("equity_curve", [])
    if not ec:
        return pd.Series(dtype=float)
    eq_vals = [e["equity"] for e in ec]
    return pd.Series(eq_vals).pct_change().dropna()


@contextmanager
def override_sma(short, mid, long):
    """Temporarily mutate settings.sma_short/mid/long, restore on exit."""
    orig = (settings.sma_short, settings.sma_mid, settings.sma_long)
    settings.sma_short = short
    settings.sma_mid = mid
    settings.sma_long = long
    try:
        yield
    finally:
        settings.sma_short, settings.sma_mid, settings.sma_long = orig


def collect_all_sharpes():
    """Load Sharpe ratios from all existing sweep result JSONs."""
    sharpes = []
    for path in sorted(RESULTS_DIR.glob("phase2_gap*.json")):
        with open(path) as f:
            results = json.load(f)
        for r in results:
            if r.get("metrics") and r["metrics"].get("sharpe_ratio"):
                sharpes.append(r["metrics"]["sharpe_ratio"])
    for path in sorted(RESULTS_DIR.glob("phase3_batch*.json")):
        with open(path) as f:
            results = json.load(f)
        for r in results:
            if r.get("metrics") and r["metrics"].get("sharpe_ratio"):
                sharpes.append(r["metrics"]["sharpe_ratio"])
    baseline_path = RESULTS_DIR / "baseline.json"
    if baseline_path.exists():
        with open(baseline_path) as f:
            data = json.load(f)
        if data.get("metrics") and data["metrics"].get("sharpe_ratio"):
            sharpes.append(data["metrics"]["sharpe_ratio"])
    return sharpes


def compute_deflated_sharpe(sr_hat_annual, all_sharpes_annual, daily_returns):
    """Compute Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

    All input Sharpes are annualized; internally converted to non-annualized
    for the DSR test statistic.
    """
    N = len(all_sharpes_annual)
    T = len(daily_returns)

    if N < 2 or T < 30:
        return {"dsr": None, "error": f"Insufficient data: N={N}, T={T}"}

    # Convert to non-annualized (daily scale) for correct DSR calculation
    sqrt252 = np.sqrt(252)
    sr_hat = sr_hat_annual / sqrt252
    all_sr = [s / sqrt252 for s in all_sharpes_annual]

    mean_sr = np.mean(all_sr)
    std_sr = np.std(all_sr, ddof=1)

    skew = float(daily_returns.skew())
    kurt = float(daily_returns.kurtosis())  # excess kurtosis

    # Expected maximum Sharpe (Euler-Mascheroni approximation)
    euler_gamma = 0.5772156649
    ln_N = np.log(N)
    sqrt_2lnN = np.sqrt(2 * ln_N)
    e_max_sr = (1 - euler_gamma / sqrt_2lnN) * sqrt_2lnN * std_sr + mean_sr

    # DSR test statistic
    numerator = (sr_hat - e_max_sr) * np.sqrt(T - 1)
    denom_inner = 1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2

    if denom_inner <= 0:
        return {"dsr": None, "error": "Invalid denominator (negative variance adjustment)"}

    denominator = np.sqrt(denom_inner)
    dsr = float(norm.cdf(numerator / denominator))

    verdict = "PASS" if dsr >= 0.95 else ("CAUTION" if dsr >= 0.50 else "FAIL")

    return {
        "dsr": round(dsr, 4),
        "sr_hat_annual": round(sr_hat_annual, 4),
        "sr_hat_daily": round(float(sr_hat), 4),
        "e_max_sr_annual": round(float(e_max_sr * sqrt252), 4),
        "e_max_sr_daily": round(float(e_max_sr), 4),
        "n_trials": N,
        "n_observations": T,
        "mean_sr_annual": round(float(mean_sr * sqrt252), 4),
        "std_sr_annual": round(float(std_sr * sqrt252), 4),
        "skewness": round(skew, 4),
        "excess_kurtosis": round(kurt, 4),
        "verdict": verdict,
    }


# ---------- Commands ----------

def cmd_quick_tests():
    """Tests 1 (Deflated Sharpe) + 2c (Regime Thresholds) + 6 (Regime Performance)."""
    data = load_pickle()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Test 1: Deflated Sharpe Ratio ----
    print("\n" + "=" * 60)
    print("TEST 1: DEFLATED SHARPE RATIO")
    print("=" * 60)

    all_sharpes = collect_all_sharpes()
    print(f"Collected {len(all_sharpes)} Sharpe ratios from prior sweeps")

    print("  Running winner (rsi_exit=75)...", end=" ", flush=True)
    r = run_single(WINNER_MR, data["all_data"], data["breadth"],
                   data["screens"], data["mr_ind"])
    m = extract_metrics(r)
    daily_ret = get_daily_returns(r)

    if m:
        print(f"Sharpe={m['sharpe_ratio']:.2f}")
        dsr_result = compute_deflated_sharpe(m["sharpe_ratio"], all_sharpes, daily_ret)
        print(f"  Winner Sharpe: {m['sharpe_ratio']:.2f}")
        print(f"  E[max(SR)]:    {dsr_result.get('e_max_sr_annual', 'N/A')}")
        print(f"  DSR:           {dsr_result.get('dsr', 'N/A')}")
        print(f"  Verdict:       {dsr_result.get('verdict', 'N/A')}")
    else:
        dsr_result = {"dsr": None, "error": "Winner backtest failed"}
        print("ERROR: Winner backtest returned no results!")

    save_json(dsr_result, RESULTS_DIR / "overfit_deflated_sharpe.json")

    # ---- Test 2c: Regime Threshold Sensitivity ----
    print("\n" + "=" * 60)
    print("TEST 2c: REGIME THRESHOLD SENSITIVITY")
    print("=" * 60)

    regime_results = []
    for thresh_name, bear_th, bull_th in REGIME_THRESHOLDS:
        regime_cfg = {"bear_threshold": bear_th, "bull_threshold": bull_th}
        for mr_name, mr_overrides in REGIME_MR_CONFIGS:
            label = f"{thresh_name} / {mr_name}"
            print(f"  Running {label}...", end=" ", flush=True)
            r = run_single(mr_overrides, data["all_data"], data["breadth"],
                           data["screens"], data["mr_ind"],
                           regime_overrides=regime_cfg)
            m = extract_metrics(r)
            if m:
                print(f"Sharpe={m['sharpe_ratio']:.2f} Ret={m['total_return_pct']:.0f}%")
            else:
                print("N/A")
            regime_results.append({
                "threshold": thresh_name,
                "bear": bear_th,
                "bull": bull_th,
                "mr_config": mr_name,
                "metrics": m,
            })

    # Analyze: max Sharpe diff across thresholds per MR config
    regime_analysis = {}
    for mr_name, _ in REGIME_MR_CONFIGS:
        sharpes = [r["metrics"]["sharpe_ratio"] for r in regime_results
                   if r["mr_config"] == mr_name and r["metrics"]]
        if sharpes:
            max_diff = max(sharpes) - min(sharpes)
            verdict = "PASS" if max_diff < 0.3 else "FAIL"
            regime_analysis[mr_name] = {
                "sharpes": sharpes,
                "max_diff": round(max_diff, 4),
                "verdict": verdict,
            }
            print(f"  {mr_name}: range={min(sharpes):.2f}-{max(sharpes):.2f}, "
                  f"diff={max_diff:.2f} -> {verdict}")

    overall_verdict = ("PASS" if all(v["verdict"] == "PASS" for v in regime_analysis.values())
                       else "FAIL")
    regime_data = {
        "runs": regime_results,
        "analysis": regime_analysis,
        "verdict": overall_verdict,
    }
    save_json(regime_data, RESULTS_DIR / "overfit_regime_threshold.json")

    # ---- Test 6: Regime-Specific Performance ----
    print("\n" + "=" * 60)
    print("TEST 6: REGIME-SPECIFIC PERFORMANCE")
    print("=" * 60)

    # VCP-only: disable MR entries via max_positions=0
    print("  Running VCP-only...", end=" ", flush=True)
    r_vcp = run_single({"max_positions": 0}, data["all_data"], data["breadth"],
                       data["screens"], data["mr_ind"])
    m_vcp = extract_metrics(r_vcp)
    yb_vcp = year_breakdown(r_vcp)
    if m_vcp:
        print(f"Sharpe={m_vcp['sharpe_ratio']:.2f} Ret={m_vcp['total_return_pct']:.0f}%")
    else:
        print("N/A")

    # MR-only: empty screens -> no VCP candidates
    print("  Running MR-only (all regimes)...", end=" ", flush=True)
    r_mr = run_single({"all_regimes": True, "rsi_exit": 75}, data["all_data"],
                      data["breadth"], data["screens"], data["mr_ind"],
                      screens_override={})
    m_mr = extract_metrics(r_mr)
    yb_mr = year_breakdown(r_mr)
    if m_mr:
        print(f"Sharpe={m_mr['sharpe_ratio']:.2f} Ret={m_mr['total_return_pct']:.0f}%")
    else:
        print("N/A")

    # MR all_regimes + VCP: full system with MR active everywhere
    print("  Running MR all_regimes + VCP...", end=" ", flush=True)
    r_both = run_single({"all_regimes": True, "rsi_exit": 75}, data["all_data"],
                        data["breadth"], data["screens"], data["mr_ind"])
    m_both = extract_metrics(r_both)
    yb_both = year_breakdown(r_both)
    if m_both:
        print(f"Sharpe={m_both['sharpe_ratio']:.2f} Ret={m_both['total_return_pct']:.0f}%")
    else:
        print("N/A")

    # Analyze regime profitability
    vcp_positive_years = sum(1 for y in yb_vcp if y["return_pct"] > 0) if yb_vcp else 0
    mr_positive_years = sum(1 for y in yb_mr if y["return_pct"] > 0) if yb_mr else 0
    total_years = len(yb_vcp) if yb_vcp else 0
    vcp_pass = vcp_positive_years >= 8
    mr_pass = mr_positive_years >= 6

    print(f"\n  VCP profitable years: {vcp_positive_years}/{total_years} "
          f"(need >=8) -> {'PASS' if vcp_pass else 'FAIL'}")
    print(f"  MR profitable years:  {mr_positive_years}/{len(yb_mr) if yb_mr else 0} "
          f"(need >=6) -> {'PASS' if mr_pass else 'FAIL'}")

    regime_perf = {
        "vcp_only": {"metrics": m_vcp, "year_breakdown": yb_vcp},
        "mr_only": {"metrics": m_mr, "year_breakdown": yb_mr},
        "mr_all_regimes_plus_vcp": {"metrics": m_both, "year_breakdown": yb_both},
        "vcp_positive_years": vcp_positive_years,
        "mr_positive_years": mr_positive_years,
        "total_years": total_years,
        "verdict": "PASS" if vcp_pass and mr_pass else "FAIL",
    }
    save_json(regime_perf, RESULTS_DIR / "overfit_regime_perf.json")


def cmd_sensitivity_rsi():
    """Test 2a: RSI exit sensitivity (60-80, step 1). 21 backtests."""
    data = load_pickle()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("TEST 2a: RSI EXIT SENSITIVITY (60-80)")
    print("=" * 60)

    results = []
    for rsi_val in range(60, 81):
        print(f"  RSI exit {rsi_val}...", end=" ", flush=True)
        r = run_single({"rsi_exit": rsi_val}, data["all_data"], data["breadth"],
                       data["screens"], data["mr_ind"])
        m = extract_metrics(r)
        yb = year_breakdown(r)
        if m:
            print(f"Sharpe={m['sharpe_ratio']:.2f} Ret={m['total_return_pct']:.0f}%")
        else:
            print("N/A")
        results.append({"rsi_exit": rsi_val, "metrics": m, "year_breakdown": yb})

    # Analyze: sort by Sharpe, check top-3 span
    valid = [(r["rsi_exit"], r["metrics"]["sharpe_ratio"])
             for r in results if r["metrics"]]
    valid.sort(key=lambda x: -x[1])
    top3 = valid[:3]
    top3_rsi = [v[0] for v in top3]
    span = max(top3_rsi) - min(top3_rsi)
    is_plateau = span >= 5

    print(f"\n  Top 3: {top3}")
    print(f"  RSI span: {span} (need >=5 for plateau) "
          f"-> {'PASS (plateau)' if is_plateau else 'FAIL (spike)'}")

    rsi_data = {
        "runs": results,
        "top3": [{"rsi_exit": v[0], "sharpe": v[1]} for v in top3],
        "span": span,
        "verdict": "PASS" if is_plateau else "FAIL",
    }
    save_json(rsi_data, RESULTS_DIR / "overfit_sensitivity_rsi.json")


def cmd_sensitivity_sma():
    """Test 2b: SMA period sensitivity (3 triplets x 3 MR configs). 9 backtests."""
    data = load_pickle()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("TEST 2b: SMA PERIOD SENSITIVITY")
    print("=" * 60)

    results = []
    for triplet_name, sma_s, sma_m, sma_l in SMA_TRIPLETS:
        print(f"\n  SMA triplet {triplet_name}:", flush=True)
        # Recompute screens with overridden SMA settings
        with override_sma(sma_s, sma_m, sma_l):
            print(f"    Precomputing screens...", flush=True)
            t0 = time.time()
            triplet_screens = precompute_screens(data["all_data"], START, END)
            print(f"    Done in {time.time()-t0:.0f}s", flush=True)

            for mr_name, mr_overrides in SMA_MR_CONFIGS:
                label = f"{triplet_name} / {mr_name}"
                print(f"    Running {label}...", end=" ", flush=True)
                r = run_single(mr_overrides, data["all_data"], data["breadth"],
                               triplet_screens, data["mr_ind"])
                m = extract_metrics(r)
                if m:
                    print(f"Sharpe={m['sharpe_ratio']:.2f}")
                else:
                    print("N/A")
                results.append({
                    "sma_triplet": triplet_name,
                    "mr_config": mr_name,
                    "metrics": m,
                })

    # Analyze: is current triplet dramatically better?
    current_sharpes = [r["metrics"]["sharpe_ratio"] for r in results
                       if r["sma_triplet"] == "20/50/100" and r["metrics"]]
    other_sharpes = [r["metrics"]["sharpe_ratio"] for r in results
                     if r["sma_triplet"] != "20/50/100" and r["metrics"]]

    current_avg = float(np.mean(current_sharpes)) if current_sharpes else 0
    other_avg = float(np.mean(other_sharpes)) if other_sharpes else 0

    if current_sharpes and other_sharpes and other_avg != 0:
        improvement = (current_avg - other_avg) / abs(other_avg) * 100
        verdict = "PASS" if improvement < 30 else "FAIL"
        print(f"\n  Current avg Sharpe: {current_avg:.2f}")
        print(f"  Other avg Sharpe:   {other_avg:.2f}")
        print(f"  Improvement: {improvement:.0f}% (need <30%) -> {verdict}")
    else:
        improvement = None
        verdict = "UNKNOWN"

    sma_data = {
        "runs": results,
        "current_avg_sharpe": round(current_avg, 4),
        "other_avg_sharpe": round(other_avg, 4),
        "improvement_pct": round(improvement, 2) if improvement is not None else None,
        "verdict": verdict,
    }
    save_json(sma_data, RESULTS_DIR / "overfit_sensitivity_sma.json")


def cmd_walk_forward():
    """Test 3: Walk-forward analysis (5 folds, 5Y IS / 1Y OOS). ~40 backtests."""
    data = load_pickle()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("TEST 3: WALK-FORWARD ANALYSIS")
    print("=" * 60)

    fold_results = []

    for fold_idx, fold in enumerate(WF_FOLDS, 1):
        print(f"\n  Fold {fold_idx}: IS={fold['is_start']}->{fold['is_end']}, "
              f"OOS={fold['oos_start']}->{fold['oos_end']}")

        # Run all configs on IS period
        is_results = []
        for cfg_name, cfg_overrides in WF_CONFIGS:
            print(f"    IS {cfg_name}...", end=" ", flush=True)
            r = run_single(cfg_overrides, data["all_data"], data["breadth"],
                           data["screens"], data["mr_ind"],
                           start=fold["is_start"], end=fold["is_end"])
            m = extract_metrics(r)
            sharpe = m["sharpe_ratio"] if m else -999
            if m:
                print(f"Sharpe={sharpe:.2f}")
            else:
                print("N/A")
            is_results.append({
                "name": cfg_name, "overrides": cfg_overrides,
                "sharpe": sharpe, "metrics": m,
            })

        # Pick IS winner by Sharpe
        is_results.sort(key=lambda x: -x["sharpe"])
        is_winner = is_results[0]
        print(f"    IS winner: {is_winner['name']} (Sharpe={is_winner['sharpe']:.2f})")

        # Run IS winner on OOS
        print(f"    OOS winner ({is_winner['name']})...", end=" ", flush=True)
        r_oos_w = run_single(is_winner["overrides"], data["all_data"], data["breadth"],
                             data["screens"], data["mr_ind"],
                             start=fold["oos_start"], end=fold["oos_end"])
        m_oos_w = extract_metrics(r_oos_w)
        oos_w_sharpe = m_oos_w["sharpe_ratio"] if m_oos_w else 0
        oos_w_mr = m_oos_w["mr_trades"] if m_oos_w else 0
        print(f"Sharpe={oos_w_sharpe:.2f} MR_trades={oos_w_mr}")

        # Run baseline on OOS
        print(f"    OOS baseline...", end=" ", flush=True)
        r_oos_b = run_single({}, data["all_data"], data["breadth"],
                             data["screens"], data["mr_ind"],
                             start=fold["oos_start"], end=fold["oos_end"])
        m_oos_b = extract_metrics(r_oos_b)
        oos_b_sharpe = m_oos_b["sharpe_ratio"] if m_oos_b else 0
        print(f"Sharpe={oos_b_sharpe:.2f}")

        fold_results.append({
            "fold": fold_idx,
            "is_period": f"{fold['is_start']}->{fold['is_end']}",
            "oos_period": f"{fold['oos_start']}->{fold['oos_end']}",
            "is_winner": is_winner["name"],
            "is_winner_sharpe": is_winner["sharpe"],
            "oos_winner_sharpe": oos_w_sharpe,
            "oos_baseline_sharpe": oos_b_sharpe,
            "oos_mr_trades": oos_w_mr,
            "low_trade_warning": oos_w_mr < 5,
        })

    # Compute Walk-Forward Efficiency
    is_sharpes = [f["is_winner_sharpe"] for f in fold_results if f["is_winner_sharpe"] > 0]
    oos_sharpes = [f["oos_winner_sharpe"] for f in fold_results]
    mean_is = float(np.mean(is_sharpes)) if is_sharpes else 0
    mean_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0
    wfe = (mean_oos / mean_is * 100) if mean_is > 0 else 0

    unique_winners = len(set(f["is_winner"] for f in fold_results))
    low_trade_folds = sum(1 for f in fold_results if f["low_trade_warning"])

    if wfe >= 50:
        verdict = "PASS"
    elif wfe >= 40:
        verdict = "CAUTION"
    else:
        verdict = "FAIL"

    print(f"\n  WFE: {wfe:.1f}% (mean OOS {mean_oos:.2f} / mean IS {mean_is:.2f})")
    print(f"  Unique IS winners: {unique_winners}/5")
    print(f"  Low-trade OOS folds: {low_trade_folds}")
    print(f"  Verdict: {verdict}")

    wf_data = {
        "folds": fold_results,
        "mean_is_sharpe": round(mean_is, 4),
        "mean_oos_sharpe": round(mean_oos, 4),
        "wfe_pct": round(wfe, 2),
        "unique_is_winners": unique_winners,
        "low_trade_folds": low_trade_folds,
        "verdict": verdict,
    }
    save_json(wf_data, RESULTS_DIR / "overfit_walkforward.json")


def cmd_year_exclusion():
    """Test 4: Year exclusion (skip 2023, skip 2020). 12 backtests."""
    data = load_pickle()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("TEST 4: YEAR EXCLUSION")
    print("=" * 60)

    exclusions = [
        {
            "name": "skip_2023",
            "periods": [
                ("pre_2023", date(2016, 4, 1), date(2022, 12, 31)),
                ("post_2023", date(2024, 1, 1), date(2026, 3, 1)),
            ],
        },
        {
            "name": "skip_2020",
            "periods": [
                ("pre_2020", date(2016, 4, 1), date(2019, 12, 31)),
                ("post_2020", date(2021, 1, 1), date(2026, 3, 1)),
            ],
        },
    ]

    configs = [
        ("baseline", {}),
        ("rsi75", WINNER_MR),
        ("adx30", ADX30_MR),
    ]

    all_results = []
    for excl in exclusions:
        print(f"\n  {excl['name']}:")
        excl_results = {"name": excl["name"], "periods": []}

        for period_name, p_start, p_end in excl["periods"]:
            period_data = {
                "period": period_name,
                "start": str(p_start),
                "end": str(p_end),
                "configs": [],
            }
            for cfg_name, cfg_overrides in configs:
                label = f"{period_name}/{cfg_name}"
                print(f"    {label}...", end=" ", flush=True)
                r = run_single(cfg_overrides, data["all_data"], data["breadth"],
                               data["screens"], data["mr_ind"],
                               start=p_start, end=p_end)
                m = extract_metrics(r)
                if m:
                    print(f"Sharpe={m['sharpe_ratio']:.2f}")
                else:
                    print("N/A")
                period_data["configs"].append({"name": cfg_name, "metrics": m})
            excl_results["periods"].append(period_data)

        # Check: winner (rsi75) beats baseline in BOTH sub-periods
        winner_beats = True
        for period in excl_results["periods"]:
            base_sharpe = None
            winner_sharpe = None
            for cfg in period["configs"]:
                if cfg["name"] == "baseline" and cfg["metrics"]:
                    base_sharpe = cfg["metrics"]["sharpe_ratio"]
                if cfg["name"] == "rsi75" and cfg["metrics"]:
                    winner_sharpe = cfg["metrics"]["sharpe_ratio"]
            if base_sharpe is not None and winner_sharpe is not None:
                if winner_sharpe <= base_sharpe:
                    winner_beats = False
            else:
                winner_beats = False

        excl_results["winner_beats_both"] = winner_beats
        print(f"    Winner beats baseline in both periods: {winner_beats}")
        all_results.append(excl_results)

    # Overall: winner must beat baseline in BOTH exclusion tests
    overall = all(r["winner_beats_both"] for r in all_results)
    year_excl_data = {
        "exclusions": all_results,
        "verdict": "PASS" if overall else "FAIL",
    }
    save_json(year_excl_data, RESULTS_DIR / "overfit_year_exclusion.json")


def cmd_analysis_only():
    """Tests 5 (Consistency) + 7 (Trade Count) + 8 (Survivorship). No backtests."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Test 5: Consistency Metrics ----
    print("\n" + "=" * 60)
    print("TEST 5: CONSISTENCY METRICS")
    print("=" * 60)

    configs_to_analyze = {}

    # Load baseline
    baseline_path = RESULTS_DIR / "baseline.json"
    if baseline_path.exists():
        with open(baseline_path) as f:
            configs_to_analyze["baseline"] = json.load(f)

    # Find rsi75 in phase2_gap4
    gap4_path = RESULTS_DIR / "phase2_gap4_rsi_exit.json"
    if gap4_path.exists():
        with open(gap4_path) as f:
            gap4 = json.load(f)
        for r in gap4:
            if r.get("overrides", {}).get("rsi_exit") == 75:
                configs_to_analyze["rsi75"] = r
                break

    # Find adx30 in phase2_gap2
    gap2_path = RESULTS_DIR / "phase2_gap2_adx.json"
    if gap2_path.exists():
        with open(gap2_path) as f:
            gap2 = json.load(f)
        for r in gap2:
            ov = r.get("overrides", {})
            if ov.get("require_adx") is True and ov.get("adx_max") == 30:
                configs_to_analyze["adx30"] = r
                break

    consistency_data = {}
    for cfg_name, cfg_data in configs_to_analyze.items():
        yb = cfg_data.get("year_breakdown", [])
        m = cfg_data.get("metrics", {})
        if not yb:
            continue

        returns = [y["return_pct"] for y in yb]
        sharpes = [y["sharpe"] for y in yb]
        mr_pnls = [y["mr_pnl"] for y in yb]
        positive_years = sum(1 for r in returns if r > 0)
        neg_returns = [r for r in returns if r < 0]
        pos_returns = [r for r in returns if r > 0]

        gain_to_pain = (sum(pos_returns) / abs(sum(neg_returns))) if neg_returns else float("inf")
        max_dd = m.get("max_drawdown_pct", 0)
        recovery_factor = (m.get("total_return_pct", 0) / max_dd) if max_dd > 0 else float("inf")

        info = {
            "positive_years": positive_years,
            "total_years": len(yb),
            "sharpe_std": round(float(np.std(sharpes)), 4),
            "worst_year_return": round(min(returns), 2),
            "worst_year_sharpe": round(min(sharpes), 2),
            "gain_to_pain": round(gain_to_pain, 2),
            "recovery_factor": round(recovery_factor, 2),
            "mr_pnl_std": round(float(np.std(mr_pnls)), 2),
            "year_breakdown": yb,
        }
        consistency_data[cfg_name] = info
        print(f"\n  {cfg_name}:")
        print(f"    Positive years:  {positive_years}/{len(yb)}")
        print(f"    Sharpe std:      {info['sharpe_std']:.2f}")
        print(f"    Worst year:      {info['worst_year_return']:.1f}% "
              f"(Sharpe {info['worst_year_sharpe']:.2f})")
        print(f"    Gain-to-pain:    {info['gain_to_pain']:.2f}")
        print(f"    Recovery factor: {info['recovery_factor']:.2f}")

    save_json(consistency_data, RESULTS_DIR / "overfit_consistency.json")

    # ---- Test 7: Trade Count Validation ----
    print("\n" + "=" * 60)
    print("TEST 7: TRADE COUNT VALIDATION")
    print("=" * 60)

    if "baseline" in configs_to_analyze:
        bd = configs_to_analyze["baseline"]
        m = bd.get("metrics", {})
        total_trades = m.get("total_trades", 0)
        mr_trades_count = m.get("mr_trades", 0)
        vcp_trades = total_trades - mr_trades_count

        sr = m.get("sharpe_ratio", 0)
        # SE of Sharpe = sqrt((1 + 0.5*SR^2) / T), T = daily observations
        T = 10 * 252
        se_sharpe = np.sqrt((1 + 0.5 * sr ** 2) / T)
        ci_lower = sr - 1.96 * se_sharpe
        ci_upper = sr + 1.96 * se_sharpe

        yb = bd.get("year_breakdown", [])
        low_trade_years = [y for y in yb if y["total_trades"] < 30]

        trade_data = {
            "total_trades": total_trades,
            "vcp_trades": vcp_trades,
            "mr_trades": mr_trades_count,
            "sharpe": sr,
            "se_sharpe": round(float(se_sharpe), 4),
            "ci_95_lower": round(float(ci_lower), 4),
            "ci_95_upper": round(float(ci_upper), 4),
            "low_trade_years": low_trade_years,
            "min_trades_per_year": min(y["total_trades"] for y in yb) if yb else 0,
        }
        print(f"  Total: {total_trades} (VCP: {vcp_trades}, MR: {mr_trades_count})")
        print(f"  Sharpe SE: {se_sharpe:.3f}")
        print(f"  95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]")
        print(f"  Low-trade years (<30): {len(low_trade_years)}")
    else:
        trade_data = {"error": "baseline.json not found"}
        print("  ERROR: baseline.json not found")

    save_json(trade_data, RESULTS_DIR / "overfit_trade_count.json")

    # ---- Test 8: Survivorship Bias Estimate ----
    print("\n" + "=" * 60)
    print("TEST 8: SURVIVORSHIP BIAS ESTIMATE")
    print("=" * 60)

    try:
        from sqlalchemy import func
        from vcp_screener.db import get_session, init_db
        from vcp_screener.models.daily_price import DailyPrice

        init_db()
        session = get_session()

        results = session.query(
            DailyPrice.symbol,
            func.min(DailyPrice.date).label("first_date"),
            func.max(DailyPrice.date).label("last_date"),
        ).group_by(DailyPrice.symbol).all()

        total_stocks = len(results)
        entered_after_2016 = sum(1 for r in results if r.first_date > date(2016, 6, 1))
        ended_before_2026 = sum(1 for r in results if r.last_date < date(2025, 12, 1))

        session.close()

        # Kohli et al. haircut: 1-4% annual overstatement for Indian markets
        # Conservative: assume 2% annual bias
        annual_bias = 2.0

        if "baseline" in configs_to_analyze:
            bl_m = configs_to_analyze["baseline"].get("metrics", {})
            orig_sharpe = bl_m.get("sharpe_ratio", 0)
            orig_cagr = bl_m.get("cagr_pct", 0)
            adjusted_cagr = orig_cagr - annual_bias
            sharpe_reduction = annual_bias / orig_cagr if orig_cagr > 0 else 0
            adjusted_sharpe = orig_sharpe * (1 - sharpe_reduction)
        else:
            orig_sharpe = orig_cagr = adjusted_sharpe = adjusted_cagr = 0
            sharpe_reduction = 0

        survivorship_data = {
            "total_stocks_in_db": total_stocks,
            "entered_after_2016": entered_after_2016,
            "ended_before_2026": ended_before_2026,
            "estimated_survivorship_pct": round(
                ended_before_2026 / total_stocks * 100, 1) if total_stocks > 0 else 0,
            "haircut_range_annual": "1-4%",
            "assumed_annual_bias": annual_bias,
            "original_sharpe": orig_sharpe,
            "adjusted_sharpe": round(adjusted_sharpe, 2),
            "original_cagr": orig_cagr,
            "adjusted_cagr": round(adjusted_cagr, 2),
            "sharpe_reduction_pct": round(sharpe_reduction * 100, 1),
        }
        print(f"  Stocks in DB: {total_stocks}")
        print(f"  Entered after 2016: {entered_after_2016}")
        print(f"  Ended before 2026: {ended_before_2026}")
        print(f"  Est. survivorship: {survivorship_data['estimated_survivorship_pct']:.1f}%")
        print(f"  Sharpe: {orig_sharpe:.2f} -> {adjusted_sharpe:.2f} "
              f"(after {annual_bias}% annual haircut)")

    except Exception as e:
        survivorship_data = {"error": str(e)}
        print(f"  ERROR: {e}")

    save_json(survivorship_data, RESULTS_DIR / "overfit_survivorship.json")


def cmd_report():
    """Generate OVERFITTING_REPORT.md from all test results."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("GENERATING OVERFITTING REPORT")
    print("=" * 60)

    def load_result(name):
        path = RESULTS_DIR / name
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    dsr = load_result("overfit_deflated_sharpe.json")
    regime_thresh = load_result("overfit_regime_threshold.json")
    regime_perf = load_result("overfit_regime_perf.json")
    sens_rsi = load_result("overfit_sensitivity_rsi.json")
    sens_sma = load_result("overfit_sensitivity_sma.json")
    wf = load_result("overfit_walkforward.json")
    year_excl = load_result("overfit_year_exclusion.json")
    consistency = load_result("overfit_consistency.json")
    trade_count = load_result("overfit_trade_count.json")
    survivorship = load_result("overfit_survivorship.json")

    lines = [
        "# Overfitting Analysis Report",
        "",
        f"Generated: {date.today()}",
        "",
        "## Summary",
        "",
        "| # | Test | Verdict |",
        "|---|------|---------|",
    ]

    verdicts = {}

    # Collect verdicts
    v = dsr.get("verdict", "N/A") if dsr else "NOT RUN"
    verdicts["1_dsr"] = v
    dsr_val = dsr.get("dsr", "N/A") if dsr else "N/A"
    lines.append(f"| 1 | Deflated Sharpe Ratio (DSR={dsr_val}) | **{v}** |")

    v = sens_rsi.get("verdict", "N/A") if sens_rsi else "NOT RUN"
    verdicts["2a_rsi"] = v
    span = sens_rsi.get("span", "N/A") if sens_rsi else "N/A"
    lines.append(f"| 2a | RSI Exit Sensitivity (span={span}) | **{v}** |")

    v = sens_sma.get("verdict", "N/A") if sens_sma else "NOT RUN"
    verdicts["2b_sma"] = v
    imp = sens_sma.get("improvement_pct", "N/A") if sens_sma else "N/A"
    lines.append(f"| 2b | SMA Period Sensitivity (imp={imp}%) | **{v}** |")

    v = regime_thresh.get("verdict", "N/A") if regime_thresh else "NOT RUN"
    verdicts["2c_regime"] = v
    lines.append(f"| 2c | Regime Threshold Sensitivity | **{v}** |")

    v = wf.get("verdict", "N/A") if wf else "NOT RUN"
    verdicts["3_wf"] = v
    wfe = wf.get("wfe_pct", "N/A") if wf else "N/A"
    lines.append(f"| 3 | Walk-Forward Analysis (WFE={wfe}%) | **{v}** |")

    v = year_excl.get("verdict", "N/A") if year_excl else "NOT RUN"
    verdicts["4_year_excl"] = v
    lines.append(f"| 4 | Year Exclusion | **{v}** |")

    verdicts["5_consistency"] = "INFO"
    lines.append("| 5 | Consistency Metrics | **INFO** |")

    v = regime_perf.get("verdict", "N/A") if regime_perf else "NOT RUN"
    verdicts["6_regime"] = v
    lines.append(f"| 6 | Regime-Specific Performance | **{v}** |")

    verdicts["7_trades"] = "INFO"
    lines.append("| 7 | Trade Count Validation | **INFO** |")

    verdicts["8_surv"] = "INFO"
    lines.append("| 8 | Survivorship Bias Estimate | **INFO** |")

    lines.append("")

    # ---- Detailed sections ----

    # Test 1
    lines.append("## Test 1: Deflated Sharpe Ratio")
    lines.append("")
    if dsr and "error" not in dsr:
        lines.append(f"- **DSR**: {dsr.get('dsr', 'N/A')}")
        lines.append(f"- **Winner Sharpe**: {dsr.get('sr_hat_annual', 'N/A')}")
        lines.append(f"- **E[max(SR)]**: {dsr.get('e_max_sr_annual', 'N/A')}")
        lines.append(f"- **Trials**: {dsr.get('n_trials', 'N/A')}")
        lines.append(f"- **Observations**: {dsr.get('n_observations', 'N/A')}")
        lines.append(f"- **Skewness**: {dsr.get('skewness', 'N/A')}")
        lines.append(f"- **Excess Kurtosis**: {dsr.get('excess_kurtosis', 'N/A')}")
        lines.append("")
        lines.append("DSR >= 0.95 = robust, DSR < 0.50 = likely noise from multiple testing.")
    else:
        lines.append(f"Error: {dsr.get('error', 'Not run') if dsr else 'Not run'}")
    lines.append("")

    # Test 2a
    lines.append("## Test 2a: RSI Exit Sensitivity")
    lines.append("")
    if sens_rsi:
        top3 = sens_rsi.get("top3", [])
        top3_str = ", ".join(f"RSI {t['rsi_exit']} (Sharpe {t['sharpe']:.2f})" for t in top3)
        lines.append(f"- **Top 3**: {top3_str}")
        lines.append(f"- **RSI span**: {sens_rsi.get('span', 'N/A')} (need >= 5 for plateau)")
        lines.append("")
        lines.append("| RSI Exit | Sharpe |")
        lines.append("|----------|--------|")
        for r in sens_rsi.get("runs", []):
            if r.get("metrics"):
                lines.append(f"| {r['rsi_exit']} | {r['metrics']['sharpe_ratio']:.2f} |")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 2b
    lines.append("## Test 2b: SMA Period Sensitivity")
    lines.append("")
    if sens_sma:
        lines.append(f"- **Current (20/50/100) avg Sharpe**: {sens_sma.get('current_avg_sharpe', 'N/A')}")
        lines.append(f"- **Alternative avg Sharpe**: {sens_sma.get('other_avg_sharpe', 'N/A')}")
        lines.append(f"- **Improvement**: {sens_sma.get('improvement_pct', 'N/A')}% (need <30%)")
        lines.append("")
        lines.append("| SMA Triplet | MR Config | Sharpe |")
        lines.append("|-------------|-----------|--------|")
        for r in sens_sma.get("runs", []):
            sharpe = f"{r['metrics']['sharpe_ratio']:.2f}" if r.get("metrics") else "N/A"
            lines.append(f"| {r['sma_triplet']} | {r['mr_config']} | {sharpe} |")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 2c
    lines.append("## Test 2c: Regime Threshold Sensitivity")
    lines.append("")
    if regime_thresh:
        for mr_name, info in regime_thresh.get("analysis", {}).items():
            lines.append(f"- **{mr_name}**: Sharpe range "
                         f"{min(info['sharpes']):.2f}-{max(info['sharpes']):.2f}, "
                         f"diff={info['max_diff']:.2f} -> {info['verdict']}")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 3
    lines.append("## Test 3: Walk-Forward Analysis")
    lines.append("")
    if wf:
        lines.append(f"- **WFE**: {wf.get('wfe_pct', 'N/A')}%")
        lines.append(f"- **Mean IS Sharpe**: {wf.get('mean_is_sharpe', 'N/A')}")
        lines.append(f"- **Mean OOS Sharpe**: {wf.get('mean_oos_sharpe', 'N/A')}")
        lines.append(f"- **Unique IS winners**: {wf.get('unique_is_winners', 'N/A')}/5")
        lines.append(f"- **Low-trade OOS folds**: {wf.get('low_trade_folds', 'N/A')}")
        lines.append("")
        folds = wf.get("folds", [])
        if folds:
            lines.append("| Fold | IS Period | OOS Period | IS Winner | IS Sharpe | OOS Sharpe | OOS Baseline |")
            lines.append("|------|-----------|------------|-----------|-----------|------------|--------------|")
            for f in folds:
                warn = " *" if f.get("low_trade_warning") else ""
                lines.append(
                    f"| {f['fold']} | {f['is_period']} | {f['oos_period']} | "
                    f"{f['is_winner']} | {f['is_winner_sharpe']:.2f} | "
                    f"{f['oos_winner_sharpe']:.2f} | {f['oos_baseline_sharpe']:.2f}{warn} |"
                )
        lines.append("")
        lines.append("WFE >= 50% = genuine edge, 40-50% = caution, < 40% = overfit.")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 4
    lines.append("## Test 4: Year Exclusion")
    lines.append("")
    if year_excl:
        for excl in year_excl.get("exclusions", []):
            lines.append(f"### {excl['name']}")
            lines.append("")
            lines.append(f"Winner beats baseline in both periods: **{excl['winner_beats_both']}**")
            lines.append("")
            for period in excl.get("periods", []):
                lines.append(f"**{period['period']}** ({period['start']} -> {period['end']}):")
                for cfg in period.get("configs", []):
                    sharpe = (f"{cfg['metrics']['sharpe_ratio']:.2f}"
                              if cfg.get("metrics") else "N/A")
                    lines.append(f"- {cfg['name']}: Sharpe={sharpe}")
                lines.append("")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 5
    lines.append("## Test 5: Consistency Metrics")
    lines.append("")
    if consistency:
        for cfg_name, info in consistency.items():
            if cfg_name == "year_breakdown":
                continue
            lines.append(f"### {cfg_name}")
            lines.append("")
            lines.append(f"- Positive years: {info.get('positive_years', 'N/A')}/{info.get('total_years', 'N/A')}")
            lines.append(f"- Sharpe std: {info.get('sharpe_std', 'N/A')}")
            lines.append(f"- Worst year: {info.get('worst_year_return', 'N/A')}% "
                         f"(Sharpe {info.get('worst_year_sharpe', 'N/A')})")
            lines.append(f"- Gain-to-pain: {info.get('gain_to_pain', 'N/A')}")
            lines.append(f"- Recovery factor: {info.get('recovery_factor', 'N/A')}")
            lines.append(f"- MR PnL std: {info.get('mr_pnl_std', 'N/A')}")
            lines.append("")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 6
    lines.append("## Test 6: Regime-Specific Performance")
    lines.append("")
    if regime_perf:
        lines.append(f"- **VCP profitable years**: {regime_perf.get('vcp_positive_years', 'N/A')}/"
                     f"{regime_perf.get('total_years', 'N/A')} (need >= 8)")
        lines.append(f"- **MR profitable years**: {regime_perf.get('mr_positive_years', 'N/A')} (need >= 6)")
        lines.append("")
        for strategy in ["vcp_only", "mr_only", "mr_all_regimes_plus_vcp"]:
            info = regime_perf.get(strategy, {})
            m = info.get("metrics")
            if m:
                lines.append(f"**{strategy}**: Sharpe={m['sharpe_ratio']:.2f}, "
                             f"Return={m['total_return_pct']:.0f}%, "
                             f"MaxDD={m['max_drawdown_pct']:.1f}%")
            else:
                lines.append(f"**{strategy}**: N/A")
        lines.append("")
    else:
        lines.append("Not run.")
    lines.append("")

    # Test 7
    lines.append("## Test 7: Trade Count Validation")
    lines.append("")
    if trade_count and "error" not in trade_count:
        lines.append(f"- **Total trades**: {trade_count.get('total_trades', 'N/A')} "
                     f"(VCP: {trade_count.get('vcp_trades', 'N/A')}, "
                     f"MR: {trade_count.get('mr_trades', 'N/A')})")
        lines.append(f"- **Sharpe SE**: {trade_count.get('se_sharpe', 'N/A')}")
        lines.append(f"- **95% CI**: [{trade_count.get('ci_95_lower', 'N/A')}, "
                     f"{trade_count.get('ci_95_upper', 'N/A')}]")
        lines.append(f"- **Min trades/year**: {trade_count.get('min_trades_per_year', 'N/A')}")
        lines.append(f"- **Low-trade years**: {len(trade_count.get('low_trade_years', []))}")
    else:
        lines.append(f"Error: {trade_count.get('error', 'Not run') if trade_count else 'Not run'}")
    lines.append("")

    # Test 8
    lines.append("## Test 8: Survivorship Bias Estimate")
    lines.append("")
    if survivorship and "error" not in survivorship:
        lines.append(f"- **Stocks in DB**: {survivorship.get('total_stocks_in_db', 'N/A')}")
        lines.append(f"- **Entered after 2016**: {survivorship.get('entered_after_2016', 'N/A')}")
        lines.append(f"- **Ended before 2026**: {survivorship.get('ended_before_2026', 'N/A')}")
        lines.append(f"- **Est. survivorship**: {survivorship.get('estimated_survivorship_pct', 'N/A')}%")
        lines.append(f"- **Original Sharpe**: {survivorship.get('original_sharpe', 'N/A')}")
        lines.append(f"- **Adjusted Sharpe**: {survivorship.get('adjusted_sharpe', 'N/A')} "
                     f"(after {survivorship.get('assumed_annual_bias', 2)}% annual haircut)")
        lines.append(f"- **Sharpe reduction**: {survivorship.get('sharpe_reduction_pct', 'N/A')}%")
    else:
        lines.append(f"Error: {survivorship.get('error', 'Not run') if survivorship else 'Not run'}")
    lines.append("")

    # ---- Decision Framework ----

    lines.append("## Decision Framework")
    lines.append("")
    lines.append("### RSI Exit 75 (MR Change)")
    lines.append("")

    rsi75_decision = "UNDETERMINED"
    reasons = []

    if verdicts.get("1_dsr") == "FAIL":
        rsi75_decision = "REJECT"
        reasons.append("DSR < 0.50 — likely noise from 126+ trials")
    elif verdicts.get("2a_rsi") == "FAIL":
        rsi75_decision = "REJECT"
        reasons.append("RSI sensitivity shows a spike at 75 (fragile)")
    elif verdicts.get("3_wf") == "FAIL":
        rsi75_decision = "REJECT"
        reasons.append("Walk-forward: doesn't generalize to unseen data")
    elif verdicts.get("4_year_excl") == "FAIL":
        rsi75_decision = "REJECT"
        reasons.append("Year exclusion: improvement driven by single-year anomaly")
    elif all(v in ("PASS", "INFO", "CAUTION", "NOT RUN") for v in verdicts.values()):
        rsi75_decision = "ADOPT"
        reasons.append("All critical tests passed")
    else:
        rsi75_decision = "REVIEW"
        failed = [k for k, v in verdicts.items() if v == "FAIL"]
        reasons.append(f"Mixed results — failed tests: {', '.join(failed)}")

    lines.append(f"**Decision: {rsi75_decision}**")
    lines.append("")
    for r in reasons:
        lines.append(f"- {r}")
    lines.append("")

    lines.append("### System Robustness")
    lines.append("")
    wfe_val = wf.get("wfe_pct", 0) if wf else 0
    if wfe_val >= 50:
        lines.append("- WFE >= 50%: **System has genuine edge**")
    elif wfe_val >= 40:
        lines.append("- WFE 40-50%: **Proceed with caution, consider reducing parameters**")
    else:
        lines.append("- WFE < 40%: **System may be overfit, consider fundamental redesign**")

    if survivorship and "error" not in survivorship:
        reduction = survivorship.get("sharpe_reduction_pct", 0)
        if reduction > 50:
            lines.append(f"- Survivorship haircut ({reduction}%) > 50% of Sharpe: "
                         "**Results unreliable**")
        else:
            lines.append(f"- Survivorship haircut ({reduction}%) <= 50% of Sharpe: "
                         "**Acceptable**")
    lines.append("")

    # Final recommendation
    lines.append("## Final Recommendation")
    lines.append("")
    if rsi75_decision == "ADOPT":
        lines.append("**Keep RSI exit 75** — all overfitting tests passed. "
                     "The improvement is robust.")
    elif rsi75_decision == "REJECT":
        lines.append("**Revert to RSI exit 65** — the RSI 75 improvement "
                     "does not survive validation.")
        lines.append("")
        lines.append("Consider ADX<30 as an alternative (more theoretically grounded).")
    elif rsi75_decision == "REVIEW":
        lines.append("**Further investigation needed** — mixed results across tests.")
        lines.append("")
        lines.append("Review individual test details above to determine the best path forward.")
    else:
        lines.append("**Cannot determine** — not all tests have been run yet.")
    lines.append("")

    report_path = Path(__file__).resolve().parent / "OVERFITTING_REPORT.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSaved: {report_path}")


def cmd_all():
    """Run all tests sequentially."""
    t0 = time.time()
    cmd_quick_tests()
    cmd_sensitivity_rsi()
    cmd_sensitivity_sma()
    cmd_walk_forward()
    cmd_year_exclusion()
    cmd_analysis_only()
    cmd_report()
    print(f"\nTotal time: {(time.time()-t0)/60:.1f} min")


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(
        description="Overfitting Analysis — 8-test validation suite")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--quick-tests", action="store_true",
                       help="Tests 1 + 2c + 6 (~4 min)")
    group.add_argument("--sensitivity-rsi", action="store_true",
                       help="Test 2a: RSI exit 60-80 (~9 min)")
    group.add_argument("--sensitivity-sma", action="store_true",
                       help="Test 2b: SMA triplets (~4 min)")
    group.add_argument("--walk-forward", action="store_true",
                       help="Test 3: walk-forward (~17 min)")
    group.add_argument("--year-exclusion", action="store_true",
                       help="Test 4: skip 2023/2020 (~5 min)")
    group.add_argument("--analysis-only", action="store_true",
                       help="Tests 5+7+8: no backtests (<10s)")
    group.add_argument("--report", action="store_true",
                       help="Generate OVERFITTING_REPORT.md")
    group.add_argument("--all", action="store_true",
                       help="Run everything sequentially")

    args = parser.parse_args()

    if args.quick_tests:
        cmd_quick_tests()
    elif args.sensitivity_rsi:
        cmd_sensitivity_rsi()
    elif args.sensitivity_sma:
        cmd_sensitivity_sma()
    elif args.walk_forward:
        cmd_walk_forward()
    elif args.year_exclusion:
        cmd_year_exclusion()
    elif args.analysis_only:
        cmd_analysis_only()
    elif args.report:
        cmd_report()
    elif args.all:
        cmd_all()


if __name__ == "__main__":
    main()
