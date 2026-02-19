"""Portfolio positions and trade history."""

from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from vcp_screener.db import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    entry_date: Mapped[date] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    stop_loss: Mapped[float] = mapped_column(Float)
    trailing_stop: Mapped[float] = mapped_column(Float, nullable=True)
    highest_price: Mapped[float] = mapped_column(Float)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_date: Mapped[date] = mapped_column(Date, nullable=True)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(50), nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
