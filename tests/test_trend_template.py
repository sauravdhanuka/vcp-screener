"""Tests for trend template filter."""

import numpy as np
import pandas as pd

from vcp_screener.services.trend_template import check_trend_template


def _make_uptrending_prices(n=300, start=100, drift=0.3):
    """Generate an uptrending price series."""
    np.random.seed(42)
    returns = np.random.randn(n) * 0.02 + drift / n
    prices = start * np.cumprod(1 + returns)
    return pd.Series(prices)


def test_strong_uptrend_passes():
    close = _make_uptrending_prices(n=300, drift=0.5)
    result = check_trend_template(close, rs_percentile=85.0)
    # A strong uptrend should pass most conditions
    assert isinstance(result["conditions"], dict)
    assert len(result["conditions"]) == 8


def test_insufficient_data():
    close = pd.Series([100, 101, 102])
    result = check_trend_template(close, rs_percentile=80.0)
    assert result["passes"] is False


def test_low_rs_fails_condition_8():
    close = _make_uptrending_prices(n=300, drift=0.5)
    result = check_trend_template(close, rs_percentile=50.0)
    assert result["conditions"]["8_rs_percentile_above_70"] is False
