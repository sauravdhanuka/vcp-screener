"""VCP (Volatility Contraction Pattern) detection engine.

Detects base formation, swing points, contractions, volume dry-up,
and scores pattern quality.
"""

import logging

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from vcp_screener.config import settings
from vcp_screener.services.indicators import average_volume

logger = logging.getLogger(__name__)


def find_swing_highs(high: pd.Series, order: int = 5) -> pd.Series:
    """Find local maxima (swing highs) using N-bar method."""
    indices = argrelextrema(high.values, np.greater_equal, order=order)[0]
    result = pd.Series(np.nan, index=high.index)
    result.iloc[indices] = high.iloc[indices]
    return result


def find_swing_lows(low: pd.Series, order: int = 5) -> pd.Series:
    """Find local minima (swing lows) using N-bar method."""
    indices = argrelextrema(low.values, np.less_equal, order=order)[0]
    result = pd.Series(np.nan, index=low.index)
    result.iloc[indices] = low.iloc[indices]
    return result


def find_base_start(high: pd.Series, close: pd.Series, min_correction_pct: float = 10.0) -> int | None:
    """Find the start of the base: highest high before a >= min_correction_pct decline.

    Returns the integer index of the base start, or None.
    """
    # Look for the highest point followed by a correction
    peak_idx = high.idxmax()
    peak_val = high[peak_idx]
    peak_pos = high.index.get_loc(peak_idx)

    # Find lowest close after the peak
    post_peak_close = close.iloc[peak_pos:]
    if len(post_peak_close) < 5:
        return None

    trough_val = post_peak_close.min()
    correction_pct = (peak_val - trough_val) / peak_val * 100

    if correction_pct >= min_correction_pct:
        return peak_pos

    return None


def detect_contractions(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    order: int = None,
) -> dict:
    """Detect VCP contractions within price data.

    Returns dict with contractions, pivot price, and quality metrics.
    """
    if order is None:
        order = settings.swing_order

    if len(close) < 50:
        return {"found": False, "reason": "insufficient data"}

    # Find the base start
    base_start = find_base_start(high, close, settings.min_base_correction_pct)
    if base_start is None:
        return {"found": False, "reason": "no base formation found"}

    # Work with data from base start onwards
    h = high.iloc[base_start:]
    l = low.iloc[base_start:]
    c = close.iloc[base_start:]
    v = volume.iloc[base_start:]

    if len(h) < 20:
        return {"found": False, "reason": "base too short"}

    # Find swing highs and lows within the base
    swing_highs = find_swing_highs(h, order=order)
    swing_lows = find_swing_lows(l, order=order)

    sh_values = swing_highs.dropna()
    sl_values = swing_lows.dropna()

    if len(sh_values) < 2 or len(sl_values) < 2:
        return {"found": False, "reason": "not enough swing points"}

    # Measure contractions: pair consecutive swing high-low ranges
    contractions = []
    sh_list = list(sh_values.items())
    sl_list = list(sl_values.items())

    # Build contraction ranges by matching swing highs with nearby swing lows
    for i in range(len(sh_list)):
        sh_date, sh_val = sh_list[i]
        # Find the nearest swing low after this swing high
        nearby_lows = [(d, v) for d, v in sl_list if d >= sh_date]
        if not nearby_lows:
            continue

        sl_date, sl_val = nearby_lows[0]
        range_pct = (sh_val - sl_val) / sh_val * 100

        # Volume in this contraction window
        mask = (v.index >= sh_date) & (v.index <= sl_date)
        contraction_vol = v[mask].mean() if mask.any() else 0

        contractions.append({
            "high_date": sh_date,
            "high_val": float(sh_val),
            "low_date": sl_date,
            "low_val": float(sl_val),
            "range_pct": float(range_pct),
            "avg_volume": float(contraction_vol),
        })

    if len(contractions) < settings.min_contractions:
        return {"found": False, "reason": f"only {len(contractions)} contractions found"}

    # Check that contractions are getting tighter (each range smaller than previous)
    valid_contractions = [contractions[0]]
    for i in range(1, len(contractions)):
        if contractions[i]["range_pct"] < contractions[i - 1]["range_pct"]:
            valid_contractions.append(contractions[i])
        else:
            # Allow one violation then break
            if len(valid_contractions) >= settings.min_contractions:
                break
            valid_contractions.append(contractions[i])

    if len(valid_contractions) < settings.min_contractions:
        return {"found": False, "reason": "contractions not tightening"}

    # Cap contractions
    valid_contractions = valid_contractions[:settings.max_contractions]

    # Pivot price = high of the last contraction
    pivot_price = valid_contractions[-1]["high_val"]

    # Volume dry-up: compare last contraction volume to first
    first_vol = valid_contractions[0]["avg_volume"]
    last_vol = valid_contractions[-1]["avg_volume"]
    vol_dry_up = (1 - last_vol / first_vol) * 100 if first_vol > 0 else 0.0

    # Base depth: total correction from highest high to lowest low in base
    base_high = h.max()
    base_low = l.min()
    base_depth_pct = (base_high - base_low) / base_high * 100

    # Base duration in trading days
    base_duration = len(h)

    # Tightness ratio: last contraction range / first contraction range
    tightness = valid_contractions[-1]["range_pct"] / valid_contractions[0]["range_pct"] if valid_contractions[0]["range_pct"] > 0 else 1.0

    return {
        "found": True,
        "contractions": valid_contractions,
        "num_contractions": len(valid_contractions),
        "pivot_price": pivot_price,
        "base_depth_pct": base_depth_pct,
        "base_duration_days": base_duration,
        "tightness_ratio": tightness,
        "volume_dry_up_pct": vol_dry_up,
        "base_start_idx": base_start,
    }


def score_vcp(vcp_result: dict) -> float:
    """Score a VCP pattern from 0-100 based on quality metrics.

    Scoring components:
    - Contraction count (2=10, 3=25, 4+=30)       max 30
    - Tightness ratio (lower = better)             max 25
    - Volume dry-up (higher = better)              max 20
    - Base duration (40-120 days ideal)             max 15
    - Proximity to pivot (closer = better)         max 10
    """
    if not vcp_result.get("found"):
        return 0.0

    score = 0.0

    # 1. Contraction count (max 30)
    n = vcp_result["num_contractions"]
    if n >= 4:
        score += 30
    elif n == 3:
        score += 25
    elif n == 2:
        score += 10

    # 2. Tightness ratio (max 25) - lower is better
    tightness = vcp_result["tightness_ratio"]
    if tightness <= 0.3:
        score += 25
    elif tightness <= 0.5:
        score += 20
    elif tightness <= 0.7:
        score += 12
    else:
        score += 5

    # 3. Volume dry-up (max 20) - higher is better
    vol_dry = vcp_result["volume_dry_up_pct"]
    if vol_dry >= 50:
        score += 20
    elif vol_dry >= 30:
        score += 15
    elif vol_dry >= 10:
        score += 8
    else:
        score += 3

    # 4. Base duration (max 15) - 40-120 days is ideal
    dur = vcp_result["base_duration_days"]
    if 40 <= dur <= 120:
        score += 15
    elif 25 <= dur <= 180:
        score += 10
    else:
        score += 5

    # 5. Base depth (max 10) - 15-35% is ideal for NSE
    depth = vcp_result["base_depth_pct"]
    if 15 <= depth <= 35:
        score += 10
    elif 10 <= depth <= 50:
        score += 6
    else:
        score += 2

    return min(score, 100.0)
