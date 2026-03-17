"""
bot/commands.py
Telegram command handler functions.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


def make_handlers(config: dict, run_check_fn, get_best_fn):
    """
    Factory that returns all command handler coroutines,
    closing over config and dependency functions.
    """

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "👟 *Shoe Deal Tracker Bot*\n\n"
            "I monitor shoe prices across multiple sites and send you the best deal daily.\n\n"
            "*Commands:*\n"
            "/list — Show all tracked shoes\n"
            "/check — Run a manual price check now\n"
            "/best — Show current best deals\n"
            "/help — Show this help message\n"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "*Available Commands:*\n\n"
            "/start — Introduction\n"
            "/list — Show tracked shoes\n"
            "/check — Manual check now\n"
            "/best — Current best deals\n"
            "/help — This help message\n"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def list_shoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
        shoes = config.get("tracked_shoes", [])
        if not shoes:
            await update.message.reply_text("No shoes are currently tracked.")
            return

        lines = ["*Tracked Shoes:*\n"]
        for i, shoe in enumerate(shoes, 1):
            active = "✅" if shoe.get("is_active", True) else "⏸"
            lines.append(f"{active} *{i}. {shoe['name']}* — Size {shoe.get('size', '?')}")
            if shoe.get("target_price"):
                lines.append(f"   🎯 Target: ₹{shoe['target_price']:,}")
            urls = shoe.get("urls", [])
            site_names = ", ".join(u["site_name"] for u in urls)
            lines.append(f"   🌐 Sites: {site_names}")
            lines.append("")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Running price check... this may take a minute.")
        try:
            async def send_fn(chat_id, text):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )

            results = await run_check_fn(config, send_telegram_fn=send_fn, force_summary=True)
            found_count = sum(1 for r in results if r.get("best_offer"))
            await update.message.reply_text(
                f"✅ Check complete! Found deals for {found_count}/{len(results)} shoes.\nSummary sent above."
            )
        except Exception as exc:
            logger.error("Manual check failed: %s", exc, exc_info=True)
            await update.message.reply_text(f"❌ Check failed: {exc}")

    async def best(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            lines = await get_best_fn(config)
            if not lines:
                await update.message.reply_text("No price data yet. Run /check first.")
                return
            await update.message.reply_text(
                lines,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.error("Best command failed: %s", exc)
            await update.message.reply_text(f"❌ Error: {exc}")

    return {
        "start": start,
        "help": help_cmd,
        "list": list_shoes,
        "check": check_now,
        "best": best,
    }
