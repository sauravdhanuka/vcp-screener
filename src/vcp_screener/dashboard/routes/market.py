"""Market overview route — GET /market."""

from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/market")
async def market_page(request: Request):
    from vcp_screener.dashboard.services.data_bridge import get_market_data

    data = await get_market_data()

    return templates.TemplateResponse(
        "pages/market.html",
        {
            "request": request,
            "active_nav": "market",
            "regime": data["regime"] if data else {},
            "nifty": data["nifty_chart"] if data else None,
        },
    )
