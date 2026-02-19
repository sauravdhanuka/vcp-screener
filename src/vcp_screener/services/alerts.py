"""Telegram alert system for buy/sell signals and daily summaries."""

import logging
from datetime import datetime

from vcp_screener.config import settings

logger = logging.getLogger(__name__)


async def _send_telegram(text: str):
    """Send a message via Telegram bot."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured. Set VCP_TELEGRAM_BOT_TOKEN and VCP_TELEGRAM_CHAT_ID.")
        return False

    from telegram import Bot

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def send_alert(text: str):
    """Sync wrapper to send a Telegram alert."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send_telegram(text))
        else:
            asyncio.run(_send_telegram(text))
    except RuntimeError:
        asyncio.run(_send_telegram(text))


def format_buy_signals_alert(signals: list[dict]) -> str:
    """Format buy signals into a Telegram message."""
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    regime = signals[0].get("market_regime", "UNKNOWN") if signals else "UNKNOWN"

    lines = [
        f"<b>📊 VCP Screener — {now}</b>",
        f"Market: <b>{regime}</b>",
        "",
    ]

    buys = [s for s in signals if s["signal"] == "BUY"]
    watch_vol = [s for s in signals if s["signal"] == "WATCH_VOLUME"]
    near = [s for s in signals if s["signal"] == "NEAR_PIVOT"]

    if buys:
        lines.append(f"<b>🟢 BUY — {len(buys)} Breakout(s) Confirmed</b>")
        lines.append("")
        for s in buys[:5]:
            lines.append(
                f"<b>{s['symbol']}</b> ₹{s['close']:,.1f}\n"
                f"  Pivot: ₹{s['pivot']:,.1f} | Vol: {s['vol_ratio']:.1f}x\n"
                f"  VCP: {s['vcp_score']:.0f} | RS: {s['rs_percentile']:.0f}\n"
                f"  ➡️ Buy {s['shares']} shares @ ₹{s['entry_price']:,.1f}\n"
                f"  🛑 Stop: ₹{s['stop_price']:,.1f} | Cost: ₹{s['cost']:,.0f}"
            )
            lines.append("")
    else:
        lines.append("🟢 No confirmed breakouts today.")
        lines.append("")

    if watch_vol:
        lines.append(f"<b>🟡 Above Pivot — Need Volume ({len(watch_vol)})</b>")
        for s in watch_vol[:5]:
            lines.append(f"  {s['symbol']} ₹{s['close']:,.0f} (vol {s['vol_ratio']:.1f}x, need {settings.breakout_volume_mult}x)")
        if len(watch_vol) > 5:
            lines.append(f"  +{len(watch_vol) - 5} more")
        lines.append("")

    if near:
        lines.append(f"<b>🔵 Near Pivot — Watchlist ({len(near)})</b>")
        for s in near[:5]:
            lines.append(f"  {s['symbol']} ₹{s['close']:,.0f} → pivot ₹{s['pivot']:,.0f} ({s['distance_to_pivot_pct']:.1f}% away)")
        if len(near) > 5:
            lines.append(f"  +{len(near) - 5} more")
        lines.append("")

    forming = len([s for s in signals if s["signal"] == "FORMING"])
    lines.append(f"<i>{forming} more stocks still forming patterns</i>")

    return "\n".join(lines)


def format_sell_alerts(alerts: list[dict]) -> str:
    """Format sell alerts into a Telegram message."""
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    lines = [
        f"<b>🚨 SELL ALERTS — {now}</b>",
        "",
    ]

    for a in alerts:
        alert_types = ", ".join(a["alerts"])
        emoji = "🔴" if any(x in alert_types for x in ["STOP", "PROTECT"]) else "🟡"
        gain_emoji = "📈" if a["gain_pct"] > 0 else "📉"

        lines.append(
            f"{emoji} <b>{a['symbol']}</b> (#{a['position_id']})\n"
            f"  Signal: {alert_types}\n"
            f"  Entry: ₹{a['entry_price']:,.1f} → Now: ₹{a['current_price']:,.1f} {gain_emoji} {a['gain_pct']:+.1f}%\n"
            f"  Stop: ₹{a['effective_stop']:,.1f}"
        )
        lines.append("")

    return "\n".join(lines)


def format_portfolio_summary(holdings: list[dict]) -> str:
    """Format portfolio summary for daily report."""
    if not holdings:
        return "<b>💼 Portfolio:</b> No open positions."

    total_cost = sum(h["cost"] for h in holdings)
    total_value = sum(h["market_value"] for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

    pnl_emoji = "📈" if total_pnl >= 0 else "📉"

    lines = [
        f"<b>💼 Portfolio — {len(holdings)} positions</b>",
        f"Cost: ₹{total_cost:,.0f} | Value: ₹{total_value:,.0f}",
        f"P&L: ₹{total_pnl:+,.0f} ({total_pnl_pct:+.1f}%) {pnl_emoji}",
        "",
    ]

    for h in holdings:
        emoji = "🟢" if h["pnl"] >= 0 else "🔴"
        lines.append(f"  {emoji} {h['symbol']} {h['pnl_pct']:+.1f}% (₹{h['pnl']:+,.0f})")

    return "\n".join(lines)


def send_daily_report(signals: list[dict], alerts: list[dict], holdings: list[dict]):
    """Send the full daily report: buy signals + sell alerts + portfolio summary."""
    parts = []

    # Buy signals
    if signals:
        parts.append(format_buy_signals_alert(signals))

    # Sell alerts
    if alerts:
        parts.append(format_sell_alerts(alerts))

    # Portfolio
    parts.append(format_portfolio_summary(holdings))

    full_message = "\n\n━━━━━━━━━━━━━━━\n\n".join(parts)

    # Telegram has a 4096 char limit — split if needed
    if len(full_message) <= 4096:
        send_alert(full_message)
    else:
        for part in parts:
            send_alert(part)
