"""Daily auto-run scheduler.

Runs at 4:15 PM IST after market close:
1. Updates price data
2. Runs VCP + MR screening (both saved to DB)
3. Saves equity snapshot
4. Updates trailing stops
"""

import logging
import time

import schedule

from vcp_screener.config import settings
from vcp_screener.services.data_fetcher import update_prices
from vcp_screener.services.screener import run_all_screens
from vcp_screener.services.portfolio_manager import update_trailing_stops, save_equity_snapshot

logger = logging.getLogger(__name__)


def daily_screening_job():
    """Run the full daily pipeline after market close."""
    logger.info("=== Daily Screening Job Started ===")
    try:
        # Step 1: Update prices
        logger.info("Step 1: Updating price data...")
        update_prices(days_back=5)

        # Step 2: Run VCP + MR screening (both saved to DB)
        logger.info("Step 2: Running VCP + MR screening...")
        results = run_all_screens(save_results=True)
        logger.info(f"VCP: {len(results['vcp_candidates'])} candidates, "
                     f"MR: {len(results['mr_signals'])} signals, "
                     f"Regime: {results['market_regime']}")

        # Step 3: Save equity snapshot
        logger.info("Step 3: Saving equity snapshot...")
        save_equity_snapshot()

        # Step 4: Update trailing stops
        logger.info("Step 4: Updating trailing stops...")
        update_trailing_stops()

        logger.info("=== Daily Job Complete ===")
    except Exception as e:
        logger.error(f"Daily job failed: {e}", exc_info=True)


def start_scheduler():
    """Start the scheduler to run daily at configured time (IST)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.data_dir / "scheduler.log"),
        ],
    )

    logger.info(f"VCP Scheduler started. Daily job at {settings.screen_time} IST.")

    schedule.every().day.at(settings.screen_time).do(daily_screening_job)

    # Also allow running immediately for testing
    import sys
    if "--now" in sys.argv:
        logger.info("Running immediately (--now flag)")
        daily_screening_job()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    start_scheduler()
