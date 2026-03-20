"""Stock detail route — GET /stock/{symbol}."""

import json

from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/stock/{symbol}")
async def stock_detail_page(request: Request, symbol: str):
    from vcp_screener.dashboard.services.data_bridge import get_stock_detail

    detail = await get_stock_detail(symbol.upper())

    # Serialize OHLCV data for Lightweight Charts
    chart_data_json = "[]"
    volume_data_json = "[]"
    sma_data = {}
    if detail and detail.get("price_data") is not None:
        df = detail["price_data"]
        chart_data = []
        volume_data = []
        for date, row in df.iterrows():
            ts = date.strftime("%Y-%m-%d")
            chart_data.append({
                "time": ts,
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
            })
            color = "#22c55e80" if row["close"] >= row["open"] else "#ef444480"
            volume_data.append({
                "time": ts,
                "value": int(row["volume"]),
                "color": color,
            })
        chart_data_json = json.dumps(chart_data)
        volume_data_json = json.dumps(volume_data)

        # Precompute SMAs
        close = df["close"]
        for period in [20, 50, 100, 200]:
            if len(close) >= period:
                sma = close.rolling(period).mean()
                sma_data[period] = json.dumps([
                    {"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                    for d, v in sma.items() if not (v != v)  # skip NaN
                ])

    return templates.TemplateResponse(
        "pages/stock_detail.html",
        {
            "request": request,
            "active_nav": "screener",
            "symbol": symbol.upper(),
            "detail": detail,
            "chart_data_json": chart_data_json,
            "volume_data_json": volume_data_json,
            "sma_data": sma_data,
        },
    )
