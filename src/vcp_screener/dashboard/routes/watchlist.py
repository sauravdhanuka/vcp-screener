"""Watchlist routes — numbered watchlists with add/remove mutations."""

import asyncio

from fastapi import APIRouter, Form, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


# ---------------------------------------------------------------------------
# Full page
# ---------------------------------------------------------------------------


@router.get("/watchlist")
async def watchlist_page(request: Request):
    from vcp_screener.dashboard.services.data_bridge import (
        get_watchlist,
        get_watchlist_numbers,
    )

    numbers = await get_watchlist_numbers()
    active_list = numbers[0] if numbers else 1
    items = await get_watchlist(active_list)

    return templates.TemplateResponse(
        "pages/watchlist.html",
        {
            "request": request,
            "active_nav": "watchlist",
            "watchlist_numbers": numbers or [],
            "active_list": active_list,
            "items": items or [],
        },
    )


# ---------------------------------------------------------------------------
# Tab partial (switch between watchlist numbers)
# ---------------------------------------------------------------------------


@router.get("/partials/watchlist/{list_number}")
async def watchlist_items_partial(request: Request, list_number: int):
    from vcp_screener.dashboard.services.data_bridge import get_watchlist

    items = await get_watchlist(list_number)
    return templates.TemplateResponse(
        "partials/watchlist_items.html",
        {"request": request, "items": items or [], "list_number": list_number},
    )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


@router.post("/api/watchlist/add")
async def add_watchlist_api(
    request: Request,
    symbol: str = Form(...),
    list_number: int = Form(1),
    strategy: str = Form("vcp"),
    notes: str = Form(""),
):
    from vcp_screener.dashboard.services.data_bridge import (
        clear_watchlist_cache,
        get_watchlist,
    )
    from vcp_screener.services.watchlist_service import add_to_watchlist

    await asyncio.to_thread(
        add_to_watchlist,
        symbol.upper(),
        list_number=list_number,
        strategy=strategy,
        notes=notes if notes else None,
    )
    clear_watchlist_cache()

    items = await get_watchlist(list_number)
    response = templates.TemplateResponse(
        "partials/watchlist_items.html",
        {"request": request, "items": items or [], "list_number": list_number},
    )
    response.headers["HX-Trigger"] = (
        '{"showToast": {"message": "Added '
        + symbol.upper()
        + " to Watchlist #"
        + str(list_number)
        + '", "type": "success"}}'
    )
    return response


@router.delete("/api/watchlist/{item_id}")
async def delete_watchlist_api(request: Request, item_id: int):
    from vcp_screener.dashboard.services.data_bridge import (
        clear_watchlist_cache,
        get_watchlist,
        get_watchlist_numbers,
    )
    from vcp_screener.services.watchlist_service import remove_from_watchlist

    await asyncio.to_thread(remove_from_watchlist, item_id)
    clear_watchlist_cache()

    numbers = await get_watchlist_numbers()
    list_number = numbers[0] if numbers else 1
    items = await get_watchlist(list_number)
    response = templates.TemplateResponse(
        "partials/watchlist_items.html",
        {"request": request, "items": items or [], "list_number": list_number},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Removed from watchlist", "type": "success"}}'
    return response


