"""
Optional ZebPay Spot public API (no API keys) for INR / USDT crypto OHLCV.

Docs: https://apidocs.zebpay.com/ — Spot base https://sapi.zebpay.com (v2)
Reference: https://github.com/zebpay/zebpay-api-references
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional

import pandas as pd
import requests

ZEBPAY_SPOT_BASE = os.environ.get("ZEBPAY_SPOT_BASE", "https://sapi.zebpay.com").rstrip("/")

# ZebPay returns prices in PAISA (1/100 of INR)
# Example: 7915800 paisa = ₹79,158 = ~$950 USD
# To convert to INR: divide by 100
# To convert to USD: divide by 100 then by ~83 (exchange rate)
PAISA_TO_INR = 0.01
INR_TO_USD = 0.012  # ~1 INR = 0.012 USD (83 INR = 1 USD)
PAISA_TO_USD = PAISA_TO_INR * INR_TO_USD  # = 0.00012

# ZebPay supported INR pairs (QuickTrade)
# Maps: BTCUSDT -> BTC-INR, BTC -> BTC-INR, etc.
_DEFAULT_MAP: Dict[str, str] = {
    # USDT suffix format
    "BTCUSDT": "BTC-INR",
    "ETHUSDT": "ETH-INR",
    "BNBUSDT": "BNB-INR",
    "SOLUSDT": "SOL-INR",
    "XRPUSDT": "XRP-INR",
    "ADAUSDT": "ADA-INR",
    "DOGEUSDT": "DOGE-INR",
    "DOTUSDT": "DOT-INR",
    "LINKUSDT": "LINK-INR",
    "AVAXUSDT": "AVAX-INR",
    "MATICUSDT": "MATIC-INR",
    "NEARUSDT": "NEAR-INR",
    "ATOMUSDT": "ATOM-INR",
    "LTCUSDT": "LTC-INR",
    "UNIUSDT": "UNI-INR",
    # Also support bare symbol format
    "BTC": "BTC-INR",
    "ETH": "ETH-INR",
    "BNB": "BNB-INR",
    "SOL": "SOL-INR",
    "XRP": "XRP-INR",
    "ADA": "ADA-INR",
}

# Default quote for auto-mapped pairs (BTCUSDT -> BTC-INR)
_DEFAULT_QUOTE = os.environ.get("ZEBPAY_QUOTE", "INR").upper()

_DEFAULT_MAP: Dict[str, str] = {
    "BTCUSDT": "BTC-INR",
    "ETHUSDT": "ETH-INR",
    "BNBUSDT": "BNB-INR",
    "SOLUSDT": "SOL-INR",
    "XRPUSDT": "XRP-INR",
    "ADAUSDT": "ADA-INR",
    "DOGEUSDT": "DOGE-INR",
    "MATICUSDT": "MATIC-INR",
    "DOTUSDT": "DOT-INR",
    "LINKUSDT": "LINK-INR",
}


def binance_symbol_to_zebpay(symbol: str) -> str:
    """Map watchlist symbol (BTCUSDT or BTC) to ZebPay pair (BTC-INR)."""
    s = symbol.upper().strip()
    
    # Handle: BTC, ETH, etc.
    if s in _DEFAULT_MAP.values():
        return s
    
    # Handle: BTCUSDT, ETHUSDT
    if s.endswith("USDT"):
        base = s[:-4]
        if base in _DEFAULT_MAP:
            return _DEFAULT_MAP[base + "USDT"]
        return f"{base}-{_DEFAULT_QUOTE}"
    
    # Handle: BTC -> BTC-INR
    for key, val in _DEFAULT_MAP.items():
        if key.startswith(s):
            return val
    
    return f"{s}-{_DEFAULT_QUOTE}"


# Binance kline interval -> ZebPay interval string
_INTERVAL_MAP = {
    "1m": "1m",
    "3m": "5m",
    "5m": "5m",
    "15m": "15m",
    "30m": "15m",
    "1h": "1h",
    "2h": "4h",
    "4h": "4h",
    "6h": "4h",
    "8h": "4h",
    "12h": "4h",
    "1d": "1d",
    "3d": "1d",
    "1w": "1d",
    "1M": "1d",
}


def _seconds_per_zebpay_candle(zeb_interval: str) -> int:
    return {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }.get(zeb_interval, 86400)


def _parse_klines_payload(data: list) -> Optional[pd.DataFrame]:
    if not data:
        return None
    first_t = data[0][0]
    unit = "ms" if first_t > 1e12 else "s"
    rows = []
    for row in data:
        if len(row) < 7:
            continue
        t_open = row[0]
        ts = pd.to_datetime(t_open, unit=unit)
        rows.append(
            {
                "open_time": ts,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.set_index("open_time").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def fetch_zebpay_klines(
    symbol: str,
    interval: str = "1d",
    limit: int = 200,
    timeout: int = 20,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV from ZebPay Spot public GET /api/v2/market/klines.

    symbol: Binance-style (BTCUSDT) or ZebPay pair (BTC-INR).
    interval: Binance-style interval string (e.g. 1d, 4h).
    """
    zeb_pair = binance_symbol_to_zebpay(symbol)
    zeb_iv = _INTERVAL_MAP.get(interval, "1d")
    sec = _seconds_per_zebpay_candle(zeb_iv)

    span_mult = 7 if interval == "1w" else 1
    n = max(10, min(500, limit * span_mult))

    end = int(time.time())
    start = end - sec * n

    url = f"{ZEBPAY_SPOT_BASE}/api/v2/market/klines"

    # API docs mention ms; some payloads use seconds — try both
    for scale in (1000, 1):
        params = {
            "symbol": zeb_pair,
            "interval": zeb_iv,
            "startTime": start * scale,
            "endTime": end * scale,
        }
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code != 200:
                continue
            payload = r.json()
        except Exception:
            continue

        data = payload.get("data")
        if not data:
            continue

        # DEBUG: Print first row to verify data
        if data and len(data) > 0:
            print(f"  📊 {symbol} (ZebPay INR): First kline: open={data[0][1]}, close={data[0][4]}")

        df = _parse_klines_payload(data)
        if df is None or df.empty:
            continue
        if len(df) > limit:
            df = df.tail(limit)
        
        # ZebPay returns PAISA (1/100 INR) - convert to USD for consistent display
        # Example: 7915800 paisa = ₹79,158 → $950
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col] * PAISA_TO_USD
        # Volume stays the same (it's the token amount)
        
        return df

    return None


def fetch_zebpay_ticker(symbol: str) -> Optional[Dict]:
    """
    Fetch real-time ticker from ZebPay.
    Returns: {bid, ask, last, volume_24h, high_24h, low_24h, change_24h}
    """
    zeb_pair = binance_symbol_to_zebpay(symbol)
    url = f"{ZEBPAY_SPOT_BASE}/api/v2/market/ticker"
    
    params = {"symbol": zeb_pair}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ticker = data.get("data", {})
            
            # ZebPay returns paisa (1/100 INR)
            return {
                "symbol": symbol,
                "bid": float(ticker.get("bid", 0)) * PAISA_TO_USD,
                "ask": float(ticker.get("ask", 0)) * PAISA_TO_USD,
                "last": float(ticker.get("last", 0)) * PAISA_TO_USD,
                "volume_24h": float(ticker.get("volume24h", 0)),
                "high_24h": float(ticker.get("high24h", 0)) * PAISA_TO_USD,
                "low_24h": float(ticker.get("low24h", 0)) * PAISA_TO_USD,
                "change_24h": float(ticker.get("priceChangePercent", 0)),
                "source": "zebpay_inr",
            }
    except Exception as e:
        print(f"  ⚠ {symbol}: ZebPay ticker error: {e}")
    return None


def get_zebpay_supported_pairs() -> List[str]:
    """Return list of supported ZebPay trading pairs."""
    return list(_DEFAULT_MAP.keys())


def is_zebpay_supported(symbol: str) -> bool:
    """Check if symbol is available on ZebPay."""
    return symbol.upper() in _DEFAULT_MAP
