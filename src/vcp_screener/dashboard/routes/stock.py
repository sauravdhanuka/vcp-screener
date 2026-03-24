"""Stock detail route — GET /stock/{symbol}."""

import json

import numpy as np
from fastapi import APIRouter, Request

from vcp_screener.dashboard.app import templates

router = APIRouter()


@router.get("/stock/{symbol}")
async def stock_detail_page(request: Request, symbol: str, view: str = "vcp"):
    from vcp_screener.dashboard.services.data_bridge import (
        get_mr_results,
        get_stock_detail,
    )

    detail = await get_stock_detail(symbol.upper())

    # Fetch MR data when view=mr
    mr_data = None
    if view == "mr":
        mr_results = await get_mr_results()
        if mr_results:
            for r in mr_results:
                if r["symbol"] == symbol.upper():
                    mr_data = r
                    break

    # Serialize OHLCV data for Lightweight Charts
    chart_data_json = "[]"
    volume_data_json = "[]"
    sma_data = {}
    rsi_data_json = "[]"
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

        # Compute RSI(14) — Wilder's smoothing
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi_data_json = json.dumps([
            {"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
            for d, v in rsi.items() if not (np.isnan(v))
        ])

    return templates.TemplateResponse(
        "pages/stock_detail.html",
        {
            "request": request,
            "active_nav": "screener",
            "symbol": symbol.upper(),
            "detail": detail,
            "view": view,
            "mr_data": mr_data,
            "chart_data_json": chart_data_json,
            "volume_data_json": volume_data_json,
            "sma_data": sma_data,
            "rsi_data_json": rsi_data_json,
        },
    )
