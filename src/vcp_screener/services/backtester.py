"""Event-driven backtester with breakout confirmation.

V2: Indian-adapted. Instead of buying blindly at next day's open,
candidates go into a watchlist and we only enter when the price
crosses the pivot on 1.5x+ average volume (confirmed breakout).
"""

import logging
from datetime import date

import numpy as np
import pandas as pd

from vcp_screener.config import settings
from vcp_screener.db import get_session, init_db
from vcp_screener.models.backtest import BacktestRun, BacktestTrade, BacktestEquity
from vcp_screener.models.daily_price import DailyPrice
from vcp_screener.models.stock import Stock
from vcp_screener.services.indicators import compute_rs_raw, compute_rs_percentiles, average_volume
from vcp_screener.services.trend_template import check_trend_template
from vcp_screener.services.vcp_detector import detect_contractions, score_vcp

logger = logging.getLogger(__name__)


def _load_all_prices(session) -> dict[str, pd.DataFrame]:
    """Load all price data into memory, keyed by symbol."""
    symbols = [s[0] for s in session.query(Stock.symbol).filter(Stock.is_active == True).all()]
    all_data = {}
    for sym in symbols:
        rows = (
            session.query(DailyPrice)
            .filter(DailyPrice.symbol == sym)
            .order_by(DailyPrice.date)
            .all()
        )
        if not rows:
            continue
        df = pd.DataFrame([{
            "date": r.date, "open": r.open, "high": r.high,
            "low": r.low, "close": r.close, "volume": r.volume,
        } for r in rows])
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        all_data[sym] = df
    return all_data


def _screen_on_date(all_data: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> list[dict]:
    """Run screening using only data available up to as_of (no look-ahead)."""
    rs_raw = {}
    filtered = {}

    for sym, full_df in all_data.items():
        df = full_df[full_df.index <= as_of]
        if len(df) < settings.min_trading_days:
            continue
        last_close = df["close"].iloc[-1]
        if last_close < settings.min_price:
            continue
        if settings.max_price and last_close > settings.max_price:
            continue
        if average_volume(df["volume"]) < settings.min_avg_volume:
            continue
        filtered[sym] = df
        rs_raw[sym] = compute_rs_raw(df["close"])

    if not filtered:
        return []

    rs_pct = compute_rs_percentiles(rs_raw)
    candidates = []

    for sym, df in filtered.items():
        pct = rs_pct.get(sym, 0)
        trend = check_trend_template(df["close"], pct)
        if not trend["passes"]:
            continue

        vcp = detect_contractions(df["high"], df["low"], df["close"], df["volume"])
        if not vcp["found"]:
            continue

        sc = score_vcp(vcp)
        avg_vol = average_volume(df["volume"])

        candidates.append({
            "symbol": sym,
            "close": float(df["close"].iloc[-1]),
            "vcp_score": sc,
            "rs_percentile": pct,
            "pivot_price": vcp.get("pivot_price"),
            "avg_volume": avg_vol,
        })

    candidates.sort(key=lambda x: (-x["vcp_score"], -x["rs_percentile"]))
    return candidates[:settings.top_n]


class BacktestEngine:
    """Event-driven backtesting engine with breakout confirmation."""

    def __init__(self, initial_capital: float = None, max_positions: int = None):
        self.initial_capital = initial_capital or settings.account_size
        self.max_positions = max_positions or settings.max_positions
        self.cash = self.initial_capital
        self.positions: list[dict] = []
        self.closed_trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.peak_equity = self.initial_capital
        # Watchlist: candidates waiting for breakout confirmation
        self.watchlist: list[dict] = []

    def _current_equity(self, all_data: dict, as_of: pd.Timestamp) -> float:
        equity = self.cash
        for pos in self.positions:
            sym = pos["symbol"]
            if sym in all_data:
                df = all_data[sym]
                df_slice = df[df.index <= as_of]
                if not df_slice.empty:
                    equity += df_slice["close"].iloc[-1] * pos["shares"]
        return equity

    def _check_stops(self, all_data: dict, current_date: pd.Timestamp):
        """Check and execute stops for all open positions."""
        to_close = []
        for pos in self.positions:
            sym = pos["symbol"]
            if sym not in all_data:
                continue
            df = all_data[sym]
            df_today = df[df.index == current_date]
            if df_today.empty:
                continue

            current_price = float(df_today["close"].iloc[0])
            today_low = float(df_today["low"].iloc[0])

            # Update highest price
            if current_price > pos["highest_price"]:
                pos["highest_price"] = current_price

            gain_pct = (current_price / pos["entry_price"] - 1) * 100

            # Update trailing stop
            if gain_pct >= settings.trailing_stop_trigger_pct:
                new_trail = pos["highest_price"] * (1 - settings.trailing_stop_pct / 100)
                if pos["trailing_stop"] is None or new_trail > pos["trailing_stop"]:
                    pos["trailing_stop"] = new_trail
            elif gain_pct >= settings.breakeven_trigger_pct:
                if pos["trailing_stop"] is None or pos["entry_price"] > pos["trailing_stop"]:
                    pos["trailing_stop"] = pos["entry_price"]

            effective_stop = max(pos["stop_loss"], pos["trailing_stop"] or 0)

            if today_low <= effective_stop:
                exit_price = effective_stop
                reason = "trailing_stop" if pos["trailing_stop"] and effective_stop == pos["trailing_stop"] else "stop_loss"
                to_close.append((pos, exit_price, reason, current_date))

        for pos, exit_price, reason, dt in to_close:
            self._close_position(pos, exit_price, reason, dt)

    def _close_position(self, pos: dict, exit_price: float, reason: str, exit_date: pd.Timestamp):
        pnl = (exit_price - pos["entry_price"]) * pos["shares"]
        pnl_pct = (exit_price / pos["entry_price"] - 1) * 100
        hold_days = (exit_date - pos["entry_date"]).days

        self.cash += exit_price * pos["shares"]
        self.positions.remove(pos)
        self.closed_trades.append({
            "symbol": pos["symbol"],
            "entry_date": pos["entry_date"],
            "entry_price": pos["entry_price"],
            "shares": pos["shares"],
            "exit_date": exit_date,
            "exit_price": exit_price,
            "exit_reason": reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "hold_days": hold_days,
        })

    def _check_breakouts(self, all_data: dict, current_date: pd.Timestamp):
        """Check watchlist for breakout confirmations.

        A breakout is confirmed when:
        1. Price closes above the pivot price
        2. Volume is >= 1.5x the 50-day average
        """
        if len(self.positions) >= self.max_positions:
            return

        held_symbols = {p["symbol"] for p in self.positions}
        triggered = []

        for candidate in self.watchlist:
            sym = candidate["symbol"]
            if sym in held_symbols:
                continue
            if sym not in all_data:
                continue

            df = all_data[sym]
            df_today = df[df.index == current_date]
            if df_today.empty:
                continue

            today_close = float(df_today["close"].iloc[0])
            today_high = float(df_today["high"].iloc[0])
            today_volume = float(df_today["volume"].iloc[0])
            pivot = candidate["pivot_price"]
            avg_vol = candidate["avg_volume"]

            # Breakout confirmation: close above pivot + volume surge
            if today_close > pivot and today_volume >= avg_vol * settings.breakout_volume_mult:
                triggered.append((candidate, today_close))
                if len(self.positions) + len(triggered) >= self.max_positions:
                    break

        # Enter confirmed breakouts (sorted by VCP score)
        triggered.sort(key=lambda x: -x[0]["vcp_score"])
        for candidate, entry_price in triggered:
            if len(self.positions) >= self.max_positions:
                break
            self._enter_position_at_price(candidate, entry_price, current_date)
            # Remove from watchlist
            if candidate in self.watchlist:
                self.watchlist.remove(candidate)

    def _enter_position_at_price(self, candidate: dict, entry_price: float, entry_date: pd.Timestamp):
        """Enter a position at a confirmed breakout price."""
        stop_price = entry_price * (1 - settings.default_stop_loss_pct / 100)

        risk_amount = self.cash * (settings.risk_per_trade_pct / 100)
        risk_per_share = entry_price - stop_price
        if risk_per_share <= 0:
            return
        shares = int(risk_amount / risk_per_share)
        if shares <= 0:
            return

        cost = entry_price * shares
        if cost > self.cash:
            shares = int(self.cash / entry_price)
            if shares <= 0:
                return
            cost = entry_price * shares

        self.cash -= cost
        self.positions.append({
            "symbol": candidate["symbol"],
            "entry_date": entry_date,
            "entry_price": entry_price,
            "shares": shares,
            "stop_loss": stop_price,
            "trailing_stop": None,
            "highest_price": entry_price,
        })

    def _expire_watchlist(self, current_date: pd.Timestamp):
        """Remove stale candidates from watchlist."""
        expiry = settings.breakout_watchlist_expiry_days
        self.watchlist = [
            c for c in self.watchlist
            if (current_date - c["added_date"]).days <= expiry
        ]

    def run(self, start_date: date, end_date: date, screen_interval_days: int = 5) -> dict:
        """Run the backtest over the given date range."""
        init_db()
        session = get_session()

        try:
            logger.info("Loading all price data...")
            all_data = _load_all_prices(session)
            logger.info(f"Loaded data for {len(all_data)} stocks")

            all_dates = set()
            for df in all_data.values():
                all_dates.update(df.index)
            trading_days = sorted([
                d for d in all_dates
                if start_date <= d.date() <= end_date
            ])

            if not trading_days:
                return {"error": "No trading days in range"}

            logger.info(f"Backtesting {len(trading_days)} trading days from {start_date} to {end_date}")

            last_screen_date = None

            for i, current_date in enumerate(trading_days):
                # 1. Check stops first
                self._check_stops(all_data, current_date)

                # 2. Check watchlist for breakout confirmations
                self._check_breakouts(all_data, current_date)

                # 3. Expire stale watchlist entries
                self._expire_watchlist(current_date)

                # 4. Run screening periodically and add to watchlist
                should_screen = (
                    last_screen_date is None or
                    (current_date - last_screen_date).days >= screen_interval_days
                )

                if should_screen:
                    screen_results = _screen_on_date(all_data, current_date)
                    last_screen_date = current_date

                    # Add new candidates to watchlist (avoid duplicates)
                    watchlist_symbols = {c["symbol"] for c in self.watchlist}
                    held_symbols = {p["symbol"] for p in self.positions}
                    for candidate in screen_results:
                        sym = candidate["symbol"]
                        if sym not in watchlist_symbols and sym not in held_symbols:
                            candidate["added_date"] = current_date
                            self.watchlist.append(candidate)

                # 5. Record equity
                equity = self._current_equity(all_data, current_date)
                if equity > self.peak_equity:
                    self.peak_equity = equity
                drawdown = (self.peak_equity - equity) / self.peak_equity * 100

                self.equity_curve.append({
                    "date": current_date,
                    "equity": equity,
                    "drawdown_pct": drawdown,
                })

                if (i + 1) % 50 == 0:
                    logger.info(f"  Day {i + 1}/{len(trading_days)}: equity=Rs {equity:,.0f} "
                                f"(positions={len(self.positions)}, watchlist={len(self.watchlist)})")

            # Close remaining positions at last day's close
            final_date = trading_days[-1]
            for pos in list(self.positions):
                sym = pos["symbol"]
                if sym in all_data:
                    df = all_data[sym]
                    df_final = df[df.index <= final_date]
                    if not df_final.empty:
                        self._close_position(pos, float(df_final["close"].iloc[-1]), "end_of_backtest", final_date)

            return self._compute_metrics(start_date, end_date)

        finally:
            session.close()

    def _compute_metrics(self, start_date: date, end_date: date) -> dict:
        """Compute performance metrics from closed trades and equity curve."""
        trades = self.closed_trades
        if not trades:
            return {
                "total_trades": 0,
                "final_capital": self.cash,
                "total_return_pct": (self.cash / self.initial_capital - 1) * 100,
            }

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]

        total_gains = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))

        equity_values = [e["equity"] for e in self.equity_curve]
        max_dd = max(e["drawdown_pct"] for e in self.equity_curve) if self.equity_curve else 0

        if len(equity_values) >= 2:
            daily_returns = pd.Series(equity_values).pct_change().dropna()
            sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
        else:
            sharpe = 0

        years = (end_date - start_date).days / 365.25
        final_equity = equity_values[-1] if equity_values else self.cash
        cagr = ((final_equity / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        return {
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": self.initial_capital,
            "final_capital": round(final_equity, 2),
            "total_return_pct": round((final_equity / self.initial_capital - 1) * 100, 2),
            "cagr_pct": round(cagr, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "profit_factor": round(total_gains / total_losses, 2) if total_losses > 0 else float("inf"),
            "avg_gain_pct": round(np.mean([t["pnl_pct"] for t in wins]), 2) if wins else 0,
            "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losses]), 2) if losses else 0,
            "avg_hold_days": round(np.mean([t["hold_days"] for t in trades]), 1),
            "trades": trades,
            "equity_curve": self.equity_curve,
        }


def run_backtest(
    start_date: date,
    end_date: date,
    initial_capital: float = None,
    max_positions: int = None,
    save: bool = True,
) -> dict:
    """Run a backtest and optionally save results to DB."""
    engine = BacktestEngine(initial_capital=initial_capital, max_positions=max_positions)
    results = engine.run(start_date, end_date)

    if save and "error" not in results and results.get("total_trades", 0) > 0:
        _save_backtest_results(results)

    return results


def _save_backtest_results(results: dict):
    """Save backtest results to DB."""
    session = get_session()
    try:
        run = BacktestRun(
            start_date=results["start_date"],
            end_date=results["end_date"],
            initial_capital=results["initial_capital"],
            final_capital=results["final_capital"],
            total_return_pct=results["total_return_pct"],
            cagr_pct=results.get("cagr_pct"),
            max_drawdown_pct=results["max_drawdown_pct"],
            sharpe_ratio=results.get("sharpe_ratio"),
            win_rate_pct=results["win_rate_pct"],
            profit_factor=results.get("profit_factor"),
            total_trades=results["total_trades"],
            avg_gain_pct=results.get("avg_gain_pct"),
            avg_loss_pct=results.get("avg_loss_pct"),
            avg_hold_days=results.get("avg_hold_days"),
        )
        session.add(run)
        session.flush()

        for t in results.get("trades", []):
            trade = BacktestTrade(
                run_id=run.id,
                symbol=t["symbol"],
                entry_date=t["entry_date"],
                entry_price=t["entry_price"],
                shares=t["shares"],
                exit_date=t["exit_date"],
                exit_price=t["exit_price"],
                exit_reason=t["exit_reason"],
                pnl=t["pnl"],
                pnl_pct=t["pnl_pct"],
                hold_days=t["hold_days"],
            )
            session.add(trade)

        for e in results.get("equity_curve", []):
            eq = BacktestEquity(
                run_id=run.id,
                date=e["date"],
                equity=e["equity"],
                drawdown_pct=e["drawdown_pct"],
            )
            session.add(eq)

        session.commit()
        logger.info(f"Saved backtest run #{run.id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving backtest: {e}")
    finally:
        session.close()
