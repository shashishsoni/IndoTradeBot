"""
Core signal generation engine.
Combines indicators, market context, and risk rules to produce TradeSignal objects.
"""

from typing import List, Optional, Tuple

import pandas as pd

from config import (
    AGGRESSIVE_RR_RATIO,
    MIN_REWARD_RISK_RATIO,
    Confidence,
    MarketType,
    SignalType,
    Timeframe,
    TradeSignal,
)
from indicators import (
    IndicatorSnapshot,
    compute_indicators,
    detect_ema_crossover,
    find_support_resistance,
)


def _round_price(price: float, market: MarketType) -> float:
    if market == MarketType.CRYPTO:
        if price > 1000:
            return round(price, 2)
        if price > 1:
            return round(price, 4)
        return round(price, 6)
    return round(price, 2)


def _determine_timeframe(df: pd.DataFrame) -> Timeframe:
    """Infer timeframe from the data interval."""
    if len(df) < 2:
        return Timeframe.INTRADAY

    delta = df.index[-1] - df.index[-2]
    minutes = delta.total_seconds() / 60

    if minutes <= 15:
        return Timeframe.SCALP
    if minutes <= 60:
        return Timeframe.INTRADAY
    if minutes <= 1440:  # daily
        return Timeframe.SWING
    return Timeframe.POSITIONAL


def _build_reasoning(
    snap: IndicatorSnapshot,
    crossover: Optional[str],
    signal: SignalType,
    support: float,
    resistance: float,
) -> Tuple[List[str], str]:
    """Build at least 3 technical + 1 fundamental reason."""
    technicals = []
    fundamental = ""
    price = snap.ema_20  # proxy for current price

    if signal == SignalType.BUY:
        if snap.ema_bullish_stack:
            technicals.append(
                f"EMA stack bullish: EMA20 ({snap.ema_20:.2f}) > "
                f"EMA50 ({snap.ema_50:.2f}) > EMA200 ({snap.ema_200:.2f})"
            )
        elif crossover == "golden_cross":
            technicals.append("EMA 20/50 golden cross detected in last 3 bars")
        else:
            technicals.append(
                f"Price near EMA20 ({snap.ema_20:.2f}) — potential dynamic support"
            )

        if snap.rsi_oversold:
            technicals.append(f"RSI ({snap.rsi:.1f}) in oversold territory (<30) — bounce likely")
        elif snap.rsi < 50:
            technicals.append(f"RSI ({snap.rsi:.1f}) below 50 with room to rise")

        if snap.macd_bullish_cross:
            technicals.append("MACD histogram positive with bullish signal cross")
        elif snap.macd_hist > snap.macd_signal * 0.5:
            technicals.append(f"MACD histogram ({snap.macd_hist:.4f}) trending positive")

        if snap.volume_spike:
            technicals.append(
                f"Volume spike: {snap.volume_current:,.0f} vs "
                f"20-day avg {snap.volume_avg_20:,.0f}"
            )

        if snap.bb_squeeze:
            technicals.append("Bollinger Band squeeze — breakout imminent")

        fundamental = (
            f"Price holding above key support at {support:.2f}; "
            f"next resistance at {resistance:.2f}"
        )

    elif signal == SignalType.SELL:
        if snap.ema_bearish_stack:
            technicals.append(
                f"EMA stack bearish: EMA20 ({snap.ema_20:.2f}) < "
                f"EMA50 ({snap.ema_50:.2f}) < EMA200 ({snap.ema_200:.2f})"
            )
        elif crossover == "death_cross":
            technicals.append("EMA 20/50 death cross detected in last 3 bars")
        else:
            technicals.append(
                f"Price below EMA20 ({snap.ema_20:.2f}) — acting as resistance"
            )

        if snap.rsi_overbought:
            technicals.append(f"RSI ({snap.rsi:.1f}) overbought (>70) — reversal likely")
        elif snap.rsi > 50:
            technicals.append(f"RSI ({snap.rsi:.1f}) declining from above 50")

        if snap.macd_bearish_cross:
            technicals.append("MACD histogram negative with bearish signal cross")
        else:
            technicals.append(f"MACD histogram ({snap.macd_hist:.4f}) trending negative")

        if snap.obv_slope < 0:
            technicals.append("OBV declining — distribution detected")

        fundamental = (
            f"Price rejected from resistance at {resistance:.2f}; "
            f"support at {support:.2f} could be tested"
        )

    else:  # HOLD
        technicals.append(f"RSI ({snap.rsi:.1f}) in neutral zone — no clear momentum")
        technicals.append(
            f"EMA20 ({snap.ema_20:.2f}) and EMA50 ({snap.ema_50:.2f}) converging"
        )
        technicals.append("No confirmed MACD crossover — wait for direction")
        fundamental = "Market consolidating between S/R levels; patience required"

    while len(technicals) < 3:
        technicals.append(f"ATR ({snap.atr:.2f}) indicating current volatility regime")

    return technicals[:4], fundamental


def _compute_confidence(
    snap: IndicatorSnapshot,
    crossover: Optional[str],
    signal: SignalType,
) -> int:
    """Score 1-10 based on indicator alignment."""
    score = 5  # baseline

    if signal == SignalType.BUY:
        if snap.ema_bullish_stack:
            score += 1
        if crossover == "golden_cross":
            score += 1
        if snap.rsi_oversold:
            score += 1
        elif snap.rsi < 45:
            score += 0.5
        if snap.macd_bullish_cross:
            score += 1
        if snap.volume_spike:
            score += 1
        if snap.obv_slope > 0:
            score += 0.5
        if snap.rsi_neutral:
            score -= 1

    elif signal == SignalType.SELL:
        if snap.ema_bearish_stack:
            score += 1
        if crossover == "death_cross":
            score += 1
        if snap.rsi_overbought:
            score += 1
        elif snap.rsi > 55:
            score += 0.5
        if snap.macd_bearish_cross:
            score += 1
        if snap.volume_spike:
            score += 1
        if snap.obv_slope < 0:
            score += 0.5
        if snap.rsi_neutral:
            score -= 1

    if not snap.volume_spike:
        score -= 1  # no volume confirmation = lower confidence

    return max(1, min(10, int(score)))


def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    market: MarketType,
) -> Optional[TradeSignal]:
    """
    Analyze OHLCV data and produce a TradeSignal.
    Returns None if indicators are insufficient.
    """
    snap = compute_indicators(df)
    if snap is None:
        return None

    close = df["close"].iloc[-1]
    support, resistance = find_support_resistance(df)
    crossover = detect_ema_crossover(df)
    timeframe = _determine_timeframe(df)
    currency = "$" if market == MarketType.CRYPTO else "₹"

    # ── Determine signal direction ──
    buy_score = 0
    sell_score = 0

    if snap.ema_bullish_stack:
        buy_score += 2
    if snap.ema_bearish_stack:
        sell_score += 2

    if crossover == "golden_cross":
        buy_score += 2
    elif crossover == "death_cross":
        sell_score += 2

    if snap.rsi_oversold:
        buy_score += 2
    elif snap.rsi_overbought:
        sell_score += 2
    elif snap.rsi < 45:
        buy_score += 1
    elif snap.rsi > 55:
        sell_score += 1

    if snap.macd_bullish_cross:
        buy_score += 1.5
    elif snap.macd_bearish_cross:
        sell_score += 1.5

    if snap.obv_slope > 0:
        buy_score += 1
    elif snap.obv_slope < 0:
        sell_score += 1

    if close < snap.bb_lower:
        buy_score += 1
    elif close > snap.bb_upper:
        sell_score += 1

    # Require meaningful edge
    if abs(buy_score - sell_score) < 2:
        signal = SignalType.HOLD
    elif buy_score > sell_score:
        signal = SignalType.BUY
    else:
        signal = SignalType.SELL

    # Skip signals when RSI is in no-man's-land
    if snap.rsi_neutral and signal != SignalType.HOLD:
        signal = SignalType.HOLD

    # ── Calculate levels ──
    atr = snap.atr

    if signal == SignalType.BUY:
        entry_low = _round_price(close - atr * 0.3, market)
        entry_high = _round_price(close + atr * 0.1, market)
        stop_loss = _round_price(close - atr * 1.5, market)
        risk = abs(close - stop_loss)
        target_1 = _round_price(close + risk * MIN_REWARD_RISK_RATIO, market)
        target_2 = _round_price(close + risk * AGGRESSIVE_RR_RATIO, market)
        invalidation = f"Close below {_round_price(stop_loss - atr * 0.2, market)}"

    elif signal == SignalType.SELL:
        entry_low = _round_price(close - atr * 0.1, market)
        entry_high = _round_price(close + atr * 0.3, market)
        stop_loss = _round_price(close + atr * 1.5, market)
        risk = abs(stop_loss - close)
        target_1 = _round_price(close - risk * MIN_REWARD_RISK_RATIO, market)
        target_2 = _round_price(close - risk * AGGRESSIVE_RR_RATIO, market)
        invalidation = f"Close above {_round_price(stop_loss + atr * 0.2, market)}"

    else:  # HOLD
        entry_low = _round_price(close - atr * 0.2, market)
        entry_high = _round_price(close + atr * 0.2, market)
        stop_loss = _round_price(close - atr * 2, market)
        target_1 = _round_price(close + atr, market)
        target_2 = _round_price(close + atr * 2, market)
        invalidation = (
            f"Breakout above {_round_price(resistance, market)} or "
            f"breakdown below {_round_price(support, market)}"
        )

    confidence = _compute_confidence(snap, crossover, signal)
    technicals, fundamental = _build_reasoning(
        snap, crossover, signal, support, resistance
    )

    risk_notes = []
    if not snap.volume_spike:
        risk_notes.append("No volume confirmation — lower conviction")
    if snap.bb_squeeze:
        risk_notes.append("Bollinger Band squeeze — expect sharp move, trail stops tight")

    return TradeSignal(
        asset=symbol,
        market=market,
        signal=signal,
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        timeframe=timeframe,
        confidence=confidence,
        invalidation=invalidation,
        reasoning_technical=technicals,
        reasoning_fundamental=fundamental,
        risk_notes=risk_notes,
        currency_symbol=currency,
    )
