"""Parameter sweep: test many strategy combinations and find the best one."""

import itertools
import logging
import sys
from datetime import date

from vcp_screener.config import settings
from vcp_screener.services.backtester import BacktestEngine, _load_all_prices, _screen_on_date
from vcp_screener.services.indicators import compute_rs_raw, compute_rs_percentiles, average_volume
from vcp_screener.services.trend_template import check_trend_template
from vcp_screener.services.vcp_detector import detect_contractions, score_vcp
from vcp_screener.db import get_session, init_db

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ── Parameter grid ──────────────────────────────────────────────
CONFIGS = [
    # name, sma_short, sma_mid, sma_long, stop%, breakeven%, trail_trigger%, trail%, risk%, max_pos, breakout_confirm, breakout_vol_mult, rs_weights, max_price

    # --- GROUP A: Original Minervini (baseline) ---
    ("A1_original_5pos",         50, 150, 200, 10, 15, 25, 10, 2.0, 5, False, 1.0, (0.40,0.20,0.20,0.20), 0),
    ("A2_original_4pos",         50, 150, 200, 10, 15, 25, 10, 2.5, 4, False, 1.0, (0.40,0.20,0.20,0.20), 0),

    # --- GROUP B: Fast SMAs only ---
    ("B1_fast_sma",              20,  50, 100, 10, 15, 25, 10, 2.0, 5, False, 1.0, (0.40,0.20,0.20,0.20), 0),
    ("B2_fast_sma_4pos",         20,  50, 100, 10, 15, 25, 10, 2.5, 4, False, 1.0, (0.40,0.20,0.20,0.20), 0),

    # --- GROUP C: Fast SMAs + recency RS ---
    ("C1_fast+recency",          20,  50, 100, 10, 15, 25, 10, 2.0, 5, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("C2_fast+recency_4pos",     20,  50, 100, 10, 15, 25, 10, 2.5, 4, False, 1.0, (0.50,0.25,0.15,0.10), 0),

    # --- GROUP D: Breakout confirmation ---
    ("D1_breakout_confirm",      50, 150, 200, 10, 15, 25, 10, 2.0, 5, True,  1.5, (0.40,0.20,0.20,0.20), 0),
    ("D2_fast+breakout",         20,  50, 100, 10, 15, 25, 10, 2.0, 5, True,  1.5, (0.40,0.20,0.20,0.20), 0),
    ("D3_fast+breakout+recency", 20,  50, 100, 10, 15, 25, 10, 2.0, 5, True,  1.5, (0.50,0.25,0.15,0.10), 0),
    ("D4_breakout_1.3x",         20,  50, 100, 10, 15, 25, 10, 2.0, 5, True,  1.3, (0.50,0.25,0.15,0.10), 0),

    # --- GROUP E: Tighter stops (8%) ---
    ("E1_8pct_stop",             50, 150, 200,  8, 12, 20, 10, 2.5, 5, False, 1.0, (0.40,0.20,0.20,0.20), 0),
    ("E2_fast+8pct",             20,  50, 100,  8, 12, 20, 10, 2.5, 5, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("E3_fast+8pct+breakout",    20,  50, 100,  8, 12, 20, 10, 2.5, 5, True,  1.5, (0.50,0.25,0.15,0.10), 0),

    # --- GROUP F: Aggressive (higher risk, more positions) ---
    ("F1_aggressive_5pos",       20,  50, 100, 10, 12, 20, 10, 3.0, 5, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("F2_aggressive_6pos",       20,  50, 100, 10, 12, 20, 10, 3.0, 6, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("F3_aggro+breakout",        20,  50, 100, 10, 12, 20, 10, 3.0, 5, True,  1.3, (0.50,0.25,0.15,0.10), 0),

    # --- GROUP G: Wider trail (let winners run more) ---
    ("G1_wide_trail",            50, 150, 200, 10, 15, 30, 12, 2.0, 5, False, 1.0, (0.40,0.20,0.20,0.20), 0),
    ("G2_fast+wide_trail",       20,  50, 100, 10, 15, 30, 12, 2.5, 5, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("G3_fast+wide+breakout",    20,  50, 100, 10, 15, 30, 12, 2.5, 5, True,  1.3, (0.50,0.25,0.15,0.10), 0),

    # --- GROUP H: Kitchen sink combos ---
    ("H1_fast+recency+aggro+wide",  20, 50, 100, 10, 12, 30, 12, 3.0, 5, False, 1.0, (0.50,0.25,0.15,0.10), 0),
    ("H2_best_guess",               20, 50, 100,  9, 12, 25, 10, 2.5, 5, True,  1.3, (0.50,0.25,0.15,0.10), 0),
]

# ── Test periods ────────────────────────────────────────────────
PERIODS = [
    ("2022_bull",    date(2022, 6, 1),  date(2022, 12, 31)),
    ("2023_H1",      date(2023, 1, 1),  date(2023, 6, 30)),
    ("2023_H2",      date(2023, 7, 1),  date(2023, 12, 31)),
    ("2024_bull",    date(2024, 1, 1),  date(2024, 9, 30)),
    ("2024_H2_corr", date(2024, 10, 1), date(2025, 3, 31)),
    ("2025_recent",  date(2025, 4, 1),  date(2026, 2, 18)),
]

CAPITAL = 100_000


def run_single_backtest(all_data, trading_days_cache, config, period_name, start, end):
    """Run one backtest with given parameters."""
    name, sma_s, sma_m, sma_l, stop, be_trig, trail_trig, trail, risk, max_pos, bkout, bkout_vol, rs_w, max_p = config

    # Override settings
    settings.sma_short = sma_s
    settings.sma_mid = sma_m
    settings.sma_long = sma_l
    settings.default_stop_loss_pct = stop
    settings.breakeven_trigger_pct = be_trig
    settings.trailing_stop_trigger_pct = trail_trig
    settings.trailing_stop_pct = trail
    settings.risk_per_trade_pct = risk
    settings.max_positions = max_pos
    settings.breakout_volume_mult = bkout_vol
    settings.max_price = max_p
    settings.rs_weight_3m = rs_w[0]
    settings.rs_weight_6m = rs_w[1]
    settings.rs_weight_9m = rs_w[2]
    settings.rs_weight_12m = rs_w[3]
    settings.account_size = CAPITAL
    settings.min_trading_days = 200

    # Get trading days for this period
    trading_days = [d for d in trading_days_cache if start <= d.date() <= end]
    if not trading_days:
        return None

    engine = BacktestEngine(initial_capital=CAPITAL, max_positions=max_pos)

    last_screen_date = None

    for i, current_date in enumerate(trading_days):
        engine._check_stops(all_data, current_date)

        if bkout:
            engine._check_breakouts(all_data, current_date)
            engine._expire_watchlist(current_date)

        should_screen = (
            last_screen_date is None or
            (current_date - last_screen_date).days >= 5
        )

        if should_screen:
            screen_results = _screen_on_date(all_data, current_date)
            last_screen_date = current_date

            if bkout:
                # Add to watchlist
                wl_syms = {c["symbol"] for c in engine.watchlist}
                held_syms = {p["symbol"] for p in engine.positions}
                for c in screen_results:
                    if c["symbol"] not in wl_syms and c["symbol"] not in held_syms:
                        c["added_date"] = current_date
                        engine.watchlist.append(c)
            else:
                # Direct entry at next day open
                if i + 1 < len(trading_days):
                    next_day = trading_days[i + 1]
                    slots = max_pos - len(engine.positions)
                    held_syms = {p["symbol"] for p in engine.positions}
                    for c in screen_results[:slots]:
                        if c["symbol"] not in held_syms:
                            engine._enter_position_at_price(c, float(all_data[c["symbol"]][all_data[c["symbol"]].index == next_day]["open"].iloc[0]) if c["symbol"] in all_data and not all_data[c["symbol"]][all_data[c["symbol"]].index == next_day].empty else c["close"], next_day)

        equity = engine._current_equity(all_data, current_date)
        if equity > engine.peak_equity:
            engine.peak_equity = equity
        dd = (engine.peak_equity - equity) / engine.peak_equity * 100
        engine.equity_curve.append({"date": current_date, "equity": equity, "drawdown_pct": dd})

    # Close remaining
    if trading_days:
        final = trading_days[-1]
        for pos in list(engine.positions):
            sym = pos["symbol"]
            if sym in all_data:
                df = all_data[sym]
                df_f = df[df.index <= final]
                if not df_f.empty:
                    engine._close_position(pos, float(df_f["close"].iloc[-1]), "end_of_backtest", final)

    return engine._compute_metrics(start, end)


def main():
    init_db()
    session = get_session()

    print("Loading all price data (one time)...")
    all_data = _load_all_prices(session)
    session.close()
    print(f"Loaded {len(all_data)} stocks\n")

    # Pre-compute all trading days
    all_dates = set()
    for df in all_data.values():
        all_dates.update(df.index)
    trading_days_cache = sorted(all_dates)

    # Results storage
    results = []

    total = len(CONFIGS) * len(PERIODS)
    done = 0

    for config in CONFIGS:
        name = config[0]
        period_results = {}

        for period_name, start, end in PERIODS:
            done += 1
            sys.stdout.write(f"\r  [{done}/{total}] {name} x {period_name}              ")
            sys.stdout.flush()

            try:
                r = run_single_backtest(all_data, trading_days_cache, config, period_name, start, end)
            except Exception as e:
                r = None

            if r and r.get("total_trades", 0) > 0:
                period_results[period_name] = {
                    "return": r["total_return_pct"],
                    "trades": r["total_trades"],
                    "win_rate": r["win_rate_pct"],
                    "pf": r.get("profit_factor", 0),
                    "max_dd": r.get("max_drawdown_pct", 0),
                    "sharpe": r.get("sharpe_ratio", 0),
                    "avg_gain": r.get("avg_gain_pct", 0),
                    "avg_loss": r.get("avg_loss_pct", 0),
                }
            else:
                period_results[period_name] = {"return": 0, "trades": 0, "win_rate": 0, "pf": 0, "max_dd": 0, "sharpe": 0, "avg_gain": 0, "avg_loss": 0}

        # Compute aggregate stats
        rets = [v["return"] for v in period_results.values() if v["trades"] > 0]
        total_trades = sum(v["trades"] for v in period_results.values())
        avg_return = np.mean(rets) if rets else 0
        min_return = min(rets) if rets else 0
        max_return = max(rets) if rets else 0
        max_dd = max(v["max_dd"] for v in period_results.values())
        avg_sharpe = np.mean([v["sharpe"] for v in period_results.values() if v["trades"] > 0]) if rets else 0
        avg_wr = np.mean([v["win_rate"] for v in period_results.values() if v["trades"] > 0]) if rets else 0
        avg_pf = np.mean([v["pf"] for v in period_results.values() if v["trades"] > 0 and v["pf"] < 100]) if rets else 0

        results.append({
            "name": name,
            "avg_return": avg_return,
            "min_return": min_return,
            "max_return": max_return,
            "total_trades": total_trades,
            "avg_win_rate": avg_wr,
            "avg_pf": avg_pf,
            "max_dd": max_dd,
            "avg_sharpe": avg_sharpe,
            "periods": period_results,
        })

    print("\n\n")

    # Sort by avg return
    results.sort(key=lambda x: x["avg_return"], reverse=True)

    # Print results table
    print("=" * 140)
    print(f"{'Config':<30} {'Avg Ret%':>8} {'Min Ret%':>9} {'Max Ret%':>9} {'Max DD%':>8} {'Sharpe':>7} {'WinRate':>8} {'PF':>6} {'Trades':>7}")
    print("=" * 140)
    for r in results:
        print(f"{r['name']:<30} {r['avg_return']:>+7.1f}% {r['min_return']:>+8.1f}% {r['max_return']:>+8.1f}% {r['max_dd']:>7.1f}% {r['avg_sharpe']:>7.2f} {r['avg_win_rate']:>7.1f}% {r['avg_pf']:>5.2f} {r['total_trades']:>7}")

    print("\n")

    # Detailed breakdown of top 5
    print("=" * 140)
    print("TOP 5 CONFIGS - Per Period Breakdown")
    print("=" * 140)
    for r in results[:5]:
        print(f"\n>>> {r['name']} (avg return: {r['avg_return']:+.1f}%)")
        for pname, pdata in r["periods"].items():
            if pdata["trades"] > 0:
                print(f"    {pname:<16} return={pdata['return']:>+6.1f}%  trades={pdata['trades']:>3}  WR={pdata['win_rate']:>5.1f}%  PF={pdata['pf']:>5.2f}  DD={pdata['max_dd']:>5.1f}%  sharpe={pdata['sharpe']:>5.2f}")
            else:
                print(f"    {pname:<16} (no trades)")

    # Print the winner config details
    winner = results[0]
    print(f"\n\n{'='*80}")
    print(f"BEST CONFIG: {winner['name']}")
    print(f"{'='*80}")
    print(f"Avg Return across periods: {winner['avg_return']:+.1f}%")
    print(f"Best period: {winner['max_return']:+.1f}%  |  Worst period: {winner['min_return']:+.1f}%")
    print(f"Max Drawdown: {winner['max_dd']:.1f}%  |  Avg Sharpe: {winner['avg_sharpe']:.2f}")
    print(f"Avg Win Rate: {winner['avg_win_rate']:.1f}%  |  Avg Profit Factor: {winner['avg_pf']:.2f}")


if __name__ == "__main__":
    main()
