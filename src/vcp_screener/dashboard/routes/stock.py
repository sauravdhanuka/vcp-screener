"""Stock detail route — GET /stock/{symbol}."""

from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/stock/{symbol}")
async def stock_detail_page(request: Request, symbol: str):
    from vcp_screener.dashboard.services.data_bridge import get_stock_detail

    detail = await get_stock_detail(symbol.upper())

    return templates.TemplateResponse(
        "pages/stock_detail.html",
        {
            "request": request,
            "active_nav": "screener",
            "symbol": symbol.upper(),
            "detail": detail,
        },
    )
