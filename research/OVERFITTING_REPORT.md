# Overfitting Analysis Report

Generated: 2026-03-19

## Summary

| # | Test | Verdict |
|---|------|---------|
| 1 | Deflated Sharpe Ratio (DSR=0.3594) | **FAIL** |
| 2a | RSI Exit Sensitivity (span=9) | **PASS** |
| 2b | SMA Period Sensitivity (imp=56.99%) | **FAIL** |
| 2c | Regime Threshold Sensitivity | **FAIL** |
| 3 | Walk-Forward Analysis (WFE=85.65%) | **PASS** |
| 4 | Year Exclusion | **FAIL** |
| 5 | Consistency Metrics | **INFO** |
| 6 | Regime-Specific Performance | **FAIL** |
| 7 | Trade Count Validation | **INFO** |
| 8 | Survivorship Bias Estimate | **INFO** |

## Test 1: Deflated Sharpe Ratio

- **DSR**: 0.3594
- **Winner Sharpe**: 1.7
- **E[max(SR)]**: 1.8165
- **Trials**: 63
- **Observations**: 2449
- **Skewness**: -0.0841
- **Excess Kurtosis**: 3.7699

DSR >= 0.95 = robust, DSR < 0.50 = likely noise from multiple testing.

## Test 2a: RSI Exit Sensitivity

- **Top 3**: RSI 75 (Sharpe 1.70), RSI 66 (Sharpe 1.63), RSI 68 (Sharpe 1.63)
- **RSI span**: 9 (need >= 5 for plateau)

| RSI Exit | Sharpe |
|----------|--------|
| 60 | 1.58 |
| 61 | 1.30 |
| 62 | 1.33 |
| 63 | 1.50 |
| 64 | 1.47 |
| 65 | 1.61 |
| 66 | 1.63 |
| 67 | 1.50 |
| 68 | 1.63 |
| 69 | 1.60 |
| 70 | 1.35 |
| 71 | 1.58 |
| 72 | 1.07 |
| 73 | 1.55 |
| 74 | 1.63 |
| 75 | 1.70 |
| 76 | 1.39 |
| 77 | 1.46 |
| 78 | 1.45 |
| 79 | 1.60 |
| 80 | 1.58 |

## Test 2b: SMA Period Sensitivity

- **Current (20/50/100) avg Sharpe**: 1.6667
- **Alternative avg Sharpe**: 1.0617
- **Improvement**: 56.99% (need <30%)

| SMA Triplet | MR Config | Sharpe |
|-------------|-----------|--------|
| 20/50/100 | baseline | 1.61 |
| 20/50/100 | rsi75 | 1.70 |
| 20/50/100 | adx30 | 1.69 |
| 50/150/200 | baseline | 1.09 |
| 50/150/200 | rsi75 | 0.81 |
| 50/150/200 | adx30 | 1.20 |
| 30/80/150 | baseline | 1.24 |
| 30/80/150 | rsi75 | 0.99 |
| 30/80/150 | adx30 | 1.04 |

## Test 2c: Regime Threshold Sensitivity

- **baseline**: Sharpe range 0.88-1.61, diff=0.73 -> FAIL
- **rsi75**: Sharpe range 1.00-1.70, diff=0.70 -> FAIL

## Test 3: Walk-Forward Analysis

- **WFE**: 85.65%
- **Mean IS Sharpe**: 1.7
- **Mean OOS Sharpe**: 1.456
- **Unique IS winners**: 4/5
- **Low-trade OOS folds**: 0

| Fold | IS Period | OOS Period | IS Winner | IS Sharpe | OOS Sharpe | OOS Baseline |
|------|-----------|------------|-----------|-----------|------------|--------------|
| 1 | 2016-04-01->2021-03-31 | 2021-04-01->2022-03-31 | rsi70 | 1.52 | 1.97 | 1.97 |
| 2 | 2017-04-01->2022-03-31 | 2022-04-01->2023-03-31 | adx30 | 1.59 | -0.07 | -0.20 |
| 3 | 2018-04-01->2023-03-31 | 2023-04-01->2024-03-31 | rsi65 | 1.62 | 2.62 | 2.62 |
| 4 | 2019-04-01->2024-03-31 | 2024-04-01->2025-03-31 | rsi60 | 1.83 | 1.05 | 1.41 |
| 5 | 2020-04-01->2025-03-31 | 2025-04-01->2026-03-01 | rsi65 | 1.94 | 1.71 | 1.71 |

WFE >= 50% = genuine edge, 40-50% = caution, < 40% = overfit.

## Test 4: Year Exclusion

### skip_2023

Winner beats baseline in both periods: **False**

**pre_2023** (2016-04-01 -> 2022-12-31):
- baseline: Sharpe=1.54
- rsi75: Sharpe=1.43
- adx30: Sharpe=1.58

**post_2023** (2024-01-01 -> 2026-03-01):
- baseline: Sharpe=0.90
- rsi75: Sharpe=0.79
- adx30: Sharpe=0.84

### skip_2020

Winner beats baseline in both periods: **False**

**pre_2020** (2016-04-01 -> 2019-12-31):
- baseline: Sharpe=1.11
- rsi75: Sharpe=1.07
- adx30: Sharpe=1.31

**post_2020** (2021-01-01 -> 2026-03-01):
- baseline: Sharpe=1.63
- rsi75: Sharpe=1.39
- adx30: Sharpe=1.61


## Test 5: Consistency Metrics

### baseline

- Positive years: 9/11
- Sharpe std: 0.9723
- Worst year: -1.14% (Sharpe -0.01)
- Gain-to-pain: 288.4
- Recovery factor: 126.95
- MR PnL std: 556667.28

### rsi75

- Positive years: 10/11
- Sharpe std: 1.313
- Worst year: -4.89% (Sharpe -1.25)
- Gain-to-pain: 105.28
- Recovery factor: 162.27
- MR PnL std: 908611.93

### adx30

- Positive years: 10/11
- Sharpe std: 1.3164
- Worst year: -5.19% (Sharpe -2.1)
- Gain-to-pain: 89.12
- Recovery factor: 137.32
- MR PnL std: 890996.16


## Test 6: Regime-Specific Performance

- **VCP profitable years**: 7/11 (need >= 8)
- **MR profitable years**: 5 (need >= 6)

**vcp_only**: Sharpe=1.21, Return=921%, MaxDD=30.4%
**mr_only**: Sharpe=0.18, Return=17%, MaxDD=45.5%
**mr_all_regimes_plus_vcp**: Sharpe=1.00, Return=666%, MaxDD=29.6%


## Test 7: Trade Count Validation

- **Total trades**: 626 (VCP: 373, MR: 253)
- **Sharpe SE**: 0.0302
- **95% CI**: [1.5508, 1.6692]
- **Min trades/year**: 18
- **Low-trade years**: 2

## Test 8: Survivorship Bias Estimate

- **Stocks in DB**: 2240
- **Entered after 2016**: 1094
- **Ended before 2026**: 0
- **Est. survivorship**: 0.0%
- **Original Sharpe**: 1.61
- **Adjusted Sharpe**: 1.53 (after 2.0% annual haircut)
- **Sharpe reduction**: 4.8%

## Decision Framework

### RSI Exit 75 (MR Change)

**Decision: REJECT**

- DSR < 0.50 — likely noise from 126+ trials

### System Robustness

- WFE >= 50%: **System has genuine edge**
- Survivorship haircut (4.8%) <= 50% of Sharpe: **Acceptable**

## Final Recommendation

**Revert to RSI exit 65** — the RSI 75 improvement does not survive validation.

Consider ADX<30 as an alternative (more theoretically grounded).
