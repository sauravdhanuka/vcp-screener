"""Watchlist management service."""

import logging
from datetime import datetime

from vcp_screener.db import get_session, init_db
from vcp_screener.models.watchlist import WatchlistItem
from vcp_screener.services.screener import load_price_data

logger = logging.getLogger(__name__)


def add_to_watchlist(
    symbol: str,
    list_number: int = 1,
    added_price: float = None,
    pivot_price: float = None,
    strategy: str = "vcp",
    notes: str = None,
) -> WatchlistItem | None:
    """Add a stock to a numbered watchlist."""
    init_db()
    session = get_session()
    try:
        # Check if already in this list
        existing = (
            session.query(WatchlistItem)
            .filter(WatchlistItem.symbol == symbol, WatchlistItem.list_number == list_number)
            .first()
        )
        if existing:
            logger.info(f"{symbol} already in watchlist #{list_number}")
            return existing

        # Get current price if not provided
        if added_price is None:
            df = load_price_data(symbol)
            added_price = float(df["close"].iloc[-1]) if not df.empty else None

        item = WatchlistItem(
            list_number=list_number,
            symbol=symbol,
            added_price=added_price,
            pivot_price=pivot_price,
            strategy=strategy,
            notes=notes,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        logger.info(f"Added {symbol} to watchlist #{list_number}")
        return item
    finally:
        session.close()


def remove_from_watchlist(item_id: int) -> bool:
    """Remove a stock from watchlist by ID."""
    session = get_session()
    try:
        item = session.get(WatchlistItem, item_id)
        if item:
            session.delete(item)
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_watchlist(list_number: int = None) -> list[dict]:
    """Get watchlist items with current prices and P&L."""
    session = get_session()
    try:
        query = session.query(WatchlistItem)
        if list_number is not None:
            query = query.filter(WatchlistItem.list_number == list_number)
        items = query.order_by(WatchlistItem.list_number, WatchlistItem.created_at).all()

        result = []
        for item in items:
            df = load_price_data(item.symbol)
            current_price = float(df["close"].iloc[-1]) if not df.empty else None
            change_pct = None
            if current_price and item.added_price:
                change_pct = (current_price / item.added_price - 1) * 100

            result.append({
                "id": item.id,
                "list_number": item.list_number,
                "symbol": item.symbol,
                "strategy": item.strategy or "vcp",
                "added_price": item.added_price,
                "pivot_price": item.pivot_price,
                "current_price": current_price,
                "change_pct": change_pct,
                "notes": item.notes,
                "created_at": item.created_at,
            })
        return result
    finally:
        session.close()


def get_watchlist_numbers() -> list[int]:
    """Get all distinct watchlist numbers."""
    session = get_session()
    try:
        rows = session.query(WatchlistItem.list_number).distinct().order_by(WatchlistItem.list_number).all()
        return [r[0] for r in rows]
    finally:
        session.close()
