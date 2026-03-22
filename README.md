# Trading Signal Analyzer

Structured BUY / SELL / HOLD signal generator for **Indian equities (NSE/BSE)** and **global cryptocurrency** markets.

## Setup (virtual environment)

**Windows (PowerShell)** — from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Use **`python -m pip`** (not bare `pip`) so packages install into the same interpreter you run with `python`.

**Windows (cmd.exe):**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After activation, your prompt usually shows `(.venv)`.

### Windows: `python3` not found?

On Windows, use **`python`** (not `python3`). The Store alias for `python3` may show “Python was not found”.

```powershell
python --version
python -m venv .venv
```

If you have the **Python Launcher** installed:

```powershell
py -3 -m venv .venv
```

If `python` also fails, install Python from [python.org](https://www.python.org/downloads/) and check **“Add python.exe to PATH”** during setup, or turn off **App execution aliases** for `python.exe` / `python3.exe` under *Settings → Apps → Advanced app settings → App execution aliases*.

## Usage

### Interactive Mode

```bash
python main.py
```

This opens a REPL with full access to all commands:

| Command | Description |
|---|---|
| `analyze RELIANCE equity` | Analyze an NSE stock (blocked Sat/Sun & outside 9:15–3:30 IST) |
| `analyze RELIANCE equity --force` | Same, but allowed off-hours/weekend (research only) |
| `analyze BTCUSDT crypto` | Analyze a crypto pair (24/7; no weekend block) |
| `scan equity` / `scan crypto` | Full ranked report in console; add **`-t`** or **`--telegram`** to also send that report to Telegram |
| `risk` | Show risk management dashboard |
| `capital 500000` | Set trading capital |
| `result RELIANCE 2500` | Record trade P&L |
| `reset-review` | Exit review mode after analysis |
| `reset-halt` | Resume after drawdown halt |
| `watchlist` | Show default watchlists |

### Single Analysis (CLI)

```bash
python main.py RELIANCE equity
python main.py BTCUSDT crypto
```

### Detailed scan output (`scan equity` / `scan crypto`)

Each scan prints:

1. **Per-symbol line** — signal and confidence.  
2. **Highest-confidence BUY list** and **SELL list** — which names to research first for longs vs shorts.  
3. **“TOP BUY / TOP SELL PICK”** — single best name in each direction this run.  
4. **Entry focus table** — entry zone and stop for every symbol (sorted by confidence).  
5. **Strong signal guide** — how professionals often combine RSI, MACD, and volume (see references below).  
6. **Full signal report** for the highest-confidence actionable symbol (or highest HOLD if everything is HOLD).

**Further reading (external, not affiliated):**

- [Investing.com Academy — RSI and MACD together](https://www.investing.com/academy/analysis/how-to-use-rsi-and-macd-together/)  
- RSI + volume / avoiding false signals: search for “RSI volume confirmation” on reputable TA sites.

This tool **does not** guarantee which stock to buy; it **ranks** candidates from your watchlist so you know where to look first.

## Architecture

```
tradingBot/
├── config.py          # All thresholds, enums, and the TradeSignal dataclass
├── data_fetcher.py    # yfinance (equities) + ZebPay Spot INR (crypto) + market data
├── indicators.py      # EMA, RSI, MACD, Bollinger Bands, ATR, OBV
├── market_context.py  # Timing windows, event filters, India/crypto specifics
├── signal_engine.py   # Core signal generation combining all indicators
├── scan_report.py     # Detailed scan rankings, entry table, strong-signal education text
├── risk_manager.py    # Position sizing, drawdown tracking, review/halt mode
├── formatter.py       # Structured output matching the signal report template
├── notifier.py        # Telegram alerts
├── main.py            # CLI entry point (interactive + single-shot + auto)
├── zebpay_client.py   # ZebPay public Spot API (INR pairs, klines)
└── requirements.txt
```

## Signal Output Format

Every signal includes: asset, direction, entry zone, stop loss, two targets, timeframe, confidence (1-10), invalidation level, and 3+ technical + 1 fundamental reason.

## Automated Mode (Daemon)

Run the bot continuously to automatically scan markets and send alerts:

```powershell
# Scan every 15 minutes (default)
python main.py auto

# Scan every 5 minutes
python main.py auto --interval 5

# Scan with Telegram notifications
python main.py auto --telegram

# Scan specific markets
python main.py auto --interval 15 --markets equity crypto
python main.py auto -i 5 -m crypto  # Crypto only, 5 min interval

# Full options
python main.py auto -i 15 -t -m equity crypto
```

### Environment Variables

**`.env` in the project folder** (same folder as `main.py`) is **loaded automatically** when you run the app — no need to export variables manually, as long as you have `python-dotenv` installed (`pip install -r requirements.txt`).

Example `.env` (no spaces around `=`; no quotes needed unless the value has spaces):

```env
TELEGRAM_BOT_TOKEN=123456789:AA...your_token
TELEGRAM_CHAT_ID=123456789
CAPITAL=1000
```

**`CAPITAL` (or `TRADING_CAPITAL`)** — Trading account size in ₹ for position sizing.  
Because **`risk_state.json` is gitignored**, production (Render, VPS, etc.) usually has **no** saved file on first deploy. In that case the app reads **`CAPITAL` from the environment** (set it in the Render dashboard or `.env` on the server). Example: `CAPITAL=1000` for ₹1,000.

If a **`risk_state.json` file already exists** (e.g. on your PC), that file wins unless you set **`FORCE_CAPITAL_FROM_ENV=1`** to reset capital from env.

If Telegram still says “not configured”, check: **file is named `.env`**, it lives next to `main.py`, you **restarted** the process after editing, and you ran **`pip install python-dotenv`**.

Alternatively set variables in the shell for that session only:

```powershell
# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
python main.py auto --telegram
```

### Telegram Setup

1. **Create Bot**: Message @BotFather on Telegram, use /newbot command
2. **Get Chat ID**: Open Telegram **as your personal account** and message **@userinfobot** — copy the numeric **Id** (e.g. `123456789`).  
   - Do **not** use another bot’s id or your bot’s username as “chat id” — if you see `403 Forbidden: bots can't send messages to bots`, your `TELEGRAM_CHAT_ID` is wrong.
3. **First contact**: Open your new bot in Telegram and tap **Start** once so the bot can message you.
4. **Configure**: Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env` **or** set them as environment variables (see above)

### What Happens in Auto Mode

- Scans all 20 Indian equity stocks and the crypto watchlist (default: **Xpress**-style INR list + QuickTrade MARKET pairs; override with `CRYPTO_WATCHLIST` / `CRYPTO_WATCHLIST_MODE`)
- With `--telegram` / `-t`: after each scan, sends the **full detailed report** to Telegram (rankings, entry table, strong-signal guide, full signal on top pick) — split into multiple messages if very long
- Prevents spam with 5-minute cooldown per asset
- Console still shows the same detailed output locally
- Press Ctrl+C to stop

## Deploy on Render

**Free Web Service:** use **`python main.py serve ...`** — it binds HTTP to **`$PORT`** (`/` = **Flask HTML homepage**; `/health` = JSON) and runs the same scan loop as `auto` in a **background thread**.

- Plain **`python main.py auto`** on a Web Service will fail (*“No open ports detected”*) because there is no HTTP listener.
- See **`DEPLOY_RENDER.md`** for step-by-step; **`render.yaml`** uses `type: web` and `serve`.
- If your plan includes **Background Workers**, you can use `auto` with `type: worker` instead (no HTTP needed).

## ZebPay (public market data)

Crypto OHLCV is **always** from **ZebPay Spot (INR)** — prices and Telegram reports use **₹**.

See **`docs/ZEBPAY.md`** for env vars, symbol mapping (`BTCUSDT` → `BTC-INR`), watchlist modes (**`CRYPTO_WATCHLIST_MODE=xpress`** default: Xpress-style list + QuickTrade; use **`quicktrade`** for a short ~7-symbol scan), and limits. **Order placement** is not implemented; use ZebPay’s private API only in a separate, audited module if you add it later.

## Risk Management

- Max 2% capital at risk per trade
- Max 3 simultaneous signals
- 3 consecutive losses → automatic review mode
- 10% drawdown → all signals halted until human review
- Position sizing: `(Capital × 0.02) ÷ (Entry − Stop Loss) = Units`

## Disclaimer

This tool provides algorithmic analysis, not financial advice. Past performance does not guarantee future results. Never risk more than you can afford to lose.
