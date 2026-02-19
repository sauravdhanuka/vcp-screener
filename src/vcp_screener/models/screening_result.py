"""Screening results stored per run."""

from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from vcp_screener.db import Base


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    close_price: Mapped[float] = mapped_column(Float)
    rs_percentile: Mapped[float] = mapped_column(Float)
    vcp_score: Mapped[float] = mapped_column(Float)
    pivot_price: Mapped[float] = mapped_column(Float, nullable=True)
    base_depth_pct: Mapped[float] = mapped_column(Float, nullable=True)
    num_contractions: Mapped[int] = mapped_column(Integer, nullable=True)
    tightness_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    volume_dry_up: Mapped[float] = mapped_column(Float, nullable=True)
    base_duration_days: Mapped[int] = mapped_column(Integer, nullable=True)
    market_regime: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
