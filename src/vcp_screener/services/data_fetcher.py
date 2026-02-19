"""NSE stock list download and batch yfinance OHLCV fetcher."""

import logging
import time
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from vcp_screener.config import settings
from vcp_screener.db import get_session, init_db
from vcp_screener.models.stock import Stock
from vcp_screener.models.daily_price import DailyPrice

logger = logging.getLogger(__name__)

NSE_EQUITY_CSV = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/csv",
}


def fetch_nse_stock_list() -> list[dict]:
    """Download the current NSE equity list."""
    logger.info("Fetching NSE stock list...")
    try:
        resp = requests.get(NSE_EQUITY_CSV, headers=NSE_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        logger.warning("Primary NSE URL failed, using fallback...")
        fallback = "https://www1.nseindia.com/content/equities/EQUITY_L.csv"
        resp = requests.get(fallback, headers=NSE_HEADERS, timeout=30)
        resp.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(resp.text))
    df.columns = df.columns.str.strip()

    stocks = []
    for _, row in df.iterrows():
        symbol = str(row.get("SYMBOL", "")).strip()
        if not symbol:
            continue
        stocks.append({
            "symbol": symbol,
            "name": str(row.get("NAME OF COMPANY", "")).strip(),
        })
    logger.info(f"Found {len(stocks)} NSE stocks")
    return stocks


def save_stock_list(stocks: list[dict]):
    """Upsert stock list into DB."""
    init_db()
    session = get_session()
    try:
        for s in stocks:
            existing = session.get(Stock, s["symbol"])
            if existing:
                existing.name = s["name"]
                existing.is_active = True
                existing.last_updated = datetime.utcnow()
            else:
                session.add(Stock(
                    symbol=s["symbol"],
                    name=s["name"],
                    is_active=True,
                    last_updated=datetime.utcnow(),
                ))
        session.commit()
        logger.info(f"Saved {len(stocks)} stocks to DB")
    finally:
        session.close()


def get_active_symbols() -> list[str]:
    """Get all active stock symbols from DB."""
    session = get_session()
    try:
        stocks = session.query(Stock.symbol).filter(Stock.is_active == True).all()
        return [s[0] for s in stocks]
    finally:
        session.close()


def download_ohlcv(symbols: list[str], period: str = None):
    """Download OHLCV data for given symbols in batches using yfinance."""
    if period is None:
        period = settings.history_period

    total = len(symbols)
    batch_size = settings.batch_size

    for i in range(0, total, batch_size):
        batch = symbols[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        logger.info(f"Batch {batch_num}/{total_batches}: downloading {len(batch)} tickers...")

        # Add .NS suffix for NSE
        yf_tickers = [f"{s}.NS" for s in batch]
        ticker_str = " ".join(yf_tickers)

        try:
            data = yf.download(
                ticker_str,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
        except Exception as e:
            logger.error(f"Batch {batch_num} download failed: {e}")
            continue

        if data.empty:
            logger.warning(f"Batch {batch_num}: no data returned")
            continue

        _save_batch_prices(data, batch)

        if i + batch_size < total:
            time.sleep(settings.batch_delay_seconds)


def _save_batch_prices(data: pd.DataFrame, symbols: list[str]):
    """Save downloaded price data to DB."""
    session = get_session()
    try:
        rows_to_insert = []
        for symbol in symbols:
            yf_symbol = f"{symbol}.NS"
            try:
                if len(symbols) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[yf_symbol]
            except (KeyError, TypeError):
                continue

            if ticker_data.empty:
                continue

            # Drop rows where close is NaN
            ticker_data = ticker_data.dropna(subset=["Close"])

            for dt, row in ticker_data.iterrows():
                if pd.isna(row["Close"]):
                    continue
                trade_date = dt.date() if hasattr(dt, 'date') else dt
                rows_to_insert.append({
                    "symbol": symbol,
                    "date": trade_date,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "adj_close": float(row.get("Adj Close", row["Close"])),
                    "volume": int(row["Volume"]),
                })

        if rows_to_insert:
            # Insert in chunks to avoid SQLite variable limit
            chunk_size = 500
            for start in range(0, len(rows_to_insert), chunk_size):
                chunk = rows_to_insert[start:start + chunk_size]
                stmt = sqlite_upsert(DailyPrice).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "adj_close": stmt.excluded.adj_close,
                        "volume": stmt.excluded.volume,
                    },
                )
                session.execute(stmt)
            session.commit()
            logger.info(f"Saved {len(rows_to_insert)} price rows")
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving prices: {e}")
    finally:
        session.close()


def update_prices(days_back: int = 10):
    """Incremental update: fetch recent data for all active symbols."""
    symbols = get_active_symbols()
    if not symbols:
        logger.warning("No active symbols found. Run full download first.")
        return
    logger.info(f"Updating prices for {len(symbols)} symbols ({days_back}d)...")
    download_ohlcv(symbols, period=f"{days_back}d")


def full_download():
    """Full pipeline: fetch stock list + download all OHLCV data."""
    stocks = fetch_nse_stock_list()
    save_stock_list(stocks)
    symbols = [s["symbol"] for s in stocks]
    logger.info(f"Starting full OHLCV download for {len(symbols)} stocks...")
    download_ohlcv(symbols)
    logger.info("Full download complete.")
