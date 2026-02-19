"""Tests for VCP pattern detection."""

import numpy as np
import pandas as pd

from vcp_screener.services.vcp_detector import (
    find_swing_highs, find_swing_lows, detect_contractions, score_vcp,
)


def _make_vcp_pattern(n=200):
    """Generate synthetic price data with a VCP-like pattern."""
    np.random.seed(123)

    # Stage 1: Run up (days 0-50)
    up = np.linspace(100, 150, 50) + np.random.randn(50) * 1

    # Stage 2: Base formation with contracting ranges
    # Contraction 1: 150 -> 130 -> 148
    c1_down = np.linspace(150, 130, 25) + np.random.randn(25) * 0.5
    c1_up = np.linspace(130, 148, 20) + np.random.randn(20) * 0.5

    # Contraction 2: 148 -> 138 -> 147
    c2_down = np.linspace(148, 138, 20) + np.random.randn(20) * 0.3
    c2_up = np.linspace(138, 147, 15) + np.random.randn(15) * 0.3

    # Contraction 3: 147 -> 142 -> 146 (tight)
    c3_down = np.linspace(147, 142, 15) + np.random.randn(15) * 0.2
    c3_up = np.linspace(142, 146, 15) + np.random.randn(15) * 0.2

    # Remaining days: tight range
    remaining = n - len(up) - len(c1_down) - len(c1_up) - len(c2_down) - len(c2_up) - len(c3_down) - len(c3_up)
    flat = np.linspace(146, 148, max(remaining, 10)) + np.random.randn(max(remaining, 10)) * 0.2

    close = np.concatenate([up, c1_down, c1_up, c2_down, c2_up, c3_down, c3_up, flat])[:n]
    # Derive high/low from close
    high = close + np.abs(np.random.randn(len(close)) * 1)
    low = close - np.abs(np.random.randn(len(close)) * 1)

    # Volume: decreasing through contractions
    vol_base = 1000000
    volume = np.concatenate([
        np.random.randint(vol_base, vol_base * 2, len(up)),
        np.random.randint(int(vol_base * 0.8), int(vol_base * 1.5), len(c1_down) + len(c1_up)),
        np.random.randint(int(vol_base * 0.5), int(vol_base * 0.8), len(c2_down) + len(c2_up)),
        np.random.randint(int(vol_base * 0.2), int(vol_base * 0.4), len(c3_down) + len(c3_up)),
        np.random.randint(int(vol_base * 0.1), int(vol_base * 0.3), max(remaining, 10)),
    ])[:n]

    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return (
        pd.Series(high, index=dates),
        pd.Series(low, index=dates),
        pd.Series(close, index=dates),
        pd.Series(volume, index=dates, dtype=int),
    )


def test_find_swing_highs():
    np.random.seed(42)
    high = pd.Series(np.sin(np.linspace(0, 4 * np.pi, 100)) * 10 + 100)
    swings = find_swing_highs(high, order=5)
    non_nan = swings.dropna()
    assert len(non_nan) >= 2


def test_find_swing_lows():
    np.random.seed(42)
    low = pd.Series(np.sin(np.linspace(0, 4 * np.pi, 100)) * 10 + 100)
    swings = find_swing_lows(low, order=5)
    non_nan = swings.dropna()
    assert len(non_nan) >= 2


def test_detect_contractions_synthetic():
    high, low, close, volume = _make_vcp_pattern()
    result = detect_contractions(high, low, close, volume)
    # Should find the pattern
    assert result["found"] is True
    assert result["num_contractions"] >= 2
    assert result["pivot_price"] > 0
    assert result["base_depth_pct"] > 0


def test_score_vcp_found():
    high, low, close, volume = _make_vcp_pattern()
    result = detect_contractions(high, low, close, volume)
    score = score_vcp(result)
    assert 0 < score <= 100


def test_score_vcp_not_found():
    result = {"found": False}
    assert score_vcp(result) == 0.0


def test_detect_insufficient_data():
    dates = pd.date_range("2024-01-01", periods=10)
    close = pd.Series(range(100, 110), index=dates)
    result = detect_contractions(close, close - 1, close, pd.Series([1000] * 10, index=dates))
    assert result["found"] is False
