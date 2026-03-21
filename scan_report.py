"""
Detailed watchlist scan output: rankings, entry focus, and strong signal education.

Strong buy/sell criteria align with common multi-factor TA practice (RSI + MACD +
volume confirmation); see README for external references.
"""

import datetime
from typing import List, Optional, Sequence

from zoneinfo import ZoneInfo

from config import SignalType, TradeSignal
from risk_manager import RiskState
from formatter import format_signal_report

IST = ZoneInfo("Asia/Kolkata")


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


def _sort_by_confidence(signals: Sequence[TradeSignal]) -> List[TradeSignal]:
    return sorted(signals, key=lambda s: s.confidence, reverse=True)


def format_entry_focus_table(results: Sequence[TradeSignal]) -> str:
    """Compact table: where to look for entries (all symbols)."""
    lines = [
        "",
        "┌─ WHERE TO LOOK (ENTRY FOCUS) ────────────────────────────────────────────┐",
        f"│ {'Symbol':<12} {'Sig':<5} {'Conf':<6} {'Entry zone (mid)':<28} {'Stop':<14} │",
        "├" + "─" * 74 + "┤",
    ]
    for s in _sort_by_confidence(list(results)):
        c = s.currency_symbol
        mid = (s.entry_low + s.entry_high) / 2
        sig = s.signal.value
        entry_txt = f"{c}{s.entry_low:,.2f}-{c}{s.entry_high:,.2f}"
        if len(entry_txt) > 28:
            entry_txt = entry_txt[:25] + "..."
        lines.append(
            f"│ {s.asset:<12} {sig:<5} {s.confidence}/10  {entry_txt:<28} {c}{s.stop_loss:,.2f} │"
        )
    lines.append("└" + "─" * 74 + "┘")
    return "\n".join(lines)


def format_ranked_opportunities(results: Sequence[TradeSignal]) -> str:
    """Rank BUY and SELL separately by confidence; explain top picks."""
    buys = _sort_by_confidence([r for r in results if r.signal == SignalType.BUY])
    sells = _sort_by_confidence([r for r in results if r.signal == SignalType.SELL])
    holds = _sort_by_confidence([r for r in results if r.signal == SignalType.HOLD])

    blocks = []

    if buys:
        blocks.append("🟢 HIGHEST-CONFIDENCE BUY IDEAS (consider these first for longs)")
        for i, s in enumerate(buys, 1):
            c = s.currency_symbol
            blocks.append(
                f"   {i}. {s.asset} — confidence {s.confidence}/10 | "
                f"entry zone {c}{s.entry_low:,.2f}–{c}{s.entry_high:,.2f} | "
                f"SL {c}{s.stop_loss:,.2f} | T1 {c}{s.target_1:,.2f}"
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
                f"entry zone {c}{s.entry_low:,.2f}–{c}{s.entry_high:,.2f} | "
                f"SL {c}{s.stop_loss:,.2f} | T1 {c}{s.target_1:,.2f}"
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
) -> str:
    """
    Full textual report after a watchlist scan: rankings, table, education, optional full signal for top actionable.
    """
    if not results:
        return "\n⚠️ No symbols returned data — check network or symbols.\n"

    lines = [
        "",
        "╔" + "═" * 68 + "╗",
        f"║  DETAILED SCAN — {market_name.upper():<48} ║",
        "╚" + "═" * 68 + "╝",
        "",
        format_ranked_opportunities(results),
        "",
        format_entry_focus_table(results),
        "",
    ]

    if include_guide:
        lines.append(STRONG_SIGNAL_GUIDE)

    actionable = _sort_by_confidence(
        [r for r in results if r.signal != SignalType.HOLD]
    )
    if include_full_top_report and actionable:
        top = actionable[0]
        now = datetime.datetime.now(IST)
        lines.append("")
        lines.append("═" * 70)
        lines.append(f" FULL REPORT — HIGHEST-CONFIDENCE ACTIONABLE: {top.asset} ")
        lines.append("═" * 70)
        lines.append(
            format_signal_report(top, context=None, risk_state=risk_state, now=now)
        )
    elif include_full_top_report and not actionable:
        # All HOLD: show full report for highest confidence name for detail
        best = _sort_by_confidence(results)[0]
        now = datetime.datetime.now(IST)
        lines.append("")
        lines.append("═" * 70)
        lines.append(
            f" FULL REPORT — HIGHEST CONFIDENCE (HOLD): {best.asset} — for levels only "
        )
        lines.append("═" * 70)
        lines.append(
            format_signal_report(best, context=None, risk_state=None, now=now)
        )

    return "\n".join(lines)
