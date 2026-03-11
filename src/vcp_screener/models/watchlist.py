"""User watchlists for tracking stocks."""

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from vcp_screener.db import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    list_number: Mapped[int] = mapped_column(Integer, default=1, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    added_price: Mapped[float] = mapped_column(Float, nullable=True)
    pivot_price: Mapped[float] = mapped_column(Float, nullable=True)
    strategy: Mapped[str] = mapped_column(String(20), default="vcp")
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
