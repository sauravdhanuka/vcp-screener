"""Tests for indicator calculations."""

import numpy as np
import pandas as pd
import pytest

from vcp_screener.services.indicators import sma, compute_rs_raw, compute_rs_percentiles, average_volume, volume_ratio


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    result = sma(s, 3)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[9] == pytest.approx(9.0)


def test_compute_rs_raw():
    np.random.seed(42)
    # Create 252 days of uptrending prices
    prices = pd.Series(np.cumsum(np.random.randn(300)) + 100)
    prices = prices.clip(lower=1)  # Avoid negatives
    score = compute_rs_raw(prices)
    assert not np.isnan(score)


def test_compute_rs_raw_insufficient_data():
    prices = pd.Series([100, 101, 102])
    score = compute_rs_raw(prices)
    assert np.isnan(score)


def test_compute_rs_percentiles():
    scores = {"A": 50.0, "B": 100.0, "C": 25.0, "D": 75.0}
    pcts = compute_rs_percentiles(scores)
    assert pcts["B"] > pcts["D"] > pcts["A"] > pcts["C"]
    assert 0 <= pcts["C"] <= 100


def test_average_volume():
    vol = pd.Series([100, 200, 300, 400, 500] * 20)
    avg = average_volume(vol, period=50)
    assert avg == pytest.approx(300.0)


def test_volume_ratio():
    vol = pd.Series([100] * 50 + [200] * 10)
    ratio = volume_ratio(vol, short=10, long=50)
    # Last 10 are 200, earlier avg is roughly 100-ish
    assert ratio > 1.0
