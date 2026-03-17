# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_vcp_detector.py -v

# Run a single test
pytest tests/test_vcp_detector.py::test_function_name -v

# Launch dashboard
vcp dashboard
# or directly:
streamlit run src/vcp_screener/dashboard/app.py

# CLI commands
vcp data download          # Full NSE stock list + OHLCV (30-60 min)
vcp data update            # Incremental update (last 10 days)
vcp screen run             # Run VCP screening pipeline
vcp screen signals         # Show actionable buy signals
vcp screen detail SYMBOL   # Detailed VCP analysis
vcp portfolio holdings     # Current positions with P&L
vcp backtest run --start 2024-01-01 --end 2025-12-31
```

## Architecture

The system implements two complementary strategies that switch based on market regime (breadth % of stocks above 50-day SMA):
- **BULLISH** (breadth > 55%): VCP breakout entries
- **CAUTIOUS** (35-55%): VCP with reduced positions (3 max via equity curve MA)
- **BEARISH** (< 35%): Mean Reversion only

### Key Data Flow

1. `data_fetcher.py` → downloads 2,200+ NSE stocks via yfinance, stores OHLCV in DB
2. `screener.py` → 5-stage pipeline: pre-filter → RS ranking → trend template → VCP detection → signal generation
3. `vcp_detector.py` → swing point analysis + 100-point scoring system (contractions, volume dry-up, base depth)
4. `backtester.py` → event-driven engine, processes days sequentially, precomputes screens for parameter sweeps
5. `portfolio_manager.py` → position sizing (2.5% risk/trade), multi-layer trailing stops, sell signal generation
6. `market_regime.py` → breadth calculation drives strategy switching
7. `dashboard/app.py` → single-page Streamlit app with 6 pages rendered as sections

### Database

- **Local**: SQLite at `data/vcp_screener.db`
- **Cloud**: PostgreSQL via `DATABASE_URL` env var (Neon on Streamlit Cloud)
- `db.py` auto-detects: if `DATABASE_URL` is set, uses PostgreSQL; otherwise SQLite
- `init_db()` creates tables + runs `_migrate_schema()` for safe column additions
- 6 ORM models: `Stock`, `DailyPrice`, `ScreeningResult`, `Position`, `BacktestRun`, `Watchlist`

### Configuration

All settings are in `config.py` as a Pydantic `Settings` class. Every field is overridable via `VCP_` prefixed environment variables or a `.env` file. Key tunables: `VCP_ACCOUNT_SIZE`, `VCP_MAX_POSITIONS`, `VCP_RISK_PER_TRADE_PCT`, `VCP_MIN_RS_PERCENTILE`.

### Dashboard Structure

`dashboard/app.py` renders all 6 pages in sequence (not multi-page routing) with a sidebar nav that uses `st.session_state` to track the active page. Pages are in `dashboard/pages/`: screener, signals, stock detail, portfolio, backtest, market overview. Charts are in `dashboard/components/charts.py`.

### Watchlist System

VCP candidates that don't yet have a breakout go onto a watchlist (up to 20-day expiry). The screener checks watchlist stocks daily for breakout confirmation (close > pivot + 1.3x volume). `watchlist_service.py` manages CRUD; `watchlist.py` is the ORM model.

## Important Design Decisions

- **SMAs are 20/50/100** (not Minervini's 50/150/200) — Indian mid/small-caps are more volatile
- **RS weights are recency-biased** (50% on 3-month) — captures faster trend changes in Indian market
- **Backtester enters at close on signal day** (known bias, accepted for research consistency)
- **`backtester.py` precomputes screens** at 5-day intervals then replays them for fast parameter sweeps — do not break this separation
- **MR strategy only activates in BEARISH regime** — enabling it in CAUTIOUS was tested and always made results worse
- The baseline model configuration was the winner across 126+ parameter sweeps; resist adding complexity
