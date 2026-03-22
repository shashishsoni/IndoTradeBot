"""
Formatted output for signal reports.
Matches the exact output template specified in the system rules.
"""

import datetime
from typing import List, Optional

from zoneinfo import ZoneInfo

from config import MarketType, SignalType, TradeSignal
from market_context import MarketContextReport
from risk_manager import RiskState, calculate_position_size

IST = ZoneInfo("Asia/Kolkata")

SIGNAL_EMOJI = {
    SignalType.BUY: "\U0001f7e2 BUY",
    SignalType.SELL: "\U0001f534 SELL",
    SignalType.HOLD: "\U0001f7e1 HOLD",
}

SEPARATOR = "═" * 50


def _fmt_price(value: float, currency: str) -> str:
    if currency == "$":
        if value >= 1:
            return f"${value:,.2f}"
        return f"${value:,.6f}"
    return f"₹{value:,.2f}"


def format_signal_report(
    signal: TradeSignal,
    context: Optional[MarketContextReport] = None,
    risk_state: Optional[RiskState] = None,
    now: Optional[datetime.datetime] = None,
) -> str:
    if now is None:
        now = datetime.datetime.now(IST)

    c = signal.currency_symbol
    timestamp = now.strftime("%d %b %Y / %I:%M %p IST")

    lines = [
        "",
        SEPARATOR,
        f"\U0001f4ca SIGNAL REPORT — {timestamp}",
        SEPARATOR,
        f"ASSET:        {signal.asset}",
    ]
    if signal.market == MarketType.CRYPTO:
        lines.append("SOURCE:       ZebPay Spot · INR (public klines)")
    lines.extend(
        [
            f"SIGNAL:       {SIGNAL_EMOJI[signal.signal]}",
            f"ENTRY ZONE:   {_fmt_price(signal.entry_low, c)} – {_fmt_price(signal.entry_high, c)}",
            f"STOP LOSS:    {_fmt_price(signal.stop_loss, c)}  (Risk: {signal.risk_pct}%)",
            f"TARGET 1:     {_fmt_price(signal.target_1, c)}  (R:R = 1:{signal.rr_t1})",
            f"TARGET 2:     {_fmt_price(signal.target_2, c)}  (R:R = 1:{signal.rr_t2})",
            f"TIMEFRAME:    {signal.timeframe.value}",
            f"CONFIDENCE:   {signal.confidence}/10",
            f"INVALIDATION: {signal.invalidation}",
            "",
            "REASONING:",
        ]
    )

    for i, tech in enumerate(signal.reasoning_technical, 1):
        lines.append(f"  → Technical {i}: {tech}")
    lines.append(f"  → Fundamental: {signal.reasoning_fundamental}")

    # Position sizing
    if risk_state and signal.signal != SignalType.HOLD:
        pos_mod = context.position_size_modifier if context else 1.0
        sizing = calculate_position_size(
            risk_state.capital,
            signal.entry_mid,
            signal.stop_loss,
            pos_mod,
        )
        lines.append("")
        lines.append("POSITION SIZING:")
        lines.append(f"  Capital:       {c}{risk_state.capital:,.2f}")
        lines.append(f"  Risk (2%):     {c}{sizing['risk_amount']:,.2f}")
        lines.append(f"  Units to buy:  {sizing['units']:,.4f}")
        lines.append(f"  Position value:{c}{sizing['position_value']:,.2f}")

    # Risk notes
    all_notes = list(signal.risk_notes)
    if context:
        all_notes.extend(context.warnings)

    if all_notes:
        lines.append("")
        lines.append("RISK NOTES:")
        for note in all_notes:
            lines.append(f"  ⚠ {note}")

    lines.append(SEPARATOR)
    lines.append(
        "DISCLAIMER: This is algorithmic analysis, not financial advice. "
        "Past performance does not guarantee future results. "
        "Never risk more than you can afford to lose."
    )
    lines.append(SEPARATOR)
    lines.append("")

    return "\n".join(lines)


def format_context_warnings(context: MarketContextReport) -> str:
    if not context.warnings:
        return ""
    lines = ["\n⚠ MARKET CONTEXT WARNINGS:"]
    for w in context.warnings:
        lines.append(f"  • {w}")
    return "\n".join(lines)


def format_skip_message(context: MarketContextReport) -> str:
    hint = ""
    if "Weekend" in context.skip_reason or "Outside NSE" in context.skip_reason:
        hint = (
            "\nTip: For chart research on weekends or after hours, run:\n"
            "     analyze <SYMBOL> equity --force\n"
        )
    return (
        f"\n🚫 SIGNAL BLOCKED: {context.skip_reason}\n"
        "No signal generated — conditions do not meet safety filters."
        f"{hint}\n"
    )


def format_review_mode_message(state: RiskState) -> str:
    return (
        f"\n🔍 REVIEW MODE ACTIVE\n"
        f"{'─' * 40}\n"
        f"Consecutive losses: {state.consecutive_losses}\n"
        f"Current drawdown:   {state.drawdown:.1%}\n"
        f"Win rate:           {state.win_rate:.1%}\n\n"
        f"Action required:\n"
        f"  1. Review last {state.consecutive_losses} losing trades\n"
        f"  2. Identify pattern (wrong timeframe? ignoring volume? fighting trend?)\n"
        f"  3. Reset review mode only after analysis\n"
        f"{'─' * 40}\n"
    )


def format_halt_message(state: RiskState) -> str:
    return (
        f"\n🛑 TRADING HALTED\n"
        f"{'─' * 40}\n"
        f"Drawdown: {state.drawdown:.1%} (threshold: 10%)\n"
        f"Capital:  {state.capital:,.2f} / {state.initial_capital:,.2f}\n\n"
        f"ALL SIGNAL GENERATION SUSPENDED.\n"
        f"Human review required before resuming.\n"
        f"{'─' * 40}\n"
    )
