"""FastAPI dashboard entry point — replaces Streamlit app."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vcp_screener.db import init_db

DASHBOARD_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))


# Custom Jinja2 filters for currency/number formatting
def _currency(value, decimals=0, sign=False):
    """Format number as currency with commas. sign=True adds +/- prefix."""
    try:
        fmt = f"{value:+,.{decimals}f}" if sign else f"{value:,.{decimals}f}"
        return fmt
    except (ValueError, TypeError):
        return str(value)


def _signed(value, decimals=1):
    """Format number with +/- sign and commas."""
    try:
        return f"{value:+,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


templates.env.filters["currency"] = _currency
templates.env.filters["signed"] = _signed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="VCP Screener", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR / "static")), name="static")

# Import and include routers
from vcp_screener.dashboard.routes import (  # noqa: E402
    screener,
    stock,
    signals,
    portfolio,
    watchlist,
    market,
    api,
)

app.include_router(screener.router)
app.include_router(stock.router)
app.include_router(signals.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(market.router)
app.include_router(api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
