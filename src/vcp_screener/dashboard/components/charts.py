"""Plotly chart components for the dashboard."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def candlestick_chart(
    df: pd.DataFrame,
    symbol: str,
    sma_periods: list[int] = None,
    contractions: list[dict] = None,
    pivot_price: float = None,
) -> go.Figure:
    """Create a candlestick chart with optional SMA overlays and VCP annotations."""
    if sma_periods is None:
        from vcp_screener.config import settings
        sma_periods = [settings.sma_short, settings.sma_mid, settings.sma_long]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="OHLC",
    ), row=1, col=1)

    # SMAs
    colors = {"20": "#FF6B6B", "50": "#4ECDC4", "100": "#45B7D1", "150": "#4ECDC4", "200": "#45B7D1"}
    for period in sma_periods:
        sma_vals = df["close"].rolling(period).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=sma_vals, name=f"SMA {period}",
            line=dict(width=1.5, color=colors.get(str(period), "gray")),
        ), row=1, col=1)

    # Pivot line
    if pivot_price:
        fig.add_hline(y=pivot_price, line_dash="dash", line_color="orange",
                      annotation_text=f"Pivot ₹{pivot_price:,.0f}", row=1, col=1)

    # Contraction zones
    if contractions:
        for i, c in enumerate(contractions):
            fig.add_shape(
                type="rect",
                x0=c.get("high_date"), x1=c.get("low_date"),
                y0=c["low_val"], y1=c["high_val"],
                fillcolor="rgba(255,165,0,0.1)", line=dict(color="orange", width=1),
                row=1, col=1,
            )

    # Volume bars
    colors_vol = ["red" if df["close"].iloc[i] < df["open"].iloc[i] else "green"
                  for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"], name="Volume",
        marker_color=colors_vol, opacity=0.5,
    ), row=2, col=1)

    fig.update_layout(
        title=f"{symbol} - Daily Chart",
        xaxis_rangeslider_visible=False,
        height=600,
        template="plotly_dark",
    )
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def equity_curve_chart(equity_data: list[dict]) -> go.Figure:
    """Plot equity curve with drawdown."""
    dates = [e["date"] for e in equity_data]
    equity = [e["equity"] for e in equity_data]
    drawdown = [e["drawdown_pct"] for e in equity_data]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05, row_heights=[0.7, 0.3],
    )

    fig.add_trace(go.Scatter(
        x=dates, y=equity, name="Equity",
        line=dict(color="#4ECDC4", width=2), fill="tozeroy",
        fillcolor="rgba(78,205,196,0.1)",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=drawdown, name="Drawdown %",
        line=dict(color="#FF6B6B", width=1), fill="tozeroy",
        fillcolor="rgba(255,107,107,0.2)",
    ), row=2, col=1)

    fig.update_layout(
        title="Equity Curve & Drawdown",
        height=500, template="plotly_dark",
    )
    fig.update_yaxes(title_text="Equity (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)

    return fig


def sector_heatmap(sector_data: dict[str, float]) -> go.Figure:
    """Create a sector performance heatmap."""
    sectors = list(sector_data.keys())
    values = list(sector_data.values())

    fig = go.Figure(go.Bar(
        x=values, y=sectors, orientation="h",
        marker_color=["green" if v >= 0 else "red" for v in values],
        text=[f"{v:+.1f}%" for v in values],
        textposition="auto",
    ))
    fig.update_layout(
        title="Sector Performance (1 Month)",
        height=400, template="plotly_dark",
        xaxis_title="Return %",
    )
    return fig
