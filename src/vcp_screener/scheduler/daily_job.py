"""Daily auto-run scheduler with Telegram alerts.

Runs at 4:15 PM IST after market close:
1. Updates price data
2. Runs VCP screening
3. Checks buy signals (breakout confirmations)
4. Updates trailing stops
5. Checks sell alerts
6. Sends everything to Telegram
"""

import logging
import time

import schedule

from vcp_screener.config import settings
from vcp_screener.services.data_fetcher import update_prices
from vcp_screener.services.screener import run_screening, get_buy_signals
from vcp_screener.services.portfolio_manager import (
    update_trailing_stops, check_sell_alerts, get_holdings,
)
from vcp_screener.services.alerts import send_daily_report, send_alert

logger = logging.getLogger(__name__)


def daily_screening_job():
    """Run the full daily pipeline and send Telegram alerts."""
    logger.info("=== Daily VCP Screening Job Started ===")

    try:
        # Step 1: Update prices
        logger.info("Step 1: Updating price data...")
        update_prices(days_back=5)

        # Step 2: Run screening
        logger.info("Step 2: Running VCP screening...")
        results = run_screening(save_results=True)
        logger.info(f"Screening complete: {len(results)} candidates found")

        # Step 3: Check buy signals
        logger.info("Step 3: Checking buy signals...")
        signals = get_buy_signals()
        buy_count = len([s for s in signals if s["signal"] == "BUY"])
        near_count = len([s for s in signals if s["signal"] == "NEAR_PIVOT"])
        logger.info(f"Buy signals: {buy_count} confirmed, {near_count} near pivot")

        # Step 4: Update portfolio stops
        logger.info("Step 4: Updating trailing stops...")
        update_trailing_stops()

        # Step 5: Check sell alerts
        logger.info("Step 5: Checking sell alerts...")
        alerts = check_sell_alerts()
        if alerts:
            logger.warning(f"SELL ALERTS for {len(alerts)} positions:")
            for a in alerts:
                logger.warning(f"  {a['symbol']}: {', '.join(a['alerts'])}")

        # Step 6: Get portfolio holdings
        holdings = get_holdings()

        # Step 7: Send Telegram report
        logger.info("Step 6: Sending Telegram alerts...")
        send_daily_report(signals, alerts, holdings)

        logger.info("=== Daily Job Complete ===")

    except Exception as e:
        logger.error(f"Daily job failed: {e}", exc_info=True)
        try:
            send_alert(f"<b>❌ VCP Screener Error</b>\n\n{e}")
        except Exception:
            pass


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

    if settings.telegram_bot_token and settings.telegram_chat_id:
        logger.info("Telegram alerts: ENABLED")
        send_alert("<b>✅ VCP Scheduler Started</b>\nDaily screening will run at 4:15 PM IST.")
    else:
        logger.warning("Telegram alerts: DISABLED (set VCP_TELEGRAM_BOT_TOKEN and VCP_TELEGRAM_CHAT_ID)")

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
