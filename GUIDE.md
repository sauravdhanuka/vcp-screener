# VCP Stock Screener for NSE — Complete Technical Guide

An automated stock screener for the Indian NSE market based on **Mark Minervini's VCP (Volatility Contraction Pattern)** strategy, re-engineered and optimized for Indian mid/small-cap stocks using data-driven parameter tuning across 126 backtests.

Built with Python, SQLAlchemy, yfinance, Click, Rich, Streamlit, and Plotly.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Setting Up on a Fresh Windows Laptop](#2-setting-up-on-a-fresh-windows-laptop)
3. [All CLI Commands](#3-all-cli-commands)
4. [Using the Streamlit Dashboard](#4-using-the-streamlit-dashboard)
5. [Telegram Alerts — Setup & Usage](#5-telegram-alerts--setup--usage)
6. [Project Architecture](#6-project-architecture)
7. [Why Each Technology Was Chosen](#7-why-each-technology-was-chosen)
8. [The Screening Algorithm — Deep Dive](#8-the-screening-algorithm--deep-dive)
9. [Buy Signals — How Stocks Get Selected](#9-buy-signals--how-stocks-get-selected)
10. [How We Adapted Minervini for India](#10-how-we-adapted-minervini-for-india)
11. [Parameter Optimization — The 126-Backtest Sweep](#11-parameter-optimization--the-126-backtest-sweep)
12. [Backtest Results](#12-backtest-results)
13. [Portfolio Management System](#13-portfolio-management-system)
14. [Backtester Architecture](#14-backtester-architecture)
15. [Configuration Reference](#15-configuration-reference)
16. [Daily Workflow — Manual & Automated](#16-daily-workflow--manual--automated)
17. [Code Walkthrough — Every File Explained](#17-code-walkthrough--every-file-explained)
18. [Testing](#18-testing)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Quick Start

### Prerequisites
- Python 3.11+
- pip
- Internet connection

### Installation

```bash
cd ~/vcp-screener
pip install -e ".[dev]"
```

`-e` = editable mode (code changes take effect immediately). `[dev]` installs pytest.

### First Run

```bash
# Step 1: Download 5 years of data for 2200+ NSE stocks (~5-6 minutes)
vcp data download

# Step 2: Run the screener
vcp screen run

# Step 3: Get actionable buy signals (the most important command)
vcp screen signals

# Step 4: Analyze a specific stock
vcp screen detail GRAPHITE

# Step 5: Launch the web dashboard
vcp dashboard
# Opens at http://localhost:8501

# Step 5: Run a backtest
vcp backtest run --start 2024-01-01 --end 2024-09-30 --capital 100000 --positions 5
```

### Daily Usage (after first setup)

```bash
vcp data update          # Fetch last 10 days (~2 min)
vcp screen run           # Find today's top 50 VCP candidates
vcp portfolio alerts     # Check if any positions need selling
vcp dashboard            # Visual analysis
```

---

## 2. Setting Up on a Fresh Windows Laptop

If you're setting this up on a brand new Windows machine from scratch, follow these steps exactly.

### Step 1: Install Python

1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or higher (click the big yellow button)
3. **IMPORTANT**: On the installer, check the box that says **"Add Python to PATH"** before clicking Install
4. Open **Command Prompt** (search "cmd" in Start menu) and verify:

```cmd
python --version
pip --version
```

Both should show version numbers. If `python` doesn't work, try `python3`.

### Step 2: Install Git

1. Go to https://git-scm.com/download/win
2. Download and install with default settings
3. Verify in Command Prompt:

```cmd
git --version
```

### Step 3: Clone the Project

```cmd
cd %USERPROFILE%
git clone <your-repo-url> vcp-screener
cd vcp-screener
```

If you're copying the folder instead of using git, just put the `vcp-screener` folder in your home directory (`C:\Users\YourName\vcp-screener`).

### Step 4: Install the Package

```cmd
cd %USERPROFILE%\vcp-screener
pip install -e ".[dev]"
```

This installs all dependencies (yfinance, pandas, streamlit, plotly, etc.) and registers the `vcp` command.

**If you get a "pip not found" error:**
```cmd
python -m pip install -e ".[dev]"
```


### Step 5: Download Stock Data

```cmd
vcp data download
```

If `vcp` is not recognized, use:
```cmd
python -m vcp_screener.cli.main data download
```

This takes 5-10 minutes. It downloads 5 years of data for 2200+ NSE stocks.

### Step 6: Run the Screener

```cmd
vcp screen run
vcp screen signals
```

### Step 7: Launch Dashboard

```cmd
vcp dashboard
```

Opens at http://localhost:8501 in your browser.

### Step 8: Set Up Telegram Alerts (Optional)

On Windows, set environment variables like this:

**Temporary (current session only):**
```cmd
set VCP_TELEGRAM_BOT_TOKEN=your-token-here
set VCP_TELEGRAM_CHAT_ID=your-chat-id-here
vcp alert test
```

**Permanent (persists across restarts):**
1. Search "Environment Variables" in the Start menu
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", click "New"
5. Add `VCP_TELEGRAM_BOT_TOKEN` with your bot token
6. Add `VCP_TELEGRAM_CHAT_ID` with your chat ID
7. Click OK, restart Command Prompt

### Step 9: Start Daily Scheduler

```cmd
vcp alert schedule
```

Leave this terminal open. It runs the full pipeline at 4:15 PM IST daily and sends alerts to Telegram.

**To run it in the background on Windows**, use Task Scheduler:
1. Search "Task Scheduler" in Start menu
2. Click "Create Basic Task"
3. Name: "VCP Screener Daily"
4. Trigger: Daily, 4:15 PM
5. Action: Start a program
6. Program: `python`
7. Arguments: `-m vcp_screener.scheduler.daily_job --now`
8. Start in: `C:\Users\YourName\vcp-screener`

### Windows-Specific Notes

- **Use `cmd` or PowerShell**, not Git Bash — some yfinance operations have issues in Git Bash on Windows
- **Firewall**: If `vcp data download` fails, check if your firewall/antivirus is blocking Python's network access
- **Path issues**: If `vcp` command isn't found after install, add Python's Scripts directory to PATH:
  ```cmd
  set PATH=%PATH%;%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts
  ```
- **SQLite**: Works natively on Windows, no extra setup needed
- **Streamlit**: If `vcp dashboard` fails, try: `python -m streamlit run src\vcp_screener\dashboard\app.py`
- **Line endings**: If you get weird import errors after copying files, run: `git config --global core.autocrlf true`

---

## 3. All CLI Commands

The CLI uses a `vcp <group> <command>` structure. Run `vcp --help` or `vcp <group> --help` for details.

### Data Commands
| Command | What It Does |
|---------|-------------|
| `vcp data download` | Full download: NSE stock list + 5 years OHLCV for all 2200+ stocks |
| `vcp data update` | Incremental: fetch last 10 days of data (fast) |
| `vcp data update --days 30` | Fetch last 30 days |

### Screening Commands
| Command | What It Does |
|---------|-------------|
| `vcp screen run` | Run the full screening pipeline, display top 50 candidates |
| `vcp screen signals` | **Actionable buy signals**: which stocks are breaking out RIGHT NOW with entry/stop/shares |
| `vcp screen detail SYMBOL` | Deep analysis: trend template, VCP detection, pivot price |

### Portfolio Commands
| Command | What It Does |
|---------|-------------|
| `vcp portfolio buy SYMBOL PRICE` | Record a buy (auto-sizes position, sets stop) |
| `vcp portfolio buy SYMBOL PRICE --stop 180` | Buy with manual stop-loss price |
| `vcp portfolio buy SYMBOL PRICE --shares 200` | Buy exact number of shares |
| `vcp portfolio sell ID PRICE` | Close a position (ID from `holdings`) |
| `vcp portfolio sell ID PRICE --reason "target hit"` | Close with reason |
| `vcp portfolio holdings` | Show all open positions with live P&L |
| `vcp portfolio alerts` | Check sell signals (stop hit, trailing stop, climax top) |
| `vcp portfolio history` | Show closed trade history |

### Backtest Commands
| Command | What It Does |
|---------|-------------|
| `vcp backtest run --start 2024-01-01 --end 2024-09-30` | Run backtest with default capital |
| `vcp backtest run --start 2024-01-01 --end 2024-09-30 --capital 100000 --positions 5` | Custom |

### Dashboard
| Command | What It Does |
|---------|-------------|
| `vcp dashboard` | Launch Streamlit web app at localhost:8501 |

### Telegram Alert Commands
| Command | What It Does |
|---------|-------------|
| `vcp alert setup` | Step-by-step guide to create a Telegram bot and configure alerts |
| `vcp alert test` | Send a test message to verify Telegram is working |
| `vcp alert now` | Run screening + send full buy/sell alert report to Telegram immediately |
| `vcp alert schedule` | Start the daily scheduler (runs at 4:15 PM IST, sends Telegram alerts) |

---

## 4. Using the Streamlit Dashboard

Launch with `vcp dashboard` or directly with `streamlit run src/vcp_screener/dashboard/app.py`.

The sidebar on the left lets you navigate between 5 pages:

### Page 1: Screener
**What you see:** A table of the top 50 VCP candidates from the most recent `vcp screen run`.

**How to use it:**
1. Select a screening date from the dropdown (results are saved per day)
2. Use the sliders to filter: minimum VCP score, minimum RS percentile, minimum contractions
3. The metrics row shows total candidates, average scores, and the current market regime
4. Click column headers to sort

**Why this page matters:** This is your daily shopping list. Stocks at the top with VCP Score > 70 and RS > 85 are the strongest candidates.

### Page 2: Stock Detail
**What you see:** Enter any NSE symbol to get a full breakdown.

**How to use it:**
1. Type a symbol (e.g., `GRAPHITE`) in the text box
2. You get 4 metric cards: Close price, RS percentile, VCP score, Pivot price
3. Below that: a **candlestick chart** with:
   - Red/green/blue lines = 20/50/100-day SMAs
   - Orange shaded boxes = VCP contraction zones
   - Orange dashed line = pivot price (the breakout level)
   - Bottom panel = volume bars (red = down day, green = up day)
4. Below the chart: trend template checklist (green checks / red X for each condition)
5. Contraction details table showing each T1, T2, T3 with range % and volume

**Why this page matters:** Before buying any screener candidate, check it here. You want to see the contractions getting visibly tighter and volume drying up. The chart makes patterns obvious that numbers alone can't convey.

### Page 3: Portfolio
**What you see:** Three tabs — Holdings, Sell Alerts, Trade History.

**Holdings tab:**
- Table of all open positions with entry price, current price, shares, cost, market value, P&L, P&L %, and stop prices
- Summary metrics: total positions, total cost, market value, overall P&L

**Sell Alerts tab:**
- Shows any positions with active sell signals (stop hit, trailing stop, high-volume decline, etc.)
- Red alerts = act immediately, Yellow = monitor closely

**Trade History tab:**
- All closed trades with win rate and total P&L summary

### Page 4: Backtest
**What you see:** Two tabs — Run Backtest, Past Results.

**Run Backtest tab:**
1. Set start date, end date, initial capital, and max positions
2. Click "Run Backtest" (takes a few minutes)
3. Results show: KPI cards (return, CAGR, max drawdown, Sharpe, win rate)
4. Equity curve chart with drawdown overlay
5. Full trade log table

**Past Results tab:**
- Browse previous backtest runs stored in the database
- Each expandable section shows KPIs and the equity curve chart

### Page 5: Market Overview
**What you see:** Nifty 50 chart with SMA overlays and regime classification.

**How to read it:**
- **BULLISH** (green): Nifty above both 50 and 200 SMA, SMAs aligned upward. Best time to trade VCP breakouts.
- **CAUTIOUS** (orange): Nifty above 200 SMA but below 50 SMA. Reduce position sizes, be selective.
- **BEARISH** (red): Nifty below 200 SMA. Avoid new entries, protect existing positions.

The page also shows trading guidance text based on the current regime.

---

## 5. Telegram Alerts — Setup & Usage

Get buy/sell signals delivered straight to your phone via Telegram. No checking dashboards or terminals — alerts come to you.

### What You Receive Daily at 4:15 PM

After market close, you get a message like this on Telegram:

```
📊 VCP Screener — 19 Feb 2026, 04:15 PM
Market: CAUTIOUS

🟢 BUY — 1 Breakout Confirmed

JBCHEPHARM ₹1,998
  Pivot: ₹1,992 | Vol: 1.6x
  VCP: 33 | RS: 85
  ➡️ Buy 12 shares @ ₹1,998
  🛑 Stop: ₹1,798 | Cost: ₹23,976

🟡 Above Pivot — Need Volume (12)
  MASFIN, IOC, PNB, AEROFLEX, ADANIPORTS
  +7 more

🔵 Near Pivot — Watchlist (3)
  CCL (0.0% away), SAIL (0.3%), GNA (2.9%)

21 more stocks still forming patterns

━━━━━━━━━━━━━━━

🚨 SELL ALERTS

🔴 NETWEB (#1)
  Signal: TRAILING_STOP_HIT
  Entry: ₹3,507 → Now: ₹3,150 📉 -10.2%
  Stop: ₹3,156

━━━━━━━━━━━━━━━

💼 Portfolio — 2 positions
Cost: ₹48,000 | Value: ₹51,200
P&L: ₹+3,200 (+6.7%) 📈

  🟢 JBCHEPHARM +9.4%
  🔴 NETWEB -1.2%
```

### Setup (2 Minutes)

#### Step 1: Create a Telegram Bot

1. Open Telegram on your phone
2. Search for **@BotFather** (the official bot that creates bots)
3. Send `/newbot`
4. Give it a name: `VCP Screener` (or anything you like)
5. Give it a username: `vcp_screener_yourname_bot` (must end in `bot`)
6. BotFather replies with a token like: `7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx`
7. **Copy this token** — you'll need it in Step 3

#### Step 2: Get Your Chat ID

1. In Telegram, search for **@userinfobot**
2. Start the bot (click Start or send `/start`)
3. It replies with your user ID, e.g., `Id: 987654321`
4. **Copy this number** — this is your chat ID

#### Step 3: Configure the Screener

**macOS/Linux:**
```bash
export VCP_TELEGRAM_BOT_TOKEN='7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx'
export VCP_TELEGRAM_CHAT_ID='987654321'

# Make it permanent (add to shell config)
echo 'export VCP_TELEGRAM_BOT_TOKEN="7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx"' >> ~/.zshrc
echo 'export VCP_TELEGRAM_CHAT_ID="987654321"' >> ~/.zshrc
```

**Windows (Command Prompt):**
```cmd
set VCP_TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx
set VCP_TELEGRAM_CHAT_ID=987654321
```

For permanent Windows setup: search "Environment Variables" in Start menu → Edit system environment variables → Environment Variables → New (under User variables) → add both variables.

#### Step 4: Test It

```bash
vcp alert test
```

You should receive a test message on Telegram within a few seconds. If not, double-check the token and chat ID.

#### Step 5: Send a Full Report Right Now

```bash
vcp alert now
```

This runs the buy signal check and sends the complete daily report to Telegram immediately — useful for testing or if you missed the 4:15 PM auto-run.

#### Step 6: Start the Daily Scheduler

```bash
vcp alert schedule
```

This starts a process that:
- Runs at **4:15 PM IST** every day
- Updates price data
- Runs the full screening pipeline
- Checks buy signals (breakout confirmations)
- Updates trailing stops on your positions
- Checks sell alerts
- Sends everything to your Telegram

Leave this terminal open, or set it up as a background service.

**On macOS** — to keep it running after closing the terminal:
```bash
nohup vcp alert schedule > ~/vcp-screener/data/scheduler.log 2>&1 &
```

**On Windows** — use Task Scheduler (see the Windows setup section above).

### Alert Commands Reference

| Command | What It Does |
|---------|-------------|
| `vcp alert setup` | Prints the step-by-step setup guide |
| `vcp alert test` | Sends a test message to verify Telegram works |
| `vcp alert now` | Sends a full buy/sell/portfolio report right now |
| `vcp alert schedule` | Starts the daily auto-scheduler with Telegram alerts |

### Why Telegram (and not Email/WhatsApp/SMS)

| Option | Push to Phone | Free | Easy Setup | Formatted Messages | Charts |
|--------|:---:|:---:|:---:|:---:|:---:|
| **Telegram** | Yes | Yes | 2 min | Yes (HTML) | Yes (images) |
| Email | Depends | Yes | Medium | Basic | As attachments |
| WhatsApp | Yes | No (Business API) | Hard | No | No |
| SMS | Yes | No (paid/msg) | Medium | No | No |
| Website | No (must check) | Yes | N/A | Yes | Yes |

Telegram is the clear winner for Indian market traders — most already use it, it's free, instant, and supports rich formatting.

---

## 6. Project Architecture

```
~/vcp-screener/
├── pyproject.toml                         # Package definition, dependencies, CLI entry point
├── param_sweep.py                         # Parameter optimization script (126 backtests)
├── GUIDE.md                               # This file
├── README.md                              # Quick reference
├── data/
│   └── vcp_screener.db                    # SQLite database (auto-created, gitignored)
├── src/vcp_screener/
│   ├── __init__.py
│   ├── config.py                          # Pydantic settings — all tunable parameters
│   ├── db.py                              # SQLAlchemy engine, session factory, init_db()
│   ├── models/                            # ORM table definitions (7 tables)
│   │   ├── stock.py                       # stocks: symbol, name, sector, is_active
│   │   ├── daily_price.py                 # daily_prices: OHLCV per symbol per date
│   │   ├── screening_result.py            # screening_results: saved top 50 per run
│   │   ├── portfolio.py                   # positions: buy/sell tracking
│   │   └── backtest.py                    # backtest_runs + backtest_trades + backtest_equity
│   ├── services/                          # Business logic layer
│   │   ├── data_fetcher.py                # NSE stock list + yfinance batch download
│   │   ├── indicators.py                  # SMA, RS rating, volume ratio, ATR
│   │   ├── trend_template.py              # 8-point Minervini trend filter (adapted)
│   │   ├── vcp_detector.py                # VCP pattern detection + scoring engine
│   │   ├── screener.py                    # Pipeline orchestrator
│   │   ├── portfolio_manager.py           # Position sizing, trailing stops, sell alerts
│   │   ├── backtester.py                  # Event-driven simulation with breakout confirmation
│   │   └── market_regime.py               # Nifty 50 bull/bear classification
│   ├── cli/
│   │   └── main.py                        # Click CLI with Rich formatting
│   ├── dashboard/
│   │   ├── app.py                         # Streamlit entry point with sidebar navigation
│   │   ├── pages/
│   │   │   ├── screener_page.py           # Top 50 table with filters
│   │   │   ├── stock_detail_page.py       # Candlestick + VCP annotation chart
│   │   │   ├── portfolio_page.py          # Holdings, alerts, history tabs
│   │   │   ├── backtest_page.py           # Run backtest + view past results
│   │   │   └── market_page.py             # Nifty 50 chart + regime
│   │   └── components/
│   │       └── charts.py                  # Plotly chart builders (candlestick, equity curve, heatmap)
│   └── scheduler/
│       └── daily_job.py                   # Auto-run pipeline at 4:15 PM IST
└── tests/
    ├── test_indicators.py                 # SMA, RS, volume tests
    ├── test_trend_template.py             # Trend filter condition tests
    ├── test_vcp_detector.py               # VCP detection with synthetic data
    └── test_portfolio.py                  # Position sizing tests
```

### Design Pattern
The project follows a **layered architecture**:
- **Models** (data layer) → define database schema
- **Services** (business logic) → implement algorithms, don't know about CLI or web
- **CLI / Dashboard** (presentation) → call services, format output
- **Config** (settings) → single source of truth for all parameters

This separation means the same screening engine works identically whether called from the CLI, the dashboard, or the backtester.

---

## 7. Why Each Technology Was Chosen

| Technology | What It Does | Why This One |
|-----------|-------------|--------------|
| **Python 3.11+** | Core language | Best ecosystem for financial data (pandas, numpy, scipy). Type hints with `Mapped[]` require 3.11+. |
| **yfinance** | Price data API | Free, no API key needed, supports NSE with `.NS` suffix. Batch download for 50 tickers at once. The alternative (NSE's own API) requires browser-like headers and breaks frequently. |
| **SQLAlchemy 2.0** | ORM / database | Modern mapped_column syntax, type-safe queries. Lets us swap SQLite for PostgreSQL later without changing code. The ORM means we write Python classes instead of raw SQL. |
| **SQLite** | Database | Zero setup, single file, perfect for local/single-user app. Handles 2+ million rows fine. No server process needed. |
| **Pydantic Settings** | Configuration | Type-validated settings with automatic env var override (`VCP_` prefix). One class defines defaults + types + validation. |
| **Click** | CLI framework | Decorator-based, supports nested command groups (`vcp data download`), auto-generates `--help`. Flask's CLI is built on Click — it's the standard. |
| **Rich** | Terminal formatting | Beautiful colored tables, panels, progress bars in the terminal. Makes CLI output look professional without complexity. |
| **Streamlit** | Web dashboard | Python-only web framework — no HTML/CSS/JS needed. `st.metric()`, `st.dataframe()`, `st.plotly_chart()` build a full dashboard in ~100 lines per page. Hot-reloads on save. |
| **Plotly** | Interactive charts | Candlestick charts with hover tooltips, zoom, pan. Integrates natively with Streamlit via `st.plotly_chart()`. Matplotlib can't do interactive candlesticks well. |
| **scipy** | Signal processing | `argrelextrema()` finds swing highs/lows mathematically — the N-bar extrema detection method. numpy alone can't do this without writing 30+ lines of loop logic. |
| **pandas** | Data manipulation | Industry standard for time-series. Rolling windows (`close.rolling(50).mean()`), resampling, vectorized operations. Every financial library outputs pandas DataFrames. |
| **schedule** | Task scheduling | Simple `schedule.every().day.at("16:15").do(job)` syntax. Lightweight alternative to APScheduler or cron for a single recurring task. |

---

## 8. The Screening Algorithm — Deep Dive

### Overview

```
2200+ NSE stocks
      │
      ▼
Step 1: Pre-filter (price, volume, data length)
      │  ~900 survive
      ▼
Step 2: Relative Strength percentile ranking
      │  All 900 scored and ranked
      ▼
Step 3: 8-Point Trend Template (ALL must pass)
      │  ~50-150 survive
      ▼
Step 4: VCP Pattern Detection + Scoring
      │  ~10-50 survive
      ▼
Step 5: Market Regime check (Nifty 50)
      │  Flags regime, doesn't filter
      ▼
Step 6: Sort by VCP Score → RS Percentile
      │
      ▼
Output: Top 50 candidates with breakout pivot prices
```

### Step 1: Pre-Filter (`screener.py → pre_filter()`)

Fast rejection to avoid wasting CPU on irrelevant stocks:

| Filter | Threshold | Why |
|--------|-----------|-----|
| Minimum price | Rs 50 | Below Rs 50 = penny stocks with manipulation risk, wide bid-ask spreads |
| Minimum 50-day avg volume | 1,00,000 shares | Below this, you can't enter/exit a Rs 20,000-30,000 position without moving the price |
| Minimum data history | 200 trading days | Need ~1 year to compute 52-week high/low, SMAs, and RS rating reliably |

**Why 200 days instead of Minervini's 252:** Indian stocks IPO frequently. 252 days = exactly 1 year of trading. By relaxing to 200, we catch strong new listings (like recent IPOs that are already trending up) that would otherwise be excluded.

### Step 2: Relative Strength Percentile (`indicators.py`)

**What it measures:** How much a stock has outperformed compared to ALL other stocks in the universe.

**Formula:**
```
RS Raw = 50% × (3-month return) + 25% × (6-month return) + 15% × (9-month return) + 10% × (12-month return)
```

Then every stock's raw score is converted to a percentile (0-100) using `scipy.stats.percentileofscore`.

**Why these specific weights (50/25/15/10):**
- Original Minervini uses 40/20/20/20 — designed for the slower-moving US market
- Indian mid/small caps trend in sharper, shorter bursts. A stock that was strong 12 months ago may be dead now
- Our backtests showed that weighting recent performance more heavily (50% on 3-month) catches Indian momentum stocks ~2-4 weeks earlier
- This was validated: configs with recency RS outperformed original RS by +3-7% average return across 6 test periods

**Why percentile ranking instead of absolute return:**
- A stock up 20% in a bull market where everything is up 30% is actually weak
- A stock up 15% in a correction where most stocks are down 10% is extremely strong
- Percentile ranking captures this relative strength regardless of market conditions

### Step 3: 8-Point Trend Template (`trend_template.py`)

ALL 8 conditions must pass simultaneously. This is the most powerful filter — it eliminates ~85% of remaining stocks.

| # | Condition | What It Checks | Why It Matters |
|---|-----------|---------------|----------------|
| 1 | Price > 50 SMA AND Price > 100 SMA | Stock is above both medium and long-term averages | If price is below its averages, the trend is down — no VCP will work |
| 2 | 50 SMA > 100 SMA | Medium-term average is above long-term | SMA alignment confirms trend direction. When shorter SMA crosses above longer, it's a bullish signal (golden cross concept) |
| 3 | 100 SMA trending up for >= 22 trading days | Long-term trend is rising, not flat | A flat 100 SMA means no trend — the stock is range-bound. We need a rising tide |
| 4 | 20 SMA > 50 SMA AND 20 SMA > 100 SMA | Short-term is the strongest of all three | This means recent price action is the most bullish. All three timeframes agree |
| 5 | Price > 20 SMA | Stock is above its short-term average | Price above 20 SMA = in an immediate uptrend, not pulling back |
| 6 | Price >= 30% above 52-week low | Stock has bounced significantly from its bottom | If a stock is only 10% above its low, it hasn't proven it can sustain a rally |
| 7 | Price within 25% of 52-week high | Stock is near its highs | We want stocks making new highs, not beaten-down value traps. A stock 50% below its high is broken |
| 8 | RS percentile >= 70 | Stock outperforms 70%+ of all stocks | Only leaders. If a stock passes conditions 1-7 but has weak RS, its sector is probably dragging it along |

**Why 20/50/100 SMA instead of Minervini's 50/150/200:**
- Minervini's original was designed for US large caps (AAPL, MSFT, NVDA) which trend over years
- Indian mid/small caps complete full trend cycles in 6-12 months, not 2-3 years
- A 200-day SMA responds too slowly — by the time it turns up, the move is often 60-70% done
- Our 100-day SMA catches trends ~2-3 months earlier
- **Backtest proof:** Fast SMA configs averaged +11-18% return vs +7% for original SMA across all test periods

### Step 4: VCP Pattern Detection (`vcp_detector.py`)

This is the most algorithmically complex part. It detects the Volatility Contraction Pattern — the specific chart pattern that precedes explosive breakouts.

**What is a VCP and why does it work?**

After a stock runs up strongly (Stage 2 uptrend), it pauses and consolidates. This consolidation is natural — early buyers take profits, creating selling pressure. The key insight is that in a healthy stock, this selling pressure decreases over time:

```
Price chart during VCP formation:

     Peak
      /\
     /  \         /\
    /    \       /  \      /\
   /      \     /    \    /  \    /\
  /        \___/      \__/    \__/  \_____ ← Pivot (breakout level)
             T1          T2      T3
        (widest)    (medium)  (tight)

Volume:
  ████████   ██████    ███     ██
  (heavy)   (less)   (dry)  (very dry)
```

**Why contractions shrink:** Each wave of selling finds fewer sellers remaining. The stock is transitioning from "weak hands" (who panic at any dip) to "strong hands" (institutions accumulating). When selling dries up completely (tight final contraction + low volume), the stock is coiled and ready to break out.

**How the code detects this:**

1. **`find_base_start()`** — Finds the highest high followed by a >= 10% correction. This marks where the consolidation began.

2. **`find_swing_highs()` / `find_swing_lows()`** — Uses `scipy.signal.argrelextrema()` with `order=5`. This means a swing high is a price bar whose high is greater than or equal to the highs of the 5 bars on each side (10 total). This mathematical approach is more reliable than eyeballing charts.

3. **`detect_contractions()`** — Pairs each swing high with the nearest following swing low. Measures the percentage range of each pair. Validates that each contraction is smaller than the previous one (the core VCP requirement). Allows one violation (real charts are messy).

4. **Volume dry-up check** — Compares average volume in the last contraction vs the first. A 50%+ decrease means selling pressure has exhausted.

5. **Pivot price** — Set at the high of the final (tightest) contraction. This is the breakout level.

**VCP Score (0-100):**

The scoring function converts pattern quality into a single number:

| Component | Max Points | Logic |
|-----------|-----------|-------|
| Contraction count | 30 | 2 contractions = 10pts, 3 = 25pts, 4+ = 30pts. More contractions = more base-building = stronger breakout |
| Tightness ratio | 25 | Last contraction range / first contraction range. Lower = better (0.3 = last is 70% tighter than first) |
| Volume dry-up | 20 | % decrease in volume from first to last contraction. 50%+ = 20pts |
| Base duration | 15 | 40-120 trading days = ideal (15pts). Too short = not enough accumulation. Too long = dead money |
| Base depth | 10 | 15-35% correction from peak to trough = ideal for Indian stocks. Deeper = riskier |

### Step 5: Market Regime (`market_regime.py`)

Downloads Nifty 50 data and classifies the overall market:

| Regime | Condition | What It Means |
|--------|-----------|---------------|
| BULLISH | Nifty > 50 SMA, > 100 SMA, 50 SMA > 100 SMA | Full risk-on. VCP breakouts have the highest success rate |
| CAUTIOUS | Nifty > 100 SMA but below 50 SMA | Market is pulling back but long-term trend intact. Be selective |
| BEARISH | Nifty < 100 SMA | Market in downtrend. Breakouts fail at high rates. Cash is a position |

### Step 6: Breakout Confirmation (in backtester + live trading)

This is our biggest improvement over vanilla Minervini. Instead of buying immediately when a stock appears on the screener, we put it on a **watchlist** and wait for a **confirmed breakout**:

**Entry criteria:**
1. Stock's closing price crosses above the pivot price
2. Volume on the breakout day is >= 1.3x the 50-day average volume

**Why 1.3x and not 1.5x or 2x:**
- We tested 1.0x (no confirmation), 1.3x, and 1.5x across 6 market periods
- 1.5x was too strict — many valid breakouts in Indian mid-caps happen on 1.2-1.4x volume
- 1.3x filtered out low-conviction breakouts while still catching the real ones
- 1.0x (no confirmation) averaged +7-11% return; 1.3x averaged +15-18%

**Watchlist expiry:** Candidates stay on the watchlist for 20 trading days. If no breakout occurs, they're removed. This prevents stale setups.

---

## 9. Buy Signals — How Stocks Get Selected

### The Problem with a Simple Screener

Running `vcp screen run` gives you 50 VCP candidates. But these are stocks that are *forming* a VCP pattern — they haven't necessarily broken out yet. Buying a stock that's still consolidating means you're entering too early, before the market has confirmed the breakout. This is exactly why the original v1 backtest had a 23.5% win rate — it was buying candidates indiscriminately.

### The Solution: Breakout Confirmation

The `vcp screen signals` command (and the backtester internally) adds a critical second step:

```
vcp screen run          ← finds 50 stocks forming VCP patterns (candidates)
                               ↓
vcp screen signals      ← checks which of those 50 are ACTUALLY breaking out today
```

### How a Stock Gets a BUY Signal

A stock moves through 4 stages:

```
FORMING  →  NEAR PIVOT  →  ABOVE PIVOT  →  BUY
  (VCP          (within         (price >        (price > pivot
   detected,     3% of          pivot,          AND volume >=
   far from      pivot)          but volume      1.3x average)
   pivot)                        too low)
```

| Stage | What It Means | What You Do |
|-------|--------------|-------------|
| **FORMING** | VCP pattern detected but stock is still 5-30% below pivot | Ignore for now, keep running screener daily |
| **NEAR PIVOT** (within 3%) | Stock is coiling tight, breakout imminent | Add to your personal watchlist, set price alerts |
| **ABOVE PIVOT** (waiting for volume) | Price crossed pivot but volume was normal | DON'T buy yet — could be a false breakout. Wait for volume confirmation |
| **BUY** (breakout confirmed) | Price above pivot AND volume >= 1.3x average | This is your entry signal. The command shows exact shares, stop, cost |

### What the Signals Command Shows

```bash
$ vcp screen signals

🟢 BUY SIGNALS (2 stocks breaking out)
   NETWEB     — ₹3,507 (pivot ₹3,371) on 4.5x volume → Buy 7 shares, stop ₹3,156, cost ₹24,546
   JBCHEPHARM — ₹1,998 (pivot ₹1,994) on 1.6x volume → Buy 12 shares, stop ₹1,798, cost ₹23,976

🟡 ABOVE PIVOT — WAITING FOR VOLUME (21 stocks)
   GRAPHITE, GMDCLTD, ANANDRATHI, MASFIN, GPIL...
   (above their pivots but today's volume was below 1.3x average)

🔵 NEAR PIVOT — WATCHLIST (4 stocks within 3%)
   LTF (0.3% below), CCL (0.0%), MANAPPURAM (2.0%), SAIL (0.3%)

34 more stocks still forming VCP patterns

Suggested Commands:
   vcp portfolio buy NETWEB 3506.5     → 7 shares, stop ₹3,155.8, cost ₹24,546
   vcp portfolio buy JBCHEPHARM 1998.0 → 12 shares, stop ₹1,798.2, cost ₹23,976
```

### How the Backtester Uses This Same Logic

The backtester doesn't buy stocks the moment they appear on the screener. It follows the exact same process:

1. **Every 5 trading days**: Run the screener on data available up to that day → get candidates with pivot prices
2. **Add candidates to a watchlist** (skip stocks already on the watchlist or already held)
3. **Every day**: Check the watchlist — did any stock close above its pivot on 1.3x+ volume?
4. **If yes**: Enter the position (highest VCP score first, up to 5 positions)
5. **If no breakout in 20 days**: Remove from watchlist (pattern is stale)

This is why the breakout confirmation configs (D4, G3, F3) dramatically outperformed the non-confirmation configs in the 126-backtest sweep. Without confirmation, you enter too many trades that never actually break out and hit your stop loss.

### Why 1.3x Volume (and not 1.5x or 2x)

We tested three thresholds across 6 market periods:

| Volume Threshold | Avg Return | Trades | Win Rate |
|-----------------|-----------|--------|----------|
| 1.0x (no confirmation) | +7-11% | Many | ~40% |
| **1.3x** | **+15-18%** | Moderate | **~44%** |
| 1.5x | +10-12% | Fewer | ~48% |

- **1.0x** enters too many false breakouts → lots of stop-loss hits
- **1.5x** is too strict for Indian mid-caps — many valid breakouts happen on 1.2-1.4x volume, and you miss them
- **1.3x** is the sweet spot — filters out low-conviction breakouts while still catching the real moves

---

## 10. How We Adapted Minervini for India

Mark Minervini's original strategy was designed for US large-cap stocks (S&P 500 universe). The Indian NSE market behaves differently in several key ways:

| Characteristic | US Market | Indian Market | Our Adaptation |
|---------------|-----------|---------------|----------------|
| Trend speed | Slow (multi-year trends) | Fast (6-12 month cycles) | Faster SMAs: 20/50/100 instead of 50/150/200 |
| Volatility | Lower (~1-2% daily swings) | Higher (~2-4% daily swings) | 10% stop loss instead of 7-8% US standard |
| Momentum persistence | Gradual, sustained | Sharp, shorter bursts | RS weights: 50/25/15/10 (more recency) vs 40/20/20/20 |
| Breakout quality | Cleaner, more institutional | Noisier, operator-driven | Added breakout volume confirmation (1.3x) |
| Winner behavior | Steady 20-30% runs | Explosive 40-80% runs then sharp reversals | Wide trailing stop: trigger at +30%, 12% trail |
| Stocks in universe | ~500 large caps | ~2200 (many small caps) | No price cap (let position sizing handle it) |

### Key Decisions and Their Evidence

**Decision: Wide trailing stop (30% trigger, 12% trail)**
- The original Minervini triggers the trail at +25% with a 10% trail
- Indian mid-caps frequently gap 5-8% on news. A 10% trail after a 25% gain gets stopped on normal volatility
- By waiting until +30% and using a 12% trail, we let the explosive Indian runners reach +40-50% before trailing
- **Evidence:** Config G3 (wide trail) averaged +18.2% vs G1 (original trail) at +9.9% across 6 periods

**Decision: No price cap**
- Initially we capped at Rs 500 for a Rs 1 lakh portfolio
- This blocked stocks like WOCKPHARMA (+36% winner), TRF (+38% winner), SOLARINDS (+14% winner)
- Position sizing automatically handles expensive stocks (fewer shares, same risk)
- **Evidence:** Removing the cap immediately improved returns from +1% to +9-18%

**Decision: 5 positions, not 3 or 6**
- With Rs 1 lakh, 3 positions means only 3 chances to catch a winner per screening cycle
- 6 positions dilutes each position too much (Rs 16,666 per position, hard to buy round lots)
- 5 positions = ~Rs 20,000 per position, enough for meaningful sizing, enough diversity to catch winners
- **Evidence:** 4-5 position configs consistently outperformed 3 and 6 position configs

---

## 11. Parameter Optimization — The 126-Backtest Sweep

We built `param_sweep.py` to systematically test 21 parameter configurations across 6 different market periods (126 total backtests) with Rs 1,00,000 starting capital.

### Configs Tested

| Group | What Changed | Configs |
|-------|-------------|---------|
| A | Original Minervini (baseline) | 50/150/200 SMA, 10% stop, 25% trail trigger |
| B | Fast SMAs only | 20/50/100 SMA, everything else original |
| C | Fast SMAs + recency RS | Added 50/25/15/10 RS weights |
| D | Breakout confirmation variants | 1.3x and 1.5x volume thresholds |
| E | Tighter stops (8%) | With and without breakout confirmation |
| F | Aggressive (3% risk, more positions) | Higher concentration bets |
| G | Wide trailing stops | 30% trigger, 12% trail |
| H | Kitchen sink combos | Multiple changes combined |

### Market Periods Tested

| Period | Dates | Market Character |
|--------|-------|-----------------|
| 2022 Bull | Jun-Dec 2022 | Post-COVID recovery rally |
| 2023 H1 | Jan-Jun 2023 | Sideways with pockets of strength |
| 2023 H2 | Jul-Dec 2023 | Strong bull run |
| 2024 Bull | Jan-Sep 2024 | Broad-based rally |
| 2024 H2 Correction | Oct 2024 - Mar 2025 | Market pullback |
| 2025 Recent | Apr 2025 - Feb 2026 | Mixed/cautious |

### Full Results Table

| Rank | Config | Avg Return | Best Period | Worst Period | Max DD | Sharpe | Win Rate | Profit Factor |
|------|--------|-----------|------------|-------------|--------|--------|----------|---------------|
| 1 | **G3: Fast SMA + Wide Trail + Breakout** | **+18.2%** | +46.1% | -22.2% | 27.5% | 1.55 | 43.8% | 4.24 |
| 2 | D4: Breakout 1.3x volume | +16.8% | +40.3% | -7.5% | 18.6% | **1.69** | 48.8% | 3.41 |
| 3 | F3: Aggressive + Breakout | +15.7% | +41.9% | -11.3% | 23.1% | 1.33 | 48.0% | 2.96 |
| 4 | C2: Fast SMA + Recency, 4 pos | +14.9% | +32.7% | -7.4% | 19.0% | 1.63 | **52.5%** | **5.55** |
| 5 | B2: Fast SMA, 4 pos | +13.6% | +31.8% | -7.9% | 21.3% | 1.57 | 50.4% | 4.83 |
| 6 | E2: Fast + 8% stop | +13.5% | +28.2% | -6.6% | 19.4% | 1.31 | 35.0% | 2.19 |
| 7 | F2: Aggressive 6 pos | +12.4% | +40.7% | -11.0% | 23.3% | 1.10 | 38.8% | 2.19 |
| 8 | G2: Fast + Wide trail | +11.6% | +26.8% | -13.7% | 21.2% | 1.28 | 41.6% | 2.69 |
| ... | | | | | | | | |
| 20 | A1: Original Minervini | +7.0% | +23.7% | -9.0% | 19.4% | 0.97 | 39.9% | 1.99 |
| 21 | E1: 8% stop (original SMA) | +3.6% | +24.6% | -15.2% | 24.2% | 0.35 | 31.4% | 1.46 |

### What the Winner (G3) Does Differently

```
SMAs:              20 / 50 / 100   (fast — catches Indian trends early)
RS Weights:        50% / 25% / 15% / 10%  (heavy recency bias)
Stop Loss:         10%             (standard — not too tight for Indian volatility)
Breakeven Trigger: +15%            (move stop to entry after solid gain)
Trail Trigger:     +30%            (wide — let winners run to 30%+ before trailing)
Trail Size:        12%             (wide trail — don't get shaken out by 5-8% daily swings)
Breakout Confirm:  1.3x volume     (filter false breakouts)
Max Positions:     5               (balanced for Rs 1 lakh)
Risk Per Trade:    2.5%            (Rs 2,500 risk per trade)
```

### Key Takeaways from the Sweep

1. **Fast SMAs universally outperform original SMAs** — every fast SMA config beat its corresponding original SMA config
2. **Breakout confirmation is the single most impactful change** — adds +5-7% avg return and dramatically reduces false entries
3. **8% stops are too tight for India** — the 8% stop configs ranked near the bottom. Indian stocks routinely swing 5-7% intraday. 10% gives breathing room
4. **Wide trailing stops > tight trailing stops** — the wide trail lets Indian mid-cap runners reach their full potential (+40-80%) instead of locking in +15-20%
5. **Recency RS adds +2-3%** on average, most impactful in fast-moving bull markets

---

## 12. Backtest Results

### 2024 Bull Market (Jan - Sep 2024) — Original Strategy (5L capital, 5 positions)

| Metric | Value |
|--------|-------|
| Initial Capital | Rs 5,00,000 |
| Final Capital | Rs 5,84,364 |
| **Total Return** | **+16.9%** |
| CAGR | 23.2% |
| Max Drawdown | 12.8% |
| Total Trades | 36 |
| Win Rate | 41.7% |
| Profit Factor | 2.12 |
| Avg Winner | +19.6% |
| Avg Loser | -7.3% |

**Top winners:** ADANIPOWER +41.8%, TRF +38.4%, WOCKPHARMA +36.3%, TEXRAIL +31.5%, ELGIRUBCO +27.6%

### Nov 2025 - Feb 2026 (Correction period)

| Metric | Value |
|--------|-------|
| **Total Return** | **-10.3%** |
| Market Regime | CAUTIOUS |
| Win Rate | 23.5% |
| 10 of 13 losses | Hit exact -10% stop |

**Lesson:** VCP is a trend-following strategy. It loses money in corrections. This is by design — the small controlled losses (-10% stops with 2.5% risk = -2.5% of capital per loss) are the cost of being positioned for the big winners when the market turns.

### Optimized Strategy — Period-by-Period Performance (Rs 1L, G3 config)

| Period | Return | Trades | Win Rate | Profit Factor | Max DD |
|--------|--------|--------|----------|---------------|--------|
| 2022 Bull | +28.1% | 16 | 50.0% | 7.78 | 9.8% |
| 2023 H1 | +13.8% | 18 | 38.9% | 2.15 | 6.3% |
| 2023 H2 | **+46.1%** | 18 | 61.1% | 7.96 | 9.4% |
| 2024 Bull | +22.1% | 29 | 41.4% | 2.72 | 16.3% |
| 2024 H2 Correction | -22.2% | 35 | 11.4% | 0.23 | 27.5% |
| 2025 Recent | +21.4% | 10 | 60.0% | 4.60 | 7.5% |
| **Average** | **+18.2%** | | **43.8%** | **4.24** | |

---

## 13. Portfolio Management System

### Position Sizing Formula

```
Shares to Buy = (Account Size × 2.5%) / (Entry Price - Stop Price)
```

**Example with Rs 1 lakh account:**
- Entry price: Rs 200
- Stop loss: Rs 180 (10% below)
- Risk amount: Rs 1,00,000 × 2.5% = Rs 2,500
- Risk per share: Rs 200 - Rs 180 = Rs 20
- Shares: Rs 2,500 / Rs 20 = 125 shares
- Total cost: 125 × Rs 200 = Rs 25,000 (25% of account)

**Why 2.5% risk:** With 5 positions, if ALL 5 hit their stops simultaneously (worst case), you lose 5 × 2.5% = 12.5% of your account. Survivable and recoverable.

### Trailing Stop Progression

| Stock Gain | What Happens | Why |
|-----------|-------------|-----|
| 0% to +15% | Hold initial stop (10% below entry) | Give the trade room to develop |
| +15% reached | Move stop to breakeven (entry price) | Eliminate risk of loss on this trade |
| +30% reached | Activate 12% trailing stop from highest price | Lock in profits while letting the trend continue |
| If highest was +40% | Trail at Rs highest × 0.88 | Won't let a +40% winner become less than +25% |

The stop **never moves down**, only up. If the stock makes a new high, the trailing stop ratchets up.

### Sell Alert Signals

The system checks for 5 sell conditions:

1. **Stop loss hit** — price dropped below initial stop
2. **Trailing stop hit** — price dropped below trailing stop
3. **High-volume decline** — 4%+ down day on 1.5x average volume (institutions dumping)
4. **Exhaustion gap** — stock gaps up but closes near the day's low (blow-off top)
5. **20% gain protection** — if a stock ever gained 20%+, never let it become a loss

---

## 14. Backtester Architecture

### Why Event-Driven

The backtester processes one day at a time, simulating exactly what you'd do in real life:

```
For each trading day:
  1. Check all open positions for stop-loss/trailing stop triggers
  2. Check watchlist for breakout confirmations (price > pivot on 1.3x volume)
  3. Remove stale watchlist entries (> 20 days old)
  4. Every 5 days: run the screener on data available UP TO today
  5. Add new screener candidates to the watchlist
  6. Record portfolio equity value
```

### No Look-Ahead Bias

On day X, the screener only sees data from the beginning of history up to day X. It cannot access day X+1 prices. This is critical — many backtests cheat by using future data (e.g., "buy at today's close" when you wouldn't know the close until after market hours).

Our entries are on the breakout day's close (confirmed after the fact) or the next day's open — both realistic execution prices.

### Metrics Computed

| Metric | Formula | What It Tells You |
|--------|---------|------------------|
| Total Return % | (Final - Initial) / Initial × 100 | Overall profitability |
| CAGR % | (Final/Initial)^(1/years) - 1 | Annualized return (comparable across time periods) |
| Max Drawdown % | Largest peak-to-trough decline in equity | Worst-case pain level |
| Sharpe Ratio | Mean(daily returns) / StdDev(daily returns) × √252 | Risk-adjusted return. > 1.0 = good, > 2.0 = excellent |
| Win Rate % | Winners / Total Trades × 100 | What % of trades make money |
| Profit Factor | Gross Gains / Gross Losses | How much you make per rupee lost. > 2.0 = strong edge |

---

## 15. Configuration Reference

All settings live in `config.py`. Override any setting with an environment variable prefixed with `VCP_`.

### Current Optimized Settings (G3 Config)

```python
# Pre-filter
min_price = 50.0          # Skip penny stocks
max_price = 0             # No cap (position sizing handles it)
min_avg_volume = 100_000  # Need liquidity
min_trading_days = 200    # ~10 months of data

# Relative Strength (recency-biased)
rs_weight_3m = 0.50       # Recent momentum matters most
rs_weight_6m = 0.25
rs_weight_9m = 0.15
rs_weight_12m = 0.10

# Trend Template (fast SMAs)
sma_short = 20            # Short-term trend
sma_mid = 50              # Medium-term trend
sma_long = 100            # Long-term trend

# Breakout Confirmation
breakout_volume_mult = 1.3  # 30% above average volume
breakout_watchlist_expiry_days = 20

# Portfolio
account_size = 100_000    # Rs 1 lakh
risk_per_trade_pct = 2.5  # Rs 2,500 risk per trade
max_positions = 5
default_stop_loss_pct = 10.0
breakeven_trigger_pct = 15.0
trailing_stop_trigger_pct = 30.0  # Wide trail
trailing_stop_pct = 12.0          # Wide trail
```

### How to Override

```bash
# Increase capital
export VCP_ACCOUNT_SIZE=500000

# Use safer D4 config (lower drawdown)
export VCP_TRAILING_STOP_TRIGGER_PCT=25
export VCP_TRAILING_STOP_PCT=10

# Tighter RS filter
export VCP_MIN_RS_PERCENTILE=80

# Then run
vcp screen run
```

---

## 16. Daily Workflow — Manual & Automated

### Option A: Fully Automated (Recommended)

Set up Telegram once (Section 5), then start the scheduler:

```bash
vcp alert schedule
```

Every day at 4:15 PM IST, you receive a Telegram message with:
- Buy signals (confirmed breakouts with exact entry/stop/shares)
- Sell alerts (positions that need action)
- Portfolio summary (all positions with P&L)

You just open Telegram, read the alert, and place orders on your broker app. That's it.

**To keep it running permanently:**

macOS:
```bash
nohup vcp alert schedule > ~/vcp-screener/data/scheduler.log 2>&1 &
```

Windows: Use Task Scheduler (see Section 2, Step 9).

### Option B: Manual (CLI)

If you prefer running things yourself each evening after 3:30 PM:

```bash
# 1. Update data (2 minutes)
vcp data update

# 2. Run screener (30 seconds)
vcp screen run

# 3. Check buy signals — THE MOST IMPORTANT COMMAND
vcp screen signals
# Shows:
#   🟢 BUY — confirmed breakouts (with exact entry, stop, shares)
#   🟡 ABOVE PIVOT — waiting for volume surge (don't buy yet)
#   🔵 NEAR PIVOT — add to watchlist, breakout imminent
#   ⚪ FORMING — still building the pattern, not ready

# 4. Check existing positions for sell alerts
vcp portfolio alerts
vcp portfolio holdings

# 5. If there's a BUY signal, the command gives you the exact command:
vcp portfolio buy NETWEB 3507
# (auto-calculates: 7 shares, stop ₹3,156, cost ₹24,546)

# 6. Examine a stock visually before buying
vcp screen detail NETWEB

# 7. If selling (position ID from holdings)
vcp portfolio sell 3 750 --reason "trailing stop"

# 8. (Optional) Open dashboard for charts
vcp dashboard
```

### Option C: Manual + Telegram Push

Run things yourself but still get the report on Telegram:

```bash
vcp data update && vcp screen run && vcp alert now
```

This updates data, runs the screener, and sends the full report to Telegram in one line.

---

## 17. Code Walkthrough — Every File Explained

### `config.py`
**Purpose:** Single source of truth for all parameters. Uses `pydantic-settings` for type validation and environment variable support.

**Why Pydantic Settings:** Every parameter has a Python type (`float`, `int`, `Path`) and a default value. If you set `VCP_ACCOUNT_SIZE=abc`, Pydantic throws a validation error instead of silently breaking. The `model_post_init` method auto-creates the data directory and builds the database URL.

### `db.py`
**Purpose:** Creates the SQLAlchemy engine and session factory.

**Key design:** `init_db()` imports all model modules and calls `Base.metadata.create_all(engine)` — this creates any missing tables without destroying existing data. The `get_session()` function returns a new session for each operation (no global state).

### `models/stock.py`
**Purpose:** Stores the master list of NSE stocks.

**Schema:** `symbol` (primary key), `name`, `sector`, `industry`, `is_active`, `last_updated`. The `is_active` flag allows soft-deleting stocks that get delisted.

### `models/daily_price.py`
**Purpose:** Stores OHLCV data — one row per stock per trading day.

**Key detail:** Has a `UniqueConstraint("symbol", "date")` — this lets us use SQLite's `INSERT OR REPLACE` (via `on_conflict_do_update`) for upserts. When we re-download data, it updates existing rows instead of creating duplicates.

### `models/screening_result.py`
**Purpose:** Persists screening output so the dashboard can display historical results.

**The `details` column** is a JSON field that stores the full contraction data and trend template conditions. SQLAlchemy serializes Python dicts to JSON automatically.

### `models/portfolio.py`
**Purpose:** Tracks real positions — what you actually bought and sold.

**Design:** `is_open` flag separates current holdings from closed trades. `trailing_stop` and `highest_price` are updated by the `update_trailing_stops()` function.

### `models/backtest.py`
**Purpose:** Three tables — `backtest_runs` (summary), `backtest_trades` (individual trades), `backtest_equity` (daily equity curve). This separation lets the dashboard display equity charts from past backtest runs.

### `services/data_fetcher.py`
**Purpose:** Downloads all data from two sources.

**NSE stock list:** Downloads CSV from `archives.nseindia.com`. Falls back to an alternate URL if the primary fails (NSE changes URLs occasionally).

**OHLCV data:** Uses `yfinance.download()` with batch mode (50 tickers per call). Each NSE symbol gets a `.NS` suffix (e.g., `TRENT` → `TRENT.NS`). Downloads are chunked to avoid Yahoo Finance rate limits (2-second delay between batches).

**Database writes:** Uses SQLite's upsert mechanism via SQLAlchemy's `on_conflict_do_update`. Inserts are chunked at 500 rows to avoid SQLite's variable limit (which we hit with 5 years × 50 stocks per batch).

### `services/indicators.py`
**Purpose:** Pure mathematical functions with no database dependency.

**`sma()`** — pandas rolling mean. Used everywhere for trend detection.

**`compute_rs_raw()`** — Calculates weighted multi-timeframe returns. Uses configurable weights from settings so the parameter sweep can test different weights without changing code.

**`compute_rs_percentiles()`** — Converts raw scores to 0-100 percentile using `scipy.stats.percentileofscore(kind="rank")`. The `kind="rank"` parameter means tied scores get averaged ranks (not arbitrary ordering).

### `services/trend_template.py`
**Purpose:** Implements the 8-point filter using configurable SMA periods.

**Why all 8 must pass:** This is Minervini's core insight — one or two conditions passing is noise. All 8 passing simultaneously means every timeframe (short, medium, long) agrees the stock is in a strong uptrend. It's like a panel of 8 judges all saying "yes".

### `services/vcp_detector.py`
**Purpose:** The most complex service — pattern detection in price data.

**`find_swing_highs/lows()`** — Wraps `scipy.signal.argrelextrema()`. The `order=5` parameter means we look 5 bars left and 5 bars right. This balances sensitivity (catching real swings) with noise rejection (ignoring 1-2 day fluctuations).

**`detect_contractions()`** — The core loop: pair swing highs with nearby swing lows, measure range, check each is smaller than the previous. Returns a structured dict with all contraction data.

**`score_vcp()`** — Converts qualitative pattern quality into a 0-100 score using 5 weighted components. The weights were chosen based on which pattern characteristics correlate most with successful breakouts in the literature.

### `services/screener.py`
**Purpose:** Orchestrates the full pipeline. Loads data, runs each filter in sequence, saves results. Also generates actionable buy signals.

**`run_screening()`** — Runs the full 6-step pipeline. Loads all price data from DB once, then runs filters in-memory. The pre-filter is intentionally first because it's the cheapest computation. The expensive VCP detection only runs on ~50-150 stocks that pass the trend template. Results are saved to the DB (old results for the same date are deleted first to prevent duplicates).

**`get_buy_signals()`** — Takes the last screening results and checks each candidate's current price against its pivot price and today's volume against its 50-day average. Classifies each into BUY (confirmed breakout), WATCH_VOLUME (above pivot, low volume), NEAR_PIVOT (within 3%), or FORMING (still building). For BUY signals, it calculates the exact entry price, stop loss, number of shares, and total cost based on account size and risk settings. This is the same logic the backtester uses internally — making the live tool and the backtest behave identically.

**`get_stock_detail()`** — Deep analysis of a single stock for the Stock Detail page.

### `services/portfolio_manager.py`
**Purpose:** All position management logic.

**`calculate_position_size()`** — The Kelly-criterion-inspired formula. It sizes positions so that your max loss per trade is exactly `risk_per_trade_pct` of your account.

**`update_trailing_stops()`** — Iterates all open positions, checks current price, ratchets trailing stops up. The stop never moves down.

**`check_sell_alerts()`** — Checks 5 different sell conditions. Returns a list of alerts with the specific trigger.

### `services/backtester.py`
**Purpose:** Event-driven historical simulation.

**The watchlist mechanism:** When the screener runs (every 5 days), candidates go into `self.watchlist` with their pivot price and average volume. On every subsequent day, `_check_breakouts()` scans the watchlist for stocks that closed above their pivot on 1.3x+ volume. Only confirmed breakouts get entered.

**`_check_stops()`** — Uses the day's LOW to check if any stop was triggered. This is conservative — in real life, an intraday wick might hit your stop even if the stock recovers by close.

### `services/market_regime.py`
**Purpose:** Downloads Nifty 50 data and classifies the market.

**Why Nifty 50:** It's the benchmark for the Indian market. When Nifty is in a downtrend, ~80% of stocks fall regardless of their individual quality. A VCP breakout in a falling market has much lower odds of success.

### `services/alerts.py`
**Purpose:** Telegram bot integration for push notifications.

**`send_alert(text)`** — Sync wrapper that sends an HTML-formatted message via the Telegram Bot API. Uses `python-telegram-bot` library. Handles the async/sync bridge automatically.

**`format_buy_signals_alert()`** — Converts the buy signals list into a rich Telegram message with emoji-coded signal types (BUY/WATCH/NEAR/FORMING), entry/stop/cost details, and volume ratios.

**`format_sell_alerts()`** — Formats sell alert data (stop hit, trailing stop, climax top) with position details and P&L.

**`send_daily_report()`** — Combines buy signals + sell alerts + portfolio summary into one message. Splits across multiple messages if it exceeds Telegram's 4096 character limit.

**Why `python-telegram-bot`:** It's the official Python wrapper for Telegram's Bot API. Handles authentication, message formatting (HTML parse mode), and error handling. The async API is wrapped in a sync function since our scheduler runs synchronously.

### `cli/main.py`
**Purpose:** User-facing terminal interface with 6 command groups: `data`, `screen`, `portfolio`, `backtest`, `alert`, `dashboard`.

**Click groups:** `@cli.group()` creates nested commands (`vcp data download`, `vcp screen signals`). Each command is a function decorated with `@group.command()`.

**Rich formatting:** `Table()`, `Panel()`, and color markup (`[green]...[/]`) create professional terminal output.

### `dashboard/app.py`
**Purpose:** Streamlit entry point. A `st.sidebar.radio()` for navigation, then conditional imports for each page.

### `dashboard/components/charts.py`
**Purpose:** Plotly chart builders used across pages.

**`candlestick_chart()`** — Creates a 2-panel figure (candlestick + volume) using `make_subplots()`. Adds SMA lines, VCP contraction boxes (`add_shape(type="rect")`), and pivot line (`add_hline()`).

**`equity_curve_chart()`** — 2-panel equity + drawdown chart for backtest results.

### `scheduler/daily_job.py`
**Purpose:** Runs the full pipeline automatically at 4:15 PM IST.

**Why 4:15 PM:** NSE closes at 3:30 PM. yfinance data for the day is typically available by 4:00-4:10 PM. 4:15 PM gives a safety margin.

---

## 18. Testing

```bash
# Run all 18 tests
cd ~/vcp-screener
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=vcp_screener --cov-report=term-missing
```

### What's Tested

| Test File | Tests | What It Validates |
|-----------|-------|------------------|
| `test_indicators.py` | 6 | SMA calculation, RS raw/percentile scoring, volume averages |
| `test_trend_template.py` | 3 | Strong uptrend passes, insufficient data fails, low RS fails condition 8 |
| `test_vcp_detector.py` | 6 | Swing detection with sinusoidal data, VCP detection with synthetic contracting pattern, scoring, edge cases |
| `test_portfolio.py` | 3 | Position sizing math, stop-above-entry rejection |

### Synthetic VCP Data in Tests

`test_vcp_detector.py` generates a realistic VCP pattern programmatically:
1. Run-up phase: linear rise from 100 to 150
2. Contraction 1: 150 → 130 → 148 (range: 20)
3. Contraction 2: 148 → 138 → 147 (range: 10)
4. Contraction 3: 147 → 142 → 146 (range: 5)
5. Volume decreases across each contraction

This guarantees a known pattern exists in the data, so we can assert the detector finds it.

---

## 19. Troubleshooting

**"No active symbols found"**
→ Run `vcp data download` first to populate the database.

**"No VCP candidates found"**
→ Normal in bear markets. The trend template is intentionally strict. Check `vcp screen run` output for the market regime — if it says BEARISH, very few stocks will qualify.

**Screener finds candidates but backtest shows 0 trades**
→ The backtest needs enough historical data BEFORE the start date. If you downloaded 2 years of data (2024-2026) but try to backtest starting in 2024, there aren't 200 days of history yet. Download 5 years of data: set `VCP_HISTORY_PERIOD=5y` and re-run `vcp data download`.

**"too many SQL variables" error**
→ This was fixed by chunking database inserts at 500 rows. If you see this, make sure you have the latest `data_fetcher.py`.

**yfinance rate limiting**
→ The code uses 2-second delays between batches. If errors persist, wait 5 minutes and retry. Yahoo Finance sometimes blocks IPs temporarily.

**Dashboard won't start**
→ Run directly: `streamlit run src/vcp_screener/dashboard/app.py`
→ If Streamlit isn't found: `pip install streamlit`

**Want to reset everything**
→ `rm data/vcp_screener.db` then `vcp data download`

**Want to switch to a safer config**
→ D4 config has much smaller drawdowns (-7.5% worst vs G3's -22.2%):
```bash
export VCP_TRAILING_STOP_TRIGGER_PCT=25
export VCP_TRAILING_STOP_PCT=10
export VCP_BREAKOUT_VOLUME_MULT=1.3
vcp screen run
```

**Telegram: "vcp alert test" does nothing**
→ Check both env vars are set: `echo $VCP_TELEGRAM_BOT_TOKEN` and `echo $VCP_TELEGRAM_CHAT_ID`
→ On Windows use `echo %VCP_TELEGRAM_BOT_TOKEN%`
→ Make sure you started a conversation with your bot on Telegram first (search for it by username and click Start)

**Telegram: message not received**
→ The bot token and chat ID must be exact (no spaces, no quotes in Windows `set` command)
→ Try `vcp alert test` and check the terminal for error messages
→ Common issue: the chat ID is wrong. Re-check with @userinfobot

**Telegram: "Forbidden: bot was blocked by the user"**
→ You blocked your own bot. Go to the bot in Telegram, click the 3-dot menu, and Unblock

**Windows: "vcp" command not found**
→ Use `python -m vcp_screener.cli.main` instead of `vcp`
→ Or add Python Scripts to PATH: `set PATH=%PATH%;%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts`

**Windows: pip install fails with "build wheel" errors**
→ Install Visual C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/
→ Select "Desktop development with C++" workload
→ Retry `pip install -e ".[dev]"`

**Windows: "ModuleNotFoundError" when running vcp**
→ Make sure you ran `pip install -e ".[dev]"` from the `vcp-screener` directory
→ Check you're using the same Python: `python -c "import vcp_screener"` should not error
