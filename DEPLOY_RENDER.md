# Deploy on Render (free **Web Service**)

Render’s **Web Service** must listen on **`$PORT`** (health checks). This project includes **`serve`** mode: a tiny HTTP server on `/` and `/health`, plus the same trading daemon as `auto`, running in a **background thread**.

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
4. **Start command:** `python main.py serve -i 5 -t -m equity crypto`  
   (same flags as `auto`: interval, `-t` Telegram, `-m` markets.)
5. **Environment** → add secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `CAPITAL` (e.g. `1000`)
6. Deploy. Open your service URL — you should see `OK - IndoTradeBot` on `/` or `/health`.

### Blueprint from repo

`render.yaml` uses `type: web` and `startCommand: python main.py serve ...`.

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
