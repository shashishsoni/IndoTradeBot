"""
Technical indicator calculations.
Priority order: EMA crossovers → RSI → OBV/Volume → ATR/BB → MACD → S/R levels.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import ta

from config import (
    ATR_PERIOD,
    BB_PERIOD,
    BB_STD,
    EMA_PERIODS,
    MACD_PARAMS,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_NEUTRAL_ZONE,
    RSI_PERIOD,
)


@dataclass
class IndicatorSnapshot:
    """All indicators for the latest bar."""
    ema_20: float
    ema_50: float
    ema_200: float
    rsi: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_width: float
    atr: float
    obv: float
    obv_slope: float       # positive = accumulation
    volume_current: float
    volume_avg_20: float
    prev_day_high: float
    prev_day_low: float

    @property
    def ema_bullish_stack(self) -> bool:
        """Price > EMA20 > EMA50 > EMA200"""
        return self.ema_20 > self.ema_50 > self.ema_200

    @property
    def ema_bearish_stack(self) -> bool:
        return self.ema_20 < self.ema_50 < self.ema_200

    @property
    def rsi_oversold(self) -> bool:
        return self.rsi < RSI_OVERSOLD

    @property
    def rsi_overbought(self) -> bool:
        return self.rsi > RSI_OVERBOUGHT

    @property
    def rsi_neutral(self) -> bool:
        return RSI_NEUTRAL_ZONE[0] <= self.rsi <= RSI_NEUTRAL_ZONE[1]

    @property
    def macd_bullish_cross(self) -> bool:
        return self.macd_line > self.macd_signal and self.macd_hist > 0

    @property
    def macd_bearish_cross(self) -> bool:
        return self.macd_line < self.macd_signal and self.macd_hist < 0

    @property
    def volume_spike(self) -> bool:
        if self.volume_avg_20 == 0:
            return False
        return self.volume_current > 1.5 * self.volume_avg_20

    @property
    def bb_squeeze(self) -> bool:
        return self.bb_width < 0.04  # tight bands


def compute_indicators(df: pd.DataFrame) -> Optional[IndicatorSnapshot]:
    """
    Compute all indicators from an OHLCV DataFrame.
    Expects lowercase columns: open, high, low, close, volume.
    """
    if df is None or len(df) < 200:
        if df is not None and len(df) >= 50:
            pass  # proceed with what we have
        else:
            return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    ema_20 = ta.trend.ema_indicator(close, window=EMA_PERIODS[0])
    ema_50 = ta.trend.ema_indicator(close, window=EMA_PERIODS[1])

    if len(df) >= 200:
        ema_200 = ta.trend.ema_indicator(close, window=EMA_PERIODS[2])
        ema_200_val = ema_200.iloc[-1]
    else:
        ema_200_val = ema_50.iloc[-1]

    rsi = ta.momentum.rsi(close, window=RSI_PERIOD)

    macd = ta.trend.MACD(
        close,
        window_slow=MACD_PARAMS[1],
        window_fast=MACD_PARAMS[0],
        window_sign=MACD_PARAMS[2],
    )

    bb = ta.volatility.BollingerBands(
        close, window=BB_PERIOD, window_dev=BB_STD
    )

    atr_indicator = ta.volatility.AverageTrueRange(
        high, low, close, window=ATR_PERIOD
    )

    obv_series = ta.volume.on_balance_volume(close, volume)
    obv_slope = obv_series.iloc[-1] - obv_series.iloc[-5] if len(obv_series) >= 5 else 0

    vol_avg_20 = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else volume.mean()

    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid != 0 else 0

    prev_idx = -2 if len(df) >= 2 else -1

    return IndicatorSnapshot(
        ema_20=ema_20.iloc[-1],
        ema_50=ema_50.iloc[-1],
        ema_200=ema_200_val,
        rsi=rsi.iloc[-1],
        macd_line=macd.macd().iloc[-1],
        macd_signal=macd.macd_signal().iloc[-1],
        macd_hist=macd.macd_diff().iloc[-1],
        bb_upper=bb_upper,
        bb_middle=bb_mid,
        bb_lower=bb_lower,
        bb_width=bb_width,
        atr=atr_indicator.average_true_range().iloc[-1],
        obv=obv_series.iloc[-1],
        obv_slope=obv_slope,
        volume_current=volume.iloc[-1],
        volume_avg_20=vol_avg_20,
        prev_day_high=high.iloc[prev_idx],
        prev_day_low=low.iloc[prev_idx],
    )


def find_support_resistance(
    df: pd.DataFrame, lookback: int = 20
) -> Tuple[float, float]:
    """
    Simple S/R from recent swing highs/lows.
    Returns (support, resistance).
    """
    recent = df.tail(lookback)
    support = recent["low"].min()
    resistance = recent["high"].max()
    return support, resistance


def detect_ema_crossover(df: pd.DataFrame) -> Optional[str]:
    """
    Detect if an EMA 20/50 crossover just occurred (within last 3 bars).
    Returns 'golden_cross', 'death_cross', or None.
    """
    close = df["close"]
    ema_20 = ta.trend.ema_indicator(close, window=20)
    ema_50 = ta.trend.ema_indicator(close, window=50)

    for i in range(-3, 0):
        if i - 1 < -len(ema_20):
            continue
        prev_diff = ema_20.iloc[i - 1] - ema_50.iloc[i - 1]
        curr_diff = ema_20.iloc[i] - ema_50.iloc[i]
        if prev_diff < 0 and curr_diff > 0:
            return "golden_cross"
        if prev_diff > 0 and curr_diff < 0:
            return "death_cross"
    return None
