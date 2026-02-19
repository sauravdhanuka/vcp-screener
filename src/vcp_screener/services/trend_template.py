"""Adapted Minervini Trend Template for Indian mid/small caps.

Uses faster SMAs (20/50/100 instead of 50/150/200) to catch
trends earlier in the more volatile Indian market.
"""

import numpy as np
import pandas as pd

from vcp_screener.services.indicators import sma
from vcp_screener.config import settings


def check_trend_template(close: pd.Series, rs_percentile: float) -> dict:
    """Check all 8 trend template conditions using configurable SMA periods.

    Returns dict with each condition's pass/fail and overall result.
    """
    min_data = max(settings.sma_long, 252)  # Need at least sma_long or 252 for 52w
    if len(close) < min_data:
        return {"passes": False, "conditions": {}, "reason": "insufficient data"}

    current_price = close.iloc[-1]
    sma_short = sma(close, settings.sma_short)
    sma_mid = sma(close, settings.sma_mid)
    sma_long = sma(close, settings.sma_long)

    sma_short_val = sma_short.iloc[-1]
    sma_mid_val = sma_mid.iloc[-1]
    sma_long_val = sma_long.iloc[-1]

    # 52-week high and low
    week_52_high = close.iloc[-252:].max()
    week_52_low = close.iloc[-252:].min()

    # Long SMA trending up for >= 1 month
    sma_long_recent = sma_long.dropna()
    trend_days = settings.sma_long_trend_days
    if len(sma_long_recent) >= trend_days:
        sma_long_month_ago = sma_long_recent.iloc[-trend_days]
        sma_long_trending_up = sma_long_val > sma_long_month_ago
    else:
        sma_long_trending_up = False

    conditions = {
        "1_price_above_mid_long_sma": (
            current_price > sma_mid_val and current_price > sma_long_val
        ),
        "2_mid_sma_above_long_sma": sma_mid_val > sma_long_val,
        "3_long_sma_trending_up": sma_long_trending_up,
        "4_short_sma_above_mid_long": (
            sma_short_val > sma_mid_val and sma_short_val > sma_long_val
        ),
        "5_price_above_short_sma": current_price > sma_short_val,
        "6_price_30pct_above_52w_low": (
            current_price >= week_52_low * (1 + settings.min_above_52w_low_pct / 100)
        ),
        "7_price_within_25pct_of_52w_high": (
            current_price >= week_52_high * (1 - settings.max_below_52w_high_pct / 100)
        ),
        "8_rs_percentile_above_70": rs_percentile >= settings.min_rs_percentile,
    }

    passes = all(conditions.values())
    return {"passes": passes, "conditions": conditions}
