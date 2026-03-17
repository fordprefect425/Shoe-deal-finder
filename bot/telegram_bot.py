"""
bot/telegram_bot.py
Sets up and starts the Telegram bot with APScheduler for daily runs.
"""

import logging
from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.commands import make_handlers
from core.checker import run_check
from core import storage
from core.ranking import rank_offers
from core.alerts import format_daily_summary

logger = logging.getLogger(__name__)


async def _get_best_deals(config: dict) -> str:
    """Load latest snapshots from DB and format as a summary string."""
    from core.alerts import format_daily_summary
    from core.ranking import get_best_deal

    results = []
    for shoe in config.get("tracked_shoes", []):
        if not shoe.get("is_active", True):
            continue
        snapshots = storage.get_last_snapshots_for_shoe(shoe["id"])
        offers = [
            {
                "price": s["price"],
                "in_stock": bool(s.get("in_stock")),
                "size_available": s.get("size_available"),
                "site_name": s.get("site_name"),
                "product_url": s.get("product_url"),
            }
            for s in snapshots if s.get("price")
        ]
        best = get_best_deal(offers)
        results.append({
            "shoe_config": shoe,
            "best_offer": best,
            "previous_price": None,
            "all_offers": offers,
        })

    if not results:
        return "No saved data. Run /check first."

    return format_daily_summary(results)


def start_bot(config: dict) -> None:
    """Build app, register handlers, start scheduler, and begin polling."""
    token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    schedule_cfg = config.get("schedule", {})

    handlers = make_handlers(config, run_check, _get_best_deals)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", handlers["start"]))
    app.add_handler(CommandHandler("help", handlers["help"]))
    app.add_handler(CommandHandler("list", handlers["list"]))
    app.add_handler(CommandHandler("check", handlers["check"]))
    app.add_handler(CommandHandler("best", handlers["best"]))

    # APScheduler daily run
    scheduler = AsyncIOScheduler()

    tz_name = schedule_cfg.get("timezone", "Asia/Kolkata")
    tz = pytz.timezone(tz_name)

    async def daily_job():
        logger.info("Scheduled daily run starting...")
        async def send_fn(cid, text):
            await app.bot.send_message(
                chat_id=cid,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        await run_check(config, send_telegram_fn=send_fn)

    scheduler.add_job(
        daily_job,
        CronTrigger(
            hour=schedule_cfg.get("hour", 9),
            minute=schedule_cfg.get("minute", 0),
            timezone=tz,
        ),
        id="daily_shoe_check",
        replace_existing=True,
    )

    logger.info(
        "Scheduler set for %02d:%02d %s",
        schedule_cfg.get("hour", 9),
        schedule_cfg.get("minute", 0),
        tz_name,
    )

    async def on_startup(_app):
        scheduler.start()

    app.post_init = on_startup
    app.run_polling(drop_pending_updates=True)
