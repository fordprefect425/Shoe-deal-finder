# Shoe Deal Tracker Bot

A personal Telegram bot that monitors shoe prices across multiple e-commerce sites, compares deals, and sends you the best offer every day.

---

## Features

- ✅ Daily automated price checks (9 AM IST by default)
- ✅ Tracks multiple shoes across multiple sites per shoe
- ✅ Price drop alerts when a meaningful saving is detected
- ✅ Size availability checking (Puma, Myntra, Tata CLiQ)
- ✅ SQLite price history
- ✅ Manual trigger via `/check`
- ✅ Graceful failure — one broken site won't stop other checks

---

## Setup

### 1. Get your Telegram Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token**

### 2. Get your Chat ID

1. Message your new bot once
2. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": <YOUR_ID>}` in the response

### 3. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure

Edit `data/config.json`:

```json
{
  "telegram": {
    "bot_token": "YOUR_REAL_TOKEN",
    "chat_id": "YOUR_REAL_CHAT_ID"
  },
  ...
}
```

Add your shoes to `tracked_shoes` array. Each shoe needs:
- `id` — unique string
- `name` — display name
- `size` — your shoe size (e.g. `"11"`)
- `target_price` — alert when price drops below this (optional)
- `urls` — list of `{site_name, site_type, product_url}`

`site_type` is either `"requests"` (static pages) or `"playwright"` (JS-rendered pages).

### 5. Run

```bash
python main.py
```

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Introduction |
| `/list` | Show all tracked shoes |
| `/check` | Run a price check right now |
| `/best` | Show current best deals from DB |
| `/help` | Show all commands |

---

## Project Structure

```
shoe-deal-bot/
├── bot/
│   ├── commands.py        # Telegram command handlers
│   └── telegram_bot.py    # Bot setup + APScheduler
├── scrapers/
│   ├── base.py            # Abstract scraper contract
│   ├── generic.py         # Fallback (requests + BS4)
│   ├── puma.py            # Puma India (Playwright)
│   ├── myntra.py          # Myntra (Playwright)
│   ├── amazon.py          # Amazon India (requests + BS4)
│   ├── tatacliq.py        # Tata CLiQ (Playwright)
│   └── factory.py         # Scraper resolver
├── core/
│   ├── storage.py         # SQLite helpers
│   ├── ranking.py         # Deal comparison logic
│   ├── alerts.py          # Change detection + message formatting
│   └── checker.py         # Main orchestration
├── data/
│   ├── config.json        # Your config (fill this in)
│   └── prices.db          # Auto-created SQLite DB
├── logs/
│   └── bot.log            # Auto-created log file
├── tests/
│   └── test_core.py       # Unit tests
├── main.py
└── requirements.txt
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deployment 🚀

To run the bot 24/7 in the cloud:

1. **Easiest**: Use [Railway.app](https://railway.app). Connect your GitHub repo, add a **Volume** at `/app/data` for your database, and it will auto-deploy.
2. **Docker**: A `Dockerfile` is provided. You can run it anywhere that supports Docker:
   ```bash
   docker build -t shoebot .
   docker run -d shoebot
   ```

See the [Deployment Guide](file:///Users/apple/.gemini/antigravity/brain/75459d1b-7822-4fa6-86c0-45431f25662d/deployment_guide.md) for more details.

---

## Scraper Notes

| Site | Method | Size Check |
|------|--------|------------|
| Puma | Playwright | ✅ Yes |
| Myntra | Playwright | ✅ Yes |
| Tata CLiQ | Playwright | ✅ Yes |
| Amazon | requests + BS4 | ❌ No |
| Other | Generic (BS4) | ❌ No |

> **Note:** E-commerce sites frequently change their HTML structure. If a scraper stops working, update the CSS selectors in the relevant `scrapers/*.py` file.

---

## Troubleshooting

**Bot doesn't respond:** Check `logs/bot.log` and verify your token is correct.

**Price shows None:** The site's HTML changed. Update selectors in the relevant scraper file.

**Playwright fails:** Run `playwright install chromium` again.

**Anti-bot blocks:** Some sites (especially Amazon) may temporarily block requests. Try running again later or reduce check frequency.
