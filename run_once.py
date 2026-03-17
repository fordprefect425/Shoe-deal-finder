"""
run_once.py
A one-off script to run the shoe price check and exit.
Perfect for GitHub Actions or a cron job.
"""

import json
import logging
import os
import sys
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"config.json not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

async def main():
    config = load_config()
    
    # Initialize DB
    from core.storage import init_db
    init_db()

    # Create a simple sender function using the Telegram Bot API directly
    from telegram import Bot
    bot = Bot(token=config["telegram"]["bot_token"])

    async def send_fn(chat_id, text):
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    # Run the check
    from core.checker import run_check
    # We set force_summary=True so that every single run of this script sends a message
    results = await run_check(config, send_telegram_fn=send_fn, force_summary=True)
    
    # Detailed logging for GitHub Actions console
    for res in results:
        shoe_name = res["shoe_config"]["name"]
        best = res.get("best_offer")
        print(f"\nSHOE: {shoe_name}")
        if best:
            print(f"  ✅ Best Price: {best['price']} at {best['site_name']}")
        else:
            print(f"  ❌ No valid price found")
        
        for offer in res.get("all_offers", []):
            status = "OK" if not offer.get("error") else f"ERROR: {offer['error']}"
            price = offer.get("price", "N/A")
            print(f"    - {offer['site_name']}: {price} [{status}]")

    logger.info("One-off check complete.")

if __name__ == "__main__":
    asyncio.run(main())
