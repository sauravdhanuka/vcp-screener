"""SQLAlchemy engine and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from vcp_screener.config import settings

if settings.db_url.startswith("postgresql"):
    engine = create_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
        connect_args={"sslmode": "require"},
    )
else:
    engine = create_engine(settings.db_url, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()


def init_db():
    """Create all tables."""
    from vcp_screener.models import stock, daily_price, screening_result, portfolio, backtest  # noqa: F401
    Base.metadata.create_all(engine)
