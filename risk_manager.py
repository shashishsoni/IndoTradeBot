"""
Risk management engine.
Enforces position sizing, drawdown limits, review mode, and signal caps.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from config import (
    CONSECUTIVE_LOSS_THRESHOLD,
    MAX_DRAWDOWN_HALT,
    MAX_RISK_PER_TRADE,
    MAX_SIMULTANEOUS_SIGNALS,
)

STATE_FILE = os.path.join(os.path.dirname(__file__), "risk_state.json")


def _parse_capital_from_env() -> Optional[float]:
    """Read CAPITAL or TRADING_CAPITAL from environment (for servers without risk_state.json)."""
    for key in ("CAPITAL", "TRADING_CAPITAL"):
        raw = os.environ.get(key)
        if not raw:
            continue
        try:
            val = float(str(raw).replace(",", "").strip())
            if val > 0:
                return val
        except ValueError:
            continue
    return None


@dataclass
class RiskState:
    capital: float = 100_000.0
    initial_capital: float = 100_000.0
    active_signals: int = 0
    consecutive_losses: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    review_mode: bool = False
    halted: bool = False
    trade_log: List[dict] = field(default_factory=list)

    @property
    def drawdown(self) -> float:
        if self.initial_capital == 0:
            return 0
        return (self.initial_capital - self.capital) / self.initial_capital

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades

    def save(self):
        data = {
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "active_signals": self.active_signals,
            "consecutive_losses": self.consecutive_losses,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "review_mode": self.review_mode,
            "halted": self.halted,
            "trade_log": self.trade_log[-50:],  # keep last 50
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "RiskState":
        """
        Load persisted state if present.

        - No risk_state.json (e.g. fresh deploy): use CAPITAL / TRADING_CAPITAL env if set.
        - File exists: load it; only replace capital from env if FORCE_CAPITAL_FROM_ENV=1.
          (So local dev keeps risk_state.json unless you force a reset.)
        """
        env_cap = _parse_capital_from_env()
        force_env = os.environ.get("FORCE_CAPITAL_FROM_ENV", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if not os.path.exists(STATE_FILE):
            state = cls()
            if env_cap is not None:
                state.capital = env_cap
                state.initial_capital = env_cap
            return state

        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            state = cls(**data)
        except Exception:
            state = cls()

        if env_cap is not None and force_env:
            state.capital = env_cap
            state.initial_capital = env_cap
        return state


def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    position_modifier: float = 1.0,
) -> dict:
    """
    Position size = (Capital × 0.02) ÷ (Entry − Stop Loss)
    Returns dict with units, capital_at_risk, and total_position_value.
    """
    risk_amount = capital * MAX_RISK_PER_TRADE * position_modifier
    risk_per_unit = abs(entry_price - stop_loss)

    if risk_per_unit == 0:
        return {"units": 0, "capital_at_risk": 0, "position_value": 0, "risk_amount": 0}

    units = risk_amount / risk_per_unit
    position_value = units * entry_price

    return {
        "units": round(units, 4),
        "capital_at_risk": round(risk_amount, 2),
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
    }


def check_can_trade(state: RiskState) -> tuple:
    """
    Returns (can_trade: bool, reason: str).
    Enforces all risk management gates.
    """
    if state.halted:
        return False, (
            "HALTED: Drawdown exceeds 10% of capital. "
            "All signals suspended — requires human review to resume."
        )

    if state.review_mode:
        return False, (
            f"REVIEW MODE: {state.consecutive_losses} consecutive losses. "
            "Analyze recent trades before generating new signals."
        )

    if state.active_signals >= MAX_SIMULTANEOUS_SIGNALS:
        return False, (
            f"Maximum {MAX_SIMULTANEOUS_SIGNALS} active signals reached. "
            "Close an existing position before entering new trades."
        )

    if state.drawdown >= MAX_DRAWDOWN_HALT:
        state.halted = True
        state.save()
        return False, (
            f"DRAWDOWN ALERT: {state.drawdown:.1%} loss from peak capital. "
            "All trading halted. Human review required."
        )

    return True, "OK"


def record_trade_result(state: RiskState, pnl: float, asset: str) -> str:
    """Record a trade result and update risk state."""
    state.total_trades += 1

    if pnl > 0:
        state.winning_trades += 1
        state.consecutive_losses = 0
        state.review_mode = False
    else:
        state.losing_trades += 1
        state.consecutive_losses += 1

    state.capital += pnl
    state.active_signals = max(0, state.active_signals - 1)

    state.trade_log.append({
        "asset": asset,
        "pnl": pnl,
        "capital_after": state.capital,
    })

    message = f"Trade on {asset}: PnL = {pnl:+,.2f} | Capital: {state.capital:,.2f}"

    if state.consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
        state.review_mode = True
        message += (
            f"\n⚠ REVIEW MODE ACTIVATED: {state.consecutive_losses} consecutive losses. "
            "Stop and analyze what failed."
        )

    if state.drawdown >= MAX_DRAWDOWN_HALT:
        state.halted = True
        message += (
            f"\n🛑 HALT: Drawdown {state.drawdown:.1%}. All signals suspended."
        )

    state.save()
    return message


def get_risk_summary(state: RiskState) -> str:
    """Return a human-readable risk dashboard."""
    lines = [
        "═══ RISK DASHBOARD ═══",
        f"Capital:         {state.capital:>12,.2f}",
        f"Initial Capital: {state.initial_capital:>12,.2f}",
        f"Drawdown:        {state.drawdown:>11.1%}",
        f"Active Signals:  {state.active_signals} / {MAX_SIMULTANEOUS_SIGNALS}",
        f"Total Trades:    {state.total_trades}",
        f"Win Rate:        {state.win_rate:.1%}",
        f"Consec. Losses:  {state.consecutive_losses}",
        f"Review Mode:     {'YES' if state.review_mode else 'No'}",
        f"Halted:          {'YES' if state.halted else 'No'}",
        "═══════════════════════",
    ]
    return "\n".join(lines)
