"""Screener route — GET / (main page) + partial endpoints for HTMX."""

from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/")
async def screener_page(request: Request):
    from vcp_screener.dashboard.services.data_bridge import (
        get_screening_results,
        get_mr_results,
    )

    results = await get_screening_results()
    mr_signals = await get_mr_results()

    return templates.TemplateResponse(
        "pages/screener.html",
        {
            "request": request,
            "active_nav": "screener",
            "results": results,
            "mr_signals": mr_signals,
        },
    )


@router.get("/partials/vcp-table")
async def vcp_table_partial(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_screening_results

    results = await get_screening_results()
    return templates.TemplateResponse(
        "partials/vcp_table.html",
        {
            "request": request,
            "results": results,
        },
    )


@router.get("/partials/mr-table")
async def mr_table_partial(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_mr_results

    mr_signals = await get_mr_results()
    return templates.TemplateResponse(
        "partials/mr_table.html",
        {
            "request": request,
            "mr_signals": mr_signals,
        },
    )
