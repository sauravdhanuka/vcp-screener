"""Portfolio management: position sizing, stops, sell alerts."""

import logging
from datetime import date, datetime

import pandas as pd

from vcp_screener.config import settings
from vcp_screener.db import get_session, init_db
from vcp_screener.models.portfolio import Position, EquitySnapshot
from vcp_screener.services.screener import load_price_data
from vcp_screener.services.indicators import rsi as compute_rsi

logger = logging.getLogger(__name__)


def calculate_position_size(entry_price: float, stop_price: float, account_size: float = None) -> int:
    """Calculate number of shares: (Account * Risk%) / (Entry - Stop).

    Returns number of shares (integer).
    """
    if account_size is None:
        account_size = settings.account_size

    risk_amount = account_size * (settings.risk_per_trade_pct / 100)
    risk_per_share = entry_price - stop_price

    if risk_per_share <= 0:
        logger.warning("Stop price must be below entry price")
        return 0

    shares = int(risk_amount / risk_per_share)
    return max(shares, 0)


def buy_stock(
    symbol: str,
    entry_price: float,
    stop_loss_price: float = None,
    shares: int = None,
    entry_date: date = None,
    strategy: str = "vcp",
    pivot_price: float = None,
) -> Position | None:
    """Record a new buy position."""
    init_db()
    session = get_session()
    try:
        # Check max positions (equity curve MA may reduce this)
        effective_max = get_effective_max_positions()
        open_count = session.query(Position).filter(Position.is_open == True).count()
        if open_count >= effective_max:
            logger.warning(f"Max positions ({effective_max}) reached. Cannot buy {symbol}.")
            return None

        # Default stop loss
        if stop_loss_price is None:
            stop_loss_price = entry_price * (1 - settings.default_stop_loss_pct / 100)

        # Calculate shares if not provided
        if shares is None:
            shares = calculate_position_size(entry_price, stop_loss_price)

        if shares <= 0:
            logger.warning("Position size is 0. Check entry/stop prices.")
            return None

        position = Position(
            symbol=symbol,
            entry_date=entry_date or datetime.now().date(),
            entry_price=entry_price,
            shares=shares,
            stop_loss=stop_loss_price,
            highest_price=entry_price,
            is_open=True,
            strategy=strategy,
            pivot_price=pivot_price,
        )
        session.add(position)
        session.commit()
        session.refresh(position)

        cost = entry_price * shares
        logger.info(
            f"BUY {symbol}: {shares} shares @ Rs {entry_price:.2f} "
            f"(cost: Rs {cost:,.0f}, stop: Rs {stop_loss_price:.2f})"
        )
        return position

    finally:
        session.close()


def sell_stock(position_id: int, exit_price: float, reason: str = "manual", exit_date: date = None) -> Position | None:
    """Record a sell for an open position."""
    session = get_session()
    try:
        pos = session.get(Position, position_id)
        if not pos or not pos.is_open:
            logger.warning(f"Position {position_id} not found or already closed")
            return None

        pos.is_open = False
        pos.exit_date = exit_date or datetime.now().date()
        pos.exit_price = exit_price
        pos.exit_reason = reason
        pos.pnl = (exit_price - pos.entry_price) * pos.shares
        pos.pnl_pct = (exit_price / pos.entry_price - 1) * 100

        session.commit()
        session.refresh(pos)

        logger.info(
            f"SELL {pos.symbol}: {pos.shares} shares @ Rs {exit_price:.2f} "
            f"(P&L: Rs {pos.pnl:+,.0f}, {pos.pnl_pct:+.1f}%, reason: {reason})"
        )
        return pos

    finally:
        session.close()


def update_trailing_stops():
    """Update trailing stops for all open positions based on current prices."""
    session = get_session()
    try:
        positions = session.query(Position).filter(Position.is_open == True).all()
        for pos in positions:
            df = load_price_data(pos.symbol)
            if df.empty:
                continue

            current_price = df["close"].iloc[-1]
            gain_pct = (current_price / pos.entry_price - 1) * 100

            # Update highest price
            if current_price > pos.highest_price:
                pos.highest_price = current_price

            # Trailing stop logic
            if gain_pct >= settings.trailing_stop_trigger_pct:
                # 10% trailing stop from highest price
                new_trail = pos.highest_price * (1 - settings.trailing_stop_pct / 100)
                # Never lower the trailing stop
                if pos.trailing_stop is None or new_trail > pos.trailing_stop:
                    pos.trailing_stop = new_trail
            elif gain_pct >= settings.breakeven_trigger_pct:
                # Move stop to breakeven
                if pos.trailing_stop is None or pos.entry_price > pos.trailing_stop:
                    pos.trailing_stop = pos.entry_price

        session.commit()
    finally:
        session.close()


def check_sell_alerts() -> list[dict]:
    """Check all open positions for sell conditions.

    Matches backtester logic:
    - VCP positions: stops, trailing stops, climax tops, failed breakouts, protect 20% gain
    - MR positions: 5% stop, RSI(2) > 65 exit, SMA(10) target, 15-day timeout
    """
    session = get_session()
    alerts = []
    try:
        positions = session.query(Position).filter(Position.is_open == True).all()
        for pos in positions:
            df = load_price_data(pos.symbol)
            if df.empty:
                continue

            current_price = float(df["close"].iloc[-1])
            hold_days = (datetime.now().date() - pos.entry_date).days

            # --- Mean Reversion exits (separate logic, matches backtester) ---
            if pos.strategy == "mean_reversion":
                alert = {
                    "position_id": pos.id,
                    "symbol": pos.symbol,
                    "strategy": "mean_reversion",
                    "entry_price": pos.entry_price,
                    "current_price": current_price,
                    "gain_pct": (current_price / pos.entry_price - 1) * 100,
                    "hold_days": hold_days,
                    "stop_loss": pos.stop_loss,
                    "alerts": [],
                }

                # MR stop loss (5%)
                if current_price <= pos.stop_loss:
                    alert["alerts"].append("MR_STOP_HIT")

                # RSI-based exit (sell on strength, RSI(2) > 65)
                if len(df) >= 3:
                    rsi_val = float(compute_rsi(df["close"], period=2).iloc[-1])
                    if rsi_val > 65:
                        alert["alerts"].append("MR_RSI_EXIT")
                        alert["rsi_2"] = round(rsi_val, 1)

                # SMA(10) target reached
                if len(df) >= 10:
                    sma_10 = float(df["close"].rolling(10).mean().iloc[-1])
                    if current_price >= sma_10:
                        alert["alerts"].append("MR_TARGET_HIT")
                        alert["sma_10"] = round(sma_10, 2)

                # 15-day timeout
                if hold_days >= 15:
                    alert["alerts"].append("MR_TIMEOUT")

                if alert["alerts"]:
                    alerts.append(alert)
                continue  # Skip VCP exit logic for MR positions

            # --- VCP exits (matches backtester _check_stops) ---
            effective_stop = max(
                pos.stop_loss,
                pos.trailing_stop or 0,
            )

            alert = {
                "position_id": pos.id,
                "symbol": pos.symbol,
                "strategy": "vcp",
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "gain_pct": (current_price / pos.entry_price - 1) * 100,
                "hold_days": hold_days,
                "stop_loss": pos.stop_loss,
                "trailing_stop": pos.trailing_stop,
                "effective_stop": effective_stop,
                "alerts": [],
            }

            # Stop loss hit
            if current_price <= pos.stop_loss:
                alert["alerts"].append("STOP_LOSS_HIT")

            # Trailing stop hit
            if pos.trailing_stop and current_price <= pos.trailing_stop:
                alert["alerts"].append("TRAILING_STOP_HIT")

            # Climax top signals
            if len(df) >= 2:
                prev_close = df["close"].iloc[-2]
                daily_change_pct = (current_price / prev_close - 1) * 100
                daily_volume = df["volume"].iloc[-1]
                avg_vol = df["volume"].iloc[-50:].mean() if len(df) >= 50 else df["volume"].mean()

                # High Volume Decline (>= 4% down on high volume)
                if daily_change_pct <= -4 and daily_volume > avg_vol * 1.5:
                    alert["alerts"].append("HIGH_VOL_DECLINE")

                # Exhaustion gap (gap up but close near low)
                today_open = df["open"].iloc[-1]
                today_low = df["low"].iloc[-1]
                today_high = df["high"].iloc[-1]
                if (today_open > prev_close * 1.02 and
                        (today_high - current_price) > (current_price - today_low) * 2):
                    alert["alerts"].append("EXHAUSTION_GAP")

            # Never let a 20%+ gain become a loss
            if (pos.highest_price / pos.entry_price - 1) >= 0.20:
                if current_price <= pos.entry_price:
                    alert["alerts"].append("PROTECT_20PCT_GAIN")

            # Failed Breakout: price falls 3% below pivot after entry
            if pos.pivot_price and current_price < pos.pivot_price * 0.97:
                alert["alerts"].append("FAILED_BREAKOUT")

            if alert["alerts"]:
                alerts.append(alert)

        return alerts
    finally:
        session.close()


def get_holdings() -> list[dict]:
    """Get all open positions with current P&L."""
    session = get_session()
    try:
        positions = session.query(Position).filter(Position.is_open == True).all()
        holdings = []
        for pos in positions:
            df = load_price_data(pos.symbol)
            current_price = float(df["close"].iloc[-1]) if not df.empty else pos.entry_price

            holdings.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "strategy": pos.strategy or "vcp",
                "entry_date": pos.entry_date,
                "entry_price": pos.entry_price,
                "shares": pos.shares,
                "current_price": current_price,
                "cost": pos.entry_price * pos.shares,
                "market_value": current_price * pos.shares,
                "pnl": (current_price - pos.entry_price) * pos.shares,
                "pnl_pct": (current_price / pos.entry_price - 1) * 100,
                "stop_loss": pos.stop_loss,
                "trailing_stop": pos.trailing_stop,
                "highest_price": pos.highest_price,
            })
        return holdings
    finally:
        session.close()


def get_closed_trades() -> list[dict]:
    """Get all closed positions."""
    session = get_session()
    try:
        positions = (
            session.query(Position)
            .filter(Position.is_open == False)
            .order_by(Position.exit_date.desc())
            .all()
        )
        return [{
            "id": p.id,
            "symbol": p.symbol,
            "entry_date": p.entry_date,
            "entry_price": p.entry_price,
            "shares": p.shares,
            "exit_date": p.exit_date,
            "exit_price": p.exit_price,
            "exit_reason": p.exit_reason,
            "pnl": p.pnl,
            "pnl_pct": p.pnl_pct,
        } for p in positions]
    finally:
        session.close()


def save_equity_snapshot():
    """Save today's portfolio equity for equity curve MA calculation.

    Call this daily (e.g., after market close) to build the equity time series.
    Equity = cash (account_size - sum of open position costs) + sum of open position market values.
    """
    session = get_session()
    try:
        today = datetime.now().date()

        # Check if snapshot already exists for today
        existing = session.query(EquitySnapshot).filter(EquitySnapshot.date == today).first()

        # Calculate current equity
        positions = session.query(Position).filter(Position.is_open == True).all()
        total_invested = 0.0
        total_market_value = 0.0
        for pos in positions:
            total_invested += pos.entry_price * pos.shares
            df = load_price_data(pos.symbol)
            if not df.empty:
                current_price = float(df["close"].iloc[-1])
                total_market_value += current_price * pos.shares
            else:
                total_market_value += pos.entry_price * pos.shares

        # Add realized P&L from closed trades
        closed_pnl = session.query(Position).filter(Position.is_open == False).all()
        realized_pnl = sum(p.pnl or 0 for p in closed_pnl)

        equity = settings.account_size + realized_pnl + (total_market_value - total_invested)

        if existing:
            existing.equity = equity
        else:
            session.add(EquitySnapshot(date=today, equity=equity))
        session.commit()
        logger.info(f"Equity snapshot: Rs {equity:,.0f}")
    finally:
        session.close()


def get_effective_max_positions() -> int:
    """Get effective max positions considering equity curve MA (matches backtester).

    If current equity < 40-day MA of equity, reduce max positions to 3.
    """
    eq_ma_days = 40
    dd_max_positions = 3

    session = get_session()
    try:
        snapshots = (
            session.query(EquitySnapshot)
            .order_by(EquitySnapshot.date.desc())
            .limit(eq_ma_days)
            .all()
        )

        if len(snapshots) < eq_ma_days:
            return settings.max_positions  # Not enough data, use default

        equity_values = [s.equity for s in snapshots]
        equity_ma = sum(equity_values) / len(equity_values)
        current_equity = equity_values[0]  # Most recent

        if current_equity < equity_ma:
            logger.info(
                f"Equity curve MA protection: equity Rs {current_equity:,.0f} < "
                f"MA({eq_ma_days}) Rs {equity_ma:,.0f}. Max positions reduced to {dd_max_positions}."
            )
            return dd_max_positions

        return settings.max_positions
    finally:
        session.close()
