"""
Data fetching layer for Indian equities (via yfinance) and crypto (via public APIs).
Crypto default: Binance public klines. Optional: ZebPay Spot (INR) via CRYPTO_DATA_SOURCE=zebpay.
"""

import os
from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from config import MarketType


def fetch_equity_data(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for an NSE/BSE stock.
    Appends .NS for NSE symbols if not already present.
    """
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            print(f"  ⚠ {symbol}: yfinance returned empty DataFrame")
            return None
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=str.lower)
        return df
    except Exception as e:
        print(f"  ❌ {symbol}: yfinance error: {e}")
        return None


def fetch_crypto_data(
    symbol: str = "BTCUSDT",
    interval: str = "1d",
    limit: int = 200,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV: Binance public API by default, or ZebPay Spot if CRYPTO_DATA_SOURCE=zebpay.
    """
    source = os.environ.get("CRYPTO_DATA_SOURCE", "binance").lower().strip()
    if source == "zebpay":
        from zebpay_client import fetch_zebpay_klines

        df_z = fetch_zebpay_klines(symbol, interval=interval, limit=limit)
        if df_z is not None and not df_z.empty:
            return df_z
        fallback_ok = os.environ.get("ZEBPAY_FALLBACK_BINANCE", "1").lower() in (
            "1",
            "true",
            "yes",
        )
        if not fallback_ok:
            return None

    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        print(f"  ❌ {symbol}: Binance API error: {e}")
        return None

    # DEBUG: Print first row to verify data
    if raw and len(raw) > 0:
        print(f"  📊 {symbol}: First kline: open={raw[0][1]}, close={raw[0][4]}")

    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    df = df[["open", "high", "low", "close", "volume"]]
    return df


def fetch_btc_dominance() -> Optional[float]:
    """Return BTC dominance percentage from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/global"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data["data"]["market_cap_percentage"].get("btc")
    except Exception:
        return None


def fetch_fear_greed_index() -> Optional[int]:
    """Crypto Fear & Greed Index (0-100)."""
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return int(data["data"][0]["value"])
    except Exception:
        return None


def fetch_gift_nifty_gap() -> Optional[float]:
    """
    Approximate pre-market gap by comparing previous Nifty close
    to the latest available GIFT Nifty indication.
    Returns gap as a fraction (e.g. 0.012 = 1.2%).
    Falls back to 0.0 if data is unavailable.
    """
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d")
        if hist.empty or len(hist) < 2:
            return 0.0
        prev_close = hist["Close"].iloc[-2]
        current = hist["Close"].iloc[-1]
        return abs(current - prev_close) / prev_close
    except Exception:
        return 0.0


def fetch_data(
    symbol: str,
    market: MarketType,
    period: str = "3mo",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """Unified fetch dispatcher."""
    if market == MarketType.INDIA_EQUITY:
        return fetch_equity_data(symbol, period=period, interval=interval)
    elif market == MarketType.CRYPTO:
        interval_map = {
            "1d": "1d", "1h": "1h", "4h": "4h",
            "15m": "15m", "5m": "5m", "1wk": "1w",
        }
        binance_interval = interval_map.get(interval, "1d")
        return fetch_crypto_data(symbol, interval=binance_interval)
    return None
