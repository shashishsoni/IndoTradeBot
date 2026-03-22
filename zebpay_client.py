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
    """Map watchlist symbol (BTCUSDT) to ZebPay pair (BTC-INR)."""
    s = symbol.upper().strip()
    if s in _DEFAULT_MAP:
        return _DEFAULT_MAP[s]
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}-{_DEFAULT_QUOTE}"
    return s.replace("_", "-")


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

        df = _parse_klines_payload(data)
        if df is None or df.empty:
            continue
        if len(df) > limit:
            df = df.tail(limit)
        return df

    return None
