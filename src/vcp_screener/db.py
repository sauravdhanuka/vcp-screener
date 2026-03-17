"""SQLAlchemy engine and session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from vcp_screener.config import settings

# SQLite needs check_same_thread=False for Streamlit's multi-threading
_connect_args = {}
if "sqlite" in settings.db_url:
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.db_url, echo=False, pool_pre_ping=True, connect_args=_connect_args
)

# Enable WAL mode for SQLite (concurrent reads + writes)
if "sqlite" in settings.db_url:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()


def init_db():
    """Create all tables and migrate schema for existing DBs."""
    from vcp_screener.models import stock, daily_price, screening_result, portfolio, backtest, watchlist, mr_screening_result  # noqa: F401
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
