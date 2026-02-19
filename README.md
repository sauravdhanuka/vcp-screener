# VCP Stock Screener for NSE

Stock screener based on Mark Minervini's VCP (Volatility Contraction Pattern) methodology, tuned for the Indian NSE market.

## Features

- **Daily Screening**: Screens ~2000+ NSE stocks, identifies top 50 buy candidates
- **8-Point Trend Template**: Minervini's trend filter with RS percentile ranking
- **VCP Detection**: Swing point analysis, contraction measurement, volume dry-up, pattern scoring
- **Portfolio Management**: Position sizing (2% risk), trailing stops, sell alerts
- **Backtesting**: Event-driven, look-ahead-free historical simulation
- **Market Regime**: Nifty 50 based bull/bear classification
- **Dashboard**: Streamlit web UI with Plotly charts

## Quick Start

```bash
# Install
cd ~/vcp-screener
pip install -e ".[dev]"

# Download data (first time - takes 30-60 min)
vcp data download

# Run screening
vcp screen run

# Analyze a specific stock
vcp screen detail TRENT

# Launch web dashboard
vcp dashboard
```

## CLI Commands

```
vcp data download          # Full NSE stock list + 2yr OHLCV download
vcp data update            # Incremental update (last 10 days)
vcp screen run             # Run VCP screening pipeline
vcp screen detail SYMBOL   # Detailed VCP analysis for a stock
vcp portfolio buy SYMBOL PRICE [--stop PRICE] [--shares N]
vcp portfolio sell ID PRICE [--reason TEXT]
vcp portfolio holdings     # Show current positions with P&L
vcp portfolio alerts       # Check sell alerts
vcp portfolio history      # Closed trade history
vcp backtest run --start 2024-01-01 --end 2025-12-31
vcp dashboard              # Launch Streamlit web dashboard
```

## Screening Pipeline

1. **Pre-Filter**: Price >= Rs 50, 50d avg volume >= 100K, >= 252 days data
2. **RS Percentile**: Weighted 3/6/9/12-month returns, ranked across all stocks
3. **Trend Template**: 8 conditions (price > SMAs, SMAs aligned, near 52w high, RS >= 70)
4. **VCP Detection**: Base formation, contracting swing ranges, volume dry-up
5. **Market Regime**: Nifty 50 above/below 50 & 200 SMA
6. **Ranking**: VCP score (desc) + RS percentile (desc), top 50

## Portfolio Rules

- Position size: (Account * 2%) / (Entry - Stop)
- Max 4-6 concurrent positions
- Stop-loss: 8-10% below entry
- Move to breakeven at 12-15% gain
- 10% trailing stop after 25% gain
- Never let a 20%+ gain become a loss

## Daily Scheduler

```bash
# Run the scheduler (will execute daily at 4:15 PM IST)
python -m vcp_screener.scheduler.daily_job
```

## Project Structure

```
src/vcp_screener/
  config.py              # Pydantic settings (all tunable parameters)
  db.py                  # SQLAlchemy engine
  models/                # ORM: stocks, prices, results, portfolio, backtest
  services/
    data_fetcher.py      # NSE list + yfinance batch download
    indicators.py        # SMA, RS, volume, ATR
    trend_template.py    # 8-point Minervini filter
    vcp_detector.py      # VCP pattern detection + scoring
    screener.py          # Pipeline orchestrator
    portfolio_manager.py # Position sizing, stops, alerts
    backtester.py        # Event-driven backtest engine
    market_regime.py     # Nifty 50 regime detection
  cli/main.py            # Click CLI
  dashboard/             # Streamlit app
  scheduler/             # Daily auto-run
```

## Configuration

All parameters are configurable via environment variables (prefix `VCP_`):

```bash
export VCP_ACCOUNT_SIZE=500000
export VCP_MAX_POSITIONS=6
export VCP_DEFAULT_STOP_LOSS_PCT=10
export VCP_MIN_RS_PERCENTILE=70
```

## Testing

```bash
pytest tests/ -v
```
