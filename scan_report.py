"""
Detailed watchlist scan output: rankings, entry focus, and strong signal education.

Strong buy/sell criteria align with common multi-factor TA practice (RSI + MACD +
volume confirmation); see README for external references.
"""

import datetime
from typing import Any, Dict, List, Optional, Sequence

from zoneinfo import ZoneInfo

from config import SignalType, TradeSignal
from risk_manager import RiskState
from formatter import format_signal_report
from zebpay_client import format_trade_price_line, format_zebpay_inr_price

IST = ZoneInfo("Asia/Kolkata")


def _is_crypto_scan(market_name: str) -> bool:
    return market_name.strip().lower() == "crypto"


# Educational text (synthesized from standard TA practice; not personalized advice)
STRONG_SIGNAL_GUIDE = """
┌─ HOW THIS BOT LABELS SIGNALS ─────────────────────────────────────────────┐
│  • BUY / SELL = model sees directional edge from EMA, RSI, MACD, volume.   │
│  • HOLD = no clear edge (often RSI 45–55 or mixed indicators).            │
│  • Confidence 1–10 = how many factors align (higher = stronger alignment). │
└───────────────────────────────────────────────────────────────────────────┘

📚 WHAT USUALLY MAKES A *STRONG* BUY (industry practice)
   • Trend: price above rising EMA20 / EMA50 (or golden cross forming).
   • Momentum: RSI rising from oversold OR holding above 50 in an uptrend.
   • Confirmation: MACD line above signal line; histogram positive.
   • Participation: volume clearly above recent average (institutional interest).
   • Invalidation: break below your planned stop or key support — exit the thesis.

📚 WHAT USUALLY MAKES A *STRONG* SELL / SHORT THESIS
   • Trend: price below falling EMAs; death cross or breakdown.
   • Momentum: RSI failing below 50 from overbought; weakness on bounces.
   • Confirmation: MACD below signal; negative histogram.
   • Participation: volume spike on down moves (distribution).
   • Always use a hard stop — short squeezes are common in crypto and volatile names.

⚠️  This app does not predict the future. Use the ranked list below to *prioritize*
   which names to research first; then verify on charts, news, and your risk rules.
"""

# Short version for Telegram (mobile-friendly, no wide box-drawing)
STRONG_SIGNAL_GUIDE_TELEGRAM = """
▸ HOW TO READ THIS
  • BUY / SELL = directional edge from indicators; HOLD = no clear edge.
  • Confidence 1–10 = factor alignment (not a guarantee).

▸ STRONG SETUPS (typical TA)
  • Buy: trend + RSI momentum + MACD + volume; use stops.
  • Sell: opposite + distribution volume.

⚠️ Not advice — verify on charts before trading.
"""


def _sort_by_confidence(signals: Sequence[TradeSignal]) -> List[TradeSignal]:
    return sorted(signals, key=lambda s: s.confidence, reverse=True)


def _fmt_inr_compact(value: float) -> str:
    """Short ₹ for Telegram (L/Cr for large prices; extra decimals for meme quotes)."""
    return format_zebpay_inr_price(value)


def _fmt_money(currency_symbol: str, value: float) -> str:
    if currency_symbol == "₹":
        return _fmt_inr_compact(value)
    return f"{currency_symbol}{value:,.2f}"


def format_entry_focus_table(
    results: Sequence[TradeSignal],
    *,
    zebpay_inr: bool = False,
    telegram_format: bool = False,
) -> str:
    """Entry zone table — console uses box chars; Telegram uses stacked lines."""
    if telegram_format:
        sub = "ZebPay INR · ₹" if zebpay_inr else "₹"
        lines = ["", f"▸ ENTRY ({sub})", ""]
        for s in _sort_by_confidence(list(results)):
            c = s.currency_symbol
            sig = s.signal.value
            entry_txt = f"{_fmt_money(c, s.entry_low)} – {_fmt_money(c, s.entry_high)}"
            sl_txt = _fmt_money(c, s.stop_loss)
            lines.append(f"  {s.asset}  ·  {sig}  ·  {s.confidence}/10")
            lines.append(f"     Zone: {entry_txt}")
            lines.append(f"     SL:   {sl_txt}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    title = (
        "┌─ ENTRY — ZebPay Spot INR (₹) — zone / SL ─────────────────────┐"
        if zebpay_inr
        else "┌─ ENTRY (₹) — zone / SL ─────────────────────────────────────────┐"
    )
    lines = [
        "",
        title,
    ]
    for s in _sort_by_confidence(list(results)):
        c = s.currency_symbol
        sig = s.signal.value
        entry_txt = (
            f"{_fmt_money(c, s.entry_low)}–{_fmt_money(c, s.entry_high)}"
        )
        sl_txt = _fmt_money(c, s.stop_loss)
        lines.append(
            f"│ {s.asset:<8} {sig:<4} {s.confidence}/10  {entry_txt}  SL {sl_txt} │"
        )
    lines.append("└" + "─" * 64 + "┘")
    return "\n".join(lines)


def format_ranked_opportunities(
    results: Sequence[TradeSignal],
    *,
    telegram_format: bool = False,
) -> str:
    """Rank BUY and SELL separately by confidence; explain top picks."""
    buys = _sort_by_confidence([r for r in results if r.signal == SignalType.BUY])
    sells = _sort_by_confidence([r for r in results if r.signal == SignalType.SELL])
    holds = _sort_by_confidence([r for r in results if r.signal == SignalType.HOLD])

    blocks = []

    if telegram_format:
        if buys:
            blocks.append("▸ BUY IDEAS")
            for i, s in enumerate(buys, 1):
                c = s.currency_symbol
                blocks.append(f"  {i}. {s.asset}  ·  {s.confidence}/10")
                blocks.append(
                    f"     Entry {format_trade_price_line(c, s.entry_low)}–{format_trade_price_line(c, s.entry_high)}  ·  "
                    f"SL {format_trade_price_line(c, s.stop_loss)}  ·  T1 {format_trade_price_line(c, s.target_1)}"
                )
            blocks.append(f"  ⭐ Top: {buys[0].asset}")
        else:
            blocks.append("▸ BUY: none")

        blocks.append("")

        if sells:
            blocks.append("▸ SELL IDEAS")
            for i, s in enumerate(sells, 1):
                c = s.currency_symbol
                blocks.append(f"  {i}. {s.asset}  ·  {s.confidence}/10")
                blocks.append(
                    f"     Entry {format_trade_price_line(c, s.entry_low)}–{format_trade_price_line(c, s.entry_high)}  ·  "
                    f"SL {format_trade_price_line(c, s.stop_loss)}"
                )
            blocks.append(f"  ⭐ Top: {sells[0].asset}")
        else:
            blocks.append("▸ SELL: none")

        blocks.append("")

        if holds and not buys and not sells:
            top_h = holds[0]
            blocks.append(
                f"▸ ALL HOLD — watch {top_h.asset} ({top_h.confidence}/10)"
            )
        elif holds:
            blocks.append(
                f"▸ HOLD ({len(holds)}) — top: {holds[0].asset} ({holds[0].confidence}/10)"
            )
        return "\n".join(blocks)

    if buys:
        blocks.append("🟢 HIGHEST-CONFIDENCE BUY IDEAS (consider these first for longs)")
        for i, s in enumerate(buys, 1):
            c = s.currency_symbol
            blocks.append(
                f"   {i}. {s.asset} — confidence {s.confidence}/10 | "
                f"entry zone {format_trade_price_line(c, s.entry_low)}–{format_trade_price_line(c, s.entry_high)} | "
                f"SL {format_trade_price_line(c, s.stop_loss)} | T1 {format_trade_price_line(c, s.target_1)}"
            )
        top = buys[0]
        blocks.append("")
        blocks.append(
            f"   ⭐ TOP BUY PICK THIS SCAN: {top.asset} (confidence {top.confidence}/10). "
            f"Use the full report below for invalidation and reasoning."
        )
    else:
        blocks.append("🟢 BUY: none in this scan — no name met the model’s BUY rules.")

    blocks.append("")

    if sells:
        blocks.append("🔴 HIGHEST-CONFIDENCE SELL / SHORT-THESIS IDEAS")
        for i, s in enumerate(sells, 1):
            c = s.currency_symbol
            blocks.append(
                f"   {i}. {s.asset} — confidence {s.confidence}/10 | "
                f"entry zone {format_trade_price_line(c, s.entry_low)}–{format_trade_price_line(c, s.entry_high)} | "
                f"SL {format_trade_price_line(c, s.stop_loss)} | T1 {format_trade_price_line(c, s.target_1)}"
            )
        top = sells[0]
        blocks.append("")
        blocks.append(
            f"   ⭐ TOP SELL PICK THIS SCAN: {top.asset} (confidence {top.confidence}/10)."
        )
    else:
        blocks.append("🔴 SELL: none in this scan — no name met the model’s SELL rules.")

    blocks.append("")

    if holds and not buys and not sells:
        top_h = holds[0]
        blocks.append(
            f"🟡 ALL HOLD — strongest *watch* (still not a directional BUY/SELL): "
            f"{top_h.asset} at {top_h.confidence}/10. Wait for breakout of invalidation "
            f"or run `analyze {top_h.asset} <market>` after fresh candles."
        )
    elif holds:
        blocks.append(
            f"🟡 HOLD names ({len(holds)}): lower priority until trend clarifies — "
            f"highest confidence HOLD is {holds[0].asset} ({holds[0].confidence}/10)."
        )

    return "\n".join(blocks)


def format_detailed_scan_report(
    results: List[TradeSignal],
    market_name: str,
    risk_state: Optional[RiskState] = None,
    include_guide: bool = True,
    include_full_top_report: bool = True,
    crypto_watchlist_diag: Optional[Dict[str, Any]] = None,
    telegram_format: bool = False,
) -> str:
    """
    Full textual report after a watchlist scan: rankings, table, education, optional full signal for top actionable.
    Set telegram_format=True for mobile-friendly layout (Telegram).
    """
    if not results:
        return "\n⚠️ No symbols returned data — check network or symbols.\n"

    is_crypto = _is_crypto_scan(market_name)
    tg = telegram_format
    sep = "──────────────" if tg else None

    if tg:
        lines = [
            "",
            sep,
            f"📊 SCAN · {market_name.upper()}",
            sep,
            "",
        ]
    else:
        lines = [
            "",
            "╔" + "═" * 68 + "╗",
            f"║  DETAILED SCAN — {market_name.upper():<48} ║",
            "╚" + "═" * 68 + "╝",
        ]

    if is_crypto:
        if tg:
            lines.extend(
                [
                    "💱 ZebPay Spot · INR (₹ from API)",
                    "",
                ]
            )
        else:
            lines.append(
                "💱 Data: ZebPay Spot · INR pairs (BTC-INR, …) — ₹ = Indian Rupees from API."
            )
        if crypto_watchlist_diag:
            from zebpay_client import format_crypto_watchlist_summary

            if tg:
                lines.append(f"⚙️ {format_crypto_watchlist_summary(crypto_watchlist_diag)}")
            else:
                lines.append(f"  ⚙️ {format_crypto_watchlist_summary(crypto_watchlist_diag)}")
            xs = crypto_watchlist_diag.get("symbols") or []
            if xs:
                if len(xs) <= (20 if tg else 30):
                    listing = ", ".join(xs)
                else:
                    lim = 20 if tg else 30
                    listing = ", ".join(xs[:lim]) + f" … (+{len(xs) - lim} more)"
                label = f"Symbols ({len(xs)})" if tg else f"  📋 Watchlist ({len(xs)})"
                lines.append(f"{label}:\n{listing}" if tg else f"{label}: {listing}")
            miss = crypto_watchlist_diag.get("xpress_not_on_exchange_api") or []
            if miss:
                shown = miss[: (8 if tg else 15)]
                tail = " …" if len(miss) > len(shown) else ""
                if tg:
                    lines.append(
                        f"⏭️ Not on Open INR API ({len(miss)}): {', '.join(shown)}{tail}"
                    )
                else:
                    lines.append(
                        f"  ⏭️ Xpress names not Open INR on API ({len(miss)}): "
                        f"{', '.join(shown)}{tail}"
                    )
        lines.append("")

    lines.extend(
        [
            format_ranked_opportunities(results, telegram_format=tg),
            "",
            format_entry_focus_table(
                results, zebpay_inr=is_crypto, telegram_format=tg
            ),
            "",
        ]
    )

    if include_guide:
        lines.append(STRONG_SIGNAL_GUIDE_TELEGRAM if tg else STRONG_SIGNAL_GUIDE)

    actionable = _sort_by_confidence(
        [r for r in results if r.signal != SignalType.HOLD]
    )
    if include_full_top_report and actionable:
        top = actionable[0]
        now = datetime.datetime.now(IST)
        lines.append("")
        if tg:
            lines.extend([sep, ""])  # break before full signal (title is inside format_signal_report)
        else:
            lines.extend(
                [
                    "═" * 70,
                    f" FULL REPORT — HIGHEST-CONFIDENCE ACTIONABLE: {top.asset} ",
                    "═" * 70,
                ]
            )
        lines.append(
            format_signal_report(
                top,
                context=None,
                risk_state=risk_state,
                now=now,
                telegram_format=tg,
            )
        )
    elif include_full_top_report and not actionable:
        best = _sort_by_confidence(results)[0]
        now = datetime.datetime.now(IST)
        lines.append("")
        if tg:
            lines.extend([sep, ""])
        else:
            lines.extend(
                [
                    "═" * 70,
                    f" FULL REPORT — HIGHEST CONFIDENCE (HOLD): {best.asset} — for levels only ",
                    "═" * 70,
                ]
            )
        lines.append(
            format_signal_report(
                best,
                context=None,
                risk_state=None,
                now=now,
                telegram_format=tg,
            )
        )

    return "\n".join(lines)
