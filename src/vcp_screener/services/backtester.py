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
            "base_low": vcp.get("base_low"),
            "avg_volume": avg_vol,
        })

    candidates.sort(key=lambda x: (-x["vcp_score"], -x["rs_percentile"]))
    return candidates[:settings.top_n]


def precompute_mr_indicators(all_data: dict) -> dict:
    """Precompute all MR indicators for each stock.

    Returns dict of symbol -> DataFrame with columns:
    sma20, std20, sma200, rsi2, ibs, avg_vol, vol
    """
    from vcp_screener.services.indicators import rsi as compute_rsi, internal_bar_strength

    indicators = {}
    for sym, df in all_data.items():
        if len(df) < 50:
            continue
        close = df["close"]
        ind = pd.DataFrame(index=df.index)
        ind["close"] = close
        ind["sma20"] = close.rolling(20).mean()
        ind["std20"] = close.rolling(20).std()
        ind["sma200"] = close.rolling(200, min_periods=200).mean()
        ind["rsi2"] = compute_rsi(close, period=2)
        ind["ibs"] = internal_bar_strength(df["high"], df["low"], close)
        ind["vol"] = df["volume"]
        ind["avg_vol"] = df["volume"].rolling(50, min_periods=10).mean()
        # Precompute "any of last N days had high volume" for lookbacks 1-5
        for lb in [1, 2, 3, 5]:
            high_vol = (df["volume"] > ind["avg_vol"] * 1.5).astype(float)
            ind[f"vol_ok_{lb}"] = high_vol.rolling(lb, min_periods=1).max()
        indicators[sym] = ind
    return indicators


def precompute_mr_candidates(all_data: dict, start_date: date, end_date: date,
                             screen_interval_days: int = 5) -> dict:
    """Precompute mean reversion candidates for all screen dates.

    Returns dict of pd.Timestamp -> list[dict].
    """
    all_dates = set()
    for df in all_data.values():
        all_dates.update(df.index)
    trading_days = sorted([
        d for d in all_dates
        if start_date <= d.date() <= end_date
    ])

    mr_screens = {}
    last_screen_date = None

    for current_date in trading_days:
        should_screen = (
            last_screen_date is None or
            (current_date - last_screen_date).days >= screen_interval_days
        )
        if not should_screen:
            continue
        last_screen_date = current_date

        candidates = []
        for sym, full_df in all_data.items():
            df = full_df[full_df.index <= current_date]
            if len(df) < 50:
                continue
            close = df["close"]
            current_price = float(close.iloc[-1])
            if current_price < settings.min_price:
                continue
            sma20 = float(close.rolling(20).mean().iloc[-1])
            std20 = float(close.rolling(20).std().iloc[-1])
            if std20 <= 0:
                continue
            today_volume = float(df["volume"].iloc[-1])
            avg_volume = float(df["volume"].iloc[-50:].mean())
            if current_price < sma20 - 2 * std20 and today_volume > avg_volume * 1.5:
                z_score = (current_price - sma20) / std20
                candidates.append({
                    "symbol": sym, "close": current_price,
                    "sma20": sma20, "z_score": z_score,
                })

        candidates.sort(key=lambda x: x["z_score"])
        mr_screens[current_date] = candidates[:5]

    return mr_screens


def precompute_screens(all_data: dict, start_date: date, end_date: date,
                       screen_interval_days: int = 5) -> dict:
    """Precompute VCP screening results for all screen dates.

    Returns dict of pd.Timestamp -> list[dict] (candidates).
    Use with BacktestEngine.run(precomputed_screens=...) to skip screening.
    """
    all_dates = set()
    for df in all_data.values():
        all_dates.update(df.index)
    trading_days = sorted([
        d for d in all_dates
        if start_date <= d.date() <= end_date
    ])

    screens = {}
    last_screen_date = None

    for current_date in trading_days:
        should_screen = (
            last_screen_date is None or
            (current_date - last_screen_date).days >= screen_interval_days
        )
        if should_screen:
            screens[current_date] = _screen_on_date(all_data, current_date)
            last_screen_date = current_date

    return screens


def load_backtest_data() -> tuple[dict, "pd.DataFrame"]:
    """Load all price data and precompute breadth. Returns (all_data, breadth_df).

    Use this to load data once for parameter sweeps.
    """
    init_db()
    session = get_session()
    try:
        all_data = _load_all_prices(session)
    finally:
        session.close()
    # Use a temporary engine to compute breadth
    engine = BacktestEngine.__new__(BacktestEngine)
    breadth = engine._precompute_breadth(all_data)
    return all_data, breadth


class BacktestEngine:
    """Event-driven backtesting engine with breakout confirmation."""

    def __init__(self, initial_capital: float = None, max_positions: int = None,
                 eq_ma_days: int = 40, dd_max_positions: int = 3, dd_risk_mult: float = 1.0,
                 mr_config: dict = None):
        # Best EqMA configs from 129-config sweep (2021-2025):
        #   Winner:    eq_ma_days=40, dd_max_positions=3, dd_risk_mult=1.0  → 1026.1%, 32.0% MaxDD, 1.98 Sharpe
        #   Runner-up: eq_ma_days=40, dd_max_positions=4, dd_risk_mult=0.75 → 1057.0%, 33.1% MaxDD, 1.97 Sharpe
        self.initial_capital = initial_capital or settings.account_size
        self.max_positions = max_positions or settings.max_positions
        self.cash = self.initial_capital
        self.positions: list[dict] = []
        self.closed_trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.peak_equity = self.initial_capital
        # Watchlist: candidates waiting for breakout confirmation
        self.watchlist: list[dict] = []
        # Equity Curve MA parameters (0 = disabled)
        self.eq_ma_days = eq_ma_days
        self.dd_max_positions = dd_max_positions
        self.dd_risk_mult = dd_risk_mult
        # Mean Reversion parameters
        # Best config from 35-combo sweep (10Y, 2016-2026):
        #   Stop12+RSI<5: 2663%, 27.4% DD, 1.63 Sharpe, 2.02 PF
        #   Runner-up: Exit+Ent1.5+RSI<5+IBS<0.2: 3150%, 24.8% DD, 1.61 Sharpe
        self.mr = {
            "stop_pct": 12,          # Stop loss percentage (was 5, widened per sweep)
            "target": "sma20",       # Exit target: "sma20", "sma10", "sma5", "rsi"
            "rsi_exit": 0,           # RSI(2) exit threshold (0 = disabled)
            "timeout_days": 15,      # Max holding period
            "max_positions": 3,      # Max MR positions
            "risk_pct": 1.5,         # Risk per trade %
            "entry_std": 2.0,        # Bollinger Band std dev threshold
            "require_rsi": True,     # Require RSI(2) < rsi_entry (was False)
            "rsi_entry": 5,          # RSI(2) entry threshold (was 10)
            "require_ibs": False,    # Require IBS < ibs_entry
            "ibs_entry": 0.3,        # IBS entry threshold
            "require_uptrend": False, # Require price > SMA(200)
            "all_regimes": False,    # Activate MR in all regimes (not just BEARISH)
            "vol_lookback": 1,       # Volume check: 1=today only, 3=any of last 3 days
        }
        if mr_config:
            self.mr.update(mr_config)

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

    def _precompute_breadth(self, all_data: dict) -> pd.DataFrame:
        """Precompute market breadth (% of stocks above 50-day SMA) and its trend.

        Uses our own stock universe for reliable regime detection
        without depending on external Nifty 50 data downloads.
        Returns DataFrame with 'breadth' and 'breadth_sma' columns.
        """
        above_sma = {}
        for sym, df in all_data.items():
            if len(df) >= 50:
                sma50 = df["close"].rolling(50, min_periods=50).mean()
                above_sma[sym] = df["close"] > sma50

        if not above_sma:
            return pd.DataFrame()

        df_above = pd.concat(above_sma, axis=1)
        raw_breadth = df_above.mean(axis=1) * 100
        smoothed = raw_breadth.rolling(10, min_periods=1).mean()
        breadth_sma = smoothed.rolling(10, min_periods=1).mean()

        return pd.DataFrame({
            "breadth": smoothed,
            "breadth_sma": breadth_sma,
        })

    def _check_stops(self, all_data: dict, current_date: pd.Timestamp):
        """Check and execute stops for VCP positions, including advanced sell signals."""
        to_close = []
        for pos in self.positions:
            # Skip mean reversion positions (handled by _check_mr_exits)
            if pos.get("strategy") == "mean_reversion":
                continue
            sym = pos["symbol"]
            if sym not in all_data:
                continue
            df = all_data[sym]
            df_slice = df[df.index <= current_date]
            if df_slice.empty:
                continue

            current_price = float(df_slice["close"].iloc[-1])
            today_low = float(df_slice["low"].iloc[-1])
            today_high = float(df_slice["high"].iloc[-1])
            today_open = float(df_slice["open"].iloc[-1])
            today_volume = float(df_slice["volume"].iloc[-1])

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

            # 1. Hard Stops & Trailing Stops
            if today_low <= effective_stop:
                exit_price = effective_stop
                reason = "trailing_stop" if pos["trailing_stop"] and effective_stop == pos["trailing_stop"] else "stop_loss"
                to_close.append((pos, exit_price, reason, current_date))
                continue

            # Advanced Sell Signals
            if len(df_slice) >= 2:
                prev_close = float(df_slice["close"].iloc[-2])
                daily_change_pct = (current_price / prev_close - 1) * 100
                avg_vol = float(df_slice["volume"].iloc[-50:].mean()) if len(df_slice) >= 50 else float(df_slice["volume"].mean())

                # 2. High Volume Decline (Climax Top / Institutional Distribution)
                if daily_change_pct <= -4 and today_volume > avg_vol * 1.5:
                    to_close.append((pos, current_price, "high_vol_decline", current_date))
                    continue

                # 3. Exhaustion Gap
                if (today_open > prev_close * 1.02 and
                        (today_high - current_price) > (current_price - today_low) * 2):
                    to_close.append((pos, current_price, "exhaustion_gap", current_date))
                    continue

            # 4. Protect 20%+ Gain (Never let it turn into a loss)
            if (pos["highest_price"] / pos["entry_price"] - 1) >= 0.20:
                if current_price <= pos["entry_price"]:
                    to_close.append((pos, pos["entry_price"], "protect_20pct_gain", current_date))
                    continue

            # 5. Failed Breakout: price falls 5% below pivot after entry
            pivot = pos.get("pivot_price")
            if pivot and current_price < pivot * 0.97:
                to_close.append((pos, current_price, "failed_breakout", current_date))
                continue

        for pos, exit_price, reason, dt in to_close:
            if pos in self.positions:  # Check if not already closed
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
        1. Price closes >= 1% above the pivot price (minimum gap)
        2. Volume is >= 1.3x the 50-day average
        """
        # Market Regime Filter: Prevent VCP entries in BEARISH markets
        regime = self._get_current_regime(current_date)
        if regime == "BEARISH":
            return

        # Equity Curve MA: reduce exposure during drawdowns
        effective_max = self.max_positions
        risk_mult = 1.0
        if self.eq_ma_days > 0 and len(self.equity_curve) >= self.eq_ma_days:
            recent_eq = [e["equity"] for e in self.equity_curve[-self.eq_ma_days:]]
            equity_ma = sum(recent_eq) / len(recent_eq)
            current_eq = self._current_equity(all_data, current_date)
            if current_eq < equity_ma:
                effective_max = self.dd_max_positions
                risk_mult = self.dd_risk_mult

        if len(self.positions) >= effective_max:
            return

        # Compounding: use current total equity for position sizing
        current_equity = self._current_equity(all_data, current_date)

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
                if len(self.positions) + len(triggered) >= effective_max:
                    break

        # Enter confirmed breakouts (sorted by VCP score)
        triggered.sort(key=lambda x: -x[0]["vcp_score"])
        for candidate, entry_price in triggered:
            if len(self.positions) >= effective_max:
                break
            self._enter_position_at_price(
                candidate, entry_price, current_date,
                current_equity=current_equity, risk_mult=risk_mult,
            )
            # Remove from watchlist
            if candidate in self.watchlist:
                self.watchlist.remove(candidate)

    def _enter_position_at_price(
        self, candidate: dict, entry_price: float, entry_date: pd.Timestamp,
        current_equity: float = None, risk_mult: float = 1.0,
    ):
        """Enter a position at a confirmed breakout price."""
        stop_price = entry_price * (1 - settings.default_stop_loss_pct / 100)

        # Compounding: use current equity for position sizing
        sizing_capital = current_equity or self.initial_capital

        risk_amount = sizing_capital * (settings.risk_per_trade_pct / 100) * risk_mult
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
            "strategy": "vcp",
            "vcp_score": candidate.get("vcp_score", 0),
            "base_low": candidate.get("base_low"),
            "pivot_price": candidate.get("pivot_price"),
        })

    def _expire_watchlist(self, current_date: pd.Timestamp):
        """Remove stale candidates from watchlist."""
        expiry = settings.breakout_watchlist_expiry_days
        self.watchlist = [
            c for c in self.watchlist
            if (current_date - c["added_date"]).days <= expiry
        ]

    def _get_current_regime(self, current_date: pd.Timestamp) -> str:
        """Get market regime based on internal breadth indicator."""
        if self.breadth_data is None or self.breadth_data.empty:
            return "BULLISH"
        valid = self.breadth_data[self.breadth_data.index <= current_date]
        if valid.empty:
            return "BULLISH"
        breadth = float(valid["breadth"].iloc[-1])
        if breadth >= 55:
            return "BULLISH"
        elif breadth >= 35:
            return "CAUTIOUS"
        else:
            return "BEARISH"

    def _manage_regime(self, all_data: dict, current_date: pd.Timestamp, regime: str):
        """Defensive cash management based on market regime.

        BEARISH: Close VCP positions that are currently at a loss (cut losers).
        CAUTIOUS: No forced exits (trailing stops handle protection).
        """
        if regime != "BEARISH":
            return

        vcp_positions = [p for p in self.positions if p.get("strategy", "vcp") == "vcp"]
        for pos in list(vcp_positions):
            sym = pos["symbol"]
            if sym in all_data:
                df_slice = all_data[sym][all_data[sym].index <= current_date]
                if not df_slice.empty and pos in self.positions:
                    current_price = float(df_slice["close"].iloc[-1])
                    # Only close positions that are losing money
                    if current_price < pos["entry_price"]:
                        self._close_position(
                            pos, current_price, "regime_cut_loser", current_date,
                        )

    def _check_mr_exits(self, all_data: dict, current_date: pd.Timestamp):
        """Check mean reversion positions for exits."""
        from vcp_screener.services.indicators import rsi as compute_rsi

        to_close = []
        for pos in self.positions:
            if pos.get("strategy") != "mean_reversion":
                continue
            sym = pos["symbol"]
            if sym not in all_data:
                continue
            df_slice = all_data[sym][all_data[sym].index <= current_date]
            if df_slice.empty:
                continue

            current_price = float(df_slice["close"].iloc[-1])
            today_low = float(df_slice["low"].iloc[-1])

            # Stop loss
            if today_low <= pos["stop_loss"]:
                to_close.append((pos, pos["stop_loss"], "mr_stop", current_date))
                continue

            # RSI-based exit (sell on strength)
            if self.mr["rsi_exit"] > 0 and len(df_slice) >= 3:
                rsi_val = float(compute_rsi(df_slice["close"], period=2).iloc[-1])
                if rsi_val > self.mr["rsi_exit"]:
                    to_close.append((pos, current_price, "mr_rsi_exit", current_date))
                    continue

            # SMA target
            target = self.mr["target"]
            if target == "sma20" and len(df_slice) >= 20:
                sma_val = float(df_slice["close"].rolling(20).mean().iloc[-1])
                if current_price >= sma_val:
                    to_close.append((pos, current_price, "mr_target", current_date))
                    continue
            elif target == "sma10" and len(df_slice) >= 10:
                sma_val = float(df_slice["close"].rolling(10).mean().iloc[-1])
                if current_price >= sma_val:
                    to_close.append((pos, current_price, "mr_target", current_date))
                    continue
            elif target == "sma5" and len(df_slice) >= 5:
                sma_val = float(df_slice["close"].rolling(5).mean().iloc[-1])
                if current_price >= sma_val:
                    to_close.append((pos, current_price, "mr_target", current_date))
                    continue

            # Time limit
            hold_days = (current_date - pos["entry_date"]).days
            if hold_days >= self.mr["timeout_days"]:
                to_close.append((pos, current_price, "mr_timeout", current_date))

        for pos, exit_price, reason, dt in to_close:
            if pos in self.positions:
                self._close_position(pos, exit_price, reason, dt)

    def _enter_mean_reversion(self, all_data: dict, current_date: pd.Timestamp,
                              precomputed_mr: dict = None, mr_indicators: dict = None):
        """Screen and enter mean reversion trades. Configurable via self.mr dict."""
        mr_count = sum(1 for p in self.positions if p.get("strategy") == "mean_reversion")
        max_mr = self.mr["max_positions"]
        if mr_count >= max_mr:
            return

        current_equity = self._current_equity(all_data, current_date)
        held_symbols = {p["symbol"] for p in self.positions}
        entry_std = self.mr["entry_std"]
        vol_lb = min(self.mr["vol_lookback"], 5)
        vol_col = f"vol_ok_{vol_lb}" if vol_lb in (1, 2, 3, 5) else "vol_ok_1"

        candidates = []

        if mr_indicators:
            # Fast path: use precomputed indicators
            for sym, ind in mr_indicators.items():
                if sym in held_symbols:
                    continue
                row = ind[ind.index <= current_date]
                if row.empty:
                    continue
                last = row.iloc[-1]
                cp = float(last["close"])
                if cp < settings.min_price:
                    continue
                sma20 = last["sma20"]
                std20 = last["std20"]
                if pd.isna(sma20) or pd.isna(std20) or std20 <= 0:
                    continue
                if cp >= sma20 - entry_std * std20:
                    continue
                if vol_col in last and not last[vol_col]:
                    continue
                if self.mr["require_rsi"] and last["rsi2"] >= self.mr["rsi_entry"]:
                    continue
                if self.mr["require_ibs"] and last["ibs"] >= self.mr["ibs_entry"]:
                    continue
                if self.mr["require_uptrend"] and not pd.isna(last["sma200"]) and cp < last["sma200"]:
                    continue
                z_score = (cp - sma20) / std20
                candidates.append({"symbol": sym, "close": cp, "sma20": float(sma20), "z_score": float(z_score)})
        else:
            # Slow path: compute on the fly
            from vcp_screener.services.indicators import rsi as compute_rsi, internal_bar_strength
            for sym, full_df in all_data.items():
                if sym in held_symbols:
                    continue
                df = full_df[full_df.index <= current_date]
                if len(df) < 50:
                    continue
                close = df["close"]
                current_price = float(close.iloc[-1])
                if current_price < settings.min_price:
                    continue
                sma20 = float(close.rolling(20).mean().iloc[-1])
                std20 = float(close.rolling(20).std().iloc[-1])
                if std20 <= 0:
                    continue
                if current_price >= sma20 - entry_std * std20:
                    continue
                avg_volume = float(df["volume"].iloc[-50:].mean())
                vol_ok = any(
                    float(df["volume"].iloc[-(vi + 1)]) > avg_volume * 1.5
                    for vi in range(min(vol_lb, len(df)))
                )
                if not vol_ok:
                    continue
                if self.mr["require_rsi"]:
                    if float(compute_rsi(close, period=2).iloc[-1]) >= self.mr["rsi_entry"]:
                        continue
                if self.mr["require_ibs"]:
                    if float(internal_bar_strength(df["high"], df["low"], close).iloc[-1]) >= self.mr["ibs_entry"]:
                        continue
                if self.mr["require_uptrend"] and len(df) >= 200:
                    if current_price < float(close.rolling(200).mean().iloc[-1]):
                        continue
                z_score = (current_price - sma20) / std20
                candidates.append({"symbol": sym, "close": current_price, "sma20": sma20, "z_score": z_score})

        candidates.sort(key=lambda x: x["z_score"])

        stop_pct = self.mr["stop_pct"] / 100
        risk_pct = self.mr["risk_pct"] / 100

        for c in candidates[:5]:
            if mr_count >= max_mr:
                break

            entry_price = c["close"]
            stop_price = entry_price * (1 - stop_pct)

            risk_amount = current_equity * risk_pct
            risk_per_share = entry_price - stop_price
            if risk_per_share <= 0:
                continue
            shares = int(risk_amount / risk_per_share)
            if shares <= 0:
                continue

            cost = entry_price * shares
            if cost > self.cash:
                shares = int(self.cash / entry_price)
                if shares <= 0:
                    continue
                cost = entry_price * shares

            self.cash -= cost
            self.positions.append({
                "symbol": c["symbol"],
                "entry_date": current_date,
                "entry_price": entry_price,
                "shares": shares,
                "stop_loss": stop_price,
                "trailing_stop": None,
                "highest_price": entry_price,
                "strategy": "mean_reversion",
            })
            mr_count += 1

    def _check_rotations(self, all_data: dict, current_date: pd.Timestamp):
        """Rotate failing VCP positions into better confirmed breakouts.

        A position qualifies for rotation if:
        - It is at > 4% loss (clearly failing)
        - OR price has dropped below the VCP base low (pattern broken)

        The new candidate must have a higher VCP score AND a confirmed
        breakout today (above pivot + volume).
        """
        # Find failing VCP positions
        failing = []
        for pos in self.positions:
            if pos.get("strategy") != "vcp":
                continue
            sym = pos["symbol"]
            if sym not in all_data:
                continue
            df_slice = all_data[sym][all_data[sym].index <= current_date]
            if df_slice.empty:
                continue

            current_price = float(df_slice["close"].iloc[-1])
            gain_pct = (current_price / pos["entry_price"] - 1) * 100
            base_low = pos.get("base_low")

            # Condition 1: > 4% loss
            is_losing = gain_pct < -4
            # Condition 2: price dropped below VCP base (pattern broken)
            below_base = base_low is not None and current_price < base_low

            if is_losing or below_base:
                reason = "below_base" if below_base else "loss_gt_4pct"
                failing.append((pos, current_price, gain_pct, reason))

        if not failing:
            return

        # Find confirmed breakouts in watchlist
        held_symbols = {p["symbol"] for p in self.positions}
        confirmed = []
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
            today_volume = float(df_today["volume"].iloc[0])
            pivot = candidate["pivot_price"]
            avg_vol = candidate["avg_volume"]

            if today_close > pivot and today_volume >= avg_vol * settings.breakout_volume_mult:
                confirmed.append((candidate, today_close))

        if not confirmed:
            return

        # Sort: best new candidates first, worst failing positions first
        confirmed.sort(key=lambda x: -x[0]["vcp_score"])
        failing.sort(key=lambda x: x[2])  # worst loss first

        current_equity = self._current_equity(all_data, current_date)

        for candidate, entry_price in confirmed:
            if not failing:
                break

            # Find a failing position with lower VCP score
            for i, (pos, exit_price, gain_pct, reason) in enumerate(failing):
                pos_score = pos.get("vcp_score", 0)
                if candidate["vcp_score"] > pos_score:
                    # Close failing position
                    self._close_position(pos, exit_price, f"rotation_{reason}", current_date)
                    # Enter new position
                    self._enter_position_at_price(
                        candidate, entry_price, current_date,
                        current_equity=current_equity,
                    )
                    # Remove from watchlist and failing list
                    if candidate in self.watchlist:
                        self.watchlist.remove(candidate)
                    failing.pop(i)
                    break

    def run(self, start_date: date, end_date: date, screen_interval_days: int = 5,
            preloaded_data: dict = None, preloaded_breadth: "pd.DataFrame | None" = None,
            precomputed_screens: dict = None, precomputed_mr: dict = None,
            precomputed_mr_ind: dict = None) -> dict:
        """Run the backtest over the given date range.

        Pass preloaded_data and preloaded_breadth to skip DB loading (for parameter sweeps).
        Pass precomputed_screens (dict of date -> candidates list) to skip VCP screening.
        """
        if preloaded_data is not None:
            all_data = preloaded_data
            self.breadth_data = preloaded_breadth if preloaded_breadth is not None else self._precompute_breadth(all_data)
        else:
            init_db()
            session = get_session()
            try:
                logger.info("Loading all price data...")
                all_data = _load_all_prices(session)
                logger.info(f"Loaded data for {len(all_data)} stocks")
                logger.info("Computing market breadth...")
                self.breadth_data = self._precompute_breadth(all_data)
            finally:
                session.close()
                session = None

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
            # 0. Get current market regime
            regime = self._get_current_regime(current_date)

            # 1. Check stops for VCP positions
            self._check_stops(all_data, current_date)

            # 2. Check mean reversion exits
            self._check_mr_exits(all_data, current_date)

            # 3. Regime management (disabled — lagging signals hurt more than help)
            # self._manage_regime(all_data, current_date, regime)

            # 4. Check watchlist for VCP breakout confirmations
            self._check_breakouts(all_data, current_date)

            # 5. Expire stale watchlist entries
            self._expire_watchlist(current_date)

            # 6. Run screening periodically and add to watchlist
            should_screen = (
                last_screen_date is None or
                (current_date - last_screen_date).days >= screen_interval_days
            )

            if should_screen:
                if precomputed_screens is not None:
                    screen_results = precomputed_screens.get(current_date, [])
                else:
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

            # 7. Mean reversion entries during BEARISH regime only
            mr_active = regime == "BEARISH" or self.mr.get("all_regimes", False)
            if mr_active and should_screen:
                self._enter_mean_reversion(all_data, current_date, mr_indicators=precomputed_mr_ind)

            # 8. Record equity
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
