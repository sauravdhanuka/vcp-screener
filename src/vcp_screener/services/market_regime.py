"""Market regime detection using breadth (primary) and Nifty 50 (fallback).

Breadth-based detection matches the backtester logic:
  - BULLISH:  breadth >= 55%
  - CAUTIOUS: 35% <= breadth < 55%
  - BEARISH:  breadth < 35%

Where breadth = % of stocks above their 50-day SMA.
"""

import logging

import pandas as pd
import yfinance as yf

from vcp_screener.services.indicators import sma

logger = logging.getLogger(__name__)

NIFTY_SYMBOL = "^NSEI"

# Breadth thresholds (must match backtester.py regime defaults)
BULL_THRESHOLD = 55
BEAR_THRESHOLD = 35


def get_nifty_data(period: str = "1y") -> pd.DataFrame:
    """Fetch Nifty 50 OHLCV data."""
    try:
        data = yf.download(NIFTY_SYMBOL, period=period, progress=False, auto_adjust=False)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch Nifty data: {e}")
        return pd.DataFrame()


def compute_breadth(price_cache: dict[str, pd.DataFrame]) -> float:
    """Compute market breadth: % of stocks above their 50-day SMA.

    Args:
        price_cache: dict of symbol -> DataFrame with 'close' column.

    Returns:
        Breadth as a percentage (0-100).
    """
    if not price_cache:
        return 50.0  # neutral default

    above_count = 0
    total = 0
    for sym, df in price_cache.items():
        if len(df) < 50:
            continue
        close = df["close"]
        sma_50 = close.rolling(50).mean().iloc[-1]
        if pd.isna(sma_50):
            continue
        total += 1
        if close.iloc[-1] > sma_50:
            above_count += 1

    if total == 0:
        return 50.0
    return (above_count / total) * 100


def detect_market_regime(nifty_data: pd.DataFrame = None, price_cache: dict = None) -> dict:
    """Detect market regime.

    Uses breadth-based detection (matching backtester) if price_cache is provided.
    Falls back to Nifty SMA-based detection otherwise.

    Returns: dict with regime (BULLISH/CAUTIOUS/BEARISH) and details.
    """
    # Primary: breadth-based (matches backtester)
    if price_cache:
        breadth = compute_breadth(price_cache)
        if breadth >= BULL_THRESHOLD:
            regime = "BULLISH"
        elif breadth >= BEAR_THRESHOLD:
            regime = "CAUTIOUS"
        else:
            regime = "BEARISH"

        return {
            "regime": regime,
            "method": "breadth",
            "breadth_pct": round(breadth, 1),
            "bull_threshold": BULL_THRESHOLD,
            "bear_threshold": BEAR_THRESHOLD,
        }

    # Fallback: Nifty SMA-based
    if nifty_data is None or nifty_data.empty:
        nifty_data = get_nifty_data()

    if nifty_data.empty or len(nifty_data) < 200:
        return {"regime": "UNKNOWN", "details": "Insufficient data"}

    close = nifty_data["Close"].squeeze()
    current = close.iloc[-1]
    sma_50_val = sma(close, 50).iloc[-1]
    sma_200_val = sma(close, 200).iloc[-1]

    above_50 = current > sma_50_val
    above_200 = current > sma_200_val
    sma_50_above_200 = sma_50_val > sma_200_val

    if above_50 and above_200 and sma_50_above_200:
        regime = "BULLISH"
    elif above_200:
        regime = "CAUTIOUS"
    else:
        regime = "BEARISH"

    return {
        "regime": regime,
        "method": "nifty_sma",
        "nifty_close": float(current),
        "nifty_sma50": float(sma_50_val),
        "nifty_sma200": float(sma_200_val),
        "above_50sma": above_50,
        "above_200sma": above_200,
    }
