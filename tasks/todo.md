# Task Tracker

## Current Task
- [x] Mean Reversion Strategy — Deep Research & Understanding document
- [x] MR Parameter Sweep — backtester mods + 62-run sweep (30 individual + 32 combo)
- [x] Overfitting Analysis — 8-test validation suite (92 backtests)

## Overfitting Analysis Results

**Decision: REJECT RSI exit 75, reverted to 65**

| Test | Verdict | Key Finding |
|------|---------|-------------|
| 1. Deflated Sharpe | FAIL (DSR=0.36) | Winner Sharpe 1.70 < E[max]=1.82 from 63 trials |
| 2a. RSI Sensitivity | PASS (span=9) | Top 3 span 66-75, but noisy landscape |
| 2b. SMA Sensitivity | FAIL (57%) | 20/50/100 is 57% better than alternatives |
| 2c. Regime Thresholds | FAIL (diff=0.73) | System very sensitive to regime boundaries |
| 3. Walk-Forward | PASS (WFE=85.6%) | System generalizes, but rsi75 never wins IS |
| 4. Year Exclusion | FAIL | rsi75 loses to baseline in all sub-periods |
| 5. Consistency | INFO | baseline: Sharpe std 0.97, rsi75: 1.31 (less stable) |
| 6. Regime Perf | FAIL | VCP 7/11, MR 5/11 years profitable |
| 7. Trade Count | INFO | 626 trades, Sharpe 95% CI [1.55, 1.67] |
| 8. Survivorship | INFO | 0% delisted, Sharpe 1.61→1.53 after haircut |

**System-level**: WFE 85.6% = genuine edge. Survivorship haircut 4.8% = acceptable.
**Parameter-level**: RSI 75 is overfit (DSR, year-exclusion, walk-forward IS all reject it).

## Actions Taken
- [x] Reverted backtester rsi_exit from 75 back to 65
- [ ] Consider ADX<30 as future alternative (more theoretically grounded, won fold 2 IS)

## Pending Decisions
- [ ] Position ranking by HV(100) instead of z-score only
- [ ] Dashboard: show 200-SMA position, ADX value, R:R ratio, consecutive decline days
