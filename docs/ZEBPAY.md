# ZebPay API — continued guide (for this project)

This doc continues from [ZebPay API docs](https://apidocs.zebpay.com/) / [docs.zebpay.com](https://docs.zebpay.com/) and explains **how it could map to IndoTradeBot** (signals vs execution).

## What the API is for (layers)

| Layer | Typical use |
|--------|-------------|
| **Public** endpoints | Tickers, order book, candles — no account needed. Good for **prices** and **backtesting-style** data. |
| **Private** endpoints | Balances, **place/cancel orders**, order history — needs **API keys + auth** (OAuth / tokens per their current docs). |
| **Spot** (`sapi`) | Spot trading vs **INR** (and related markets they list). |
| **Futures** (`futuresbe`) | Leveraged futures — separate product, separate risk. |

For **crypto**, this project uses ZebPay’s **public klines** (INR) — see `zebpay_client.py`. **Kline prices are in INR** (e.g. BTC-INR in the lakh/crore range). Reports use **₹** for crypto.

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

Public **klines** from ZebPay Spot (`GET /api/v2/market/klines`) — no API keys.  
**Exchange list:** `GET /api/v2/ex/exchangeInfo` — `fetch_zebpay_inr_base_assets()` returns every **Open** pair with **quote INR**. `fetch_zebpay_quicktrade_bases()` filters those to pairs that include **MARKET** in `orderTypes` (aligns with instant execution; QuickTrade list in the app may match this subset).

**Xpress (app):** The mobile **Xpress** INR list is not a separate field in `exchangeInfo`. This repo keeps a **curated** `ZEBPAY_XPRESS_DEFAULT_BASES` list (TURBO, PEPE, SHIB, …), intersects it with Open INR pairs, then **merges** with QuickTrade MARKET bases via `fetch_zebpay_xpress_merged_bases()`. Override the curated list with **`ZEBPAY_XPRESS_SYMBOLS`** (comma-separated bases).

| Variable | Meaning |
|----------|--------|
| `ZEBPAY_QUOTE=INR` | Bare symbols `FOO` → `FOO-INR`. |
| `ZEBPAY_SPOT_BASE` | Override API base (default `https://sapi.zebpay.com`). |
| `CRYPTO_WATCHLIST` | Comma list, e.g. `BTC,ETH,SOL`. If **unset**, watchlist is built from ZebPay (see below). |
| `CRYPTO_WATCHLIST_MODE` | **`xpress` (default)** — Xpress-style curated list + QuickTrade MARKET pairs, deduped. **`quicktrade`** — MARKET INR only (~7 symbols, faster). **`all`** — every Open INR base (capped). |
| `ZEBPAY_XPRESS_SYMBOLS` | Optional comma list of base symbols to **replace** the built-in Xpress list (still intersected with Open INR when the API works). |
| `CRYPTO_WATCHLIST_MAX` | Max symbols when auto-loading (default **120** for `xpress`, **40** for `quicktrade`; max **300**). |

Code: **`zebpay_client.py`**, **`data_fetcher.py`**, **`main.get_crypto_watchlist()`**.

**Symbols:** Use bare bases (`BTC`, `ETH`) or `BTCUSDT`-style; both map to **`BTC-INR`**.

If you want **order placement**, treat it as a **new feature** with explicit risk checks and kill-switch — not included here.
