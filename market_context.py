"""
Market context awareness: timing windows, event buffers, and market-specific filters.
"""

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from zoneinfo import ZoneInfo

from config import (
    BTC_DOMINANCE_HIGH,
    BTC_DOMINANCE_LOW,
    CRYPTO_LOW_LIQUIDITY,
    CRYPTO_MIN_24H_VOLUME,
    CRYPTO_MIN_AGE_MONTHS,
    FEAR_GREED_EXTREME_FEAR,
    FEAR_GREED_EXTREME_GREED,
    GIFT_NIFTY_GAP_THRESHOLD,
    INDIA_AVOID_OPEN_MINUTES,
    INDIA_BEST_WINDOWS,
    INDIA_MARKET_CLOSE,
    INDIA_MARKET_OPEN,
    MAX_LEVERAGE_RETAIL,
    MIN_EQUITY_VOLUME,
    MarketType,
)

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class MarketContextReport:
    market: MarketType
    timestamp: datetime.datetime
    is_market_open: bool = False
    in_best_window: bool = False
    warnings: List[str] = field(default_factory=list)
    position_size_modifier: float = 1.0  # 1.0 = full, 0.5 = halved
    should_skip: bool = False
    skip_reason: str = ""


def _time_tuple(dt: datetime.datetime):
    return (dt.hour, dt.minute)


def _in_range(now_tuple, start_tuple, end_tuple) -> bool:
    """Check if time is in range, handling overnight wraps."""
    if start_tuple <= end_tuple:
        return start_tuple <= now_tuple <= end_tuple
    return now_tuple >= start_tuple or now_tuple <= end_tuple


def get_india_context(
    now: Optional[datetime.datetime] = None,
    gift_nifty_gap: float = 0.0,
    is_fno_expiry: bool = False,
    is_friday_afternoon: bool = False,
    stock_volume: Optional[float] = None,
    in_fno_ban: bool = False,
    post_earnings_sessions: int = 999,
) -> MarketContextReport:
    if now is None:
        now = datetime.datetime.now(IST)

    report = MarketContextReport(
        market=MarketType.INDIA_EQUITY, timestamp=now
    )

    now_t = _time_tuple(now)
    open_t = INDIA_MARKET_OPEN
    close_t = INDIA_MARKET_CLOSE

    if now.weekday() >= 5:
        report.should_skip = True
        report.skip_reason = "Weekend — Indian markets closed"
        return report

    if open_t <= now_t <= close_t:
        report.is_market_open = True
    else:
        report.should_skip = True
        report.skip_reason = "Outside NSE/BSE trading hours (9:15 AM – 3:30 PM IST)"
        return report

    avoid_until = (
        INDIA_MARKET_OPEN[0],
        INDIA_MARKET_OPEN[1] + INDIA_AVOID_OPEN_MINUTES,
    )
    if now_t < avoid_until:
        report.warnings.append(
            "First 15 minutes — price discovery phase, high volatility"
        )

    for start, end in INDIA_BEST_WINDOWS:
        if _in_range(now_t, start, end):
            report.in_best_window = True
            break

    if gift_nifty_gap > GIFT_NIFTY_GAP_THRESHOLD:
        report.position_size_modifier = 0.5
        report.warnings.append(
            f"GIFT Nifty gap {gift_nifty_gap:.1%} > 1.5% — position size halved"
        )

    if is_fno_expiry:
        report.warnings.append(
            "F&O expiry day — heightened volatility, wider stop losses recommended"
        )

    if is_friday_afternoon and now_t >= (14, 0):
        report.warnings.append(
            "Friday afternoon — weekend gap risk. Consider closing intraday positions"
        )

    if stock_volume is not None and stock_volume < MIN_EQUITY_VOLUME:
        report.should_skip = True
        report.skip_reason = (
            f"Volume {stock_volume:,.0f} < 5 lakh shares — manipulation risk"
        )
        return report

    if in_fno_ban:
        report.should_skip = True
        report.skip_reason = "Stock is in F&O ban — no fresh positions"
        return report

    if post_earnings_sessions < 2:
        report.should_skip = True
        report.skip_reason = (
            f"Only {post_earnings_sessions} session(s) since earnings — "
            "wait 2 full sessions"
        )
        return report

    return report


def get_crypto_context(
    now: Optional[datetime.datetime] = None,
    btc_dominance: Optional[float] = None,
    fear_greed: Optional[int] = None,
    token_age_months: int = 12,
    volume_24h: float = 100_000_000,
    funding_rate: Optional[float] = None,
) -> MarketContextReport:
    if now is None:
        now = datetime.datetime.now(IST)

    report = MarketContextReport(market=MarketType.CRYPTO, timestamp=now)
    report.is_market_open = True  # crypto is 24/7

    now_t = _time_tuple(now)

    if _in_range(now_t, CRYPTO_LOW_LIQUIDITY[0], CRYPTO_LOW_LIQUIDITY[1]):
        report.warnings.append(
            "Low-liquidity window (2:00–5:00 AM IST) — spreads widen, use limit orders"
        )

    us_start, us_end = (21, 30), (4, 0)
    asia_start, asia_end = (5, 30), (8, 30)
    if _in_range(now_t, us_start, us_end):
        report.in_best_window = True
        report.warnings.append("US market hours — high volatility expected")
    elif _in_range(now_t, asia_start, asia_end):
        report.in_best_window = True

    if btc_dominance is not None:
        if btc_dominance > BTC_DOMINANCE_HIGH:
            report.warnings.append(
                f"BTC dominance {btc_dominance:.1f}% > 55% — prefer BTC/ETH over altcoins"
            )
        elif btc_dominance < BTC_DOMINANCE_LOW:
            report.warnings.append(
                f"BTC dominance {btc_dominance:.1f}% < 45% — altcoin season likely"
            )

    if fear_greed is not None:
        if fear_greed <= FEAR_GREED_EXTREME_FEAR:
            report.warnings.append(
                f"Fear & Greed Index: {fear_greed} — EXTREME FEAR (potential buy zone)"
            )
        elif fear_greed >= FEAR_GREED_EXTREME_GREED:
            report.warnings.append(
                f"Fear & Greed Index: {fear_greed} — EXTREME GREED (reduce exposure)"
            )
            report.position_size_modifier = 0.5

    if token_age_months < CRYPTO_MIN_AGE_MONTHS:
        report.should_skip = True
        report.skip_reason = (
            f"Token age {token_age_months} months < 6 months — rug pull risk"
        )
        return report

    if volume_24h < CRYPTO_MIN_24H_VOLUME:
        report.should_skip = True
        report.skip_reason = (
            f"24h volume ${volume_24h:,.0f} < $50M minimum — insufficient liquidity"
        )
        return report

    if funding_rate is not None:
        if funding_rate < 0:
            report.warnings.append(
                f"Negative funding rate ({funding_rate:.4f}) — bearish sentiment in futures"
            )
        elif funding_rate > 0.01:
            report.warnings.append(
                f"High positive funding rate ({funding_rate:.4f}) — longs paying premium, "
                "potential for long squeeze"
            )

    return report


def is_fno_expiry_day(dt: Optional[datetime.datetime] = None) -> bool:
    """Check if the given date is the last Thursday of the month."""
    if dt is None:
        dt = datetime.datetime.now(IST)

    if dt.weekday() != 3:  # Thursday
        return False

    next_week = dt + datetime.timedelta(days=7)
    return next_week.month != dt.month
