# MR Parameter Sweep — Progress

## Phase 0: Backtester Modifications
- [x] 0A: Add `_compute_adx()` helper
- [x] 0B: Extend `precompute_mr_indicators()` with 6 new columns
- [x] 0C: Add new config keys (require_adx, adx_max, rsi_mode, trend_filter)
- [x] 0D: Extend fast path entry logic (RSI modes, ADX, trend filter)
- [x] 0E: Handle stop_pct=None (no-stop mode) + guard exit logic
- [x] 0F: Extend slow path entry logic (mirror fast path)

## Phase 1: Sweep Script
- [x] Create `research/mr_backtest_harness.py`
- [x] Validate with --precompute (2240 stocks, 737MB pickle, 615s)
- [x] Validate with --baseline (3149.6% return, 24.8% DD, 1.61 Sharpe — EXACT MATCH)

## Phase 2: Individual Gap Sweeps
- [x] Gap 1: Stop loss (12 variants) — Winner: stop_5 (Sharpe 1.61)
- [x] Gap 2: ADX filter (5 variants) — Winner: ADX<30 (Sharpe 1.69, +5% vs baseline)
- [x] Gap 3: Cumulative RSI (3 variants) — Winner: single RSI(2)<5 (Sharpe 1.61)
- [x] Gap 4: RSI exit (6 variants) — Winner: RSI exit 75 (Sharpe 1.70, +6% vs baseline)
- [x] Gap 5: Trend filter (4 variants) — Winner: none (Sharpe 1.61)

## Phase 3: Combination Sweep
- [x] Generate combo_matrix.json (32 combos from top-2-per-gap)
- [x] Batch 1: combos 1-8
- [x] Batch 2: combos 9-16
- [x] Batch 3: combos 17-24
- [x] Batch 4: combos 25-32

## Phase 4: Analysis
- [x] Final ranking and report (FINAL_REPORT.md + PARAMETER_CHANGES.json)
