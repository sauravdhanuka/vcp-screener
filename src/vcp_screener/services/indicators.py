"""Technical indicators: SMA, RS rating, volume calculations."""

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def compute_rs_raw(close: pd.Series, min_days: int = None) -> float:
    """Compute raw relative strength score for a single stock.

    Uses configurable weights from settings.
    """
    from vcp_screener.config import settings

    if min_days is None:
        min_days = settings.min_trading_days
    if len(close) < min_days:
        return np.nan

    current = close.iloc[-1]
    returns = {}
    for label, days in [("3m", 63), ("6m", 126), ("9m", 189), ("12m", 252)]:
        if len(close) >= days:
            returns[label] = (current / close.iloc[-days] - 1) * 100
        else:
            returns[label] = 0.0

    raw = (
        settings.rs_weight_3m * returns.get("3m", 0)
        + settings.rs_weight_6m * returns.get("6m", 0)
        + settings.rs_weight_9m * returns.get("9m", 0)
        + settings.rs_weight_12m * returns.get("12m", 0)
    )
    return raw


def compute_rs_percentiles(rs_raw_scores: dict[str, float]) -> dict[str, float]:
    """Convert raw RS scores to percentile ranks (0-100) across all stocks."""
    symbols = list(rs_raw_scores.keys())
    scores = np.array([rs_raw_scores[s] for s in symbols])
    valid_mask = ~np.isnan(scores)
    valid_scores = scores[valid_mask]

    percentiles = {}
    for i, sym in enumerate(symbols):
        if valid_mask[i]:
            percentiles[sym] = percentileofscore(valid_scores, scores[i], kind="rank")
        else:
            percentiles[sym] = 0.0
    return percentiles


def average_volume(volume: pd.Series, period: int = 50) -> float:
    """Compute average volume over last N days."""
    if len(volume) < period:
        return volume.mean() if len(volume) > 0 else 0.0
    return volume.iloc[-period:].mean()


def volume_ratio(volume: pd.Series, short: int = 10, long: int = 50) -> float:
    """Ratio of short-term to long-term average volume."""
    if len(volume) < long:
        return 1.0
    short_avg = volume.iloc[-short:].mean()
    long_avg = volume.iloc[-long:].mean()
    if long_avg == 0:
        return 1.0
    return short_avg / long_avg


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()
