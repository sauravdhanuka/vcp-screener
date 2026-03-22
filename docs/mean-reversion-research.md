# Mean Reversion Strategy: Deep Research & Understanding

## Context
This is a research document, not a code change plan. The goal is to fully understand the Mean Reversion (MR) strategy — the theory behind it, how our codebase implements it, how to visually identify setups, and most importantly, how to apply human judgment to pick the best candidates from the screener output.

---

## Part 1: What Is Mean Reversion?

**Core principle**: Asset prices tend to snap back toward their long-term average after deviating from it. Like arubber band —  the further it stretches, the harder it snaps back.

**Mathematical basis**: The Ornstein-Uhlenbeck process — a stochastic model combining:
- A deterministic drift pulling price toward a long-term mean
- Random fluctuations pushing it away

The key parameter is **theta** (rate of reversion). Higher theta = faster snap-back. Statisticians test for MR using the **Augmented Dickey-Fuller test** and **Hurst exponent** (H < 0.5 = mean-reverting).

**What "mean" does price revert to?**
- 20-day SMA (Bollinger Band midline) — fastest, used for short-term trades
- 50-day EMA — swing trade target
- 200-day SMA — long-term trend anchor
- VWAP — intraday mean

---

## Part 2: How Our Code Implements MR

### Entry Criteria (ALL 5 must be true)
File: `src/vcp_screener/services/screener.py` lines 366-469, function `get_mr_signals()`

| # | Condition | What It Means |
|---|-----------|---------------|
| 1 | Price < SMA(20) - 1.5 x StdDev(20) | Below the lower Bollinger Band — price is stretched |
| 2 | RSI(2) < 5 | Extremely oversold on 2-period RSI (Connors method) |
| 3 | IBS < 0.2 | Internal Bar Strength — closed near the day's low (panic close) |
| 4 | Volume > 1.5x 50-day avg | Panic selling volume — capitulation signal |
| 5 | Price >= Rs.50 | No penny stocks |

Candidates ranked by **z-score** (most negative = most oversold). Top 10 returned.

### Position Sizing
- **Risk per trade**: 1.5% of account (vs 2.5% for VCP — MR uses less because it's counter-trend)
- **Stop loss**: 5% below entry
- **Shares** = (1.5% of account) / (entry price - stop price)
- **Max simultaneous MR positions**: 3

### Exit Rules (checked in order)
File: `src/vcp_screener/services/backtester.py` lines 630-686

| Exit | Condition | Meaning |
|------|-----------|---------|
| Stop Loss | Price drops 5% from entry | Cut losses — the reversion thesis failed |
| RSI Exit | RSI(2) > 65 | Price has bounced into overbought — sell on strength |
| Target Hit | Price reaches SMA(10) | The "mean" has been reached — take profit |
| Timeout | 15 days held | If it hasn't reverted in 15 days, thesis is dead |

### Market Regime Activation
File: `src/vcp_screener/services/market_regime.py`

- **BULLISH** (breadth > 55%): VCP only. MR disabled.
- **CAUTIOUS** (35-55%): VCP with reduced size. MR disabled.
- **BEARISH** (< 35%): VCP disabled. **MR enabled.**

This is deliberate — MR was tested in CAUTIOUS regime and always made results worse.

### Best Backtest Results (from 35-combo sweep, 2016-2026)
Stop 5% + SMA10 target + RSI(2)<5 + IBS<0.2 → **3150% return, 24.8% max DD, 1.61 Sharpe, 1.74 profit factor** (with compounding)

### MR vs VCP — Key Differences

| Aspect | VCP | MR |
|--------|-----|-----|
| Market regime | BULLISH/CAUTIOUS | BEARISH only |
| Philosophy | Buy strength (breakout) | Buy weakness (bounce) |
| Entry timing | Wait for breakout confirmation | Immediate on criteria match |
| Risk/trade | 2.5% | 1.5% |
| Max positions | 5 (3 in drawdown) | 3 |
| Typical hold | Weeks to months | 2-10 days |
| Exit logic | Trailing stops, climax tops | RSI exit, SMA target, timeout |

---

## Part 3: The Theory — Why MR Works (and When It Doesn't)

### Why MR works in bear markets specifically:

1. **Bigger swings**: From May 2008 to March 2009, while S&P fell 50%, average up-days were +1.79%. Those violent counter-trend bounces are what MR captures.
2. **Short covering rallies**: Bears rush to cover profits, creating explosive snap-backs.
3. **Fear overshooting**: Panic selling pushes prices far below fair value.
4. **More signals**: Bear markets generate far more extreme oversold readings.

### How MR differs from "buying the dip":
- MR has **quantified entry criteria** (RSI < 5, BB touch, etc.) — not "it looks cheap"
- MR has **defined exit criteria** (RSI > 65, time-based at 15 days) — not "hold forever"
- MR is **short-duration** (2-10 days) — not a long-term investment thesis
- MR uses **position sizing** as risk control, not hope

### The stops paradox (critical insight from Connors/Alvarez research):
- Traditional stop losses are **counterproductive** for MR strategies
- "The more it goes against you, the better the signal"
- Research shows adding any stop loss damages MR performance
- Our code uses a 5% stop anyway — this is a practical compromise (protects capital in individual stock blowups at the cost of some edge)
- Risk is primarily controlled through **position sizing and max positions**, not stops

---

## Part 4: Proven Backtested Results

| Strategy | Win Rate | Avg Gain | CAGR | Max DD | Profit Factor |
|----------|---------|----------|------|--------|---------------|
| RSI(2)<5, exit at 5-SMA (SPY) | 75% | 0.5% | ~5% | ~25% | ~2.0 |
| Connors R3 (25 ETFs) | 75% | 0.68% | 6.47% | -16% | 2.08 |
| Connors R3 (SPY only) | **90%** | 1.28% | — | — | **7.17** |
| Cumulative RSI (stocks) | 65% | 1.0% | 26.6% | -37% | — |
| IBS (SPY) | 78% | 0.8% | — | — | — |
| **Our backtest (2016-2026)** | — | — | **3150% (compound)** | **-24.8%** | **1.74** |

Key researchers: **Larry Connors** (RSI-2 creator), **Cesar Alvarez** (Connors Research director), **QuantifiedStrategies.com**

---

## Part 5: Visual Identification — How to READ a MR Chart

### The 3-Phase Volume Pattern

**Phase 1 — Capitulation**: Massive volume spike (2-3x normal) with large red candles. Panic selling.

**Phase 2 — Exhaustion**: Volume drops dramatically over 3-7 sessions. Volume bars shrink below average. This is the MOST IMPORTANT signal — sellers are exhausted.

**Phase 3 — Reversal Confirmation**: Price turns up with increasing volume. Rising price + rising volume = real buying interest. If price bounces on low volume → suspect (dead cat bounce).

### Bollinger Bands — What to See

**Good MR setup**: Price touches or pierces the lower band → next candle closes back INSIDE the bands → reversal candlestick forms → target is the middle band (20-SMA).

**Danger signal**: Price "walks the lower band" — touching it repeatedly with expanding band width. This is a strong downtrend, NOT a MR setup. Skip.

### RSI Divergence — The Most Reliable Visual Signal

How to spot it:
1. On price chart: two consecutive swing lows where the second is LOWER
2. On RSI panel: at those same points, RSI makes a HIGHER low
3. Draw lines connecting both — they diverge

**Meaning**: Price is making new lows but momentum is weakening. Bears losing conviction.

**Warning**: Divergence can persist for weeks in strong trends. Never trade divergence alone — always require price confirmation (close above prior bar's high, close back inside BB).

### Reversal Candlestick Patterns (Only Valid at Extremes)

- **Hammer**: Small body, long lower wick (2x body), at the lower BB
- **Bullish Engulfing**: Large green candle swallows prior red candle
- **Morning Star**: Red candle → small body → large green candle
- **Doji at lows**: Open = close at bottom of decline = indecision/exhaustion

**Critical**: These patterns are ONLY meaningful at extreme levels (lower BB, RSI < 30). A hammer in the middle of a range means nothing.

---

## Part 6: The Human Touch — Picking the Best from the Screener

**This is the most important section.** Your screener gives you 10 MR candidates. Here's how to pick the best 3.

### Green Flags (Higher Conviction — Buy These First)

1. **Long-term uptrend intact**: Price is above the 200-day SMA or was recently. The stock pulled back WITHIN an uptrend. Connors' research: buying oversold above the 200-SMA produces far higher returns and much smaller losers.

2. **Clean prior support visible**: A clear horizontal level where price bounced before. The more times tested, the stronger.

3. **RSI divergence present**: Price making lower lows but RSI making higher lows.

4. **Volume exhaustion pattern**: Climactic spike → dry-up → small volume bars. Sellers are done.

5. **Sector holding up**: Other stocks in the same sector are stable or turning up. An oversold stock in a strong sector reverts faster.

6. **Reversal candle has CLOSED**: A hammer or engulfing at the lower BB, confirmed by candle close.

7. **Most negative z-score**: Our screener ranks by this — but combine it with the above visual checks.

### Red Flags (Disqualify These — Don't Touch)

1. **Below declining 200-SMA**: Price below 200-SMA AND the SMA is sloping down. This is Stage 4 decline. "Additional volatility and much bigger losers."

2. **Fundamental catalyst**: Earnings miss, debt crisis, regulatory action. The drop is a permanent repricing, not a temporary overshoot.

3. **Walking the lower band**: Price running along the lower BB for weeks with expanding bandwidth = strong downtrend, not MR.

4. **No volume climax**: Price slowly bleeding on average volume. No capitulation event. Selling may not be over.

5. **Entire sector collapsing**: Even strong stocks get dragged down further.

6. **ADX > 30 and rising**: Strong trend in force. MR works in range-bound markets (ADX < 30).

7. **Near earnings/events**: Upcoming results can overwhelm any technical signal.

### The 30-Second Visual Scan (Per Candidate)

1. **Zoom out to 1-year daily chart.** Overall trend up or flat? → If no, skip.
2. **Is price visibly stretched below moving averages?** → If no, skip.
3. **Reversal candle or RSI divergence forming?** → If no, deprioritize.
4. **Volume dried up after a spike?** → If yes, this goes to the TOP of your list.

---

## Part 7: Common Mistakes (What NOT to Do)

### Mistake 1: Catching the Falling Knife
"It's down 15%, it must bounce." → It drops another 20%.
**Fix**: ALWAYS wait for a reversal candle to CLOSE. Never buy into a red candle.

### Mistake 2: Confusing Dead Cat Bounce with Real Reversal
- Dead cat: 1-3 day bounce, low volume, RSI stays below 50, fails at prior swing high
- Real reversal: 5+ days, increasing volume, RSI breaks 50, higher low forms
**Rule**: If bounce < 3 bars and volume is thin → treat as dead cat.

### Mistake 3: Trading MR in a Strong Downtrend
Price below declining 200-SMA, ADX > 30, each bounce fails lower.
**Fix**: Check 200-SMA direction. Sloping down + price below = skip.

### Mistake 4: Ignoring Fundamentals
Stock is "oversold" but just reported 40% earnings miss. Price is repricing, not overshooting.
**Fix**: Spend 30 seconds checking WHY the stock fell. MR works for sentiment-driven drops, not fundamental repricing.

### Mistake 5: Premature Entry
You see a hammer forming mid-day and buy before candle closes. It closes as a long red candle.
**Fix**: Wait for candle CLOSE. Pattern is not confirmed until candle is complete.

### Mistake 6: Averaging Down Without a Plan
Trade goes against you, you buy more, it drops further, you buy more.
**Proper approach**: If scaling in, pre-plan: 25% at 2 SD, 25% at 2.5 SD, 25% at 3 SD. Pre-planned scaling with max size is fine. Emotional averaging is not.

---

## Part 8: Practical Workflow — Using This With Our Screener

### Daily Process (when market regime is BEARISH):

1. **Run `vcp screen signals`** → see MR candidates with z-scores
2. **Open each candidate's chart** (TradingView or dashboard stock detail)
3. **Apply the 30-second visual scan** (section 6 above)
4. **Check green/red flags** for surviving candidates
5. **Rank by conviction**: Best z-score + most green flags + fewest red flags
6. **Enter top 1-3** positions (max 3 MR positions per our config)
7. **Set alerts** at SMA(10) target and 5% stop
8. **Check daily**: RSI(2) > 65? SMA(10) reached? 15-day timeout approaching?

### What Our Screener Already Does Well:
- Automated 5-condition filtering (BB, RSI, IBS, volume, price floor)
- Z-score ranking (most oversold first)
- Position sizing with risk management
- Regime-aware activation (BEARISH only)

### What Requires Your Human Judgment:
- Is the long-term trend intact? (200-SMA check)
- Is there a fundamental reason for the drop?
- Is the reversal candle convincing?
- Is the sector holding up?
- Which 1-3 of the 10 candidates have the best visual setup?

---

## Part 9: Code Gaps — What Our Screener Is Missing vs Research Best Practices

### Gap 1: 200-SMA Trend Filter (MEDIUM priority)

**Code now**: `require_uptrend` exists in backtester (line 273, default `False`), checks `price > SMA(200)` at line 727. Not in `screener.py`'s `get_mr_signals()`.

**Research says**: This is the #1 safety filter. Connors uses it as step 1. Alvarez: "Trading below the 200-day moving average comes with additional volatility and much bigger losers."

**The contradiction**: In BEARISH regime (breadth < 35%), most stocks ARE below their 200-SMA. Enabling this filter kills nearly all candidates.

**Resolution**: The breadth-based regime filter already serves the same macro-level purpose. A per-stock **SMA(50)** filter could help avoid terminal declines without killing the strategy. Worth backtesting.

### Gap 2: ADX Filter (HIGH priority — most impactful missing filter)

**Code now**: No ADX calculation anywhere in the codebase.

**Research says**: Alvarez lists 10-day ADX as one of his two key additional filters. ADX < 25 = range-bound (MR works). ADX > 30 = strong trend (MR fails). One study: adding ADX<25 to a BB MR strategy turned a **-$7,000 loss into +$57,000 profit**.

**Why it matters in bear markets**: High-ADX stocks are the ones in freefall where "oversold" just means "on the way to more oversold." ADX prevents entering those.

### Gap 3: Cumulative RSI (HIGH priority — ~2x per-trade improvement)

**Code now**: Single-day RSI(2) < 5.

**Research says**: Cumulative RSI = sum of RSI(2) over N consecutive days. **2-day Cumulative RSI < 10**: ~280,000 events tested since 1998. Expected return **1.0% per trade (nearly 2x single-day RSI)**. Win rate 65%. Trade frequency halves but per-trade returns nearly double.

**Implementation**: `cumulative_rsi = rsi(close, 2).rolling(2).sum()` then `cumulative_rsi < 10`. Two lines of code.

### Gap 4: Stop Loss Too Tight (HIGH priority)

**Code now**: 5% stop loss (backtester.py line 262).

**Research says**: Alvarez tested stops from 5% to 50% and with no stop. **"The larger the stop, the better. Removing stops gave the best results."** Connors confirmed: every stop level from 1% to 50% reduced performance vs no stop. Alvarez's compromise: 50% stop (psychological only) + 8-day time stop.

**Your 5% stop is extremely tight** and will trigger frequently, accumulating losses on trades that would have reversed. This is the most well-documented finding in MR research.

**Recommendation**: Widen to 20-25%, or remove entirely and rely on time-based exit + position sizing.

### Gap 5: RSI Exit Threshold (MEDIUM priority)

**Code now**: Exit when RSI(2) > 65 (backtester.py line 264).

**Research says**: Connors' original uses 70. Exiting at 65 leaves ~10-15% of the bounce on the table.

**Recommendation**: Test 70. Your sweep may have already validated 65 for Indian markets.

### Gap 6: ConnorsRSI vs Plain RSI(2) — NO CHANGE NEEDED

Alvarez's own comparison: "RSI wins by a bit over ConnorsRSI." Profit factor: RSI(2) = 1.9, ConnorsRSI = 1.79. Skip.

### Gap 7: Position Ranking (MEDIUM priority)

**Code now**: Ranks by z-score only.

**Research says (Alvarez)**: Best rankings are **100-day Historical Volatility** (most volatile first — they bounce harder) and **Rate of Return over 3-5 days**. Z-score correlates with RoR but HV(100) ranking is meaningfully different.

### Gap 8: Dashboard Display (MEDIUM priority)

**Missing for human judgment**:
- 200-SMA position (is the stock in a long-term uptrend?)
- ADX value (is the stock trending or range-bound?)
- Reward/risk ratio (trivial to calculate)
- Consecutive decline days
- Volume exhaustion pattern indicator
- Mini sparkline chart

### Top 3 Changes by Expected Impact

| Rank | Change | Evidence | Effort |
|------|--------|----------|--------|
| 1 | **Widen stop from 5% to 20-25%** | Every MR researcher confirms stops hurt | Trivial |
| 2 | **Add ADX(10) < 25 filter** | Study: loss → profit with this one filter | Medium |
| 3 | **Add Cumulative RSI option** | ~2x per-trade returns, 280K events tested | Low |

---

## Part 10: Real Chart Examples — Learning from Indian Market Setups

### Example 1: TCS — Classic RSI Oversold Bounce (October 2024)

**Setup**: TCS was in an uptrend above 200-SMA at ~Rs 4,590. Fell ~8-10% to Rs 3,950-4,050 over 20 days during broad Nifty correction (FPI selling Rs 1 lakh crore). RSI(14) dropped below 30. Price pierced the lower BB.

**Entry signal**: After consolidating 2 weeks at Rs 3,950-4,050 (building a base, not new lows), a bullish engulfing candle at Rs 3,980. Price closed back inside BB. Volume declining = seller exhaustion. RSI showed mild bullish divergence.

**Target**: 20-SMA at Rs 4,250 = +6.8% gain. Stop below Rs 3,900 (2% risk) = 3:1 reward-risk.

**What you'd SEE**: Price slides down for 3 weeks. BB spread apart. Price stabs below lower band twice but closes back inside. RSI dips into oversold zone and curls up. Small-bodied candles (indecision), then a larger green candle swallows the prior red. Volume bars get shorter during the base. 200-SMA slopes upward well below price — confirming this is a pullback, not a trend change.

### Example 2: HDFC Bank — Textbook Bollinger Band MR (January 2024)

**Setup**: Gradual drift from Rs 1,750 to Rs 1,680 over 6 months after merger. Q3 results disappointed on NIM. Crashed **12% in one week** to Rs 1,430 — biggest drop since March 2020. Hit 52-week low. RSI(14) below 25. Price sliced through lower BB and closed below it for 2-3 sessions.

**Entry signal**: At Rs 1,430, a **hammer candle** — small body with long lower wick showing buyers stepping in. Price touched lower BB and closed back inside. Volume declined after initial panic = seller exhaustion. 200-SMA nearby acting as support. Fundamentally one of India's strongest banks.

**The trade**: Entry Rs 1,440-1,450. Target 20-SMA at Rs 1,600 = **+10.3% gain**. Stop below Rs 1,400 (3% risk) = ~3:1. Recovered to Rs 1,550+ within 2-3 weeks, Rs 1,700+ by mid-2024.

**What you'd SEE**: Gentle decline from upper-left over months, then sharp acceleration — big red candle on earnings day, then another. These breach the lower BB. Then a hammer: tiny green body at the top with long shadow extending down. BBs moderately wide. RSI dips below 30 and immediately curls up. Over 2-3 weeks, green candles drift back toward middle BB. **This is textbook MR.**

### Example 3: SPY (S&P 500) — COVID Crash, March 2020

**Setup**: S&P peaked at 3,386 on Feb 19. **34% decline in 23 trading days** to 2,237 on March 23. VIX hit 82.69 (highest ever). RSI(14) in the low teens. Price FAR below lower BB for over a week.

**Entry signal**: March 23 — Fed announced unlimited QE. March 24 — massive **+9.4% rally**, huge bullish engulfing candle. Price surged back inside BBs. RSI rocketed upward.

**The trade**: Entry ~$220. SPY hit $260 by April 9 (12 days) = **+16% gain**. S&P ultimately bounced 47% in 5 months.

**Critical lesson**: RSI(2) signal fired around March 12-13 at SPY ~$250, but price fell another 12% before bottoming. **The first oversold signal was a stop-out.** This is why Alvarez says stops hurt — a wide stop or no stop would have survived to capture the bounce.

**What you'd SEE**: Price cruises along then becomes near-vertical plunge. Almost all red candles. BBs explode outward. Then on March 24, one enormous green candle — taller than any red candle — marks the reversal. Like hitting a trampoline.

### Example 4: India Election Crash — June 4, 2024 (Event-Driven MR)

**Setup**: Nifty in strong uptrend. June 3: surged 3%+ on exit poll euphoria. June 4 — BJP won 240 seats vs expected 350-400. Sensex crashed **4,389 points**. Nifty plunged **5.93%** in one day. India VIX surged 23%. Individual stocks: HDFC Bank -3.5%, Reliance -6%, power/PSU stocks -6% to -15%.

**Entry signal**: June 5 — markets opened lower but recovered afternoon, up 1.5%+. Companies didn't become 6-15% less valuable overnight. Coalition formed within days.

**The trade**: Nifty recovered to 24,142 by July 1 (~10% from the low in under a month). Reliance rallied from Rs 2,800 to record Rs 3,218 by July 8 = **15% in 5 weeks**.

**Why this worked**: Event-driven emotional dislocation, not structural. Fundamentals unchanged. The "V-shaped" recovery is the hallmark of event-driven MR.

### Example 5: Paytm — FAILED MR Setup (Feb 2024) — What NOT to Buy

**Setup that LOOKED like MR**: RBI banned Paytm Payments Bank (Jan 31). Stock crashed 20% to Rs 609, then 10% more to Rs 438, then another 9% to Rs 395. **42% collapse in 3 sessions.** Every MR indicator screamed "buy" — RSI in single digits, price far below lower BB.

**Why this was NOT a valid MR trade**:
- **Below 200-SMA** (the #1 safety filter would have blocked this)
- **Fundamental destruction** — RBI effectively killed the core business
- No reversal candle — successive limit-down circuits
- "Walking the lower band" for weeks

**What happened to dip-buyers**:
- Bought at Rs 600 (after first 20% crash) → further **48% loss** to Rs 310
- Bought at Rs 440 (after second crash) → further **29% loss** to Rs 310

**What you'd SEE**: Massive gap-down candles with opens far below prior closes. BBs explode wider but price is FAR below them — daylight between candles and the band. RSI glued to floor below 10 for days. No green candles. Enormous red volume bars. 200-SMA FAR above, sloping downward. **This is a broken stock, not a pullback.**

### Example 6: Adani Enterprises — Walking the Lower Band (Jan-Feb 2023)

**Setup**: Parabolic uptrend (300% in 2022). Hindenburg report published Jan 24. **70% collapse** over 10 days to Rs 1,017. Lost $118 billion in market value.

**The MR trap timeline**:
- Day 1-2 (Jan 25-26): Down 15%. RSI below 30. "Buy!" → Stock has 55% more to fall.
- Day 3-4 (Jan 30): Down 35%. RSI below 20. "Surely the bottom" → 35% more to fall.
- Day 7 (Feb 2): Down 55%. Every indicator at most extreme ever. "HAS to bounce" → Falls another 15%.

**What you'd SEE**: Near-vertical uptrend followed by near-vertical decline (mirror image). Each day is a long red candle with gaps down. Lower BB being dragged down but price always far below it. RSI stuck to bottom rail. No green candles for 8-10 days. **A waterfall.**

**Recovery took 15 months.** An MR trader buying at Rs 2,500 (after "only" 30% decline) watched a further 60% loss.

### Example 7: Nifty 50 October-November 2024 — Premature Entry Warning

**Setup**: Nifty fell from ATH 26,277 (Sep 27) to 23,263 by Nov 28 = **11.5% correction**. RSI hit 28.60 on Oct 25 — deeply oversold.

**The trap**: A trader buying at 24,200 (Oct 31) targeting 20-SMA at 24,800 looked reasonable. BUT Nifty made a LOWER LOW at 23,263 on Nov 28. The first oversold signal was premature.

**What you'd SEE**: The 20-SMA and 50-SMA cross bearishly. Price stabs below lower BB, attempts a small bounce (2-3 green candles), then FAILS and drops even further. RSI deep in oversold zone — "it must bounce" — but it goes lower. Eventually finds support at the rising 200-SMA.

**Lesson**: Even with RSI at 28, a broad correction can get more oversold. The 200-SMA was the critical eventual support, not the first oversold reading.

---

## Quick Reference: Success vs Failure Patterns

| Factor | Successful MR | Failed / Trap |
|--------|--------------|---------------|
| Price vs 200-SMA | Above or near it | Far below, SMA sloping down |
| Nature of decline | Pullback in uptrend, or event shock | Trend breakdown, fundamental destruction |
| RSI behavior | Dips below 30, curls up within 1-5 days | Stays pinned below 20 for 5+ days |
| Bollinger Band | Pierces lower band then closes back inside | Stays FAR below band ("walking") |
| Volume pattern | Selling volume decreases at the low | Selling volume stays high or increases |
| Reversal candle | Hammer, engulfing, or doji at support | No reversal pattern, just more red candles |
| Catalyst type | Emotional/event-driven (election, broad sell-off) | Fundamental destruction (RBI ban, fraud) |

---

## Part 11: Entry & Exit Timing (Research Findings)

### Entry Timing: Close of Signal Day

**Connors' method**: Enter at the **close** of the day all criteria are met. Not the next morning open.

**Why close, not next open**: In bear markets, stocks often gap DOWN at open after oversold closes. Buying at close captures the signal; buying at next open risks paying more if there's a relief gap, or a worse entry if the gap is down and you're already committed.

**For NSE**: Place the order in the last 15 minutes of trading (3:15-3:30 PM IST) once you've confirmed the candle will close meeting criteria.

### Exit Timing: Sell on Strength

**Connors' original**: Exit when price closes above the 5-day SMA. This is the fastest exit.

**Our code**: Uses RSI(2) > 65 OR SMA(10) target OR 15-day timeout. This is more conservative — holds longer for bigger moves but also more exposure.

**Alvarez's key finding**: Time-based exits (7-10 days) are his preferred alternative to indicator exits. Most MR bounces complete within **3-7 trading days**. After 10+ days, probability of success drops.

### The Stops Question

**Research consensus** (Connors, Alvarez, QuantifiedStrategies — all independently confirmed):
- Stops **damage** MR performance at every tested level (1% to 50%)
- Best results = no stop + time-based exit
- Acceptable compromise: very wide stop (20-25%) + 8-10 day timeout
- Our 5% stop is **too tight** — it will frequently trigger on trades that would have reversed

### Scaling In

Alvarez tested entering 25/50/75% of position on initial signal and adding on further weakness. Result: **"Large drop in CAR with either no change or large increase in MDD."** Scaling out also doesn't work. **Enter full position at signal.**

---

## Key References
- **Larry Connors**: Creator of RSI(2), author of "Short-Term Trading Strategies That Work"
- **Cesar Alvarez**: alvarezquanttrading.com — gold standard for MR research
- **QuantifiedStrategies.com**: Modern backtests of Connors-style strategies
- **John Bollinger**: Original Bollinger Bands methodology
- **Key sources**: StockCharts ChartSchool, Business Standard, CNBC, LuxAlgo, TrendSpider, Macro Ops, Interactive Brokers Campus
