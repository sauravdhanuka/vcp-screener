"""Tests for portfolio management."""

from vcp_screener.services.portfolio_manager import calculate_position_size


def test_position_sizing_basic():
    # Account=100000, risk=2.5%, entry=100, stop=90 (10% stop)
    # Risk amount = 2500, risk/share = 10 => 250 shares
    shares = calculate_position_size(
        entry_price=100, stop_price=90, account_size=100000
    )
    assert shares == 250


def test_position_sizing_wide_stop():
    # entry=200, stop=180 (10%), risk_amount=2500, risk/share=20 => 125 shares
    shares = calculate_position_size(
        entry_price=200, stop_price=180, account_size=100000
    )
    assert shares == 125


def test_position_sizing_stop_above_entry():
    shares = calculate_position_size(entry_price=100, stop_price=110, account_size=100000)
    assert shares == 0
