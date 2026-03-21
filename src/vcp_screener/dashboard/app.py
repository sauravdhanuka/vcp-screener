"""FastAPI dashboard entry point — replaces Streamlit app."""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from vcp_screener.config import settings
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


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth — skips /health so Docker health checks still work."""

    SKIP_PATHS = {"/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS or not settings.dashboard_user:
            return await call_next(request)

        import base64

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                user, passwd = decoded.split(":", 1)
                if (
                    secrets.compare_digest(user, settings.dashboard_user)
                    and secrets.compare_digest(passwd, settings.dashboard_pass)
                ):
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="VCP Screener"'},
            content="Unauthorized",
        )


app.add_middleware(BasicAuthMiddleware)
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
