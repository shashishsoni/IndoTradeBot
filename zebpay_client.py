"""
Optional ZebPay Spot public API (no API keys) for INR crypto OHLCV.

Docs: https://apidocs.zebpay.com/ — Spot base https://sapi.zebpay.com (v2)
Reference: https://github.com/zebpay/zebpay-api-references

API prices in klines/ticker are in INR (e.g. BTC-INR close ~8,000,000+), not USDT.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

ZEBPAY_SPOT_BASE = os.environ.get("ZEBPAY_SPOT_BASE", "https://sapi.zebpay.com").rstrip("/")

# Maps: BTCUSDT -> BTC-INR, BTC -> BTC-INR (extend via exchangeInfo)
_DEFAULT_MAP: Dict[str, str] = {
    "BTCUSDT": "BTC-INR",
    "ETHUSDT": "ETH-INR",
    "BNBUSDT": "BNB-INR",
    "BCHUSDT": "BCH-INR",
    "BATUSDT": "BAT-INR",
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
    "BTC": "BTC-INR",
    "ETH": "ETH-INR",
    "BNB": "BNB-INR",
    "BCH": "BCH-INR",
    "BAT": "BAT-INR",
    "SOL": "SOL-INR",
    "XRP": "XRP-INR",
    "ADA": "ADA-INR",
}

_DEFAULT_QUOTE = os.environ.get("ZEBPAY_QUOTE", "INR").upper()

# Cached raw symbol rows from exchangeInfo (shared by INR + QuickTrade helpers)
_exchange_symbols_cache: Optional[List[dict]] = None


def _get_exchange_symbols(timeout: int = 20) -> List[dict]:
    global _exchange_symbols_cache
    if _exchange_symbols_cache is not None:
        return _exchange_symbols_cache

    url = f"{ZEBPAY_SPOT_BASE}/api/v2/ex/exchangeInfo"
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data") or {}
        symbols = data.get("symbols") or []
    except Exception:
        return []

    _exchange_symbols_cache = symbols
    return symbols


def fetch_zebpay_inr_base_assets(timeout: int = 20) -> List[str]:
    """
    GET /api/v2/ex/exchangeInfo — all symbols with quote INR and status Open.
    Returns sorted unique base symbols (e.g. BTC, ETH).
    """
    symbols = _get_exchange_symbols(timeout)
    if not symbols:
        return []

    bases: set = set()
    for s in symbols:
        if (s.get("status") or "").upper() != "OPEN":
            continue
        if (s.get("quoteAsset") or "").upper() != "INR":
            continue
        b = s.get("baseAsset")
        if b:
            bases.add(str(b).upper())

    return sorted(bases)


def fetch_zebpay_quicktrade_bases(timeout: int = 20) -> List[str]:
    """
    Bases for **Open** INR pairs that list **MARKET** in `orderTypes`.

    ZebPay’s public `exchangeInfo` does not expose a `quickTrade` flag; the app’s
    QuickTrade flow uses instant execution, which aligns with **MARKET**-enabled
    pairs on Spot. Use this as the default crypto watchlist when you want
    symbols that match QuickTrade-style trading.
    """
    symbols = _get_exchange_symbols(timeout)
    if not symbols:
        return []

    bases: set = set()
    for s in symbols:
        if (s.get("status") or "").upper() != "OPEN":
            continue
        if (s.get("quoteAsset") or "").upper() != "INR":
            continue
        ots = s.get("orderTypes") or []
        if "MARKET" not in ots:
            continue
        b = s.get("baseAsset")
        if b:
            bases.add(str(b).upper())

    return sorted(bases)


# ZebPay app **Xpress** (INR) — public API has no `xpress` flag; this list matches
# the Xpress / “Xpress coin” INR row in the app. Intersected with Open INR pairs.
# Override entirely: ZEBPAY_XPRESS_SYMBOLS=TURBO,PEPE,SHIB
ZEBPAY_XPRESS_DEFAULT_BASES: tuple[str, ...] = (
    "TURBO",
    "MBL",
    "PYBOBO",
    "SLP",
    "MEW",
    "MEME",
    "HOT",
    "1000CHEEMS",
    "BOME",
    "1MBABYDOGE",
    "NOT",
    "DENT",
    "TOSHI",
    "SPELL",
    "HMSTR",
    "MEMEFI",
    "NEIRO",
    "FLOKI",
    "DOGS",
    "WIN",
    "X",
    "XEC",
    "BONK",
    "SHIB",
    "PEPE",
    "BTTC",
    "MOG",
    "ELON",
)


def fetch_zebpay_xpress_bases(timeout: int = 20) -> List[str]:
    """
    Curated Xpress INR bases. Only symbols that exist as Open INR in exchangeInfo
    are returned (preserves app list order). If exchangeInfo fails, returns the
    raw wanted list so callers can still try klines.
    """
    raw = os.environ.get("ZEBPAY_XPRESS_SYMBOLS", "").strip()
    if raw:
        wanted = [x.strip().upper() for x in raw.split(",") if x.strip()]
    else:
        wanted = list(ZEBPAY_XPRESS_DEFAULT_BASES)

    open_inr = set(fetch_zebpay_inr_base_assets(timeout))
    if not open_inr:
        return wanted

    filtered = [b for b in wanted if b in open_inr]
    return filtered if filtered else wanted


def fetch_zebpay_xpress_merged_bases(timeout: int = 20) -> List[str]:
    """
    Xpress curated list (intersected with Open INR) + QuickTrade MARKET pairs,
    deduped — Xpress order first, then remaining MARKET bases (e.g. BTC, ETH).
    """
    xp = fetch_zebpay_xpress_bases(timeout)
    qt = fetch_zebpay_quicktrade_bases(timeout)
    seen: set[str] = set()
    out: List[str] = []
    for b in xp + qt:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def resolve_crypto_watchlist(timeout: int = 20) -> Tuple[List[str], Dict[str, Any]]:
    """
    Single source of truth for crypto watchlist + diagnostics (CLI, Telegram, web UI).

    Returns:
        (symbols_to_scan, diagnostics_dict)
    """
    raw = os.environ.get("CRYPTO_WATCHLIST", "").strip()
    mode = os.environ.get("CRYPTO_WATCHLIST_MODE", "xpress").lower().strip()
    default_max = "120" if mode == "xpress" else "40"
    max_n = max(5, min(300, int(os.environ.get("CRYPTO_WATCHLIST_MAX", default_max))))

    quote = os.environ.get("ZEBPAY_QUOTE", "INR").upper()

    diag: Dict[str, Any] = {
        "data_source": "ZebPay Spot · INR (public klines)",
        "quote_asset": quote,
        "mode": mode,
        "max_cap": max_n,
    }

    if raw:
        syms = [x.strip().upper() for x in raw.split(",") if x.strip()]
        out = syms[:max_n]
        diag["source"] = "CRYPTO_WATCHLIST"
        diag["symbols"] = out
        diag["note"] = "Explicit CRYPTO_WATCHLIST — no Xpress merge."
        return out, diag

    raw_xp = os.environ.get("ZEBPAY_XPRESS_SYMBOLS", "").strip()
    if raw_xp:
        xpress_wanted = [x.strip().upper() for x in raw_xp.split(",") if x.strip()]
    else:
        xpress_wanted = list(ZEBPAY_XPRESS_DEFAULT_BASES)

    try:
        open_inr = fetch_zebpay_inr_base_assets(timeout)
        xpress_matched = fetch_zebpay_xpress_bases(timeout)
        qt = fetch_zebpay_quicktrade_bases(timeout)
        merged = fetch_zebpay_xpress_merged_bases(timeout)

        oset = set(open_inr) if open_inr else set()
        missing = [b for b in xpress_wanted if oset and b not in oset]

        diag["counts"] = {
            "xpress_configured": len(xpress_wanted),
            "xpress_matched_open_inr": len(xpress_matched),
            "quicktrade_market": len(qt),
            "merged_before_cap": len(merged),
            "open_inr_pairs": len(open_inr),
        }
        diag["xpress_not_on_exchange_api"] = missing
        diag["xpress_not_on_exchange_count"] = len(missing)

        bases: Optional[List[str]] = None
        if mode == "all":
            bases = fetch_zebpay_inr_base_assets(timeout)
        elif mode == "quicktrade":
            bases = fetch_zebpay_quicktrade_bases(timeout)
            if not bases:
                bases = fetch_zebpay_inr_base_assets(timeout)
        else:
            bases = merged
            if not bases:
                bases = fetch_zebpay_quicktrade_bases(timeout)
            if not bases:
                bases = fetch_zebpay_inr_base_assets(timeout)

        if bases:
            final = bases[:max_n]
            diag["source"] = "zebpay"
            diag["symbols"] = final
            diag["truncated_by_cap"] = len(bases) > max_n
            diag["counts"]["after_cap"] = len(final)
            return final, diag
    except Exception as e:
        diag["api_error"] = str(e)

    fb = ["BAT", "BCH", "BTC", "ETH", "LTC", "SOL", "XRP"]
    out = fb[:max_n]
    diag["source"] = "fallback"
    diag["symbols"] = out
    diag["note"] = "exchangeInfo/merge failed — static QuickTrade-style list"
    return out, diag


# Map short Xpress names → exchange baseAsset (ZebPay often uses 1000* for meme units)
_base_resolve_cache: Dict[str, str] = {}

# When both BASE and 1000BASE exist on Open INR, prefer 1000* (matches ZebPay app rows).
_MEME_PREFER_1000: frozenset[str] = frozenset(
    {
        "BONK",
        "PEPE",
        "SHIB",
        "FLOKI",
        "NEIRO",
        "MEME",
        "MEW",
        "DOGS",
        "TURBO",
        "ELON",
        "MOG",
        "HMSTR",
        "MEMEFI",
        "WIN",
        "SLP",
        "HOT",
        "XEC",
        "DENT",
        "NOT",
        "BTTC",
        "CHEEMS",
        "RATS",
        "SATS",
        "LUNC",
        "BABYDOGE",
    }
)


def resolve_open_inr_base_asset(watchlist_base: str) -> str:
    """
    Map watchlist base (e.g. BONK) to exchange Open INR baseAsset (often 1000BONK).

    The app UI may show "BONK" while the API pair is 1000BONK-INR — without this,
    klines/ticker can return empty or near-zero series and reports show ₹0.00.

    Also: if both PEPE and 1000PEPE exist, prefer 1000PEPE for meme names (same as app).
    """
    w = watchlist_base.upper().strip()
    if not w:
        return w
    if w in _base_resolve_cache:
        return _base_resolve_cache[w]

    open_bases = set(fetch_zebpay_inr_base_assets())
    if not open_bases:
        _base_resolve_cache[w] = w
        return w

    # 1) Meme: prefer 1000* when listed (even if short name also exists — avoids ₹0.00)
    if w in _MEME_PREFER_1000:
        k1000 = f"1000{w}"
        if k1000 in open_bases:
            _base_resolve_cache[w] = k1000
            return k1000

    # 2) Exact match (already scaled like 1000BONK, 1MBABYDOGE, or BTC)
    if w in open_bases:
        _base_resolve_cache[w] = w
        return w

    # 3) Prefix fallbacks for any short name
    for prefix in ("1000", "1M", "1000000"):
        cand = f"{prefix}{w}"
        if cand in open_bases:
            _base_resolve_cache[w] = cand
            return cand

    # 4) Strip leading 1000 if API uses short base only
    if w.startswith("1000") and len(w) > 4:
        short = w[4:]
        if short in open_bases:
            _base_resolve_cache[w] = short
            return short

    _base_resolve_cache[w] = w
    return w


def format_zebpay_inr_price(value: float) -> str:
    """
    Human-readable INR for ZebPay quotes — avoids ₹0.00 when price is sub-paisa
    (common for meme pairs quoted per small unit).
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "₹—"
    if v != v:  # NaN
        return "₹—"
    if v >= 1e7:
        return f"₹{v / 1e7:.2f}Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.2f}L"
    if v >= 1000:
        return f"₹{v:,.0f}"
    if v >= 1:
        return f"₹{v:,.2f}"
    if v >= 0.01:
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return f"₹{s}"
    if v > 0:
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        return f"₹{s}"
    return "₹0"


def format_trade_price_line(currency_symbol: str, value: float) -> str:
    """Single price for reports (₹ uses adaptive precision)."""
    if currency_symbol == "₹":
        return format_zebpay_inr_price(value)
    return f"{currency_symbol}{value:,.2f}"


def format_crypto_watchlist_summary(diag: Dict[str, Any]) -> str:
    """One line for console / report footer."""
    if diag.get("source") == "CRYPTO_WATCHLIST":
        return (
            f"CRYPTO_WATCHLIST · {len(diag.get('symbols', []))} syms · cap {diag.get('max_cap')}"
        )
    if diag.get("source") == "fallback":
        return f"⚠️ fallback · {diag.get('note', '')}"
    syms = diag.get("symbols") or []
    cnt = diag.get("counts") or {}
    miss = int(diag.get("xpress_not_on_exchange_count") or 0)
    parts = [
        f"{diag.get('mode')} · cap {diag.get('max_cap')} · {len(syms)} syms",
        f"Xpress∩API {cnt.get('xpress_matched_open_inr', '?')}/{cnt.get('xpress_configured', '?')}",
        f"QuickTrade MARKET {cnt.get('quicktrade_market', '?')}",
    ]
    if miss:
        parts.append(f"{miss} Xpress names not Open INR on API (omitted)")
    return " · ".join(parts)


def watchlist_symbol_to_zebpay(symbol: str) -> str:
    """Map watchlist symbol (BTCUSDT or BTC) to ZebPay pair (BTC-INR)."""
    s = symbol.upper().strip()

    if s in _DEFAULT_MAP.values():
        return s

    if s in _DEFAULT_MAP:
        return _DEFAULT_MAP[s]

    if s.endswith("USDT"):
        base = s[:-4]
        if base + "USDT" in _DEFAULT_MAP:
            return _DEFAULT_MAP[base + "USDT"]
        rb = resolve_open_inr_base_asset(base)
        return f"{rb}-{_DEFAULT_QUOTE}"

    # Bare base: BTC -> BTC-INR (or 1000BONK-INR when API uses scaled contract)
    rb = resolve_open_inr_base_asset(s)
    return f"{rb}-{_DEFAULT_QUOTE}"


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
    Fetch OHLCV from ZebPay Spot GET /api/v2/market/klines.
    Prices are kept in INR (as returned by the API).
    """
    zeb_pair = watchlist_symbol_to_zebpay(symbol)
    zeb_iv = _INTERVAL_MAP.get(interval, "1d")
    sec = _seconds_per_zebpay_candle(zeb_iv)

    span_mult = 7 if interval == "1w" else 1
    n = max(10, min(500, limit * span_mult))

    end = int(time.time())
    start = end - sec * n

    url = f"{ZEBPAY_SPOT_BASE}/api/v2/market/klines"

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


def fetch_zebpay_ticker(symbol: str) -> Optional[Dict]:
    """Ticker prices in INR."""
    zeb_pair = watchlist_symbol_to_zebpay(symbol)
    url = f"{ZEBPAY_SPOT_BASE}/api/v2/market/ticker"
    params = {"symbol": zeb_pair}

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        ticker = data.get("data", {}) or {}

        def fget(key: str) -> float:
            v = ticker.get(key)
            if v is None or v == "":
                return 0.0
            return float(v)

        return {
            "symbol": symbol,
            "bid": fget("bid"),
            "ask": fget("ask"),
            "last": fget("last"),
            "volume_24h": fget("baseVolume"),
            "high_24h": fget("high"),
            "low_24h": fget("low"),
            "change_24h": fget("percentage"),
            "source": "zebpay_inr",
        }
    except Exception:
        return None


def get_zebpay_supported_pairs() -> List[str]:
    """Legacy: keys in default map."""
    return list(_DEFAULT_MAP.keys())


def is_zebpay_supported(symbol: str) -> bool:
    return symbol.upper() in _DEFAULT_MAP
