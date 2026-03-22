"""
Web Dashboard - Indian Markets Focus
No Binance - ZebPay only for crypto
Includes SEBI-compliant disclaimers
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template_string
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Indian Regulatory Compliant Dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndoTrade - Indian Market Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #0a0e17; 
            color: #e7e9ea;
            min-height: 100vh;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #0d47a1 50%, #002171 100%);
            padding: 25px;
            border-bottom: 3px solid #ff9800;
        }
        .header h1 { 
            color: #ff9800; 
            font-size: 2rem;
            font-weight: 700;
        }
        .header .subtitle { 
            color: #90caf9; 
            font-size: 1rem;
            margin-top: 5px;
        }
        
        /* Navigation */
        .nav {
            background: #1a237e;
            padding: 12px 25px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            border-bottom: 2px solid #ff9800;
        }
        .nav a {
            color: #fff;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 25px;
            background: rgba(255,255,255,0.1);
            transition: all 0.3s;
            font-weight: 500;
        }
        .nav a:hover, .nav a.active {
            background: #ff9800;
            color: #000;
        }
        
        /* Main Container */
        .container { 
            max-width: 1600px; 
            margin: 0 auto; 
            padding: 20px;
        }
        
        /* Market Status */
        .market-ticker {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin: 20px 0;
        }
        .ticker-item {
            background: #1a237e;
            padding: 12px 20px;
            border-radius: 8px;
            border-left: 4px solid #ff9800;
        }
        .ticker-item.closed {
            border-left-color: #f44336;
        }
        .ticker-item .label { color: #90caf9; font-size: 0.85rem; }
        .ticker-item .value { font-weight: bold; font-size: 1.1rem; }
        
        /* Grid Layout */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        /* Cards */
        .card {
            background: #121824;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a3f5f;
        }
        .card h3 {
            color: #ff9800;
            margin-bottom: 15px;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Signal Colors */
        .signal-buy { color: #4caf50; font-weight: bold; }
        .signal-sell { color: #f44336; font-weight: bold; }
        .signal-hold { color: #ffc107; }
        
        /* Price Changes */
        .price-up { color: #4caf50; }
        .price-down { color: #f44336; }
        
        /* Tables */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .data-table th, .data-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #2a3f5f;
        }
        .data-table th { 
            color: #90caf9; 
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        .data-table tr:hover {
            background: rgba(255,152,0,0.1);
        }
        
        /* Probability Bar */
        .prob-bar {
            height: 20px;
            background: #1a237e;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }
        .prob-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.5s;
        }
        .prob-low { background: linear-gradient(90deg, #f44336, #ff5722); }
        .prob-medium { background: linear-gradient(90deg, #ff9800, #ffc107); }
        .prob-high { background: linear-gradient(90deg, #4caf50, #8bc34a); }
        
        /* Risk Badge */
        .risk-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .risk-low { background: #4caf50; color: #fff; }
        .risk-medium { background: #ff9800; color: #000; }
        .risk-high { background: #f44336; color: #fff; }
        
        /* Disclaimer */
        .disclaimer {
            background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
            border: 2px solid #ff9800;
            padding: 20px;
            border-radius: 12px;
            margin-top: 30px;
        }
        .disclaimer h4 {
            color: #ff9800;
            margin-bottom: 10px;
        }
        .disclaimer ul {
            margin-left: 20px;
            color: #e7e9ea;
        }
        .disclaimer li {
            margin: 8px 0;
            font-size: 0.9rem;
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 40px;
            color: #90caf9;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .nav { justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🇮🇳 IndoTrade - Indian Market Dashboard</h1>
        <div class="subtitle">SEBI-Compliant Algorithmic Analysis | Not Financial Advice</div>
    </div>
    
    <div class="nav">
        <a href="/" class="active">📊 Dashboard</a>
        <a href="/equity">📈 Equity</a>
        <a href="/fno">📊 F&O</a>
        <a href="/mf">💰 Mutual Funds</a>
        <a href="/ipo">🏢 IPOs</a>
        <a href="/mtf">🏦 MTF</a>
        <a href="/crypto">₿ Crypto (ZebPay)</a>
    </div>
    
    <div class="container">
        <!-- Market Status -->
        <div class="market-ticker" id="marketStatus">
            <div class="ticker-item">
                <div class="label">🇮🇳 NSE/BSE</div>
                <div class="value" id="nseStatus">Loading...</div>
            </div>
            <div class="ticker-item">
                <div class="label">📊 F&O</div>
                <div class="value" id="foStatus">Loading...</div>
            </div>
            <div class="ticker-item">
                <div class="label">₿ Crypto (ZebPay)</div>
                <div class="value">Open 24/7</div>
            </div>
        </div>
        
        <div class="grid">
            <!-- Equity Signals -->
            <div class="card">
                <h3>📈 Indian Equity Signals</h3>
                <div id="equitySignals">
                    <div class="loading">Loading NSE data...</div>
                </div>
            </div>
            
            <!-- F&O Signals -->
            <div class="card">
                <h3>📊 F&O Signals</h3>
                <div id="foSignals">
                    <div class="loading">Loading F&O data...</div>
                </div>
            </div>
            
            <!-- Mutual Funds -->
            <div class="card">
                <h3>💰 Mutual Fund NAVs</h3>
                <div id="mfData">
                    <div class="loading">Loading MF data...</div>
                </div>
            </div>
            
            <!-- IPOs -->
            <div class="card">
                <h3>🏢 IPO Tracker</h3>
                <div id="ipoData">
                    <div class="loading">Loading IPO data...</div>
                </div>
            </div>
            
            <!-- Risk Dashboard -->
            <div class="card">
                <h3>⚠️ Risk Dashboard</h3>
                <div id="riskDashboard">
                    <div class="loading">Loading...</div>
                </div>
            </div>
            
            <!-- Market Overview -->
            <div class="card">
                <h3>📊 Market Overview</h3>
                <div id="marketOverview">
                    <div class="loading">Loading...</div>
                </div>
            </div>
        </div>
        
        <!-- SEBI Disclaimer -->
        <div class="disclaimer">
            <h4>⚠️ SEBI REGULATORY DISCLAIMER</h4>
            <ul>
                <li><strong>Not Financial Advice:</strong> This is algorithmic analysis only. Not registered with SEBI as an Investment Advisor.</li>
                <li><strong>No Guaranteed Returns:</strong> Past performance does not guarantee future results. Market investments carry risk.</li>
                <li><strong>Crypto Warning:</strong> RBI has advised against trading in cryptocurrencies (Circular dated 31-03-2020).</li>
                <li><strong>F&O Risk:</strong> Futures & Options trading involves substantial risk. Not suitable for all investors.</li>
                <li><strong>Verify Before Trading:</strong> Consult SEBI-registered Investment Advisor before making decisions.</li>
                <li><strong>Margin Trading:</strong> MTF involves borrowing funds - risk of loss exceeds capital invested.</li>
            </ul>
            <p style="margin-top:15px;color:#90caf9;font-size:0.85rem;">
                <strong>Compliance:</strong> This platform does not hold SEBI registration. Use at your own risk.
            </p>
        </div>
    </div>
    
    <script>
        async function fetchAPI(url) {
            try {
                const resp = await fetch(url);
                return await resp.json();
            } catch (e) {
                console.error(e);
                return null;
            }
        }
        
        async function loadDashboard() {
            // Market Status
            const status = await fetchAPI('/api/market-status');
            if (status) {
                document.getElementById('nseStatus').textContent = status.indian_equity === 'OPEN' ? '🟢 OPEN' : '🔴 CLOSED';
                document.getElementById('nseStatus').parentElement.className = status.indian_equity === 'OPEN' ? 'ticker-item' : 'ticker-item closed';
                document.getElementById('foStatus').textContent = status.indian_fo === 'OPEN' ? '🟢 OPEN' : '🔴 CLOSED';
            }
            
            // Equity Signals
            const equity = await fetchAPI('/api/signals/equity');
            if (equity && equity.length > 0) {
                let html = '<table class="data-table"><tr><th>Stock</th><th>Signal</th><th>Price</th><th>Probability</th></tr>';
                equity.slice(0, 8).forEach(s => {
                    const probClass = s.probability >= 70 ? 'prob-high' : s.probability >= 50 ? 'prob-medium' : 'prob-low';
                    html += `<tr>
                        <td>${s.symbol}</td>
                        <td class="signal-${s.signal.toLowerCase()}">${s.signal}</td>
                        <td>₹${s.price?.toFixed(2) || 'N/A'}</td>
                        <td>
                            <div class="prob-bar"><div class="prob-fill ${probClass}" style="width:${s.probability}%"></div></div>
                            <small>${s.probability}%</small>
                        </td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('equitySignals').innerHTML = html;
            } else {
                document.getElementById('equitySignals').innerHTML = '<p style="color:#90caf9">Market closed or no signals</p>';
            }
            
            // F&O Signals
            const fno = await fetchAPI('/api/signals/fno');
            if (fno && fno.length > 0) {
                let html = '<table class="data-table"><tr><th>Index</th><th>Signal</th><th>Level</th><th>Risk</th></tr>';
                fno.slice(0, 5).forEach(s => {
                    html += `<tr>
                        <td>${s.symbol}</td>
                        <td class="signal-${s.signal.toLowerCase()}">${s.signal}</td>
                        <td>₹${s.price?.toFixed(0) || 'N/A'}</td>
                        <td><span class="risk-badge risk-${s.risk_level.toLowerCase()}">${s.risk_level}</span></td>
                    </tr>`;
                });
                html += '</table>';
                document.getElementById('foSignals').innerHTML = html;
            }
            
            // Mutual Funds
            const mf = await fetchAPI('/api/mutual-funds');
            if (mf && mf.length > 0) {
                let html = '<table class="data-table"><tr><th>Scheme</th><th>NAV</th><th>Date</th></tr>';
                mf.slice(0, 5).forEach(m => {
                    html += `<tr><td>${m.name}</td><td>₹${m.nav?.toFixed(2) || 'N/A'}</td><td>${m.date || 'N/A'}</td></tr>`;
                });
                html += '</table>';
                document.getElementById('mfData').innerHTML = html;
            }
            
            // IPOs
            const ipo = await fetchAPI('/api/ipos');
            if (ipo && ipo.length > 0) {
                let html = '<table class="data-table"><tr><th>Name</th><th>Status</th><th>Price</th></tr>';
                ipo.slice(0, 5).forEach(i => {
                    html += `<tr><td>${i.name}</td><td>${i.status === 'listed' ? '✅ Listed' : '📅 Upcoming'}</td><td>₹${i.issue_price || 'TBD'}</td></tr>`;
                });
                html += '</table>';
                document.getElementById('ipoData').innerHTML = html;
            }
            
            // Risk
            const risk = await fetchAPI('/api/risk');
            if (risk) {
                const dd = (risk.drawdown * 100).toFixed(1);
                const wr = (risk.win_rate * 100).toFixed(1);
                let ddClass = dd < 5 ? 'price-up' : dd < 10 ? '' : 'price-down';
                document.getElementById('riskDashboard').innerHTML = `
                    <table class="data-table">
                        <tr><td>Capital</td><td>₹${risk.capital?.toLocaleString()}</td></tr>
                        <tr><td>Drawdown</td><td class="${ddClass}">${dd}%</td></tr>
                        <tr><td>Win Rate</td><td>${wr}%</td></tr>
                        <tr><td>Active Signals</td><td>${risk.active_signals}</td></tr>
                        <tr><td>Total Trades</td><td>${risk.total_trades}</td></tr>
                    </table>
                `;
            }
        }
        
        // Initial Load
        loadDashboard();
        
        // Auto-refresh every 2 minutes
        setInterval(loadDashboard, 120000);
    </script>
</body>
</html>
"""

# Flask App
app = Flask(__name__)


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/market-status")
def api_market_status():
    """Get Indian market status."""
    from data_sources import get_market_status
    return jsonify(get_market_status())


@app.route("/api/signals/equity")
def api_equity_signals():
    """Get equity signals."""
    # This would integrate with the signal engine
    return jsonify([])


@app.route("/api/signals/fno")
def api_fno_signals():
    """Get F&O signals."""
    return jsonify([])


@app.route("/api/mutual-funds")
def api_mutual_funds():
    """Get mutual fund NAVs."""
    from data_sources import fetch_all_mf_navs
    try:
        mfs = fetch_all_mf_navs()
        return jsonify(mfs)
    except Exception:
        return jsonify([])


@app.route("/api/ipos")
def api_ipos():
    """Get IPO data."""
    from data_sources import fetch_ipos
    try:
        return jsonify(fetch_ipos())
    except Exception:
        return jsonify([])


@app.route("/api/risk")
def api_risk():
    """Get risk dashboard."""
    return jsonify({
        "capital": 100000,
        "drawdown": 0.05,
        "win_rate": 0.55,
        "active_signals": 0,
        "total_trades": 0,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now(IST).isoformat()})


def start_dashboard(port=10000):
    """Start the web dashboard."""
    print(f"🌐 Starting Indian Market Dashboard on port {port}")
    print(f"   Dashboard: http://localhost:{port}/")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    start_dashboard()
