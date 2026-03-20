"""Async data bridge — wraps sync service functions with TTL caching.

Replaces Streamlit's @st.cache_data with a simple dict-based TTL cache
and runs all blocking DB/service calls via asyncio.to_thread().
"""

import asyncio
import time
from functools import wraps


def ttl_cache(seconds: int):
    """Decorator that caches async function results for `seconds`."""

    def decorator(func):
        cache = {}

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            if key in cache:
                result, ts = cache[key]
                if now - ts < seconds:
                    return result
            result = await func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        wrapper.cache = cache
        wrapper.clear = lambda: cache.clear()
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------


@ttl_cache(300)
async def get_screening_results():
    """Load latest VCP screening results from DB (cached 5 min)."""

    def _query():
        from vcp_screener.db import get_session
        from vcp_screener.models.screening_result import ScreeningResult

        session = get_session()
        try:
            dates = [
                r[0]
                for r in session.query(ScreeningResult.run_date)
                .distinct()
                .order_by(ScreeningResult.run_date.desc())
                .all()
            ]
            if not dates:
                return None

            results = (
                session.query(ScreeningResult)
                .filter(ScreeningResult.run_date == dates[0])
                .order_by(ScreeningResult.rank)
                .limit(25)
                .all()
            )
            if not results:
                return {
                    "date": str(dates[0]),
                    "regime": None,
                    "data": [],
                    "symbols": [],
                }

            regime = results[0].market_regime
            data = [
                {
                    "rank": r.rank,
                    "symbol": r.symbol,
                    "close": r.close_price,
                    "vcp_score": r.vcp_score,
                    "rs_percentile": r.rs_percentile,
                    "pivot": r.pivot_price,
                    "depth_pct": r.base_depth_pct,
                    "contractions": r.num_contractions,
                    "tightness": r.tightness_ratio,
                    "vol_dry_up": r.volume_dry_up,
                    "days": r.base_duration_days,
                }
                for r in results
            ]
            symbols = [r.symbol for r in results]
            return {
                "date": str(dates[0]),
                "regime": regime,
                "data": data,
                "symbols": symbols,
            }
        finally:
            session.close()

    return await asyncio.to_thread(_query)


@ttl_cache(300)
async def get_mr_results():
    """Load latest Mean Reversion screening results from DB (cached 5 min)."""

    def _query():
        from vcp_screener.services.screener import load_mr_results

        return load_mr_results()

    return await asyncio.to_thread(_query)


@ttl_cache(300)
async def get_buy_signals():
    """Load actionable buy signals (cached 5 min)."""

    def _query():
        from vcp_screener.services.screener import (
            get_buy_signals as _get_buy_signals,
        )

        return _get_buy_signals()

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


@ttl_cache(120)
async def get_holdings():
    """Load current open positions (cached 2 min)."""

    def _query():
        from vcp_screener.services.portfolio_manager import (
            get_holdings as _get_holdings,
        )

        return _get_holdings()

    return await asyncio.to_thread(_query)


@ttl_cache(120)
async def get_sell_alerts():
    """Update trailing stops and check sell alerts (cached 2 min)."""

    def _query():
        from vcp_screener.services.portfolio_manager import (
            update_trailing_stops,
            check_sell_alerts as _check_sell_alerts,
        )

        update_trailing_stops()
        return _check_sell_alerts()

    return await asyncio.to_thread(_query)


@ttl_cache(120)
async def get_closed_trades():
    """Load closed trade history (cached 2 min)."""

    def _query():
        from vcp_screener.services.portfolio_manager import (
            get_closed_trades as _get_closed_trades,
        )

        return _get_closed_trades()

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


@ttl_cache(180)
async def get_watchlist_numbers():
    """Load active watchlist numbers (cached 3 min)."""

    def _query():
        from vcp_screener.services.watchlist_service import (
            get_watchlist_numbers as _get_watchlist_numbers,
        )

        return _get_watchlist_numbers()

    return await asyncio.to_thread(_query)


@ttl_cache(180)
async def get_watchlist(list_number: int):
    """Load watchlist items for a specific list (cached 3 min)."""

    def _query():
        from vcp_screener.services.watchlist_service import (
            get_watchlist as _get_watchlist,
        )

        return _get_watchlist(list_number)

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------


@ttl_cache(600)
async def get_market_data():
    """Load market regime and Nifty data (cached 10 min)."""

    def _query():
        from vcp_screener.services.market_regime import (
            detect_market_regime,
            get_nifty_data,
        )

        nifty_df = get_nifty_data(period="2y")
        regime = detect_market_regime(nifty_data=nifty_df)

        # Convert Nifty data to JSON-serializable format for Chart.js
        nifty_chart = []
        if not nifty_df.empty:
            close = nifty_df["Close"].squeeze()
            for dt, val in close.items():
                nifty_chart.append(
                    {"date": str(dt.date()), "close": round(float(val), 2)}
                )

        return {
            "regime": regime,
            "nifty_chart": nifty_chart,
        }

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Stock Detail
# ---------------------------------------------------------------------------


@ttl_cache(300)
async def get_stock_detail(symbol: str):
    """Load detailed stock analysis (cached 5 min)."""

    def _query():
        from vcp_screener.services.screener import (
            get_stock_detail as _get_stock_detail,
        )

        return _get_stock_detail(symbol)

    return await asyncio.to_thread(_query)


# ---------------------------------------------------------------------------
# Cache Invalidation
# ---------------------------------------------------------------------------


def clear_screening_cache():
    """Invalidate screening and signals caches after a new screen run."""
    get_screening_results.clear()
    get_mr_results.clear()
    get_buy_signals.clear()


def clear_portfolio_cache():
    """Invalidate portfolio-related caches after a trade."""
    get_holdings.clear()
    get_sell_alerts.clear()
    get_closed_trades.clear()


def clear_watchlist_cache():
    """Invalidate watchlist caches after add/remove."""
    get_watchlist_numbers.clear()
    get_watchlist.clear()
