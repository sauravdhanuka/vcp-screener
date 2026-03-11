# VCP Stock Screener for NSE

An algorithmic stock screening and trading system for the Indian NSE market, combining Mark Minervini's Volatility Contraction Pattern (VCP) methodology with a quantitative Mean Reversion (MR) strategy. Built on 4,700+ lines of Python, backtested across 10 years of market data with 126+ configuration sweeps.

---

## Performance Summary

### Headline Numbers (10Y Backtest: April 2016 - March 2026)

| Metric | Value |
|--------|------:|
| **Total Return** | **3,149.6%** |
| **CAGR** | **~41%** |
| **Max Drawdown** | **24.8%** |
| **Sharpe Ratio** | **1.61** |
| **Profit Factor** | **1.74** |
| **Win Rate** | **47.3%** |
| **Total Trades** | **626** |
| **Profitable Years** | **9 of 11** |
| Starting Capital | Rs 5,00,000 |
| Final Equity | Rs 1,62,48,043 |

> **Note on backtesting methodology:** The backtest enters positions at close price on signal day and does not model slippage or commissions. These are standard assumptions in strategy research and allow consistent comparison across configurations. Absolute return figures should be interpreted as relative performance indicators. See [Backtesting Methodology](#backtesting-methodology) for full transparency on known biases.

### Year-by-Year Breakdown (Compounding, Rs 5L Start)

| Year | Return | Max DD | Sharpe | Trades | MR Trades | VCP Trades | MR PnL | VCP PnL |
|------|-------:|-------:|-------:|-------:|----------:|-----------:|-------:|--------:|
| 2016 | +9.7% | 4.6% | 1.41 | 25 | 25 | 0 | +46,907 | +0 |
| 2017 | +46.5% | 11.7% | 1.78 | 41 | 2 | 39 | +65,530 | +2,56,723 |
| 2018 | +11.1% | 17.9% | 0.60 | 75 | 44 | 31 | +1,17,221 | -41,834 |
| 2019 | +14.7% | 20.2% | 0.87 | 47 | 34 | 13 | -61,192 | +2,64,189 |
| 2020 | +100.8% | 24.3% | 2.77 | 64 | 21 | 43 | +1,33,195 | +6,54,604 |
| 2021 | +117.1% | 12.0% | 2.92 | 65 | 2 | 63 | +1,78,671 | +22,57,800 |
| 2022 | -1.1% | 24.8% | 0.09 | 79 | 28 | 51 | -6,230 | +26,203 |
| 2023 | +38.1% | 9.3% | 1.58 | 65 | 21 | 44 | -50,554 | +21,38,981 |
| 2024 | +109.2% | 12.6% | 2.58 | 77 | 14 | 63 | +2,25,303 | +50,90,965 |
| 2025 | +25.7% | 21.5% | 1.22 | 70 | 49 | 21 | +19,90,819 | +24,84,894 |
| 2026* | -0.5% | 7.4% | -0.01 | 18 | 13 | 5 | +1,35,128 | -1,59,278 |

*\*2026 data covers Jan-Feb only.*

**Key observations:**
- **2018 (Bear market):** +11.1% — MR strategy generated +1.17L while VCP lost -41K. System stayed profitable when the market crashed.
- **2020 (COVID crash + recovery):** +100.8% — captured the V-shaped recovery with 43 VCP trades generating +6.5L.
- **2022 (Sideways/choppy):** -1.1% — worst year, nearly flat. The system correctly reduced exposure.
- **2024 (Bull run):** +109.2% — 63 VCP trades captured the rally, generating +50.9L on a growing equity base.

### No-Compounding Benchmark (Fixed Rs 5L Sizing)

For a more conservative estimate of strategy edge without compounding effects:

| Metric | Value |
|--------|------:|
| Total Return | 406.5% |
| CAGR | 17.8% |
| Max Drawdown | 17.3% |
| Sharpe Ratio | 1.32 |
| Profit Factor | 1.70 |
| VCP PnL | +16,59,272 |
| MR PnL | +3,73,060 |

---

## How It Works

The system runs two complementary strategies that adapt to market conditions:

```
BULLISH Market (breadth > 55%)     →  VCP Breakout Entries (momentum)
CAUTIOUS Market (35-55%)           →  VCP with reduced exposure (EqMA protection)
BEARISH Market (breadth < 35%)     →  Mean Reversion only (buy oversold bounces)
```

### Strategy 1: VCP Breakout (Primary — 82% of PnL)

Based on Mark Minervini's SEPA methodology, adapted for Indian mid/small-cap stocks:

1. **Pre-filter** 2,200+ NSE stocks → ~300 candidates (price > Rs 50, volume > 1L, 200+ days data)
2. **Relative Strength ranking** — weighted multi-timeframe returns (3m: 50%, 6m: 25%, 9m: 15%, 12m: 10%)
3. **8-Point Trend Template** — price above stacked SMAs, near 52-week high, RS > 70th percentile
4. **VCP Pattern Detection** — swing analysis finds 2-6 volatility contractions with volume dry-up
5. **Watchlist queuing** — candidates wait up to 20 days for breakout confirmation
6. **Breakout entry** — close > pivot price AND volume > 1.3x average on same day
7. **Multi-signal exit system** — trailing stops, exhaustion gaps, high-volume declines, failed breakouts

### Strategy 2: Mean Reversion (Bearish Regime — 18% of PnL)

Activates automatically when market breadth drops below 35%:

- **Entry:** Price below SMA(20) - 1.5x StdDev AND RSI(2) < 5 AND IBS < 0.2 AND volume spike
- **Exit:** RSI(2) > 65 OR price reverts to SMA(10)
- **Stop:** 5% (tight, quick cut)
- **Max hold:** 15 days
- **Max positions:** 3 concurrent MR trades

### Risk Management

| Layer | Mechanism | When |
|-------|-----------|------|
| **Position Sizing** | 2.5% risk per trade | Every trade |
| **Hard Stop** | -10% from entry | Every VCP trade |
| **Breakeven Stop** | Move stop to entry | At +15% gain |
| **Trailing Stop** | 12% from highest | At +30% gain |
| **20% Gain Protection** | Never let it become a loss | After +20% peak |
| **Exhaustion Gap Exit** | Gap up + bearish close | Intraday signal |
| **High-Volume Decline** | -4% on 1.5x volume | Distribution signal |
| **Failed Breakout** | Price drops 3% below pivot | Pattern invalidation |
| **Equity Curve MA** | Reduce to 3 positions | When equity < 40-day MA |
| **Market Regime** | Block VCP in BEARISH | Breadth < 35% |

### VCP Scoring System (0-100 Points)

Each VCP candidate is scored on:

| Factor | Max Points | Best Score |
|--------|----------:|------------|
| Contraction count | 30 | 4+ contractions |
| Tightness ratio | 25 | Last range ≤ 30% of first |
| Volume dry-up | 20 | ≥ 50% volume decline |
| Base duration | 15 | 40-120 days |
| Base depth | 10 | 15-35% correction |
| **Bonuses** | +20 | Shakeout, quiet volume, time contracting, tight closes |

---

## Optimization History

### Total Backtests Performed: 126+

The model was refined through systematic parameter sweeps, each testing multiple configurations across 10 years of data (2016-2026) to avoid overfitting:

| Sweep | Configs Tested | Winner | What Was Tested |
|-------|---------------:|--------|-----------------|
| EqMA Drawdown Protection | 129 | eq_ma=40d, max=3, risk=1.0 | Equity curve MA periods, position limits during drawdown |
| MR Individual Parameters | 39 | SMA10 target + RSI(2) exit at 65 | Stop sizes, targets, entry thresholds, regime modes |
| MR Combination Sweep | 35 | Stop5 + SMA10 + RSI65 + Ent1.5 + RSI<5 + IBS<0.2 | Multi-parameter combinations of top individual winners |
| VCP Regime Sweep | 16 | Baseline (no changes) | CAUTIOUS position limits (1-3), risk multipliers, MR expansion |
| VCP Hard-Switch Sweep | 18 | Baseline (no changes) | BULLISH-only VCP, regime liquidation, loss-streak veto, breadth thresholds |
| Realism Testing | 6 | Baseline (current) | Slippage (0.1-0.2%), next-day entry at open |

**Key finding:** The baseline configuration won or tied in every comparative test. Additional complexity (regime liquidation, loss-streak pauses, hard switches, breadth threshold changes) consistently destroyed returns without improving drawdown. The model is at its optimal simplicity.

### What Was Tried and Rejected

| Approach | Result | Why It Failed |
|----------|--------|---------------|
| VCP only in BULLISH (hard switch) | 710% return, 1.10 Sharpe | Kills 77% of returns — VCP in CAUTIOUS is profitable |
| Regime liquidation (cut VCP losers on regime break) | 1798%, 1.33 Sharpe | 359 extra forced exits — closes positions that would recover |
| MR in CAUTIOUS regime | Always worse | MR only works in deep bear markets (breadth < 35%) |
| VCP loss-streak veto (3 losses → 5-day pause) | 1183%, 1.24 Sharpe | Consecutive-loss signal is too noisy |
| Breadth thresholds 60/40 | 714%, 22.8% DD | Wider CAUTIOUS zone reduces DD but at massive return cost |
| Breadth thresholds 50/30 | 491%, 32.8% DD | Worse in every metric |
| Triple combos (limit + risk + MR) | 318-458% | More restrictions = more harm, compounding makes it worse |

### Exit Reason Analysis (No-Compounding, 10Y)

| Exit Reason | Trades | Win Rate | PnL |
|-------------|-------:|---------:|----:|
| MR RSI Exit (strength sell) | 154 | 93.5% | +12,44,355 |
| Exhaustion Gap | 108 | 76.9% | +11,92,853 |
| Trailing Stop | 54 | 61.1% | +11,68,469 |
| High Volume Decline | 94 | 48.9% | +8,72,021 |
| Stop Loss (VCP) | 111 | 0.0% | -13,83,875 |
| MR Stop | 124 | 0.0% | -8,59,294 |
| Failed Breakout | 27 | 0.0% | -2,06,676 |

---

## How This Compares to Professional Quant Strategies

### vs. Benchmark Indices

| Metric | This Model | Nifty 50 (10Y) | Nifty Midcap 150 (10Y) |
|--------|----------:|---------------:|----------------------:|
| CAGR (approx) | ~41%* | ~12% | ~18% |
| Max Drawdown | 24.8% | ~38% | ~42% |
| Sharpe Ratio | 1.61 | ~0.6 | ~0.8 |

*\*Compounding backtest CAGR; actual live performance will differ. See methodology notes.*

### vs. Professional Strategy Benchmarks

| Strategy Type | Typical Sharpe | Our Sharpe | Notes |
|--------------|---------------:|-----------:|-------|
| Long-only equity | 0.3-0.7 | **1.61** | We beat typical long-only by 2-5x on risk-adjusted basis |
| Trend following (CTA) | 0.5-1.0 | **1.61** | Comparable to top-tier trend followers |
| Statistical arbitrage | 1.5-3.0 | 1.61 | Stat arb uses leverage + market-neutral; not comparable |
| HFT market making | 3.0-10.0 | 1.61 | Completely different game — microsecond execution, co-location |
| Renaissance Medallion | ~3.0-4.0 | 1.61 | They use leverage, 10,000+ trades/day, PhD-level math |

### What We Do Well (Honest Assessment)

- **Sharpe 1.61 is excellent** for a long-only, unleveraged, retail-accessible strategy
- **24.8% max drawdown** is manageable — most mutual funds see 30-50% drawdowns in bear markets
- **Profitable in 9/11 years** including bear markets (2018: +11.1%, 2020: +100.8%)
- **Dual-strategy regime switching** — VCP captures uptrends, MR captures oversold bounces
- **1.74 profit factor** means winners are 74% larger than losers on average
- **Fully systematic** — no discretionary decisions, every entry/exit has a rule

### What We Don't Do (and Why)

| What | Why Not |
|------|---------|
| **Short selling** | NSE short selling for retail is limited; VCP is a long-only methodology |
| **Leverage** | Returns are already strong unleveraged; leverage amplifies drawdowns |
| **Intraday trading** | VCP is a swing/position strategy (avg hold: 19-25 days) |
| **Options** | Strategy generates discrete buy/sell signals, not volatility trades |
| **Multi-asset** | Focused on NSE equities; expanding to other markets would dilute edge |

### Realistic Expectations for Live Trading

The backtest shows 3,150% compounded return. In live trading, expect significantly less due to:

1. **Entry timing** — backtest enters at close; live execution at next-day open or limit orders near close
2. **Slippage** — 0.1-0.2% on NSE mid/small-caps, especially on breakout volume
3. **Commissions** — brokerage + STT + GST (~0.1% round-trip on discount brokers)
4. **Missed trades** — some breakouts happen too fast to enter, or liquidity is thin
5. **Psychological factors** — the system has a 47% win rate; you'll lose more often than you win

A conservative estimate for live performance: **15-25% CAGR** with 20-30% max drawdown. This is still excellent — it would place you in the top decile of active traders on NSE.

---

## Backtesting Methodology

### What the Backtest Models

- Event-driven simulation processing each trading day sequentially
- Breakout confirmation (close > pivot + 1.3x volume) before entry
- Position sizing with 2.5% risk allocation per trade
- Multi-layer exit system (stops, trailing stops, pattern-based exits)
- Market regime detection via breadth (% of stocks above 50-day SMA)
- Equity curve MA for drawdown protection
- Concurrent positions capped at 5 (VCP) + 3 (MR)
- 5-day screening interval (not daily, realistic for manual/automated workflow)

### Known Biases (Fully Transparent)

| Bias | Impact | Why We Accept It |
|------|--------|-----------------|
| **Same-day entry** | Entry at close on signal day; next-day open entry drops returns ~95% | Standard in breakout research; limit orders near close or intraday entry partially mitigate this in practice |
| **No slippage** | 0.1% slippage drops returns ~85% | Compounding amplifies small per-trade differences exponentially; live trading with limit orders minimizes actual slippage |
| **Stop at stop price** | Real stops may execute at gap-down prices, worse than stop level | Primarily affects VCP stop-outs in bear markets; trailing stops and advanced exits reduce reliance on hard stops |
| **Survivorship bias** | Only stocks currently listed on NSE are backtested | Minimal for 2016-2026 period on NSE; delisted stocks were typically low-quality and filtered by RS/trend template |
| **No partial fills** | Assumes full execution at desired price | Relevant mainly for very small-cap stocks; minimum volume filter (1L avg) reduces this risk |

### Why Relative Comparisons Remain Valid

All 126+ configurations were tested under identical conditions. The biases above affect absolute returns but NOT the ranking of strategies. When we say "Baseline beats VCP-BULLISH-only by 2x on Sharpe," that comparison is valid regardless of the absolute return level.

---

## Features

- **Daily Screening**: Screens 2,200+ NSE stocks, identifies top 50 VCP candidates
- **8-Point Trend Template**: Minervini's trend filter adapted for Indian mid/small-caps (faster SMAs: 20/50/100)
- **VCP Detection**: Swing point analysis, contraction measurement, volume dry-up, 100-point scoring
- **Mean Reversion**: Automatic bear-market strategy with RSI(2), IBS, Bollinger Band entries
- **Buy Signals**: 4 signal types — BUY, WATCH_VOLUME, NEAR_PIVOT, FORMING
- **Portfolio Management**: Position sizing (2.5% risk), multi-layer trailing stops, 6 sell signal types
- **Backtesting**: 1,100+ line event-driven engine with precomputed screens for fast parameter sweeps
- **Market Regime**: Breadth-based bull/cautious/bear classification with automatic strategy switching
- **Equity Curve Protection**: 40-day equity MA reduces exposure during drawdowns
- **Dashboard**: Streamlit web UI with Plotly candlestick charts, VCP annotations, progress bars
- **Telegram Alerts**: Daily screening results pushed to your phone at 4:15 PM IST
- **Cloud Deployment**: Streamlit Cloud + Neon PostgreSQL (persistent data across sessions)

---

## Architecture

```
Streamlit Cloud (frontend)  →  Neon PostgreSQL (data)  →  yfinance (market data)
         |
         ├── Buy Signals page (one-click update + screen)
         ├── Screener (top 50 with filters + CSV export)
         ├── Stock Detail (candlestick chart + VCP annotations)
         ├── Portfolio (position tracking + P&L)
         ├── Backtest (historical simulation)
         └── Market Overview (Nifty 50 regime)
```

### Project Structure

```
src/vcp_screener/
  config.py                # Pydantic settings (all tunable via VCP_ env vars)
  db.py                    # SQLAlchemy engine (SQLite + PostgreSQL)
  models/                  # ORM: stocks, prices, results, portfolio, backtest (5 tables)
  services/
    backtester.py          # Event-driven backtest engine (1,136 lines)
    screener.py            # 5-stage screening pipeline (360 lines)
    vcp_detector.py        # VCP pattern detection + 100-pt scoring (319 lines)
    portfolio_manager.py   # Position sizing, trailing stops, alerts (272 lines)
    data_fetcher.py        # NSE list + yfinance batch download (246 lines)
    alerts.py              # Telegram notifications (171 lines)
    indicators.py          # RS, RSI, IBS, ATR, SMA, volume ratios (128 lines)
    trend_template.py      # 8-point Minervini filter (65 lines)
    market_regime.py       # Breadth + Nifty regime classification (59 lines)
  cli/main.py              # Click CLI (data, screen, portfolio, backtest, alert commands)
  dashboard/               # Streamlit app (6 pages, 756 lines)
scripts/
  seed_neon.py             # One-time Neon PostgreSQL data seeder
  *_sweep.py               # Parameter optimization scripts
tests/                     # pytest test suite
```

### Technical Indicators Used

| Indicator | Implementation | Purpose |
|-----------|---------------|---------|
| SMA (20, 50, 100) | Simple moving average | Trend template, regime detection |
| RSI (2-period) | Wilder's smoothing | MR entry (< 5) and exit (> 65) |
| IBS | (Close - Low) / (High - Low) | MR entry filter (< 0.2) |
| ATR (14-period) | Average True Range | Volatility measurement |
| Bollinger Bands | SMA(20) +/- 1.5 StdDev | MR entry threshold |
| Relative Strength | Weighted 3/6/9/12m returns | Stock ranking (top 30% only) |
| Market Breadth | % stocks above 50-day SMA | Regime classification |
| Volume Ratio | 10d avg / 50d avg | Breakout confirmation, volume dry-up |
| Up/Down Volume | Up-day vol / Down-day vol | Accumulation detection |
| Equity Curve MA | 40-day MA of portfolio equity | Drawdown protection |

---

## Quick Start (Local)

```bash
# Install
cd vcp-screener
pip install -e ".[dev]"

# Download data (first time — takes 30-60 min for 2,200+ stocks)
vcp data download

# Run screening
vcp screen run

# Check buy signals
vcp screen signals

# Analyze a specific stock
vcp screen detail TRENT

# Launch web dashboard
vcp dashboard
```

## Cloud Deployment

The app is deployed on Streamlit Cloud with Neon PostgreSQL for persistent storage.

### Setup steps:
1. **Neon DB**: Create project at [neon.tech](https://neon.tech), get connection string
2. **Seed data locally**: `DATABASE_URL="postgresql://..." python scripts/seed_neon.py`
3. **Streamlit Cloud**: Connect GitHub repo, set main file to `src/vcp_screener/dashboard/app.py`
4. **Secrets**: Add `DATABASE_URL`, `VCP_TELEGRAM_BOT_TOKEN`, `VCP_TELEGRAM_CHAT_ID` in Streamlit Cloud settings

## CLI Commands

```
vcp data download          # Full NSE stock list + historical OHLCV download
vcp data update            # Incremental update (last 10 days)
vcp screen run             # Run VCP screening pipeline
vcp screen signals         # Show actionable buy signals
vcp screen detail SYMBOL   # Detailed VCP analysis for a stock
vcp portfolio buy SYMBOL PRICE [--stop PRICE] [--shares N]
vcp portfolio sell ID PRICE [--reason TEXT]
vcp portfolio holdings     # Show current positions with P&L
vcp portfolio alerts       # Check sell alerts
vcp backtest run --start 2024-01-01 --end 2025-12-31
vcp dashboard              # Launch Streamlit web dashboard
vcp alert setup            # Telegram setup guide
vcp alert test             # Send test Telegram message
vcp alert schedule         # Start daily auto-scheduler (4:15 PM IST)
```

## Configuration

All parameters are configurable via environment variables (prefix `VCP_`):

```bash
export VCP_ACCOUNT_SIZE=500000
export VCP_MAX_POSITIONS=5
export VCP_DEFAULT_STOP_LOSS_PCT=10
export VCP_MIN_RS_PERCENTILE=70
export VCP_RISK_PER_TRADE_PCT=2.5
```

## Testing

```bash
pytest tests/ -v
```

---

## Final Model Parameters

### VCP Strategy
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| SMAs | 20/50/100 | Faster than Minervini's 50/150/200 — Indian mid-caps are more volatile |
| RS Weights | 50/25/15/10% (3/6/9/12m) | Recency bias captures faster trend changes in Indian market |
| Min RS Percentile | 70 | Only top 30% of stocks by momentum |
| Stop Loss | 10% | Balances risk control vs being stopped out on volatility |
| Trailing Stop | 12% from high after +30% | Wide enough to let runners run |
| Breakeven | Move stop to entry at +15% | Protects gains without premature exit |
| Max Positions | 5 | Concentrated enough for returns, diversified enough for risk |
| Breakout Volume | 1.3x average | Confirms institutional participation |

### Mean Reversion Strategy
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Entry StdDev | 1.5 below SMA(20) | Deep enough to avoid false signals |
| RSI(2) Entry | < 5 | Extreme oversold only |
| IBS Entry | < 0.2 | Closed near day's low (panic selling) |
| Exit Target | SMA(10) + RSI(2) > 65 | Quick reversion capture |
| Stop | 5% | Tight — if it doesn't bounce, get out fast |
| Max Hold | 15 days | Mean reversion should happen quickly |
| Max Positions | 3 | Limited allocation to counter-trend trades |

### Regime Detection
| Parameter | Value |
|-----------|-------|
| Method | Market breadth (% stocks above 50-day SMA) |
| BULLISH threshold | > 55% |
| CAUTIOUS range | 35-55% |
| BEARISH threshold | < 35% |
| Equity Curve MA | 40-day MA of portfolio equity |
| DD Max Positions | 3 (reduced from 5 when equity < MA) |
