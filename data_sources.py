"""
Indian Market Data Sources - No Binance
Uses: yfinance, nsetools, and other Indian financial APIs
"""

import os
from typing import Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ==================== INDIAN EQUITIES (NSE/BSE) ====================

# Major NSE indices
NSE_INDICES = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY IT": "^NSECOT",
    "NIFTY PHARMA": "^NIPHARM",
    "NIFTY AUTO": "^NIFAUTO",
    "NIFTY METAL": "^NIFMETAL",
    "NIFTY FMCG": "^NFMCG",
    "NIFTY ENERGY": "^NIENERGY",
    "NIFTY REALTY": "^NIFREAL",
}

# Popular NSE stocks
NSE_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
    "BHARTIARTL", "BAJFINANCE", "HINDUNILVR", "ITC", "KOTAKBANK",
    "LT", "M&M", "SUNPHARMA", "TITAN", "ADANIPORTS",
    "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "CIPLA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HEROMOTOCO", "HINDZINC",
    "JSWSTEEL", "MARUTI", "NESTLE", "NTPC", "ONGC",
    "POWERGRID", "SBILIFE", "SHREECEM", "TATASTEEL", "ULTRACEMCO",
    "WIPRO", "ADANIENSOL", "ADANIGREEN", "ADANITRANS", "ZOMATO",
]


def fetch_nse_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """
    Fetch NSE/BSE equity data via yfinance.
    Automatically appends .NS for NSE symbols.
    """
    # Handle special cases
    if symbol.upper() in NSE_INDICES:
        yf_symbol = NSE_INDICES[symbol.upper()]
    else:
        # Add .NS suffix for NSE
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        yf_symbol = f"{clean_sym}.NS"
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=str.lower)
        return df
    except Exception as e:
        print(f"  ❌ {symbol}: NSE fetch error: {e}")
        return None


def fetch_bse_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """Fetch BSE equity data via yfinance."""
    clean_sym = symbol.upper().replace(".BO", "")
    yf_symbol = f"{clean_sym}.BO"
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=str.lower)
        return df
    except Exception as e:
        print(f"  ❌ {symbol}: BSE fetch error: {e}")
        return None


# ==================== INDIAN F&O DATA ====================

FNO_INDICES = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "^NSEI",
    "MIDCAPNIFTY": "^NSEMDCP",
    "NIFTY IT": "^NSECOT",
    "NIFTY PHARMA": "^NIPHARM",
}

# Stock futures (monthly expiry - these are ETF proxies)
STOCK_FUTURES_ETF = {
    "NIFTYBEES": "^NSEI",  # Nifty ETF as proxy
    "GOLDBEES": "GC=F",    # Gold ETF
    "SILVERBEES": "SI=F",   # Silver ETF
}


def fetch_fno_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """
    Fetch Indian F&O index data.
    Note: yfinance provides ETF data as proxy for futures.
    """
    if symbol.upper() in FNO_INDICES:
        yf_symbol = FNO_INDICES[symbol.upper()]
    elif symbol.upper() in STOCK_FUTURES_ETF:
        yf_symbol = STOCK_FUTURES_ETF[symbol.upper()]
    else:
        return None
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval="1d")
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=str.lower)
        return df
    except Exception as e:
        print(f"  ❌ {symbol}: F&O fetch error: {e}")
        return None


# ==================== INDIAN MUTUAL FUNDS ====================

# Popular mutual fund schemes (by scheme code)
MUTUAL_FUNDS = {
    # Large Cap
    "SBI Bluechip Fund": "SBIBEEEQF",
    "HDFC Top 100": "HDFC100G",
    "ICICI Pru Bluechip": "ICICIBLUCH",
    "Nippon India Large Cap": "NIPPONLGC",
    "Mirae Asset Large Cap": "MALCOL",
    # Mid Cap
    "DSP Mid Cap": "DSP212G",
    "Kotak Emerging Equity": "KOTAKEMF",
    "Mid Cap Opportunities": "MIDCAP",
    # Small Cap
    "SBI Small Cap": "SBISMLCAP",
    "Nippon India Small Cap": "NIFTYSMALLCAP",
    # ELSS/Tax Savings
    "Axis Long Term Equity": "AXISLT-EQ",
    "Mirae Asset Tax Saver": "MASTEPE",
    "DSP Tax Saver": "DSPTSAEQ",
    # Hybrid
    "ICICI Pru Balanced Advantage": "ICICIBALA",
    "SBI Balanced Advantage": "SAAMBALA",
}


def fetch_mf_nav(scheme_code: str) -> Optional[Dict]:
    """
    Fetch mutual fund NAV from AMFI India.
    """
    try:
        url = "https://www.amfiindia.com/spages/NAVAll.txt"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        
        for line in resp.text.split("\n"):
            if scheme_code in line:
                parts = line.split(";")
                if len(parts) >= 5:
                    nav = parts[4].strip()
                    return {
                        "scheme": parts[1].strip(),
                        "nav": float(nav) if nav and nav != "NA" else None,
                        "date": parts[5].strip() if len(parts) > 5 else None,
                    }
    except Exception as e:
        print(f"  ❌ MF {scheme_code}: Error: {e}")
    return None


def fetch_all_mf_navs() -> List[Dict]:
    """Fetch NAV for all configured mutual funds."""
    results = []
    for name, code in MUTUAL_FUNDS.items():
        mf_data = fetch_mf_nav(code)
        if mf_data:
            mf_data["name"] = name
            results.append(mf_data)
    return results


# ==================== IPO DATA ====================

def fetch_ipos() -> List[Dict]:
    """
    Fetch Indian IPO data.
    Uses publicly available data sources.
    """
    # Note: For production, consider paid APIs like
    # MoneyControl or Trendlyne
    
    ipos = []
    
    # Try NSE IPO list
    try:
        url = "https://www.nseindia.com/corporates/securitiesInfo/corpInfoCorpActlties.jsp?security=ALL&segment=equities"
        headers = {"User-Agent": "Mozilla/5.0"}
        # This endpoint requires proper session - fallback to static
    except Exception:
        pass
    
    # Static IPO data (can be updated via API in production)
    # Recent IPOs (2023-2024)
    recent_ipos = [
        {"name": "Premier Energies", "symbol": "PREMIERENE", "listing_date": "2024-09-03", "issue_price": 1560, "status": "listed"},
        {"name": "Ola Electric", "symbol": "OLA", "listing_date": "2024-08-09", "issue_price": 76, "status": "listed"},
        {"name": "Bajaj Housing Finance", "symbol": "BAJAJHFL", "listing_date": "2024-09-16", "issue_price": 150, "status": "listed"},
        {"name": "PNC Infratech", "symbol": "PNCINFRA", "listing_date": "2024-05-14", "issue_price": 463, "status": "listed"},
        {"name": "Apex Frozen Foods", "symbol": "APEX", "listing_date": "2024-04-26", "issue_price": 160, "status": "listed"},
    ]
    
    # Upcoming IPOs
    upcoming_ipos = [
        {"name": "MGM Healthcare", "symbol": "MGMH", "status": "upcoming", "expected_date": "2025-Q1"},
        {"name": "Niva Bupa Health", "symbol": "NIVA", "status": "upcoming", "expected_date": "2025-Q1"},
    ]
    
    return recent_ipos + upcoming_ipos


# ==================== MARGIN TRADING FACILITY (MTF) ====================

def get_mtf_stocks() -> List[Dict]:
    """
    Get list of stocks eligible for MTF (Margin Trading Facility).
    Based on NSE/BSE eligibility criteria.
    """
    # Major stocks eligible for MTF (usually large caps with good liquidity)
    # In production, this would come from broker API
    
    mtf_eligible = [
        {"symbol": "RELIANCE", "name": "Reliance Industries", "margin": 50},
        {"symbol": "TCS", "name": "Tata Consultancy Services", "margin": 50},
        {"symbol": "HDFCBANK", "name": "HDFC Bank", "margin": 50},
        {"symbol": "INFY", "name": "Infosys", "margin": 50},
        {"symbol": "ICICIBANK", "name": "ICICI Bank", "margin": 50},
        {"symbol": "SBIN", "name": "State Bank of India", "margin": 50},
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel", "margin": 50},
        {"symbol": "BAJFINANCE", "name": "Bajaj Finance", "margin": 50},
        {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank", "margin": 50},
        {"symbol": "HINDUNILVR", "name": "Hindustan Unilever", "margin": 50},
        {"symbol": "TITAN", "name": "Titan Company", "margin": 50},
        {"symbol": "SUNPHARMA", "name": "Sun Pharma", "margin": 50},
    ]
    
    return mtf_eligible


# ==================== MARKET STATUS ====================

def get_market_status() -> Dict[str, str]:
    """Get status of Indian markets."""
    import datetime
    
    now = datetime.datetime.now(IST)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    time_val = hour * 60 + minute
    
    # NSE hours: 9:15 AM - 3:30 PM IST
    nse_open = 9 * 60 + 15
    nse_close = 15 * 60 + 30
    
    is_weekend = weekday >= 5
    is_trading_hours = nse_open <= time_val <= nse_close
    
    status = {
        "indian_equity": "CLOSED" if is_weekend or not is_trading_hours else "OPEN",
        "indian_fo": "CLOSED" if is_weekend or not is_trading_hours else "OPEN",
        " Weekend": "YES" if is_weekend else "NO",
        "next_open": "9:15 AM IST (Monday)" if is_weekend else "Next close: 3:30 PM IST",
    }
    
    return status


# ==================== CRYPTO (ZEBPAY ONLY - NO BINANCE) ====================

# ZebPay supported pairs (INR)
ZEBPAY_PAIRS = {
    "BTC": "BTC-INR",
    "ETH": "ETH-INR",
    "BNB": "BNB-INR",
    "SOL": "SOL-INR",
    "XRP": "XRP-INR",
    "ADA": "ADA-INR",
    "DOGE": "DOGE-INR",
    "DOT": "DOT-INR",
    "LINK": "LINK-INR",
    "AVAX": "AVAX-INR",
    "MATIC": "MATIC-INR",
    "NEAR": "NEAR-INR",
    "ATOM": "ATOM-INR",
    "LTC": "LTC-INR",
    "UNI": "UNI-INR",
}


def fetch_zebpay_crypto(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """
    Fetch crypto data from ZebPay only (no Binance fallback).
    """
    from zebpay_client import fetch_zebpay_klines
    
    # Map symbol to ZebPay pair
    clean_sym = symbol.upper().replace("USDT", "").replace("-INR", "")
    zeb_pair = ZEBPAY_PAIRS.get(clean_sym)
    
    if not zeb_pair:
        print(f"  ⚠ {symbol}: Not available on ZebPay")
        return None
    
    df = fetch_zebpay_klines(symbol, interval="1d")
    return df


# ==================== WRAPPER FUNCTION ====================

def fetch_market_data(symbol: str, market: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """
    Unified data fetch for all markets.
    market: 'equity' | 'fno' | 'crypto'
    """
    if market == "equity":
        return fetch_nse_data(symbol, period)
    elif market == "fno":
        return fetch_fno_data(symbol, period)
    elif market == "crypto":
        return fetch_zebpay_crypto(symbol, period)
    return None
