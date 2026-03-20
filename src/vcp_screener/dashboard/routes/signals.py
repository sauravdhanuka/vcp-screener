"""Signals route — GET /signals, GET /partials/signals."""

from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/signals")
async def signals_page(request: Request):
    from vcp_screener.dashboard.services.data_bridge import (
        get_buy_signals,
        get_mr_results,
    )

    signals = await get_buy_signals()
    mr_signals = await get_mr_results()

    return templates.TemplateResponse(
        "pages/signals.html",
        {
            "request": request,
            "active_nav": "signals",
            "signals": signals or [],
            "mr_signals": mr_signals or [],
            "view": "vcp",
        },
    )


@router.get("/partials/signals")
async def signals_partial(request: Request, view: str = "vcp"):
    from vcp_screener.dashboard.services.data_bridge import (
        get_buy_signals,
        get_mr_results,
    )

    if view == "mr":
        mr_signals = await get_mr_results()
        return templates.TemplateResponse(
            "partials/signal_list.html",
            {
                "request": request,
                "view": "mr",
                "signals": [],
                "mr_signals": mr_signals or [],
            },
        )
    else:
        signals = await get_buy_signals()
        return templates.TemplateResponse(
            "partials/signal_list.html",
            {
                "request": request,
                "view": "vcp",
                "signals": signals or [],
                "mr_signals": [],
            },
        )
