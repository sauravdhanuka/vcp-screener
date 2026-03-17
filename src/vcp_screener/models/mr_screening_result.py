"""Mean Reversion screening results stored per run."""

from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from vcp_screener.db import Base


class MRScreeningResult(Base):
    __tablename__ = "mr_screening_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    close_price: Mapped[float] = mapped_column(Float)
    sma_20: Mapped[float] = mapped_column(Float)
    sma_10: Mapped[float] = mapped_column(Float)
    rsi_2: Mapped[float] = mapped_column(Float)
    ibs: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float)
    volume_ratio: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    cost: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
