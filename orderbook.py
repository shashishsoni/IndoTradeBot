"""
Market depth — ZebPay Spot ticker (INR prices).
"""

from typing import Dict, Optional

from zebpay_client import fetch_zebpay_ticker


def fetch_market_depth(symbol: str) -> Optional[Dict]:
    """
    Best bid/ask / last from ZebPay public ticker. Prices in INR.
    """
    t = fetch_zebpay_ticker(symbol)
    if not t:
        return None

    bid = t.get("bid") or 0.0
    ask = t.get("ask") or 0.0
    last = t.get("last") or 0.0
    volume = float(t.get("volume_24h") or 0)

    spread = ask - bid if bid and ask else 0.0
    spread_pct = (spread / last * 100) if last else 0.0

    return {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid_price": (bid + ask) / 2 if bid and ask else last,
        "spread": spread,
        "spread_pct": spread_pct,
        "volume_24h": volume,
        "source": "zebpay_inr",
        "bid_volume": volume / 2 if volume else 0,
        "ask_volume": volume / 2 if volume else 0,
    }


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

    bid_vol = depth.get("bid_volume", 0)
    ask_vol = depth.get("ask_volume", 0)
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
