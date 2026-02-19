"""CLI entry point using Click + Rich."""

import logging
import sys
from datetime import date, datetime

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


@click.group()
def cli():
    """VCP Stock Screener for NSE - Mark Minervini Methodology"""
    pass


# ── Data commands ──────────────────────────────────────────────

@cli.group()
def data():
    """Download and manage stock data."""
    pass


@data.command("download")
def data_download():
    """Full download: NSE stock list + 2 years OHLCV data."""
    from vcp_screener.services.data_fetcher import full_download
    console.print("[bold green]Starting full data download...[/]")
    console.print("This will download ~2000+ NSE stocks. May take 30-60 minutes.")
    full_download()
    console.print("[bold green]Download complete![/]")


@data.command("update")
@click.option("--days", default=10, help="Days of recent data to fetch")
def data_update(days):
    """Incremental update: fetch recent price data."""
    from vcp_screener.services.data_fetcher import update_prices
    console.print(f"[bold]Updating last {days} days of data...[/]")
    update_prices(days_back=days)
    console.print("[bold green]Update complete![/]")


# ── Screen commands ────────────────────────────────────────────

@cli.group()
def screen():
    """Run stock screening."""
    pass


@screen.command("run")
def screen_run():
    """Run the full VCP screening pipeline."""
    from vcp_screener.services.screener import run_screening

    console.print("[bold]Running VCP screening pipeline...[/]")
    results = run_screening()

    if not results:
        console.print("[yellow]No VCP candidates found.[/]")
        return

    regime = results[0].get("market_regime", "UNKNOWN")
    regime_color = {"BULLISH": "green", "CAUTIOUS": "yellow", "BEARISH": "red"}.get(regime, "white")
    console.print(Panel(f"Market Regime: [{regime_color}]{regime}[/]", title="Market Status"))

    table = Table(title=f"Top {len(results)} VCP Candidates", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Symbol", style="cyan bold", width=12)
    table.add_column("Close", justify="right", width=10)
    table.add_column("VCP Score", justify="right", width=10)
    table.add_column("RS %ile", justify="right", width=8)
    table.add_column("Pivot", justify="right", width=10)
    table.add_column("Depth %", justify="right", width=8)
    table.add_column("Contr.", justify="right", width=6)
    table.add_column("Tight.", justify="right", width=7)
    table.add_column("Vol Dry%", justify="right", width=8)
    table.add_column("Days", justify="right", width=6)

    for r in results:
        score_color = "green" if r["vcp_score"] >= 70 else "yellow" if r["vcp_score"] >= 50 else "white"
        table.add_row(
            str(r["rank"]),
            r["symbol"],
            f"₹{r['close_price']:,.1f}",
            f"[{score_color}]{r['vcp_score']}[/]",
            f"{r['rs_percentile']:.0f}",
            f"₹{r.get('pivot_price', 0):,.1f}" if r.get("pivot_price") else "-",
            f"{r.get('base_depth_pct', 0):.1f}",
            str(r.get("num_contractions", 0)),
            f"{r.get('tightness_ratio', 0):.2f}",
            f"{r.get('volume_dry_up', 0):.0f}",
            str(r.get("base_duration_days", 0)),
        )

    console.print(table)


@screen.command("signals")
def screen_signals():
    """Show actionable buy signals: which stocks are breaking out NOW."""
    from vcp_screener.services.screener import get_buy_signals

    from vcp_screener.config import settings

    console.print("[bold]Checking buy signals...[/]")
    signals = get_buy_signals()

    if not signals:
        console.print("[yellow]No candidates found. Run `vcp screen run` first.[/]")
        return

    regime = signals[0].get("market_regime", "UNKNOWN")
    regime_color = {"BULLISH": "green", "CAUTIOUS": "yellow", "BEARISH": "red"}.get(regime, "white")
    console.print(Panel(f"Market Regime: [{regime_color}]{regime}[/]  |  Account: ₹{signals[0].get('risk_amount', 0) / (signals[0].get('risk_amount', 1) and 1) * 40:,.0f}", title="Status"))

    # BUY signals
    buys = [s for s in signals if s["signal"] == "BUY"]
    if buys:
        console.print(f"\n[bold green]🟢 BUY SIGNALS ({len(buys)} stocks breaking out)[/]")
        table = Table(show_lines=True)
        table.add_column("Symbol", style="green bold", width=12)
        table.add_column("Close", justify="right")
        table.add_column("Pivot", justify="right")
        table.add_column("Vol Ratio", justify="right")
        table.add_column("VCP", justify="right")
        table.add_column("RS", justify="right")
        table.add_column("Entry", justify="right")
        table.add_column("Stop", justify="right")
        table.add_column("Shares", justify="right")
        table.add_column("Cost", justify="right")

        for s in buys:
            table.add_row(
                s["symbol"],
                f"₹{s['close']:,.1f}",
                f"₹{s['pivot']:,.1f}",
                f"[green]{s['vol_ratio']:.1f}x[/]",
                f"{s['vcp_score']:.0f}",
                f"{s['rs_percentile']:.0f}",
                f"[bold]₹{s['entry_price']:,.1f}[/]",
                f"₹{s['stop_price']:,.1f}",
                str(s["shares"]),
                f"₹{s['cost']:,.0f}",
            )
        console.print(table)
    else:
        console.print("\n[yellow]No confirmed breakouts today.[/]")

    # WATCH_VOLUME signals
    watch = [s for s in signals if s["signal"] == "WATCH_VOLUME"]
    if watch:
        console.print(f"\n[bold yellow]🟡 ABOVE PIVOT — WAITING FOR VOLUME ({len(watch)} stocks)[/]")
        table = Table(show_lines=True)
        table.add_column("Symbol", style="yellow bold", width=12)
        table.add_column("Close", justify="right")
        table.add_column("Pivot", justify="right")
        table.add_column("Vol Ratio", justify="right")
        table.add_column("Need", justify="right")
        table.add_column("VCP", justify="right")
        table.add_column("RS", justify="right")

        for s in watch[:10]:
            table.add_row(
                s["symbol"],
                f"₹{s['close']:,.1f}",
                f"₹{s['pivot']:,.1f}",
                f"{s['vol_ratio']:.1f}x",
                f"{settings.breakout_volume_mult}x",
                f"{s['vcp_score']:.0f}",
                f"{s['rs_percentile']:.0f}",
            )
        console.print(table)

    # NEAR_PIVOT signals
    near = [s for s in signals if s["signal"] == "NEAR_PIVOT"]
    if near:
        console.print(f"\n[bold cyan]🔵 NEAR PIVOT — WATCHLIST ({len(near)} stocks within 3%)[/]")
        table = Table(show_lines=True)
        table.add_column("Symbol", style="cyan", width=12)
        table.add_column("Close", justify="right")
        table.add_column("Pivot", justify="right")
        table.add_column("Gap", justify="right")
        table.add_column("VCP", justify="right")
        table.add_column("RS", justify="right")

        for s in near[:10]:
            table.add_row(
                s["symbol"],
                f"₹{s['close']:,.1f}",
                f"₹{s['pivot']:,.1f}",
                f"{s['distance_to_pivot_pct']:.1f}%",
                f"{s['vcp_score']:.0f}",
                f"{s['rs_percentile']:.0f}",
            )
        console.print(table)

    # Summary
    forming = [s for s in signals if s["signal"] == "FORMING"]
    console.print(f"\n[dim]{len(forming)} more stocks still forming VCP patterns (not near pivot yet)[/]")

    if buys:
        console.print(Panel(
            "\n".join([
                f"[green bold]vcp portfolio buy {s['symbol']} {s['entry_price']}[/]  "
                f"→ {s['shares']} shares, stop ₹{s['stop_price']:,.1f}, cost ₹{s['cost']:,.0f}"
                for s in buys[:3]
            ]),
            title="[bold]Suggested Commands[/]",
        ))


@screen.command("detail")
@click.argument("symbol")
def screen_detail(symbol):
    """Show detailed VCP analysis for a stock."""
    from vcp_screener.services.screener import get_stock_detail

    symbol = symbol.upper()
    console.print(f"[bold]Analyzing {symbol}...[/]")
    detail = get_stock_detail(symbol)

    if not detail:
        console.print(f"[red]No data found for {symbol}[/]")
        return

    # Summary
    console.print(Panel(
        f"Close: ₹{detail['close']:,.2f}  |  RS Percentile: {detail['rs_percentile']:.0f}  |  "
        f"VCP Score: {detail['vcp_score']:.0f}",
        title=f"[bold]{symbol}[/]",
    ))

    # Trend Template
    trend = detail["trend_template"]
    table = Table(title="Trend Template", show_lines=True)
    table.add_column("Condition", width=45)
    table.add_column("Pass?", justify="center", width=8)
    for name, passes in trend.get("conditions", {}).items():
        icon = "[green]✓[/]" if passes else "[red]✗[/]"
        table.add_row(name.replace("_", " ").title(), icon)
    console.print(table)

    # VCP Details
    vcp = detail["vcp"]
    if vcp.get("found"):
        console.print(f"\n[bold]VCP Pattern:[/] {vcp['num_contractions']} contractions, "
                      f"tightness={vcp['tightness_ratio']:.2f}, "
                      f"volume dry-up={vcp['volume_dry_up_pct']:.0f}%")
        console.print(f"Pivot Price: [bold cyan]₹{vcp['pivot_price']:,.2f}[/]")
        console.print(f"Base Depth: {vcp['base_depth_pct']:.1f}%, Duration: {vcp['base_duration_days']} days")

        ctable = Table(title="Contractions")
        ctable.add_column("#")
        ctable.add_column("High")
        ctable.add_column("Low")
        ctable.add_column("Range %")
        ctable.add_column("Avg Volume")
        for i, c in enumerate(vcp["contractions"], 1):
            ctable.add_row(
                str(i),
                f"₹{c['high_val']:,.1f}",
                f"₹{c['low_val']:,.1f}",
                f"{c['range_pct']:.1f}%",
                f"{c['avg_volume']:,.0f}",
            )
        console.print(ctable)
    else:
        console.print(f"\n[yellow]No VCP pattern detected: {vcp.get('reason', 'unknown')}[/]")


# ── Portfolio commands ─────────────────────────────────────────

@cli.group()
def portfolio():
    """Manage your portfolio."""
    pass


@portfolio.command("buy")
@click.argument("symbol")
@click.argument("entry_price", type=float)
@click.option("--stop", type=float, help="Stop-loss price (default: 10% below entry)")
@click.option("--shares", type=int, help="Shares to buy (auto-calculated if omitted)")
def portfolio_buy(symbol, entry_price, stop, shares):
    """Record a buy position."""
    from vcp_screener.services.portfolio_manager import buy_stock
    from vcp_screener.db import init_db
    init_db()
    pos = buy_stock(symbol.upper(), entry_price, stop_loss_price=stop, shares=shares)
    if pos:
        cost = pos.entry_price * pos.shares
        console.print(f"[green]Bought {pos.shares} shares of {pos.symbol} @ ₹{pos.entry_price:,.2f}[/]")
        console.print(f"Cost: ₹{cost:,.0f}  |  Stop: ₹{pos.stop_loss:,.2f}")
    else:
        console.print("[red]Buy failed. Check max positions or pricing.[/]")


@portfolio.command("sell")
@click.argument("position_id", type=int)
@click.argument("exit_price", type=float)
@click.option("--reason", default="manual", help="Exit reason")
def portfolio_sell(position_id, exit_price, reason):
    """Record a sell for a position."""
    from vcp_screener.services.portfolio_manager import sell_stock
    pos = sell_stock(position_id, exit_price, reason=reason)
    if pos:
        console.print(f"[{'green' if pos.pnl > 0 else 'red'}]"
                      f"Sold {pos.symbol}: P&L ₹{pos.pnl:+,.0f} ({pos.pnl_pct:+.1f}%)[/]")


@portfolio.command("holdings")
def portfolio_holdings():
    """Show current holdings with P&L."""
    from vcp_screener.services.portfolio_manager import get_holdings
    from vcp_screener.db import init_db
    init_db()
    holdings = get_holdings()

    if not holdings:
        console.print("[yellow]No open positions.[/]")
        return

    table = Table(title="Current Holdings", show_lines=True)
    table.add_column("ID", width=4)
    table.add_column("Symbol", style="cyan bold", width=12)
    table.add_column("Entry", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Stop", justify="right")

    total_cost = total_value = 0
    for h in holdings:
        pnl_color = "green" if h["pnl"] >= 0 else "red"
        effective_stop = max(h["stop_loss"], h["trailing_stop"] or 0)
        table.add_row(
            str(h["id"]), h["symbol"],
            f"₹{h['entry_price']:,.1f}", f"₹{h['current_price']:,.1f}",
            str(h["shares"]),
            f"₹{h['cost']:,.0f}", f"₹{h['market_value']:,.0f}",
            f"[{pnl_color}]₹{h['pnl']:+,.0f}[/]",
            f"[{pnl_color}]{h['pnl_pct']:+.1f}%[/]",
            f"₹{effective_stop:,.1f}",
        )
        total_cost += h["cost"]
        total_value += h["market_value"]

    console.print(table)
    total_pnl = total_value - total_cost
    pnl_color = "green" if total_pnl >= 0 else "red"
    console.print(f"Total: Cost ₹{total_cost:,.0f} | Value ₹{total_value:,.0f} | "
                  f"P&L [{pnl_color}]₹{total_pnl:+,.0f}[/]")


@portfolio.command("alerts")
def portfolio_alerts():
    """Check sell alerts for open positions."""
    from vcp_screener.services.portfolio_manager import check_sell_alerts, update_trailing_stops
    from vcp_screener.db import init_db
    init_db()

    update_trailing_stops()
    alerts = check_sell_alerts()

    if not alerts:
        console.print("[green]No sell alerts. All positions OK.[/]")
        return

    for a in alerts:
        alert_text = ", ".join(a["alerts"])
        color = "red" if any(x in alert_text for x in ["STOP", "PROTECT"]) else "yellow"
        console.print(Panel(
            f"[{color}]{alert_text}[/]\n"
            f"Entry: ₹{a['entry_price']:,.1f} | Current: ₹{a['current_price']:,.1f} | "
            f"Gain: {a['gain_pct']:+.1f}%\n"
            f"Stop: ₹{a['effective_stop']:,.1f}",
            title=f"[bold]{a['symbol']}[/] (Position #{a['position_id']})",
        ))


@portfolio.command("history")
def portfolio_history():
    """Show closed trade history."""
    from vcp_screener.services.portfolio_manager import get_closed_trades
    from vcp_screener.db import init_db
    init_db()
    trades = get_closed_trades()

    if not trades:
        console.print("[yellow]No closed trades.[/]")
        return

    table = Table(title="Closed Trades", show_lines=True)
    table.add_column("Symbol", style="cyan")
    table.add_column("Entry Date")
    table.add_column("Exit Date")
    table.add_column("Entry", justify="right")
    table.add_column("Exit", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Reason")

    for t in trades:
        pnl_color = "green" if (t["pnl"] or 0) >= 0 else "red"
        table.add_row(
            t["symbol"],
            str(t["entry_date"]),
            str(t.get("exit_date", "")),
            f"₹{t['entry_price']:,.1f}",
            f"₹{t.get('exit_price', 0):,.1f}",
            f"[{pnl_color}]₹{(t.get('pnl') or 0):+,.0f}[/]",
            f"[{pnl_color}]{(t.get('pnl_pct') or 0):+.1f}%[/]",
            t.get("exit_reason", ""),
        )
    console.print(table)


# ── Backtest commands ──────────────────────────────────────────

@cli.group()
def backtest():
    """Run backtests."""
    pass


@backtest.command("run")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--capital", type=float, default=500000, help="Initial capital")
@click.option("--positions", type=int, default=6, help="Max concurrent positions")
def backtest_run(start, end, capital, positions):
    """Run a historical backtest."""
    from vcp_screener.services.backtester import run_backtest

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    console.print(f"[bold]Running backtest: {start_date} to {end_date}[/]")
    console.print(f"Capital: ₹{capital:,.0f} | Max positions: {positions}")

    results = run_backtest(start_date, end_date, initial_capital=capital, max_positions=positions)

    if "error" in results:
        console.print(f"[red]Error: {results['error']}[/]")
        return

    if results.get("total_trades", 0) == 0:
        console.print(f"[yellow]No trades executed. Final capital: ₹{results.get('final_capital', capital):,.0f}[/]")
        console.print("This may happen if there isn't enough historical data for the period.")
        return

    # KPI cards
    console.print(Panel(
        f"Return: [{'green' if results['total_return_pct'] > 0 else 'red'}]"
        f"{results['total_return_pct']:+.1f}%[/]  |  "
        f"CAGR: {results.get('cagr_pct', 0):.1f}%  |  "
        f"Max Drawdown: [red]{results.get('max_drawdown_pct', 0):.1f}%[/]  |  "
        f"Sharpe: {results.get('sharpe_ratio', 0):.2f}",
        title="[bold]Backtest Results[/]",
    ))

    table = Table(title="Performance Metrics")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Initial Capital", f"₹{results['initial_capital']:,.0f}")
    table.add_row("Final Capital", f"₹{results['final_capital']:,.0f}")
    table.add_row("Total Trades", str(results["total_trades"]))
    table.add_row("Win Rate", f"{results['win_rate_pct']:.1f}%")
    table.add_row("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
    table.add_row("Avg Gain", f"{results.get('avg_gain_pct', 0):+.1f}%")
    table.add_row("Avg Loss", f"{results.get('avg_loss_pct', 0):+.1f}%")
    table.add_row("Avg Hold (days)", f"{results.get('avg_hold_days', 0):.0f}")
    console.print(table)

    # Top 10 trades
    trades = results.get("trades", [])
    if trades:
        trades_sorted = sorted(trades, key=lambda t: t["pnl"], reverse=True)
        ttable = Table(title="Top 10 Trades by P&L")
        ttable.add_column("Symbol", style="cyan")
        ttable.add_column("Entry")
        ttable.add_column("Exit")
        ttable.add_column("P&L", justify="right")
        ttable.add_column("P&L %", justify="right")
        ttable.add_column("Reason")
        for t in trades_sorted[:10]:
            c = "green" if t["pnl"] > 0 else "red"
            ttable.add_row(
                t["symbol"],
                str(t["entry_date"].date() if hasattr(t["entry_date"], "date") else t["entry_date"]),
                str(t["exit_date"].date() if hasattr(t["exit_date"], "date") else t["exit_date"]),
                f"[{c}]₹{t['pnl']:+,.0f}[/]",
                f"[{c}]{t['pnl_pct']:+.1f}%[/]",
                t["exit_reason"],
            )
        console.print(ttable)


# ── Dashboard command ──────────────────────────────────────────

@cli.command("dashboard")
def launch_dashboard():
    """Launch the Streamlit web dashboard."""
    import subprocess
    app_path = str(__import__("vcp_screener").__file__).replace("__init__.py", "") + "dashboard/app.py"
    console.print("[bold green]Launching Streamlit dashboard...[/]")
    subprocess.run(["streamlit", "run", app_path])


# ── Alert commands ─────────────────────────────────────────────

@cli.group()
def alert():
    """Telegram alert setup and testing."""
    pass


@alert.command("setup")
def alert_setup():
    """Step-by-step guide to set up Telegram alerts."""
    console.print(Panel(
        "[bold]How to set up Telegram alerts (2 minutes):[/]\n\n"
        "[cyan]Step 1:[/] Open Telegram, search for @BotFather\n"
        "[cyan]Step 2:[/] Send /newbot, give it a name like 'VCP Screener'\n"
        "[cyan]Step 3:[/] BotFather gives you a token like 7123456789:AAH...\n"
        "[cyan]Step 4:[/] Search for @userinfobot in Telegram, it tells you your chat ID\n"
        "[cyan]Step 5:[/] Set the environment variables:\n\n"
        "   [green]export VCP_TELEGRAM_BOT_TOKEN='your-token-here'[/]\n"
        "   [green]export VCP_TELEGRAM_CHAT_ID='your-chat-id-here'[/]\n\n"
        "[cyan]Step 6:[/] Test it:\n\n"
        "   [green]vcp alert test[/]\n\n"
        "[dim]Tip: Add the exports to your ~/.zshrc or ~/.bashrc to persist them.[/]",
        title="[bold]Telegram Alert Setup[/]",
    ))


@alert.command("test")
def alert_test():
    """Send a test message to verify Telegram is working."""
    from vcp_screener.config import settings
    from vcp_screener.services.alerts import send_alert

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        console.print("[red]Telegram not configured.[/]")
        console.print("Run [bold]vcp alert setup[/] for instructions.")
        return

    console.print("Sending test message to Telegram...")
    send_alert("<b>✅ VCP Screener — Test Alert</b>\n\nTelegram alerts are working!")
    console.print("[green]Message sent! Check your Telegram.[/]")


@alert.command("now")
def alert_now():
    """Run screening + send full alert report to Telegram right now."""
    from vcp_screener.config import settings
    from vcp_screener.services.screener import get_buy_signals
    from vcp_screener.services.portfolio_manager import (
        update_trailing_stops, check_sell_alerts, get_holdings,
    )
    from vcp_screener.services.alerts import send_daily_report
    from vcp_screener.db import init_db

    init_db()

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        console.print("[red]Telegram not configured. Run `vcp alert setup`[/]")
        return

    console.print("[bold]Generating and sending alert...[/]")

    signals = get_buy_signals()
    update_trailing_stops()
    alerts = check_sell_alerts()
    holdings = get_holdings()

    buy_count = len([s for s in signals if s["signal"] == "BUY"])
    near_count = len([s for s in signals if s["signal"] == "NEAR_PIVOT"])

    send_daily_report(signals, alerts, holdings)

    console.print(f"[green]Alert sent![/] ({buy_count} buy signals, {len(alerts)} sell alerts, {near_count} near pivot)")


@alert.command("schedule")
def alert_schedule():
    """Start the daily scheduler (runs at 4:15 PM IST with Telegram alerts)."""
    from vcp_screener.scheduler.daily_job import start_scheduler
    console.print("[bold green]Starting daily scheduler...[/]")
    console.print(f"Will run at {settings.screen_time} IST every day.")
    console.print("Press Ctrl+C to stop.\n")
    start_scheduler()


if __name__ == "__main__":
    cli()
