# Comprehensive Overfitting Analysis — VCP + MR Strategies

## Context

Our trading system has **97 parameters** across VCP breakout and MR mean reversion strategies, optimized on 10 years of Indian stock data (2016-2026, 2240 NSE stocks). We ran 126+ parameter sweeps. The codebase audit reveals:

- **MR strategy**: Backtest Sharpe 1.70, but 2026 YTD Sharpe -1.25 (classic overfitting signal)
- **VCP strategy**: Uses modified Minervini template (SMA 20/50/100 instead of 50/150/200) — unvalidated adaptation
- **Regime switching**: MR only in BEARISH (breadth < 35%) — regime-dependent, untested at boundaries
- **No OOS validation**: All 126+ sweeps on the same 10-year dataset
- **Survivorship bias**: Only current NSE stocks — delisted stocks excluded (1-4% annual overstatement)
- **126+ trials on 10Y data**: Bailey et al. threshold is ~90 trials for 10 years — we exceed this

## What We're Building

**Script**: `research/overfitting_analysis.py` — 8 tests covering both strategies, producing `research/OVERFITTING_REPORT.md`

---

## Test Suite (8 Tests)

### Test 1: Deflated Sharpe Ratio (`--deflated-sharpe`) — PRIORITY 1

**Covers**: Entire system (VCP + MR combined)
**Question**: Given 126+ configs tested, is our best Sharpe just the expected maximum of random draws?
**Method**: Bailey & Lopez de Prado (2014) DSR formula
- Load all config Sharpe ratios from existing sweep JSONs + the prior 35-combo sweep
- Run winner backtest to get daily returns (for skewness, kurtosis)
- Compute: `DSR = Φ[(SR_hat - E[max(SR)]) × √(T-1) / √(1 - γ₃×SR + (γ₄-1)/4 × SR²)]`
- E[max(SR)] uses Euler-Mascheroni approximation for N trials
**Pass**: DSR ≥ 0.95 = robust. DSR < 0.50 = likely noise.
**Runs**: 1 backtest + math. ~30s.

### Test 2: Parameter Sensitivity — Fine-Grained (`--sensitivity`)

**Covers**: MR strategy (RSI exit parameter) + VCP (SMA periods)
**Question**: Are our key parameters on plateaus or fragile spikes?

**2a. RSI Exit (MR)**: 21 backtests — RSI exit 60 to 80 in steps of 1
- Pass: Top-3 Sharpe values span ≥5 points (plateau). Fail: only 75 ±1 works (spike).

**2b. VCP SMA Periods**: 9 backtests testing 3 SMA triplets:
- Current: 20/50/100 (Indian adaptation)
- Original Minervini: 50/150/200
- Middle ground: 30/80/150
- Pass: current SMA triplet isn't dramatically better than alternatives. Fail: only 20/50/100 works.

**2c. Regime Thresholds**: 6 backtests testing breadth thresholds:
- Current: BEAR < 35%, BULL > 55%
- Alt 1: BEAR < 30%, BULL > 50%
- Alt 2: BEAR < 40%, BULL > 60%
- Pass: results stable across ±5% threshold shifts.

**Total runs**: 36 × ~25s = ~15 min

### Test 3: Walk-Forward Analysis (`--walk-forward`)

**Covers**: Both VCP and MR (full system)
**Question**: Does the system's performance generalize to unseen future data?
**Method**: 5 rolling folds with 5-year IS, 1-year OOS:

| Fold | In-Sample | Out-of-Sample |
|------|-----------|---------------|
| 1 | 2016-04 → 2021-03 | 2021-04 → 2022-03 |
| 2 | 2017-04 → 2022-03 | 2022-04 → 2023-03 |
| 3 | 2018-04 → 2023-03 | 2023-04 → 2024-03 |
| 4 | 2019-04 → 2024-03 | 2024-04 → 2025-03 |
| 5 | 2020-04 → 2025-03 | 2025-04 → 2026-03 |

Per fold: test 6 MR configs (RSI exit 60/65/70/75/80 + ADX<30) in IS. Pick IS winner. Run IS winner + baseline on OOS.

**Compute Walk-Forward Efficiency**: `WFE = Mean OOS Sharpe / Mean IS Sharpe`
- Pass: WFE ≥ 50%. Caution: WFE 40-50%. Fail: WFE < 40%.
- Also check: does the IS winner change wildly between folds? (stability)
- Flag folds with < 5 MR trades in OOS (regime didn't activate)

**Runs**: 40 × ~25s = ~17 min

### Test 4: Year-Exclusion / Anomaly Removal (`--year-exclusion`)

**Covers**: MR strategy primarily (2023 anomaly)
**Question**: Is the RSI-75 improvement driven by a single outlier year?
**Method**: Run 3 configs on sub-periods that skip 2023:
- Period A: 2016-04 → 2022-12 (pre-anomaly)
- Period B: 2024-01 → 2026-03 (post-anomaly)
- Configs: baseline (RSI exit 65), winner (RSI exit 75), ADX<30

Also run an "exclude 2020" test (COVID year — another anomaly):
- Period A: 2016-04 → 2019-12
- Period B: 2021-01 → 2026-03

**Pass**: Winner beats baseline in BOTH sub-periods for BOTH exclusion tests.
**Runs**: 3 configs × 4 sub-periods = 12 × ~25s = ~5 min

### Test 5: Consistency Metrics (`--consistency`)

**Covers**: Both VCP and MR
**Question**: Which configuration is most stable year-over-year?
**Method**: Pure computation from existing year_breakdown JSON data. For baseline, RSI-75, and ADX<30:
1. **Year-win-rate**: How many of 11 years does config beat baseline?
2. **Sharpe consistency**: Std dev of per-year Sharpes (lower = more stable)
3. **Worst-year return and Sharpe**
4. **Gain-to-pain ratio**: Sum(positive returns) / Sum(|negative returns|)
5. **Recovery factor**: Total return / MaxDD
6. **Positive year count**
7. **MR contribution consistency**: Std dev of per-year MR PnL

**Runs**: 0 backtests, pure math from existing JSONs. < 1s.

### Test 6: Regime-Specific Performance (`--regime`)

**Covers**: Both strategies — tests regime-dependency
**Question**: Does each strategy work across regimes, or only in its designated one?
**Method**:
- Run VCP-only backtest (MR disabled) across full 10Y — does VCP make money in bear years?
- Run MR-only backtest (VCP disabled) across full 10Y — does MR make money in bull years?
- Run MR with `all_regimes=True` — what happens when MR trades in all regimes?
- Segment existing results by regime (BULL/CAUTIOUS/BEARISH years) and compute per-regime Sharpe

**Pass**: VCP profitable in ≥ 8/11 years. MR profitable in ≥ 6/11 years. Neither strategy has catastrophic losses outside its regime.
**Runs**: 3 backtests × ~25s = ~1.5 min + analysis

### Test 7: Trade Count Validation (`--trade-count`)

**Covers**: Both strategies
**Question**: Do we have enough trades for statistical significance?
**Method**: From existing results:
- Total trades: 626 (✓ > 200 threshold)
- MR trades: 253 (✓ > 200)
- VCP trades: ~373 (✓ > 200)
- Per-year minimum: flag years with < 30 trades
- Per-regime minimum: flag regimes with < 50 trades
- Compute: standard error of Sharpe = `√((1 + 0.5×SR²) / T)` — how tight is our confidence interval?

**Runs**: 0 backtests, pure analysis. < 1s.

### Test 8: Survivorship Bias Estimate (`--survivorship`)

**Covers**: Entire system
**Question**: How much are our results inflated by excluding delisted stocks?
**Method**: We can't get delisted stock data from yfinance, but we CAN:
1. Count stocks in our DB that have data starting after 2016 (newly listed — survivorship in reverse)
2. Count stocks whose data ends before 2026 (possibly delisted)
3. Estimate bias using Kohli et al. research: 1-4% annual overstatement for Indian markets
4. Apply a **survivorship haircut** to our Sharpe/return numbers
5. Report: "After estimated survivorship bias correction, Sharpe drops from X to Y"

**Runs**: 1 DB query + math. < 10s.

---

## Parallel Execution Strategy

The 92 backtests are split across **5 named subagents** running in parallel, plus a sequential analysis phase. Each subagent loads the pickle independently (~2s, ~737MB each, ~3.7GB peak RAM total).

### Phase A: Parallel Backtests (5 subagents)

```
[PARALLEL] 5 named subagents, each runs one CLI command:

subagent "sensitivity-rsi"    → --sensitivity-rsi     (21 runs, ~9 min)
subagent "sensitivity-sma"    → --sensitivity-sma     (9 runs, ~4 min)
subagent "walk-forward"       → --walk-forward        (40 runs, ~17 min)  ← bottleneck
subagent "year-exclusion"     → --year-exclusion      (12 runs, ~5 min)
subagent "quick-tests"        → --quick-tests         (10 runs, ~4 min)
                                                       Tests 1 (DSR) + 2c (regime thresh) + 6 (regime perf)
```

**Wall-clock**: ~17 min (limited by walk-forward, the longest single test)

### Phase B: Analysis-Only (no backtests, sequential)

```
[SEQUENTIAL] After Phase A completes:

python research/overfitting_analysis.py --analysis-only    (Tests 5, 7, 8 — reads existing JSONs, < 10s)
```

### Phase C: Report Generation

```
[SEQUENTIAL] After Phase B:

python research/overfitting_analysis.py --report           (Merges all results → OVERFITTING_REPORT.md)
```

### Total Time: ~18 min parallel vs ~39 min sequential

---

## Script CLI

```bash
# Phase A — run via 5 parallel subagents
python research/overfitting_analysis.py --sensitivity-rsi    # Test 2a: RSI exit 60-80 (21 runs)
python research/overfitting_analysis.py --sensitivity-sma    # Test 2b: SMA triplets (9 runs)
python research/overfitting_analysis.py --walk-forward       # Test 3: 5-fold rolling OOS (40 runs)
python research/overfitting_analysis.py --year-exclusion     # Test 4: skip 2023 + skip 2020 (12 runs)
python research/overfitting_analysis.py --quick-tests        # Tests 1 + 2c + 6 combined (10 runs)

# Phase B — sequential, instant (reads Phase A outputs)
python research/overfitting_analysis.py --analysis-only      # Tests 5, 7, 8 (no backtests)

# Phase C — merge and report
python research/overfitting_analysis.py --report             # → OVERFITTING_REPORT.md

# Or run everything sequentially with one pickle load:
python research/overfitting_analysis.py --all
```

---

## Decision Framework

After all tests, the report applies this decision tree:

**For RSI exit 75 (MR change)**:
1. DSR < 0.50 → **REJECT** (likely noise from 126+ trials)
2. Sensitivity: spike at exactly 75 → **REJECT** (fragile)
3. Walk-forward: OOS Sharpe < baseline OOS Sharpe → **REJECT** (doesn't generalize)
4. Year-exclusion: loses to baseline without 2023 → **REJECT** (single-year anomaly)
5. All pass → **ADOPT**

**For overall system robustness**:
1. WFE < 40% → System is overfit, needs fundamental redesign
2. WFE 40-50% → Proceed with caution, reduce parameter count
3. WFE ≥ 50% → System has genuine edge
4. Regime test: strategy profitable only in designated regime → Flag as fragile
5. Survivorship haircut > 50% of Sharpe → Results unreliable

**Final recommendation** will be one of:
- Keep RSI exit 75 (all MR tests pass)
- Revert to RSI exit 65 (MR tests fail, but system is robust)
- Adopt ADX<30 instead (more theoretically grounded, passes more tests)
- Reduce parameters / simplify system (if WFE < 40%)

---

## Time Budget

| Subagent | Tests | Runs | Sequential Time | Parallel Group |
|----------|-------|------|----------------|----------------|
| `sensitivity-rsi` | 2a | 21 | ~9 min | A |
| `sensitivity-sma` | 2b | 9 | ~4 min | A |
| `walk-forward` | 3 | 40 | ~17 min | A (bottleneck) |
| `year-exclusion` | 4 | 12 | ~5 min | A |
| `quick-tests` | 1 + 2c + 6 | 10 | ~4 min | A |
| `analysis-only` | 5, 7, 8 | 0 | < 10s | B (after A) |
| `report` | — | 0 | < 5s | C (after B) |
| **Total** | **8 tests** | **92** | **~39 min seq / ~18 min parallel** | |

---

## Output Files

```
research/
  overfitting_analysis.py            # New: the analysis script
  overfitplan.md                     # This plan
  results/
    overfit_deflated_sharpe.json     # Test 1
    overfit_sensitivity.json         # Test 2 (RSI + SMA + regime thresholds)
    overfit_walkforward.json         # Test 3
    overfit_year_exclusion.json      # Test 4
    overfit_consistency.json         # Test 5
    overfit_regime.json              # Test 6
    overfit_trade_count.json         # Test 7
    overfit_survivorship.json        # Test 8
  OVERFITTING_REPORT.md             # Final report with verdicts
```

## Files to Modify

| File | Change |
|------|--------|
| `research/overfitting_analysis.py` | **New** — 8-test analysis script |
| `research/overfitplan.md` | **New** — this plan |
| `src/vcp_screener/services/backtester.py` | May **revert** rsi_exit 75→65 depending on results |

## Verification

1. Run `--all` end-to-end (~39 min)
2. Check each JSON has valid data (non-empty, no errors)
3. Report has clear PASS/FAIL for each test
4. Final recommendation is unambiguous
5. If RSI-75 fails: revert the backtester change
