"""
Market Depth & Order Book - ZebPay Only
No Binance - Indian market data only
"""

import requests
from typing import Dict, Optional

from zebpay_client import PAISA_TO_USD


def fetch_market_depth(symbol: str) -> Optional[Dict]:
    """
    Get market depth from ZebPay only.
    Returns bid/ask prices and spread for crypto.
    """
    from zebpay_client import binance_symbol_to_zebpay
    
    zeb_pair = binance_symbol_to_zebpay(symbol)
    url = "https://sapi.zebpay.com/api/v2/market/ticker"
    
    try:
        resp = requests.get(url, params={"symbol": zeb_pair}, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            
            bid = float(data.get("bid", 0)) * PAISA_TO_USD
            ask = float(data.get("ask", 0)) * PAISA_TO_USD
            last = float(data.get("last", 0)) * PAISA_TO_USD
            volume = float(data.get("volume24h", 0))
            
            spread = ask - bid if bid and ask else 0
            spread_pct = (spread / last * 100) if last else 0
            
            return {
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid_price": (bid + ask) / 2 if bid and ask else last,
                "spread": spread,
                "spread_pct": spread_pct,
                "volume_24h": volume,
                "source": "zebpay",
                "bid_volume": volume / 2,
                "ask_volume": volume / 2,
            }
    except Exception as e:
        print(f"  ⚠ {symbol}: ZebPay depth error: {e}")
    
    return None


def format_depth_report(depth: Dict, currency: str = "₹") -> str:
    """Format market depth for display."""
    if not depth:
        return "No market depth available"
    
    lines = [
        f"\n📊 Market Depth — {depth['symbol']}",
        "=" * 40,
        f"Last Price: {currency}{depth['last']:,.2f}",
        f"Bid:        {currency}{depth['bid']:,.2f}",
        f"Ask:        {currency}{depth['ask']:,.2f}",
        f"Spread:     {depth['spread']:.2f} ({depth['spread_pct']:.3f}%)",
        f"24h Volume: {depth['volume_24h']:,.2f}",
    ]
    
    # Bid/Ask imbalance
    bid_vol = depth.get('bid_volume', 0)
    ask_vol = depth.get('ask_volume', 0)
    total = bid_vol + ask_vol
    if total > 0:
        ratio = bid_vol / total
        if ratio > 0.6:
            lines.append("📈 Pressure: 🟢 Buying Pressure")
        elif ratio < 0.4:
            lines.append("📉 Pressure: 🔴 Selling Pressure")
        else:
            lines.append("⚖️ Pressure: Balanced")
    
    return "\n".join(lines)
