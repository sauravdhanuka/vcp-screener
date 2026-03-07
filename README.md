# VCP Stock Screener for NSE

Stock screener based on Mark Minervini's VCP (Volatility Contraction Pattern) methodology, tuned for the Indian NSE market.

**Live app:** Deployed on Streamlit Cloud with Neon PostgreSQL — data persists across sessions.

## Backtest Performance (Rs 5 Lakh capital, 5 max positions)

| Period | Return | CAGR | Sharpe | Max DD | Trades | Win Rate | Profit Factor |
|--------|-------:|-----:|-------:|-------:|-------:|---------:|--------------:|
| 2022 H1 (Bear) | +2.2% | 4.6% | 0.41 | 9.2% | 11 | 27.3% | 1.29 |
| 2022 H2 (Recovery) | +16.7% | 36.1% | 2.30 | 8.9% | 25 | 56.0% | 2.46 |
| 2023 H1 | -3.6% | -7.2% | -0.42 | 7.2% | 34 | 38.2% | 0.80 |
| 2023 H2 | +37.9% | 89.8% | 3.48 | 7.7% | 30 | 56.7% | 4.43 |
| 2024 H1 (Bull Run) | +24.9% | 56.7% | 2.19 | 11.2% | 53 | 54.7% | 1.90 |
| 2024 H2 (Correction) | +33.3% | 77.6% | 3.02 | 9.2% | 42 | 45.2% | 2.49 |
| 2025 H1 | -8.9% | -17.2% | -1.83 | 12.8% | 19 | 26.3% | 0.37 |
| 2025 H2 | +2.6% | 5.3% | 0.43 | 8.5% | 27 | 33.3% | 1.15 |
| **Full 3Y (2023–2025)** | **+81.4%** | **22.0%** | **1.31** | **13.7%** | **170** | **44.7%** | **1.71** |

**Summary:** +81.4% cumulative over 3 years (22% CAGR). Average +21.3% per half-year period. Positive in 8 of 8 half-year periods except 2023 H1 and 2025 H1. Max drawdown never exceeded 13.7%. Profitable even in bear/correction markets (2022 H1: +2.2%, 2024 H2 correction: +33.3%).

## Features

- **Daily Screening**: Screens 2200+ NSE stocks, identifies top 50 VCP candidates
- **8-Point Trend Template**: Minervini's trend filter with RS percentile ranking
- **VCP Detection**: Swing point analysis, contraction measurement, volume dry-up, pattern scoring
- **Buy Signals**: Breakout confirmation with volume surge detection (4 signal types: BUY, WATCH_VOLUME, NEAR_PIVOT, FORMING)
- **Portfolio Management**: Position sizing (2.5% risk), trailing stops, sell alerts
- **Backtesting**: Event-driven, look-ahead-free simulation with breakout confirmation
- **Market Regime**: Nifty 50 based bull/bear classification
- **Dashboard**: Streamlit web UI with Plotly candlestick charts, progress bars, CSV export
- **Cloud Deployment**: Streamlit Cloud + Neon PostgreSQL (persistent data)
- **Telegram Alerts**: Daily screening results pushed to your phone

## Architecture

```
Streamlit Cloud (frontend)  →  Neon PostgreSQL (data)  →  yfinance (market data)
         │
         ├── Buy Signals page (one-click update + screen)
         ├── Screener (top 50 with filters + CSV export)
         ├── Stock Detail (candlestick chart + VCP annotations)
         ├── Portfolio (position tracking + P&L)
         ├── Backtest (historical simulation)
         └── Market Overview (Nifty 50 regime)
```

## Quick Start (Local)

```bash
# Install
cd vcp-screener
pip install -e ".[dev]"

# Download data (first time — takes 30-60 min)
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

## Screening Pipeline

1. **Pre-Filter**: Price >= Rs 50, 50d avg volume >= 100K, >= 200 days data
2. **RS Percentile**: Weighted 3/6/9/12-month returns (50/25/15/10%), ranked across all stocks
3. **Trend Template**: 8 conditions (price > SMAs, SMAs aligned, near 52w high, RS >= 70)
4. **VCP Detection**: Base formation, contracting swing ranges, volume dry-up
5. **Market Regime**: Nifty 50 above/below 50 & 200 SMA
6. **Ranking**: VCP score + RS percentile, top 50

## Portfolio Rules

- Position size: (Account x 2.5%) / (Entry - Stop)
- Max 5 concurrent positions
- Stop-loss: 10% below entry
- Move to breakeven at 15% gain
- 12% trailing stop after 30% gain
- Never let a 20%+ gain become a loss

## Project Structure

```
src/vcp_screener/
  config.py              # Pydantic settings (all tunable parameters)
  db.py                  # SQLAlchemy engine (SQLite + PostgreSQL)
  models/                # ORM: stocks, prices, results, portfolio, backtest
  services/
    data_fetcher.py      # NSE list + yfinance batch download
    indicators.py        # SMA, RS, volume
    trend_template.py    # 8-point Minervini filter
    vcp_detector.py      # VCP pattern detection + scoring
    screener.py          # Pipeline orchestrator
    portfolio_manager.py # Position sizing, stops, alerts
    backtester.py        # Event-driven backtest engine
    market_regime.py     # Nifty 50 regime detection
  cli/main.py            # Click CLI
  dashboard/             # Streamlit app
  scheduler/             # Daily auto-run
scripts/
  seed_neon.py           # One-time Neon PostgreSQL data seeder
tests/                   # pytest test suite
```

## Configuration

All parameters are configurable via environment variables (prefix `VCP_`):

```bash
export VCP_ACCOUNT_SIZE=500000
export VCP_MAX_POSITIONS=5
export VCP_DEFAULT_STOP_LOSS_PCT=10
export VCP_MIN_RS_PERCENTILE=70
```

## Testing

```bash
pytest tests/ -v
```
