"""One-time script to seed Neon PostgreSQL with initial historical data.

Usage:
    DATABASE_URL="postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require" python scripts/seed_neon.py

This downloads 3 years of OHLCV data for 2200+ NSE stocks into Neon (~30-60 min).
Run locally to avoid Streamlit Cloud timeout issues.
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from vcp_screener.config import settings

if "sqlite" in settings.db_url:
    print("ERROR: DATABASE_URL is not set or points to SQLite.")
    print("Set it to your Neon PostgreSQL connection string:")
    print('  DATABASE_URL="postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require" python scripts/seed_neon.py')
    sys.exit(1)

print(f"Database: {settings.db_url.split('@')[1] if '@' in settings.db_url else settings.db_url}")
print(f"History period: {settings.history_period}")

from vcp_screener.db import init_db
from vcp_screener.services.data_fetcher import full_download

print("Creating tables...")
init_db()

print("Starting full download (this will take 30-60 minutes)...")
full_download(period="3y")

print("Seed complete!")
