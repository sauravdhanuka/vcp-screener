"""Screening pipeline orchestrator.

Pre-filter -> RS calculation -> Trend Template -> VCP Detection -> Rank Top 50.
"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from vcp_screener.config import settings
from vcp_screener.db import get_session, init_db
from vcp_screener.models.daily_price import DailyPrice
from vcp_screener.models.stock import Stock
from vcp_screener.models.screening_result import ScreeningResult
from vcp_screener.services.indicators import compute_rs_raw, compute_rs_percentiles, average_volume
from vcp_screener.services.trend_template import check_trend_template
from vcp_screener.services.vcp_detector import detect_contractions, score_vcp
from vcp_screener.services.market_regime import detect_market_regime

logger = logging.getLogger(__name__)


def load_price_data(symbol: str, session=None) -> pd.DataFrame:
    """Load price data for a symbol from DB into a DataFrame."""
    own_session = session is None
    if own_session:
        session = get_session()
    try:
        rows = (
            session.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.date)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = pd.DataFrame([{
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "adj_close": r.adj_close,
            "volume": r.volume,
        } for r in rows])
        data["date"] = pd.to_datetime(data["date"])
        data.set_index("date", inplace=True)
        return data
    finally:
        if own_session:
            session.close()


def pre_filter(df: pd.DataFrame) -> bool:
    """Step 1: Fast rejection based on price, volume, data length."""
    if len(df) < settings.min_trading_days:
        return False
    last_close = df["close"].iloc[-1]
    if last_close < settings.min_price:
        return False
    if settings.max_price and last_close > settings.max_price:
        return False
    if average_volume(df["volume"]) < settings.min_avg_volume:
        return False
    return True


def run_screening(save_results: bool = True) -> list[dict]:
    """Run the full screening pipeline.

    Returns list of dicts for top N stocks, sorted by VCP score desc.
    """
    init_db()
    session = get_session()

    try:
        # Get all active symbols
        symbols = [
            s[0] for s in
            session.query(Stock.symbol).filter(Stock.is_active == True).all()
        ]
        logger.info(f"Screening {len(symbols)} stocks...")

        # Step 1 & RS raw: load data, pre-filter, compute RS
        rs_raw_scores = {}
        price_cache = {}

        for i, symbol in enumerate(symbols):
            if (i + 1) % 200 == 0:
                logger.info(f"  Loading data: {i + 1}/{len(symbols)}...")
            df = load_price_data(symbol, session)
            if df.empty:
                continue
            if not pre_filter(df):
                continue
            price_cache[symbol] = df
            rs_raw_scores[symbol] = compute_rs_raw(df["close"])

        logger.info(f"After pre-filter: {len(price_cache)} stocks")

        # Step 2: RS percentiles
        rs_percentiles = compute_rs_percentiles(rs_raw_scores)

        # Step 3 & 4: Trend Template + VCP Detection
        candidates = []
        for symbol, df in price_cache.items():
            rs_pct = rs_percentiles.get(symbol, 0)

            # Step 3: Trend Template
            trend_result = check_trend_template(df["close"], rs_pct)
            if not trend_result["passes"]:
                continue

            # Step 4: VCP Detection
            vcp_result = detect_contractions(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                volume=df["volume"],
            )
            if not vcp_result["found"]:
                continue

            vcp_sc = score_vcp(vcp_result)

            candidates.append({
                "symbol": symbol,
                "close_price": float(df["close"].iloc[-1]),
                "rs_percentile": round(rs_pct, 1),
                "vcp_score": round(vcp_sc, 1),
                "pivot_price": vcp_result.get("pivot_price"),
                "base_depth_pct": round(vcp_result.get("base_depth_pct", 0), 1),
                "num_contractions": vcp_result.get("num_contractions", 0),
                "tightness_ratio": round(vcp_result.get("tightness_ratio", 0), 2),
                "volume_dry_up": round(vcp_result.get("volume_dry_up_pct", 0), 1),
                "base_duration_days": vcp_result.get("base_duration_days", 0),
                "trend_conditions": trend_result["conditions"],
                "contractions": vcp_result.get("contractions", []),
            })

        # Step 5: Market regime
        regime = detect_market_regime()

        # Step 6: Sort and rank
        candidates.sort(key=lambda x: (-x["vcp_score"], -x["rs_percentile"]))
        top_n = candidates[:settings.top_n]

        # Assign ranks
        for i, c in enumerate(top_n):
            c["rank"] = i + 1
            c["market_regime"] = regime["regime"]

        logger.info(f"Found {len(candidates)} VCP candidates. Top {len(top_n)} selected.")

        # Save to DB (delete previous results for same date first)
        if save_results and top_n:
            run_date = datetime.now().date()
            session.query(ScreeningResult).filter(ScreeningResult.run_date == run_date).delete()
            for c in top_n:
                result = ScreeningResult(
                    run_date=run_date,
                    symbol=c["symbol"],
                    rank=c["rank"],
                    close_price=c["close_price"],
                    rs_percentile=c["rs_percentile"],
                    vcp_score=c["vcp_score"],
                    pivot_price=c.get("pivot_price"),
                    base_depth_pct=c.get("base_depth_pct"),
                    num_contractions=c.get("num_contractions"),
                    tightness_ratio=c.get("tightness_ratio"),
                    volume_dry_up=c.get("volume_dry_up"),
                    base_duration_days=c.get("base_duration_days"),
                    market_regime=c.get("market_regime", "UNKNOWN"),
                    details={
                        "contractions": [
                            {k: (str(v) if hasattr(v, 'isoformat') else v)
                             for k, v in ct.items()}
                            for ct in c.get("contractions", [])
                        ],
                        "trend_conditions": {
                            k: bool(v) for k, v in c.get("trend_conditions", {}).items()
                        },
                    },
                )
                session.add(result)
            session.commit()
            logger.info(f"Saved {len(top_n)} screening results for {run_date}")

        return top_n

    finally:
        session.close()


def get_buy_signals(candidates: list[dict] = None) -> list[dict]:
    """Check which VCP candidates have actionable buy signals RIGHT NOW.

    A stock gets a buy signal when:
    1. It passed all screening filters (it's in the top 50)
    2. Current close is within 3% of pivot price OR already above pivot
    3. Today's volume is >= 1.3x the 50-day average (breakout confirmation)

    Also categorizes near-breakout stocks (within 3% of pivot, waiting for volume).

    Returns list of dicts with signal type, entry/stop/shares recommendations.
    """
    if candidates is None:
        # Load from last screening run
        session = get_session()
        try:
            last_date = (
                session.query(ScreeningResult.run_date)
                .order_by(ScreeningResult.run_date.desc())
                .first()
            )
            if not last_date:
                return []
            results = (
                session.query(ScreeningResult)
                .filter(ScreeningResult.run_date == last_date[0])
                .order_by(ScreeningResult.rank)
                .all()
            )
            candidates = [{
                "symbol": r.symbol,
                "close_price": r.close_price,
                "vcp_score": r.vcp_score,
                "rs_percentile": r.rs_percentile,
                "pivot_price": r.pivot_price,
                "num_contractions": r.num_contractions,
                "tightness_ratio": r.tightness_ratio,
                "volume_dry_up": r.volume_dry_up,
                "base_depth_pct": r.base_depth_pct,
                "market_regime": r.market_regime,
            } for r in results]
        finally:
            session.close()

    signals = []
    session = get_session()
    try:
        for c in candidates:
            symbol = c["symbol"]
            pivot = c.get("pivot_price")
            if not pivot or pivot <= 0:
                continue

            df = load_price_data(symbol, session)
            if df.empty or len(df) < 50:
                continue

            close = float(df["close"].iloc[-1])
            today_volume = float(df["volume"].iloc[-1])
            avg_volume = float(df["volume"].iloc[-50:].mean())
            vol_ratio = today_volume / avg_volume if avg_volume > 0 else 0

            distance_to_pivot_pct = (pivot - close) / pivot * 100
            above_pivot = close > pivot

            # Calculate recommended entry, stop, shares
            entry_price = close if above_pivot else pivot
            stop_price = entry_price * (1 - settings.default_stop_loss_pct / 100)
            risk_amount = settings.account_size * (settings.risk_per_trade_pct / 100)
            risk_per_share = entry_price - stop_price
            shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            cost = shares * entry_price

            signal = {
                "symbol": symbol,
                "close": close,
                "pivot": pivot,
                "vcp_score": c.get("vcp_score", 0),
                "rs_percentile": c.get("rs_percentile", 0),
                "num_contractions": c.get("num_contractions", 0),
                "distance_to_pivot_pct": round(distance_to_pivot_pct, 1),
                "above_pivot": above_pivot,
                "today_volume": int(today_volume),
                "avg_volume": int(avg_volume),
                "vol_ratio": round(vol_ratio, 2),
                "breakout_confirmed": above_pivot and vol_ratio >= settings.breakout_volume_mult,
                "entry_price": round(entry_price, 2),
                "stop_price": round(stop_price, 2),
                "shares": shares,
                "cost": round(cost, 0),
                "risk_amount": round(risk_amount, 0),
                "market_regime": c.get("market_regime", "UNKNOWN"),
            }

            # Classify signal
            if above_pivot and vol_ratio >= settings.breakout_volume_mult:
                signal["signal"] = "BUY"
                signal["reason"] = f"Breakout confirmed: closed above pivot ₹{pivot:,.0f} on {vol_ratio:.1f}x volume"
            elif above_pivot:
                signal["signal"] = "WATCH_VOLUME"
                signal["reason"] = f"Above pivot but volume only {vol_ratio:.1f}x (need {settings.breakout_volume_mult}x). Wait for volume surge"
            elif distance_to_pivot_pct <= 3:
                signal["signal"] = "NEAR_PIVOT"
                signal["reason"] = f"Only {distance_to_pivot_pct:.1f}% below pivot. Add to watchlist"
            else:
                signal["signal"] = "FORMING"
                signal["reason"] = f"{distance_to_pivot_pct:.1f}% below pivot. VCP still forming"

            signals.append(signal)

        # Sort: BUY first, then WATCH_VOLUME, then NEAR_PIVOT, then FORMING
        signal_order = {"BUY": 0, "WATCH_VOLUME": 1, "NEAR_PIVOT": 2, "FORMING": 3}
        signals.sort(key=lambda s: (signal_order.get(s["signal"], 9), -s["vcp_score"]))

        return signals
    finally:
        session.close()


def get_stock_detail(symbol: str) -> dict | None:
    """Get detailed screening analysis for a single stock."""
    session = get_session()
    try:
        df = load_price_data(symbol, session)
        if df.empty:
            return None

        # Compute RS (need all stocks for percentile, so use last saved)
        rs_raw = compute_rs_raw(df["close"])

        # Approximate percentile (from last screening run)
        last_result = (
            session.query(ScreeningResult)
            .filter(ScreeningResult.symbol == symbol)
            .order_by(ScreeningResult.run_date.desc())
            .first()
        )
        rs_pct = last_result.rs_percentile if last_result else 50.0

        trend = check_trend_template(df["close"], rs_pct)
        vcp = detect_contractions(df["high"], df["low"], df["close"], df["volume"])
        vcp_sc = score_vcp(vcp) if vcp["found"] else 0.0

        return {
            "symbol": symbol,
            "close": float(df["close"].iloc[-1]),
            "rs_raw": rs_raw,
            "rs_percentile": rs_pct,
            "trend_template": trend,
            "vcp": vcp,
            "vcp_score": vcp_sc,
            "price_data": df,
        }
    finally:
        session.close()
