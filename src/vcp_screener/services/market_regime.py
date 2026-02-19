"""Market regime detection using Nifty 50 index."""

import logging

import pandas as pd
import yfinance as yf

from vcp_screener.services.indicators import sma

logger = logging.getLogger(__name__)

NIFTY_SYMBOL = "^NSEI"


def get_nifty_data(period: str = "1y") -> pd.DataFrame:
    """Fetch Nifty 50 OHLCV data."""
    try:
        data = yf.download(NIFTY_SYMBOL, period=period, progress=False, auto_adjust=False)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch Nifty data: {e}")
        return pd.DataFrame()


def detect_market_regime(nifty_data: pd.DataFrame = None) -> dict:
    """Detect market regime based on Nifty 50.

    Returns: dict with regime (BULLISH/CAUTIOUS/BEARISH) and details.
    """
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
        "nifty_close": float(current),
        "nifty_sma50": float(sma_50_val),
        "nifty_sma200": float(sma_200_val),
        "above_50sma": above_50,
        "above_200sma": above_200,
    }
