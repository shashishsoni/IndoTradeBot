"""
Trading Signal Analyzer — CLI Entry Point.
Supports Indian equities (NSE/BSE) and global crypto markets.

AUTOMATED MODE:
    python main.py auto --interval 15  # Scan every 15 minutes
    python main.py auto --interval 5   # Scan every 5 minutes
    python main.py auto --telegram     # Enable Telegram alerts

RENDER FREE WEB SERVICE — same behavior as `auto`, plus Flask homepage on $PORT:
    python main.py serve -i 5 -t -m equity crypto
    # GET / → full HTML dashboard (not plain text).
"""

import datetime
import os
import signal
import sys
import threading
import time
from typing import List, Optional

from zoneinfo import ZoneInfo


def _configure_server_logging() -> None:
    """Line-buffer stdout/stderr on PaaS so background-thread prints appear in dashboard logs."""
    if os.environ.get("RENDER") or os.environ.get("PORT"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
            sys.stderr.reconfigure(line_buffering=True)
        except (AttributeError, OSError):
            pass


def _load_dotenv() -> None:
    """Load .env from project root so TELEGRAM_* and other vars are available."""
    try:
        from dotenv import load_dotenv

        root = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(root, ".env")
        load_dotenv(env_path)
    except ImportError:
        pass


_load_dotenv()
_configure_server_logging()

from config import MarketType, SignalType
from data_fetcher import (
    fetch_btc_dominance,
    fetch_data,
    fetch_fear_greed_index,
    fetch_gift_nifty_gap,
)
from formatter import (
    format_context_warnings,
    format_halt_message,
    format_review_mode_message,
    format_signal_report,
    format_skip_message,
)
from market_context import (
    get_crypto_context,
    get_india_context,
    is_fno_expiry_day,
)
from notifier import TelegramNotifier, send_scan_alert, send_telegram_alert
from risk_manager import (
    RiskState,
    check_can_trade,
    get_risk_summary,
    record_trade_result,
)
from scan_report import format_detailed_scan_report
from signal_engine import generate_signal
from zebpay_client import format_trade_price_line

IST = ZoneInfo("Asia/Kolkata")

# Global flag for daemon mode
_daemon_running = False

HELP_TEXT = """
╔══════════════════════════════════════════════════════════╗
║          TRADING SIGNAL ANALYZER v1.0                   ║
║   Indian Equities (NSE/BSE) & Crypto Markets            ║
╚══════════════════════════════════════════════════════════╝

COMMANDS:
  analyze <symbol> [equity|crypto] [--force]  — Generate signal (see --force below)
  scan <equity|crypto> [--telegram]   — Scan watchlist; add -t to send full report to Telegram
  auto --interval <min>             — Auto-scan mode (daemon)
  risk                              — Show risk dashboard
  capital <amount>                  — Set trading capital
  result <asset> <pnl>             — Record a trade result
  reset-review                      — Exit review mode (after analysis)
  reset-halt                        — Resume trading (after human review)
  watchlist                         — Show default watchlists
  help                              — Show this message
  quit                              — Exit

  --force                           — Bypass weekend / off-hours block (research only)

EXAMPLES:
  analyze RELIANCE equity           — Analyze Reliance (blocked Sat/Sun & off-hours)
  analyze RELIANCE equity --force   — Same, but allowed on weekend (chart research)
  analyze TCS equity                — Analyze TCS (NSE)
  analyze BTCUSDT crypto            — Analyze Bitcoin/USDT
  analyze ETHUSDT crypto            — Analyze Ethereum/USDT
  scan equity                       — Scan Indian equity watchlist
  scan crypto                       — Scan crypto watchlist
  capital 500000                    — Set capital to ₹5,00,000
  result RELIANCE 2500              — Record ₹2,500 profit
  result BTCUSDT -150               — Record $150 loss

AUTO MODE (Daemon):
  python main.py auto --interval 15      — Scan every 15 minutes
  python main.py auto --interval 5        — Scan every 5 minutes
  python main.py auto --telegram         — Scan with Telegram alerts
  python main.py auto -i 15 -t -m equity  — Equity only, 15 min, Telegram

ENVIRONMENT VARIABLES:
  TELEGRAM_BOT_TOKEN=<token>   — Your Telegram bot token
  TELEGRAM_CHAT_ID=<id>         — Your Telegram chat ID
"""

EQUITY_WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
    "BHARTIARTL", "BAJFINANCE", "HINDUNILVR", "ITC", "KOTAKBANK",
    "LT", "M&M", "SUNPHARMA", "TITAN", "ADANIPORTS",
    "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "CIPLA", "DRREDDY",
]


def get_crypto_watchlist() -> List[str]:
    """
    Crypto symbols for ZebPay (bare base: BTC, ETH).

    - Set CRYPTO_WATCHLIST=BTC,ETH,SOL (comma-separated) to override.
    - Else CRYPTO_WATCHLIST_MODE controls the list:
        - xpress (default): Xpress-style INR list + QuickTrade MARKET pairs (see zebpay_client).
        - quicktrade: Open INR pairs with MARKET orders only (~7 symbols, faster scan).
        - all: every Open INR base from exchangeInfo (capped by CRYPTO_WATCHLIST_MAX).
    - ZEBPAY_XPRESS_SYMBOLS: optional comma list to replace the built-in Xpress list.
    - If the API fails, uses a fixed fallback aligned with QuickTrade MARKET pairs.
    """
    from zebpay_client import resolve_crypto_watchlist

    syms, _ = resolve_crypto_watchlist()
    return syms


def analyze_asset(
    symbol: str,
    market: MarketType,
    risk_state: RiskState,
    force: bool = False,
) -> str:
    """Full analysis pipeline for a single asset."""
    now = datetime.datetime.now(IST)

    can_trade, reason = check_can_trade(risk_state)
    if not can_trade and not force:
        if risk_state.halted:
            return format_halt_message(risk_state)
        if risk_state.review_mode:
            return format_review_mode_message(risk_state)
        return f"\n⚠ {reason}\n"

    # Market context
    if market == MarketType.INDIA_EQUITY:
        gap = fetch_gift_nifty_gap() or 0.0
        fno_expiry = is_fno_expiry_day(now)
        is_friday_pm = now.weekday() == 4
        context = get_india_context(
            now=now,
            gift_nifty_gap=gap,
            is_fno_expiry=fno_expiry,
            is_friday_afternoon=is_friday_pm,
        )
    else:
        btc_dom = fetch_btc_dominance()
        fg = fetch_fear_greed_index()
        context = get_crypto_context(
            now=now,
            btc_dominance=btc_dom,
            fear_greed=fg,
        )

    if context.should_skip and not force:
        return format_skip_message(context)

    if force and context.should_skip:
        context.warnings.append(
            "--force: market-hours/weekend filter bypassed — research only, "
            "not live intraday timing."
        )

    # Fetch data
    print(f"  Fetching data for {symbol}...")
    interval = "1d"
    period = "3mo"
    df = fetch_data(symbol, market, period=period, interval=interval)

    if df is None or df.empty:
        return f"\n❌ Could not fetch data for {symbol}. Check the symbol and try again.\n"

    if len(df) < 50:
        return (
            f"\n❌ Insufficient data for {symbol} ({len(df)} bars). "
            f"Need at least 50 bars for reliable analysis.\n"
        )

    # Generate signal
    signal = generate_signal(df, symbol, market)
    if signal is None:
        return f"\n❌ Could not generate indicators for {symbol}. Insufficient data.\n"

    # Track active signals
    if signal.signal != SignalType.HOLD:
        risk_state.active_signals += 1
        risk_state.save()

    output = format_signal_report(signal, context, risk_state, now)

    if context.warnings:
        output += format_context_warnings(context)

    return output


def scan_watchlist(
    market: MarketType,
    risk_state: RiskState,
    send_telegram: bool = False,
) -> str:
    """Scan a full watchlist: rankings, entry table, strong-signal guide, full report for top name."""
    crypto_diag = None
    if market == MarketType.INDIA_EQUITY:
        watchlist = EQUITY_WATCHLIST
    else:
        from zebpay_client import resolve_crypto_watchlist

        watchlist, crypto_diag = resolve_crypto_watchlist()
    market_name = "Indian Equity" if market == MarketType.INDIA_EQUITY else "Crypto"

    header = (
        f"\n{'═' * 50}\n"
        f"📋 WATCHLIST SCAN — {market_name} ({len(watchlist)} assets)\n"
        f"{'═' * 50}\n"
    )
    if crypto_diag:
        from zebpay_client import format_crypto_watchlist_summary

        header += f"  ⚙️ {format_crypto_watchlist_summary(crypto_diag)}\n"

    results = []
    progress_lines = []
    for symbol in watchlist:
        try:
            print(f"  · Scanning {symbol}...", end="\r", flush=True)
            df = fetch_data(symbol, market)
            if df is None or len(df) < 50:
                progress_lines.append(f"  ⚠️ {symbol:<12} | skipped (no data)")
                continue
            sig = generate_signal(df, symbol, market)
            if sig is None:
                progress_lines.append(f"  ⚠️ {symbol:<12} | skipped (indicators)")
                continue
            results.append(sig)
            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[sig.signal.value]
            c = sig.currency_symbol
            progress_lines.append(
                f"  {emoji} {symbol:<12} | {sig.signal.value:<4} | "
                f"Conf {sig.confidence}/10 | {format_trade_price_line(c, sig.entry_mid)}"
            )
        except Exception as e:
            progress_lines.append(f"  ❌ {symbol:<12} | Error: {e}")

    print(" " * 40, end="\r")

    if not results:
        return header + "\n".join(progress_lines) + "\n\n⚠️ No symbols produced signals.\n"

    body = format_detailed_scan_report(
        results,
        market_name,
        risk_state=risk_state,
        include_guide=True,
        include_full_top_report=True,
        crypto_watchlist_diag=crypto_diag,
    )
    out = header + "\n".join(progress_lines) + "\n" + body

    if send_telegram:
        notifier = TelegramNotifier()
        if notifier.is_configured():
            notifier.send_detailed_scan_report(
                results,
                market_name,
                risk_state=risk_state,
                include_guide=True,
                include_full_top_report=True,
                crypto_watchlist_diag=crypto_diag,
            )
            out += "\n✅ Same detailed report sent to Telegram.\n"
        else:
            out += "\n⚠️ Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env\n"

    return out


def interactive_loop():
    """Main interactive CLI loop."""
    state = RiskState.load()

    print(HELP_TEXT)
    print(get_risk_summary(state))

    while True:
        try:
            raw = input("\n📊 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd == "risk":
            print(get_risk_summary(state))

        elif cmd == "watchlist":
            print("\n📋 EQUITY WATCHLIST:", ", ".join(EQUITY_WATCHLIST))
            from zebpay_client import format_crypto_watchlist_summary, resolve_crypto_watchlist

            c_syms, c_diag = resolve_crypto_watchlist()
            print("📋 CRYPTO WATCHLIST:", ", ".join(c_syms))
            print("   ⚙️", format_crypto_watchlist_summary(c_diag))
            miss = c_diag.get("xpress_not_on_exchange_api") or []
            if miss:
                print(
                    f"   ⏭️ {len(miss)} configured Xpress bases not Open INR on API (not in scan): "
                    f"{', '.join(miss[:20])}{' …' if len(miss) > 20 else ''}"
                )

        elif cmd == "capital":
            if len(parts) < 2:
                print("Usage: capital <amount>")
                continue
            try:
                amount = float(parts[1].replace(",", ""))
                state.capital = amount
                state.initial_capital = max(state.initial_capital, amount)
                state.save()
                print(f"✅ Capital set to {amount:,.2f}")
            except ValueError:
                print("Invalid amount.")

        elif cmd == "result":
            if len(parts) < 3:
                print("Usage: result <asset> <pnl>")
                continue
            asset = parts[1].upper()
            try:
                pnl = float(parts[2].replace(",", ""))
                msg = record_trade_result(state, pnl, asset)
                print(msg)
            except ValueError:
                print("Invalid PnL amount.")

        elif cmd == "reset-review":
            state.review_mode = False
            state.consecutive_losses = 0
            state.save()
            print("✅ Review mode cleared. Signal generation resumed.")

        elif cmd == "reset-halt":
            state.halted = False
            state.initial_capital = state.capital
            state.save()
            print("✅ Trading halt lifted. Drawdown baseline reset to current capital.")

        elif cmd == "analyze":
            if len(parts) < 2:
                print("Usage: analyze <symbol> [equity|crypto]")
                continue

            symbol = parts[1].upper()
            market_str = parts[2].lower() if len(parts) > 2 else "equity"

            if market_str in ("equity", "stock", "nse", "bse"):
                market = MarketType.INDIA_EQUITY
            elif market_str in ("crypto", "btc", "coin"):
                market = MarketType.CRYPTO
            else:
                market = MarketType.INDIA_EQUITY

            force = "--force" in parts
            print(analyze_asset(symbol, market, state, force=force))

        elif cmd == "scan":
            if len(parts) < 2:
                print("Usage: scan <equity|crypto> [--telegram]")
                continue

            send_tg = "--telegram" in parts or "-t" in parts
            market_tokens = [p for p in parts[1:] if p.lower() not in ("--telegram", "-t")]
            if not market_tokens:
                print("Usage: scan <equity|crypto> [--telegram]")
                continue

            market_str = market_tokens[0].lower()
            if market_str in ("equity", "stock", "nse"):
                market = MarketType.INDIA_EQUITY
            elif market_str in ("crypto", "btc", "coin"):
                market = MarketType.CRYPTO
            else:
                print("Unknown market. Use 'equity' or 'crypto'.")
                continue

            print(scan_watchlist(market, state, send_telegram=send_tg))

        elif cmd == "auto":
            # Auto/daemon mode
            interval = 15
            markets = ["equity", "crypto"]
            telegram = False
            
            # Parse simple args like "auto 15" or "auto equity crypto"
            for i, part in enumerate(parts[1:], 1):
                if part.isdigit():
                    interval = int(part)
                elif part in ("equity", "crypto"):
                    markets = [part]
                elif part in ("--telegram", "-t"):
                    telegram = True
            
            print(f"\n🚀 Starting auto mode: {interval} min interval, markets: {markets}")
            print("Press Ctrl+C to stop\n")
            
            # Get Telegram settings from environment
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            
            try:
                run_daemon_mode(
                    interval_minutes=interval,
                    markets=markets,
                    telegram_enabled=telegram,
                    token=token if token else None,
                    chat_id=chat_id if chat_id else None,
                )
            except KeyboardInterrupt:
                print("\n✅ Auto mode stopped")

        elif cmd in ("daemon", "run"):
            # Alias for auto mode
            print("\n🚀 Starting daemon mode...")
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            
            try:
                run_daemon_mode(
                    interval_minutes=15,
                    markets=["equity", "crypto"],
                    telegram_enabled=bool(token and chat_id),
                    token=token if token else None,
                    chat_id=chat_id if chat_id else None,
                )
            except KeyboardInterrupt:
                print("\n✅ Daemon stopped")

        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")


def _scan_market(
    market: MarketType,
    state: RiskState,
    notifier: Optional[TelegramNotifier] = None,
    send_notifications: bool = False,
) -> List:
    """
    Scan a market and return results.
    
    Args:
        market: MarketType to scan
        state: RiskState instance
        notifier: TelegramNotifier instance (optional)
        send_notifications: Whether to send Telegram alerts
        
    Returns:
        List of TradeSignal objects
    """
    crypto_diag = None
    if market == MarketType.INDIA_EQUITY:
        watchlist = EQUITY_WATCHLIST
    else:
        from zebpay_client import format_crypto_watchlist_summary, resolve_crypto_watchlist

        watchlist, crypto_diag = resolve_crypto_watchlist()
    market_name = "India Equity" if market == MarketType.INDIA_EQUITY else "Crypto"
    
    print(f"\n{'='*50}")
    print(f"🔄 SCANNING {market_name} MARKET...")
    print(f"{'='*50}")
    
    results = []
    now = datetime.datetime.now(IST)
    
    print(f"  📋 Symbols to scan: {watchlist}")
    if crypto_diag:
        print(f"  ⚙️ {format_crypto_watchlist_summary(crypto_diag)}")
    
    for symbol in watchlist:
        try:
            df = fetch_data(symbol, market)
            if df is None:
                print(f"  ⚠ {symbol}: No data returned")
                continue
            if len(df) < 50:
                print(f"  ⚠ {symbol}: Insufficient data ({len(df)} bars, need 50)")
                continue
            sig = generate_signal(df, symbol, market)
            if sig is None:
                print(f"  ⚠ {symbol}: Signal generation returned None")
                continue
            results.append(sig)

            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[sig.signal.value]
            print(f"  {emoji} {symbol:<12} | {sig.signal.value:<4} | Conf: {sig.confidence}/10")

            # Full detailed report is sent once after the scan (see below).

        except Exception as e:
            print(f"  ❌ {symbol:<12} | Error: {e}")

    buy_signals = [r for r in results if r.signal == SignalType.BUY]
    sell_signals = [r for r in results if r.signal == SignalType.SELL]
    hold_signals = [r for r in results if r.signal == SignalType.HOLD]

    print(f"\n📊 SCAN COMPLETE:")
    print(f"  🟢 BUY: {len(buy_signals)}")
    print(f"  🔴 SELL: {len(sell_signals)}")
    print(f"  🟡 HOLD: {len(hold_signals)}")

    if results:
        # Ranked opportunities + entry table (skip long guide each interval in daemon)
        print(
            format_detailed_scan_report(
                results,
                market_name,
                risk_state=state,
                include_guide=not send_notifications,
                include_full_top_report=True,
                crypto_watchlist_diag=crypto_diag,
            )
        )

    # Send full detailed scan (rankings, entry table, guide, top pick report) to Telegram
    if send_notifications and notifier and notifier.is_configured() and results:
        notifier.send_detailed_scan_report(
            results,
            market_name,
            risk_state=state,
            include_guide=True,
            include_full_top_report=True,
            crypto_watchlist_diag=crypto_diag,
        )

    return results


def is_market_open(market: MarketType) -> bool:
    """Check if market is currently open based on IST time."""
    now = datetime.datetime.now(IST)
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    if market == MarketType.INDIA_EQUITY:
        # Indian Market: 9:15 AM - 3:30 PM IST, Mon-Fri
        if weekday >= 5:  # Saturday or Sunday
            return False
        hour, minute = now.hour, now.minute
        market_time = hour * 60 + minute  # minutes from midnight
        open_time = 9 * 60 + 15   # 9:15 AM
        close_time = 15 * 60 + 30  # 3:30 PM
        return open_time <= market_time < close_time
    
    elif market == MarketType.CRYPTO:
        # Crypto: 24/7 but avoid low liquidity 2-5 AM IST
        hour = now.hour
        return True  # Always open
    
    return False


def get_market_schedule_message(market: MarketType) -> str:
    """Get schedule info for market."""
    now = datetime.datetime.now(IST)
    weekday = now.weekday()
    
    if market == MarketType.INDIA_EQUITY:
        if weekday >= 5:
            return "📅 Weekend - Market Closed"
        hour, minute = now.hour, now.minute
        market_time = hour * 60 + minute
        open_time = 9 * 60 + 15
        close_time = 15 * 60 + 30
        
        if market_time < open_time:
            mins_until = open_time - market_time
            return f"⏰ Market opens in {mins_until//60}h {mins_until%60}m"
        elif market_time >= close_time:
            return f"🔴 Market Closed (reopens Monday)"
        else:
            mins_left = close_time - market_time
            return f"🟢 Market Open - {mins_left//60}h {mins_left%60}m left"
    
    elif market == MarketType.CRYPTO:
        hour = now.hour
        if 2 <= hour < 5:
            return "🌙 Low liquidity period (2-5 AM IST)"
        return "🟢 Crypto Market Open 24/7"
    
    return ""


def run_daemon_mode(
    interval_minutes: int = 15,
    markets: List[str] = None,
    telegram_enabled: bool = False,
    token: str = None,
    chat_id: str = None,
    smart_schedule: bool = True,
    register_signals: bool = True,
):
    """
    Run the bot in daemon mode - continuously scanning at intervals with smart scheduling.
    
    Args:
        interval_minutes: Minutes between scans
        markets: List of markets to scan ["equity", "crypto"]
        telegram_enabled: Enable Telegram notifications
        token: Telegram bot token
        chat_id: Telegram chat ID
        smart_schedule: Enable smart scheduling (market hours only)
        register_signals: Set False when daemon runs inside a worker thread (e.g. web serve mode)
    """
    global _daemon_running

    # Setup signal handlers for graceful shutdown (main thread only)
    if register_signals:

        def signal_handler(sig, frame):
            global _daemon_running
            print("\n🛑 Received stop signal. Finishing current scan...")
            _daemon_running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    state = RiskState.load()
    
    # Setup Telegram notifier
    notifier = None
    if telegram_enabled:
        notifier = TelegramNotifier(token=token, chat_id=chat_id)
        if notifier.is_configured():
            print("✅ Telegram notifications enabled", flush=True)
            notifier.test_connection()
            # Proves delivery to your chat (getMe alone does not message you)
            notifier.send_plain_text(
                "IndoTradeBot: daemon started on server.\n"
                f"Scan interval: {interval_minutes} min.\n"
                "You will get a detailed report after each scan when symbols return data."
            )
        else:
            print(
                "⚠️ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                "(Render: Environment → add both as secrets)",
                flush=True,
            )
    
    # Default markets
    if markets is None:
        markets = ["equity", "crypto"]
    
    market_types = []
    for m in markets:
        if m.lower() in ("equity", "stock", "nse"):
            market_types.append(MarketType.INDIA_EQUITY)
        elif m.lower() in ("crypto", "btc", "coin"):
            market_types.append(MarketType.CRYPTO)
    
    if not market_types:
        market_types = [MarketType.INDIA_EQUITY, MarketType.CRYPTO]
    
    print(f"\n{'='*60}", flush=True)
    print(f"🤖 TRADING SIGNAL DAEMON STARTED", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"📊 Scan Interval: {interval_minutes} minutes", flush=True)
    print(f"📈 Markets: {[m.value for m in market_types]}", flush=True)
    print(f"🔔 Telegram: {'Enabled' if telegram_enabled else 'Disabled'}", flush=True)
    print(f"🕐 Started: {datetime.datetime.now(IST).strftime('%Y-%m-%d %I:%M %p IST')}", flush=True)
    print(f"⏰ Smart Schedule: {'Enabled' if smart_schedule else 'Disabled'}", flush=True)
    print(f"\nPress Ctrl+C to stop", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    _daemon_running = True
    scan_count = 0
    last_status_time = 0
    
    while _daemon_running:
        now = datetime.datetime.now(IST)
        current_minute = now.hour * 60 + now.minute
        
        # Determine which markets to scan now
        markets_to_scan = []
        for market in market_types:
            if smart_schedule:
                if market == MarketType.INDIA_EQUITY:
                    if is_market_open(market):
                        markets_to_scan.append(market)
                else:  # Crypto - always scan
                    markets_to_scan.append(market)
            else:
                markets_to_scan.append(market)
        
        # Show status every minute
        if current_minute != last_status_time:
            last_status_time = current_minute
            status_parts = [get_market_schedule_message(m) for m in market_types]
            print(f"\n🕐 {now.strftime('%I:%M %p IST')} | {' | '.join(status_parts)}")
        
        # Run scans for open markets
        if markets_to_scan:
            scan_count += 1
            print(f"\n🔄 Scan #{scan_count} - Scanning: {[m.value for m in markets_to_scan]}")
            
            for market in markets_to_scan:
                try:
                    _scan_market(market, state, notifier, telegram_enabled)
                except Exception as e:
                    print(f"❌ Error scanning {market.value}: {e}")
        else:
            # Show waiting message occasionally
            if scan_count == 0 or (current_minute % 30 == 0):
                print(f"⏳ Waiting for market open...")
        
        # Check if we should continue
        if not _daemon_running:
            break
            
        # Sleep until next scan interval
        sleep_seconds = interval_minutes * 60
        for _ in range(sleep_seconds):
            if not _daemon_running:
                break
            time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"🛑 DAEMON STOPPED")
    print(f"Total scans completed: {scan_count}")
    print(f"{'='*60}")


def single_analysis(symbol: str, market_str: str = "equity"):
    """Run a single analysis from command-line args."""
    state = RiskState.load()

    if market_str in ("equity", "stock", "nse", "bse"):
        market = MarketType.INDIA_EQUITY
    else:
        market = MarketType.CRYPTO

    print(analyze_asset(symbol, market, state, force=True))


def parse_auto_args(args_list):
    """Parse command line arguments for auto/daemon mode."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Trading Signal Analyzer - Automated Mode",
        prog="python main.py auto"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=15,
        help="Scan interval in minutes (default: 15)"
    )
    parser.add_argument(
        "--markets", "-m",
        nargs="+",
        default=["equity", "crypto"],
        choices=["equity", "crypto"],
        help="Markets to scan (default: equity crypto)"
    )
    parser.add_argument(
        "--telegram", "-t",
        action="store_true",
        help="Enable Telegram notifications"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env)"
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=os.environ.get("TELEGRAM_CHAT_ID", ""),
        help="Telegram chat ID (or set TELEGRAM_CHAT_ID env)"
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help="Disable smart scheduling (run 24/7)"
    )
    
    # Remove 'auto', 'daemon', 'run' and script name from args
    clean_args = [a for a in args_list[2:] if a.lower() not in ('auto', 'daemon', 'run')]
    return parser.parse_args(clean_args)


def parse_serve_args(args_list):
    """Same as auto/daemon args, for `python main.py serve` (Render free Web Service)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Trading Signal Analyzer — Web mode (HTTP + bot in background)",
        prog="python main.py serve",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=15,
        help="Scan interval in minutes (default: 15)",
    )
    parser.add_argument(
        "--markets", "-m",
        nargs="+",
        default=["equity", "crypto"],
        choices=["equity", "crypto"],
        help="Markets to scan (default: equity crypto)",
    )
    parser.add_argument(
        "--telegram", "-t",
        action="store_true",
        help="Enable Telegram notifications",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env)",
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=os.environ.get("TELEGRAM_CHAT_ID", ""),
        help="Telegram chat ID (or set TELEGRAM_CHAT_ID env)",
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help="Disable smart scheduling (run 24/7)",
    )
    clean_args = [a for a in args_list[2:] if a.lower() != "serve"]
    return parser.parse_args(clean_args)


def run_web_server_with_bot(
    interval_minutes: int = 15,
    markets: List[str] = None,
    telegram_enabled: bool = False,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    smart_schedule: bool = True,
) -> None:
    """
    Run Flask (homepage + APIs) on 0.0.0.0:$PORT and the trading daemon in a background thread.
    GET / always returns the HTML dashboard from web_dashboard.
    """
    port = int(os.environ.get("PORT", "10000"))

    def on_signal(signum, frame):
        global _daemon_running
        _daemon_running = False

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    def _run_bot():
        run_daemon_mode(
            interval_minutes=interval_minutes,
            markets=markets,
            telegram_enabled=telegram_enabled,
            token=token,
            chat_id=chat_id,
            smart_schedule=smart_schedule,
            register_signals=False,
        )

    bot_thread = threading.Thread(target=_run_bot, name="indo-bot-daemon", daemon=True)
    bot_thread.start()

    from web_dashboard import app as flask_app

    print(f"\n🌐 Homepage (HTML): http://0.0.0.0:{port}/")
    print("   /health + /api/* JSON · /crypto → /#crypto")
    print("   Bot daemon runs in background (same as `auto`).\n")
    flask_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        # Debug: print command
        # print(f"Command: {cmd}, Args: {sys.argv}")
        
        # Check for scan command first
        if cmd == "scan":
            market_str = sys.argv[2].lower() if len(sys.argv) > 2 else "crypto"
            if market_str in ("equity", "stock", "nse"):
                market = MarketType.INDIA_EQUITY
            else:
                market = MarketType.CRYPTO
            state = RiskState.load()
            print(scan_watchlist(market, state))
        # Check for auto/daemon mode
        elif cmd == "serve":
            args = parse_serve_args(sys.argv)
            run_web_server_with_bot(
                interval_minutes=args.interval,
                markets=args.markets,
                telegram_enabled=args.telegram,
                token=args.token if args.token else None,
                chat_id=args.chat_id if args.chat_id else None,
                smart_schedule=not args.no_schedule,
            )
        elif cmd in ("auto", "daemon", "run"):
            args = parse_auto_args(sys.argv)
            run_daemon_mode(
                interval_minutes=args.interval,
                markets=args.markets,
                telegram_enabled=args.telegram,
                token=args.token if args.token else None,
                chat_id=args.chat_id if args.chat_id else None,
                smart_schedule=not args.no_schedule,
            )
        # Single analysis mode
        else:
            symbol = sys.argv[1].upper()
            market_str = sys.argv[2] if len(sys.argv) > 2 else "equity"
            single_analysis(symbol, market_str)
    else:
        interactive_loop()
