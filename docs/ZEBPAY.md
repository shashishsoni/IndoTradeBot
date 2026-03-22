# ZebPay API — continued guide (for this project)

This doc continues from [ZebPay API docs](https://apidocs.zebpay.com/) / [docs.zebpay.com](https://docs.zebpay.com/) and explains **how it could map to IndoTradeBot** (signals vs execution).

## What the API is for (layers)

| Layer | Typical use |
|--------|-------------|
| **Public** endpoints | Tickers, order book, candles — no account needed. Good for **prices** and **backtesting-style** data. |
| **Private** endpoints | Balances, **place/cancel orders**, order history — needs **API keys + auth** (OAuth / tokens per their current docs). |
| **Spot** (`sapi`) | Spot trading vs **INR** (and related markets they list). |
| **Futures** (`futuresbe`) | Leveraged futures — separate product, separate risk. |

Your bot today **does not** call ZebPay; it uses other sources for crypto/equity **analysis only**. ZebPay APIs are relevant if you want **INR prices from ZebPay** or **automated trading on ZebPay**.

## How this differs from your current bot

- **IndoTradeBot now:** generates **BUY/SELL/HOLD** signals + risk rules; **no exchange orders**.
- **With ZebPay:** you could add an optional **execution layer** (submit orders, track fills) — that is **real money** and needs careful testing, limits, and compliance.

Do **not** wire live trading until you understand fees, slippage, and their [terms](https://zebpay.com/) / KYC rules.

## Practical next steps (if you integrate)

1. **Register** on [ZebPay Build](https://build.zebpay.com/) (or current developer portal) and **create an app** to get **client ID / secret** (or whatever their current flow uses).
2. Read **Authentication** in their docs: token lifetime, refresh, **IP whitelisting** for production.
3. Start with **read-only** calls: **balance** or **market data** only (no orders).
4. Add **sandbox / test** mode if they offer it; otherwise use **minimum size** orders on mainnet.
5. In code, keep **exchange code separate** (`zebpay_client.py`) with:
   - timeouts, retries, rate-limit handling
   - **no secrets in git** — use `.env` / Render env vars

## Official references

- [apidocs.zebpay.com](https://apidocs.zebpay.com/) — interactive API reference  
- [docs.zebpay.com](https://docs.zebpay.com/) — documentation hub  
- [ZebPay API services (spot & futures)](https://zebpay.com/api-services-for-spot-and-futures) — product overview  
- [Help: ZebPay APIs](https://help.zebpay.com/support/solutions/articles/44000886589-zebpay-apis) — access & support  
- [GitHub: zebpay-api-references](https://github.com/zebpay/zebpay-api-references) — examples / base URLs (verify against official docs; versions change)

## Implemented in this repo (optional)

Public **klines** from ZebPay Spot are wired behind env flags (no API keys).

| Variable | Meaning |
|----------|--------|
| `CRYPTO_DATA_SOURCE=zebpay` | Use ZebPay `GET /api/v2/market/klines` for crypto OHLCV instead of Binance. |
| `ZEBPAY_FALLBACK_BINANCE=1` | If ZebPay returns nothing for a symbol, fall back to Binance (default **on**). |
| `ZEBPAY_QUOTE=INR` | For unmapped symbols `FOOUSDT` → `FOO-INR`. |
| `ZEBPAY_SPOT_BASE` | Override base URL (default `https://sapi.zebpay.com`). |

Code: **`zebpay_client.py`** (mapping + fetch), **`data_fetcher.py`** (`fetch_crypto_data`).

**Note:** Watchlist symbols stay `BTCUSDT`-style; they map to **`BTC-INR`** etc. Altcoins without an INR pair on ZebPay may need a manual mapping or will use Binance fallback.

If you want **order placement**, treat it as a **new feature** with explicit risk checks and kill-switch — not included here.
