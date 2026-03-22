"""
Data fetching layer for Indian equities (via yfinance) and crypto (ZebPay Spot INR).
"""

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
    OHLCV from ZebPay Spot (INR). All prices are in rupees.
    """
    from zebpay_client import fetch_zebpay_klines

    df = fetch_zebpay_klines(symbol, interval=interval, limit=limit)
    if df is not None and not df.empty:
        return df

    print(f"  ⚠ {symbol}: ZebPay unavailable — no data")
    return None


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
    if market == MarketType.CRYPTO:
        interval_map = {
            "1d": "1d",
            "1h": "1h",
            "4h": "4h",
            "15m": "15m",
            "5m": "5m",
            "1wk": "1w",
        }
        zeb_interval = interval_map.get(interval, "1d")
        return fetch_crypto_data(symbol, interval=zeb_interval)
    return None
