"""API routes — mutations and actions (POST/DELETE endpoints)."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from vcp_screener.dashboard.services.data_bridge import (
    clear_screening_cache,
    clear_watchlist_cache,
)

router = APIRouter(prefix="/api")


@router.post("/screen-now")
async def screen_now(request: Request):
    """Trigger a screening run. Redirects to screener page on completion."""
    from vcp_screener.services.data_fetcher import download_ohlcv, get_active_symbols
    from vcp_screener.services.portfolio_manager import save_equity_snapshot
    from vcp_screener.services.screener import run_all_screens

    def _run():
        symbols = get_active_symbols()
        if symbols:
            download_ohlcv(symbols, period="5d", batch_size=100, batch_delay=0.5)
        run_all_screens()
        save_equity_snapshot()

    await asyncio.to_thread(_run)
    clear_screening_cache()

    response = HTMLResponse("")
    response.headers["HX-Redirect"] = "/"
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Screening complete!", "type": "success"}}'
    return response


@router.post("/signals/{symbol}/add-watchlist")
async def add_signal_to_watchlist(symbol: str, request: Request):
    """Add a symbol from the signals page to the default watchlist."""
    from vcp_screener.services.watchlist_service import add_to_watchlist

    await asyncio.to_thread(add_to_watchlist, symbol.upper(), strategy="vcp")
    clear_watchlist_cache()

    return HTMLResponse(
        content=(
            '<span class="px-2 py-1 text-xs rounded border border-accent-green '
            'text-accent-green">Added</span>'
        ),
        headers={
            "HX-Trigger": '{"showToast": {"message": "Added '
            + symbol
            + ' to Watchlist", "type": "success"}}'
        },
    )
