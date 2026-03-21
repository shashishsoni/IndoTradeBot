"""
Central configuration for the Trading Signal Analyzer.
All thresholds, timing windows, and risk parameters live here.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class MarketType(Enum):
    INDIA_EQUITY = "india_equity"
    CRYPTO = "crypto"


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Timeframe(Enum):
    SCALP = "Scalp (5-15 min)"
    INTRADAY = "Intraday"
    SWING = "Swing (3-10 days)"
    POSITIONAL = "Positional"


class Confidence(Enum):
    LOW = 3
    MEDIUM = 6
    HIGH = 8


# ── Indian Equity Timing ──────────────────────────────────────────────

INDIA_MARKET_OPEN = (9, 15)       # 9:15 AM IST
INDIA_MARKET_CLOSE = (15, 30)     # 3:30 PM IST
INDIA_AVOID_OPEN_MINUTES = 15     # skip first 15 min
INDIA_EVENT_BUFFER_MINUTES = 30   # avoid 30 min before major events

INDIA_BEST_WINDOWS = [
    ((9, 30), (11, 30)),   # morning session
    ((13, 30), (15, 0)),   # afternoon session
]

# ── Crypto Timing (IST) ──────────────────────────────────────────────

CRYPTO_HIGH_VOL_WINDOWS = [
    ((21, 30), (4, 0)),    # US market hours
    ((5, 30), (8, 30)),    # Asian open
]

CRYPTO_LOW_LIQUIDITY = ((2, 0), (5, 0))

# ── Technical Indicator Params ────────────────────────────────────────

EMA_PERIODS = (20, 50, 200)
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_NEUTRAL_ZONE = (45, 55)
ATR_PERIOD = 14
MACD_PARAMS = (12, 26, 9)  # fast, slow, signal
BB_PERIOD = 20
BB_STD = 2

# ── Risk Management ──────────────────────────────────────────────────

MAX_RISK_PER_TRADE = 0.02          # 2% of capital
MAX_SIMULTANEOUS_SIGNALS = 3
CONSECUTIVE_LOSS_THRESHOLD = 3     # enter review mode
MAX_DRAWDOWN_HALT = 0.10           # 10% drawdown halts signals
MIN_REWARD_RISK_RATIO = 1.5        # conservative target
AGGRESSIVE_RR_RATIO = 2.5          # target 2 when trend confirmed

# ── India-Specific Filters ───────────────────────────────────────────

MIN_EQUITY_VOLUME = 500_000        # 5 lakh shares/day
GIFT_NIFTY_GAP_THRESHOLD = 0.015   # 1.5% gap → halve position
POST_EARNINGS_WAIT_SESSIONS = 2

# ── Crypto-Specific Filters ─────────────────────────────────────────

CRYPTO_MIN_AGE_MONTHS = 6
CRYPTO_MIN_24H_VOLUME = 50_000_000  # $50M
BTC_DOMINANCE_HIGH = 55             # prefer BTC/ETH
BTC_DOMINANCE_LOW = 45              # altcoin season
FEAR_GREED_EXTREME_FEAR = 20
FEAR_GREED_EXTREME_GREED = 80
MAX_LEVERAGE_RETAIL = 3


@dataclass
class TradeSignal:
    asset: str
    market: MarketType
    signal: SignalType
    entry_low: float
    entry_high: float
    stop_loss: float
    target_1: float
    target_2: float
    timeframe: Timeframe
    confidence: int                   # 1-10 scale
    invalidation: str
    reasoning_technical: List[str] = field(default_factory=list)
    reasoning_fundamental: str = ""
    risk_notes: List[str] = field(default_factory=list)
    currency_symbol: str = "₹"

    @property
    def entry_mid(self) -> float:
        return (self.entry_low + self.entry_high) / 2

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry_mid - self.stop_loss)

    @property
    def reward_t1(self) -> float:
        return abs(self.target_1 - self.entry_mid)

    @property
    def reward_t2(self) -> float:
        return abs(self.target_2 - self.entry_mid)

    @property
    def rr_t1(self) -> float:
        if self.risk_per_unit == 0:
            return 0
        return round(self.reward_t1 / self.risk_per_unit, 2)

    @property
    def rr_t2(self) -> float:
        if self.risk_per_unit == 0:
            return 0
        return round(self.reward_t2 / self.risk_per_unit, 2)

    @property
    def risk_pct(self) -> float:
        if self.entry_mid == 0:
            return 0
        return round(abs(self.entry_mid - self.stop_loss) / self.entry_mid * 100, 2)
