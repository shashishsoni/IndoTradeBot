# Deploy on Render (free **Web Service**)

Render’s **Web Service** must listen on **`$PORT`** (health checks). This project includes **`serve`** mode: a tiny HTTP server on `/` and `/health`, plus the **same** trading daemon as **`auto`** (same flags, same loop), running in a **background thread**.

So **`serve`** *is* auto-scanning — it is not a different strategy. Example:

- `python main.py serve -i 5 -t -m equity crypto`  
  → same scans as `python main.py auto -i 5 -t -m equity crypto`, **plus** HTTP for Render.

## Use **`python main.py serve`** (not plain `auto` on Web Service)

| Wrong on Web Service | Right |
|----------------------|--------|
| `python main.py auto ...` only (no HTTP) | `python main.py serve ...` (HTTP + bot) |

If you only run `auto` on a Web Service, you may see:

- `No open ports detected`
- `Port scan timeout reached`
- `Timed Out`

### Steps

1. Render Dashboard → **New +** → **Web Service** (free tier if available on your account).
2. Connect your repo and branch.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python -u main.py serve -i 5 -t -m equity crypto`  
   (`-u` = unbuffered logs; same flags as `auto`: interval, `-t` Telegram, `-m` markets.)
5. **Environment** → add secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `CAPITAL` (e.g. `1000`)
6. Deploy. Open your service URL — you should see `OK - IndoTradeBot` on `/` or `/health`.

### Blueprint from repo

`render.yaml` uses `type: web` and `startCommand: python -u main.py serve ...`.

### Local test (optional)

```bash
set PORT=8080
python main.py serve -i 15
# Visit http://127.0.0.1:8080/health
```

### Alternative: Background Worker

If your Render plan includes **Background Workers** and you prefer no HTTP, you can use `python main.py auto ...` with `type: worker` in `render.yaml` instead — no `$PORT` required.

### Optional: Python version

This repo includes `runtime.txt` to pin a stable Python (e.g. 3.12). Render will use it when supported.

---

## Logs & notifications (troubleshooting)

### Where are logs?

This deploy is a **Web Service**, not a Background Worker. Open **Render Dashboard → your service (`trading-bot`) → Logs**. You should see:

- HTTP lines when something hits `/` or `/health`
- `TRADING SIGNAL DAEMON STARTED`, scan lines, and Telegram status from the **daemon thread**

If logs looked **empty** before: Python was **buffering** stdout. The repo now uses **`python -u`**, **`PYTHONUNBUFFERED=1`**, and line-buffered stdout so thread output shows up. **Redeploy** after pulling the latest changes.

### Telegram: no messages

1. **Secrets on Render** — `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be set under **Environment** (not only in local `.env`). Redeploy after saving.
2. **Startup ping** — After deploy you should get **one Telegram message**: *“daemon started on server”*. If you never get that, the token/chat id is wrong or the bot is blocked — check Logs for `Telegram API error`.
3. **Scan reports** — A full report is sent **after each scan** only when the scan returns **at least one symbol with data**. If every fetch fails (network, rate limits), you get **no scan message** until data works — but you should still see errors in **Logs**.
4. **Chat with the bot** — Open your bot in Telegram and tap **Start** once so the bot can message you.

### Free tier: service “sleeps”

On **Render free** Web Services, the instance often **spins down** after ~15 minutes **without incoming HTTP traffic**. While sleeping, **nothing runs** (no scans, no Telegram). To keep it awake, use a free external monitor (e.g. UptimeRobot, cron-job.org) to **GET** `https://YOUR-SERVICE.onrender.com/health` every **10–14 minutes**. For true 24/7 without pings, use a **paid** instance or a **Background Worker** if included on your plan.
