"""
main.py
Entry point: load config, init DB, start bot.
"""

import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        logger.error("config.json not found at %s", CONFIG_PATH)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict) -> None:
    token = config.get("telegram", {}).get("bot_token", "")
    chat_id = config.get("telegram", {}).get("chat_id", "")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set your Telegram bot_token in data/config.json")
        sys.exit(1)
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        logger.error("Please set your Telegram chat_id in data/config.json")
        sys.exit(1)
    shoes = config.get("tracked_shoes", [])
    if not shoes:
        logger.warning("No tracked shoes configured — add entries to data/config.json")


def main():
    os.makedirs("logs", exist_ok=True)
    config = load_config()
    validate_config(config)

    from core.storage import init_db
    init_db()
    logger.info("Starting Shoe Deal Tracker Bot...")

    from bot.telegram_bot import start_bot
    start_bot(config)


if __name__ == "__main__":
    main()
