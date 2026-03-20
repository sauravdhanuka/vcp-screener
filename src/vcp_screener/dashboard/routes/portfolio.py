"""Portfolio routes — holdings, sell alerts, trade history, buy/sell mutations."""

import asyncio

from fastapi import APIRouter, Form, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


# ---------------------------------------------------------------------------
# Full page
# ---------------------------------------------------------------------------


@router.get("/portfolio")
async def portfolio_page(request: Request):
    from vcp_screener.dashboard.services.data_bridge import (
        get_holdings,
        get_sell_alerts,
        get_closed_trades,
    )
    from vcp_screener.services.portfolio_manager import get_effective_max_positions

    holdings = await get_holdings()
    alerts = await get_sell_alerts()
    closed = await get_closed_trades()
    max_positions = await asyncio.to_thread(get_effective_max_positions)

    return templates.TemplateResponse(
        "pages/portfolio.html",
        {
            "request": request,
            "active_nav": "portfolio",
            "holdings": holdings or [],
            "alerts": alerts or [],
            "closed_trades": closed or [],
            "max_positions": max_positions,
        },
    )


# ---------------------------------------------------------------------------
# Tab partials
# ---------------------------------------------------------------------------


@router.get("/partials/holdings")
async def holdings_partial(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_holdings
    from vcp_screener.services.portfolio_manager import get_effective_max_positions

    holdings = await get_holdings()
    max_positions = await asyncio.to_thread(get_effective_max_positions)
    return templates.TemplateResponse(
        "partials/holdings_list.html",
        {"request": request, "holdings": holdings or [], "max_positions": max_positions},
    )


@router.get("/partials/sell-alerts")
async def sell_alerts_partial(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_sell_alerts

    alerts = await get_sell_alerts()
    return templates.TemplateResponse(
        "partials/sell_alerts.html",
        {"request": request, "alerts": alerts or []},
    )


@router.get("/partials/trade-history")
async def trade_history_partial(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_closed_trades

    closed = await get_closed_trades()
    return templates.TemplateResponse(
        "partials/trade_history.html",
        {"request": request, "closed_trades": closed or []},
    )


@router.get("/partials/buy-form")
async def buy_form_partial(request: Request):
    return templates.TemplateResponse(
        "partials/buy_form.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


@router.post("/api/portfolio/buy")
async def buy_stock_api(
    request: Request,
    symbol: str = Form(...),
    entry_price: float = Form(...),
    stop_loss: float = Form(0),
    shares: int = Form(0),
    strategy: str = Form("vcp"),
    pivot_price: float = Form(0),
):
    from vcp_screener.dashboard.services.data_bridge import (
        clear_portfolio_cache,
        get_holdings,
    )
    from vcp_screener.services.portfolio_manager import (
        buy_stock,
        get_effective_max_positions,
    )

    pos = await asyncio.to_thread(
        buy_stock,
        symbol=symbol.upper(),
        entry_price=entry_price,
        stop_loss_price=stop_loss if stop_loss > 0 else None,
        shares=shares if shares > 0 else None,
        strategy=strategy,
        pivot_price=pivot_price if pivot_price > 0 else None,
    )
    clear_portfolio_cache()

    if pos:
        holdings = await get_holdings()
        max_positions = await asyncio.to_thread(get_effective_max_positions)
        response = templates.TemplateResponse(
            "partials/holdings_list.html",
            {"request": request, "holdings": holdings or [], "max_positions": max_positions},
        )
        response.headers["HX-Trigger"] = (
            '{"showToast": {"message": "Bought '
            + str(pos.shares)
            + " shares of "
            + pos.symbol
            + '", "type": "success"}}'
        )
        return response

    # Return error on buy form
    response = templates.TemplateResponse(
        "partials/buy_form.html",
        {"request": request, "error": "Buy failed. Max positions reached or invalid prices."},
    )
    return response


@router.post("/api/portfolio/sell/{position_id}")
async def sell_stock_api(request: Request, position_id: int):
    from vcp_screener.dashboard.services.data_bridge import (
        clear_portfolio_cache,
        get_holdings,
    )
    from vcp_screener.services.portfolio_manager import (
        get_effective_max_positions,
        sell_stock,
    )

    # Need current price from holdings
    holdings = await get_holdings()
    holding = next((h for h in holdings if h["id"] == position_id), None)
    if not holding:
        max_positions = await asyncio.to_thread(get_effective_max_positions)
        return templates.TemplateResponse(
            "partials/holdings_list.html",
            {"request": request, "holdings": holdings or [], "max_positions": max_positions},
        )

    pos = await asyncio.to_thread(sell_stock, position_id, holding["current_price"])
    clear_portfolio_cache()

    holdings = await get_holdings()
    max_positions = await asyncio.to_thread(get_effective_max_positions)
    response = templates.TemplateResponse(
        "partials/holdings_list.html",
        {"request": request, "holdings": holdings or [], "max_positions": max_positions},
    )
    if pos:
        response.headers["HX-Trigger"] = (
            '{"showToast": {"message": "Sold '
            + pos.symbol
            + " — P&L: Rs "
            + f"{pos.pnl:+,.0f}"
            + '", "type": "success"}}'
        )
    return response
