# Plan: Migrate Dashboard from Streamlit to FastAPI + HTMX + TradingView

## Context
The Streamlit dashboard on a GCP e2-micro VM (0.25 vCPU, 1GB RAM) is slow due to full-page reruns on every interaction, server-side chart rendering (~150MB RAM), and live computation at render time. The user wants clickable stocks with TradingView charts and faster load times. Streamlit can't do URL routing (`/stock/SYMBOL`), clickable table rows, or native TradingView embedding.

**Goal**: Replace Streamlit with FastAPI + HTMX. ~30MB RAM, instant page loads, real URL routing, TradingView charts, clickable stocks everywhere.

**What stays unchanged**: All backend services (screener, portfolio_manager, watchlist_service, market_regime, data_fetcher), DB layer, scheduler, CLI.

---

## Architecture

```
Browser (HTMX + TradingView + Chart.js + Tailwind CSS)
    ↕ HTTP (HTML fragments)
FastAPI + Jinja2 (routes → templates)
    ↕ asyncio.to_thread()
Existing services (screener.py, portfolio_manager.py, etc.)
    ↕ SQLAlchemy
SQLite DB
```

- **HTMX**: Partial page updates via HTML fragments (no JSON API, no JS framework)
- **`hx-boost="true"`** on body: All nav links swap only `<body>`, no full reload — SPA-like feel
- **TradingView widget**: Client-side iframe for stock charts (zero server cost)
- **Chart.js** via CDN: Nifty chart on market page (client-side rendering)
- **Tailwind CSS** via CDN: Dark theme matching current `#0d1117` scheme

---

## New Directory Structure

```
src/vcp_screener/dashboard/
    __init__.py
    app.py                          # FastAPI app factory + lifespan + middleware
    routes/
        __init__.py
        screener.py                 # GET /  + partials
        signals.py                  # GET /signals  + partials
        portfolio.py                # GET /portfolio  + POST mutations
        watchlist.py                # GET /watchlist  + POST/DELETE mutations
        market.py                   # GET /market
        stock.py                    # GET /stock/{symbol}
        api.py                      # POST /api/screen-now
    templates/
        base.html                   # Shared layout: nav, HTMX/Tailwind/Chart.js CDN
        pages/
            screener.html
            signals.html
            portfolio.html
            watchlist.html
            market.html
            stock_detail.html       # NEW: TradingView widget + VCP/MR analysis
        partials/                   # HTMX fragments (no <html>/<body>)
            vcp_table.html
            mr_table.html
            signal_list.html
            holdings_list.html
            sell_alerts.html
            trade_history.html
            buy_form.html
            watchlist_items.html
            regime_badge.html
            stock_vcp_details.html
            stock_mr_details.html
    services/
        __init__.py
        data_bridge.py              # Async wrappers + TTL cache (replaces st.cache_data)
    static/
        css/app.css                 # Badge styles, nav, scrollbar (rest is Tailwind)
        js/app.js                   # Toast system, tab switching, Nifty chart init
```

---

## Route Definitions

### Full Pages

| Method | URL | Template | Service Calls |
|--------|-----|----------|---------------|
| GET | `/` | screener.html | `_load_screening_results()`, `load_mr_results()` |
| GET | `/signals` | signals.html | `get_buy_signals()`, `load_mr_results()` |
| GET | `/portfolio` | portfolio.html | `get_holdings()` |
| GET | `/watchlist` | watchlist.html | `get_watchlist_numbers()`, `get_watchlist(1)` |
| GET | `/market` | market.html | `detect_market_regime()`, `get_nifty_data()` |
| GET | `/stock/{symbol}` | stock_detail.html | `get_stock_detail(symbol)` |
| GET | `/health` | JSON | — |

### HTMX Partials

| Method | URL | Partial | Purpose |
|--------|-----|---------|---------|
| GET | `/partials/vcp-table` | vcp_table.html | Refresh VCP table |
| GET | `/partials/mr-table` | mr_table.html | Refresh MR table |
| GET | `/partials/signals?view=vcp\|mr` | signal_list.html | Tab toggle |
| GET | `/partials/holdings` | holdings_list.html | Portfolio tab |
| GET | `/partials/sell-alerts` | sell_alerts.html | Portfolio tab |
| GET | `/partials/trade-history` | trade_history.html | Portfolio tab |
| GET | `/partials/buy-form` | buy_form.html | Portfolio tab |
| GET | `/partials/watchlist/{n}` | watchlist_items.html | Watchlist tab |

### Mutations

| Method | URL | Returns | Action |
|--------|-----|---------|--------|
| POST | `/api/screen-now` | Updated tables | Run screening |
| POST | `/api/portfolio/buy` | holdings_list.html | Buy stock |
| POST | `/api/portfolio/sell/{id}` | holdings_list.html | Sell position |
| POST | `/api/watchlist/add` | watchlist_items.html | Add item |
| DELETE | `/api/watchlist/{id}` | watchlist_items.html | Remove item |
| POST | `/api/signals/{symbol}/add-watchlist` | "Added" span | +WL button |

---

## Stock Detail Page (`/stock/{symbol}`)

70/30 layout. Left: TradingView Advanced Chart widget (NSE:SYMBOL, dark theme, SMAs 20/50, volume). Right: VCP score, RS percentile, trend template checklist, contraction details, MR metrics, add-to-watchlist form.

---

## Performance Comparison

| Metric | Streamlit | FastAPI + HTMX |
|--------|-----------|----------------|
| RAM | ~150MB | ~25-30MB |
| Page nav | Full script rerun | HTML fragment swap |
| Charts | Server-side Plotly (40MB) | Client-side TradingView (0MB) |
| Cold start | 15-20s | <2s |

---

## Implementation Phases

### Phase 1: Scaffold
- `app.py`, `data_bridge.py`, `base.html`, `app.css`, `app.js`, `routes/__init__.py`

### Phase 2: Build pages
1. Screener → 2. Stock Detail → 3. Signals → 4. Portfolio → 5. Watchlist → 6. Market

### Phase 3: Wire mutations
- All POST/DELETE endpoints + toast notifications

### Phase 4: Docker + CLI cutover
- uvicorn instead of streamlit, port 8000, updated Dockerfile/docker-compose

### Phase 5: Cleanup
- Delete old views/, components/, remove streamlit/plotly deps

---

## Dependency Changes

**Remove**: `streamlit>=1.28`, `plotly>=5.18`
**Add**: `fastapi>=0.115`, `uvicorn[standard]>=0.34`, `jinja2>=3.1`, `python-multipart>=0.0.9`
