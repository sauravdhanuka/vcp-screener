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
    """Create all tables and migrate schema for existing DBs."""
    from vcp_screener.models import stock, daily_price, screening_result, portfolio, backtest, watchlist  # noqa: F401
    Base.metadata.create_all(engine)
    _migrate_schema()


def _migrate_schema():
    """Add missing columns to existing tables (safe for fresh DBs too)."""
    from sqlalchemy import text, inspect

    insp = inspect(engine)

    # positions table migrations
    if "positions" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("positions")}
        migrations = [
            ("strategy", "VARCHAR(20) DEFAULT 'vcp'"),
            ("pivot_price", "FLOAT"),
        ]
        with engine.begin() as conn:
            for col_name, col_type in migrations:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE positions ADD COLUMN {col_name} {col_type}"))
